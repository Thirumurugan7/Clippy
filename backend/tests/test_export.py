import json

from backend import db
from worker.steps.export_edit import run_export_edit


def _short_video_id():
    with db.get_conn() as c:
        row = c.execute(
            "SELECT v.id FROM videos v JOIN transcripts t ON t.video_id=v.id "
            "WHERE v.original_filename LIKE 'sample_short%' "
            "ORDER BY v.created_at DESC LIMIT 1"
        ).fetchone()
    return row["id"] if row else None


def test_export_from_edl_reordered():
    vid = _short_video_id()
    assert vid
    dur = db.get_video(vid)["duration_seconds"]
    # Two segments, reordered: second half first, then first half.
    half = round(dur / 2, 2)
    segs = [
        {"id": "b", "sourceStart": half, "sourceEnd": dur},
        {"id": "a", "sourceStart": 0.0, "sourceEnd": half},
    ]
    db.save_edit(vid, json.dumps(segs))
    job = {"id": "exptest01", "video_id": vid, "params_json": "{}"}
    res = run_export_edit(job)
    assert res["num_segments"] == 2
    assert abs(res["output_duration"] - dur) < 1.0  # same total, reordered
