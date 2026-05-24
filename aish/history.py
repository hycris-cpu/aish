"""History — searchable command history.

Stores every command run through Aish, with timestamp, exit code,
and working directory. Searchable by keyword.

Storage: ~/.config/aish/history.db (SQLite)
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

HISTORY_DIR = Path.home() / ".config" / "aish"
HISTORY_DB = HISTORY_DIR / "history.db"


def _get_db() -> sqlite3.Connection:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(HISTORY_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            nl_input TEXT,
            command TEXT NOT NULL,
            exit_code INTEGER,
            cwd TEXT,
            duration REAL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_history_command ON history(command)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history(timestamp)")
    conn.commit()
    return conn


def record(nl_input: str, command: str, exit_code: int = 0, duration: float = 0):
    """Record a command in history."""
    try:
        conn = _get_db()
        conn.execute(
            "INSERT INTO history (timestamp, nl_input, command, exit_code, cwd, duration) VALUES (?, ?, ?, ?, ?, ?)",
            (time.time(), nl_input, command, exit_code, os.getcwd(), duration),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def search(query: str, limit: int = 20) -> list[dict]:
    """Search history by keyword."""
    try:
        conn = _get_db()
        rows = conn.execute(
            """SELECT timestamp, nl_input, command, exit_code, cwd, duration
               FROM history
               WHERE command LIKE ? OR nl_input LIKE ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        conn.close()
        return [
            {
                "time": r[0],
                "nl_input": r[1],
                "command": r[2],
                "exit_code": r[3],
                "cwd": r[4],
                "duration": r[5],
            }
            for r in rows
        ]
    except Exception:
        return []


def recent(limit: int = 20) -> list[dict]:
    """Get recent history."""
    try:
        conn = _get_db()
        rows = conn.execute(
            """SELECT timestamp, nl_input, command, exit_code, cwd, duration
               FROM history
               ORDER BY timestamp DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        conn.close()
        return [
            {
                "time": r[0],
                "nl_input": r[1],
                "command": r[2],
                "exit_code": r[3],
                "cwd": r[4],
                "duration": r[5],
            }
            for r in rows
        ]
    except Exception:
        return []


def clear():
    """Clear all history."""
    try:
        conn = _get_db()
        conn.execute("DELETE FROM history")
        conn.commit()
        conn.close()
    except Exception:
        pass


def stats() -> dict:
    """Get history statistics."""
    try:
        conn = _get_db()
        total = conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]
        unique_commands = conn.execute("SELECT COUNT(DISTINCT command) FROM history").fetchone()[0]
        last = conn.execute(
            "SELECT command, timestamp FROM history ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return {
            "total": total,
            "unique_commands": unique_commands,
            "last_command": last[0] if last else "",
            "last_time": last[1] if last else 0,
        }
    except Exception:
        return {"total": 0, "unique_commands": 0}
