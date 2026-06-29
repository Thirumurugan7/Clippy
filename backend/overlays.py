"""Static text (and emoji) overlays for the export.

Overlays don't change per frame, so we render them ONCE to an RGBA layer and
return a (BGR, alpha) pair the export loop blends onto every frame — cheap.
Mirrored on the canvas in the live preview so what you place is what bakes.

Because Pillow here has no RAQM font-fallback, a line is split into emoji vs
text runs: text runs render with DejaVu, emoji runs render with the macOS colour
emoji font (at a fixed strike, then scaled). Runs are laid out left-to-right and
the line is centred. Each overlay: {text, position: top|center|bottom,
size: fraction-of-height, color: hex}.
"""
from __future__ import annotations

import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from backend.captions import _default_font_path, _rgba

# Broad emoji match (symbols, pictographs, flags, dingbats, variation selectors).
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF"
    "\U00002190-\U000021FF\U0000FE00-\U0000FE0F\U0001F1E6-\U0001F1FF\U0000200D]+"
)
_EMOJI_FONT = "/System/Library/Fonts/Apple Color Emoji.ttc"
_EMOJI_STRIKE = 160


def _runs(text: str):
    out, last = [], 0
    for m in _EMOJI_RE.finditer(text):
        if m.start() > last:
            out.append(("text", text[last:m.start()]))
        out.append(("emoji", m.group()))
        last = m.end()
    if last < len(text):
        out.append(("text", text[last:]))
    return out


def _text_tile(text, font, color, sw):
    bb = font.getbbox(text, stroke_width=sw)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    tile = Image.new("RGBA", (max(1, w + 2 * sw), max(1, h + 2 * sw)), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((sw - bb[0], sw - bb[1]), text, font=font,
                              fill=color, stroke_width=sw, stroke_fill=(0, 0, 0, 255))
    return tile


def _emoji_tile(run, size):
    try:
        f = ImageFont.truetype(_EMOJI_FONT, _EMOJI_STRIKE)
    except Exception:
        return None
    big = Image.new("RGBA", (_EMOJI_STRIKE * (len(run) + 2), _EMOJI_STRIKE * 2), (0, 0, 0, 0))
    try:
        ImageDraw.Draw(big).text((0, 0), run, font=f, embedded_color=True)
    except Exception:
        return None
    bbox = big.getbbox()
    if not bbox:
        return None
    crop = big.crop(bbox)
    scale = size / crop.height
    return crop.resize((max(1, int(crop.width * scale)), max(1, int(size))), Image.LANCZOS)


def build_overlay_layer(overlays, tw: int, th: int):
    """Return (bgr_ndarray, alpha_ndarray[h,w,1]) or (None, None) if nothing to draw."""
    items = [o for o in (overlays or []) if str(o.get("text", "")).strip()]
    if not items:
        return None, None

    img = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    font_path = _default_font_path()
    margin = int(th * 0.05)

    for ov in items:
        text = str(ov["text"]).strip()
        size = max(10, int(float(ov.get("size", 0.06)) * th))
        sw = max(2, size // 16)
        color = _rgba(ov.get("color", "#ffffff"))
        font = ImageFont.truetype(font_path, size)

        tiles = []
        for kind, s in _runs(text):
            if not s:
                continue
            tile = _emoji_tile(s, size) if kind == "emoji" else _text_tile(s, font, color, sw)
            if tile is not None:
                tiles.append(tile)
        if not tiles:
            continue

        line_w = sum(t.width for t in tiles)
        line_h = max(t.height for t in tiles)
        x = (tw - line_w) // 2
        pos = ov.get("position", "top")
        if pos == "top":
            y = margin
        elif pos == "bottom":
            y = th - line_h - margin
        else:
            y = (th - line_h) // 2
        cx = x
        for t in tiles:
            img.alpha_composite(t, (int(cx), int(y + (line_h - t.height) // 2)))
            cx += t.width

    bgr = np.asarray(img.convert("RGB"))[:, :, ::-1].copy()
    alpha = (np.asarray(img)[:, :, 3:4].astype(np.float32)) / 255.0
    return bgr, alpha
