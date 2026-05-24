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

"""File operations tool — ls, cp, mv, rm, mkdir, touch, cat, head, tail, wc, find, grep, sed, sort."""

from __future__ import annotations

ACTIONS = {
    "list": "list files in directory",
    "list_details": "list files with details (ls -la)",
    "copy": "copy file to destination",
    "move": "move file to destination",
    "rename": "rename file",
    "delete": "delete file",
    "delete_force": "force delete file",
    "create_dir": "create a directory",
    "create_dirs": "create nested directories (mkdir -p)",
    "create_file": "create empty file (touch)",
    "show": "show file contents (cat)",
    "head": "show first N lines",
    "tail": "show last N lines",
    "tail_follow": "follow file for new lines",
    "count": "count lines in file (wc -l)",
    "sort": "sort file alphabetically",
    "find_name": "find files by name pattern",
    "find_size": "find files by size",
    "find_time": "find files by modification time",
    "find_empty": "find empty directories",
    "grep": "search for pattern in files",
    "grep_insensitive": "case-insensitive search",
    "sed_replace": "replace text in file",
    "sort_unique": "show unique sorted lines",
}


def _quote(s: str) -> str:
    """Return shell-safe quoted string."""
    return f'"{s}"' if " " in s else s


def build(action: str, kwargs: dict) -> str | None:
    """Build a file operation command."""

    if action == "list":
        path = kwargs.get("path", ".")
        return f"ls {path}"
    elif action == "list_details":
        path = kwargs.get("path", ".")
        return f"ls -la {path}"
    elif action == "copy":
        src = kwargs.get("src", kwargs.get("file", ""))
        dst = kwargs.get("dst", kwargs.get("dest", kwargs.get("to", "")))
        if src and dst:
            return f"cp {_quote(src)} {_quote(dst)}"
        return None
    elif action == "move":
        src = kwargs.get("src", kwargs.get("file", ""))
        dst = kwargs.get("dst", kwargs.get("dest", kwargs.get("to", "")))
        if src and dst:
            return f"mv {_quote(src)} {_quote(dst)}"
        return None
    elif action == "rename":
        old = kwargs.get("old", kwargs.get("from", kwargs.get("src", "")))
        new = kwargs.get("new", kwargs.get("to", kwargs.get("dst", "")))
        if old and new:
            return f"mv {_quote(old)} {_quote(new)}"
        return None
    elif action == "delete":
        path = kwargs.get("path", kwargs.get("file", ""))
        if path:
            return f"rm {_quote(path)}"
        return None
    elif action == "delete_force":
        path = kwargs.get("path", kwargs.get("file", ""))
        if path:
            return f"rm -f {_quote(path)}"
        return None
    elif action == "create_dir":
        path = kwargs.get("path", kwargs.get("name", kwargs.get("dir", "")))
        if path:
            return f"mkdir {_quote(path)}"
        return None
    elif action == "create_dirs":
        path = kwargs.get("path", kwargs.get("name", kwargs.get("dir", "")))
        if path:
            return f"mkdir -p {_quote(path)}"
        return None
    elif action == "create_file":
        path = kwargs.get("path", kwargs.get("name", kwargs.get("file", "")))
        if path:
            return f"touch {_quote(path)}"
        return None
    elif action == "show":
        path = kwargs.get("path", kwargs.get("file", ""))
        if path:
            return f"cat {_quote(path)}"
        return None
    elif action == "head":
        path = kwargs.get("path", kwargs.get("file", ""))
        n = kwargs.get("n", kwargs.get("lines", "10"))
        return f"head -n {n} {_quote(path)}" if path else None
    elif action == "tail":
        path = kwargs.get("path", kwargs.get("file", ""))
        n = kwargs.get("n", kwargs.get("lines", "20"))
        return f"tail -n {n} {_quote(path)}" if path else None
    elif action == "tail_follow":
        path = kwargs.get("path", kwargs.get("file", ""))
        return f"tail -f {_quote(path)}" if path else None
    elif action == "count":
        path = kwargs.get("path", kwargs.get("file", ""))
        return f"wc -l {_quote(path)}" if path else None
    elif action == "sort":
        path = kwargs.get("path", kwargs.get("file", ""))
        return f"sort {_quote(path)}" if path else None
    elif action == "sort_unique":
        path = kwargs.get("path", kwargs.get("file", ""))
        return f"sort {_quote(path)} | uniq" if path else None
    elif action == "find_name":
        pattern = kwargs.get("pattern", kwargs.get("name", ""))
        path = kwargs.get("path", ".")
        if pattern:
            return f"find {_quote(path)} -type f -name {_quote(pattern)}"
        return None
    elif action == "find_size":
        size = kwargs.get("size", kwargs.get("pattern", ""))
        path = kwargs.get("path", ".")
        if size:
            return f"find {_quote(path)} -type f -size {size}"
        return None
    elif action == "find_time":
        days = kwargs.get("days", kwargs.get("n", "7"))
        path = kwargs.get("path", ".")
        sign = kwargs.get("sign", "-")
        return f"find {_quote(path)} -mtime {sign}{days}"
    elif action == "find_empty":
        path = kwargs.get("path", ".")
        return f"find {_quote(path)} -type d -empty"
    elif action == "grep":
        pattern = kwargs.get("pattern", kwargs.get("text", ""))
        path = kwargs.get("path", kwargs.get("file", "."))
        if pattern:
            return f"grep -r {_quote(pattern)} {_quote(path)}"
        return None
    elif action == "grep_insensitive":
        pattern = kwargs.get("pattern", kwargs.get("text", ""))
        path = kwargs.get("path", kwargs.get("file", "."))
        if pattern:
            return f"grep -ri {_quote(pattern)} {_quote(path)}"
        return None
    elif action == "sed_replace":
        old = kwargs.get("old", kwargs.get("from", ""))
        new = kwargs.get("new", kwargs.get("to", ""))
        file = kwargs.get("file", kwargs.get("path", ""))
        if old and new and file:
            return f"sed -i 's/{old}/{new}/g' {_quote(file)}"
        return None
    return None


def example(action: str) -> str | None:
    """Return an example NL→command string for this action."""
    examples = {
        "list": "list files → ls .",
        "list_details": "list files with details → ls -la .",
        "copy": "copy file.txt to /backup → cp file.txt /backup",
        "move": "move file.txt to /tmp → mv file.txt /tmp",
        "rename": "rename old.txt to new.txt → mv old.txt new.txt",
        "delete": "delete temp.log → rm temp.log",
        "create_dir": "create directory called data → mkdir data",
        "create_dirs": "create nested dirs a/b/c → mkdir -p a/b/c",
        "create_file": "create empty file readme.md → touch readme.md",
        "show": "show contents of config.json → cat config.json",
        "head": "show first 5 lines of log.txt → head -n 5 log.txt",
        "tail": "show last 20 lines of log.txt → tail -n 20 log.txt",
        "count": "count lines in file.txt → wc -l file.txt",
        "find_name": "find all python files → find . -type f -name *.py",
        "find_size": "find files larger than 10MB → find . -type f -size +10M",
        "find_time": "find files modified in last 7 days → find . -mtime -7",
        "grep": "search for error in log files → grep -r error /var/log/",
        "grep_insensitive": "search case-insensitive for warning → grep -ri warning .",
        "sed_replace": "replace foo with bar in config.txt → sed -i s/foo/bar/g config.txt",
        "sort": "sort names.txt alphabetically → sort names.txt",
    }
    return examples.get(action)
