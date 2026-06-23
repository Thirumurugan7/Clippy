import uuid

import pytest

from backend import auth, db


def _email():
    return f"t_{uuid.uuid4().hex[:8]}@example.com"


def test_hash_verify():
    salt, h = auth.hash_password("hunter2")
    assert auth.verify_password("hunter2", salt, h)
    assert not auth.verify_password("wrong", salt, h)


def test_register_and_authenticate():
    email = _email()
    uid = auth.register(email, "secret123")
    assert auth.authenticate(email, "secret123") == uid
    assert auth.authenticate(email, "nope") is None


def test_register_duplicate_raises():
    email = _email()
    auth.register(email, "secret123")
    with pytest.raises(ValueError):
        auth.register(email, "secret123")


def test_register_validates():
    with pytest.raises(ValueError):
        auth.register("notanemail", "secret123")
    with pytest.raises(ValueError):
        auth.register(_email(), "short")


def test_session_roundtrip():
    uid = auth.register(_email(), "secret123")
    token = auth.new_session(uid)
    u = auth.user_for_token(token)
    assert u is not None and u["id"] == uid
    db.delete_session(token)
    assert auth.user_for_token(token) is None
