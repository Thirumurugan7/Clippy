from backend.subtitle_edit import replace_cue_words


def _words():
    return [
        {"i": 0, "word": "hello", "start": 0.0, "end": 0.5, "prob": 0.9},
        {"i": 1, "word": "wrold", "start": 0.5, "end": 1.0, "prob": 0.3},  # typo to fix
        {"i": 2, "word": "again", "start": 2.0, "end": 2.5, "prob": 0.9},  # outside the cue
    ]


def test_replace_fixes_text_and_retimes():
    out = replace_cue_words(_words(), 0.0, 1.0, "hello world")
    texts = [w["word"] for w in out]
    assert texts == ["hello", "world", "again"]
    # the two new words split the 0..1.0 span evenly
    assert out[0]["start"] == 0.0 and abs(out[1]["end"] - 1.0) < 1e-6
    # the outside word is untouched
    assert out[2]["start"] == 2.0
    # indices renumbered
    assert [w["i"] for w in out] == [0, 1, 2]


def test_replace_changes_word_count():
    out = replace_cue_words(_words(), 0.0, 1.0, "a b c d")
    assert [w["word"] for w in out][:4] == ["a", "b", "c", "d"]
    assert len(out) == 5  # 4 new + "again"


def test_empty_text_removes_cue_words():
    out = replace_cue_words(_words(), 0.0, 1.0, "")
    assert [w["word"] for w in out] == ["again"]
