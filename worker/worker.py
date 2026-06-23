"""ClipForge worker process.

Runs as a SEPARATE process from the API. Pulls one job at a time from the
SQLite job table and runs it to completion before taking the next — no
concurrency, matching the 16 GB Apple Silicon constraint.

Restart safety: on startup any job left in 'running' (because a previous worker
crashed or was killed mid-job) is requeued, so no work is silently lost.

M0 handles one job type: 'probe'. Later milestones register more handlers in
the HANDLERS dispatch table without changing this loop.
"""
from __future__ import annotations

import json
import signal
import sys
import time
import traceback

from backend import db
from worker.steps.probe import run_probe
from worker.steps.transcribe import run_transcribe
from worker.steps.export_edit import run_export_edit
from worker.steps.waveform import run_waveform
from worker.steps.highlights import run_highlights_job
from worker.steps.vertical import run_vertical_export
from worker.steps.reframe import run_reframe
from worker.steps.ai_edit import run_ai_edit_job
import json as _json

POLL_INTERVAL_SECONDS = 1.0

# Dispatch table: job type -> handler(job_row) -> result dict (JSON-serialisable).
# Handlers receive the whole job row so they can read params_json when needed.
HANDLERS = {
    "probe": lambda job: run_probe(job["video_id"]),
    "transcribe": lambda job: run_transcribe(job["video_id"], job["id"]),
    "waveform": lambda job: run_waveform(job["video_id"]),
    "highlights": lambda job: run_highlights_job(job["video_id"]),
    "reframe": lambda job: run_reframe(job["video_id"]),
    "ai_edit": lambda job: run_ai_edit_job(job["video_id"], _json.loads(job["params_json"] or "{}").get("prompt", "")),
    "export_edit": run_export_edit,
    "export_vertical": run_vertical_export,
}

_running = True


def _handle_signal(signum, _frame) -> None:
    global _running
    _running = False
    print(f"[worker] received signal {signum}, finishing current loop and exiting...")


def process_one() -> bool:
    """Claim and run a single job. Returns True if a job was processed."""
    job = db.claim_next_job()
    if job is None:
        return False

    job_id = job["id"]
    job_type = job["type"]
    video_id = job["video_id"]
    print(f"[worker] running job {job_id} type={job_type} video={video_id}")

    handler = HANDLERS.get(job_type)
    if handler is None:
        db.fail_job(job_id, f"No handler registered for job type '{job_type}'")
        print(f"[worker] FAILED job {job_id}: unknown type '{job_type}'")
        return True

    try:
        result = handler(job)
        db.finish_job(job_id, result_json=json.dumps(result))
        print(f"[worker] DONE job {job_id}: {result}")
    except Exception as exc:  # noqa: BLE001 - we persist every failure
        err = f"{exc}\n{traceback.format_exc()}"
        db.fail_job(job_id, err)
        print(f"[worker] FAILED job {job_id}: {exc}", file=sys.stderr)
    return True


def main() -> None:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    db.init_db()
    requeued = db.reset_orphaned_jobs()
    if requeued:
        print(f"[worker] requeued {requeued} orphaned running job(s) from a prior run")

    print("[worker] started; polling for jobs...")
    while _running:
        try:
            did_work = process_one()
        except Exception as exc:  # defensive: never let the loop die
            print(f"[worker] loop error: {exc}", file=sys.stderr)
            did_work = False
        if not did_work:
            time.sleep(POLL_INTERVAL_SECONDS)

    print("[worker] stopped.")


if __name__ == "__main__":
    main()
