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

"""System tool — process mgmt, system info, services, packages."""

from __future__ import annotations

ACTIONS = {
    # Process
    "ps": "show all running processes (ps aux)",
    "ps_grep": "find process by name (ps aux | grep)",
    "kill_name": "kill process by name (pkill)",
    "kill_pid": "kill process by PID",
    "kill_force": "force kill by PID",
    "top": "show processes in real time",
    # System info
    "uname": "show system info",
    "memory": "check memory usage (free -h)",
    "disk": "check disk space (df -h)",
    "disk_usage": "show disk usage of dir (du -sh)",
    "uptime": "show system uptime",
    "whoami": "show current user",
    # Services
    "service_start": "start a systemd service",
    "service_stop": "stop a systemd service",
    "service_restart": "restart a systemd service",
    "service_status": "check service status",
    "service_enable": "enable service on boot",
    # Packages
    "install": "install package (dnf install)",
    "remove": "remove package (dnf remove)",
    "update": "update all packages (dnf update)",
    "pip_install": "install python package (pip install)",
}


def _quote(s: str) -> str:
    return f'"{s}"' if " " in s else s


def _sudo(kwargs: dict, cmd: str) -> str:
    if kwargs.get("sudo", "true").lower() in ("true", "yes", "1"):
        return f"sudo {cmd}"
    return cmd


def build(action: str, kwargs: dict) -> str | None:
    name = kwargs.get("name", kwargs.get("service", kwargs.get("pkg", kwargs.get("package", ""))))

    if action == "ps":
        return "ps aux"
    elif action == "ps_grep":
        if name:
            return f"ps aux | grep {_quote(name)}"
        return None
    elif action == "kill_name":
        if name:
            return f"pkill {_quote(name)}"
        return None
    elif action == "kill_pid":
        pid = kwargs.get("pid", name)
        if pid:
            return f"kill {pid}"
        return None
    elif action == "kill_force":
        pid = kwargs.get("pid", name)
        if pid:
            return f"kill -9 {pid}"
        return None
    elif action == "top":
        return "top"
    elif action == "uname":
        return "uname -a"
    elif action == "memory":
        return "free -h"
    elif action == "disk":
        return "df -h"
    elif action == "disk_usage":
        path = kwargs.get("path", ".")
        return f"du -sh {_quote(path)}"
    elif action == "uptime":
        return "uptime"
    elif action == "whoami":
        return "whoami"
    elif action == "service_start":
        if name:
            return _sudo(kwargs, f"systemctl start {name}")
        return None
    elif action == "service_stop":
        if name:
            return _sudo(kwargs, f"systemctl stop {name}")
        return None
    elif action == "service_restart":
        if name:
            return _sudo(kwargs, f"systemctl restart {name}")
        return None
    elif action == "service_status":
        if name:
            return f"systemctl status {name}"
        return None
    elif action == "service_enable":
        if name:
            return _sudo(kwargs, f"systemctl enable {name}")
        return None
    elif action == "install":
        if name:
            return _sudo(kwargs, f"dnf install -y {_quote(name)}")
        return None
    elif action == "remove":
        if name:
            return _sudo(kwargs, f"dnf remove -y {_quote(name)}")
        return None
    elif action == "update":
        return _sudo(kwargs, "dnf update -y")
    elif action == "pip_install":
        if name:
            return f"pip install {_quote(name)}"
        return None
    return None


def example(action: str) -> str | None:
    examples = {
        "ps": "show running processes → ps aux",
        "ps_grep": "find nginx process → ps aux | grep nginx",
        "kill_name": "kill nginx → pkill nginx",
        "kill_pid": "kill pid 1234 → kill 1234",
        "kill_force": "force kill pid 1234 → kill -9 1234",
        "uname": "show system info → uname -a",
        "memory": "check memory → free -h",
        "disk": "check disk space → df -h",
        "disk_usage": "disk usage of current dir → du -sh .",
        "uptime": "show uptime → uptime",
        "whoami": "show current user → whoami",
        "service_start": "start nginx → sudo systemctl start nginx",
        "service_stop": "stop nginx → sudo systemctl stop nginx",
        "service_restart": "restart nginx → sudo systemctl restart nginx",
        "service_status": "check nginx status → systemctl status nginx",
        "service_enable": "enable nginx on boot → sudo systemctl enable nginx",
        "install": "install nginx → sudo dnf install -y nginx",
        "remove": "remove nginx → sudo dnf remove -y nginx",
        "update": "update all packages → sudo dnf update -y",
        "pip_install": "install requests → pip install requests",
    }
    return examples.get(action)
