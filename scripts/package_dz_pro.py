"""Build a sanitized DZ Pro ZIP from files tracked by Git."""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "dist" / "AI-Video-Meeting-Analyzer-DZ-Pro.zip"
FORBIDDEN_PARTS = {
    ".git", ".venv", ".quality-venv", ".cache", ".teacher-demo-data", "data",
    "uploads", "models", "frontend-dist", "node_modules", "secrets", "credentials",
}
FORBIDDEN_SUFFIXES = {
    ".sqlite", ".sqlite3", ".db", ".mp4", ".webm", ".wav", ".mp3", ".key", ".pem", ".log",
}


def is_allowed(relative: Path) -> bool:
    parts = {part.lower() for part in relative.parts}
    name = relative.name.lower()
    if parts & FORBIDDEN_PARTS or name in {".env"}:
        return False
    if name.startswith(".env.") and name != ".env.example":
        return False
    return relative.suffix.lower() not in FORBIDDEN_SUFFIXES


def main() -> None:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "-z"], cwd=ROOT, check=True, capture_output=True,
    )
    paths = sorted(Path(item.decode("utf-8")) for item in result.stdout.split(b"\0") if item)
    paths = [path for path in paths if is_allowed(path)]
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in paths:
            absolute = ROOT / relative
            if absolute.is_file():
                archive.write(absolute, Path("AI-Video-Meeting-Analyzer") / relative)
    print(f"Created {ARCHIVE.name} with {len(paths)} tracked, filtered entries.")


if __name__ == "__main__":
    main()
