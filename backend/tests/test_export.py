import json

from backend import db
from worker.steps.export_edit import run_export_edit
from worker.steps.vertical import run_vertical_export
from worker.steps.export_batch import run_export_batch, _normalize_clips


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


def test_export_square_aspect():
    vid = _short_video_id()
    assert vid
    dur = db.get_video(vid)["duration_seconds"]
    db.save_edit(vid, json.dumps([{"id": "a", "sourceStart": 0.0, "sourceEnd": min(8.0, dur)}]))
    db.save_settings(vid, json.dumps({
        "aspect": "1:1", "framing": "auto", "crop_cx": 0.5,
        "caption": {"preset": "hormozi", "fontsize": 58, "color": "#ffd400", "position": "bottom"},
    }))
    res = run_vertical_export({"id": "sq01", "video_id": vid, "params_json": "{}"})
    assert res["width"] == 1080 and res["height"] == 1080
    assert res["aspect"] == "1:1"


def test_background_segmenter_shapes():
    import numpy as np
    from backend.segment import BackgroundSegmenter
    frame = (np.random.rand(640, 360, 3) * 255).astype("uint8")
    for mode in ("blur", "color"):
        seg = BackgroundSegmenter(mode=mode, color="#101218")
        out = seg.apply(frame)
        seg.close()
        assert out.shape == frame.shape and out.dtype == np.uint8


def test_export_vertical_with_background_blur():
    vid = _short_video_id()
    assert vid
    dur = db.get_video(vid)["duration_seconds"]
    db.save_edit(vid, json.dumps([{"id": "a", "sourceStart": 0.0, "sourceEnd": min(4.0, dur)}]))
    db.save_settings(vid, json.dumps({
        "aspect": "9:16", "framing": "auto", "crop_cx": 0.5,
        "background": {"mode": "blur", "color": "#10121a"},
        "caption": {"preset": "karaoke", "fontsize": 58, "color": "#ff8a3d", "position": "bottom"},
    }))
    res = run_vertical_export({"id": "bg01", "video_id": vid, "params_json": "{}"})
    assert res["width"] == 1080 and res["height"] == 1920
    assert res["duration"] > 0


def test_export_with_audio_enhancement():
    vid = _short_video_id()
    assert vid
    dur = db.get_video(vid)["duration_seconds"]
    db.save_edit(vid, json.dumps([{"id": "a", "sourceStart": 0.0, "sourceEnd": min(8.0, dur)}]))
    db.save_settings(vid, json.dumps({
        "aspect": "9:16", "framing": "auto", "crop_cx": 0.5, "enhance_audio": True,
        "caption": {"preset": "karaoke", "fontsize": 58, "color": "#ff8a3d", "position": "bottom"},
    }))
    res = run_export_edit({"id": "aud01", "video_id": vid, "params_json": "{}"})
    assert res["enhance_audio"] is True
    assert res["output_duration"] > 0


def test_normalize_clips_clamps_and_drops_slivers():
    clips = _normalize_clips(
        [
            {"start": -2.0, "end": 5.0},      # start clamped to 0
            {"start": 8.0, "end": 100.0},     # end clamped to duration
            {"start": 3.0, "end": 3.05},      # sliver -> dropped
            {"start": "x", "end": 4.0},       # malformed -> dropped
        ],
        duration=25.0,
    )
    assert len(clips) == 2
    assert clips[0] == {"start": 0.0, "end": 5.0, "reason": ""}
    assert clips[1]["end"] == 25.0


def test_export_batch_renders_multiple_shorts():
    vid = _short_video_id()
    assert vid
    dur = db.get_video(vid)["duration_seconds"]
    db.save_settings(vid, json.dumps({
        "aspect": "9:16", "framing": "auto", "crop_cx": 0.5,
        "caption": {"preset": "karaoke", "fontsize": 58, "color": "#ff8a3d", "position": "bottom"},
    }))
    third = round(dur / 3, 2)
    params = json.dumps({"clips": [
        {"start": 0.0, "end": third, "reason": "hook"},
        {"start": third, "end": 2 * third, "reason": "payoff"},
    ]})
    res = run_export_batch({"id": "batch01", "video_id": vid, "params_json": params})
    assert res["count"] == 2 and res["ok"] == 2
    assert {c["index"] for c in res["clips"]} == {0, 1}
    for c in res["clips"]:
        assert c["width"] == 1080 and c["height"] == 1920
        assert "error" not in c
        assert c["duration"] > 0
