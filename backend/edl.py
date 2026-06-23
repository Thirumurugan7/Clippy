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


def project_words(segments: list[dict], words: list[dict], min_keep_ratio: float = 0.5) -> list[dict]:
    """Map transcript words onto the EDITED (virtual) timeline, in EDL order.

    Mirror of the frontend projectWords: walk segments in order, emit words whose
    source timestamps fall inside each segment (>=min_keep_ratio retained),
    annotated with virtual start/end. Used to time captions on the edited clip.
    """
    out: list[dict] = []
    acc = 0.0
    for seg in segments:
        a = float(seg["sourceStart"])
        b = float(seg["sourceEnd"])
        seg_len = b - a
        for w in words:
            ostart = max(w["start"], a)
            oend = min(w["end"], b)
            overlap = oend - ostart
            wlen = max(w["end"] - w["start"], 1e-6)
            if overlap > 0 and overlap / wlen >= min_keep_ratio:
                out.append({
                    "word": w["word"],
                    "virtual_start": acc + (ostart - a),
                    "virtual_end": acc + (oend - a),
                })
        acc += seg_len
    return out
