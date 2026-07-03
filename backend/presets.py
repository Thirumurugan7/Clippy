"""Aspect ratios and caption presets, shared by the export (Pillow) and the
preview (canvas, via a JS mirror in frontend/src/presets.js).

Caption presets are modeled on the looks the most successful short-form creators
use. Each preset resolves to a full style dict; the renderers interpret it.
"""
from __future__ import annotations

ASPECTS = {
    "9:16": {"ratio": 9 / 16, "w": 1080, "h": 1920},
    "1:1": {"ratio": 1.0, "w": 1080, "h": 1080},
    "4:5": {"ratio": 4 / 5, "w": 1080, "h": 1350},
    "16:9": {"ratio": 16 / 9, "w": 1920, "h": 1080},
}

# Full style schema (defaults). Each preset overrides a subset.
_BASE = {
    "font": None,            # None -> default DejaVu bold
    "fontsize": 58,
    "primary": "#ff8a3d",    # active / highlight colour
    "upcoming": "#ffffff",   # not-yet-spoken
    "outline_color": "#000000",
    "outline_width": 6,
    "uppercase": False,
    "word_box": None,        # per-word chip bg "rgba" hex (#RRGGBBAA) or None
    "active_box": None,      # box behind the active word
    "line_band": None,       # band behind the whole line
    "glow": None,            # glow colour
    "gradient": None,        # [from, to] for the active word fill
    "position": "bottom",    # bottom | center | top
    "max_words": 4,
}


def _p(**over) -> dict:
    s = dict(_BASE)
    s.update(over)
    return s


CAPTION_PRESETS = {
    "hormozi": _p(uppercase=True, fontsize=64, outline_width=9,
                  primary="#1c1c1c", active_box="#ffd400", upcoming="#ffffff", max_words=4),
    "beast": _p(fontsize=70, outline_width=10, glow="#000000", primary="#ffe14d",
                upcoming="#ffffff", max_words=3),
    "karaoke": _p(),
    "boxed": _p(word_box="#11131aCC", active_box="#ff8a3d", upcoming="#ffffff",
                outline_width=2, fontsize=54),
    "tiktok": _p(line_band="#000000AA", outline_width=2, primary="#ffffff",
                 upcoming="#ffffff", fontsize=52, max_words=6),
    "neon": _p(primary="#39ff14", upcoming="#d8ffd0", glow="#39ff14", outline_color="#063b00",
               outline_width=4),
    "bold_pop": _p(fontsize=66, outline_width=8, primary="#ff8a3d", upcoming="#ffffff"),
    "clean": _p(outline_width=3, primary="#ffd400", upcoming="#ffffff", fontsize=52),
    "minimal": _p(fontsize=42, outline_width=2, primary="#ffffff", upcoming="#cfd5e0",
                  position="bottom", max_words=6),
    "uppercase": _p(uppercase=True, fontsize=58, outline_width=6, primary="#ff8a3d"),
    "gradient": _p(fontsize=64, outline_width=6, gradient=["#ffb259", "#ff5a3c"], upcoming="#ffffff"),
    "subtitle": _p(line_band="#0b0c0fEE", outline_width=0, primary="#ffffff",
                   upcoming="#ffffff", fontsize=46, max_words=8, position="bottom"),
}

DEFAULT_PRESET = "karaoke"

# Reveal type = HOW words appear over time (independent of the colour preset).
# Mirrors Descript (Karaoke / Clean / word-by-word) and Veed's dynamic captions.
#   highlight — whole line shown, active word emphasised (classic karaoke).
#   build     — words appear one-by-one as spoken and stay (cumulative).
#   word      — one word on screen at a time (big, TikTok-style).
#   line      — whole line shown at once, steady, no per-word emphasis (clean).
REVEALS = {"highlight", "build", "word", "line"}
DEFAULT_REVEAL = "highlight"

# Per-word MOTION applied to the active word (mirrors Veed's named animations:
# Impact Pop, Scale In, Float In, Drop In, Slide In, Stomp, Bounce, Pulse).
# Composes with any reveal type + colour style, so Clippy reproduces every
# Veed/Descript caption preset by combining these three axes.
ANIMATIONS = {"none", "pop", "bounce", "scale_in", "float_in",
              "drop_in", "slide_in", "stomp", "pulse"}
DEFAULT_ANIMATION = "none"


def resolve_caption_style(caption: dict | None) -> dict:
    """Preset defaults overlaid with user fontsize/color/position/reveal/motion."""
    caption = caption or {}
    preset = caption.get("preset", DEFAULT_PRESET)
    style = dict(CAPTION_PRESETS.get(preset, CAPTION_PRESETS[DEFAULT_PRESET]))
    if caption.get("fontsize"):
        style["fontsize"] = int(caption["fontsize"])
    if caption.get("color"):
        style["primary"] = caption["color"]
    if caption.get("position"):
        style["position"] = caption["position"]
    reveal = caption.get("reveal", DEFAULT_REVEAL)
    style["reveal"] = reveal if reveal in REVEALS else DEFAULT_REVEAL
    # Motion: explicit `animation` wins; else fall back to the legacy `animate`
    # boolean (which meant "pop"). Keeps old saved settings working.
    anim = caption.get("animation")
    if anim is None:
        anim = "pop" if caption.get("animate") else DEFAULT_ANIMATION
    style["animation"] = anim if anim in ANIMATIONS else DEFAULT_ANIMATION
    style["animate"] = style["animation"] != "none"
    return style
