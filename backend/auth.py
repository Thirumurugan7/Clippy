"""Authentication: email + password with PBKDF2 hashing (stdlib, no deps) and
opaque session tokens stored in SQLite. Multi-user with per-user isolation —
every video is owned by a user and access is checked against the session.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import uuid

from backend import db

_ITERATIONS = 200_000


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS).hex()
    return salt, h


def verify_password(password: str, salt: str, expected: str) -> bool:
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS).hex()
    return secrets.compare_digest(h, expected)


def register(email: str, password: str) -> str:
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError("a valid email is required")
    if len(password) < 6:
        raise ValueError("password must be at least 6 characters")
    if db.get_user_by_email(email):
        raise ValueError("email already registered")
    salt, h = hash_password(password)
    user_id = uuid.uuid4().hex
    db.create_user_row(user_id, email, salt, h)
    return user_id


def authenticate(email: str, password: str) -> str | None:
    user = db.get_user_by_email(email.strip().lower())
    if user is None:
        return None
    if verify_password(password, user["pw_salt"], user["pw_hash"]):
        return user["id"]
    return None


def new_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    db.create_session_row(token, user_id)
    return token


def user_for_token(token: str | None):
    if not token:
        return None
    return db.get_session_user(token)


def ensure_admin() -> None:
    """Ensure an admin account exists and that any pre-auth (ownerless) videos are
    adopted by it. Runs every startup but is idempotent: it only creates the admin
    when missing-and-needed, and only adopts orphan videos (which exist once,
    before migration)."""
    email = os.environ.get("CLIPPY_ADMIN_EMAIL", "admin@clippy.local").strip().lower()
    password = os.environ.get("CLIPPY_ADMIN_PASSWORD", "clippy-admin")
    admin = db.get_user_by_email(email)
    if admin is not None:
        admin_id = admin["id"]
    elif db.count_users() == 0 or db.count_orphan_videos() > 0:
        admin_id = register(email, password)
        print(f"[auth] created admin '{email}' (password: {password})")
    else:
        return  # real users exist and nothing orphaned; no admin needed
    adopted = db.assign_orphan_videos(admin_id)
    if adopted:
        print(f"[auth] adopted {adopted} pre-auth video(s) under '{email}'")
