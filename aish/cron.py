"""Cron — scheduled task execution for Aish.

Supports one-shot and recurring schedules.
Uses systemd --user timers on Linux for actual scheduling,
or a simple JSON store for manual management.

Storage: ~/.config/aish/cron.json
"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

CRON_FILE = Path.home() / ".config" / "aish" / "cron.json"


def _load() -> list[dict]:
    if not CRON_FILE.exists():
        return []
    try:
        return json.loads(CRON_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _save(jobs: list[dict]):
    CRON_FILE.parent.mkdir(parents=True, exist_ok=True)
    CRON_FILE.write_text(json.dumps(jobs, indent=2))


def _parse_schedule(schedule: str) -> tuple[str, str]:
    """Parse a human-friendly schedule into systemd format.

    Returns (systemd_calendar, description).
    """
    s = schedule.strip().lower()

    if s in ("hourly", "every hour", "1h", "1 hour"):
        return "hourly", "Every hour"
    elif s in ("daily", "every day", "1d", "1 day"):
        return "daily", "Every day"
    elif s in ("weekly", "every week", "1 week"):
        return "weekly", "Every week"
    elif s in ("monthly", "every month"):
        return "monthly", "Every month"
    elif s.startswith("every "):
        parts = s[6:].split()
        if parts:
            num = int(parts[0]) if parts[0].isdigit() else 1
            unit = parts[1] if len(parts) > 1 else "hour"
            if unit.startswith("h"):
                return f"0/1:0:0", f"Every {num} hour(s)"
            elif unit.startswith("m"):
                return f"0:0/1:0", f"Every {num} minute(s)"
            elif unit.startswith("d"):
                return f"daily", f"Every {num} day(s)"
    return s, s


def add(name: str, command: str, schedule: str, description: str = "") -> str:
    """Add a scheduled job."""
    jobs = _load()

    # Check duplicate name
    for j in jobs:
        if j["name"] == name:
            return f"Job '{name}' already exists"

    cal, desc = _parse_schedule(schedule)
    now = time.time()

    jobs.append({
        "name": name,
        "command": command,
        "schedule": schedule,
        "calendar": cal,
        "description": description or desc,
        "created": now,
        "last_run": 0,
        "next_run": now + _parse_interval_seconds(schedule),
        "enabled": True,
        "runs": 0,
    })
    _save(jobs)
    return f"Scheduled '{name}' ({desc})"


def _parse_interval_seconds(schedule: str) -> int:
    """Parse a schedule into seconds."""
    s = schedule.strip().lower()
    if s in ("hourly", "every hour", "1h"):
        return 3600
    elif s in ("daily", "every day", "1d"):
        return 86400
    elif s in ("weekly", "every week"):
        return 604800
    elif s in ("monthly", "every month"):
        return 2592000
    elif s.startswith("every "):
        parts = s[6:].split()
        num = int(parts[0]) if parts[0].isdigit() else 1
        unit = parts[1] if len(parts) > 1 else "h"
        if unit.startswith("h"):
            return num * 3600
        elif unit.startswith("m"):
            return num * 60
        elif unit.startswith("d"):
            return num * 86400
    return 86400  # default daily


def list_jobs() -> list[dict]:
    """Return all scheduled jobs."""
    return sorted(_load(), key=lambda j: j.get("next_run", 0))


def remove(name: str) -> bool:
    """Remove a scheduled job."""
    jobs = _load()
    before = len(jobs)
    jobs = [j for j in jobs if j["name"] != name]
    if len(jobs) < before:
        _save(jobs)
        return True
    return False


def get_due() -> list[dict]:
    """Get all jobs that are due to run."""
    now = time.time()
    due = []
    jobs = _load()
    for j in jobs:
        if j.get("enabled", True) and j.get("next_run", 0) <= now:
            due.append(j)
    return due


def mark_run(name: str):
    """Mark a job as having run."""
    jobs = _load()
    now = time.time()
    for j in jobs:
        if j["name"] == name:
            j["last_run"] = now
            j["runs"] = j.get("runs", 0) + 1
            interval = _parse_interval_seconds(j.get("schedule", "daily"))
            j["next_run"] = now + interval
            _save(jobs)
            break
