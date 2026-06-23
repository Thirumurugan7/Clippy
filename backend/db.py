"""SQLite-backed storage for videos and the job queue.

The same database is shared by the FastAPI process (which enqueues jobs) and
the worker process (which executes them). SQLite in WAL mode handles this
multi-process access safely for a single-worker dev setup.

Design notes / hard requirements satisfied here:
- Jobs have status queued/running/done/failed and a stored `error` message.
- The schema is process-restart safe: see `reset_orphaned_jobs()`, which the
  worker calls on startup to requeue jobs that were mid-flight when it died.
"""
from __future__ import annotations

import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Iterator, Optional

from . import config

# Valid job lifecycle states.
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"


def _connect() -> sqlite3.Connection:
    config.ensure_dirs()
    conn = sqlite3.connect(config.DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # WAL allows the API and worker processes to read/write concurrently.
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they do not exist. Safe to call repeatedly."""
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id         TEXT PRIMARY KEY,
                email      TEXT UNIQUE NOT NULL,
                pw_salt    TEXT NOT NULL,
                pw_hash    TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token      TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL REFERENCES users(id),
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS videos (
                id               TEXT PRIMARY KEY,
                original_filename TEXT NOT NULL,
                stored_path      TEXT NOT NULL,
                size_bytes       INTEGER NOT NULL,
                created_at       REAL NOT NULL,
                -- Filled in by the M0 probe job (real ffprobe output):
                duration_seconds REAL,
                width            INTEGER,
                height           INTEGER,
                fps              REAL,
                video_codec      TEXT,
                audio_codec      TEXT
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id          TEXT PRIMARY KEY,
                video_id    TEXT NOT NULL REFERENCES videos(id),
                type        TEXT NOT NULL,
                status      TEXT NOT NULL,
                error       TEXT,
                params_json TEXT,
                result_json TEXT,
                created_at  REAL NOT NULL,
                started_at  REAL,
                finished_at REAL
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_status_created
                ON jobs(status, created_at);

            -- (transcripts table below)
            CREATE TABLE IF NOT EXISTS transcripts (
                video_id             TEXT PRIMARY KEY REFERENCES videos(id),
                language             TEXT,
                language_probability REAL,
                model                TEXT NOT NULL,
                duration_seconds     REAL,
                created_at           REAL NOT NULL,
                -- Flat list of words: [{i, word, start, end, prob}], JSON.
                words_json           TEXT NOT NULL,
                -- Segments referencing word index ranges:
                -- [{id, start, end, text, word_start, word_end}], JSON.
                segments_json        TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS edits (
                video_id   TEXT PRIMARY KEY REFERENCES videos(id),
                edl_json   TEXT NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS highlights (
                video_id   TEXT PRIMARY KEY REFERENCES videos(id),
                clips_json TEXT,
                raw        TEXT,
                model      TEXT,
                error      TEXT,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                video_id   TEXT PRIMARY KEY REFERENCES videos(id),
                json       TEXT NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ai_edits (
                video_id       TEXT PRIMARY KEY REFERENCES videos(id),
                clip_json      TEXT,
                aspect         TEXT,
                caption_preset TEXT,
                reason         TEXT,
                raw            TEXT,
                error          TEXT,
                updated_at     REAL NOT NULL
            );
            """
        )
        # Migration for databases created before params_json existed.
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(jobs)")]
        if "params_json" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN params_json TEXT")
        # Migration: per-user ownership of videos.
        vcols = [r["name"] for r in conn.execute("PRAGMA table_info(videos)")]
        if "owner_id" not in vcols:
            conn.execute("ALTER TABLE videos ADD COLUMN owner_id TEXT")


# --------------------------------------------------------------------------- #
# Videos
# --------------------------------------------------------------------------- #
def create_video(original_filename: str, stored_path: str, size_bytes: int) -> str:
    video_id = uuid.uuid4().hex
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO videos (id, original_filename, stored_path, size_bytes, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (video_id, original_filename, stored_path, size_bytes, time.time()),
        )
    return video_id


def update_video_metadata(
    video_id: str,
    *,
    duration_seconds: Optional[float],
    width: Optional[int],
    height: Optional[int],
    fps: Optional[float],
    video_codec: Optional[str],
    audio_codec: Optional[str],
) -> None:
    with get_conn() as conn:
        conn.execute(
            """UPDATE videos
               SET duration_seconds=?, width=?, height=?, fps=?,
                   video_codec=?, audio_codec=?
               WHERE id=?""",
            (duration_seconds, width, height, fps, video_codec, audio_codec, video_id),
        )


def get_video(video_id: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM videos WHERE id=?", (video_id,)).fetchone()


def list_videos_for_owner(owner_id: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM videos WHERE owner_id=? ORDER BY created_at DESC", (owner_id,)
        ).fetchall()


# --------------------------------------------------------------------------- #
# Users & sessions
# --------------------------------------------------------------------------- #
def create_user_row(user_id: str, email: str, pw_salt: str, pw_hash: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (id, email, pw_salt, pw_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, email, pw_salt, pw_hash, time.time()),
        )


def get_user_by_email(email: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()


def get_user_by_id(user_id: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()


def count_users() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def create_session_row(token: str, user_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, time.time()),
        )


def get_session_user(token: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?",
            (token,),
        ).fetchone()


def delete_session(token: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))


def count_orphan_videos() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM videos WHERE owner_id IS NULL").fetchone()["n"]


def assign_orphan_videos(owner_id: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE videos SET owner_id=? WHERE owner_id IS NULL", (owner_id,)
        )
        return cur.rowcount


# --------------------------------------------------------------------------- #
# Transcripts
# --------------------------------------------------------------------------- #
def save_transcript(
    video_id: str,
    *,
    language: Optional[str],
    language_probability: Optional[float],
    model: str,
    duration_seconds: Optional[float],
    words_json: str,
    segments_json: str,
) -> None:
    """Insert or replace the transcript for a video (one transcript per video)."""
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO transcripts
               (video_id, language, language_probability, model, duration_seconds,
                created_at, words_json, segments_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                video_id,
                language,
                language_probability,
                model,
                duration_seconds,
                time.time(),
                words_json,
                segments_json,
            ),
        )


def get_transcript(video_id: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM transcripts WHERE video_id=?", (video_id,)
        ).fetchone()


# --------------------------------------------------------------------------- #
# Edits (EDL)
# --------------------------------------------------------------------------- #
def get_edit(video_id: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM edits WHERE video_id=?", (video_id,)
        ).fetchone()


def save_edit(video_id: str, edl_json: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO edits (video_id, edl_json, updated_at) VALUES (?, ?, ?)",
            (video_id, edl_json, time.time()),
        )


# --------------------------------------------------------------------------- #
# Highlights (gemma4 candidate clips)
# --------------------------------------------------------------------------- #
def save_highlights(
    video_id: str, *, clips_json: Optional[str], raw: Optional[str],
    model: Optional[str], error: Optional[str],
) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO highlights
               (video_id, clips_json, raw, model, error, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (video_id, clips_json, raw, model, error, time.time()),
        )


def get_highlights(video_id: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM highlights WHERE video_id=?", (video_id,)
        ).fetchone()


# --------------------------------------------------------------------------- #
# Settings (framing + captions) and AI-edit proposals
# --------------------------------------------------------------------------- #
def get_settings(video_id: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM settings WHERE video_id=?", (video_id,)).fetchone()


def save_settings(video_id: str, json_str: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (video_id, json, updated_at) VALUES (?, ?, ?)",
            (video_id, json_str, time.time()),
        )


def save_ai_edit(video_id: str, *, clip_json, aspect, caption_preset, reason, raw, error) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO ai_edits
               (video_id, clip_json, aspect, caption_preset, reason, raw, error, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (video_id, clip_json, aspect, caption_preset, reason, raw, error, time.time()),
        )


def get_ai_edit(video_id: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM ai_edits WHERE video_id=?", (video_id,)).fetchone()


# --------------------------------------------------------------------------- #
# Jobs
# --------------------------------------------------------------------------- #
def create_job(video_id: str, job_type: str, params_json: Optional[str] = None) -> str:
    job_id = uuid.uuid4().hex
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO jobs (id, video_id, type, status, params_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (job_id, video_id, job_type, STATUS_QUEUED, params_json, time.time()),
        )
    return job_id


def get_job(job_id: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()


def list_jobs(limit: int = 100) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()


def list_jobs_for_owner(owner_id: str, limit: int = 100) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT j.* FROM jobs j JOIN videos v ON v.id=j.video_id
               WHERE v.owner_id=? ORDER BY j.created_at DESC LIMIT ?""",
            (owner_id, limit),
        ).fetchall()


def claim_next_job() -> Optional[sqlite3.Row]:
    """Atomically move the oldest queued job to 'running' and return it.

    The UPDATE ... WHERE status=queued guard means that even if two workers
    raced (we only run one in dev), only one could claim a given job.
    """
    with get_conn() as conn:
        row = conn.execute(
            """SELECT * FROM jobs WHERE status=?
               ORDER BY created_at ASC LIMIT 1""",
            (STATUS_QUEUED,),
        ).fetchone()
        if row is None:
            return None
        cur = conn.execute(
            """UPDATE jobs SET status=?, started_at=?
               WHERE id=? AND status=?""",
            (STATUS_RUNNING, time.time(), row["id"], STATUS_QUEUED),
        )
        if cur.rowcount != 1:
            return None  # someone else claimed it first
        return conn.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()


def finish_job(job_id: str, *, result_json: Optional[str] = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET status=?, finished_at=?, result_json=?, error=NULL WHERE id=?",
            (STATUS_DONE, time.time(), result_json, job_id),
        )


def fail_job(job_id: str, error: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET status=?, finished_at=?, error=? WHERE id=?",
            (STATUS_FAILED, time.time(), error, job_id),
        )


def reset_orphaned_jobs() -> int:
    """Requeue jobs left in 'running' by a crashed/restarted worker.

    With a single worker, any job still marked 'running' at startup was
    interrupted, so it is safe to move it back to 'queued' to retry.
    Returns the number of jobs requeued.
    """
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE jobs SET status=?, started_at=NULL WHERE status=?",
            (STATUS_QUEUED, STATUS_RUNNING),
        )
        return cur.rowcount
