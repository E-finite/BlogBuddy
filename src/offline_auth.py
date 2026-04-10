"""Offline authentication fallback using a local SQLite file."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from src import config

logger = logging.getLogger(__name__)

OFFLINE_USER_ID = -1
OFFLINE_USER_EMAIL = "offline@localhost"


def _db_path() -> Path:
    """Return the configured sqlite path for offline auth."""
    path = Path(config.OFFLINE_AUTH_DB_PATH)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    return path


def _connect() -> sqlite3.Connection:
    """Open a connection to the local offline auth sqlite database."""
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_offline_auth_store(bcrypt) -> bool:
    """Ensure sqlite store exists and contains one fallback account."""
    if not config.OFFLINE_AUTH_ENABLED:
        return False

    try:
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS offline_users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_admin INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                last_login TEXT NULL
            )
            """
        )

        cursor.execute("SELECT id FROM offline_users WHERE id = ?", (OFFLINE_USER_ID,))
        row = cursor.fetchone()
        if not row:
            password_hash = bcrypt.generate_password_hash(
                config.OFFLINE_AUTH_PASSWORD
            ).decode("utf-8")
            now = datetime.utcnow().isoformat(timespec="seconds")
            cursor.execute(
                """
                INSERT INTO offline_users
                    (id, username, email, password_hash, is_active, is_admin, created_at)
                VALUES
                    (?, ?, ?, ?, 1, 1, ?)
                """,
                (
                    OFFLINE_USER_ID,
                    config.OFFLINE_AUTH_USERNAME,
                    OFFLINE_USER_EMAIL,
                    password_hash,
                    now,
                ),
            )
            logger.info("Offline fallback user initialized at %s", _db_path())

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as exc:
        logger.warning("Offline auth store initialization failed: %s", exc)
        return False


def regenerate_offline_auth_store(bcrypt) -> bool:
    """Delete and recreate the offline sqlite auth store from scratch."""
    if not config.OFFLINE_AUTH_ENABLED:
        return False

    try:
        path = _db_path()
        if path.exists():
            path.unlink()
            logger.info("Removed offline auth store at %s", path)
    except Exception as exc:
        logger.warning("Could not remove offline auth store: %s", exc)

    return init_offline_auth_store(bcrypt)


def get_offline_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Return an offline user by username from sqlite store."""
    if not config.OFFLINE_AUTH_ENABLED:
        return None

    try:
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, username, email, password_hash, is_active, is_admin, created_at, last_login
            FROM offline_users
            WHERE username = ?
            """,
            (username,),
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(row) if row else None
    except Exception as exc:
        logger.warning("Offline auth lookup by username failed: %s", exc)
        return None


def get_offline_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Return an offline user by ID from sqlite store."""
    if not config.OFFLINE_AUTH_ENABLED:
        return None

    try:
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, username, email, password_hash, is_active, is_admin, created_at, last_login
            FROM offline_users
            WHERE id = ?
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(row) if row else None
    except Exception as exc:
        logger.warning("Offline auth lookup by id failed: %s", exc)
        return None


def update_offline_last_login(user_id: int) -> None:
    """Store last login timestamp for offline account."""
    if not config.OFFLINE_AUTH_ENABLED:
        return

    try:
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE offline_users SET last_login = ? WHERE id = ?",
            (datetime.utcnow().isoformat(timespec="seconds"), user_id),
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as exc:
        logger.warning("Offline auth last_login update failed: %s", exc)


def create_offline_user(username: str, email: str, password_hash: str, is_admin: bool = False) -> int:
    """Create a user in the offline sqlite auth store."""
    if not config.OFFLINE_AUTH_ENABLED:
        raise RuntimeError("Offline auth is disabled")

    conn = _connect()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat(timespec="seconds")
    cursor.execute(
        """
        INSERT INTO offline_users
            (username, email, password_hash, is_active, is_admin, created_at)
        VALUES
            (?, ?, ?, 1, ?, ?)
        """,
        (username, email, password_hash, int(is_admin), now),
    )
    user_id = int(cursor.lastrowid)
    conn.commit()
    cursor.close()
    conn.close()
    return user_id


def get_offline_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Return an offline user by email from sqlite store."""
    if not config.OFFLINE_AUTH_ENABLED:
        return None

    try:
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, username, email, password_hash, is_active, is_admin, created_at, last_login
            FROM offline_users
            WHERE email = ?
            """,
            (email,),
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(row) if row else None
    except Exception as exc:
        logger.warning("Offline auth lookup by email failed: %s", exc)
        return None


def update_offline_user_password_hash(user_id: int, password_hash: str) -> bool:
    """Update password hash for a user in sqlite fallback store."""
    if not config.OFFLINE_AUTH_ENABLED:
        return False

    try:
        conn = _connect()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE offline_users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )
        updated = cursor.rowcount > 0
        conn.commit()
        cursor.close()
        conn.close()
        return updated
    except Exception as exc:
        logger.warning("Offline auth password update failed: %s", exc)
        return False
