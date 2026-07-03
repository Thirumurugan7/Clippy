import numpy as np

from backend.captions import CaptionRenderer, word_anim
from backend.presets import resolve_caption_style

WORDS = [
    {"word": "hello", "virtual_start": 0.0, "virtual_end": 1.0},
    {"word": "world", "virtual_start": 1.0, "virtual_end": 2.0},
]


def _render(preset, t=0.5):
    style = resolve_caption_style({"preset": preset})
    r = CaptionRenderer(WORDS, width=1080, height=1920, style=style)
    return r.draw(np.zeros((1920, 1080, 3), np.uint8), t)


def test_draws_text_karaoke():
    out = _render("karaoke")
    assert out.shape == (1920, 1080, 3)
    assert out.sum() > 0  # something was drawn


def test_band_preset_paints_band():
    # tiktok/subtitle have a line band -> more painted pixels than clean
    clean = _render("clean").sum()
    band = _render("subtitle").sum()
    assert band > clean


def test_hormozi_uppercase_box():
    out = _render("hormozi")
    assert out.sum() > 0


def test_no_caption_when_outside_time():
    out = _render("karaoke", t=99.0)
    assert out.sum() == 0  # nothing active -> untouched black frame


def test_word_anim_none_is_identity():
    assert word_anim("none", 0.1, 0.25, 58) == (1.0, 0.0, 0.0, 1.0)


def test_word_anim_pop_biggest_at_start_then_settles():
    dur, fs = 0.25, 58
    s0 = word_anim("pop", 0.0, dur, fs)[0]
    s_mid = word_anim("pop", 0.12, dur, fs)[0]
    assert s0 > 1.25 and s0 > s_mid          # biggest at activation, eases down
    assert word_anim("pop", 0.3, dur, fs) == (1.0, 0.0, 0.0, 1.0)  # settled after dur


def test_word_anim_entrances_move_and_fade():
    dur, fs = 0.25, 58
    # float rises (dy>0 -> settles to 0), drop falls (dy<0), slide from right (dx>0)
    assert word_anim("float_in", 0.0, dur, fs)[2] > 0
    assert word_anim("drop_in", 0.0, dur, fs)[2] < 0
    assert word_anim("slide_in", 0.0, dur, fs)[1] > 0
    # scale_in grows from small and fades in
    sc, _, _, al = word_anim("scale_in", 0.0, dur, fs)
    assert sc < 0.5 and al == 0.0
    # all entrances resolve to identity once settled
    for name in ("float_in", "drop_in", "slide_in", "scale_in", "stomp", "bounce"):
        assert word_anim(name, dur + 0.01, dur, fs) == (1.0, 0.0, 0.0, 1.0)


def test_word_anim_pulse_is_continuous():
    # pulse never "settles" — it keeps oscillating around 1.0 while active
    dur, fs = 0.25, 58
    a = word_anim("pulse", 1.0, dur, fs)[0]
    assert 0.9 < a < 1.1


def test_animation_renders_a_frame():
    for name in ("pop", "float_in", "stomp", "pulse"):
        style = resolve_caption_style({"preset": "beast", "animation": name})
        assert style["animation"] == name
        r = CaptionRenderer(WORDS, width=1080, height=1920, style=style)
        out = r.draw(np.zeros((1920, 1080, 3), np.uint8), 0.02)  # word 1 just active
        assert out.shape == (1920, 1080, 3) and out.sum() > 0


def test_legacy_animate_flag_maps_to_pop():
    style = resolve_caption_style({"preset": "beast", "animate": True})
    assert style["animation"] == "pop" and style["animate"] is True


def test_is_keyword():
    from backend.captions import is_keyword
    assert is_keyword("crazy") and is_keyword("JLPT")
    assert not is_keyword("the") and not is_keyword("a") and not is_keyword("and")


def test_emphasis_recolours_keywords():
    style = resolve_caption_style({"preset": "karaoke", "emphasis": True, "emphasis_color": "#ff0000"})
    r = CaptionRenderer(WORDS, width=1080, height=1920, style=style)
    kw = {"word": "crazy", "virtual_start": 5, "virtual_end": 6}
    stop = {"word": "the", "virtual_start": 5, "virtual_end": 6}
    assert r._word_fill(kw, "upcoming") == "#ff0000"        # keyword -> emphasis colour
    assert r._word_fill(stop, "upcoming") == style["upcoming"]  # stopword -> normal


def test_speaker_colours_pick_from_palette():
    from backend.captions import SPEAKER_PALETTE
    style = resolve_caption_style({"preset": "karaoke", "speaker_colors": True})
    r = CaptionRenderer(WORDS, width=1080, height=1920, style=style)
    w0 = {"word": "hi", "virtual_start": 5, "virtual_end": 6, "speaker": 0}
    w1 = {"word": "hi", "virtual_start": 5, "virtual_end": 6, "speaker": 1}
    assert r._word_fill(w0, "past") == SPEAKER_PALETTE[0]
    assert r._word_fill(w1, "past") == SPEAKER_PALETTE[1]


def test_font_resolves_family_and_optional_file():
    from backend.presets import FONTS
    st = resolve_caption_style({"font": "impact"})
    assert st["font_family"].startswith("Impact")
    assert "impact" in FONTS
    # unknown font falls back cleanly
    assert resolve_caption_style({"font": "nope"})["font_family"] == FONTS["default"]["family"]


def test_project_words_carries_speaker():
    from backend.edl import project_words, attach_speakers
    words = [{"word": "a", "start": 0.0, "end": 0.5}, {"word": "b", "start": 0.5, "end": 1.0}]
    segs = [{"word_start": 0, "word_end": 1, "speaker": 0}, {"word_start": 1, "word_end": 2, "speaker": 1}]
    attach_speakers(words, segs)
    proj = project_words([{"sourceStart": 0.0, "sourceEnd": 1.0}], words)
    assert proj[0]["speaker"] == 0 and proj[1]["speaker"] == 1


def _reveal_renderer(reveal):
    style = resolve_caption_style({"preset": "karaoke", "reveal": reveal})
    return CaptionRenderer(WORDS, width=1080, height=1920, style=style)


def test_reveal_unknown_falls_back_to_highlight():
    assert resolve_caption_style({"reveal": "nope"})["reveal"] == "highlight"
    assert resolve_caption_style({"reveal": "word"})["reveal"] == "word"


def test_reveal_word_shows_only_active_word():
    r = _reveal_renderer("word")  # WORDS: hello[0,1], world[1,2]
    assert r._visible(WORDS[0], 0.5) and not r._visible(WORDS[1], 0.5)
    assert not r._visible(WORDS[0], 1.5) and r._visible(WORDS[1], 1.5)
    assert r._state(WORDS[0], 0.5) == "active"


def test_reveal_build_accumulates_then_stays():
    r = _reveal_renderer("build")
    assert r._visible(WORDS[0], 0.5) and not r._visible(WORDS[1], 0.5)   # world not started
    assert r._visible(WORDS[0], 1.5) and r._visible(WORDS[1], 1.5)        # both now shown
    assert r._state(WORDS[0], 1.5) == "past"     # already spoken, stays bright
    assert r._state(WORDS[1], 1.5) == "active"


def test_reveal_line_is_static_uniform():
    r = _reveal_renderer("line")
    assert r._visible(WORDS[0], 0.5) and r._visible(WORDS[1], 0.5)
    assert r._state(WORDS[0], 0.5) == "line" and r._state(WORDS[1], 0.5) == "line"


def test_reveal_highlight_dims_non_active():
    r = _reveal_renderer("highlight")
    assert r._state(WORDS[0], 0.5) == "active"
    assert r._state(WORDS[1], 0.5) == "upcoming"


def test_reveal_word_renders_a_frame():
    out = _reveal_renderer("word").draw(np.zeros((1920, 1080, 3), np.uint8), 0.5)
    assert out.shape == (1920, 1080, 3) and out.sum() > 0


def test_pregrouped_lines_bypass_word_grouping():
    # Translated line-level captions are handed in as `lines` and must be used
    # verbatim (one coherent cue) instead of being regrouped by max_words.
    lines = [{
        "start": 0.0, "end": 3.0,
        "words": [
            {"word": "hola", "virtual_start": 0.0, "virtual_end": 1.0},
            {"word": "mundo", "virtual_start": 1.0, "virtual_end": 2.0},
            {"word": "entero", "virtual_start": 2.0, "virtual_end": 3.0},
        ],
    }]
    style = resolve_caption_style({"preset": "karaoke"})  # max_words=4
    r = CaptionRenderer([], width=1080, height=1920, style=style, lines=lines)
    assert r.lines == lines  # not regrouped
    out = r.draw(np.zeros((1920, 1080, 3), np.uint8), 1.5)
    assert out.shape == (1920, 1080, 3) and out.sum() > 0
