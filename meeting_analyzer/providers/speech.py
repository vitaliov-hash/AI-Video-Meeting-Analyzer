import os
from dataclasses import dataclass
from functools import lru_cache

import av

from ..config import ROOT

os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))


_av_open = av.open


def _av_open_compatible(*args, **kwargs):
    try:
        return _av_open(*args, **kwargs)
    except TypeError as exc:
        if "metadata_errors" not in kwargs or "unexpected keyword" not in str(exc):
            raise
        kwargs.pop("metadata_errors")
        return _av_open(*args, **kwargs)


# Newer PyAV releases dropped metadata_errors, while Faster-Whisper still passes it.
av.open = _av_open_compatible


@dataclass
class Transcript:
    text: str
    language: str


class SpeechToTextProvider:
    def transcribe(self, audio_path: str) -> Transcript:
        raise NotImplementedError


class FasterWhisperProvider(SpeechToTextProvider):
    def __init__(self, model_name: str, device: str, compute_type: str):
        self.model_name, self.device, self.compute_type = model_name, device, compute_type

    @property
    def model(self):
        return _load_model(self.model_name, self.device, self.compute_type)

    def transcribe(self, audio_path: str) -> Transcript:
        segments, info = self.model.transcribe(audio_path, beam_size=5, vad_filter=True)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        if not text:
            raise ValueError("В аудио не удалось распознать речь. Проверьте запись и попробуйте снова.")
        return Transcript(text=text, language=info.language)


@lru_cache(maxsize=2)
def _load_model(name: str, device: str, compute_type: str):
    from faster_whisper import WhisperModel
    return WhisperModel(name, device=device, compute_type=compute_type)
