"""Detect silent / dead-air ranges in a video's audio (local, no model).

Uses ffmpeg's `silencedetect` filter — the same offline toolchain the rest of
Clippy already relies on — to find stretches quieter than a noise floor for
longer than a minimum duration. The parser is split out from the ffmpeg call so
it's unit-testable without spawning ffmpeg.

Returns SOURCE-time ranges the UI can cut from the EDL (same flow as filler-word
removal: nothing is deleted automatically; the user applies it). Each detected
silence is padded *inward* so we trim dead air without clipping the speech
onset/offset around it, and slivers shorter than the minimum are dropped.
"""
from __future__ import annotations

import re
import shutil
import subprocess

# ffmpeg prints e.g.:  [silencedetect @ 0x..] silence_start: 3.214
#                      [silencedetect @ 0x..] silence_end: 5.007 | silence_duration: 1.793
_START_RE = re.compile(r"silence_start:\s*(-?[\d.]+)")
_END_RE = re.compile(r"silence_end:\s*(-?[\d.]+)")

DEFAULT_NOISE_DB = -30.0   # anything quieter than this counts as silence
DEFAULT_MIN_SILENCE = 0.6  # seconds — ignore natural short pauses between words
DEFAULT_PAD = 0.1          # keep this much of the silence on each side (natural cut)


def _parse_silencedetect(stderr: str, duration: float | None = None) -> list[dict]:
    """Turn ffmpeg's silencedetect log into [{start, end}] ranges (raw, unpadded).

    A `silence_start` with no matching `silence_end` means silence ran to the end
    of the file; close it at `duration` if we know it, else drop it.
    """
    ranges: list[dict] = []
    pending: float | None = None
    for line in stderr.splitlines():
        ms = _START_RE.search(line)
        if ms:
            pending = float(ms.group(1))
            continue
        me = _END_RE.search(line)
        if me and pending is not None:
            ranges.append({"start": max(0.0, pending), "end": float(me.group(1))})
            pending = None
    if pending is not None and duration is not None and duration > pending:
        ranges.append({"start": max(0.0, pending), "end": float(duration)})
    return ranges


def _pad_and_filter(ranges: list[dict], pad: float, min_silence: float) -> list[dict]:
    """Shrink each range inward by `pad` on both sides and drop anything left
    shorter than `min_silence` (so we only cut real dead air, with a soft edge)."""
    out = []
    for r in ranges:
        start = r["start"] + pad
        end = r["end"] - pad
        if end - start >= min_silence - 2 * pad and end > start:
            out.append({"start": round(start, 3), "end": round(end, 3)})
    return out


def detect_silences(
    video_path: str,
    *,
    noise_db: float = DEFAULT_NOISE_DB,
    min_silence: float = DEFAULT_MIN_SILENCE,
    pad: float = DEFAULT_PAD,
    duration: float | None = None,
    ffmpeg: str = "ffmpeg",
) -> list[dict]:
    """Detect padded dead-air ranges (source time). Empty list on any failure or
    when the file has no audio — never raises into an export/edit flow."""
    exe = shutil.which(ffmpeg) or ffmpeg
    cmd = [exe, "-hide_banner", "-nostats", "-i", str(video_path),
           "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}",
           "-f", "null", "-"]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except Exception:
        return []
    raw = _parse_silencedetect(proc.stderr.decode(errors="replace"), duration)
    return _pad_and_filter(raw, pad, min_silence)


def total_silence(ranges: list[dict]) -> float:
    return round(sum(r["end"] - r["start"] for r in ranges), 3)
