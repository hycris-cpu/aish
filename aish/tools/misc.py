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

"""Misc tools — permissions, compression, docker, git, chaining."""

from __future__ import annotations

ACTIONS = {
    # Permissions
    "chmod_exec": "make file executable (chmod +x)",
    "chmod_add_read": "add read permission for everyone (chmod o+r)",
    "chmod_recursive": "set permissions recursively (chmod -R)",
    "chown": "change file owner",
    # Compression
    "tar_compress": "compress to tar.gz",
    "tar_extract": "extract tar.gz",
    "zip_compress": "compress to zip",
    "zip_extract": "extract zip",
    "gzip": "compress with gzip",
    "gunzip": "decompress gz",
    # Docker
    "docker_ps": "list running containers",
    "docker_ps_all": "list all containers",
    "docker_stop": "stop a container",
    "docker_rm": "remove a container",
    "docker_images": "list images",
    "docker_pull": "pull an image",
    "docker_logs": "view container logs",
    # Git
    "git_status": "show git status",
    "git_log": "show commit log",
    "git_log_oneline": "show commit log (oneline)",
    "git_diff": "show unstaged diff",
    "git_diff_cached": "show staged diff",
    "git_add_all": "add all files",
    "git_commit": "commit with message",
    "git_push": "push to remote",
    "git_pull": "pull from remote",
    "git_branch_create": "create and switch to new branch",
    "git_checkout": "switch to branch",
    "git_merge": "merge branch",
    "git_clone": "clone a repository",
    # Chain
    "chain": "run multiple commands sequentially",
}


def _quote(s: str) -> str:
    return f'"{s}"' if " " in s else s


def build(action: str, kwargs: dict) -> str | None:
    # ── Permissions ──
    if action == "chmod_exec":
        path = kwargs.get("path", kwargs.get("file", ""))
        return f"chmod +x {_quote(path)}" if path else None
    elif action == "chmod_add_read":
        path = kwargs.get("path", kwargs.get("file", ""))
        return f"chmod o+r {_quote(path)}" if path else None
    elif action == "chmod_recursive":
        path = kwargs.get("path", kwargs.get("dir", kwargs.get("name", "")))
        mode = kwargs.get("mode", kwargs.get("perm", "755"))
        return f"chmod -R {mode} {_quote(path)}" if path else None
    elif action == "chown":
        path = kwargs.get("path", kwargs.get("file", ""))
        owner = kwargs.get("owner", kwargs.get("user", ""))
        if path and owner:
            return f"sudo chown {_quote(owner)} {_quote(path)}"
        return None

    # ── Compression ──
    elif action == "tar_compress":
        name = kwargs.get("name", kwargs.get("archive", ""))
        source = kwargs.get("source", kwargs.get("path", kwargs.get("dir", "")))
        if source:
            archive_name = name or f"{source.split('/')[-1]}.tar.gz"
            return f"tar -czf {_quote(archive_name)} {_quote(source)}"
        return None
    elif action == "tar_extract":
        archive = kwargs.get("archive", kwargs.get("file", kwargs.get("name", "")))
        dest = kwargs.get("dest", kwargs.get("to", ""))
        if archive:
            return f"tar -xzf {_quote(archive)} {'-C ' + _quote(dest) if dest else ''}".strip()
        return None
    elif action == "zip_compress":
        source = kwargs.get("source", kwargs.get("path", kwargs.get("dir", "")))
        name = kwargs.get("name", kwargs.get("archive", f"{source.split('/')[-1]}.zip"))
        if source:
            return f"zip -r {_quote(name)} {_quote(source)}"
        return None
    elif action == "zip_extract":
        archive = kwargs.get("archive", kwargs.get("file", kwargs.get("name", "")))
        return f"unzip {_quote(archive)}" if archive else None
    elif action == "gzip":
        path = kwargs.get("path", kwargs.get("file", ""))
        return f"gzip {_quote(path)}" if path else None
    elif action == "gunzip":
        path = kwargs.get("path", kwargs.get("file", ""))
        return f"gunzip {_quote(path)}" if path else None

    # ── Docker ──
    elif action == "docker_ps":
        return "docker ps"
    elif action == "docker_ps_all":
        return "docker ps -a"
    elif action == "docker_stop":
        container = kwargs.get("container", kwargs.get("name", ""))
        return f"docker stop {container}" if container else None
    elif action == "docker_rm":
        container = kwargs.get("container", kwargs.get("name", ""))
        return f"docker rm {container}" if container else None
    elif action == "docker_images":
        return "docker images"
    elif action == "docker_pull":
        image = kwargs.get("image", kwargs.get("name", ""))
        return f"docker pull {image}" if image else None
    elif action == "docker_logs":
        container = kwargs.get("container", kwargs.get("name", ""))
        return f"docker logs {container}" if container else None

    # ── Git ──
    elif action == "git_status":
        return "git status"
    elif action == "git_log":
        return "git log"
    elif action == "git_log_oneline":
        return "git log --oneline"
    elif action == "git_diff":
        return "git diff"
    elif action == "git_diff_cached":
        return "git diff --cached"
    elif action == "git_add_all":
        return "git add -A"
    elif action == "git_commit":
        msg = kwargs.get("msg", kwargs.get("message", kwargs.get("text", "update")))
        return f'git commit -m "{msg}"'
    elif action == "git_push":
        return "git push"
    elif action == "git_pull":
        return "git pull"
    elif action == "git_branch_create":
        branch = kwargs.get("branch", kwargs.get("name", ""))
        return f"git checkout -b {branch}" if branch else None
    elif action == "git_checkout":
        branch = kwargs.get("branch", kwargs.get("name", ""))
        return f"git checkout {branch}" if branch else None
    elif action == "git_merge":
        branch = kwargs.get("branch", kwargs.get("name", ""))
        return f"git merge {branch}" if branch else None
    elif action == "git_clone":
        url = kwargs.get("url", kwargs.get("repo", ""))
        return f"git clone {url}" if url else None

    # ── Chain ──
    elif action == "chain":
        commands = kwargs.get("commands", [])
        if isinstance(commands, list) and commands:
            return " && ".join(commands)
        text = kwargs.get("text", "")
        if text and "&&" in text:
            return text
        return None

    return None


def example(action: str) -> str | None:
    examples = {
        "chmod_exec": "make script.sh executable → chmod +x script.sh",
        "chmod_recursive": "give 755 to mydir → chmod -R 755 mydir",
        "chown": "change owner to root → sudo chown root file.txt",
        "tar_compress": "compress mydir to tar.gz → tar -czf mydir.tar.gz mydir",
        "tar_extract": "extract archive.tar.gz → tar -xzf archive.tar.gz",
        "zip_compress": "zip mydir to archive.zip → zip -r archive.zip mydir",
        "zip_extract": "unzip archive.zip → unzip archive.zip",
        "docker_ps": "list running containers → docker ps",
        "docker_stop": "stop container web → docker stop web",
        "git_status": "show git status → git status",
        "git_log_oneline": "show commit history → git log --oneline",
        "git_add_all": "add all files to git → git add -A",
        "git_commit": "commit changes → git commit -m update",
    }
    return examples.get(action)
