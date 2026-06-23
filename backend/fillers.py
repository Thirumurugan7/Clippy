"""Detect filler / disfluency words in a real transcript.

Pure text logic over the stored word list — no model, no audio. Returns the
indices of words considered fillers so the UI can mark them for the user to
review (the user can always toggle any of them off before exporting; nothing
is deleted automatically).

Handles single-word fillers plus a couple of common bigrams ("you know",
"i mean"). The set is overridable via CLIPFORGE_FILLER_WORDS (comma-separated).
"""
from __future__ import annotations

import os
import re

# Pure disfluencies + the spec's named examples (um, uh, like, you know).
_DEFAULT_SINGLE = [
    "um", "umm", "ummm", "uh", "uhh", "uhm", "uhhh",
    "er", "err", "erm", "ah", "ahh", "eh",
    "hmm", "hmmm", "mhm", "mm", "mmm",
    "like",
]
_DEFAULT_BIGRAMS = [("you", "know"), ("i", "mean")]


def _single_fillers() -> set[str]:
    override = os.environ.get("CLIPFORGE_FILLER_WORDS")
    if override:
        return {w.strip().lower() for w in override.split(",") if w.strip()}
    return set(_DEFAULT_SINGLE)


def _normalize(raw: str) -> str:
    """Lowercase and strip surrounding punctuation/space, keep inner apostrophes.

    Whisper words look like ' Um,' or ' like' — we compare on the bare token.
    """
    return re.sub(r"^[^\w']+|[^\w']+$", "", raw.strip().lower())


def detect_fillers(words: list[dict]) -> list[int]:
    """Return sorted indices of words that are fillers.

    `words` is the stored transcript word list: [{i, word, start, end, prob}, ...].
    """
    singles = _single_fillers()
    norm = [_normalize(w["word"]) for w in words]
    flagged: set[int] = set()

    for i, tok in enumerate(norm):
        if tok and tok in singles:
            flagged.add(i)

    for a, b in _DEFAULT_BIGRAMS:
        for i in range(len(norm) - 1):
            if norm[i] == a and norm[i + 1] == b:
                flagged.add(i)
                flagged.add(i + 1)

    return sorted(flagged)
