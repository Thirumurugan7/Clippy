"""Clippy FastAPI application.

M0 scope only:
- POST /api/upload         : receive and store a real video, enqueue a probe job
- GET  /api/videos/{id}    : video record + its metadata (filled by the worker)
- GET  /api/jobs           : list jobs (status queued/running/done/failed)
- GET  /api/jobs/{id}      : single job
- GET  /api/health         : liveness

No heavy processing happens in the request thread. Upload only stores bytes and
inserts a queued job row; the separate worker process does the ffprobe work.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from . import auth, config, db
from .edl import validate_edl, project_words
from .fillers import detect_fillers
from .silences import detect_silences, total_silence
from .presets import ASPECTS, CAPTION_PRESETS, REVEALS, ANIMATIONS, FONTS
from .subtitles import group_cues, cues_to_srt, cues_to_vtt
from .subtitle_edit import replace_cue_words
from .translate import translate_cues, LANGUAGES
from .diarize import diarize_segments
from .social import generate_social

COOKIE = "clippy_session"
_VIDEO_PATH = re.compile(r"^/api/videos/([0-9a-f]+)")
_EXPORT_PATH = re.compile(r"^/api/exports/([0-9a-f]+)")

DEFAULT_SETTINGS = {
    "aspect": "9:16",
    "framing": "auto",
    "crop_cx": 0.5,
    "crop_cy": 0.5,
    "enhance_audio": False,
    "background": {"mode": "none", "color": "#10121a"},
    "progress_bar": {"enabled": False, "color": "#8b6cf6", "position": "bottom"},
    "transition": {"fade": False},
    "text_overlays": [],
    "caption": {"preset": "karaoke", "fontsize": 58, "color": "#ff8a3d", "position": "bottom"},
}

app = FastAPI(title="Clippy", version="0.1.0")

# Vite dev server runs on a different origin during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Accept common container formats. ffprobe will validate for real in the worker.
ALLOWED_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}


@app.on_event("startup")
def _startup() -> None:
    config.ensure_dirs()
    db.init_db()
    auth.ensure_admin()


@app.middleware("http")
async def auth_and_ownership(request: Request, call_next):
    """Require a valid session for every /api route except auth + health, and
    enforce that a /api/videos/{id}... or /api/exports/{job}... path belongs to
    the signed-in user. Centralizes per-user isolation in one place."""
    path = request.url.path
    needs_auth = (
        path.startswith("/api/")
        and not path.startswith("/api/auth/")
        and path != "/api/health"
    )
    if needs_auth:
        user = auth.user_for_token(request.cookies.get(COOKIE))
        if user is None:
            return JSONResponse({"detail": "not authenticated"}, status_code=401)
        request.state.user = user
        m = _VIDEO_PATH.match(path)
        if m:
            v = db.get_video(m.group(1))
            if v is None or v["owner_id"] != user["id"]:
                return JSONResponse({"detail": "video not found"}, status_code=404)
        m = _EXPORT_PATH.match(path)
        if m:
            job = db.get_job(m.group(1))
            v = db.get_video(job["video_id"]) if job else None
            if v is None or v["owner_id"] != user["id"]:
                return JSONResponse({"detail": "export not found"}, status_code=404)
    return await call_next(request)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
class AuthBody(BaseModel):
    email: str
    password: str


def _set_session(response: Response, user_id: str) -> None:
    token = auth.new_session(user_id)
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)


@app.post("/api/auth/register")
def auth_register(body: AuthBody, response: Response) -> dict:
    try:
        user_id = auth.register(body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _set_session(response, user_id)
    return {"email": body.email.strip().lower()}


@app.post("/api/auth/login")
def auth_login(body: AuthBody, response: Response) -> dict:
    user_id = auth.authenticate(body.email, body.password)
    if user_id is None:
        raise HTTPException(status_code=401, detail="invalid email or password")
    _set_session(response, user_id)
    return {"email": body.email.strip().lower()}


@app.post("/api/auth/logout")
def auth_logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(COOKIE)
    if token:
        db.delete_session(token)
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/api/auth/me")
def auth_me(request: Request) -> dict:
    user = auth.user_for_token(request.cookies.get(COOKIE))
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return {"email": user["email"]}


def _job_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "video_id": row["video_id"],
        "type": row["type"],
        "status": row["status"],
        "error": row["error"],
        "params_json": row["params_json"],
        "result_json": row["result_json"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }


def _video_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "original_filename": row["original_filename"],
        "stored_path": row["stored_path"],
        "size_bytes": row["size_bytes"],
        "created_at": row["created_at"],
        "duration_seconds": row["duration_seconds"],
        "width": row["width"],
        "height": row["height"],
        "fps": row["fps"],
        "video_codec": row["video_codec"],
        "audio_codec": row["audio_codec"],
    }


@app.post("/api/upload")
async def upload(request: Request, file: UploadFile = File(...)) -> dict:
    """Store an uploaded video on disk (under the owner's dir) and enqueue jobs.

    The file is streamed to disk in chunks so a multi-GB upload does not get
    buffered entirely in memory.
    """
    owner_id = request.state.user["id"]
    original_name = file.filename or "upload"
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {sorted(ALLOWED_SUFFIXES)}",
        )

    video_id = uuid.uuid4().hex
    dest_dir = config.UPLOADS_DIR / owner_id / video_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / original_name

    size_bytes = 0
    with dest_path.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)  # 1 MiB
            if not chunk:
                break
            size_bytes += len(chunk)
            out.write(chunk)

    if size_bytes == 0:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file was empty.")

    # Record the video using the id we already used for its directory.
    with db.get_conn() as conn:
        conn.execute(
            """INSERT INTO videos (id, original_filename, stored_path, size_bytes, created_at, owner_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (video_id, original_name, str(dest_path), size_bytes, time.time(), owner_id),
        )

    # Enqueue probe (metadata) then transcription. The worker runs them in
    # creation order, one at a time.
    probe_job_id = db.create_job(video_id, job_type="probe")
    transcribe_job_id = db.create_job(video_id, job_type="transcribe")
    db.create_job(video_id, job_type="waveform")

    return {
        "video_id": video_id,
        "job_id": probe_job_id,
        "probe_job_id": probe_job_id,
        "transcribe_job_id": transcribe_job_id,
        "stored_path": str(dest_path),
        "size_bytes": size_bytes,
    }


@app.get("/api/videos/{video_id}")
def get_video(video_id: str) -> dict:
    row = db.get_video(video_id)
    if row is None:
        raise HTTPException(status_code=404, detail="video not found")
    return _video_to_dict(row)


@app.get("/api/jobs")
def list_jobs(request: Request) -> dict:
    owner_id = request.state.user["id"]
    return {"jobs": [_job_to_dict(r) for r in db.list_jobs_for_owner(owner_id)]}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, request: Request) -> dict:
    row = db.get_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    v = db.get_video(row["video_id"])
    if v is None or v["owner_id"] != request.state.user["id"]:
        raise HTTPException(status_code=404, detail="job not found")
    return _job_to_dict(row)


@app.get("/api/videos/{video_id}/transcript")
def get_transcript(video_id: str) -> dict:
    """Return the stored transcript (word-level timestamps) for a video.

    While transcription is still running we return 200 with {"ready": false}
    rather than 404, so the frontend can poll without spamming the browser
    console with failed-request errors. A genuinely missing video is still 404.
    """
    if db.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="video not found")
    row = db.get_transcript(video_id)
    if row is None:
        job = db.latest_job(video_id, "transcribe")
        return {
            "ready": False,
            "progress": (job["progress"] if job else 0.0) or 0.0,
            "status": job["status"] if job else "queued",
        }
    return {
        "ready": True,
        "video_id": row["video_id"],
        "language": row["language"],
        "language_probability": row["language_probability"],
        "model": row["model"],
        "duration_seconds": row["duration_seconds"],
        "words": json.loads(row["words_json"]),
        "segments": json.loads(row["segments_json"]),
    }


def _projected_caption_words(video_id: str) -> list[dict]:
    """Transcript words mapped onto the edited timeline (same as the export)."""
    tr = db.get_transcript(video_id)
    if tr is None:
        raise HTTPException(status_code=400, detail="transcript not ready")
    words = json.loads(tr["words_json"])
    edit = db.get_edit(video_id)
    if edit is not None:
        segments = json.loads(edit["edl_json"])
    else:
        v = db.get_video(video_id)
        segments = [{"id": "full", "sourceStart": 0.0, "sourceEnd": v["duration_seconds"]}]
    return project_words(segments, words)


def _cues_for(video_id: str, lang: str) -> list[dict]:
    """Caption cues for the edited clip, optionally translated to `lang`."""
    cues = group_cues(_projected_caption_words(video_id))
    if lang and lang in LANGUAGES:
        cues = translate_cues(cues, lang)
    return cues


@app.get("/api/subtitles/languages")
def subtitle_languages() -> dict:
    """Languages Clippy can translate captions into (local gemma4)."""
    return {"languages": [{"code": c, "name": n} for c, n in LANGUAGES.items()]}


class CueEdit(BaseModel):
    start: float
    end: float
    text: str


@app.put("/api/videos/{video_id}/transcript/cue")
def edit_transcript_cue(video_id: str, body: CueEdit) -> dict:
    """Replace the words under one subtitle cue with edited text (retimed evenly).

    Fixes flow to burned-in captions and SRT/VTT alike (both read the words).
    """
    tr = db.get_transcript(video_id)
    if tr is None:
        raise HTTPException(status_code=400, detail="transcript not ready")
    if body.end <= body.start:
        raise HTTPException(status_code=400, detail="end must be after start")
    words = json.loads(tr["words_json"])
    updated = replace_cue_words(words, body.start, body.end, body.text)
    db.update_transcript_words(video_id, json.dumps(updated))
    return {"ok": True, "word_count": len(updated)}


class DiarizeBody(BaseModel):
    max_speakers: int = 4


@app.post("/api/videos/{video_id}/diarize")
def diarize_video(video_id: str, body: DiarizeBody = DiarizeBody()) -> dict:
    """Tag each transcript segment with a speaker index (local, no model download).

    Runs synchronously — MFCC + clustering over the segments is fast (numpy). The
    speaker labels are written back onto `segments_json`, so they flow to the
    transcript view and can colour captions per speaker.
    """
    video = db.get_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="video not found")
    tr = db.get_transcript(video_id)
    if tr is None:
        raise HTTPException(status_code=400, detail="transcript not ready")
    max_speakers = max(1, min(int(body.max_speakers), 8))
    segments = json.loads(tr["segments_json"])
    labels = diarize_segments(video["stored_path"], segments, max_speakers=max_speakers)
    for seg, spk in zip(segments, labels):
        seg["speaker"] = int(spk)
    db.update_transcript_segments(video_id, json.dumps(segments))
    return {"ok": True, "num_speakers": (max(labels) + 1) if labels else 0, "segments": segments}


@app.get("/api/videos/{video_id}/subtitles.srt")
def get_subtitles_srt(video_id: str, lang: str = ""):
    if db.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="video not found")
    suffix = f".{lang}" if lang in LANGUAGES else ""
    body = cues_to_srt(_cues_for(video_id, lang))
    return Response(content=body, media_type="application/x-subrip",
                    headers={"Content-Disposition": f'attachment; filename="{video_id}{suffix}.srt"'})


@app.get("/api/videos/{video_id}/subtitles.vtt")
def get_subtitles_vtt(video_id: str, lang: str = ""):
    if db.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="video not found")
    suffix = f".{lang}" if lang in LANGUAGES else ""
    body = cues_to_vtt(_cues_for(video_id, lang))
    return Response(content=body, media_type="text/vtt",
                    headers={"Content-Disposition": f'attachment; filename="{video_id}{suffix}.vtt"'})


# Browsers request video in byte ranges so the player can seek. Starlette's
# FileResponse does not implement Range, so we handle it explicitly here.
_CHUNK = 1024 * 1024  # 1 MiB


def _stream_with_range(path: Path, request: Request, media_type: str = "video/mp4"):
    """Stream a file with HTTP Range support (206 partial content) for seeking."""
    if not path.exists():
        raise HTTPException(status_code=404, detail="file missing on disk")

    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    if range_header is None:
        def full_iter():
            with path.open("rb") as f:
                while True:
                    data = f.read(_CHUNK)
                    if not data:
                        break
                    yield data

        return StreamingResponse(
            full_iter(),
            media_type=media_type,
            headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)},
        )

    # Parse "bytes=start-end" (end optional).
    try:
        units, rng = range_header.split("=", 1)
        if units.strip() != "bytes":
            raise ValueError
        start_s, _, end_s = rng.partition("-")
        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else file_size - 1
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid Range header")

    if start > end or start >= file_size:
        return Response(
            status_code=416,
            headers={"Content-Range": f"bytes */{file_size}"},
        )
    end = min(end, file_size - 1)
    length = end - start + 1

    def range_iter():
        with path.open("rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                data = f.read(min(_CHUNK, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
    }
    return StreamingResponse(
        range_iter(), status_code=206, media_type=media_type, headers=headers
    )


@app.get("/api/videos/{video_id}/file")
def get_video_file(video_id: str, request: Request):
    video = db.get_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="video not found")
    return _stream_with_range(Path(video["stored_path"]), request)


@app.get("/api/videos/{video_id}/waveform")
def get_waveform(video_id: str) -> dict:
    """Return precomputed audio peaks for the timeline (404 until the job runs)."""
    path = config.EXPORTS_DIR / video_id / "waveform.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="waveform not ready")
    return json.loads(path.read_text())


@app.get("/api/videos/{video_id}/fillers")
def get_fillers(video_id: str) -> dict:
    """Return indices of detected filler words for the user to review."""
    if db.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="video not found")
    tr = db.get_transcript(video_id)
    if tr is None:
        raise HTTPException(status_code=404, detail="transcript not ready")
    words = json.loads(tr["words_json"])
    indices = detect_fillers(words)
    return {"indices": indices, "count": len(indices)}


@app.get("/api/videos/{video_id}/silences")
def get_silences(video_id: str, min_silence: float = 0.6, noise_db: float = -30.0) -> dict:
    """Detect dead-air ranges (source time) for the user to cut. Local, ffmpeg-only.

    Same review-then-apply flow as filler removal: the frontend drops these ranges
    from the EDL; nothing is deleted automatically.
    """
    video = db.get_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="video not found")
    ranges = detect_silences(
        video["stored_path"],
        noise_db=noise_db,
        min_silence=max(0.2, min_silence),
        duration=video["duration_seconds"],
    )
    return {"ranges": ranges, "count": len(ranges), "total_seconds": total_silence(ranges)}


class EdlBody(BaseModel):
    segments: list[dict]


@app.get("/api/videos/{video_id}/edit")
def get_edit(video_id: str) -> dict:
    """Return the saved EDL, or a default single full-length segment."""
    video = db.get_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="video not found")
    row = db.get_edit(video_id)
    if row is not None:
        return {"segments": json.loads(row["edl_json"])}
    dur = video["duration_seconds"] or 0.0
    return {"segments": [{"id": uuid.uuid4().hex, "sourceStart": 0.0, "sourceEnd": dur}]}


@app.put("/api/videos/{video_id}/edit")
def put_edit(video_id: str, body: EdlBody) -> dict:
    """Persist the EDL (autosaved by the editor). Validated against duration."""
    video = db.get_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="video not found")
    dur = video["duration_seconds"] or 0.0
    try:
        validate_edl(body.segments, dur)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.save_edit(video_id, json.dumps(body.segments))
    return {"ok": True}


@app.post("/api/videos/{video_id}/highlights")
def generate_highlights(video_id: str) -> dict:
    """Enqueue a gemma4 highlight-detection job over the video's transcript."""
    if db.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="video not found")
    if db.get_transcript(video_id) is None:
        raise HTTPException(status_code=400, detail="transcript not ready")
    job_id = db.create_job(video_id, job_type="highlights")
    return {"job_id": job_id}


@app.post("/api/videos/{video_id}/social")
def social_copy(video_id: str) -> dict:
    """Generate a hook title, description, and hashtags from the transcript (local gemma4)."""
    if db.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="video not found")
    try:
        return generate_social(video_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/videos/{video_id}/highlights")
def get_highlights(video_id: str) -> dict:
    """Return stored highlight candidates (and the raw model output)."""
    if db.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="video not found")
    row = db.get_highlights(video_id)
    if row is None:
        return {"ready": False, "clips": None}
    return {
        "ready": True,
        "clips": json.loads(row["clips_json"]) if row["clips_json"] else None,
        "model": row["model"],
        "error": row["error"],
        "raw": row["raw"],
    }


class BatchClip(BaseModel):
    start: float
    end: float
    reason: str = ""


class ExportBatchBody(BaseModel):
    # If omitted, the stored highlight candidates (M3) are exported.
    clips: list[BatchClip] | None = None


@app.post("/api/videos/{video_id}/export_batch")
def export_batch(video_id: str, body: ExportBatchBody | None = None) -> dict:
    """Enqueue ONE job that renders many vertical shorts from this source.

    Clips come from the request body, or fall back to the stored highlight
    candidates. This is the "one long video -> many clips" flow.
    """
    if db.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="video not found")
    if db.get_transcript(video_id) is None:
        raise HTTPException(status_code=400, detail="transcript not ready")

    clips = [c.model_dump() for c in body.clips] if body and body.clips else None
    if clips is None:
        row = db.get_highlights(video_id)
        clips = json.loads(row["clips_json"]) if row and row["clips_json"] else None
        if not clips:
            raise HTTPException(status_code=400, detail="no clips provided and no highlights available")
    job_id = db.create_job(video_id, job_type="export_batch", params_json=json.dumps({"clips": clips}))
    return {"job_id": job_id, "count": len(clips)}


@app.post("/api/videos/{video_id}/export")
def export_edit(video_id: str) -> dict:
    """Enqueue an export job that renders the saved EDL for this video.

    The editor PUTs the EDL (autosave) before calling this, so no body is
    needed; the worker reads the saved EDL.
    """
    if db.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="video not found")
    if db.get_transcript(video_id) is None:
        raise HTTPException(status_code=400, detail="transcript not ready")
    job_id = db.create_job(video_id, job_type="export_edit")
    return {"job_id": job_id}


class AiEditBody(BaseModel):
    prompt: str


@app.post("/api/videos/{video_id}/ai_edit")
def start_ai_edit(video_id: str, body: AiEditBody) -> dict:
    if db.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="video not found")
    if db.get_transcript(video_id) is None:
        raise HTTPException(status_code=400, detail="transcript not ready")
    job_id = db.create_job(video_id, job_type="ai_edit", params_json=json.dumps({"prompt": body.prompt}))
    return {"job_id": job_id}


@app.get("/api/videos/{video_id}/ai_edit")
def get_ai_edit(video_id: str) -> dict:
    row = db.get_ai_edit(video_id)
    if row is None:
        return {"ready": False}
    return {
        "ready": True,
        "clip": json.loads(row["clip_json"]) if row["clip_json"] else None,
        "aspect": row["aspect"],
        "caption_preset": row["caption_preset"],
        "reason": row["reason"],
        "raw": row["raw"],
        "error": row["error"],
    }


@app.get("/api/videos/{video_id}/ai_edit/turns")
def get_ai_edit_turns(video_id: str) -> dict:
    """The conversation so far — each turn's prompt and resulting proposal."""
    turns = []
    for row in db.get_ai_edit_turns(video_id):
        turns.append({
            "id": row["id"],
            "prompt": row["prompt"],
            "proposal": json.loads(row["proposal_json"]) if row["proposal_json"] else None,
            "error": row["error"],
        })
    return {"turns": turns}


class SettingsBody(BaseModel):
    aspect: str
    framing: str
    crop_cx: float
    crop_cy: float = 0.5
    enhance_audio: bool = False
    background: dict = {"mode": "none", "color": "#10121a"}
    progress_bar: dict = {"enabled": False, "color": "#8b6cf6", "position": "bottom"}
    transition: dict = {"fade": False}
    text_overlays: list = []
    caption: dict


@app.get("/api/videos/{video_id}/settings")
def get_settings(video_id: str) -> dict:
    if db.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="video not found")
    row = db.get_settings(video_id)
    return json.loads(row["json"]) if row else dict(DEFAULT_SETTINGS)


@app.put("/api/videos/{video_id}/settings")
def put_settings(video_id: str, body: SettingsBody) -> dict:
    if db.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="video not found")
    if body.aspect not in ASPECTS:
        raise HTTPException(status_code=400, detail=f"unknown aspect {body.aspect}")
    if body.framing not in ("auto", "manual"):
        raise HTTPException(status_code=400, detail="framing must be auto|manual")
    if not (0.0 <= body.crop_cx <= 1.0):
        raise HTTPException(status_code=400, detail="crop_cx out of range")
    if body.caption.get("preset") not in CAPTION_PRESETS:
        raise HTTPException(status_code=400, detail="unknown caption preset")
    lang = body.caption.get("language")
    if lang and lang not in LANGUAGES:
        raise HTTPException(status_code=400, detail=f"unknown caption language {lang}")
    reveal = body.caption.get("reveal")
    if reveal and reveal not in REVEALS:
        raise HTTPException(status_code=400, detail=f"unknown caption reveal type {reveal}")
    anim = body.caption.get("animation")
    if anim and anim not in ANIMATIONS:
        raise HTTPException(status_code=400, detail=f"unknown caption animation {anim}")
    font = body.caption.get("font")
    if font and font not in FONTS:
        raise HTTPException(status_code=400, detail=f"unknown caption font {font}")
    db.save_settings(video_id, json.dumps(body.model_dump()))
    return {"ok": True}


_BG_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


@app.post("/api/videos/{video_id}/background_image")
async def upload_background_image(video_id: str, file: UploadFile = File(...)) -> dict:
    """Store a custom background photo for the 'image' background mode."""
    if db.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="video not found")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _BG_IMAGE_EXTS:
        ext = ".png"
    out_dir = config.EXPORTS_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in out_dir.glob("bg_source.*"):
        p.unlink(missing_ok=True)
    path = out_dir / f"bg_source{ext}"
    path.write_bytes(await file.read())
    return {"image": str(path)}


@app.get("/api/videos/{video_id}/background_image/file")
def get_background_image(video_id: str):
    out_dir = config.EXPORTS_DIR / video_id
    for p in sorted(out_dir.glob("bg_source.*")):
        media = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(p.suffix.lower(), "image/png")
        return Response(content=p.read_bytes(), media_type=media)
    raise HTTPException(status_code=404, detail="no background image")


@app.post("/api/videos/{video_id}/reframe")
def generate_reframe(video_id: str) -> dict:
    """Enqueue face-track analysis (for the live vertical preview + export)."""
    if db.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="video not found")
    path = config.EXPORTS_DIR / video_id / "reframe.json"
    if path.exists():
        return {"job_id": None, "ready": True}
    job_id = db.create_job(video_id, job_type="reframe")
    return {"job_id": job_id, "ready": False}


@app.get("/api/videos/{video_id}/reframe")
def get_reframe(video_id: str) -> dict:
    path = config.EXPORTS_DIR / video_id / "reframe.json"
    if not path.exists():
        return {"ready": False}
    data = json.loads(path.read_text())
    data["ready"] = True
    return data


@app.post("/api/videos/{video_id}/export_vertical")
def export_vertical(video_id: str) -> dict:
    """Enqueue a 9:16 vertical export: face-tracked reframe + burned captions."""
    if db.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="video not found")
    if db.get_transcript(video_id) is None:
        raise HTTPException(status_code=400, detail="transcript not ready")
    job_id = db.create_job(video_id, job_type="export_vertical")
    return {"job_id": job_id}


@app.get("/api/exports/{job_id}/file")
def get_export_file(job_id: str, request: Request):
    """Stream an exported edited video (range-capable for the player)."""
    job = db.get_job(job_id)
    if job is None or job["type"] not in ("export_edit", "export_vertical"):
        raise HTTPException(status_code=404, detail="export job not found")
    if job["status"] != "done" or not job["result_json"]:
        raise HTTPException(status_code=409, detail=f"export not ready (status={job['status']})")
    out_path = json.loads(job["result_json"]).get("output_path")
    if not out_path:
        raise HTTPException(status_code=500, detail="export has no output path")
    return _stream_with_range(Path(out_path), request)


@app.get("/api/exports/{job_id}/clip/{index}/file")
def get_batch_clip_file(job_id: str, index: int, request: Request):
    """Stream one short from a batch export job by its clip index."""
    job = db.get_job(job_id)
    if job is None or job["type"] != "export_batch":
        raise HTTPException(status_code=404, detail="batch export job not found")
    if job["status"] != "done" or not job["result_json"]:
        raise HTTPException(status_code=409, detail=f"export not ready (status={job['status']})")
    clips = json.loads(job["result_json"]).get("clips", [])
    match = next((c for c in clips if c.get("index") == index and c.get("output_path")), None)
    if match is None:
        raise HTTPException(status_code=404, detail="clip not found or failed to render")
    return _stream_with_range(Path(match["output_path"]), request)
