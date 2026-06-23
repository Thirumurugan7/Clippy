import json

from backend import db, config
from worker.steps.waveform import run_waveform


def _short_video_id():
    with db.get_conn() as c:
        row = c.execute(
            "SELECT id FROM videos WHERE original_filename LIKE 'sample_short%' "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return row["id"] if row else None


def test_waveform_real():
    vid = _short_video_id()
    assert vid, "need an uploaded sample_short.mp4 (run M1 first)"
    res = run_waveform(vid)
    assert res["count"] > 100
    path = config.EXPORTS_DIR / vid / "waveform.json"
    data = json.loads(path.read_text())
    assert len(data["peaks"]) == res["count"]
    assert max(data["peaks"]) <= 1.0 and min(data["peaks"]) >= 0.0
