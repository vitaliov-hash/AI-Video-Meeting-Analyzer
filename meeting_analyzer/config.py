import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    provider: str = os.getenv("AI_PROVIDER", "deepseek").strip().lower()
    whisper_model: str = os.getenv("WHISPER_MODEL", "small")
    whisper_device: str = os.getenv("WHISPER_DEVICE", "cpu")
    whisper_compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "500"))
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    personal_data_dir: Path = Path(os.getenv("DATA_DIR", str(ROOT / "data")))
    teacher_demo_enabled: bool = os.getenv("TEACHER_DEMO_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
    teacher_demo_password: str = os.getenv("TEACHER_DEMO_PASSWORD", "")
    teacher_demo_token_secret: str = os.getenv("TEACHER_DEMO_TOKEN_SECRET", "")
    teacher_demo_data_dir: Path = Path(os.getenv("TEACHER_DEMO_DATA_DIR", str(ROOT / ".teacher-demo-data")))
    teacher_demo_days: int = int(os.getenv("TEACHER_DEMO_DAYS", "5"))
    teacher_demo_max_transcript_chars: int = int(os.getenv("TEACHER_DEMO_MAX_TRANSCRIPT_CHARS", "8000"))
    cors_allowed_origins: tuple[str, ...] = tuple(
        origin.strip().rstrip("/")
        for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    )

    @property
    def data_dir(self) -> Path:
        return self.teacher_demo_data_dir.resolve() if self.teacher_demo_enabled else self.personal_data_dir

    @property
    def ai_max_output_tokens(self) -> int:
        return 600 if self.teacher_demo_enabled else 1600

    def __post_init__(self):
        if self.max_upload_mb < 1:
            raise ValueError("MAX_UPLOAD_MB must be at least 1.")
        if not self.teacher_demo_enabled:
            return
        if self.provider != "deepseek":
            raise ValueError("Teacher Demo requires AI_PROVIDER=deepseek.")
        if self.host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Teacher Demo backend must bind to a loopback address.")
        if len(self.teacher_demo_password) < 20:
            raise ValueError("TEACHER_DEMO_PASSWORD must contain at least 20 characters.")
        if len(self.teacher_demo_token_secret) < 32:
            raise ValueError("TEACHER_DEMO_TOKEN_SECRET must contain at least 32 characters.")
        if not 1 <= self.teacher_demo_days <= 7:
            raise ValueError("TEACHER_DEMO_DAYS must be between 1 and 7.")
        if not 1 <= self.max_upload_mb <= 100:
            raise ValueError("Teacher Demo MAX_UPLOAD_MB must be between 1 and 100.")
        if not 1000 <= self.teacher_demo_max_transcript_chars <= 8000:
            raise ValueError("TEACHER_DEMO_MAX_TRANSCRIPT_CHARS must be between 1000 and 8000.")
        if len(self.cors_allowed_origins) != 1:
            raise ValueError("Teacher Demo requires exactly one allowed HTTPS frontend origin.")
        origin = urlsplit(self.cors_allowed_origins[0])
        if (origin.scheme != "https" or not origin.netloc or origin.username or origin.password
                or origin.path not in ("", "/") or origin.query or origin.fragment):
            raise ValueError("Teacher Demo CORS origin must be one exact HTTPS origin.")
        personal = self.personal_data_dir.resolve()
        demo = self.teacher_demo_data_dir.resolve()
        if demo == personal or demo.is_relative_to(personal) or personal.is_relative_to(demo):
            raise ValueError("Teacher Demo data directory must be isolated from personal data.")


settings = Settings()
