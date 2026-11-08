# Contributing to VoxStream

Thank you for helping build VoxStream! We appreciate pull requests, bug reports, and design discussions.

---

## Development Philosophy

1. **Keep it typed and clean:** We enforce `ruff` and `mypy --strict`. Every new function must include explicit type annotations.
2. **Never hardcode vendor APIs:** All external services (STT, translation, TTS) belong behind abstract protocols in `src/voxstream/providers/`.
3. **No secrets in tests:** Never commit or log API keys. All automated unit and integration tests must run against fake/mock providers without network access.
4. **Pragmatic, working code:** When in doubt between complex abstractions and direct, readable logic, pick the simpler approach and document the decision in `docs/DECISIONS.md`.

---

## Local Setup

We use [`uv`](https://docs.astral.sh/uv/) for project and dependency management:

```bash
# Clone the repository
git clone https://github.com/whrizkey/voxstream.git
cd voxstream

# Install all development dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Check code formatting & types
uv run ruff check .
uv run mypy
```

---

## Pull Request Guidelines

1. Ensure all tests pass locally (`uv run pytest`).
2. Verify formatting and typing (`uv run ruff check .` and `uv run mypy`).
3. If introducing a new provider, include corresponding mock test fixtures in `tests/fixtures/`.
4. Keep PRs focused on a single milestone or feature.
