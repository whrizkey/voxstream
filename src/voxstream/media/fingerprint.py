"""Deterministic media fingerprint generation for cache keys."""

import hashlib
from pathlib import Path


def calculate_fingerprint(path_or_url: str | Path, duration: float) -> str:
    """Generate a sha256 media identifier based on file content sample and duration."""
    target_str = str(path_or_url)
    hasher = hashlib.sha256()

    duration_ms = round(duration * 1000.0)
    hasher.update(str(duration_ms).encode("utf-8"))

    if target_str.startswith(("http://", "https://")):
        hasher.update(target_str.encode("utf-8"))
        return hasher.hexdigest()[:32]

    file_path = Path(path_or_url)
    if not file_path.exists():
        hasher.update(target_str.encode("utf-8"))
        return hasher.hexdigest()[:32]

    file_size = file_path.stat().st_size
    hasher.update(str(file_size).encode("utf-8"))

    chunk_size = 1024 * 1024  # 1 MiB
    with open(file_path, "rb") as f:
        # First 1 MiB
        first_chunk = f.read(chunk_size)
        hasher.update(first_chunk)

        # Last 1 MiB
        if file_size > chunk_size:
            f.seek(max(0, file_size - chunk_size))
            last_chunk = f.read(chunk_size)
            hasher.update(last_chunk)

    return hasher.hexdigest()[:32]
