"""Memory — user preferences that influence command generation.

Like Hermes memory: durable facts that persist across sessions.
Stored in ~/.config/aish/memory.json and injected into the system prompt.

Use cases:
  "aish remember use dnf not apt"
  "aish remember my shell is zsh"
  "aish remember prefer ip over ifconfig"
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

MEMORY_FILE = Path.home() / ".config" / "aish" / "memory.json"


def _load() -> list[dict]:
    if not MEMORY_FILE.exists():
        return []
    try:
        return json.loads(MEMORY_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _save(memories: list[dict]):
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE.write_text(json.dumps(memories, indent=2))


def add(fact: str):
    """Save a memory/fact about user preferences."""
    memories = _load()
    # Avoid duplicates
    for m in memories:
        if m["fact"].lower().strip() == fact.lower().strip():
            m["updated"] = time.time()
            _save(memories)
            return
    memories.append({
        "fact": fact.strip(),
        "created": time.time(),
        "updated": time.time(),
    })
    # Cap at 50 memories
    if len(memories) > 50:
        memories.sort(key=lambda m: m.get("updated", 0))
        memories = memories[-50:]
    _save(memories)


def remove(fact: str) -> bool:
    """Remove a memory."""
    memories = _load()
    before = len(memories)
    memories = [m for m in memories if m["fact"].lower().strip() != fact.lower().strip()]
    if len(memories) < before:
        _save(memories)
        return True
    return False


def list_all() -> list[dict]:
    """Return all memories."""
    return _load()


def clear():
    """Clear all memories."""
    _save([])


def format_prompt() -> str:
    """Format memories as a prompt suffix."""
    memories = _load()
    if not memories:
        return ""
    facts = "\n".join(f"- {m['fact']}" for m in memories)
    return f"\n\nUser preferences:\n{facts}"
