"""SQLite durable storage and authentication models for Dossier."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


DEFAULT_DB_PATH = Path(os.getenv("DOSSIER_DB_PATH", "dossier.db")).resolve()


def get_db_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open or create a SQLite database connection with row access."""
    target_path = Path(db_path) if db_path else DEFAULT_DB_PATH
    conn = sqlite3.connect(str(target_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | str | None = None) -> None:
    """Initialize database tables for authentication and research history."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS research_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    question TEXT NOT NULL,
                    output_format TEXT NOT NULL,
                    response_id TEXT,
                    provider TEXT NOT NULL,
                    model TEXT,
                    result TEXT NOT NULL,
                    sources TEXT,
                    follow_up_of INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
                )
                """
            )
    finally:
        conn.close()


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Hash a password securely using PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()
    return hashed, salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Verify if the given plaintext password matches the stored hash."""
    expected_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(expected_hash, password_hash)


@dataclass(frozen=True)
class User:
    id: int
    email: str
    created_at: str


def register_user(email: str, password: str, db_path: Path | str | None = None) -> User:
    """Register a new user account."""
    clean_email = email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise ValueError("A valid email address is required.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters long.")

    pw_hash, salt = hash_password(password)
    now = datetime.now(timezone.utc).isoformat()

    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO users (email, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                (clean_email, pw_hash, salt, now),
            )
            user_id = cursor.lastrowid
            return User(id=user_id, email=clean_email, created_at=now)
    except sqlite3.IntegrityError:
        raise ValueError("An account with this email already exists.")
    finally:
        conn.close()


def authenticate_user(email: str, password: str, db_path: Path | str | None = None) -> tuple[User, str]:
    """Verify user credentials and create a session token."""
    clean_email = email.strip().lower()
    conn = get_db_connection(db_path)
    try:
        row = conn.execute(
            "SELECT id, email, password_hash, salt, created_at FROM users WHERE email = ?",
            (clean_email,),
        ).fetchone()

        if not row or not verify_password(password, row["password_hash"], row["salt"]):
            raise ValueError("Invalid email or password.")

        token = secrets.token_hex(32)
        now = datetime.now(timezone.utc).isoformat()
        with conn:
            conn.execute(
                "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
                (token, row["id"], now),
            )

        return User(id=row["id"], email=row["email"], created_at=row["created_at"]), token
    finally:
        conn.close()


def get_user_by_token(token: str, db_path: Path | str | None = None) -> Optional[User]:
    """Retrieve the user corresponding to a session token."""
    if not token:
        return None
    conn = get_db_connection(db_path)
    try:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.created_at
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ?
            """,
            (token.strip(),),
        ).fetchone()
        if not row:
            return None
        return User(id=row["id"], email=row["email"], created_at=row["created_at"])
    finally:
        conn.close()


def delete_session(token: str, db_path: Path | str | None = None) -> None:
    """Invalidate an active session token."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token.strip(),))
    finally:
        conn.close()
