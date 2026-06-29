"""Edit transcript words behind a subtitle cue.

A subtitle editor lets you fix a misheard line. We replace every word fully
inside the cue's [start, end] with the new tokens, distributing the cue's time
span evenly across them (how subtitle editors retime edited text). Operates on
the source transcript, so the fix flows to burned-in captions AND SRT/VTT.
"""
from __future__ import annotations


def replace_cue_words(words: list[dict], start: float, end: float, text: str,
                      eps: float = 0.05) -> list[dict]:
    kept = [w for w in words
            if not (w["start"] >= start - eps and w["end"] <= end + eps)]
    tokens = text.split()
    new: list[dict] = []
    if tokens:
        span = max(end - start, 0.05)
        step = span / len(tokens)
        for k, tok in enumerate(tokens):
            new.append({
                "word": tok,
                "start": round(start + k * step, 3),
                "end": round(start + (k + 1) * step, 3),
                "prob": 1.0,
            })
    merged = sorted(kept + new, key=lambda w: w["start"])
    for idx, w in enumerate(merged):
        w["i"] = idx
    return merged
