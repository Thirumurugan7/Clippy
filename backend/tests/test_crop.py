from backend.crop import compute_crop, target_dims


def test_target_dims():
    assert target_dims("9:16") == (1080, 1920)
    assert target_dims("4:5") == (1080, 1350)
    assert target_dims("1:1") == (1080, 1080)


def test_crop_landscape_to_916_centered():
    sx, sy, cw, ch = compute_crop(1920, 1080, "9:16", 0.5)
    assert ch == 1080 and cw == round(1080 * 9 / 16)
    assert sx == round((1920 - cw) / 2) and sy == 0


def test_crop_pans_and_clamps():
    sx, _, cw, _ = compute_crop(1920, 1080, "9:16", 0.0)
    assert sx == 0
    sx2, _, cw2, _ = compute_crop(1920, 1080, "9:16", 1.0)
    assert sx2 == 1920 - cw2


def test_crop_169_is_full_width():
    sx, sy, cw, ch = compute_crop(1920, 1080, "16:9", 0.5)
    assert cw == 1920 and ch == 1080
