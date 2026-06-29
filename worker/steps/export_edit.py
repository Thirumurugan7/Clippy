"""Export an edited video by concatenating the saved EDL's segments.

Real cuts on the real timeline. The EDL is an ordered list of source-time
segments; ffmpeg `trim`/`atrim` + `concat` render them in one pass, in list
order (so reorder/trim/split all flow through here). Re-encoding (not stream
copy) means cuts land on the exact requested time, not the nearest keyframe.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from backend import db, config
from backend.edl import ordered_intervals


def _bin(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"{name} not found on PATH (install ffmpeg).")
    return path


# Local audio cleanup chain (no external model needed, unlike RNNoise):
# high-pass removes rumble, afftdn is an FFT denoiser, loudnorm brings the clip
# to the -16 LUFS social-media target. Applied only when the user opts in.
AUDIO_ENHANCE_FILTER = "highpass=f=70,afftdn=nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11"


def _probe_duration(path: str) -> float:
    out = subprocess.run(
        [_bin("ffprobe"), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def _build_filtergraph(kept: list[tuple[float, float]], has_audio: bool, enhance_audio: bool = False) -> str:
    parts = []
    for n, (s, e) in enumerate(kept):
        parts.append(
            f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{n}];"
        )
        if has_audio:
            parts.append(
                f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{n}];"
            )
    if has_audio:
        streams = "".join(f"[v{n}][a{n}]" for n in range(len(kept)))
        # The concat'd audio comes from the complex graph, so the cleanup chain
        # must live inside it too (ffmpeg forbids mixing -af with a graph output).
        if enhance_audio:
            parts.append(f"{streams}concat=n={len(kept)}:v=1:a=1[outv][acat];")
            parts.append(f"[acat]{AUDIO_ENHANCE_FILTER}[outa]")
        else:
            parts.append(f"{streams}concat=n={len(kept)}:v=1:a=1[outv][outa]")
    else:
        streams = "".join(f"[v{n}]" for n in range(len(kept)))
        parts.append(f"{streams}concat=n={len(kept)}:v=1:a=0[outv]")
    return "\n".join(parts)


def run_export_edit(job) -> dict:
    """Render the saved EDL (ordered segments) to a real edited MP4.

    The EDL's segments are concatenated in list order, so trim/split/ripple-
    delete and reorder all flow through the same path.
    """
    video_id = job["video_id"]

    video = db.get_video(video_id)
    if video is None:
        raise RuntimeError(f"video {video_id} not found")

    total_duration = video["duration_seconds"] or _probe_duration(video["stored_path"])
    has_audio = bool(video["audio_codec"])

    edit = db.get_edit(video_id)
    if edit is not None:
        segments = json.loads(edit["edl_json"])
        kept = ordered_intervals(segments)
    else:
        kept = [(0.0, total_duration)]
    if not kept:
        raise RuntimeError("EDL is empty; nothing to export.")

    out_dir = config.EXPORTS_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{job['id']}.mp4"

    srow = db.get_settings(video_id)
    enhance_audio = bool(json.loads(srow["json"]).get("enhance_audio")) if srow else False
    render_segments(video["stored_path"], kept, has_audio, str(out_path), enhance_audio=enhance_audio)

    out_duration = _probe_duration(str(out_path))
    return {
        "output_path": str(out_path),
        "num_segments": len(kept),
        "original_duration": round(total_duration, 3),
        "output_duration": round(out_duration, 3),
        "enhance_audio": enhance_audio,
    }


def render_segments(src_path: str, kept: list[tuple[float, float]], has_audio: bool,
                    out_path: str, enhance_audio: bool = False) -> None:
    """Cut + concat the given source-time intervals (in order) into out_path.

    Shared by the normal edit export and the vertical export (which reframes and
    captions the result). Re-encodes for frame-accurate cuts. When enhance_audio
    is set and the source has audio, the cleanup chain is applied to the output.
    """
    graph = _build_filtergraph(kept, has_audio, enhance_audio)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(graph)
        graph_path = f.name

    cmd = [_bin("ffmpeg"), "-y", "-i", src_path, "-filter_complex_script", graph_path, "-map", "[outv]"]
    if has_audio:
        cmd += ["-map", "[outa]", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-movflags", "+faststart", out_path]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    Path(graph_path).unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg export failed (exit {proc.returncode}): {proc.stderr[-1500:]}")
