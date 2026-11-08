# VoxStream

[![CI](https://github.com/whrizkey/voxstream/actions/workflows/ci.yml/badge.svg)](https://github.com/whrizkey/voxstream/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checked: mypy](https://img.shields.io/badge/mypy-strict-blue)](https://mypy-lang.org/)

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
   - **Fix:** VoxStream runs energy-based voice activity detection around candidate boundaries to snap cuts to natural silences, pads each chunk with 2 seconds of audio context, and de-duplicates segments using midpoint ownership.

3. **Audio clock drift:** Bluetooth headphones, buffer underruns, and operating system audio mixers cause independent audio streams to drift out of sync over time.
   - **Fix:** The VoxStream audio mixer anchors its sample timeline directly to `mpv`'s `time-pos` clock. If the monotonic drift between the player clock and the dub mixer exceeds 80ms, it smoothly crossfades back into sync instead of hard-cutting.

---

## Feature Matrix

| Feature | Subtitles (`subs`) | Dubbing (`dub`) | Combined (`both`) |
|---|:---:|:---:|:---:|
| **Live Playback Sync** | Yes (OSD overlay) | Yes (Ducked mixer) | Yes |
| **Offline Export** | `.srt` / `.ass` | Ducked `.wav` | Muxed `.mp4` / `.mkv` |
| **Seek Recovery** | < 250ms resync | Dynamic buffer refill | Full state invalidation |
| **Speaker Diarization** | Speaker labels | Multi-voice routing | Supported |
| **Background Separation** | N/A | Vocal cut / BGM mix | Supported |
| **Dual Subtitles** | Top original / Bottom translated | N/A | Supported |

---

## Architecture & Providers

All speech and language models sit behind abstract Python protocols. You can run 100% locally and offline without external API keys, or connect cloud providers:

| Stage | Default / Local | Cloud / Alternatives |
|---|---|---|
| **STT (Transcription)** | `faster-whisper` (CPU int8 / CUDA) | OpenAI Whisper API (`openai_compat_stt`), Groq |
| **Translation** | Ollama / LM Studio (OpenAI-compatible) | OpenAI (`gpt-4o-mini`), Anthropic Claude, DeepL |
| **TTS (Speech Synth)** | `edge` (online Microsoft endpoint, zero-config) | Local Piper (offline CPU), ElevenLabs, OpenAI TTS |
| **Player & Subtitles** | `libmpv` via `python-mpv` | OSD ASS overlay with word wrapping |
| **Dub Mixer** | `sounddevice` (PortAudio callback) | Dynamic volume ducking (-14 dB default) |

---

## Quickstart

VoxStream is packaged with modern Python tooling using `uv`:

```bash
# 1. Clone the repository
git clone https://github.com/whrizkey/voxstream.git
cd voxstream

# 2. Install dependencies in an isolated virtual environment
uv sync --all-extras

# 3. Verify your system dependencies and audio devices
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

## CLI Usage

### 1. Live Playback

```bash
# Watch a video with live translated Japanese subtitles
voxstream play lecture.mp4 --to ja --mode subs

# Watch a video dubbed into Spanish while ducking original audio
voxstream play interview.mkv --to es --mode dub

# Watch with both dual-language subtitles and dubbing
voxstream play presentation.mp4 --to de --mode both

# Stream and translate directly from an online URL via yt-dlp
voxstream play "https://www.youtube.com/watch?v=..." --to es --mode subs
```

### 2. Offline Batch Processing

If you want to produce clean deliverable files for publishing or offline viewing:

```bash
# Export standard SubRip (.srt) subtitles
voxstream process talk.mp4 --to es --mode subs --out ./output/

# Export styled Advanced SubStation Alpha (.ass) subtitles with anime preset
voxstream process talk.mp4 --to ja --mode subs --out ./output/

# Produce a dubbed multi-track video file (remuxed with original video)
voxstream process documentary.mp4 --to de --mode dub --out ./output/ --mux

# Produce dual-language subtitles (original audio on top, translation below)
voxstream export-srt talk.mp4 --to es --dual --out ./output/talk_dual.srt
```

### 3. Desktop Application GUI

Launch the desktop player interface with embedded video rendering, interactive timeline seek bar showing processed lookahead buffers, and masked API key settings:

```bash
voxstream gui
# or open directly with a file:
voxstream gui movie.mp4
```

### 4. Cache Management

All transcriptions, translations, and synthesized audio chunks are stored in a persistent SQLite WAL cache. If you pause, seek back, or replay a video, cached cues load instantly:

```bash
# Inspect cache size, entry count, and hit rates
voxstream cache info

# Prune old cache entries to keep size under 5 GB
voxstream cache prune --max-gb 5

# Clear entire cache
voxstream cache clear
```

---

## Configuration & Provider Setup

Copy `.env.example` to `.env` to configure your preferred providers and API keys:

```bash
cp .env.example .env
```

### Local-Only Air-Gapped Profile (Zero API Keys)

To run completely offline with no network requests:

```bash
# STT: faster-whisper runs locally on CPU or CUDA GPU
VOXSTREAM_STT_PROVIDER=faster_whisper
VOXSTREAM_WHISPER_MODEL=base

# Translation: Point to a local Ollama or LM Studio instance
VOXSTREAM_TRANSLATE_PROVIDER=openai_compat
VOXSTREAM_OPENAI_BASE_URL=http://localhost:11434/v1
VOXSTREAM_TRANSLATE_MODEL=llama3.2

# TTS: Local neural voices using Piper (runs offline on CPU via ONNX)
VOXSTREAM_TTS_PROVIDER=piper
```

> [!IMPORTANT]
> **Edge TTS is NOT local/air-gapped.** While `edge` requires no API key, it sends text to Microsoft Edge cloud endpoints to synthesize audio. For strict offline air-gapped operation, configure `VOXSTREAM_TTS_PROVIDER=piper` with local ONNX voice models.

### Cloud Profile (OpenAI / Anthropic / DeepL / ElevenLabs)

```bash
# Cloud STT (fast transcription on low-end CPUs)
VOXSTREAM_STT_PROVIDER=openai_compat_stt
OPENAI_API_KEY=sk-...

# High-fidelity translation
VOXSTREAM_TRANSLATE_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Studio-quality voice synthesis
VOXSTREAM_TTS_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=...
```

Inspect active capabilities and missing keys at any time:

```bash
voxstream providers list
```

---

## Cost Controls & Usage Accounting

VoxStream tracks every audio second transcribed and character translated or synthesized. Costs are calculated against `pricing.toml`:

```toml
[pricing]
openai_compat_stt = 0.000100   # ~$0.006 per minute
anthropic = 0.000001           # ~$1.00 per 1M characters
elevenlabs = 0.000150          # $150.00 per 1M characters
```

### Hard Safety Ceiling

Set `VOXSTREAM_MAX_COST_USD` in your `.env` to prevent unexpected cloud bills:

```bash
# Abort processing if estimated session cost exceeds $2.50
VOXSTREAM_MAX_COST_USD=2.50
```

When a run finishes, a clear cost breakdown table is printed to your console. If projected expenditure exceeds the ceiling during execution, processing halts immediately with a `BudgetExceededError`.

---

## Privacy & Security Controls

| Provider | What leaves your machine? | Destination |
|---|---|---|
| `faster_whisper` | Nothing (runs on local CPU/GPU) | Localhost |
| `piper` | Nothing (runs on local CPU) | Localhost |
| `openai_compat` (Ollama / LM Studio) | Nothing | Localhost |
| `openai_compat_stt` (Cloud Whisper) | Audio chunks for transcription | OpenAI API |
| `openai_compat` (Cloud LLM) | Text snippets for translation | OpenAI API |
| `anthropic` | Text snippets for translation | Anthropic API |
| `deepl` | Text snippets for translation | DeepL API |
| `edge` | Text snippets for voice synthesis | Microsoft Edge TTS endpoints |
| `elevenlabs` | Text snippets for voice synthesis | ElevenLabs API |

### Security Measures
- **Credential Protection:** API keys are stored as `SecretStr` instances, preventing accidental disclosure in tracebacks or object representations. Secret redaction sanitizes bearer tokens, API keys, and HTTP 5xx error text in logs.
- **Environment Isolation:** `.env` files are not loaded blindly from arbitrary working directories. Loading is restricted to an explicit `VOXSTREAM_ENV_FILE`, `~/.config/voxstream/.env`, or the repository root containing a `.git` directory.
- **Untrusted Media Handling:** Subprocess invocations of `ffmpeg` and `ffprobe` enforce strict protocol whitelists (`-protocol_whitelist "file,http,https,tcp,tls,crypto"`), option delimiters (`--`), and prefix escaping for filenames starting with dashes.
- **Path Traversal Defenses:** Cache clearing operations validate media IDs against `^[0-9a-f]{32}$` and verify strict filesystem containment within the designated cache directory.

---

## Known Limitations

- **Live Dubbing Sync:** While live subtitle overlay runs smoothly with `mpv`, live dubbing audio mixing with dynamic ducking is experimental and can experience audio drift under high CPU load. For production-quality dubbed media files, batch processing via `voxstream process --mode dub --mux` is recommended.
- **Speed Changes:** When video playback speed is set to anything other than `1.0x` during live dubbing, dub audio is temporarily muted and original audio plays at the selected speed. Subtitles remain active. Returning to `1.0x` automatically resumes dubbing.
- **CPU Performance on Local STT:** Running `faster-whisper` large models on low-end dual-core CPUs may result in real-time factors > 1.0, causing the lookahead buffer to underrun. On machines without a discrete GPU, use `tiny` or `base` models, or use a cloud STT provider.
- **libmpv Embedding:** Embedded GUI rendering requires `libmpv` dynamic libraries (`libmpv.so.2` on Linux, `libmpv.dylib` on macOS, `mpv-2.dll` on Windows). If not found, run `voxstream doctor` for installation instructions.

---

## Testing

VoxStream includes a comprehensive offline test suite running property-based tests (`hypothesis`) and contract tests across all providers without requiring network access:

```bash
# Run full unit and integration test suite
uv run pytest

# Check code formatting and strict type checks
uv run ruff check .
uv run mypy
```

---

## Documentation

- [Architecture & Timing Synchronization](docs/ARCHITECTURE.md)
- [Provider Setup & API Guide](docs/PROVIDERS.md)
- [Technical Design Decisions](docs/DECISIONS.md)
- [Contributing Guidelines](docs/CONTRIBUTING.md)
- [Third-Party Licenses](docs/LICENSES.md)

---

## License

Licensed under the [Apache License, Version 2.0](LICENSE).  
Dependencies such as `libmpv` are linked dynamically and retain their respective open-source licenses.
