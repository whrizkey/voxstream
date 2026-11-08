# Changelog

All notable changes to VoxStream are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-08

### Added
- **Core Architecture & Engine:**
  - Rolling lookahead scheduler buffering 60–120 seconds ahead of the playback playhead.
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
  - 20-seek stress recovery test harness verifying clean cue invalidation without stale overlays.
- **Export Formats & Media Tools:**
  - SubRip (`.srt`) export with line wrapping and dual-language subtitles.
  - Advanced SubStation Alpha (`.ass`) export with custom style presets (`default`, `anime`, `cinematic`, `dual`).
  - Complete dub track rendering and multi-track container muxing (`.mp4`, `.mkv`).
  - Online stream resolution via `yt-dlp` for web videos and network URLs.
  - Speaker diarization attribution hook (`pyannote`) and audio source separation hook (`demucs`).
- **Cost Accounting & Configuration:**
  - Usage tracking across STT audio seconds, translation characters, and TTS characters.
  - User-configurable `pricing.toml` with cost ceiling protection (`VOXSTREAM_MAX_COST_USD`).
  - Persistent SQLite WAL cache surviving process restarts.
- **User Interface & Tooling:**
  - PySide6 desktop GUI with embedded video surface, seek-buffer progress bar, and masked API key settings.
  - `voxstream doctor` diagnostic command verifying system dependencies and GPU hardware.
  - CLI subcommands: `play`, `process`, `export-srt`, `cache`, `doctor`, `providers`, `gui`.
