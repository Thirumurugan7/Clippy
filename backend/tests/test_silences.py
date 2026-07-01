from backend.silences import (
    _parse_silencedetect, _pad_and_filter, detect_silences, total_silence,
)

SAMPLE = """\
[silencedetect @ 0x1] silence_start: 3.214
[silencedetect @ 0x1] silence_end: 5.007 | silence_duration: 1.793
[silencedetect @ 0x1] silence_start: 10.0
[silencedetect @ 0x1] silence_end: 10.9 | silence_duration: 0.9
"""


def test_parse_pairs_start_and_end():
    out = _parse_silencedetect(SAMPLE)
    assert out == [
        {"start": 3.214, "end": 5.007},
        {"start": 10.0, "end": 10.9},
    ]


def test_parse_open_ended_uses_duration():
    log = "[silencedetect @ 0x1] silence_start: 8.0\n"
    assert _parse_silencedetect(log, duration=12.0) == [{"start": 8.0, "end": 12.0}]
    # unknown duration -> the dangling silence is dropped
    assert _parse_silencedetect(log) == []


def test_parse_ignores_noise_lines():
    assert _parse_silencedetect("random ffmpeg banner\nframe= 100 ...\n") == []


def test_pad_shrinks_inward_and_drops_slivers():
    ranges = [{"start": 3.0, "end": 5.0}, {"start": 10.0, "end": 10.3}]
    out = _pad_and_filter(ranges, pad=0.1, min_silence=0.6)
    # first range: 3.1..4.9 kept; second (0.3s) dropped after padding
    assert out == [{"start": 3.1, "end": 4.9}]


def test_total_silence():
    assert total_silence([{"start": 1.0, "end": 2.5}, {"start": 4.0, "end": 4.5}]) == 2.0


def test_detect_silences_missing_file_is_empty():
    # ffmpeg fails on a nonexistent input -> no ranges, no exception.
    assert detect_silences("/no/such/file.mp4") == []


def test_detect_silences_on_real_short_returns_list():
    from backend import db
    with db.get_conn() as c:
        row = c.execute(
            "SELECT stored_path, duration_seconds FROM videos "
            "WHERE original_filename LIKE 'sample_short%' "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if not row:
        import pytest
        pytest.skip("no seeded sample_short video")
    ranges = detect_silences(row["stored_path"], duration=row["duration_seconds"])
    assert isinstance(ranges, list)
    for r in ranges:  # whatever it finds must be well-formed and in-bounds
        assert 0.0 <= r["start"] < r["end"] <= (row["duration_seconds"] or 1e9)
