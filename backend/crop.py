"""Aspect-aware crop math (mirrored in frontend/src/crop.js).

Given a source frame and a target aspect, returns the largest crop window of that
aspect, positioned horizontally by a normalized centre (face-track or manual).
Horizontal pan only for v1; vertical is centered.
"""
from __future__ import annotations

from backend.presets import ASPECTS


def target_dims(aspect: str) -> tuple[int, int]:
    a = ASPECTS.get(aspect, ASPECTS["9:16"])
    return a["w"], a["h"]


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def compute_crop(W: int, H: int, aspect: str, cx_norm: float, cy_norm: float = 0.5) -> tuple[int, int, int, int]:
    ratio = ASPECTS.get(aspect, ASPECTS["9:16"])["ratio"]  # w/h
    if W / H >= ratio:
        ch = H
        cw = round(H * ratio)
    else:
        cw = W
        ch = round(W / ratio)
    cw = min(cw, W)
    ch = min(ch, H)
    sx = int(_clamp(round(cx_norm * W - cw / 2), 0, W - cw))
    sy = int(_clamp(round(cy_norm * H - ch / 2), 0, H - ch))
    return sx, sy, cw, ch
