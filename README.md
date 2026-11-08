# VoxStream

> **Status: Pre-alpha (Active Development)**  
> Milestone 0 bootstrap complete. CLI commands and pipeline components are under active development. See [Milestones](#milestones) below.

Most video translation workflows are offline batch jobs: you feed in a 45-minute video, wait 15 minutes for Whisper and a cloud TTS provider to transcribe, translate, and synthesize everything, and only then get a dub back. That is fine for publishing content, but it does not work when you simply want to sit down and watch an untranslated talk, foreign documentary, or overseas stream right now.

**VoxStream** is an open-source media player designed to solve that. It translates speech into subtitles and synchronized dubbing audio *while the video plays* by maintaining a rolling look-ahead window 1–2 minutes ahead of your playback position.

```
                    +--------------------------------------------+
                    |        libmpv Playback Engine              |
                    | (Video Surface + Master time-pos Clock)    |
                    +----------------------+---------------------+
                                           |
                [Clock Sync & Seek Events] | [OSD Subtitle Overlay]
                                           v
+----------------+      +------------------+-------------------+      +----------------+
| Audio Chunks   | ---> | Pipeline Scheduler                   | ---> | PortAudio      |
| (ffmpeg/VAD)   |      | • Stage 1: STT (faster-whisper / API)|      | Custom Mixer   |
| 30s + overlap  |      | • Stage 2: Length-constrained LLM    |      | (Ducked master |
+----------------+      | • Stage 3: TTS + Elastic Time-Fit    |      |  + Dub clips)  |
                        +--------------------------------------+      +----------------+
```

---

## Why Timing is Hard (and How VoxStream Solves It)

Translating and dubbing on the fly is fundamentally a timing problem, not just a model inference problem:

1. **Syllable rate mismatch:** A thought expressed in 10 English words often takes 30% more syllables when translated to Spanish or German. If a synthesized dub clip is longer than the speaker's original utterance, it will bleed into the next sentence.
   - **Fix:** VoxStream computes a character and duration budget (`max_chars`) based on language-specific speaking rates and passes it into the translation prompt. If the synthesized audio is still slightly too long, it applies pitch-preserving time stretching (up to 1.25x). If it still exceeds the gap, it retranslates once with a tighter paraphrase constraint.

2. **Chunk boundaries cutting mid-sentence:** Audio split naively every 30 seconds will chop words in half and hallucinate punctuation.
   - **Fix:** VoxStream runs voice activity detection (VAD) around candidate boundaries to snap cuts to natural silences, pads each chunk with 2 seconds of audio context, and de-duplicates segments using midpoint ownership.

3. **Audio clock drift:** Bluetooth headphones, buffer underruns, and operating system audio mixers cause independent audio streams to drift out of sync over time.
   - **Fix:** The VoxStream audio mixer anchors its sample timeline directly to `mpv`'s `time-pos` clock. If the monotonic drift between the player clock and the dub mixer exceeds 80ms, it smoothly crossfades back into sync instead of hard-cutting.

---

## Architecture & Providers

All speech and language models sit behind clean, decoupled Python protocols. You can swap between 100% local offline execution and cloud APIs:

| Stage | Default / Local | Cloud / Alternatives |
|---|---|---|
| **STT (Transcription)** | `faster-whisper` (CPU int8 / CUDA) | OpenAI Whisper API, Groq |
| **Translation** | Ollama / LM Studio (OpenAI-compatible) | OpenAI (`gpt-4o-mini`), Anthropic Claude, DeepL |
| **TTS (Speech Synth)** | `edge-tts` (zero-config, high quality) | ElevenLabs, OpenAI TTS, local Piper |
| **Player & Subtitles** | `libmpv` via `python-mpv` | OSD ASS overlay with word wrapping |
| **Dub Mixer** | `sounddevice` (PortAudio callback) | Dynamic volume ducking (-14 dB default) |

---

## Prerequisites

VoxStream relies on standard multimedia tools:

- **Python 3.11+**
- **FFmpeg & FFprobe:** Installed on your system `PATH`.
- **libmpv:** Required for video rendering.
  - **Linux (Ubuntu/Debian):** `sudo apt install ffmpeg libmpv-dev libmpv2`
  - **macOS (Homebrew):** `brew install ffmpeg mpv`
  - **Windows:** Download static builds of `ffmpeg` and `mpv-dev` and add them to your `PATH`.

---

## Quickstart

VoxStream is packaged with modern Python tooling using `uv`:

```bash
# Clone the repository
git clone https://github.com/whrizkey/voxstream.git
cd voxstream

# Install dependencies in an isolated virtual environment
uv sync --all-extras

# Run the system diagnostic to verify your environment
uv run voxstream doctor
```

### Checking Your Environment (`voxstream doctor`)

The `doctor` command inspects your system for required binaries, audio output devices, and available GPU acceleration:

```
$ uv run voxstream doctor

VoxStream System Diagnostics
----------------------------
[OK] Python 3.11.9
[OK] ffmpeg found (/usr/bin/ffmpeg)
[OK] ffprobe found (/usr/bin/ffprobe)
[OK] libmpv dynamic library loaded
[OK] Audio output device detected: Default PulseAudio
[INFO] GPU Acceleration: CUDA available (NVIDIA GeForce RTX 4090)
[INFO] Usable Providers: faster-whisper, openai_compat, edge-tts
```

---

## Planned CLI Usage

```bash
# Watch a video with live translated Japanese subtitles
voxstream play lecture.mp4 --to ja --mode subs

# Watch a video dubbed into Spanish while ducking original audio
voxstream play interview.mkv --to es --mode dub

# Offline processing: produce .srt, dub .wav, and muxed .mp4 without playing
voxstream process documentary.mp4 --to de --out ./output/ --mux

# Manage local segment & transcription cache
voxstream cache info
voxstream cache prune --max-gb 5
```

---

## Milestones & Roadmap

- [x] **M0: Bootstrap & Architecture Skeleton** (Current)
  - Typed project structure, `pyproject.toml`, ruff/mypy/pytest CI.
  - `voxstream doctor` diagnostic command.
  - Protocol specifications and core data models.
- [ ] **M1: Provider Foundation & Offline Fixtures**
  - Concrete `SttProvider`, `TranslateProvider`, and `TtsProvider` protocols.
  - Fake mock providers for 100% offline unit/integration test coverage without API keys.
- [ ] **M2: Subtitles Pipeline (`process --mode subs`)**
  - Silence-aware chunking, midpoint de-duplication, and SRT export.
- [ ] **M3: Dubbing Pipeline (`process --mode dub`)**
  - Time-fit algorithm, duration scaling, ducked audio export.
- [ ] **M4: Live Player & Subtitles**
  - mpv event loop integration and look-ahead chunk scheduler.
- [ ] **M5: Live Dubbing Mixer**
  - Real-time PortAudio mixer with monotonic clock slaved to mpv `time-pos`.
- [ ] **M6: Extended Provider Suite & Cost Accounting**
  - Anthropic, DeepL, ElevenLabs, Piper, token/cost estimation before playback.
- [ ] **M7: Desktop UI (PySide6 / Qt6)**
  - Embedded player window, seek-buffer progress bar, and settings dialog.

---

## Testing

VoxStream uses `pytest` with a fake provider suite to test the entire media pipeline without hitting external networks or requiring API tokens:

```bash
# Run unit and integration tests
uv run pytest

# Run linting and type checking
uv run ruff check .
uv run mypy
```

---

## License

Licensed under the [Apache License, Version 2.0](LICENSE).  
Dependencies such as `libmpv` are linked dynamically.
