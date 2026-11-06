from fastapi.testclient import TestClient

from meeting_analyzer import app as app_module
from meeting_analyzer.storage import MeetingStore


def test_single_page_history_and_upload_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "store", MeetingStore(tmp_path / "test.sqlite3"))
    client = TestClient(app_module.app)
    page = client.get("/")
    assert page.status_code == 200
    assert "Анализатор встреч" in page.text
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
