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
    def __init__(self, words, *, width=1080, height=1920, style=None):
        from backend.presets import resolve_caption_style
        self.W = width
        self.H = height
        self.s = style or resolve_caption_style(None)
        self.lines = _group_lines(words, self.s["max_words"], 0.7)
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

    def _wrap(self, line):
        max_w = self.W - 120
        rows, row, row_w = [], [], 0
        for w in line["words"]:
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
        s = self.s
        img = Image.fromarray(frame_bgr[:, :, ::-1]).convert("RGBA")
        rows = self._wrap(line)
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
                active = w["virtual_start"] <= t <= w["virtual_end"]
                box = _rgba(s["active_box"]) if active and s["active_box"] else _rgba(s["word_box"])
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
                active = w["virtual_start"] <= t <= w["virtual_end"]
                txt = self._txt(w)
                self._draw_word(img, d, x, y, txt, active)
                x += tw + self.space
            y += line_h
        return np.asarray(img.convert("RGB"))[:, :, ::-1].copy()

    def _draw_word(self, img, d, x, y, txt, active):
        s = self.s
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
            fill = (_rgba(s["primary"]) if active else _rgba(s["upcoming"]))[:3]
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
