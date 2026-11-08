# Architecture Decision Records (ADRs)

This document tracks significant design choices, tradeoffs, and rationale for VoxStream.

---

## ADR-001: Separation of Audio Mixer from Video Player

- **Date:** 2026-11-08
- **Status:** Accepted
- **Context:** `libmpv` provides audio playback, but loading and mixing dynamically synthesized speech clips on precise sub-second timelines while simultaneously ducking the original audio track is difficult through mpv's internal filters in real time.
- **Decision:** Build an independent audio output mixer using `sounddevice` (PortAudio callback) and slave its playback clock to `mpv`'s `time-pos` property. The original audio in mpv is attenuated via volume properties during dub playback.
- **Tradeoff:** Requires managing buffer drift and audio hardware latency explicitly, but provides total control over clip scheduling, crossfades, and pitch stretching.

---

## ADR-002: Strict Abstract Protocols for All Providers

- **Date:** 2026-11-08
- **Status:** Accepted
- **Context:** Relying directly on vendor SDKs (e.g. OpenAI SDK, ElevenLabs client) creates tight coupling and makes offline unit testing dependent on network credentials and API quotas.
- **Decision:** Every external dependency (STT, Translation, TTS) must implement a Python `typing.Protocol` with typed dataclass inputs and outputs.
- **Consequence:** Pipeline logic never touches vendor clients directly. A complete set of `fake` mock providers allows the entire suite to run offline in CI without network access.

---

## ADR-003: Look-Ahead Scheduling with Generation Counters

- **Date:** 2026-11-08
- **Status:** Accepted
- **Context:** In a live video player, users frequently pause, seek forward, or seek backward. In-flight API requests for obsolete playback regions waste tokens and compute.
- **Decision:** Every seek increments a monotonically increasing `generation` ID. Chunks are scheduled in priority order relative to the current playhead. Completed tasks from stale generations are cached in SQLite (since their transcripts are valid for future seeks) but do not trigger mixer updates. In-flight cancellable tasks outside the active look-ahead window are cancelled immediately.

---

## ADR-004: Length-Constrained Translation with Character Budgets

- **Date:** 2026-11-08
- **Status:** Accepted
- **Context:** Unconstrained translation models generate natural prose that often has far more syllables than the source language audio slot, causing audio collisions or extreme speedup.
- **Decision:** Compute an explicit `max_chars` budget based on standard speech rates per target language and pass it directly in the translation schema.
