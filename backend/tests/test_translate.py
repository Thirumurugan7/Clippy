from backend.translate import _parse, translate_lines, translate_cues, LANGUAGES


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
