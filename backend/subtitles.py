"""Build downloadable subtitle files (SRT / WebVTT) from projected caption words.

Input is the word list already mapped onto the edited (virtual) timeline by
`edl.project_words`, so the subtitles line up with the exported clip — not the
raw source. Words are grouped into short caption lines (same idea as the burned-in
renderer) and emitted as standard cues.
"""
from __future__ import annotations


def _fmt_ts(t: float, sep: str) -> str:
    """Seconds -> HH:MM:SS,mmm (SRT, sep=',') or HH:MM:SS.mmm (VTT, sep='.')."""
    if t < 0:
        t = 0.0
    total_ms = int(round(t * 1000))
    h, rem = divmod(total_ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def group_cues(words: list[dict], max_words: int = 7, max_gap: float = 0.7) -> list[dict]:
    """Group word dicts ({word, virtual_start, virtual_end}) into caption lines."""
    lines: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        if cur:
            gap = w["virtual_start"] - cur[-1]["virtual_end"]
            if len(cur) >= max_words or gap > max_gap:
                lines.append(cur)
                cur = []
        cur.append(w)
    if cur:
        lines.append(cur)

    cues = []
    for ln in lines:
        start = ln[0]["virtual_start"]
        end = max(ln[-1]["virtual_end"], start + 0.4)  # never zero-length
        text = " ".join(x["word"].strip() for x in ln).strip()
        if text:
            cues.append({"start": start, "end": end, "text": text})
    return cues


def cues_to_srt(cues: list[dict]) -> str:
    blocks = [
        f"{i}\n{_fmt_ts(c['start'], ',')} --> {_fmt_ts(c['end'], ',')}\n{c['text']}\n"
        for i, c in enumerate(cues, 1)
    ]
    return "\n".join(blocks)


def cues_to_vtt(cues: list[dict]) -> str:
    blocks = ["WEBVTT\n"]
    blocks += [
        f"{_fmt_ts(c['start'], '.')} --> {_fmt_ts(c['end'], '.')}\n{c['text']}\n"
        for c in cues
    ]
    return "\n".join(blocks)


def build_srt(words: list[dict]) -> str:
    return cues_to_srt(group_cues(words))


def build_vtt(words: list[dict]) -> str:
    return cues_to_vtt(group_cues(words))
