import logging
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .cloud_import import (
    CloudImportError,
    download_google_drive_video,
    normalize_google_drive_url,
)
from .config import ROOT, settings
from .pipeline import process_video
from .storage import MeetingStore
from .teacher_demo import TeacherBodyLimitMiddleware, TeacherDemoGuard

logging.basicConfig(level=logging.INFO)
# HTTP client request logs include full URLs. Never send those through application logs.
for logger_name in ("httpx", "httpcore", "httpx2", "httpcore2", "uvicorn.access"):
    http_logger = logging.getLogger(logger_name)
    http_logger.setLevel(logging.CRITICAL)
    http_logger.disabled = True
    for existing_name, existing_logger in logging.Logger.manager.loggerDict.items():
        if existing_name.startswith(f"{logger_name}.") and isinstance(existing_logger, logging.Logger):
            existing_logger.setLevel(logging.CRITICAL)
            existing_logger.disabled = True
log = logging.getLogger("meeting-analyzer")
store = MeetingStore(settings.data_dir / "meetings.sqlite3")
teacher_guard = TeacherDemoGuard(settings)
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="meeting-analysis")
processing_lock = Lock()
ALLOWED = {".mp4", ".webm"}
PROCESSING_ERROR = "Обработка не удалась. Проверьте файл и настройки и загрузите его повторно."


def _remove_upload(path: Path):
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        log.error("Temporary upload cleanup failed (%s)", type(exc).__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    teacher_guard.initialize()
    recovered = store.recover_interrupted()
    if recovered:
        log.info("Marked %s interrupted meeting(s) as failed", recovered)
    upload_dir = settings.data_dir / "uploads"
    if upload_dir.is_dir():
        for path in upload_dir.iterdir():
            if path.is_file() and re.fullmatch(r"[0-9a-f]{32}\.(mp4|webm)", path.name):
                _remove_upload(path)
    yield


app = FastAPI(
    title="AI Video Meeting Analyzer",
    lifespan=lifespan,
    docs_url=None if settings.teacher_demo_enabled else "/docs",
    redoc_url=None if settings.teacher_demo_enabled else "/redoc",
    openapi_url=None if settings.teacher_demo_enabled else "/openapi.json",
)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


class TeacherLogin(BaseModel):
    password: str = Field(min_length=1, max_length=256)


@app.middleware("http")
async def teacher_api_security(request: Request, call_next):
    if teacher_guard.enabled and request.url.path.startswith("/api/") and request.method != "OPTIONS":
        try:
            login_route = request.url.path == "/api/teacher-demo/login"
            teacher_guard.check_rate(request, "login" if login_route else "api")
            if not login_route and not teacher_guard.authenticate(request.headers.get("authorization")):
                return JSONResponse(
                    {"detail": "Войдите в Teacher Demo."}, status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if request.method == "POST":
                path_limits = {
                    "/api/teacher-demo/login": 1024,
                    "/api/meetings/cloud": 8192,
                    "/api/meetings": settings.max_upload_mb * 1024 * 1024 + 65536,
                }
                limit = path_limits.get(request.url.path, 8192)
                content_length = request.headers.get("content-length")
                if content_length:
                    try:
                        if int(content_length) > limit:
                            return JSONResponse(
                                {"detail": "Размер запроса превышает ограничение Teacher Demo."},
                                status_code=413,
                            )
                    except ValueError:
                        return JSONResponse({"detail": "Некорректный Content-Length."}, status_code=400)
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
    return await call_next(request)


# Stream bounds protect multipart parsing even when Content-Length is omitted.
app.add_middleware(
    TeacherBodyLimitMiddleware,
    guard=teacher_guard,
    upload_limit_bytes=settings.max_upload_mb * 1024 * 1024,
)

# CORS wraps the auth middleware so preflight and authorized responses carry exact-origin headers.
if settings.cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )


@app.post("/api/teacher-demo/login")
def teacher_login(payload: TeacherLogin, request: Request):
    if not teacher_guard.enabled:
        raise HTTPException(404, "Teacher Demo не включён.")
    if not teacher_guard.verify_password(payload.password):
        raise HTTPException(401, "Неверный пароль.")
    token, expires_at = teacher_guard.issue_token()
    status = teacher_guard.status()
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires_at,
        "analyses_remaining": status["analyses_remaining"],
        "session_expires_at": status["expires_at"],
    }


@app.get("/api/teacher-demo/status")
def teacher_status():
    return teacher_guard.status()


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/meetings")
def meetings():
    return store.list()


@app.get("/api/meetings/{meeting_id}")
def meeting(meeting_id: str):
    value = store.get(meeting_id)
    if value is None:
        raise HTTPException(404, "Встреча не найдена.")
    return value


@app.post("/api/meetings")
async def upload(file: Annotated[UploadFile, File()]):
    acquired = False
    submitted = False
    temp_path = None
    meeting_value = None
    try:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED:
            raise HTTPException(400, "Поддерживаются только видео MP4 и WebM.")
        acquired = processing_lock.acquire(blocking=False)
        if not acquired:
            raise HTTPException(409, "Уже обрабатывается одна встреча. Дождитесь завершения и загрузите файл снова.")
        filename = Path((file.filename or "meeting" + suffix).replace("\\", "/")).name
        upload_dir = settings.data_dir / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        temp_path = upload_dir / f"{uuid4().hex}{suffix}"
        total = 0
        max_bytes = settings.max_upload_mb * 1024 * 1024
        with temp_path.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(413, f"Файл превышает ограничение {settings.max_upload_mb} МБ.")
                target.write(chunk)
        if total == 0:
            raise HTTPException(400, "Файл пустой. Выберите видео и попробуйте снова.")
        teacher_guard.reserve_analysis()
        meeting_value = store.create(filename, phase="transcription")
        executor.submit(_process_and_release, meeting_value["id"], temp_path)
        submitted = True
        return meeting_value
    except HTTPException:
        raise
    except Exception as exc:
        message = "Не удалось сохранить или запустить видео. Проверьте свободное место и повторите загрузку."
        log.error("Upload failed (%s)", type(exc).__name__)
        if meeting_value is not None:
            store.update(meeting_value["id"], status="error", error=message)
        raise HTTPException(500, message) from exc
    finally:
        try:
            await file.close()
        finally:
            if acquired and not submitted:
                if temp_path is not None:
                    _remove_upload(temp_path)
                processing_lock.release()


@app.post("/api/meetings/cloud")
async def upload_from_cloud(payload: dict):
    public_url = payload.get("url") if isinstance(payload, dict) else None
    if not isinstance(public_url, str):
        raise HTTPException(400, "Вставьте публичную ссылку на видео Google Drive.")
    try:
        normalized, _file_id = normalize_google_drive_url(public_url)
    except CloudImportError as exc:
        raise HTTPException(400, str(exc)) from exc
    existing = store.find_by_source_url(normalized)
    if existing:
        existing["duplicate"] = True
        return existing
    if not processing_lock.acquire(blocking=False):
        raise HTTPException(409, "Уже обрабатывается одна встреча. Дождитесь завершения и повторите импорт.")
    try:
        teacher_guard.reserve_analysis()
        try:
            record = store.create("Видео из Google Drive", source="cloud",
                                  source_url=normalized, phase="downloading")
        except Exception:
            existing = store.find_by_source_url(normalized)
            if existing:
                existing["duplicate"] = True
                processing_lock.release()
                return existing
            raise
        try:
            executor.submit(_import_cloud_and_release, record["id"], normalized)
        except Exception:
            store.update(record["id"], status="error", phase="error",
                         error="Не удалось запустить импорт. Повторите попытку позже.")
            raise
        return store.get(record["id"]) or record
    except HTTPException:
        processing_lock.release()
        raise
    except Exception as exc:
        processing_lock.release()
        log.error("Cloud import submission failed (%s)", type(exc).__name__)
        raise HTTPException(500, "Не удалось начать импорт облачного файла.") from exc


def _import_cloud_and_release(meeting_id: str, public_url: str):
    temp_path = None
    try:
        try:
            temp_path, filename, _canonical_url = download_google_drive_video(
                public_url, settings.data_dir / "uploads", settings.max_upload_mb * 1024 * 1024
            )
            store.update(meeting_id, filename=filename, phase="transcription")
            _process_meeting(meeting_id, temp_path)
        except Exception as exc:  # noqa: BLE001 — persist import failures without retrying AI work
            message = str(exc) if isinstance(exc, (CloudImportError, ValueError, RuntimeError)) else ""
            message = message or "Не удалось получить видео из облака. Скачайте его и загрузите вручную."
            log.error("Cloud import failed (%s)", type(exc).__name__)
            store.update(meeting_id, status="error", phase="error", error=message[:1200])
    finally:
        if temp_path is not None:
            _remove_upload(temp_path)
        processing_lock.release()


def _process_and_release(meeting_id: str, path: Path):
    try:
        _process_meeting(meeting_id, path)
    finally:
        processing_lock.release()


def _process_meeting(meeting_id: str, path: Path):
    try:
        transcript, language, summary = process_video(
            path, on_transcript=lambda text, lang: store.update(
                meeting_id, transcript=text, language=lang, phase="ai"
            )
        )
        store.update(meeting_id, status="ready", transcript=transcript,
                     language=language, summary=summary, phase="ready")
    except Exception as exc:  # noqa: BLE001 — background task must persist any failure state
        message = str(exc).strip() if isinstance(exc, (ValueError, RuntimeError)) else ""
        message = message or PROCESSING_ERROR
        log.error("Meeting processing failed (%s)", type(exc).__name__)
        store.update(meeting_id, status="error", error=message[:1200], phase="error")
    finally:
        _remove_upload(path)


def run():
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info", access_log=False)
