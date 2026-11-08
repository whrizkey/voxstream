# Changelog

All notable changes to VoxStream are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-08

### Added
- **Core Architecture & Engine:**
  - Rolling lookahead scheduler buffering ahead of the playback playhead.
  - Multi-track media probing and SHA-256 media fingerprinting.
  - Silence-aware chunking with energy threshold snapping and 2.0s context padding to eliminate mid-sentence word chops.
  - Midpoint boundary ownership to eliminate duplicate subtitle cues across adjacent chunks.
- **Speech-to-Text (STT) Providers:**
  - `faster-whisper`: Local GPU/CPU inference with int8 quantization support.
  - `openai_compat`: Cloud transcription supporting Whisper API and compatible proxies (Groq, Together).
  - Deterministic `fake` STT provider for offline test suites.
- **Translation Providers & Timing Fit:**
  - `openai_compat`: Structured JSON translation with system prompt constraints.
  - `anthropic`: Claude 3.5 Haiku / Sonnet translator with token budgeting.
  - `deepl`: DeepL Pro API translator with formality and context preservation.
  - Dynamic character budgeting (`max_chars`) calculated from target language speaking rates.
  - Two-pass translation: draft pass followed by timed paraphrase pass when utterances overflow.
  - User glossary support via JSON/CSV with case-preserving boundary replacement.
- **Text-to-Speech (TTS) Providers & Audio Rendering:**
  - `edge`: High-fidelity Microsoft Edge neural TTS with silent leading/trailing audio trimming.
  - `openai`: OpenAI Audio Speech API (`tts-1` / `tts-1-hd`).
  - `elevenlabs`: ElevenLabs Multilingual v2 integration.
  - `piper`: Local zero-cloud neural TTS engine.
  - Pitch-preserving time-stretching (`atempo`) up to 1.25x with fallback retranslation and bounded overflow fade-out.
  - Full timeline audio rendering with -14 dB dynamic ducking (120ms attack, 300ms release).
- **Live Playback Layer:**
  - Unified `Player` interface with `MpvPlayer` (embedded `libmpv`) and headless `VirtualPlayer`.
  - Subtitle store supporting $O(\log n)$ bisect lookups for instant cue rendering.
  - Real-time `DubMixer` slaved to `time-pos` with 80ms monotonic drift correction and sample-level latency compensation.
- **Export Formats & Media Tools:**
  - SubRip (`.srt`) export with line wrapping and dual-language subtitles.
  - Advanced SubStation Alpha (`.ass`) export with custom style presets (`default`, `anime`, `cinematic`, `dual`).
  - Complete dub track rendering and multi-track container muxing (`.mp4`, `.mkv`).
  - Online stream resolution via `yt-dlp` for web videos and network URLs.
- **Cost Accounting & Configuration:**
  - Usage tracking across STT audio seconds, translation characters, and TTS characters.
  - User-configurable `pricing.toml` with cost ceiling protection (`VOXSTREAM_MAX_COST_USD`).
  - Persistent SQLite WAL cache surviving process restarts.
- **User Interface & Tooling:**
  - PySide6 desktop GUI with embedded video surface, seek-buffer progress bar, and masked API key settings.
  - `voxstream doctor` diagnostic command verifying system dependencies and GPU hardware.
  - CLI subcommands: `play`, `process`, `export-srt`, `cache`, `doctor`, `providers`, `gui`.

### Security
- **Path Traversal Prevention:** Enforced 32-character hexadecimal media ID format validation and strict relative path containment in `cache clear --media` to prevent directory traversal.
- **Cost Ceiling Enforcement:** Wired `VOXSTREAM_MAX_COST_USD` through `UsageTracker.check_budget()` across offline batch and live lookahead pipelines.
- **Air-Gapped Privacy:** Added recognition for `VOXSTREAM_OPENAI_BASE_URL`, `VOXSTREAM_WHISPER_MODEL`, and `VOXSTREAM_TRANSLATE_MODEL` in config. Clarified that Edge TTS routes to Microsoft servers while Piper is strictly local.
- **Provider Misconfiguration:** Raised `ConfigurationError` when configured STT/translation/TTS providers are missing credentials rather than silently substituting fake test providers.
- **Secret Redaction:** Redacted bearer tokens, HTTP 5xx responses, and API keys (`sk-`, `sk-ant-`, `deep-`, `Bearer`, query params) from logs and error traces. Stored API keys in `SecretStr`.
- **Media Argument Sanitization:** Added `-protocol_whitelist "file,http,https,tcp,tls,crypto"`, `--` separator, and `./` path sanitization to `ffmpeg` and `ffprobe` invocations.
- **CWD Environment Isolation:** Restricted `.env` loading to explicit paths (`VOXSTREAM_ENV_FILE`), `~/.config/voxstream/.env`, or the repository root with `.git`.
- **CI Hardening:** Pinned GitHub Actions to immutable commit SHAs, restricted default token permissions with `permissions: contents: read`, added `pip-audit` security vulnerability scans, and configured Dependabot.

### Fixed
- **Seek Stalled Chunks:** Resolved issue where chunks interrupted in `TRANSCRIBED` state during a generation bump were not re-scheduled by `LookaheadScheduler.step()`.
- **Dynamic Cache Keys:** Replaced hardcoded cache parameters with active provider names, models, language codes, and chunk slicing parameters.
- **Edge TTS Event Loop Collision:** Implemented thread-isolated voice discovery in `EdgeTtsProvider.list_voices()` and added `list_voices_async()` to avoid event loop conflicts. Added language-specific default voice fallback.
- **Audio Resampling in Dub Mixer:** Implemented pre-decoding and linear resampling for clips with mismatched sample rates (such as Piper's 22.05 kHz audio into 24 kHz mixer).
- **Audio Callback Thread Safety:** Eliminated blocking disk I/O from mixer playback callback and added thread synchronization locks for clip updates.
- **Async Execution:** Moved blocking ffmpeg audio extraction to threadpool executor and converted Piper TTS synthesis to non-blocking async subprocess execution.
- **Pause & Underrun Coordination:** Preserved user pause state during underrun buffering recovery so manual pauses are not overridden by buffer completion.
- **CLI Wiring:** Wired `--mux` flag in `voxstream process`, implemented real LRU cache pruning in `voxstream cache prune`, and enabled URL playback with `MpvPlayer` in `voxstream play`.
- **Settings Dialog Keyring:** Stored and retrieved API keys securely via system keyring in the desktop settings dialog.
