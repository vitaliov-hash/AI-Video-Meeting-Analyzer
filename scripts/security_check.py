"""Check tracked/untracked project files and optional ZIP for secrets and local data."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRET_PATTERNS = [
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(rb"\bsk-[A-Za-z0-9]{24,}\b"),
]
FORBIDDEN_NAMES = {
    ".env", ".venv", "venv", "data", "uploads", "models", ".cache",
    "__pycache__", ".pytest_cache", ".ruff_cache",
}
FORBIDDEN_SUFFIXES = {".sqlite", ".sqlite3", ".db", ".mp4", ".webm", ".wav", ".mp3"}
DRIVE_LINK = re.compile(rb"https?://drive\.google\.com/file/d/([^/?\s`]+)", re.IGNORECASE)
SAFE_DRIVE_IDS = {
    b"FILE_ID", b"{FILE_ID}", b"{file_id}",
    b"TEST_FILE_ID_1234567890ABCDE", "…".encode(),
}
EMAIL_ADDRESS = re.compile(rb"\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b", re.IGNORECASE)
SAFE_EMAIL_DOMAINS = {b"example.com", b"example.invalid"}


def sensitive_reason(name: str, content: bytes) -> str | None:
    parts = Path(name.replace("\\", "/")).parts
    if any(part in FORBIDDEN_NAMES for part in parts):
        return "local data/cache path"
    if Path(name).suffix.lower() in FORBIDDEN_SUFFIXES:
        return "database or media file"
    if Path(name).name == ".env":
        return "environment file"
    if Path(name).name.startswith(".env.") and Path(name).name != ".env.example":
        return "non-example environment file"
    if any(pattern.search(content) for pattern in SECRET_PATTERNS):
        return "secret-like value"
    if any(match.group(1) not in SAFE_DRIVE_IDS for match in DRIVE_LINK.finditer(content)):
        return "non-placeholder Google Drive file URL"
    if any(
        match.group(1).lower() not in SAFE_EMAIL_DOMAINS
        and content[max(0, match.start() - 3):match.start()] != b"://"
        for match in EMAIL_ADDRESS.finditer(content)
    ):
        return "email address / possible personal data"
    if len(content) < 2_000_000 and re.search(
        rb"(?im)^[ \t]*(?:DEEPSEEK|OPENAI|GEMINI)_API_KEY[ \t]*=[ \t]*[^\s#]+", content
    ):
        return "non-empty provider API key assignment"
    return None


def listed_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, check=True, capture_output=True,
    )
    return [ROOT / item.decode("utf-8", errors="surrogateescape")
            for item in result.stdout.split(b"\0") if item]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--archive-optional", action="store_true")
    args = parser.parse_args()
    findings: list[str] = []

    for path in listed_files():
        if not path.is_file():
            continue
        try:
            content = path.read_bytes()
        except OSError as exc:
            findings.append(f"{path.relative_to(ROOT)}: unreadable ({type(exc).__name__})")
            continue
        reason = sensitive_reason(str(path.relative_to(ROOT)), content)
        if reason:
            findings.append(f"{path.relative_to(ROOT)}: {reason}")

    if args.archive:
        archive = args.archive if args.archive.is_absolute() else ROOT / args.archive
        if not archive.exists():
            if not args.archive_optional:
                findings.append(f"{archive.relative_to(ROOT)}: archive missing")
        else:
            try:
                with zipfile.ZipFile(archive) as bundle:
                    for item in bundle.infolist():
                        if item.is_dir():
                            continue
                        reason = sensitive_reason(item.filename, bundle.read(item))
                        if reason:
                            findings.append(f"{archive.name}:{item.filename}: {reason}")
            except (OSError, zipfile.BadZipFile) as exc:
                findings.append(f"{archive.name}: unreadable archive ({type(exc).__name__})")

    if findings:
        print("Security check failed:")
        print("\n".join(f"- {item}" for item in findings))
        return 1
    print("Security check passed: no obvious secrets or local data in repository files/archive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
