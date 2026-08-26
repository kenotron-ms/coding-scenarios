"""
storage.py — SQLite persistence layer for the URL shortener service.

A-1 Resolution (idempotent/dedupe): If POST /api/shorten receives a URL that
already exists, return the existing code (201 with existing code, clicks preserved).

A-3 Resolution (store verbatim): Store the URL exactly as submitted; Location
header is byte-identical to the stored URL.
"""

import sqlite3
import threading
from typing import Optional

# Module-level lock for write operations when using shared connections
_write_lock = threading.Lock()


def _get_connection(db_path: str) -> sqlite3.Connection:
    """Create a new SQLite connection with WAL mode and row factory."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db(db_path: str) -> None:
    """
    Initialize the database schema.

    Creates the links table if it does not exist and enables WAL mode.
    """
    conn = _get_connection(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS links (
                code       TEXT PRIMARY KEY,
                url        TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                clicks     INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return {
        "code": row["code"],
        "url": row["url"],
        "clicks": row["clicks"],
        "created_at": row["created_at"],
    }


def create_link(db_path: str, code: str, url: str) -> dict:
    """
    INSERT a new row into the links table.

    Args:
        db_path: Path to the SQLite database file.
        code: The short code (primary key).
        url: The destination URL to store verbatim (A-3).

    Returns:
        A dict with {code, url, clicks, created_at}.

    Raises:
        sqlite3.IntegrityError: If the code already exists (UNIQUE constraint).
    """
    conn = _get_connection(db_path)
    try:
        with _write_lock:
            conn.execute(
                "INSERT INTO links (code, url) VALUES (?, ?)",
                (code, url),
            )
            conn.commit()
            row = conn.execute(
                "SELECT code, url, clicks, created_at FROM links WHERE code = ?",
                (code,),
            ).fetchone()
            return _row_to_dict(row)
    finally:
        conn.close()


def get_link(db_path: str, code: str) -> Optional[dict]:
    """
    SELECT a link by code.

    Args:
        db_path: Path to the SQLite database file.
        code: The short code to look up.

    Returns:
        A dict with {code, url, clicks, created_at}, or None if not found.
    """
    conn = _get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT code, url, clicks, created_at FROM links WHERE code = ?",
            (code,),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def increment_clicks(db_path: str, code: str) -> Optional[dict]:
    """
    Atomically increment the click counter for a link and return the updated row.

    The DB owns the arithmetic (clicks = clicks + 1) — no Python +1.
    This is a single transaction.

    Args:
        db_path: Path to the SQLite database file.
        code: The short code to increment.

    Returns:
        A dict with {code, url, clicks, created_at} after increment, or None if not found.
    """
    conn = _get_connection(db_path)
    try:
        with _write_lock:
            conn.execute(
                "UPDATE links SET clicks = clicks + 1 WHERE code = ?",
                (code,),
            )
            conn.commit()
            row = conn.execute(
                "SELECT code, url, clicks, created_at FROM links WHERE code = ?",
                (code,),
            ).fetchone()
            return _row_to_dict(row) if row else None
    finally:
        conn.close()


def delete_link(db_path: str, code: str) -> bool:
    """
    DELETE a link by code.

    Args:
        db_path: Path to the SQLite database file.
        code: The short code to delete.

    Returns:
        True if a row was deleted, False otherwise.
    """
    conn = _get_connection(db_path)
    try:
        with _write_lock:
            cursor = conn.execute(
                "DELETE FROM links WHERE code = ?",
                (code,),
            )
            conn.commit()
            return cursor.rowcount > 0
    finally:
        conn.close()


def health_check(db_path: str) -> bool:
    """
    Execute a trivial SELECT to confirm the DB is reachable.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        True if the database is reachable.
    """
    conn = _get_connection(db_path)
    try:
        conn.execute("SELECT 1 FROM links LIMIT 1")
        return True
    except Exception:
        return False
    finally:
        conn.close()


def find_by_url(db_path: str, url: str) -> Optional[dict]:
    """
    SELECT a link by its destination URL (for A-1 idempotency dedupe).

    Args:
        db_path: Path to the SQLite database file.
        url: The destination URL to search for.

    Returns:
        A dict with {code, url, clicks, created_at} if found, or None.
    """
    conn = _get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT code, url, clicks, created_at FROM links WHERE url = ?",
            (url,),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()
