import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import ROOT, settings
from .pipeline import process_video
from .storage import MeetingStore

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("meeting-analyzer")
store = MeetingStore(settings.data_dir / "meetings.sqlite3")
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="meeting-analysis")
app = FastAPI(title="AI Video Meeting Analyzer")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
ALLOWED = {".mp4", ".webm"}


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
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(400, "Поддерживаются только видео MP4 и WebM.")
    filename = Path(file.filename or "meeting" + suffix).name
    temp_name = f"{uuid4().hex}{suffix}"
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    temp_path = settings.data_dir / temp_name
    total = 0
    max_bytes = settings.max_upload_mb * 1024 * 1024
    try:
        with temp_path.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(413, f"Файл превышает ограничение {settings.max_upload_mb} МБ.")
                target.write(chunk)
        if total == 0:
            raise HTTPException(400, "Файл пустой. Выберите видео и попробуйте снова.")
        meeting_value = store.create(filename)
        executor.submit(_process_meeting, meeting_value["id"], temp_path)
        return meeting_value
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


def _process_meeting(meeting_id: str, path: Path):
    try:
        transcript, language, summary = process_video(
            path, on_transcript=lambda text, lang: store.update(
                meeting_id, transcript=text, language=lang
            )
        )
        store.update(meeting_id, status="ready", transcript=transcript,
                     language=language, summary=summary)
    except Exception as exc:
        message = str(exc).strip() or "Обработка не удалась. Проверьте файл и настройки и загрузите его повторно."
        log.exception("Meeting processing failed for %s", meeting_id)
        store.update(meeting_id, status="error", error=message[:1200])
    finally:
        path.unlink(missing_ok=True)


def run():
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")
