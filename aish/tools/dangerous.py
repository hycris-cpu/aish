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

"""Dangerous operations — must prefix with DANGEROUS:"""

from __future__ import annotations

ACTIONS = {
    "delete_recursive": "recursively delete a directory (DANGEROUS)",
    "format_disk": "format a disk (DANGEROUS)",
    "dd_zero": "write zeros to device (DANGEROUS)",
    "shutdown": "shutdown the system (DANGEROUS)",
    "reboot": "reboot the system (DANGEROUS)",
    "chmod_777_recursive": "777 permissions recursively (DANGEROUS)",
}


def _quote(s: str) -> str:
    return f'"{s}"' if " " in s else s


def build(action: str, kwargs: dict) -> str | None:
    if action == "delete_recursive":
        path = kwargs.get("path", kwargs.get("dir", kwargs.get("name", "")))
        if path:
            return f"DANGEROUS: rm -rf {_quote(path)}"
        return None
    elif action == "format_disk":
        device = kwargs.get("device", kwargs.get("disk", kwargs.get("path", "")))
        fstype = kwargs.get("fstype", kwargs.get("type", "ext4"))
        if device:
            return f"DANGEROUS: sudo mkfs.{fstype} {_quote(device)}"
        return None
    elif action == "dd_zero":
        device = kwargs.get("device", kwargs.get("of", ""))
        infile = kwargs.get("infile", kwargs.get("if", "/dev/zero"))
        if device:
            return f"DANGEROUS: sudo dd if={infile} of={_quote(device)}"
        return None
    elif action == "shutdown":
        return "DANGEROUS: sudo poweroff"
    elif action == "reboot":
        return "DANGEROUS: sudo reboot"
    elif action == "chmod_777_recursive":
        path = kwargs.get("path", kwargs.get("dir", kwargs.get("name", "")))
        if path:
            return f"DANGEROUS: sudo chmod -R 777 {_quote(path)}"
        return None

    return None


def example(action: str) -> str | None:
    examples = {
        "delete_recursive": "delete directory recursively → DANGEROUS: rm -rf mydir",
        "format_disk": "format sdb as ext4 → DANGEROUS: sudo mkfs.ext4 /dev/sdb",
        "shutdown": "shutdown → DANGEROUS: sudo poweroff",
        "reboot": "reboot → DANGEROUS: sudo reboot",
    }
    return examples.get(action)
