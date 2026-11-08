# Architecture & Technical Design

VoxStream translates and dubs video on the fly while playback progresses. This document details the core pipeline stages, clock synchronization model, and time-fitting mechanics.

---

## 1. Pipeline Overview

```
                      +-----------------------------+
                      | Media Source (File or URL)  |
                      +--------------+--------------+
                                     |
                                     v
                        [ Chunker & Silence Snapper ]
                        • 30s nominal duration
                        • 2s pad before/after
                        • VAD silence snap (±5s)
                                     |
                                     v
                           [ Stage 1: STT ]
                        • faster-whisper / API
                        • Midpoint de-duplication
                        • Confidence filtering
                                     |
                                     v
                        [ Stage 2: Translation ]
                        • Context window (last 5 lines)
                        • Speaking rate character budget
                        • Strict JSON schema output
                                     |
                                     v
                        [ Stage 3: TTS & Fit ]
                        • Voice synthesis to wav
                        • Rubberband / atempo time stretch (<= 1.25x)
                        • Retranslate fallback on overflow
                                     |
                                     v
                       +-------------+-------------+
                       |                           |
                       v                           v
              [ Subtitle Store ]           [ Dub Audio Mixer ]
              • ASS cues for mpv           • PortAudio stream
              • Subtitle wrapping          • Clock slaved to mpv time-pos
                                           • Dynamic audio ducking (-14 dB)
```

---

## 2. Clock Synchronization & Drift Control

Playback operates under two independent timing systems:
1. **Video/Master Clock:** Driven by `libmpv`'s `time-pos` property, updated asynchronously as video frames are decoded and rendered.
2. **Audio Output Clock:** Driven by the PortAudio / `sounddevice` callback running on a real-time OS audio thread.

### The Master Clock Anchor

The dub mixer maintains a monotonic clock anchor whenever `mpv` publishes a `time-pos` event:

$$\text{anchor} = (\text{media\_time}, \text{monotonic\_time})$$

For any sample requested by the audio hardware at timestamp $t_{\text{mono}}$, the media position is calculated as:

$$\text{media\_pos}(t_{\text{mono}}) = \text{anchor}_{\text{media}} + (t_{\text{mono}} - \text{anchor}_{\text{mono}}) \times \text{playback\_speed}$$

### Re-anchoring Thresholds

- If $|\text{estimated\_media\_pos} - \text{mpv.time\_pos}| > 80\text{ ms}$, the mixer re-anchors to avoid cumulative drift.
- Rather than abruptly jumping the audio buffer (which causes an audible click), the mixer applies a 20 ms linear crossfade between the existing stream and the re-anchored stream.
- On user seeks, the scheduler increments an internal `generation` counter. In-flight requests for older generations are discarded or background-cached, while the audio mixer immediately flushes its buffer and re-anchors at the new target time.

---

## 3. Silence-Aware Chunking & Midpoint Ownership

Extracting fixed 30-second windows without regard for speech breaks causes words to be cut mid-syllable, leading STT models to hallucinate completions or miss trailing phonemes.

### Silence Snapping
1. The chunker plans nominal 30-second boundaries: $T_0, T_1, T_2, \dots$
2. For boundary $T_i$, the system runs VAD on the audio segment $[T_i - 5\text{s}, T_i + 5\text{s}]$.
3. The boundary snaps to the quietest point within that window.
4. Each chunk is extracted with $2\text{s}$ leading and trailing padding to provide acoustic context to the STT model.

### Midpoint Ownership
Because adjacent chunks overlap, segments will be transcribed multiple times near boundaries. VoxStream eliminates duplicates deterministically:
- A segment with start time $S$ and end time $E$ has midpoint $M = \frac{S + E}{2}$.
- The segment is exclusively assigned to the chunk whose core range $[T_{\text{start}}, T_{\text{end}})$ contains $M$.

---

## 4. The Time-Fitting Algorithm (`fit.py`)

When translating speech across languages, character and syllable counts change significantly. For instance, expressing a thought in German or Spanish often requires 20–30% more time than English.

Let:
- $\text{slot} = \text{seg.end} - \text{seg.start}$
- $\text{gap} = \text{next\_seg.start} - \text{seg.end}$
- $\text{room} = \min(\text{next\_seg.start} - \text{seg.start}, \text{slot} + 1.0)$
- $\text{clip\_dur} = \text{duration of synthesized speech}$

The pure `fit()` function decides:

1. **Exact Fit:** If $\text{clip\_dur} \le \text{slot}$, play unmodified at $\text{seg.start}$ with speed factor $1.0$.
2. **Gap Overflow:** If $\text{clip\_dur} \le \text{room}$, let the speech play slightly past $\text{seg.end}$ into the natural silence gap.
3. **Time-Stretching:** If $\text{clip\_dur} > \text{room}$, compute $\text{needed} = \frac{\text{clip\_dur}}{\text{room}}$.
   - If $\text{needed} \le 1.25$: apply pitch-preserving time stretching with factor $\text{needed}$.
4. **Retranslation Paraphrase:** If $\text{needed} > 1.25$: prompt the translation model a second time with an explicit shorter character budget ($\text{max\_chars} \times \frac{1}{\text{needed}}$) and a concise paraphrasing instruction.
5. **Hard Truncation (Fallback):** If retranslation still exceeds allowable room, stretch up to $1.35\times$ and fade out the final 60 ms as a last resort to guarantee zero overlap with subsequent speakers.
