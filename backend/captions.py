"""Render burned-in word-level captions per frame with Pillow, supporting the
full influencer-preset style schema (see backend/presets.py).

Mirrored on the preview side by frontend/src/captionLayout.js so a preset looks
the same in the live preview and the exported short.
"""
from __future__ import annotations

import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import matplotlib


def _default_font_path() -> str:
    return os.path.join(
        os.path.dirname(matplotlib.__file__), "mpl-data/fonts/ttf/DejaVuSans-Bold.ttf"
    )


def _rgba(h):
    """#RRGGBB or #RRGGBBAA -> (r,g,b,a). None -> None."""
    if not h:
        return None
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    a = int(h[6:8], 16) if len(h) >= 8 else 255
    return (r, g, b, a)


import math

# Per-word motion. Each returns (scale, dx, dy, alpha) for the active word at
# elapsed time `e` (seconds since it became active), over a `dur`-second entrance.
# MUST match frontend captionLayout.wordAnim so preview == export.
ANIM_DUR = 0.25


def word_anim(name, e, dur, fs):
    if not name or name == "none":
        return (1.0, 0.0, 0.0, 1.0)
    if name == "pulse":  # continuous gentle breathing while active
        return (1.0 + 0.05 * math.sin(2 * math.pi * e / 0.7), 0.0, 0.0, 1.0)
    p = e / dur if dur > 0 else 1.0
    if p < 0 or p > 1:
        return (1.0, 0.0, 0.0, 1.0)
    q = 1.0 - p
    if name == "pop":
        return (1.0 + 0.30 * q, 0.0, 0.0, 1.0)
    if name == "bounce":
        return (1.0 + 0.35 * math.sin(math.pi * p), 0.0, 0.0, 1.0)
    if name == "scale_in":
        return (0.4 + 0.6 * p, 0.0, 0.0, p)
    if name == "float_in":
        return (1.0, 0.0, 0.55 * fs * q, p)      # rises up into place
    if name == "drop_in":
        return (1.0, 0.0, -0.55 * fs * q, p)     # falls down into place
    if name == "slide_in":
        return (1.0, 0.6 * fs * q, 0.0, p)       # slides in from the right
    if name == "stomp":
        return (1.0 + 0.8 * q * q, 0.0, 0.0, min(1.0, 0.5 + 0.5 * p))
    return (1.0, 0.0, 0.0, 1.0)


def _group_lines(words, max_words, max_gap):
    lines, cur = [], []
    for w in words:
        if cur:
            gap = w["virtual_start"] - cur[-1]["virtual_end"]
            if len(cur) >= max_words or gap > max_gap:
                lines.append(cur)
                cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    return [{"start": ln[0]["virtual_start"], "end": ln[-1]["virtual_end"], "words": ln} for ln in lines]


class CaptionRenderer:
    def __init__(self, words, *, width=1080, height=1920, style=None, lines=None):
        from backend.presets import resolve_caption_style
        self.W = width
        self.H = height
        self.s = style or resolve_caption_style(None)
        # Pre-grouped `lines` (translated line-level captions) bypass word grouping
        # so a translated cue stays one coherent line; otherwise group words.
        self.lines = lines if lines is not None else _group_lines(words, self.s["max_words"], 0.7)
        self.font = ImageFont.truetype(self.s["font"] or _default_font_path(), int(self.s["fontsize"]))
        self.space = self.font.getbbox(" ")[2] or self.s["fontsize"] // 3
        self.pad = max(8, int(self.s["fontsize"] * 0.22))

    def _txt(self, w):
        t = w["word"].strip()
        return t.upper() if self.s["uppercase"] else t

    def _active_line(self, t):
        for ln in self.lines:
            if ln["start"] <= t <= ln["end"]:
                return ln
        return None

    def _visible(self, w, t):
        """Whether a word is on screen at t, given the reveal type."""
        reveal = self.s.get("reveal", "highlight")
        if reveal == "word":
            return w["virtual_start"] <= t <= w["virtual_end"]
        if reveal == "build":
            return t >= w["virtual_start"]
        return True  # highlight, line

    def _state(self, w, t):
        """active | upcoming | past | line — drives colour and emphasis."""
        reveal = self.s.get("reveal", "highlight")
        if reveal == "line":
            return "line"
        if w["virtual_start"] <= t <= w["virtual_end"]:
            return "active"
        if reveal == "build":
            return "past"      # already-spoken words stay bright
        if reveal == "word":
            return "active"    # only the active word is ever shown
        return "upcoming"      # highlight: not-yet/again-dim

    def _wrap(self, words):
        max_w = self.W - 120
        rows, row, row_w = [], [], 0
        for w in words:
            tw = self.font.getbbox(self._txt(w))[2]
            add = tw + (self.space if row else 0)
            if row and row_w + add > max_w:
                rows.append(row)
                row, row_w = [], 0
                add = tw
            row.append(w)
            row_w += add
        if row:
            rows.append(row)
        return rows

    def draw(self, frame_bgr, t):
        line = self._active_line(t)
        if line is None:
            return frame_bgr
        shown = [w for w in line["words"] if self._visible(w, t)]
        if not shown:
            return frame_bgr
        s = self.s
        img = Image.fromarray(frame_bgr[:, :, ::-1]).convert("RGBA")
        rows = self._wrap(shown)
        line_h = (self.font.getbbox("Ay")[3] - self.font.getbbox("Ay")[1]) + 18
        total_h = line_h * len(rows)
        if s["position"] == "center":
            y0 = (self.H - total_h) // 2
        elif s["position"] == "top":
            y0 = int(self.H * 0.12)
        else:
            y0 = self.H - int(self.H * 0.16) - total_h

        # --- boxes / bands on an alpha overlay ---
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        y = y0
        for r in rows:
            widths = [self.font.getbbox(self._txt(w))[2] for w in r]
            row_w = sum(widths) + self.space * (len(r) - 1)
            x = (self.W - row_w) // 2
            if _rgba(s["line_band"]):
                od.rounded_rectangle([x - self.pad, y - self.pad // 2, x + row_w + self.pad, y + line_h - 4],
                                     radius=14, fill=_rgba(s["line_band"]))
            cx = x
            for w, tw in zip(r, widths):
                st = self._state(w, t)
                box = _rgba(s["active_box"]) if st == "active" and s["active_box"] else _rgba(s["word_box"])
                if box:
                    od.rounded_rectangle([cx - self.pad // 2, y - self.pad // 3, cx + tw + self.pad // 2, y + line_h - 8],
                                         radius=10, fill=box)
                cx += tw + self.space
            y += line_h
        img = Image.alpha_composite(img, overlay)

        # --- text ---
        d = ImageDraw.Draw(img)
        y = y0
        for r in rows:
            widths = [self.font.getbbox(self._txt(w))[2] for w in r]
            row_w = sum(widths) + self.space * (len(r) - 1)
            x = (self.W - row_w) // 2
            for w, tw in zip(r, widths):
                st = self._state(w, t)
                txt = self._txt(w)
                tr = None
                if st == "active":
                    anim = self.s.get("animation", "none")
                    dur = min(ANIM_DUR, (w["virtual_end"] - w["virtual_start"]) * 0.8) or ANIM_DUR
                    scale, dx, dy, alpha = word_anim(anim, t - w["virtual_start"], dur, self.s["fontsize"])
                    if abs(scale - 1) > 1e-3 or dx or dy or alpha < 0.999:
                        tr = (scale, dx, dy, alpha)
                if tr:
                    self._draw_word_tile(img, x, y, tw, txt, *tr)
                else:
                    self._draw_word(img, d, x, y, txt, st)
                x += tw + self.space
            y += line_h
        return np.asarray(img.convert("RGB"))[:, :, ::-1].copy()

    def _draw_word_tile(self, img, x, y, tw, txt, scale, dx, dy, alpha):
        """Render the active word to a tile and composite it with a motion
        transform (scale + offset + alpha) centred on its slot. Outline + primary
        fill — parity with the preview's wordAnim path."""
        s = self.s
        ow = int(s["outline_width"])
        oc = _rgba(s["outline_color"])[:3]
        fill = _rgba(s["primary"])[:3]
        bb = self.font.getbbox(txt)
        gw, gh = bb[2] - bb[0], bb[3] - bb[1]
        pad = ow + 6
        tile = Image.new("RGBA", (gw + pad * 2, gh + pad * 2), (0, 0, 0, 0))
        stroke = {"stroke_width": ow, "stroke_fill": oc} if ow > 0 else {}
        ImageDraw.Draw(tile).text((pad - bb[0], pad - bb[1]), txt, font=self.font, fill=fill, **stroke)
        if abs(scale - 1) > 1e-3:
            nw, nh = max(1, int(tile.width * scale)), max(1, int(tile.height * scale))
            tile = tile.resize((nw, nh), Image.LANCZOS)
        if alpha < 0.999:
            tile.putalpha(tile.getchannel("A").point(lambda v: int(v * max(0.0, alpha))))
        cx = x + tw / 2 + dx
        cy = y + (bb[1] + bb[3]) / 2 + dy  # vertical centre of the glyph at draw y
        img.alpha_composite(tile, (int(cx - tile.width / 2), int(cy - tile.height / 2)))

    def _draw_word(self, img, d, x, y, txt, state):
        s = self.s
        active = state == "active"
        # "past" (build) and "line" words are confirmed text -> primary colour;
        # only "upcoming" (highlight mode) is dimmed. Emphasis (glow/gradient) is
        # reserved for the active word.
        bright = state in ("active", "past", "line")
        ow = int(s["outline_width"])
        oc = _rgba(s["outline_color"])[:3]
        stroke = {"stroke_width": ow, "stroke_fill": oc} if ow > 0 else {}
        # soft glow halo behind the active word
        glow = _rgba(s["glow"])
        if glow and active:
            for ox, oy in ((-4, 0), (4, 0), (0, -4), (0, 4), (-3, -3), (3, 3), (-3, 3), (3, -3)):
                d.text((x + ox, y + oy), txt, font=self.font, fill=glow[:3] + (140,))
        if active and s["gradient"]:
            # solid outline base, then a vertical-gradient fill over the glyph
            if ow > 0:
                d.text((x, y), txt, font=self.font, fill=oc, **stroke)
            self._gradient_word(img, x, y, txt, s["gradient"])
        else:
            fill = (_rgba(s["primary"]) if bright else _rgba(s["upcoming"]))[:3]
            d.text((x, y), txt, font=self.font, fill=fill, **stroke)

    def _gradient_word(self, img, x, y, txt, grad):
        bb = self.font.getbbox(txt)
        w, h = bb[2] + 4, bb[3] + 8
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).text((0, 0), txt, font=self.font, fill=255)
        c0 = _rgba(grad[0])[:3]
        c1 = _rgba(grad[1])[:3]
        grad_img = Image.new("RGB", (w, h))
        gp = grad_img.load()
        for yy in range(h):
            f = yy / max(1, h - 1)
            col = tuple(int(c0[i] + (c1[i] - c0[i]) * f) for i in range(3))
            for xx in range(w):
                gp[xx, yy] = col
        img.paste(grad_img, (int(x), int(y)), mask)
