# Dependency Licenses & Third-Party Notice

VoxStream is open source under the **Apache-2.0 License**.

When distributing binaries, packaging installers, or integrating external libraries, take note of third-party licensing considerations:

---

## 1. libmpv & FFmpeg

- **libmpv** is licensed under LGPL v2.1+ or GPL v2+ depending on its build configuration.
- **FFmpeg** is licensed under LGPL v2.1+ or GPL v2+ depending on included flags (such as `--enable-gpl` or `--enable-nonfree`).
- **Policy:** VoxStream dynamically links to `libmpv` via `python-mpv` and executes system `ffmpeg` binaries via subprocesses. VoxStream does not bundle static GPL binaries in its source distribution.

---

## 2. TTS & Cloud Services

- `edge-tts`: Relies on an unofficial route to Microsoft's neural TTS service. It is provided for evaluation and personal use on a best-effort basis without guarantees of uptime or commercial rights.
- Cloud providers (OpenAI, Anthropic, ElevenLabs, DeepL): User audio and text segments are transmitted across the network to chosen API endpoints. Users must review and adhere to the respective vendor data policies and terms of service.
