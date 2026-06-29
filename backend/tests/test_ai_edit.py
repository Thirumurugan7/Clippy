import pytest

from backend import db
from backend.ai_edit import parse_ai_edit, _build_prompt, _history_block


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


def test_history_block_empty_is_blank():
    assert _history_block([]) == ""


def test_history_block_renders_prior_turns():
    history = [
        {"prompt": "make a 40s reel", "clip": {"start": 10.0, "end": 50.0},
         "aspect": "9:16", "caption_preset": "karaoke"},
        {"prompt": "shorter", "clip": None},
    ]
    block = _history_block(history)
    assert "make a 40s reel" in block
    assert "10-50s" in block
    assert "no valid clip" in block
    assert "refinement" in block


def test_build_prompt_includes_history():
    segs = [{"start": 0.0, "end": 5.0, "text": "hello world"}]
    history = [{"prompt": "first try", "clip": {"start": 0.0, "end": 5.0},
                "aspect": "9:16", "caption_preset": "karaoke"}]
    p = _build_prompt("make it punchier", segs, 5.0, history)
    assert "make it punchier" in p
    assert "first try" in p  # earlier turn carried into the prompt


def test_ai_edit_turns_roundtrip():
    # Use an existing video id if present; else this still exercises the schema.
    with db.get_conn() as c:
        row = c.execute("SELECT id FROM videos LIMIT 1").fetchone()
    if row is None:
        pytest.skip("no videos in test db")
    vid = row["id"]
    before = len(db.get_ai_edit_turns(vid))
    db.append_ai_edit_turn(vid, "test prompt",
                           proposal_json='{"clip":{"start":1,"end":2}}', error=None)
    after = db.get_ai_edit_turns(vid)
    assert len(after) == before + 1
    assert after[-1]["prompt"] == "test prompt"
