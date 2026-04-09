"""
utils/audit.py - Local SQLite audit log.

Every action taken through the dashboard is recorded here:
timestamp, admin email, action, object type/id/name, success, API tracking ID.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "audit.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT    NOT NULL,
                admin_email     TEXT    NOT NULL DEFAULT '',
                action          TEXT    NOT NULL,
                object_type     TEXT    NOT NULL DEFAULT '',
                object_id       TEXT    NOT NULL DEFAULT '',
                object_name     TEXT    NOT NULL DEFAULT '',
                details         TEXT    NOT NULL DEFAULT '',
                success         INTEGER NOT NULL DEFAULT 1,
                error_message   TEXT    NOT NULL DEFAULT '',
                tracking_id     TEXT    NOT NULL DEFAULT ''
            )
        """)
        conn.commit()


_ensure_table()


def log(
    action:       str,
    object_type:  str  = "",
    object_id:    str  = "",
    object_name:  str  = "",
    details:      dict = None,
    success:      bool = True,
    error_message: str = "",
    tracking_id:  str  = "",
    admin_email:  str  = "",
) -> None:
    """Write one entry to the audit log."""
    with _connect() as conn:
        conn.execute(
            """INSERT INTO audit_log
               (timestamp, admin_email, action, object_type, object_id,
                object_name, details, success, error_message, tracking_id)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                datetime.utcnow().isoformat(timespec="seconds") + "Z",
                admin_email,
                action,
                object_type,
                object_id,
                object_name,
                json.dumps(details or {}),
                1 if success else 0,
                error_message,
                tracking_id,
            ),
        )
        conn.commit()


def get_entries(
    limit:       int  = 200,
    action:      str  = None,
    object_type: str  = None,
    success:     bool = None,
) -> list[dict]:
    """Retrieve recent audit log entries as a list of dicts."""
    where_clauses = []
    params: list  = []

    if action:
        where_clauses.append("action = ?")
        params.append(action)
    if object_type:
        where_clauses.append("object_type = ?")
        params.append(object_type)
    if success is not None:
        where_clauses.append("success = ?")
        params.append(1 if success else 0)

    where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    params.append(limit)

    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM audit_log {where} ORDER BY id DESC LIMIT ?",
            params,
        ).fetchall()

    return [dict(r) for r in rows]


def clear_all() -> None:
    """Delete all audit log entries (use with caution)."""
    with _connect() as conn:
        conn.execute("DELETE FROM audit_log")
        conn.commit()
