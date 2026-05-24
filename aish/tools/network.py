"""Network tool — ping, curl, ss, ip, ssh."""

from __future__ import annotations

ACTIONS = {
    "ping": "ping a host",
    "download_curl": "download a file with curl",
    "download_wget": "download a file with wget",
    "ports": "show listening ports (ss -tlnp)",
    "connections": "show network connections (ss -tupn)",
    "ip_addr": "show IP addresses",
    "ip_link": "show network interfaces",
    "ssh": "SSH into a remote host",
    "scp": "copy file to remote host via SCP",
}


def _quote(s: str) -> str:
    return f'"{s}"' if " " in s else s


def build(action: str, kwargs: dict) -> str | None:
    host = kwargs.get("host", kwargs.get("name", ""))
    url = kwargs.get("url", "")

    if action == "ping":
        count = kwargs.get("count", kwargs.get("n", "4"))
        return f"ping -c {count} {_quote(host)}" if host else None
    elif action == "download_curl":
        output = kwargs.get("output", kwargs.get("o", ""))
        if output:
            return f"curl -o {_quote(output)} {_quote(url)}" if url else None
        return f"curl -O {_quote(url)}" if url else None
    elif action == "download_wget":
        return f"wget {_quote(url)}" if url else None
    elif action == "ports":
        return "ss -tlnp"
    elif action == "connections":
        return "ss -tupn"
    elif action == "ip_addr":
        return "ip addr"
    elif action == "ip_link":
        return "ip link"
    elif action == "ssh":
        user = kwargs.get("user", "")
        if host:
            target = f"{user}@{host}" if user else host
            return f"ssh {_quote(target)}"
        return None
    elif action == "scp":
        src = kwargs.get("src", kwargs.get("file", ""))
        dst = kwargs.get("dst", kwargs.get("dest", kwargs.get("to", "")))
        if src and dst:
            return f"scp {_quote(src)} {_quote(dst)}"
        return None
    return None


def example(action: str) -> str | None:
    examples = {
        "ping": "ping google.com → ping -c 4 google.com",
        "download_curl": "download file from url → curl -O https://example.com/file.zip",
        "ports": "show listening ports → ss -tlnp",
        "ip_addr": "show ip address → ip addr",
        "ssh": "ssh into server → ssh user@192.168.1.1",
    }
    return examples.get(action)
