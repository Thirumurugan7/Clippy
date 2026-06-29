import numpy as np

from backend.captions import CaptionRenderer, _pop_scale
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


def test_pop_scale_curve():
    w = {"word": "x", "virtual_start": 1.0, "virtual_end": 2.0}
    assert _pop_scale(1.0, w) > 1.2          # biggest right at activation
    assert _pop_scale(1.0, w) > _pop_scale(1.1, w)  # eases down
    assert _pop_scale(1.5, w) == 1.0         # settled after POP_DUR
    assert _pop_scale(0.5, w) == 1.0         # not yet active


def test_animate_renders_popped_word():
    # animate=True must still produce a valid frame (popped-word render path)
    style = resolve_caption_style({"preset": "beast", "animate": True})
    assert style["animate"] is True
    r = CaptionRenderer(WORDS, width=1080, height=1920, style=style)
    out = r.draw(np.zeros((1920, 1080, 3), np.uint8), 0.02)  # just after word 1 activates
    assert out.shape == (1920, 1080, 3) and out.sum() > 0
