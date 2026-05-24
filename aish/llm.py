"""LLM client for aish — Forge-inspired harness.

Architecture:
1. Override rules: regex patterns for structured commands (services, packages, git, docker, etc.)
2. LLM generation: tight 15-example prompt for everything else (proven ~90% hit rate)
3. Guardrail retry: if LLM produces ERROR or malformed output, retry once
4. Respond tool: detect chat-only queries, no command generation
5. Danger scan: post-build safety check
"""

from __future__ import annotations

import json
import re
import textwrap
from typing import Optional

import requests as req

from .config import BUILTIN_PROVIDERS, load_config
from .learn import recall, learn

# ═══════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT — tight, focused, with tool descriptions
# ═══════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = textwrap.dedent("""\
You are a bash command translator for Linux. Given a user request, output ONLY the bash command.

NO explanations, NO markdown, NO backticks. Just the command.

If the user is just chatting (greeting, asking who you are, saying thanks) or the request
has no reasonable Linux command, output: RESPOND:<your message>

EXAMPLES:
list files with details → ls -la
show disk space → df -h
show memory usage → free -h
show running processes → ps aux
show uptime → uptime
show system info → uname -a
show current user → whoami
show contents of config.json → cat config.json
delete temp.log → rm temp.log
find all python files → find . -type f -name "*.py"
find files larger than 100MB → find / -type f -size +100M
search for error in log files → grep -r "error" /var/log/
kill process named nginx → pkill nginx
compress mydir into tar.gz → tar -czf mydir.tar.gz mydir
show block devices → lsblk
show kernel messages → dmesg | tail -50
show listening ports → ss -tlnp
ping google.com → ping -c 4 google.com
hello → RESPOND:Hello! I'm your Aish Linux assistant. How can I help?
""")

# ═══════════════════════════════════════════════════════════════════════
# OVERRIDE RULES — structured patterns the 0.6B gets wrong
# ═══════════════════════════════════════════════════════════════════════

OVERRIDES: list[tuple[re.Pattern, callable]] = [
    # ── Package management ──
    (re.compile(r'^install\s+(\S[\w.\-]*)', re.IGNORECASE),
     lambda m: f"sudo dnf install -y {m.group(1)}"),
    (re.compile(r'^remove\s+(\S[\w.\-]*)', re.IGNORECASE),
     lambda m: f"sudo dnf remove -y {m.group(1)}"),
    (re.compile(r'^update\s+(all\s+)?(packages|system)', re.IGNORECASE),
     lambda _: "sudo dnf update -y"),
    (re.compile(r'^pip\s+install\s+(\S+)', re.IGNORECASE),
     lambda m: f"pip install {m.group(1)}"),

    # ── Service management ──
    (re.compile(r'^(start|stop|restart|enable)\s+(\S+)\s*(service)?$', re.IGNORECASE),
     lambda m: f"sudo systemctl {m.group(1).lower()} {m.group(2)}"),
    (re.compile(r'^(check|get)\s+(\S+)\s+(service\s+)?(status|health|running)', re.IGNORECASE),
     lambda m: f"systemctl status {m.group(2)}"),
    (re.compile(r'^status\s+of\s+(\S+)', re.IGNORECASE),
     lambda m: f"systemctl status {m.group(1)}"),

    # ── Docker ──
    (re.compile(r'^(list|show)\s+(running\s+)?docker\s+containers', re.IGNORECASE), lambda _: "docker ps"),
    (re.compile(r'^docker\s+ps', re.IGNORECASE), lambda _: "docker ps"),
    (re.compile(r'^docker\s+stop\s+(\S+)', re.IGNORECASE), lambda m: f"docker stop {m.group(1)}"),
    (re.compile(r'^(stop|rm)\s+docker\s+container\s+(\S+)', re.IGNORECASE), lambda m: f"docker {m.group(1).lower()} {m.group(2)}"),
    (re.compile(r'^docker\s+images', re.IGNORECASE), lambda _: "docker images"),

    # ── Git ──
    (re.compile(r'^git\s+status', re.IGNORECASE), lambda _: "git status"),
    (re.compile(r'^git\s+(push|pull|diff)', re.IGNORECASE), lambda m: f"git {m.group(1).lower()}"),
    (re.compile(r'^(show\s+)?commit\s+history', re.IGNORECASE), lambda _: "git log --oneline"),
    (re.compile(r'^(add|git\s+add)\s+(all\s+)?files', re.IGNORECASE), lambda _: "git add -A"),
    (re.compile(r'^git\s+clone\s+(\S+)', re.IGNORECASE), lambda m: f"git clone {m.group(1)}"),
    (re.compile(r'^commit\s+(changes\s+)?(with\s+message\s+)?["]?(.+?)["]?$', re.IGNORECASE),
     lambda m: f'git commit -m "{m.group(3) or "update"}"'),

    # ── Compression ──
    (re.compile(r'^(compress|tar)\s+(\S+)\s+(into|to)\s+(\S+)', re.IGNORECASE),
     lambda m: f"tar -czf {m.group(4)} {m.group(2)}"),
    (re.compile(r'^(extract|untar)\s+(\S+\.tar\.gz)', re.IGNORECASE), lambda m: f"tar -xzf {m.group(2)}"),

    # ── Permissions ──
    (re.compile(r'^make\s+(\S+)\s+executable', re.IGNORECASE), lambda m: f"chmod +x {m.group(1)}"),
    (re.compile(r'^give\s+(\d+)\s+permissions?\s+(to|for)\s+(\S+)', re.IGNORECASE),
     lambda m: f"chmod -R {m.group(1)} {m.group(3)}"),
    (re.compile(r'^change\s+owner\s+(of\s+)?(\S+)\s+(to\s+)?(\S+)', re.IGNORECASE),
     lambda m: f"sudo chown {m.group(4)} {m.group(2)}"),

    # ── Network — what's on port ──
    (re.compile(r'(what|which)\s+(server|process|app|service|port)\s+is\s+(on|using|running|listening)\D*(\d{3,5})', re.IGNORECASE),
     lambda m: f"ss -tlnp | grep :{m.group(4)}"),
    (re.compile(r'find\s+(the\s+)?(what|which)\s+(server|process|app|service|port)\s+is\s+(on|using|running|listening)\D*(\d{3,5}).*', re.IGNORECASE),
     lambda m: f"ss -tlnp | grep :{m.group(5)}"),

    # ── Dangerous ──
    (re.compile(r'^delete\s+directory\s+recursive', re.IGNORECASE), lambda _: "DANGEROUS: rm -rf <path>"),
    (re.compile(r'^format\s+(\S+)\s+(as\s+)?(\w+)?', re.IGNORECASE),
     lambda m: f"DANGEROUS: sudo mkfs.{m.group(3) or 'ext4'} {m.group(1)}"),
    (re.compile(r'^shutdown(\s+the\s+system)?', re.IGNORECASE), lambda _: "DANGEROUS: sudo poweroff"),
    (re.compile(r'^reboot(\s+the\s+system)?', re.IGNORECASE), lambda _: "DANGEROUS: sudo reboot"),
]

# ═══════════════════════════════════════════════════════════════════════
# DANGER SCAN — post-build safety
# ═══════════════════════════════════════════════════════════════════════

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

CHAT_PATTERNS = [
    re.compile(r'^(hello|hi|hey|good\s+(morning|afternoon|evening)|what(\'s|\sis)\s+(your\s+)?name|who\s+are\s+you|thanks|thank\s+you)', re.IGNORECASE),
]


def _is_chat(text: str) -> bool:
    """Check if this is a chat-only query (no command needed)."""
    for pat in CHAT_PATTERNS:
        if pat.match(text.strip()):
            return True
    return False


def _scan_dangerous(command: str) -> Optional[str]:
    """Check if command is dangerous. Returns DANGEROUS: prefix if so."""
    for pat in DANGEROUS_PATTERNS:
        if pat.search(command):
            return f"DANGEROUS: {command}"
    return None


# ═══════════════════════════════════════════════════════════════════════
# LLM CALL
# ═══════════════════════════════════════════════════════════════════════

def _call_llm(user_input: str, api_key: str, base_url: str, model: str,
              max_tokens: int = 256, system_override: str = None) -> tuple[Optional[str], Optional[str]]:
    """Call the LLM with the system prompt."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    sp = system_override or SYSTEM_PROMPT
    try:
        resp = req.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": sp},
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
    except Exception as e:
        return None, str(e)


# ═══════════════════════════════════════════════════════════════════════
# GUARDRAIL — retry prompt for malformed output
# ═══════════════════════════════════════════════════════════════════════

GUARDRAIL_PROMPT = textwrap.dedent("""\
Your last response was not a valid bash command. Output ONLY a single bash command.
No explanations. Just the command.
""")


# ═══════════════════════════════════════════════════════════════════════
# TRANSLATE — main entry point
# ═══════════════════════════════════════════════════════════════════════

def translate(nl_input: str, api_key: str, base_url: str, model: str,
              verbose: bool = False) -> tuple[Optional[str], Optional[str]]:
    """Translate NL to bash command with guardrails."""
    # API key check
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

    # ── Step 0: Chat-only detection ──
    if _is_chat(text):
        if verbose:
            print("  [aish] Chat query detected")
        return None, None  # caller handles this

    # ── Step 0b: Recall learned pattern ──
    learned_cmd = recall(text)
    if learned_cmd:
        if verbose:
            print(f"  [aish] Learned pattern found: {learned_cmd}")
        dangerous = _scan_dangerous(learned_cmd)
        return (dangerous or learned_cmd), None

    # ── Step 1: Override rules ──
    for pattern, builder in OVERRIDES:
        m = pattern.match(text)
        if m:
            cmd = builder(m)
            if cmd:
                if verbose:
                    print(f"  [aish] Override matched: {cmd}")
                dangerous = _scan_dangerous(cmd)
                return (dangerous or cmd), None

    # ── Step 2: LLM generation (with guardrail retry) ──
    for attempt in range(2):
        if verbose:
            print(f"  [aish] LLM attempt {attempt + 1}...")

        sp = GUARDRAIL_PROMPT if attempt == 1 else None
        result, err = _call_llm(text, api_key, base_url, model, system_override=sp)
        if err:
            return None, err

        if verbose:
            print(f"  [aish] => {result[:80]}")

        # Handle RESPOND: prefix (chat detected by LLM)
        if result.upper().startswith("RESPOND:"):
            return None, None  # chat query, caller handles

        if result.upper().startswith("ERROR"):
            if attempt == 0:
                if verbose:
                    print("  [aish] ERROR output, retrying...")
                continue
            return None, result[6:].strip()

        # Strip markdown fences
        if result.startswith("```"):
            for line in result.split("\n"):
                if line.strip() and not line.strip().startswith("```"):
                    result = line.strip()
                    break

        # Validate: should look like a command (not prose)
        if attempt == 0 and (len(result) > 120 or " " not in result.strip() and len(result) > 30):
            if verbose:
                print("  [aish] Output looks like prose, retrying...")
            continue

        # Validate: don't echo the prompt back
        if attempt == 0 and result.strip().lower() == text.lower():
            if verbose:
                print("  [aish] Output echoes prompt, retrying...")
            continue

        # ── Step 3: Danger scan ──
        dangerous = _scan_dangerous(result)
        final_cmd = dangerous or result

        # ── Step 4: Learn if retry succeeded ──
        if attempt == 1:
            if verbose:
                print(f"  [aish] Learning pattern: {text[:40]} → {final_cmd[:40]}")
            learn(text, final_cmd)

        return final_cmd, None

    return None, f"Cannot translate: '{text}'"
