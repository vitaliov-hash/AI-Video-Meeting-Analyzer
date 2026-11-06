import httpx
import pytest

from meeting_analyzer import cloud_import
from meeting_analyzer.cloud_import import (
    CloudImportError,
    download_google_drive_video,
    normalize_google_drive_url,
)

FILE_ID = "TEST_FILE_ID_1234567890ABCDE"
SHARE = f"https://drive.google.com/file/d/{FILE_ID}/view?usp=sharing"


def test_normalizes_google_drive_share_link():
    assert normalize_google_drive_url(SHARE) == (
        f"https://drive.google.com/file/d/{FILE_ID}/view", FILE_ID
    )


@pytest.mark.parametrize("url", [
    f"http://drive.google.com/file/d/{FILE_ID}/view",
    f"https://drive.google.com.evil.example/file/d/{FILE_ID}/view",
    f"https://user@drive.google.com/file/d/{FILE_ID}/view",
    f"https://127.0.0.1/file/d/{FILE_ID}/view",
    f"https://drive.google.com/drive/folders/{FILE_ID}",
])
def test_rejects_unsafe_or_non_file_share_urls(url):
    with pytest.raises(CloudImportError):
        normalize_google_drive_url(url)


def _mock_client(monkeypatch, handler):
    monkeypatch.setattr(cloud_import, "_validate_google_target", lambda _url: None)
    client_class = httpx.Client
    monkeypatch.setattr(
        cloud_import.httpx, "Client",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )


def test_downloads_and_validates_public_webm(monkeypatch, tmp_path):
    video = bytes.fromhex("1a45dfa3") + b"webm fixture"
    _mock_client(monkeypatch, lambda _request: httpx.Response(
        200, content=video, headers={
            "content-type": "video/webm", "content-disposition": 'attachment; filename="lesson.webm"',
        }
    ))
    path, filename, normalized = download_google_drive_video(SHARE, tmp_path, 1024)
    assert filename == "lesson.webm"
    assert path.read_bytes() == video
    assert normalized == f"https://drive.google.com/file/d/{FILE_ID}/view"


def test_rejects_html_confirmation_or_login_page(monkeypatch, tmp_path):
    _mock_client(monkeypatch, lambda _request: httpx.Response(
        200, content=b"<html>sign in</html>", headers={"content-type": "text/html"}
    ))
    with pytest.raises(CloudImportError, match="страницу подтверждения или входа"):
        download_google_drive_video(SHARE, tmp_path, 1024)
    assert list(tmp_path.iterdir()) == []


def test_enforces_streamed_size_limit_and_removes_partial_file(monkeypatch, tmp_path):
    video = bytes.fromhex("1a45dfa3") + b"more than limit"
    _mock_client(monkeypatch, lambda _request: httpx.Response(
        200, content=video, headers={"content-type": "video/webm"}
    ))
    with pytest.raises(CloudImportError, match="превышает ограничение"):
        download_google_drive_video(SHARE, tmp_path, 8)
    assert list(tmp_path.iterdir()) == []


def test_rejects_redirect_to_non_google_host(monkeypatch, tmp_path):
    checks = []

    def verify(url):
        checks.append(url)
        if "evil.example" in url:
            raise CloudImportError("Unexpected host blocked")

    monkeypatch.setattr(cloud_import, "_validate_google_target", verify)
    client_class = httpx.Client
    monkeypatch.setattr(cloud_import.httpx, "Client", lambda **kwargs: client_class(
        transport=httpx.MockTransport(lambda _request: httpx.Response(
            302, headers={"location": "https://evil.example/steal"}
        )), **kwargs
    ))
    with pytest.raises(CloudImportError, match="Unexpected host"):
        download_google_drive_video(SHARE, tmp_path, 1024)
    assert len(checks) == 2
    assert list(tmp_path.iterdir()) == []
