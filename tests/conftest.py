"""Pytest configuration and shared test fixtures."""

import os

import pytest

# Sanitize bracketed IPv6 in NO_PROXY for httpx urlparse compatibility
for _env_key in ("NO_PROXY", "no_proxy"):
    _val = os.environ.get(_env_key)
    if _val and ",[::1]" in _val:
        os.environ[_env_key] = _val.replace(",[::1]", "")


@pytest.fixture
def sample_media_id() -> str:
    return "media_hash_abc123"
