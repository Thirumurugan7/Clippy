"""ClipForge FastAPI application.

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
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from . import config, db
from .fillers import detect_fillers

app = FastAPI(title="ClipForge", version="0.1.0")

# Vite dev server runs on a different origin during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Accept common container formats. ffprobe will validate for real in the worker.
ALLOWED_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}


@app.on_event("startup")
def _startup() -> None:
    config.ensure_dirs()
    db.init_db()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


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
async def upload(file: UploadFile = File(...)) -> dict:
    """Store an uploaded video on disk and enqueue a probe job.

    The file is streamed to disk in chunks so a multi-GB upload does not get
    buffered entirely in memory.
    """
    original_name = file.filename or "upload"
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {sorted(ALLOWED_SUFFIXES)}",
        )

    video_id = uuid.uuid4().hex
    dest_dir = config.UPLOADS_DIR / video_id
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
            """INSERT INTO videos (id, original_filename, stored_path, size_bytes, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (video_id, original_name, str(dest_path), size_bytes, time.time()),
        )

    # Enqueue probe (metadata) then transcription. The worker runs them in
    # creation order, one at a time.
    probe_job_id = db.create_job(video_id, job_type="probe")
    transcribe_job_id = db.create_job(video_id, job_type="transcribe")

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
def list_jobs() -> dict:
    return {"jobs": [_job_to_dict(r) for r in db.list_jobs()]}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    row = db.get_job(job_id)
    if row is None:
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
        return {"ready": False}
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


class ExportRequest(BaseModel):
    delete_word_indices: list[int] = []


@app.post("/api/videos/{video_id}/export")
def export_edit(video_id: str, req: ExportRequest) -> dict:
    """Enqueue an export job that cuts the deleted words' time spans."""
    if db.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="video not found")
    if db.get_transcript(video_id) is None:
        raise HTTPException(status_code=400, detail="transcript not ready")
    params = json.dumps({"delete_word_indices": sorted(set(req.delete_word_indices))})
    job_id = db.create_job(video_id, job_type="export_edit", params_json=params)
    return {"job_id": job_id, "deleted": len(set(req.delete_word_indices))}


@app.get("/api/exports/{job_id}/file")
def get_export_file(job_id: str, request: Request):
    """Stream an exported edited video (range-capable for the player)."""
    job = db.get_job(job_id)
    if job is None or job["type"] != "export_edit":
        raise HTTPException(status_code=404, detail="export job not found")
    if job["status"] != "done" or not job["result_json"]:
        raise HTTPException(status_code=409, detail=f"export not ready (status={job['status']})")
    out_path = json.loads(job["result_json"]).get("output_path")
    if not out_path:
        raise HTTPException(status_code=500, detail="export has no output path")
    return _stream_with_range(Path(out_path), request)
