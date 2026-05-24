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

"""Tool registry and dispatch for aish.

Each tool module exports:
  name: str  — identifier for the tool
  build(kwargs: dict) -> str  — returns bash command string

Tools can prefix with DANGEROUS: to force extra confirmation.
"""

from __future__ import annotations

from typing import Optional

import aish.tools.files as files
import aish.tools.system as system
import aish.tools.network as network
import aish.tools.dangerous as dangerous
import aish.tools.misc as misc

# Registry: all known tools
TOOLS = {
    "files": files,
    "system": system,
    "network": network,
    "dangerous": dangerous,
    "misc": misc,
}


def dispatch(tool_name: str, action: str, params: dict) -> tuple[Optional[str], Optional[str], bool]:
    """Dispatch to a tool builder.

    Returns:
        (command, error, is_dangerous) — error takes priority over command
    """
    tool = TOOLS.get(tool_name)
    if not tool:
        return None, f"unknown tool: {tool_name}", False

    try:
        cmd = tool.build(action, params)
        if cmd is None:
            return None, f"unknown action '{action}' for tool '{tool_name}'", False
        is_dangerous = cmd.startswith("DANGEROUS:")
        return cmd, None, is_dangerous
    except Exception as e:
        return None, str(e), False


def list_actions() -> str:
    """Return a formatted summary of all tool actions for the system prompt."""
    lines = []
    for name in sorted(TOOLS):
        tool = TOOLS[name]
        actions = getattr(tool, "ACTIONS", {})
        for action, desc in sorted(actions.items()):
            example = tool.example(action)
            if example:
                lines.append(f"  {name}.{action:30s} # {desc:40s} ex: {example}")
    return "\n".join(lines)
