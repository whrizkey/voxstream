"""VoxStream: Real-time speech translation and dubbing player."""

import os

__version__ = "0.1.0"

# Workaround for httpx 0.28+ urlparse bug when NO_PROXY contains bracketed IPv6 like [::1]
for _env_key in ("NO_PROXY", "no_proxy"):
    _val = os.environ.get(_env_key)
    if _val and ",[::1]" in _val:
        os.environ[_env_key] = _val.replace(",[::1]", "")
