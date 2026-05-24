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

"""Security scanner — detects dangerous command patterns."""

from __future__ import annotations

import re

# Patterns that require DANGEROUS: prefix
DANGEROUS_PATTERNS = [
    re.compile(r'\brm\s+-rf\s+/'),
    re.compile(r'\brm\s+-rf\s+\~'),
    re.compile(r'\brm\s+-rf\s+\$'),
    re.compile(r'\brm\s+-rf\s+\*'),
    re.compile(r'\bmkfs\.'),
    re.compile(r'\bdd\s+if='),
    re.compile(r'\bsudo\s+poweroff'),
    re.compile(r'\bsudo\s+reboot'),
    re.compile(r'\bsudo\s+shutdown'),
    re.compile(r'\bchmod\s+-R\s+777'),
    re.compile(r'\bchmod\s+777'),
    re.compile(r'\b>\s+/dev/sd'),
    re.compile(r'\bkill\s+-9\s+-1'),
    re.compile(r'\bsudo\s+rm\s+-rf'),
]

# Patterns that should always raise a warning
WARNING_PATTERNS = [
    re.compile(r'\brm\s+-rf'),
    re.compile(r'\bsudo\s+rm'),
    re.compile(r'\bdocker\s+rm\s+'),
    re.compile(r'\bdocker\s+stop\s+'),
    re.compile(r'\bkill\s+-9\b'),
    re.compile(r'\b>\s+/dev/'),
    re.compile(r'\bsudo\s+dd'),
    re.compile(r'\bdd\s+'),
    re.compile(r'\b:(){ :\|:&\};:'),
    re.compile(r'\bwget\s+.*\|\s*bash'),
    re.compile(r'\bcurl\s+.*\|\s*bash'),
    re.compile(r'\bsudo\s+chmod\s+777'),
    re.compile(r'\bsudo\s+mkfs\.'),
    re.compile(r'\bsudo\s+fdisk'),
    re.compile(r'\bsudo\s+dd'),
    re.compile(r'\| sudo'),
    re.compile(r'>\s+/etc/'),
    re.compile(r'\brm\s+.*/\s*$'),
]


def scan(command: str) -> tuple[bool, bool, str]:
    """Scan a command for dangerous patterns.

    Returns:
        (is_dangerous, has_warning, message)
    """
    for pattern in DANGEROUS_PATTERNS:
        m = pattern.search(command)
        if m:
            return True, True, f"DANGEROUS: command matches {m.group()[:40]}"

    warnings = []
    for pattern in WARNING_PATTERNS:
        m = pattern.search(command)
        if m:
            warnings.append(m.group()[:40])

    if warnings:
        return False, True, "Warning: " + "; ".join(warnings)

    return False, False, ""
