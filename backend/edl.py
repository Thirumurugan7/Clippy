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


def virtual_to_source(segments: list[dict], vt: float) -> float:
    """Map a virtual (edited-timeline) time to the original source time."""
    acc = 0.0
    for s in segments:
        a = float(s["sourceStart"])
        b = float(s["sourceEnd"])
        d = b - a
        if vt < acc + d:
            return a + (vt - acc)
        acc += d
    return float(segments[-1]["sourceEnd"]) if segments else 0.0


def cx_at(centers: list[dict], s: float) -> float:
    """Linear-interpolate the normalized face centre at source time s (0.5 = middle)."""
    prev = None
    for c in centers:
        if c.get("cx") is None:
            continue
        if c["t"] <= s:
            prev = c
        else:
            if prev is None:
                return c["cx"]
            span = c["t"] - prev["t"] or 1.0
            return prev["cx"] + ((s - prev["t"]) / span) * (c["cx"] - prev["cx"])
    return prev["cx"] if prev else 0.5


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
                pw = {
                    "word": w["word"],
                    "virtual_start": acc + (ostart - a),
                    "virtual_end": acc + (oend - a),
                }
                if w.get("speaker") is not None:  # carry diarized speaker through
                    pw["speaker"] = w["speaker"]
                out.append(pw)
        acc += seg_len
    return out


def attach_speakers(words: list[dict], segments: list[dict]) -> list[dict]:
    """Tag each transcript word with its diarized speaker (from segment word
    ranges), so per-speaker caption colour survives projection. No-op if the
    transcript hasn't been diarized."""
    for seg in segments:
        spk = seg.get("speaker")
        if spk is None:
            continue
        for i in range(int(seg.get("word_start", 0)), int(seg.get("word_end", 0))):
            if 0 <= i < len(words):
                words[i]["speaker"] = spk
    return words
