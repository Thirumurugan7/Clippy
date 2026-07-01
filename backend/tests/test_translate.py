from backend.translate import (
    _parse, translate_lines, translate_cues, translated_caption_lines,
    _cue_to_words, LANGUAGES,
)


def test_parse_valid():
    assert _parse('{"lines": ["hola", "mundo"]}', 2) == ["hola", "mundo"]


def test_parse_pads_and_trims_to_n():
    assert _parse('{"lines": ["a"]}', 2) == ["a", ""]
    assert _parse('{"lines": ["a","b","c"]}', 2) == ["a", "b"]


def test_parse_bad_json_is_none():
    assert _parse("not json", 2) is None
    assert _parse('{"nope": 1}', 2) is None


def test_unknown_language_returns_source():
    assert translate_lines(["hello"], "xx") == ["hello"]
    assert translate_lines([], "es") == []


def test_translate_lines_to_spanish_real_model():
    # Real gemma4 round-trip — output should differ from the English source.
    out = translate_lines(["Hello, how are you today?"], "es")
    assert len(out) == 1 and out[0]
    assert out[0].strip().lower() != "hello, how are you today?"


def test_translate_cues_preserves_timing():
    cues = [{"start": 0.0, "end": 1.0, "text": "Good morning"}]
    out = translate_cues(cues, "es")
    assert out[0]["start"] == 0.0 and out[0]["end"] == 1.0
    assert out[0]["text"]  # non-empty translation (or source fallback)


def test_cue_to_words_spreads_timing_evenly():
    line = _cue_to_words({"start": 0.0, "end": 3.0, "text": "uno dos tres"})
    assert [w["word"] for w in line["words"]] == ["uno", "dos", "tres"]
    assert line["words"][0]["virtual_start"] == 0.0
    assert line["words"][1]["virtual_start"] == 1.0
    assert line["words"][-1]["virtual_end"] == 3.0
    assert line["start"] == 0.0 and line["end"] == 3.0


def test_cue_to_words_handles_empty_text():
    line = _cue_to_words({"start": 0.0, "end": 1.0, "text": "   "})
    assert line["words"] == []


def test_translated_caption_lines_empty_language_is_noop():
    cues = [{"start": 0.0, "end": 1.0, "text": "hi"}]
    assert translated_caption_lines(cues, "") == []
    assert translated_caption_lines(cues, "xx") == []


def test_translated_caption_lines_are_burnable_and_ordered():
    cues = [
        {"start": 0.0, "end": 1.5, "text": "Good morning everyone"},
        {"start": 2.0, "end": 3.5, "text": "Welcome back"},
    ]
    lines = translated_caption_lines(cues, "es")
    assert len(lines) == 2
    for ln, src in zip(lines, cues):
        assert ln["words"]  # each cue stays one coherent, non-empty line
        assert ln["start"] == src["start"]
        # every word carries burn-in timing keys the renderer expects
        for w in ln["words"]:
            assert {"word", "virtual_start", "virtual_end"} <= set(w)
            assert w["virtual_start"] <= w["virtual_end"]
