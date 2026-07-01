import json

import pytest
from fastapi import HTTPException

from backend import db
from backend.app import get_settings, put_settings, SettingsBody, DEFAULT_SETTINGS


def _vid():
    with db.get_conn() as c:
        return c.execute("SELECT id FROM videos LIMIT 1").fetchone()["id"]


def test_default_when_none():
    vid = _vid()
    with db.get_conn() as c:
        c.execute("DELETE FROM settings WHERE video_id=?", (vid,))
    assert get_settings(vid)["aspect"] == DEFAULT_SETTINGS["aspect"]


def test_put_then_get_roundtrip():
    vid = _vid()
    body = SettingsBody(aspect="1:1", framing="manual", crop_cx=0.3,
                        caption={"preset": "hormozi", "fontsize": 64, "color": "#ffd400", "position": "center"})
    assert put_settings(vid, body) == {"ok": True}
    s = get_settings(vid)
    assert s["aspect"] == "1:1" and s["framing"] == "manual" and s["caption"]["preset"] == "hormozi"


def test_put_rejects_bad_aspect():
    vid = _vid()
    body = SettingsBody(aspect="bogus", framing="auto", crop_cx=0.5,
                        caption={"preset": "karaoke"})
    with pytest.raises(HTTPException):
        put_settings(vid, body)


def test_put_rejects_bad_preset():
    vid = _vid()
    body = SettingsBody(aspect="9:16", framing="auto", crop_cx=0.5,
                        caption={"preset": "nope"})
    with pytest.raises(HTTPException):
        put_settings(vid, body)


def test_put_rejects_bad_caption_language():
    vid = _vid()
    body = SettingsBody(aspect="9:16", framing="auto", crop_cx=0.5,
                        caption={"preset": "karaoke", "language": "xx"})
    with pytest.raises(HTTPException):
        put_settings(vid, body)


def test_put_accepts_known_caption_language():
    vid = _vid()
    body = SettingsBody(aspect="9:16", framing="auto", crop_cx=0.5,
                        caption={"preset": "karaoke", "language": "es"})
    assert put_settings(vid, body) == {"ok": True}
    assert get_settings(vid)["caption"]["language"] == "es"
