"""Safe import of publicly shared Google Drive videos (no OAuth)."""

import ipaddress
import re
import socket
import time
from email.message import Message
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx

GOOGLE_DRIVE_HOSTS = {"drive.google.com"}
GOOGLE_DOWNLOAD_HOSTS = (
    "google.com", ".google.com", "googleusercontent.com", ".googleusercontent.com",
)
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
MAX_REDIRECTS = 5
MAX_DOWNLOAD_SECONDS = 15 * 60
GOOGLE_UC_URL = "https://drive.google.com/uc"


class CloudImportError(ValueError):
    """A safe, user-displayable failure while importing a shared file."""


def normalize_google_drive_url(value: str) -> tuple[str, str]:
    """Return a canonical view URL and file ID from a supported Drive share link."""
    try:
        parts = urlsplit(value.strip())
        host = (parts.hostname or "").lower().rstrip(".")
        if (parts.scheme != "https" or host not in GOOGLE_DRIVE_HOSTS
                or parts.username or parts.password or parts.port not in (None, 443)):
            raise ValueError
        match = re.fullmatch(r"/file/d/([A-Za-z0-9_-]{10,200})(?:/view)?/?", parts.path)
        file_id = match.group(1) if match else None
        if not file_id and parts.path in {"/open", "/uc"}:
            file_id = parse_qs(parts.query).get("id", [None])[0]
        if not isinstance(file_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{10,200}", file_id):
            raise ValueError
        return f"https://drive.google.com/file/d/{file_id}/view", file_id
    except (ValueError, TypeError) as exc:
        raise CloudImportError(
            "Нужна общедоступная ссылка Google Drive вида "
            "https://drive.google.com/file/d/…/view. Проверьте доступ «Все, у кого есть ссылка» "
            "или скачайте видео и загрузите его вручную."
        ) from exc


def _validate_google_target(url: str) -> None:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().rstrip(".")
    if (parts.scheme != "https" or not host or parts.username or parts.password
            or parts.port not in (None, 443)):
        raise CloudImportError("Google Drive вернул небезопасную ссылку для скачивания.")
    if not (host in GOOGLE_DOWNLOAD_HOSTS or any(host.endswith(suffix) for suffix in GOOGLE_DOWNLOAD_HOSTS if suffix.startswith("."))):
        raise CloudImportError("Google Drive вернул ссылку на неожиданный домен; скачивание остановлено.")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise CloudImportError("Адрес облачного файла недоступен или ведёт во внутреннюю сеть.")
    except (OSError, ValueError) as exc:
        if isinstance(exc, CloudImportError):
            raise
        raise CloudImportError("Не удалось проверить сетевой адрес Google Drive.") from exc


def _safe_filename(content_disposition: str, file_id: str, suffix: str) -> str:
    message = Message()
    message["content-disposition"] = content_disposition
    name = message.get_filename() or ""
    name = Path(name.replace("\\", "/")).name
    if Path(name).suffix.lower() not in {".mp4", ".webm"}:
        name = f"google-drive-{file_id}{suffix}"
    return name[:240]


def download_google_drive_video(share_url: str, destination_dir: Path,
                               max_bytes: int) -> tuple[Path, str, str]:
    """Stream a public Drive file to disk with bounded size, redirects and time."""
    normalized, file_id = normalize_google_drive_url(share_url)
    timeout = httpx.Timeout(connect=10, read=25, write=10, pool=10)
    destination_dir.mkdir(parents=True, exist_ok=True)
    path: Path | None = None
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            current = str(httpx.URL(GOOGLE_UC_URL).copy_merge_params({
                "export": "download", "id": file_id,
            }))
            response = None
            for _ in range(MAX_REDIRECTS + 1):
                _validate_google_target(current)
                try:
                    response = client.send(client.build_request("GET", current), stream=True)
                except httpx.HTTPError as exc:
                    raise CloudImportError("Не удалось связаться с Google Drive. Проверьте ссылку и интернет.") from exc
                if response.status_code in REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    base = response.url
                    response.close()
                    if not location:
                        raise CloudImportError("Google Drive вернул некорректное перенаправление.")
                    current = str(base.join(location))
                    continue
                break
            else:
                raise CloudImportError("Google Drive перенаправил слишком много раз.")
            if response is None or response.status_code >= 400:
                status = response.status_code if response is not None else 502
                if response is not None:
                    response.close()
                if status in (401, 403, 404):
                    raise CloudImportError(
                        "Google Drive не разрешил скачать файл. Включите доступ «Все, у кого есть ссылка» "
                        "и проверьте, что скачивание не запрещено."
                    )
                raise CloudImportError(f"Google Drive вернул ошибку HTTP {status}.")
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" in content_type:
                response.close()
                raise CloudImportError(
                    "Google Drive показал страницу подтверждения или входа, а не файл. "
                    "Проверьте публичный доступ; при необходимости скачайте видео и загрузите вручную."
                )
            length = response.headers.get("content-length")
            if length and length.isdigit() and int(length) > max_bytes:
                response.close()
                raise CloudImportError(f"Видео превышает ограничение {max_bytes // (1024 * 1024)} МБ.")
            disposition = response.headers.get("content-disposition", "")
            path = destination_dir / f"{uuid4().hex}.download"
            prefix = bytearray()
            total = 0
            deadline = time.monotonic() + MAX_DOWNLOAD_SECONDS
            try:
                with path.open("wb") as output:
                    for chunk in response.iter_bytes(1024 * 1024):
                        if time.monotonic() > deadline:
                            raise CloudImportError("Скачивание заняло слишком много времени. Попробуйте позже.")
                        total += len(chunk)
                        if total > max_bytes:
                            raise CloudImportError(f"Видео превышает ограничение {max_bytes // (1024 * 1024)} МБ.")
                        if len(prefix) < 16:
                            prefix.extend(chunk[:16 - len(prefix)])
                        output.write(chunk)
            finally:
                response.close()
            if prefix.startswith(bytes.fromhex("1a45dfa3")):
                suffix = ".webm"
            elif len(prefix) >= 8 and prefix[4:8] == b"ftyp":
                suffix = ".mp4"
            else:
                raise CloudImportError("Загруженный файл не похож на MP4/WebM. Скачайте его и загрузите вручную.")
            if not total:
                raise CloudImportError("Google Drive вернул пустой файл.")
            filename = _safe_filename(disposition, file_id, suffix)
            final_path = path.with_suffix(suffix)
            path.replace(final_path)
            path = final_path
            return path, filename, normalized
    except Exception:
        if path is not None:
            path.unlink(missing_ok=True)
        raise
