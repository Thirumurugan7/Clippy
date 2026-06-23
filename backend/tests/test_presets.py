from backend.presets import ASPECTS, CAPTION_PRESETS, resolve_caption_style


def test_aspects():
    assert ASPECTS["9:16"]["w"] == 1080 and ASPECTS["9:16"]["h"] == 1920
    assert ASPECTS["16:9"]["w"] == 1920 and ASPECTS["16:9"]["h"] == 1080
    assert abs(ASPECTS["1:1"]["ratio"] - 1.0) < 1e-6
    assert ASPECTS["4:5"]["w"] == 1080 and ASPECTS["4:5"]["h"] == 1350


def test_twelve_presets():
    assert len(CAPTION_PRESETS) >= 12
    assert "hormozi" in CAPTION_PRESETS and CAPTION_PRESETS["hormozi"]["uppercase"]
    # every preset has the full schema keys
    keys = {"font", "fontsize", "primary", "upcoming", "outline_color", "outline_width",
            "uppercase", "word_box", "active_box", "line_band", "glow", "gradient",
            "position", "max_words"}
    for name, p in CAPTION_PRESETS.items():
        assert keys <= set(p.keys()), f"{name} missing {keys - set(p.keys())}"


def test_resolve_overrides():
    s = resolve_caption_style({"preset": "karaoke", "fontsize": 70, "color": "#00ff00", "position": "center"})
    assert s["fontsize"] == 70 and s["primary"] == "#00ff00" and s["position"] == "center"


def test_resolve_unknown_preset_falls_back():
    s = resolve_caption_style({"preset": "nope"})
    assert s["fontsize"] > 0
