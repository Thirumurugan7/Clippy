import numpy as np

from backend.overlays import build_overlay_layer


def test_empty_returns_none():
    bgr, alpha = build_overlay_layer([], 1080, 1920)
    assert bgr is None and alpha is None
    bgr, alpha = build_overlay_layer([{"text": "   "}], 1080, 1920)
    assert bgr is None  # blank text ignored


def test_layer_shapes_and_alpha():
    bgr, alpha = build_overlay_layer(
        [{"text": "HELLO", "position": "top", "size": 0.07, "color": "#ffffff"}], 1080, 1920
    )
    assert bgr.shape == (1920, 1080, 3) and bgr.dtype == np.uint8
    assert alpha.shape == (1920, 1080, 1)
    assert alpha.max() > 0.5  # something was actually drawn


def test_emoji_run_renders_in_colour():
    from backend.overlays import _runs
    # run splitting separates emoji from text
    runs = _runs("🔥 3 TIPS 🔥")
    kinds = [k for k, _ in runs]
    assert "emoji" in kinds and "text" in kinds
    # the layer renders and the emoji adds colour (red channel differs from blue)
    bgr, alpha = build_overlay_layer([{"text": "🔥 HOT", "position": "center", "size": 0.08}], 1080, 1920)
    assert bgr is not None
    painted = alpha[:, :, 0] > 0.5
    assert painted.sum() > 0
    # within painted pixels, channels vary (colour emoji), not pure white text
    rb_diff = (bgr[:, :, 2].astype(int) - bgr[:, :, 0].astype(int))[painted]
    assert abs(rb_diff).max() > 30


def test_position_places_text_in_the_right_band():
    top = build_overlay_layer([{"text": "X", "position": "top", "size": 0.08}], 1080, 1920)[1][:, :, 0]
    bottom = build_overlay_layer([{"text": "X", "position": "bottom", "size": 0.08}], 1080, 1920)[1][:, :, 0]
    # painted rows should sit near the top vs near the bottom respectively
    top_rows = np.where(top.sum(axis=1) > 0)[0]
    bottom_rows = np.where(bottom.sum(axis=1) > 0)[0]
    assert top_rows.mean() < 1920 * 0.3
    assert bottom_rows.mean() > 1920 * 0.7
