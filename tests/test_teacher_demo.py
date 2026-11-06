from dataclasses import replace
from threading import Lock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from meeting_analyzer import app as app_module
from meeting_analyzer.config import settings
from meeting_analyzer.providers import summary as summary_module
from meeting_analyzer.storage import MeetingStore
from meeting_analyzer.teacher_demo import TeacherBodyLimitMiddleware, TeacherDemoGuard


def make_settings(tmp_path, **overrides):
    values = {
        "teacher_demo_enabled": True,
        "teacher_demo_password": "teacher-demo-password-123456",
        "teacher_demo_token_secret": "test-secret-with-at-least-thirty-two-bytes",
        "teacher_demo_data_dir": tmp_path / "teacher-data",
        "teacher_demo_days": 5,
        "teacher_demo_max_transcript_chars": 8000,
        "max_upload_mb": 25,
        "provider": "deepseek",
        "host": "127.0.0.1",
        "cors_allowed_origins": ("https://teacher-preview.example",),
    }
    values.update(overrides)
    return replace(settings, **values)


def configure_app(monkeypatch, tmp_path):
    demo_settings = make_settings(tmp_path)
    guard = app_module.teacher_guard
    monkeypatch.setattr(guard, "settings", demo_settings)
    monkeypatch.setattr(guard, "enabled", True)
    monkeypatch.setattr(guard, "database", demo_settings.data_dir / "teacher-demo-guard.sqlite3")
    monkeypatch.setattr(guard, "kill_switch", demo_settings.data_dir / "TEACHER_DEMO_DISABLED")
    monkeypatch.setattr(app_module, "settings", demo_settings)
    monkeypatch.setattr(app_module, "store", MeetingStore(demo_settings.data_dir / "meetings.sqlite3"))
    monkeypatch.setattr(app_module, "processing_lock", Lock())
    return demo_settings, guard


def test_teacher_guard_issues_tamper_proof_session_token_and_persists_quota(tmp_path):
    demo_settings = make_settings(tmp_path)
    assert demo_settings.data_dir == demo_settings.teacher_demo_data_dir.resolve()
    assert demo_settings.data_dir != demo_settings.personal_data_dir.resolve()
    guard = TeacherDemoGuard(demo_settings)
    guard.initialize()
    token, expiry = guard.issue_token()
    assert guard.verify_password("teacher-demo-password-123456")
    assert guard.authenticate(f"Bearer {token}")
    assert not guard.authenticate(f"Bearer {token}x")
    assert expiry > 0

    assert guard.reserve_analysis() == 1
    assert guard.reserve_analysis() == 0
    restarted = TeacherDemoGuard(demo_settings)
    assert restarted.status()["analyses_used"] == 2
    with pytest.raises(HTTPException) as error:
        restarted.reserve_analysis()
    assert error.value.status_code == 429


def test_teacher_demo_expiry_and_kill_switch_fail_closed(tmp_path, monkeypatch):
    demo_settings = make_settings(tmp_path)
    guard = TeacherDemoGuard(demo_settings)
    guard.initialize()
    activation, expiry, _count = guard._read_state()
    assert expiry - activation == 5 * 86400

    guard.kill_switch.parent.mkdir(parents=True, exist_ok=True)
    guard.kill_switch.write_text("disabled", encoding="utf-8")
    with pytest.raises(HTTPException) as error:
        guard.status()
    assert error.value.status_code == 503

    guard.kill_switch.unlink()
    monkeypatch.setattr("meeting_analyzer.teacher_demo.time.time", lambda: expiry + 1)
    with pytest.raises(HTTPException) as error:
        guard.status()
    assert error.value.status_code == 410


def test_all_teacher_data_and_processing_routes_require_auth_before_body_parse(tmp_path, monkeypatch):
    _demo_settings, _guard = configure_app(monkeypatch, tmp_path)
    with TestClient(app_module.app) as client:
        assert client.get("/api/meetings").status_code == 401
        assert client.get("/api/meetings/private-id").status_code == 401
        assert client.get("/api/teacher-demo/status").status_code == 401
        assert client.post("/api/meetings/cloud", content=b"not json").status_code == 401
        assert client.post("/api/meetings", files={"file": ("secret.webm", b"video", "video/webm")}).status_code == 401

        wrong = client.post("/api/teacher-demo/login", json={"password": "wrong"})
        assert wrong.status_code == 401
        login = client.post(
            "/api/teacher-demo/login", json={"password": "teacher-demo-password-123456"}
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/meetings", headers=headers).json() == []
        assert client.get("/api/teacher-demo/status", headers=headers).json()["analyses_remaining"] == 2


def test_teacher_live_analysis_quota_is_two_for_the_whole_session(tmp_path, monkeypatch):
    _demo_settings, guard = configure_app(monkeypatch, tmp_path)

    class InlineExecutor:
        def submit(self, function, *args):
            function(*args)

    monkeypatch.setattr(app_module, "executor", InlineExecutor())

    def fake_pipeline(_path, on_transcript):
        on_transcript("The meeting agreed on a safe test fixture.", "en")
        return "The meeting agreed on a safe test fixture.", "en", {
            "short_summary": "A safe test fixture was discussed.",
            "decisions": ["Use a local fixture."],
            "next_tasks": ["Prepare the fixture."],
            "open_questions": ["None."],
        }

    monkeypatch.setattr(app_module, "process_video", fake_pipeline)
    with TestClient(app_module.app) as client:
        login = client.post(
            "/api/teacher-demo/login", json={"password": "teacher-demo-password-123456"}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        for index in range(2):
            response = client.post(
                "/api/meetings", headers=headers,
                files={"file": (f"fixture-{index}.webm", b"test video", "video/webm")},
            )
            assert response.status_code == 200
            stored = client.get(f"/api/meetings/{response.json()['id']}", headers=headers)
            assert stored.json()["status"] == "ready"
        exhausted = client.post(
            "/api/meetings", headers=headers,
            files={"file": ("fixture-third.webm", b"test video", "video/webm")},
        )
        assert exhausted.status_code == 429
        assert guard.status()["analyses_used"] == 2
        assert client.get("/api/meetings", headers=headers).json()[0]["source"] == "manual"


def test_duplicate_cloud_link_does_not_consume_teacher_analysis_slot(tmp_path, monkeypatch):
    _demo_settings, guard = configure_app(monkeypatch, tmp_path)
    source = tmp_path / "cloud.webm"
    source.write_bytes(bytes.fromhex("1a45dfa3") + b"fixture")

    class InlineExecutor:
        def submit(self, function, *args):
            function(*args)

    monkeypatch.setattr(app_module, "executor", InlineExecutor())
    monkeypatch.setattr(app_module, "download_google_drive_video", lambda *_args: (
        source, "fixture.webm", "https://drive.google.com/file/d/TEST_FILE_ID_1234567890ABCDE/view"
    ))

    def fake_pipeline(_path, on_transcript):
        on_transcript("A test meeting.", "en")
        return "A test meeting.", "en", {
            "short_summary": "A test meeting.", "decisions": [], "next_tasks": [], "open_questions": []
        }

    monkeypatch.setattr(app_module, "process_video", fake_pipeline)
    with TestClient(app_module.app) as client:
        login = client.post(
            "/api/teacher-demo/login", json={"password": "teacher-demo-password-123456"}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        share = "https://drive.google.com/file/d/TEST_FILE_ID_1234567890ABCDE/view"
        first = client.post("/api/meetings/cloud", headers=headers, json={"url": share})
        duplicate = client.post("/api/meetings/cloud", headers=headers, json={"url": share})
        assert first.status_code == 200
        assert duplicate.status_code == 200
        assert duplicate.json()["duplicate"] is True
        assert guard.status()["analyses_used"] == 1


def test_teacher_summary_has_input_and_output_caps_without_external_request(tmp_path, monkeypatch):
    demo_settings = make_settings(tmp_path)
    monkeypatch.setattr(summary_module, "settings", demo_settings)
    provider = summary_module.ConfiguredSummaryProvider("deepseek")
    called = []
    monkeypatch.setattr(provider, "_request", lambda *_args: called.append(True) or "{}")
    with pytest.raises(ValueError, match="превышает ограничение"):
        provider.summarize("x" * 8001, "en")
    assert not called

    payloads = []
    provider = summary_module.ConfiguredSummaryProvider("deepseek")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": (
                '{"short_summary":"OK","decisions":[],"next_tasks":[],"open_questions":[]}'
            )}}]}

    def fake_post(_url, **kwargs):
        payloads.append(kwargs["json"])
        return FakeResponse()

    monkeypatch.setattr(summary_module.httpx, "post", fake_post)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-not-a-real-key")
    provider.summarize("A bounded test transcript.", "en")
    assert payloads[0]["max_tokens"] == 600


def test_request_body_stream_is_bounded_even_without_content_length(tmp_path):
    demo_settings = make_settings(tmp_path)
    guard = TeacherDemoGuard(demo_settings)
    middleware = TeacherBodyLimitMiddleware(None, guard, 1024)
    sent = []
    messages = [{"type": "http.request", "body": b"x" * 9000, "more_body": False}]

    async def receive():
        return messages.pop(0)

    async def send(message):
        sent.append(message)

    async def inner(scope, bounded_receive, bounded_send):
        while (await bounded_receive()).get("more_body"):
            pass

    middleware.app = inner
    import asyncio

    asyncio.run(middleware({"type": "http", "method": "POST", "path": "/api/meetings/cloud"}, receive, send))
    assert sent[0]["status"] == 413
