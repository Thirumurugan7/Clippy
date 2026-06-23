"""Server-side EDL validation and rendering helpers.

An EDL is an ordered list of segments [{id, sourceStart, sourceEnd}] over the
original video's timeline. ordered_intervals() preserves list order so reordered
edits export in the arranged order.
"""
from __future__ import annotations

MIN_SEG = 0.02


def validate_edl(segments: list[dict], duration: float) -> list[dict]:
    if not isinstance(segments, list):
        raise ValueError("segments must be a list")
    for s in segments:
        try:
            a = float(s["sourceStart"])
            b = float(s["sourceEnd"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"segment missing numeric bounds: {s!r}")
        if a < -1e-6 or b > duration + 1e-3:
            raise ValueError(f"segment {a}-{b} out of bounds [0,{duration}]")
        if b - a < MIN_SEG:
            raise ValueError(f"segment {a}-{b} shorter than {MIN_SEG}s")
    return segments


def ordered_intervals(segments: list[dict]) -> list[tuple[float, float]]:
    return [(float(s["sourceStart"]), float(s["sourceEnd"])) for s in segments]
