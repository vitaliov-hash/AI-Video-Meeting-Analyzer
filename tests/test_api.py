from fastapi.testclient import TestClient

from meeting_analyzer import app as app_module
from meeting_analyzer.storage import MeetingStore


def test_single_page_history_and_upload_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "store", MeetingStore(tmp_path / "test.sqlite3"))
    client = TestClient(app_module.app)
    page = client.get("/")
    assert page.status_code == 200
    assert 'data-i18n="appTitle"' in page.text
    assert 'id="cloud-form"' in page.text
    assert 'data-i18n="addFromCloud"' in page.text
    assert client.get("/api/meetings").json() == []
    response = client.post("/api/meetings", files={"file": ("notes.txt", b"not a video", "text/plain")})
    assert response.status_code == 400
    assert response.json()["detail"] == "Поддерживаются только видео MP4 и WebM."


def test_meeting_detail_not_found():
    client = TestClient(app_module.app)
    assert client.get("/api/meetings/missing").status_code == 404


def test_transcript_is_kept_if_summary_fails(tmp_path, monkeypatch):
    store = MeetingStore(tmp_path / "history.sqlite3")
    meeting = store.create("meeting.webm")
    monkeypatch.setattr(app_module, "store", store)

    def stt_then_summary_failure(_path, on_transcript):
        on_transcript("Обсудили проект.", "ru")
        raise RuntimeError("Не задан DEEPSEEK_API_KEY в локальном файле .env.")

    monkeypatch.setattr(app_module, "process_video", stt_then_summary_failure)
    source = tmp_path / "upload.webm"
    source.write_bytes(b"temp video")
    app_module._process_meeting(meeting["id"], source)
    result = store.get(meeting["id"])
    assert result["status"] == "error"
    assert result["language"] == "ru"
    assert result["transcript"] == "Обсудили проект."


def test_cloud_link_uses_shared_pipeline_and_deduplicates(tmp_path, monkeypatch):
    store = MeetingStore(tmp_path / "cloud.sqlite3")
    monkeypatch.setattr(app_module, "store", store)
    source = tmp_path / "download.webm"
    source.write_bytes(bytes.fromhex("1a45dfa3") + b"fixture")
    pipeline_calls = []

    class InlineExecutor:
        def submit(self, function, *args):
            function(*args)

    monkeypatch.setattr(app_module, "executor", InlineExecutor())
    monkeypatch.setattr(app_module, "download_google_drive_video", lambda *_args: (
        source, "meeting.webm", "https://drive.google.com/file/d/TEST_FILE_ID_1234567890ABCDE/view"
    ))

    def process(path, on_transcript):
        pipeline_calls.append(path)
        on_transcript("Discussed the schedule.", "en")
        return "Discussed the schedule.", "en", {
            "short_summary": "Schedule discussed", "decisions": [],
            "next_tasks": [], "open_questions": [],
        }

    monkeypatch.setattr(app_module, "process_video", process)
    client = TestClient(app_module.app)
    share = "https://drive.google.com/file/d/TEST_FILE_ID_1234567890ABCDE/view"
    first = client.post("/api/meetings/cloud", json={"url": share})
    assert first.status_code == 200
    assert first.json()["source"] == "cloud"
    assert first.json()["status"] == "ready"
    second = client.post("/api/meetings/cloud", json={
        "url": share + "?utm_source=again", "summary_language": "pt-BR",
    })
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["summary_language"] == "en"
    assert len(pipeline_calls) == 1


def test_cloud_link_rejects_unsupported_host(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "store", MeetingStore(tmp_path / "cloud.sqlite3"))
    response = TestClient(app_module.app).post(
        "/api/meetings/cloud", json={"url": "https://example.com/video.webm"}
    )
    assert response.status_code == 400
    assert "Google Drive" in response.json()["detail"]


def test_selected_summary_language_is_forwarded_without_changing_transcript(tmp_path, monkeypatch):
    store = MeetingStore(tmp_path / "language.sqlite3")
    meeting = store.create("meeting.webm", summary_language="es")
    monkeypatch.setattr(app_module, "store", store)
    calls = []

    def process(_path, on_transcript, target_language):
        calls.append(target_language)
        on_transcript("Original English speech.", "en")
        return "Original English speech.", "en", {
            "short_summary": "Resumen", "decisions": [], "next_tasks": [], "open_questions": [],
        }

    monkeypatch.setattr(app_module, "process_video", process)
    source = tmp_path / "upload.webm"
    source.write_bytes(b"fixture")
    app_module._process_meeting(meeting["id"], source)
    saved = store.get(meeting["id"])
    assert calls == ["es"]
    assert saved["language"] == "en"
    assert saved["summary_language"] == "es"
    assert saved["transcript"] == "Original English speech."


def test_cloud_rejects_unsupported_summary_language_without_analysis(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "store", MeetingStore(tmp_path / "language.sqlite3"))
    response = TestClient(app_module.app).post(
        "/api/meetings/cloud", json={"url": "https://example.com/video.webm", "summary_language": "de"}
    )
    assert response.status_code == 400
    assert "summary language" in response.json()["detail"]
