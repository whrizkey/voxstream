"""Unit tests for in-memory SubtitleStore and cue lookup."""

from voxstream.playback.subtitles import Cue, SubtitleStore


def test_subtitle_store_ordering_and_non_overlap() -> None:
    store = SubtitleStore()

    cue2 = Cue(start=5.0, end=9.0, text="Second cue")
    cue1 = Cue(start=1.0, end=6.0, text="First cue")  # Overlaps cue2

    store.add_cues([cue2, cue1])

    cues = store.all_cues()
    assert len(cues) == 2
    assert cues[0].start == 1.0
    # Overlap was resolved: cue1 end trimmed to cue2 start
    assert cues[0].end == 5.0
    assert cues[1].start == 5.0


def test_subtitle_store_binary_search_lookup() -> None:
    store = SubtitleStore()
    store.add_cues(
        [
            Cue(start=2.0, end=4.0, text="Cue A"),
            Cue(start=5.0, end=8.0, text="Cue B"),
            Cue(start=10.0, end=15.0, text="Cue C"),
        ]
    )

    # In silence
    assert store.get_active_cue(1.0) is None
    assert store.get_active_cue(4.5) is None

    # Inside Cue A
    cue = store.get_active_cue(2.5)
    assert cue is not None
    assert cue.text == "Cue A"

    # Inside Cue B
    cue = store.get_active_cue(7.9)
    assert cue is not None
    assert cue.text == "Cue B"

    # Beyond end
    assert store.get_active_cue(20.0) is None
