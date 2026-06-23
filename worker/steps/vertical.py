"""Vertical (9:16) export: reframe the edited clip with a face-tracked crop and
draw animated word-level captions, in a single frame-by-frame pass.

Stages:
  1. Render the EDL to a horizontal intermediate (shared render_segments).
  2. For each frame: detect the main face (mediapipe), smooth a horizontal pan,
     crop a 9:16 window, scale to 1080x1920, draw the karaoke caption for that
     moment (Pillow), and pipe to ffmpeg which muxes the original audio.

If faces are rarely found, the smoothed centre stays near the middle -> center
crop (the intended fallback: never produce a bad track). Simple and correct over
fancy: horizontal pan only, motion-smoothed.
"""
from __future__ import annotations

import json
import subprocess
import warnings

import cv2

from backend import db, config
from backend.edl import ordered_intervals, project_words, virtual_to_source, cx_at
from backend.crop import compute_crop, target_dims
from backend.captions import CaptionRenderer
from backend.presets import resolve_caption_style
from worker.steps.export_edit import render_segments, _bin, _probe_duration
from worker.steps.reframe import run_reframe

warnings.filterwarnings("ignore")

SMOOTH_ALPHA = 0.2  # EMA over the per-frame centre to keep the pan smooth

DEFAULT_SETTINGS = {
    "aspect": "9:16", "framing": "auto", "crop_cx": 0.5,
    "caption": {"preset": "karaoke", "fontsize": 58, "color": "#ff8a3d", "position": "bottom"},
}


def _reframe_and_caption(in_path, out_path, renderer, centers, segments, aspect, framing, crop_cx) -> dict:
    """Crop the edited intermediate to the chosen aspect, following the
    precomputed face trajectory (auto) or a fixed centre (manual), draw captions,
    and mux audio. Same trajectory as the live preview, so export == preview.
    """
    cap = cv2.VideoCapture(in_path)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    tw, th = target_dims(aspect)

    ff = subprocess.Popen(
        [_bin("ffmpeg"), "-y",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{tw}x{th}",
         "-r", f"{fps}", "-i", "-",
         "-i", in_path,
         "-map", "0:v:0", "-map", "1:a:0?", "-shortest",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_path],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    assert ff.stdin is not None

    cur_cx = crop_cx if framing == "manual" else 0.5
    total = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        vt = total / fps
        if framing == "manual":
            cur_cx = crop_cx
        else:
            src_t = virtual_to_source(segments, vt)
            target = cx_at(centers, src_t) if centers else 0.5
            cur_cx += SMOOTH_ALPHA * (target - cur_cx)
        sx, sy, cw, ch = compute_crop(W, H, aspect, cur_cx)
        out = cv2.resize(frame[sy:sy + ch, sx:sx + cw], (tw, th), interpolation=cv2.INTER_AREA)
        if renderer is not None:
            out = renderer.draw(out, vt)
        try:
            ff.stdin.write(out.tobytes())
        except BrokenPipeError:
            break
        total += 1

    cap.release()
    ff.stdin.close()
    ff.wait()
    if ff.returncode != 0:
        raise RuntimeError(f"ffmpeg reframe mux failed: {ff.stderr.read().decode()[-1200:]}")
    return {"frames": total, "width": tw, "height": th}


def run_vertical_export(job) -> dict:
    params = json.loads(job["params_json"] or "{}")
    video_id = job["video_id"]

    video = db.get_video(video_id)
    if video is None:
        raise RuntimeError(f"video {video_id} not found")
    tr = db.get_transcript(video_id)
    if tr is None:
        raise RuntimeError("transcript required for captions")
    has_audio = bool(video["audio_codec"])

    edit = db.get_edit(video_id)
    segments = json.loads(edit["edl_json"]) if edit else [
        {"id": "full", "sourceStart": 0.0, "sourceEnd": video["duration_seconds"]}
    ]
    kept = ordered_intervals(segments)
    if not kept:
        raise RuntimeError("EDL is empty; nothing to export.")

    out_dir = config.EXPORTS_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    intermediate = out_dir / f"{job['id']}_edit.mp4"
    final = out_dir / f"{job['id']}_vertical.mp4"

    # Settings drive aspect / framing / captions.
    srow = db.get_settings(video_id)
    settings = json.loads(srow["json"]) if srow else DEFAULT_SETTINGS
    aspect = settings.get("aspect", "9:16")
    framing = settings.get("framing", "auto")
    crop_cx = float(settings.get("crop_cx", 0.5))
    style = resolve_caption_style(settings.get("caption"))
    tw, th = target_dims(aspect)

    # Face-track trajectory (shared with the live preview); compute if missing.
    reframe_path = out_dir / "reframe.json"
    if not reframe_path.exists():
        run_reframe(video_id)
    rf = json.loads(reframe_path.read_text())
    centers = rf.get("centers", [])

    # 1. edit -> horizontal intermediate
    render_segments(video["stored_path"], kept, has_audio, str(intermediate))

    # 2. captions on the edited timeline
    words = json.loads(tr["words_json"])
    projected = project_words(segments, words)
    renderer = CaptionRenderer(projected, width=tw, height=th, style=style) if projected else None

    # 3. crop (aspect + trajectory/manual) + caption + mux
    _reframe_and_caption(str(intermediate), str(final), renderer, centers, segments, aspect, framing, crop_cx)
    intermediate.unlink(missing_ok=True)

    out_duration = _probe_duration(str(final))
    return {
        "output_path": str(final),
        "width": tw,
        "height": th,
        "aspect": aspect,
        "duration": round(out_duration, 3),
        "face_tracked": rf.get("tracked", False) and framing == "auto",
        "face_rate": rf.get("face_rate", 0.0),
        "num_caption_words": len(projected),
    }
