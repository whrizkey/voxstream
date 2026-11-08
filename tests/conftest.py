import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

# Sanitize bracketed IPv6 in NO_PROXY for httpx urlparse compatibility
for _env_key in ("NO_PROXY", "no_proxy"):
    _val = os.environ.get(_env_key)
    if _val and ",[::1]" in _val:
        os.environ[_env_key] = _val.replace(",[::1]", "")


@pytest.fixture
def sample_media_id() -> str:
    return "0123456789abcdef0123456789abcdef"


@pytest.fixture
def sample_wav() -> Generator[Path, None, None]:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    sr = 16000
    duration = 5.0
    num_samples = int(sr * duration)
    data = 0.1 * np.sin(2 * np.pi * 440 * np.linspace(0, duration, num_samples)).astype(np.float32)
    sf.write(str(tmp_path), data, sr)
    yield tmp_path
    if tmp_path.exists():
        tmp_path.unlink(missing_ok=True)
