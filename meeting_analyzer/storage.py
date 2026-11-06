import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4


class MeetingStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = Lock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS meetings (
                id TEXT PRIMARY KEY, filename TEXT NOT NULL, added_at TEXT NOT NULL,
                status TEXT NOT NULL, language TEXT, transcript TEXT,
                summary TEXT, error TEXT)""")

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def create(self, filename: str) -> dict[str, Any]:
        meeting = {"id": uuid4().hex, "filename": filename,
                   "added_at": datetime.now(UTC).isoformat(), "status": "processing",
                   "language": None, "transcript": None, "summary": None, "error": None}
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO meetings (id,filename,added_at,status) VALUES (?,?,?,?)",
                       (meeting["id"], filename, meeting["added_at"], meeting["status"]))
        return meeting

    def update(self, meeting_id: str, **values: Any) -> None:
        allowed = {"status", "language", "transcript", "summary", "error"}
        if not values or values.keys() - allowed:
            raise ValueError("Invalid meeting fields")
        assignments = ",".join(f"{key}=?" for key in values)
        args = [json.dumps(v, ensure_ascii=False) if key == "summary" and v is not None else v
                for key, v in values.items()]
        with self._lock, self._connect() as db:
            db.execute(f"UPDATE meetings SET {assignments} WHERE id=?", (*args, meeting_id))

    def get(self, meeting_id: str):
        with self._connect() as db:
            row = db.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
        return self._decode(row) if row else None

    def list(self):
        with self._connect() as db:
            rows = db.execute("SELECT * FROM meetings ORDER BY added_at DESC").fetchall()
        return [self._decode(row) for row in rows]

    @staticmethod
    def _decode(row):
        result = dict(row)
        result["summary"] = json.loads(result["summary"]) if result["summary"] else None
        return result
