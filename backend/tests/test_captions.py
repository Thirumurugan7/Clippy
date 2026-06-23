import numpy as np

from backend.captions import CaptionRenderer
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
