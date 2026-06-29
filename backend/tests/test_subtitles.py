from backend.subtitles import build_srt, build_vtt, group_cues, _fmt_ts


WORDS = [
    {"word": "Hello", "virtual_start": 0.0, "virtual_end": 0.4},
    {"word": "world", "virtual_start": 0.4, "virtual_end": 0.9},
    # gap > 0.7 forces a new cue
    {"word": "Second", "virtual_start": 3.0, "virtual_end": 3.5},
    {"word": "line", "virtual_start": 3.5, "virtual_end": 4.0},
]


def test_fmt_ts_srt_and_vtt():
    assert _fmt_ts(0, ",") == "00:00:00,000"
    assert _fmt_ts(3661.5, ",") == "01:01:01,500"
    assert _fmt_ts(3661.5, ".") == "01:01:01.500"


def test_group_cues_splits_on_gap():
    cues = group_cues(WORDS)
    assert len(cues) == 2
    assert cues[0]["text"] == "Hello world"
    assert cues[1]["text"] == "Second line"
    assert cues[0]["end"] > cues[0]["start"]


def test_build_srt_format():
    srt = build_srt(WORDS)
    assert srt.startswith("1\n00:00:00,000 --> 00:00:00,900\nHello world")
    assert "2\n00:00:03,000 --> 00:00:04,000\nSecond line" in srt


def test_build_vtt_format():
    vtt = build_vtt(WORDS)
    assert vtt.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:00.900\nHello world" in vtt


def test_empty_words():
    assert build_srt([]) == ""
    assert build_vtt([]).startswith("WEBVTT")
