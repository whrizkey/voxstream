"""Stage 2: Translation with context awareness and length constraints."""

import math

from voxstream.languages import get_speaking_rate
from voxstream.models import Segment, TranslatedSegment
from voxstream.pipeline.glossary import Glossary
from voxstream.providers.base import TranslateItem, TranslateProvider


async def translate_segments(
    provider: TranslateProvider,
    segments: list[Segment],
    *,
    target_lang: str,
    source_lang: str | None = None,
    context: list[str] | None = None,
    for_dubbing: bool = False,
    glossary: Glossary | None = None,
    two_pass: bool = False,
) -> list[TranslatedSegment]:
    """Translate list of segments into target language with optional dubbing budgets and glossary."""
    if not segments:
        return []

    context_lines = list(context or [])
    if glossary:
        hints = glossary.get_prompt_hints()
        if hints:
            context_lines.append(hints)

    rate = get_speaking_rate(target_lang)

    # Check for same language passthrough
    first_lang = source_lang or segments[0].language
    if first_lang and first_lang.lower().split("-")[0] == target_lang.lower().split("-")[0]:
        return [
            TranslatedSegment(
                seg=seg,
                target_lang=target_lang,
                text=glossary.apply(seg.text) if glossary else seg.text,
                provider="passthrough",
            )
            for seg in segments
        ]

    # Batch segments into TranslateItems
    items: list[TranslateItem] = []
    for i, seg in enumerate(segments):
        slot_seconds = seg.end - seg.start
        # Calculate available room for dubbing if next segment is known
        if for_dubbing:
            room = slot_seconds + 0.5
            if i + 1 < len(segments):
                room = min(segments[i + 1].start - seg.start, slot_seconds + 0.5)
            max_chars = math.floor(room * rate * 1.1)
        else:
            max_chars = None

        items.append(
            TranslateItem(
                id=seg.seg_id,
                text=seg.text,
                max_chars=max_chars,
                duration=slot_seconds,
            )
        )

    try:
        results = await provider.translate(
            items,
            source_lang=source_lang,
            target_lang=target_lang,
            context=context_lines,
        )
        results_map = {r.id: r.text for r in results}
    except Exception:
        # Fallback to original text if provider fails
        results_map = {item.id: item.text for item in items}

    # Pass 2: Refine overflowing segments if requested
    if two_pass and for_dubbing:
        refine_items: list[TranslateItem] = []
        for item in items:
            cur_text = results_map.get(item.id, "")
            if item.max_chars and len(cur_text) > item.max_chars:
                refine_items.append(
                    TranslateItem(
                        id=item.id,
                        text=f"Please shorten this translation strictly under {item.max_chars} chars: {cur_text}",
                        max_chars=item.max_chars,
                        duration=item.duration,
                    )
                )
        if refine_items:
            try:
                refine_results = await provider.translate(
                    refine_items,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    context=["Make translations concise to fit strict audio timing budgets."],
                )
                for r in refine_results:
                    if len(r.text) <= (refine_items[0].max_chars or 9999):
                        results_map[r.id] = r.text
            except Exception:
                pass

    translated_segments: list[TranslatedSegment] = []
    for seg in segments:
        text = results_map.get(seg.seg_id, seg.text)
        if glossary:
            text = glossary.apply(text)
        translated_segments.append(
            TranslatedSegment(
                seg=seg,
                target_lang=target_lang,
                text=text,
                provider=provider.name,
            )
        )

    return translated_segments
