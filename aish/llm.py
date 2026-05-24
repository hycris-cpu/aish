"""LLM client for aish — raw generation with safety scanning.

Strategy for 0.6B model:
- Tight system prompt (proven ~90% hit rate)
- Override rules for structured patterns the 0.6B gets wrong
- Danger scan on output
"""

from __future__ import annotations

import json
import re
import textwrap
from typing import Optional

import requests as req

from .config import BUILTIN_PROVIDERS, load_config

SYSTEM_PROMPT = textwrap.dedent("""\
You are a bash command translator for Linux. Given a user request, output ONLY the bash command.

NO explanations, NO markdown, NO backticks. Just the command.

EXAMPLES:
list files with details → ls -la
delete temp.log → rm temp.log
show contents of config.json → cat config.json
show disk space → df -h
show memory usage → free -h
show running processes → ps aux
show uptime → uptime
show system info → uname -a
show current user → whoami
find all python files → find . -type f -name "*.py"
find files larger than 100MB → find / -type f -size +100M
search for error in log files → grep -r "error" /var/log/
kill process named nginx → pkill nginx
compress mydir into tar.gz → tar -czf mydir.tar.gz mydir
show block devices → lsblk
show kernel messages → dmesg | tail -50
show listening ports → ss -tlnp
ping google.com → ping -c 4 google.com
""")

# ── Override rules: normalize known structured patterns ──
# format: (regex, lambda that receives match groups as args)

OVERRIDES: list[tuple[re.Pattern, callable]] = [
    # Package management
    (re.compile(r'^install\s+(\S[\w.\-]*)', re.IGNORECASE),
     lambda m: f"sudo dnf install -y {m.group(1)}"),
    (re.compile(r'^remove\s+(\S[\w.\-]*)', re.IGNORECASE),
     lambda m: f"sudo dnf remove -y {m.group(1)}"),
    (re.compile(r'^update\s+(all\s+)?(packages|system)', re.IGNORECASE),
     lambda _: "sudo dnf update -y"),

    # pip
    (re.compile(r'^pip\s+install\s+(\S+)', re.IGNORECASE),
     lambda m: f"pip install {m.group(1)}"),
    (re.compile(r'^(install|remove)\s+(\S+)\s+(with\s+)?pip', re.IGNORECASE),
     lambda m: f"pip {m.group(1).lower()} {m.group(2)}"),

    # Service management
    (re.compile(r'^(start|stop|restart|enable)\s+(\S+)\s*(service)?$', re.IGNORECASE),
     lambda m: f"sudo systemctl {m.group(1).lower()} {m.group(2)}"),
    (re.compile(r'^(check|get)\s+(\S+)\s+(service\s+)?(status|health|running)', re.IGNORECASE),
     lambda m: f"systemctl status {m.group(2)}"),
    (re.compile(r'^status\s+of\s+(\S+)', re.IGNORECASE),
     lambda m: f"systemctl status {m.group(1)}"),

    # Docker
    (re.compile(r'^(list|show)\s+(running\s+)?docker\s+containers', re.IGNORECASE),
     lambda _: "docker ps"),
    (re.compile(r'^docker\s+ps', re.IGNORECASE), lambda _: "docker ps"),
    (re.compile(r'^docker\s+stop\s+(\S+)', re.IGNORECASE),
     lambda m: f"docker stop {m.group(1)}"),
    (re.compile(r'^(stop|rm)\s+docker\s+container\s+(\S+)', re.IGNORECASE),
     lambda m: f"docker {m.group(1).lower()} {m.group(2)}"),
    (re.compile(r'^docker\s+images', re.IGNORECASE), lambda _: "docker images"),
    (re.compile(r'^list\s+docker\s+images', re.IGNORECASE), lambda _: "docker images"),

    # Git
    (re.compile(r'^git\s+status', re.IGNORECASE), lambda _: "git status"),
    (re.compile(r'^git\s+(push|pull|diff)', re.IGNORECASE),
     lambda m: f"git {m.group(1).lower()}"),
    (re.compile(r'^(show\s+)?commit\s+history', re.IGNORECASE), lambda _: "git log --oneline"),
    (re.compile(r'^(add|git\s+add)\s+(all\s+)?files', re.IGNORECASE), lambda _: "git add -A"),
    (re.compile(r'^git\s+clone\s+(\S+)', re.IGNORECASE),
     lambda m: f"git clone {m.group(1)}"),
    (re.compile(r'^commit\s+(changes\s+)?(with\s+message\s+)?[\"]?(.+?)[\"]?$', re.IGNORECASE),
     lambda m: f'git commit -m "{m.group(3) or "update"}"'),

    # Compression
    (re.compile(r'^(compress|tar)\s+(\S+)\s+(into|to)\s+(\S+)', re.IGNORECASE),
     lambda m: f"tar -czf {m.group(4)} {m.group(2)}"),
    (re.compile(r'^(extract|untar)\s+(\S+\.tar\.gz)', re.IGNORECASE),
     lambda m: f"tar -xzf {m.group(2)}"),

    # Network - process on port
    (re.compile(r'(what|which)\s+(server|process|app|service|port)\s+is\s+(on|using|running|listening)\D*(\d{3,5})', re.IGNORECASE),
     lambda m: f"ss -tlnp | grep :{m.group(4)}"),
    (re.compile(r'find\s+(the\s+)?(what|which)\s+(server|process|app|service|port)\s+is\s+(on|using|running|listening)\D*(\d{3,5}).*', re.IGNORECASE),
     lambda m: f"ss -tlnp | grep :{m.group(5)}"),

    # Permissions
    (re.compile(r'^make\s+(\S+)\s+executable', re.IGNORECASE),
     lambda m: f"chmod +x {m.group(1)}"),
    (re.compile(r'^give\s+(\d+)\s+permissions?\s+(to|for)\s+(\S+)', re.IGNORECASE),
     lambda m: f"chmod -R {m.group(1)} {m.group(3)}"),
    (re.compile(r'^change\s+owner\s+(of\s+)?(\S+)\s+(to\s+)?(\S+)', re.IGNORECASE),
     lambda m: f"sudo chown {m.group(4)} {m.group(2)}"),

    # Dangerous
    (re.compile(r'^delete\s+directory\s+recursive', re.IGNORECASE),
     lambda _: "DANGEROUS: rm -rf <path>"),
    (re.compile(r'^format\s+(\S+)\s+(as\s+)?(\w+)?', re.IGNORECASE),
     lambda m: f"DANGEROUS: sudo mkfs.{m.group(3) or 'ext4'} {m.group(1)}"),
    (re.compile(r'^shutdown(\s+the\s+system)?', re.IGNORECASE),
     lambda _: "DANGEROUS: sudo poweroff"),
    (re.compile(r'^reboot(\s+the\s+system)?', re.IGNORECASE),
     lambda _: "DANGEROUS: sudo reboot"),
]

DANGEROUS_PATTERNS = [
    re.compile(r'\brm\s+-rf\s+(/|\~|\$|\*)'),
    re.compile(r'\bmkfs\.'),
    re.compile(r'\bdd\s+if='),
    re.compile(r'\bsudo\s+(poweroff|reboot|shutdown|halt)'),
    re.compile(r'\bchmod\s+-R\s+777\b'),
    re.compile(r'\bchmod\s+777\b'),
    re.compile(r'\bkill\s+-9\s+-1'),
    re.compile(r'\bsudo\s+rm\s+-rf'),
]


def _scan(command: str) -> Optional[str]:
    """Check if command is dangerous. Returns DANGEROUS: prefix if so."""
    for pat in DANGEROUS_PATTERNS:
        if pat.search(command):
            return f"DANGEROUS: {command}"
    return None


def _call_llm(user_input: str, api_key: str, base_url: str, model: str,
              max_tokens: int = 256) -> tuple[Optional[str], Optional[str]]:
    """Call the LLM."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = req.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input},
                ],
                "temperature": 0.0,
                "max_tokens": max_tokens,
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        return raw, None
    except req.exceptions.Timeout:
        return None, "API request timed out"
    except req.exceptions.ConnectionError as e:
        return None, f"Cannot connect: {e}"
    except req.exceptions.HTTPError as e:
        return None, f"HTTP {e.response.status_code}"
    except Exception as e:
        return None, str(e)


def translate(nl_input: str, api_key: str, base_url: str, model: str,
              verbose: bool = False) -> tuple[Optional[str], Optional[str]]:
    """Translate NL to bash command."""
    if not api_key and not any(
        p.name == load_config().provider and p.api_key_env == ""
        for p in BUILTIN_PROVIDERS
    ):
        return None, "No API key."
    if not base_url:
        return None, "No API base URL."
    if not model:
        return None, "No model."

    text = nl_input.strip()

    # Step 1: Override rules for structured patterns
    for pattern, builder in OVERRIDES:
        m = pattern.match(text)
        if m:
            cmd = builder(m)
            if cmd:
                return cmd, None

    # Step 2: LLM generation
    if verbose:
        print("  [aish] LLM generation...")

    result, err = _call_llm(text, api_key, base_url, model)
    if err:
        return None, err

    if verbose:
        print(f"  [aish] => {result[:80]}")

    if result.upper().startswith("ERROR"):
        return None, result[6:].strip()

    # Strip markdown fences
    if result.startswith("```"):
        for line in result.split("\n"):
            if line.strip() and not line.strip().startswith("```"):
                result = line.strip()
                break

    # Step 3: Danger scan
    dangerous = _scan(result)
    if dangerous:
        result = dangerous

    return result, None
