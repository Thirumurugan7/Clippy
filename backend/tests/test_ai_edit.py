import pytest

from backend.ai_edit import parse_ai_edit


def test_parse_ok():
    raw = '{"clip":{"start":10,"end":50},"aspect":"9:16","caption_preset":"hormozi","reason":"hook"}'
    r = parse_ai_edit(raw, 120)
    assert r["clip"]["start"] == 10 and r["clip"]["end"] == 50
    assert r["aspect"] == "9:16" and r["caption_preset"] == "hormozi"


def test_parse_clamps_and_validates():
    raw = '{"clip":{"start":-5,"end":9999},"aspect":"weird","caption_preset":"nope","reason":"x"}'
    r = parse_ai_edit(raw, 120)
    assert r["clip"]["start"] >= 0 and r["clip"]["end"] <= 120
    assert r["aspect"] == "9:16"
    assert r["caption_preset"] == "karaoke"


def test_parse_bad_json_raises():
    with pytest.raises(Exception):
        parse_ai_edit("not json", 120)
