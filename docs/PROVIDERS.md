# Providers Guide

VoxStream decouples pipeline stages through abstract protocols. This guide covers how providers are configured, their behavioral contracts, and estimated usage costs.

---

## 1. Speech-to-Text (STT)

### `faster_whisper` (Local, Default)
- **Engine:** CTranslate2 implementation of OpenAI Whisper.
- **Execution:** Runs locally on CPU (int8 quantization) or GPU (CUDA).
- **Pros:** Completely private, zero cost, no external network calls.
- **Cons:** Model weights require initial download; CPU transcription can struggle to maintain real-time lookahead on older machines without AVX512/GPU.
- **Cost:** $0.00 (Local compute).

### `openai_compat` (Cloud)
- **Engine:** Standard HTTP `multipart/form-data` audio transcription endpoint.
- **Compatible with:** OpenAI (`whisper-1`), Groq Whisper, local vLLM.
- **Configuration:** `OPENAI_API_KEY`, `OPENAI_BASE_URL`.
- **Cost:** ~$0.006 per audio minute (OpenAI pricing).

---

## 2. Translation

### `openai_compat` (Default)
- **Engine:** Chat completions JSON mode.
- **Compatible with:** OpenAI (`gpt-4o-mini`), Ollama (`llama3.1`, `qwen2.5`), LM Studio, Groq, OpenRouter.
- **Prompt Contract:** Translates an array of `{id, text, max_chars}` segments while receiving preceding translated lines for conversational context.
- **Cost:** ~$0.15 per 1M input tokens with `gpt-4o-mini` (or free with local Ollama).

### `anthropic`
- **Engine:** Anthropic Messages API (`claude-3-5-haiku`).
- **Configuration:** `ANTHROPIC_API_KEY`.
- **Cost:** ~$0.25 per 1M input tokens.

### `deepl`
- **Engine:** DeepL Document/Text Translation API.
- **Configuration:** `DEEPL_API_KEY`.
- **Cost:** Free tier (500k chars/month) or ~$20 per 1M characters on DeepL Pro.

---

## 3. Text-to-Speech (TTS)

### `edge` (Default)
- **Engine:** Microsoft Edge online neural text-to-speech.
- **Pros:** Natural-sounding multilingual neural voices, no API key required.
- **Cons:** Dependent on an unofficial upstream service endpoint; mark as best-effort.
- **Cost:** Free.

### `openai`
- **Engine:** OpenAI Audio Speech API (`tts-1`).
- **Configuration:** `OPENAI_API_KEY`.
- **Cost:** ~$0.015 per 1,000 characters.

### `elevenlabs`
- **Engine:** ElevenLabs Turbo v2.5.
- **Configuration:** `ELEVENLABS_API_KEY`.
- **Pros:** Ultra-realistic voice timbre and cadence.
- **Cost:** ~$0.15 per 1,000 characters.

### `piper` (Local Offline)
- **Engine:** Fast, local neural text-to-speech engine optimized for CPU.
- **Pros:** 100% offline, low latency, runs well on Raspberry Pi and laptops.
- **Cost:** Free (Local compute).

---

## 4. Fake / Mock Providers

Each interface provides a deterministic `fake` implementation:
- `fake` STT: Reads predefined segments from test fixtures.
- `fake` Translate: Prefixes text with `[{target_lang}]`.
- `fake` TTS: Generates a lightweight sine-wave tone whose duration is proportional to input character count.

All unit and integration tests run exclusively with fake providers to guarantee deterministic, key-free test passes.
