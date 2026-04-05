import fnmatch
import os
from collections.abc import Iterator
from pathlib import Path

from ..constants import MAX_FILE_SIZE
from ..models import FileInfo


def djb2_hash(content: bytes) -> str:
    """Compute djb2 hash of content."""
    h = 5381
    for byte in content:
        h = ((h << 5) + h) + byte
        h &= 0xFFFFFFFF
    return hex(h)[2:]


def get_file_info(path: Path, language: str) -> FileInfo:
    """Get file metadata."""
    stat = path.stat()
    return FileInfo(
        path=str(path.resolve()),
        language=language,
        content_hash="",
        last_modified=stat.st_mtime,
        size=stat.st_size,
    )


def should_skip_file(path: Path, excludes: list[str]) -> bool:
    """Check if file should be skipped based on excludes."""
    path_str = str(path)
    path_parts = path.parts

    for exclude in excludes:
        if fnmatch.fnmatch(path.name, exclude):
            return True
        if fnmatch.fnmatch(path_str, f"*{exclude}*"):
            return True
        if exclude in path_parts:
            return True

    return False


def get_language_from_extension(path: Path) -> str | None:
    """Determine language from file extension."""
    ext_map = {
        ".py": "python",
        ".cs": "csharp",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
    }
    return ext_map.get(path.suffix.lower())


def scan_files(
    root: Path,
    includes: list[str],
    excludes: list[str],
) -> Iterator[tuple[Path, str]]:
    """Scan directory for files matching patterns."""
    if isinstance(root, str):
        root = Path(root)

    for dirpath, dirnames, filenames in os.walk(root):
        dirpath = Path(dirpath)

        dirnames[:] = [d for d in dirnames if not should_skip_file(dirpath / d, excludes)]

        for filename in filenames:
            filepath = dirpath / filename

            if should_skip_file(filepath, excludes):
                continue

            language = get_language_from_extension(filepath)
            if language is None:
                continue

            if filepath.stat().st_size > MAX_FILE_SIZE:
                continue

            yield filepath, language
