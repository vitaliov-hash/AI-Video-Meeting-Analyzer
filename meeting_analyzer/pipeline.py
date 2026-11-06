import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg

from .config import settings
from .providers.speech import FasterWhisperProvider
from .providers.summary import ConfiguredSummaryProvider
from .teacher_demo import TeacherDemoGuard


def process_video(video_path: Path, on_transcript=None) -> tuple[str, str, dict]:
    """Shared processing entry point for a local file; cloud import is intentionally out of scope."""
    with tempfile.TemporaryDirectory(prefix="meeting-audio-") as temp_dir:
        audio_path = Path(temp_dir) / "audio.wav"
        command = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(video_path), "-vn",
                   "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio_path)]
        try:
            result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=900)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Извлечение аудио заняло слишком много времени.") from exc
        if result.returncode:
            raise ValueError("Не удалось извлечь аудио. Убедитесь, что видео не повреждено и содержит звук.")
        transcript = FasterWhisperProvider(settings.whisper_model, settings.whisper_device,
                                           settings.whisper_compute_type).transcribe(str(audio_path))
    if (settings.teacher_demo_enabled
            and len(transcript.text) > settings.teacher_demo_max_transcript_chars):
        raise ValueError(
            "Распознанный текст превышает лимит Teacher Demo; AI-анализ не запускался."
        )
    if settings.teacher_demo_enabled:
        TeacherDemoGuard(settings).ensure_active()
    if on_transcript is not None:
        on_transcript(transcript.text, transcript.language)
    summary = ConfiguredSummaryProvider(settings.provider).summarize(transcript.text, transcript.language)
    return transcript.text, transcript.language, summary
