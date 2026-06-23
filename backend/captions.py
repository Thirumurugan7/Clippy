"""Render burned-in karaoke captions per video frame with Pillow.

This machine's ffmpeg has no libass (no `subtitles`/`ass` filter), and the
vertical export already processes every frame in Python, so we draw captions
directly: words are grouped into short lines; the word being spoken is drawn in
the highlight colour, the rest in white, with an outline for legibility.

Font defaults to matplotlib's bundled DejaVu Sans Bold so it works the same on a
dev laptop and a deployed server (no reliance on system fonts).
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


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


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
    """Precomputes caption lines and draws the active one onto a frame at time t."""

    def __init__(
        self, words, *, width=1080, height=1920, font=None, fontsize=58,
        primary="#ff8a3d", upcoming="#ffffff", margin_v=300, max_words=4, max_gap=0.7,
    ):
        self.width = width
        self.height = height
        self.margin_v = margin_v
        self.primary = _hex_rgb(primary)
        self.upcoming = _hex_rgb(upcoming)
        self.lines = _group_lines(words, max_words, max_gap)
        self.font = ImageFont.truetype(font or _default_font_path(), fontsize)
        self.space = self.font.getbbox(" ")[2] or fontsize // 3

    def _active_line(self, t):
        for ln in self.lines:
            if ln["start"] <= t <= ln["end"]:
                return ln
        return None

    def draw(self, frame_bgr, t):
        line = self._active_line(t)
        if line is None:
            return frame_bgr
        img = Image.fromarray(frame_bgr[:, :, ::-1])  # BGR -> RGB
        d = ImageDraw.Draw(img)

        # Lay words out on rows that fit the width (with side margins).
        max_w = self.width - 120
        rows, row, row_w = [], [], 0
        for w in line["words"]:
            tw = self.font.getbbox(w["word"].strip())[2]
            add = tw + (self.space if row else 0)
            if row and row_w + add > max_w:
                rows.append(row)
                row, row_w = [], 0
                add = tw
            row.append(w)
            row_w += add
        if row:
            rows.append(row)

        line_h = (self.font.getbbox("Ay")[3] - self.font.getbbox("Ay")[1]) + 16
        total_h = line_h * len(rows)
        y = self.height - self.margin_v - total_h

        for r in rows:
            widths = [self.font.getbbox(w["word"].strip())[2] for w in r]
            row_w = sum(widths) + self.space * (len(r) - 1)
            x = (self.width - row_w) // 2
            for w, tw in zip(r, widths):
                active = w["virtual_start"] <= t <= w["virtual_end"]
                color = self.primary if active else self.upcoming
                txt = w["word"].strip()
                # outline for legibility
                for ox, oy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2), (-2, 2), (2, -2)):
                    d.text((x + ox, y + oy), txt, font=self.font, fill=(0, 0, 0))
                d.text((x, y), txt, font=self.font, fill=color)
                x += tw + self.space
            y += line_h

        return np.asarray(img)[:, :, ::-1].copy()  # RGB -> BGR
