"""Fail-closed controls for a short-lived, single-teacher demonstration."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sqlite3
import threading
import time
from collections import deque
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

MAX_ANALYSES = 2
TOKEN_LIFETIME_SECONDS = 8 * 60 * 60
MAX_PROMPT_UTF8_BYTES = 32000
MAX_OUTPUT_TOKENS = 600
RATE_WINDOW_SECONDS = 60
API_REQUESTS_PER_WINDOW = 120
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_ATTEMPTS_PER_WINDOW = 5


def _utc_iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat().replace("+00:00", "Z")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class TeacherDemoGuard:
    """Persistent lifetime quota and stateless, short-lived HMAC bearer tokens."""

    def __init__(self, settings: Any):
        self.settings = settings
        self.enabled = bool(settings.teacher_demo_enabled)
        self.database = Path(settings.data_dir) / "teacher-demo-guard.sqlite3"
        self.kill_switch = Path(settings.data_dir) / "TEACHER_DEMO_DISABLED"
        self._rate_lock = threading.Lock()
        self._attempts: dict[tuple[str, str], deque[float]] = {}

    def _connect(self) -> sqlite3.Connection:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database, timeout=15, isolation_level=None)
        connection.execute("PRAGMA busy_timeout = 15000")
        return connection

    def initialize(self) -> None:
        if not self.enabled:
            return
        now = int(time.time())
        with closing(self._connect()) as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS teacher_demo_state (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    activated_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    analysis_count INTEGER NOT NULL CHECK (analysis_count >= 0)
                )"""
            )
            connection.execute(
                "INSERT OR IGNORE INTO teacher_demo_state VALUES (1, ?, ?, 0)",
                (now, now + self.settings.teacher_demo_days * 86400),
            )

    def _read_state(self) -> tuple[int, int, int]:
        self.initialize()
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT activated_at, expires_at, analysis_count FROM teacher_demo_state WHERE singleton = 1"
            ).fetchone()
        if row is None:
            raise HTTPException(503, "Teacher Demo не удалось безопасно инициализировать.")
        activated_at, expires_at, count = map(int, row)
        # A persisted row can never be extended beyond seven days after first activation.
        expires_at = min(expires_at, activated_at + 7 * 86400)
        return activated_at, expires_at, count

    def ensure_active(self) -> tuple[int, int, int]:
        if not self.enabled:
            raise HTTPException(404, "Teacher Demo не включён.")
        if self.kill_switch.exists():
            raise HTTPException(503, "Teacher Demo немедленно отключён владельцем.")
        state = self._read_state()
        if int(time.time()) >= state[1]:
            raise HTTPException(410, "Срок Teacher Demo завершён.")
        return state

    def check_rate(self, request: Request, category: str) -> None:
        self.ensure_active()
        now = time.monotonic()
        is_login = category == "login"
        limit = LOGIN_ATTEMPTS_PER_WINDOW if is_login else API_REQUESTS_PER_WINDOW
        window = LOGIN_WINDOW_SECONDS if is_login else RATE_WINDOW_SECONDS
        client_key = request.client.host if request.client else "unknown"
        bucket = (category, client_key)
        with self._rate_lock:
            if len(self._attempts) > 5000:
                cutoff = now - max(LOGIN_WINDOW_SECONDS, RATE_WINDOW_SECONDS)
                self._attempts = {
                    key: values for key, values in self._attempts.items()
                    if values and values[-1] > cutoff
                }
            events = self._attempts.setdefault(bucket, deque())
            while events and events[0] <= now - window:
                events.popleft()
            if len(events) >= limit:
                raise HTTPException(429, "Слишком много запросов. Попробуйте позже.")
            events.append(now)

    def verify_password(self, candidate: str) -> bool:
        expected = self.settings.teacher_demo_password.encode("utf-8")
        supplied = candidate.encode("utf-8")
        return hmac.compare_digest(supplied, expected)

    def issue_token(self) -> tuple[str, int]:
        _activated, session_expiry, _count = self.ensure_active()
        now = int(time.time())
        expires = min(now + TOKEN_LIFETIME_SECONDS, session_expiry)
        payload = _b64encode(json.dumps(
            {"sub": "teacher", "iat": now, "exp": expires},
            separators=(",", ":"),
        ).encode("utf-8"))
        signature = _b64encode(hmac.new(
            self.settings.teacher_demo_token_secret.encode("utf-8"),
            payload.encode("ascii"), hashlib.sha256,
        ).digest())
        return f"{payload}.{signature}", expires

    def authenticate(self, authorization: str | None) -> bool:
        if not authorization or not authorization.startswith("Bearer "):
            return False
        token = authorization[7:]
        if not token or len(token) > 2048 or token.count(".") != 1:
            return False
        payload, signature = token.split(".", 1)
        expected = _b64encode(hmac.new(
            self.settings.teacher_demo_token_secret.encode("utf-8"),
            payload.encode("ascii", errors="ignore"), hashlib.sha256,
        ).digest())
        if not hmac.compare_digest(signature, expected):
            return False
        try:
            data = json.loads(_b64decode(payload))
            now = int(time.time())
            _activated, session_expiry, _count = self.ensure_active()
            return (
                data.get("sub") == "teacher"
                and isinstance(data.get("iat"), int)
                and isinstance(data.get("exp"), int)
                and data["iat"] <= now + 60
                and now < data["exp"]
                and data["exp"] <= session_expiry
                and data["exp"] - data["iat"] <= TOKEN_LIFETIME_SECONDS
            )
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, HTTPException):
            return False

    def reserve_analysis(self) -> int:
        """Atomically consume one of two lifetime slots; failed jobs still consume a slot."""
        if not self.enabled:
            return MAX_ANALYSES
        self.ensure_active()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT activated_at, expires_at, analysis_count FROM teacher_demo_state WHERE singleton = 1"
            ).fetchone()
            if row is None:
                connection.rollback()
                raise HTTPException(503, "Teacher Demo не удалось безопасно инициализировать.")
            activated_at, expires_at, count = map(int, row)
            if int(time.time()) >= min(expires_at, activated_at + 7 * 86400):
                connection.rollback()
                raise HTTPException(410, "Срок Teacher Demo завершён.")
            if self.kill_switch.exists():
                connection.rollback()
                raise HTTPException(503, "Teacher Demo немедленно отключён владельцем.")
            if count >= MAX_ANALYSES:
                connection.rollback()
                raise HTTPException(429, "Лимит живых анализов Teacher Demo исчерпан.")
            count += 1
            connection.execute(
                "UPDATE teacher_demo_state SET analysis_count = ? WHERE singleton = 1", (count,)
            )
            connection.commit()
        return MAX_ANALYSES - count

    def status(self) -> dict[str, Any]:
        activated, expires, count = self.ensure_active()
        return {
            "active": True,
            "activated_at": _utc_iso(activated),
            "expires_at": _utc_iso(expires),
            "analyses_used": count,
            "analyses_remaining": max(0, MAX_ANALYSES - count),
        }


class TeacherBodyLimitMiddleware:
    """Enforce request-body bounds while streaming, before multipart parsing can spool to disk."""

    def __init__(self, app, guard: TeacherDemoGuard, upload_limit_bytes: int):
        self.app = app
        self.guard = guard
        self.upload_limit_bytes = upload_limit_bytes

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http" or not self.guard.enabled
                or scope.get("method") != "POST" or not scope.get("path", "").startswith("/api/")):
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        limit = {
            "/api/teacher-demo/login": 1024,
            "/api/meetings/cloud": 8192,
            "/api/meetings": self.upload_limit_bytes + 65536,
        }.get(path, 8192)
        size = 0
        rejected = False

        async def bounded_receive():
            nonlocal size, rejected
            if rejected:
                return {"type": "http.request", "body": b"", "more_body": False}
            message = await receive()
            if message.get("type") == "http.request":
                size += len(message.get("body", b""))
                if size > limit:
                    rejected = True
                    body = json.dumps(
                        {"detail": "Размер запроса превышает ограничение Teacher Demo."},
                        ensure_ascii=False,
                    ).encode("utf-8")
                    await send({"type": "http.response.start", "status": 413,
                                "headers": [(b"content-type", b"application/json"),
                                            (b"content-length", str(len(body)).encode("ascii"))]})
                    await send({"type": "http.response.body", "body": body, "more_body": False})
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        async def bounded_send(message):
            if not rejected:
                await send(message)

        await self.app(scope, bounded_receive, bounded_send)


def main() -> None:
    """Create the persistent kill switch: python -m meeting_analyzer.teacher_demo --disable."""
    import argparse

    from .config import settings

    parser = argparse.ArgumentParser(description="Управление Teacher Demo")
    parser.add_argument("--disable", action="store_true", help="немедленно остановить Teacher Demo")
    args = parser.parse_args()
    if not args.disable:
        parser.error("укажите --disable")
    path = Path(settings.teacher_demo_data_dir) / "TEACHER_DEMO_DISABLED"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("disabled\n", encoding="utf-8")
    print("Teacher Demo отключён. Флаг хранится локально; секреты не выводились.")


if __name__ == "__main__":
    main()
