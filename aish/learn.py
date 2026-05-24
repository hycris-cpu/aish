# Copyright (C) 2026 hycris-cpu
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Self-learning module for Aish — remembers NL→command patterns.

When guardrail retry succeeds, the query→command mapping is saved.
Next time the same or similar query is made, the learned pattern
is used directly — no LLM call needed.

Storage: ~/.config/aish/learned.json
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

LEARNED_FILE = Path.home() / ".config" / "aish" / "learned.json"


def _load() -> list[dict]:
    """Load learned patterns."""
    if not LEARNED_FILE.exists():
        return []
    try:
        return json.loads(LEARNED_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _save(patterns: list[dict]):
    """Save learned patterns."""
    LEARNED_FILE.parent.mkdir(parents=True, exist_ok=True)
    LEARNED_FILE.write_text(json.dumps(patterns, indent=2))


def learn(text: str, command: str):
    """Save a new NL→command mapping.

    Only saves if significantly different from existing patterns
    to avoid bloat.
    """
    patterns = _load()
    text_lower = text.strip().lower()

    # Don't save duplicates (same or very similar query)
    for p in patterns:
        existing = p["input"].lower()
        # Simple similarity: shared words ratio
        words1 = set(text_lower.split())
        words2 = set(existing.split())
        overlap = len(words1 & words2)
        if overlap >= min(len(words1), len(words2)) * 0.7:
            # Update existing if command differs
            if p["command"] != command:
                p["command"] = command
                p["updated"] = time.time()
                _save(patterns)
            return

    # Add new pattern
    patterns.append({
        "input": text.strip(),
        "command": command,
        "created": time.time(),
        "updated": time.time(),
        "hits": 0,
    })

    # Cap at 200 patterns to prevent bloat
    if len(patterns) > 200:
        patterns.sort(key=lambda x: x.get("hits", 0))
        patterns = patterns[-200:]

    _save(patterns)


def recall(text: str) -> Optional[str]:
    """Try to recall a learned command for this input.

    Returns the command if a match is found, None otherwise.
    Uses fuzzy matching: shared word ratio > 70%.
    """
    patterns = _load()
    if not patterns:
        return None

    text_lower = text.strip().lower()
    words1 = set(text_lower.split())

    best_match = None
    best_score = 0.0
    best_idx = -1

    for i, p in enumerate(patterns):
        existing = p.get("input", "").lower()
        words2 = set(existing.split())
        if not words2:
            continue

        overlap = len(words1 & words2)
        score = overlap / max(len(words1), len(words2))

        if score > best_score:
            best_score = score
            best_match = p
            best_idx = i

    if best_match is not None and best_score >= 0.7:
        # Increment hit counter
        best_match["hits"] = best_match.get("hits", 0) + 1
        patterns[best_idx] = best_match
        _save(patterns)
        return best_match["command"]

    return None


def list_learned() -> list[dict]:
    """Return all learned patterns for display."""
    return _load()


def forget(input_text: str = None):
    """Forget a specific pattern or all patterns."""
    patterns = _load()
    if input_text:
        patterns = [p for p in patterns if p["input"] != input_text]
    else:
        patterns = []
    _save(patterns)


def stats() -> dict:
    """Return statistics about learned patterns."""
    patterns = _load()
    return {
        "total": len(patterns),
        "total_hits": sum(p.get("hits", 0) for p in patterns),
        "top": sorted(patterns, key=lambda x: x.get("hits", 0), reverse=True)[:5],
    }
