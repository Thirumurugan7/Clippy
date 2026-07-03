from backend.social import _parse, generate_social


def test_parse_normalizes_hashtags_and_clamps():
    raw = '{"title": "T", "hook": "H", "description": "D", "hashtags": ["fun", "#viral"]}'
    out = _parse(raw)
    assert out["title"] == "T" and out["hook"] == "H" and out["description"] == "D"
    assert out["hashtags"] == ["#fun", "#viral"]  # bare tags get a leading #


def test_parse_hashtags_as_string():
    out = _parse('{"title":"x","hashtags":"#a #b #c"}')
    assert out["hashtags"] == ["#a", "#b", "#c"]


def test_parse_bad_json_is_none():
    assert _parse("not json") is None
    assert _parse("[1,2,3]") is None


def test_generate_social_real_model_shape():
    # Real gemma4 over the seeded transcript — must return the 4 keys, no crash.
    from backend import db
    with db.get_conn() as c:
        row = c.execute(
            "SELECT v.id FROM videos v JOIN transcripts t ON t.video_id=v.id "
            "WHERE v.original_filename LIKE 'sample_short%' ORDER BY v.created_at DESC LIMIT 1"
        ).fetchone()
    if not row:
        import pytest
        pytest.skip("no seeded sample_short video")
    out = generate_social(row["id"])
    assert set(out) == {"title", "hook", "description", "hashtags"}
    assert isinstance(out["hashtags"], list)
