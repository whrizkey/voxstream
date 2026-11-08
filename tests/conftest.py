"""Pytest configuration and shared test fixtures."""

import pytest


@pytest.fixture
def sample_media_id() -> str:
    return "media_hash_abc123"
