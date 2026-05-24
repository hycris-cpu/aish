"""Skills — save and recall multi-step bash workflows.

Like Hermes skills: save a NL→command mapping as a named skill,
then invoke it by name later.

Storage: ~/.config/aish/skills.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

SKILLS_FILE = Path.home() / ".config" / "aish" / "skills.json"


def _load() -> list[dict]:
    if not SKILLS_FILE.exists():
        return []
    try:
        return json.loads(SKILLS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _save(skills: list[dict]):
    SKILLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SKILLS_FILE.write_text(json.dumps(skills, indent=2))


def save(name: str, nl_input: str, command: str, description: str = "") -> str:
    """Save a new skill."""
    skills = _load()
    name = name.strip().lower().replace(" ", "-")

    # Check for duplicate
    for s in skills:
        if s["name"] == name:
            s["nl_input"] = nl_input
            s["command"] = command
            s["description"] = description or s.get("description", "")
            s["updated"] = time.time()
            s["hits"] = s.get("hits", 0)
            _save(skills)
            return f"Updated skill '{name}'"

    skills.append({
        "name": name,
        "nl_input": nl_input,
        "command": command,
        "description": description,
        "created": time.time(),
        "updated": time.time(),
        "hits": 0,
    })
    _save(skills)
    return f"Saved skill '{name}'"


def list_skills() -> list[dict]:
    """Return all skills."""
    return sorted(_load(), key=lambda s: s.get("hits", 0), reverse=True)


def get(name: str) -> Optional[dict]:
    """Get a skill by name."""
    name = name.strip().lower().replace(" ", "-")
    for s in _load():
        if s["name"] == name:
            return s
    return None


def run(name: str) -> Optional[str]:
    """Run a skill by name. Returns the command to execute."""
    s = get(name)
    if not s:
        return None
    skills = _load()
    for sk in skills:
        if sk["name"] == name:
            sk["hits"] = sk.get("hits", 0) + 1
            _save(skills)
            break
    return s["command"]


def delete(name: str) -> bool:
    """Delete a skill by name."""
    name = name.strip().lower().replace(" ", "-")
    skills = _load()
    before = len(skills)
    skills = [s for s in skills if s["name"] != name]
    if len(skills) < before:
        _save(skills)
        return True
    return False


def match_nl(text: str) -> Optional[tuple[str, str]]:
    """Try to match natural language input to a skill.

    Returns (name, command) if match found.
    Uses word overlap > 60%.
    """
    skills = _load()
    if not skills:
        return None

    text_lower = text.strip().lower()
    words1 = set(text_lower.split())

    best = None
    best_score = 0.0

    for s in skills:
        nl = s.get("nl_input", "").lower()
        words2 = set(nl.split())
        if not words2:
            continue
        overlap = len(words1 & words2)
        score = overlap / max(len(words1), len(words2))
        if score > best_score:
            best_score = score
            best = s

    if best and best_score >= 0.6:
        return (best["name"], best["command"])
    return None
