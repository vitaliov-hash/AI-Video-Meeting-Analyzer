import logging
from threading import Lock

from meeting_analyzer import app as app_module
from meeting_analyzer.cloud_import import CloudImportError
from meeting_analyzer.storage import MeetingStore


def test_http_client_request_logs_do_not_emit_urls_or_credentials(caplog):
    marker_url = "https://drive.google.com/file/d/TEST_FILE_ID_1234567890ABCDE/view"
    marker_key = "sk-test-secret-marker"
    caplog.set_level(logging.DEBUG)

    for logger_name in ("httpx", "httpx2"):
        logging.getLogger(logger_name).info(
            "request %s Authorization: Bearer %s", marker_url, marker_key
        )
    for logger_name in ("httpcore", "httpcore2"):
        logging.getLogger(f"{logger_name}.connection").debug(
            "connecting to %s with %s", marker_url, marker_key
        )
    logging.getLogger("uvicorn.access").info(
        "127.0.0.1 GET /api/meetings/%s Authorization: Bearer %s",
        "PRIVATE_MEETING_ID", marker_key,
    )

    assert marker_url not in caplog.text
    assert marker_key not in caplog.text
    assert "PRIVATE_MEETING_ID" not in caplog.text
    assert "127.0.0.1" not in caplog.text


def test_cloud_failure_log_excludes_record_id_url_and_key(tmp_path, monkeypatch, caplog):
    store = MeetingStore(tmp_path / "meetings.sqlite3")
    public_url = "https://drive.google.com/file/d/TEST_FILE_ID_1234567890ABCDE/view"
    marker_key = "sk-test-secret-marker"
    meeting = store.create("cloud-video.webm", source="cloud", source_url=public_url)
    lock = Lock()
    assert lock.acquire(blocking=False)
    monkeypatch.setattr(app_module, "store", store)
    monkeypatch.setattr(app_module, "processing_lock", lock)

    def fail_download(*_args):
        raise CloudImportError(f"Failed request for {public_url}: Bearer {marker_key}")

    monkeypatch.setattr(app_module, "download_google_drive_video", fail_download)
    caplog.set_level(logging.ERROR, logger="meeting-analyzer")

    app_module._import_cloud_and_release(meeting["id"], public_url)

    assert meeting["id"] not in caplog.text
    assert public_url not in caplog.text
    assert marker_key not in caplog.text
    assert "Authorization" not in caplog.text
    assert "Cloud import failed (CloudImportError)" in caplog.text
    assert not lock.locked()
