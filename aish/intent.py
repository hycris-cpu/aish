"""Intent classifier — uses keyword matching to find the best tool+action.

The LLM is too small for reliable structured output, so we use Python
keyword matching for intent, then LLM only for parameter extraction.
If no tool matches, falls back to raw LLM generation.
"""

from __future__ import annotations

import re
from typing import Optional

from .tools.files import build as build_files
from .tools.system import build as build_system
from .tools.network import build as build_network
from .tools.dangerous import build as build_dangerous
from .tools.misc import build as build_misc
from . import tools

# ── Keyword-to-tool-action mapping ──
# (priority, pattern, tool, action, param_extract_fn)
# Priority: lower = checked first

RULES = [
    # ── Dangerous (highest priority) ──
    (10, r'\b(delete|remove)\s+.*(recursive|directory|folder)\b', 'dangerous', 'delete_recursive'),
    (10, r'\bformat\s+(disk|drive|sda|sdb|sdc|device)\b', 'dangerous', 'format_disk'),
    (10, r'\bshutdown\b', 'dangerous', 'shutdown'),
    (10, r'\breboot\b', 'dangerous', 'reboot'),

    # ── File operations ──
    (20, r'\blist\s+.*(details|long|all|permissions)\b', 'files', 'list_details'),
    (20, r'\blist\s+files\b', 'files', 'list'),
    (20, r'\bcopy\b', 'files', 'copy'),
    (20, r'\b(move|rename)\b', 'files', 'move'),
    (20, r'\bdelete\b.*\bfile\b', 'files', 'delete'),
    (20, r'\bremove\b.*\bfile\b', 'files', 'delete'),
    (20, r'\bcreate\s+(a\s+)?directory', 'files', 'create_dir'),
    (20, r'\bcreate\s+.*(nested|sub).*dir', 'files', 'create_dirs'),
    (20, r'\bmkdir\b', 'files', 'create_dir'),
    (20, r'\btouch\b', 'files', 'create_file'),
    (20, r'\bshow\s+contents\b', 'files', 'show'),
    (20, r'\bcat\b', 'files', 'show'),
    (20, r'\bfirst\s+(\d+)\s+lines\b', 'files', 'head'),
    (20, r'\bhead\b', 'files', 'head'),
    (20, r'\blast\s+(\d+)\s+lines\b', 'files', 'tail'),
    (20, r'\btail\b', 'files', 'tail'),
    (20, r'\bcount\s+lines\b', 'files', 'count'),
    (20, r'\bwc\b', 'files', 'count'),
    (20, r'\bsort\b', 'files', 'sort'),

    # ── Find ──
    (25, r'\bfind\s+.*(file|name).*\*\.\w+|\.\w+\b', 'files', 'find_name'),
    (25, r'\bfind\s+.*larger\s+than\b', 'files', 'find_size'),
    (25, r'\bfind\s+.*size\b', 'files', 'find_size'),
    (25, r'\bfind\s+.*modif|recent|day|week\b', 'files', 'find_time'),
    (25, r'\bfind\s+.*empty\b', 'files', 'find_empty'),

    # ── Text ──
    (30, r'\b(search|grep|find.*error|find.*text|find.*word)\b', 'files', 'grep'),
    (30, r'\b(sed|replace|substitute)\b', 'files', 'sed_replace'),
    (30, r'\bcase.insensitive\b', 'files', 'grep_insensitive'),

    # ── Process ──
    (40, r'\ball\s+running\s+process|ps\s+aux|show\s+process\b', 'system', 'ps'),
    (40, r'\bfind\s+process\b', 'system', 'ps_grep'),
    (40, r'\bkill\s+process\s+named|pkill\b', 'system', 'kill_name'),
    (40, r'\bkill\s+pid\b', 'system', 'kill_pid'),
    (40, r'\bforce\s+kill\b', 'system', 'kill_force'),
    (40, r'\btop\b', 'system', 'top'),

    # ── System info ──
    (50, r'\bsystem\s+info|uname\b', 'system', 'uname'),
    (50, r'\b(memory|ram|mem\s+usage|free\b)', 'system', 'memory'),
    (50, r'\bdisk\s+space\b', 'system', 'disk'),
    (50, r'\bdisk\s+usage\b', 'system', 'disk_usage'),
    (50, r'\buptime\b', 'system', 'uptime'),
    (50, r'\b(whoami|who\s+am\s+i|current\s+user)\b', 'system', 'whoami'),

    # ── Services ──
    (60, r'\bstart\s+(\w+)\s+service\b', 'system', 'service_start'),
    (60, r'\bstop\s+(\w+)\s+service\b', 'system', 'service_stop'),
    (60, r'\brestart\s+(\w+)\s+service\b', 'system', 'service_restart'),
    (60, r'\bcheck\s+(\w+)\s+status\b', 'system', 'service_status'),
    (60, r'\bstatus\s+of\s+(\w+)\b', 'system', 'service_status'),

    # ── Packages ──
    (70, r'\binstall\s+(\w[\w.\-]*)\s*(package\s*)?(with|using)?\s*(dnf|yum|apt)?\b', 'system', 'install'),
    (70, r'\bremove\s+(\w[\w.\-]*)\s*(package\s*)?(with|using)?\s*(dnf|yum|apt)?\b', 'system', 'remove'),
    (70, r'\bupdate\s+(all\s+)?packages\b', 'system', 'update'),

    # ── Network ──
    (80, r'\bping\b', 'network', 'ping'),
    (80, r'\b(download|curl|wget|fetch)\b', 'network', 'download_curl'),
    (80, r'\b(listening|ports?)\b', 'network', 'ports'),
    (80, r'\bip\s+address\b', 'network', 'ip_addr'),

    # ── Permissions ──
    (90, r'\b(make\s+executable|chmod\s+\+x)\b', 'misc', 'chmod_exec'),
    (90, r'\bgive\s+(\d+)\s+permissions\b', 'misc', 'chmod_recursive'),
    (90, r'\b(change\s+owner|chown)\b', 'misc', 'chown'),

    # ── Compression ──
    (100, r'\b(compress|tar\s+czf)\b', 'misc', 'tar_compress'),
    (100, r'\b(extract|untar|decompress)\s+.*tar', 'misc', 'tar_extract'),
    (100, r'\b(unzip|extract.*zip)\b', 'misc', 'zip_extract'),

    # ── Docker ──
    (110, r'\b(docker\s+ps|list\s+.*docker.*container)\b', 'misc', 'docker_ps'),
    (110, r'\bstop\s+docker\s+container\b', 'misc', 'docker_stop'),
    (110, r'\bdocker\s+images\b', 'misc', 'docker_images'),

    # ── Git ──
    (120, r'\bgit\s+status\b', 'misc', 'git_status'),
    (120, r'\b(git\s+log|commit\s+history|show\s+commits)\b', 'misc', 'git_log_oneline'),
    (120, r'\bgit\s+diff\b', 'misc', 'git_diff'),
    (120, r'\bg(it\s+)?add\b', 'misc', 'git_add_all'),
    (120, r'\b(git\s+)?commit\b', 'misc', 'git_commit'),
    (120, r'\bgit\s+push\b', 'misc', 'git_push'),
    (120, r'\bgit\s+pull\b', 'misc', 'git_pull'),
    (120, r'\bgit\s+clone\b', 'misc', 'git_clone'),
]

# For multisentence parsing: split by " and ", " then ", " && "
SPLIT_PATTERN = re.compile(r'\s+(and\s+then|and\s+also|&&?)\s+', re.IGNORECASE)


def _extract_param(text: str, prefix: str) -> str:
    """Extract a parameter value from text."""
    patterns = [
        rf'{prefix}[=:]\s*(\S+)',
        rf'\b{prefix}\s+(\S[\w.\-/]+)',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""


def classify(text: str) -> list[tuple[str, str, dict]]:
    """Classify intent and extract parameters.

    Returns list of (tool, action, params) tuples. Multiple entries for
    compound requests like "update and reboot".
    """
    # Split compound requests
    parts = SPLIT_PATTERN.split(text)
    results = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        found = False
        for priority, pattern, tool, action in RULES:
            m = re.search(pattern, part, re.IGNORECASE)
            if m:
                params = _extract_params(tool, action, part)
                results.append((tool, action, params))
                found = True
                break

        if not found:
            # No keyword match — will need LLM fallback
            results.append(("__unknown__", "__unknown__", {"text": part}))

    return results


def _extract_params(tool: str, action: str, text: str) -> dict:
    """Extract parameters from text based on tool+action."""
    params = {}

    if action in ("delete", "delete_recursive", "delete_force"):
        m = re.search(r'(?:delete|remove)\s+(\S+)', text, re.IGNORECASE)
        if m:
            params["path"] = m.group(1)

    elif action == "copy":
        m = re.search(r'copy\s+(\S+)\s+(?:to|into)\s+(\S+)', text, re.IGNORECASE)
        if m:
            params["src"] = m.group(1)
            params["dst"] = m.group(2)
        else:
            m = re.search(r'copy\s+(\S+)', text, re.IGNORECASE)
            if m:
                params["src"] = m.group(1)

    elif action in ("move", "rename"):
        m = re.search(r'(?:move|rename)\s+(\S+)\s+(?:to|into)\s+(\S+)', text, re.IGNORECASE)
        if m:
            params["src"] = m.group(1)
            params["dst"] = m.group(2)

    elif action in ("create_dir", "create_dirs"):
        m = re.search(r'(?:create|mkdir)\s+(?:a\s+)?(?:directory\s+|dir\s+)?(?:called\s+)?(\S[\w\-/.]+)', text, re.IGNORECASE)
        if m:
            params["path"] = m.group(1)

    elif action in ("create_file",):
        m = re.search(r'(?:create|touch)\s+(?:a\s+|an\s+)?(?:empty\s+)?(?:file\s+)?(?:called\s+)?(\S[\w.\-]+)', text, re.IGNORECASE)
        if m:
            params["path"] = m.group(1)

    elif action in ("show",):
        m = re.search(r'(?:show|cat|contents\s+of|read)\s+(\S[\w.\-/]+)', text, re.IGNORECASE)
        if m:
            params["path"] = m.group(1)

    elif action == "head":
        m = re.search(r'first\s+(\d+)', text, re.IGNORECASE)
        if m:
            params["n"] = m.group(1)
        m = re.search(r'(?:show|head)\s+(\S[\w.\-/]+)', text, re.IGNORECASE)
        if m:
            params["path"] = m.group(1)

    elif action == "tail":
        m = re.search(r'last\s+(\d+)', text, re.IGNORECASE)
        if m:
            params["n"] = m.group(1)
        m = re.search(r'(?:show|tail)\s+(\S[\w.\-/]+)', text, re.IGNORECASE)
        if m:
            params["path"] = m.group(1)

    elif action == "find_name":
        m = re.search(r'\*?\.(\w+)\b', text) or re.search(r'name\s+(\S+)', text)
        if m:
            ext = m.group(1)
            if ext.startswith("*."):
                ext = ext[2:]
            params["pattern"] = f"*.{ext}"

    elif action == "find_size":
        m = re.search(r'(\d+)(MB|GB|KB|M|G|K)', text, re.IGNORECASE)
        if m:
            params["size"] = f"+{m.group(1)}{m.group(2)}"

    elif action in ("grep", "grep_insensitive"):
        m = re.search(r'(?:search\s+(?:for\s+)?)[\"\']?(\w[\w.\-]*)[\"\']?', text, re.IGNORECASE)
        if m:
            params["pattern"] = m.group(1)
        m = re.search(r'in\s+(\S[\w.\-/]+)', text, re.IGNORECASE)
        if m:
            params["path"] = m.group(1)

    elif action == "sed_replace":
        m = re.search(r'replace\s+(\S+)\s+with\s+(\S+)', text, re.IGNORECASE)
        if m:
            params["old"] = m.group(1)
            params["new"] = m.group(2)
        m = re.search(r'in\s+(\S[\w.\-/]+)', text, re.IGNORECASE)
        if m:
            params["file"] = m.group(1)

    elif action in ("install", "remove"):
        m = re.search(r'(?:install|remove)\s+(\S+)', text, re.IGNORECASE)
        if m:
            params["name"] = m.group(1)

    elif action == "service_start":
        m = re.search(r'start\s+(\S+)', text, re.IGNORECASE)
        if m:
            params["name"] = m.group(1)

    elif action == "service_stop":
        m = re.search(r'stop\s+(\S+)', text, re.IGNORECASE)
        if m:
            params["name"] = m.group(1)

    elif action == "service_restart":
        m = re.search(r'restart\s+(\S+)', text, re.IGNORECASE)
        if m:
            params["name"] = m.group(1)

    elif action == "service_status":
        m = re.search(r'(?:status\s+of\s+|check\s+)(\S+)', text, re.IGNORECASE)
        if m:
            params["name"] = m.group(1)

    elif action == "format_disk":
        m = re.search(r'(?:format|mkfs)\s+(\S+)', text, re.IGNORECASE)
        if m:
            params["device"] = m.group(1)
        m = re.search(r'as\s+(\w+)', text, re.IGNORECASE)
        if m:
            params["fstype"] = m.group(1)

    elif action == "ping":
        m = re.search(r'ping\s+(\S+)', text, re.IGNORECASE)
        if m:
            params["host"] = m.group(1)

    elif action in ("ps_grep", "kill_name"):
        m = re.search(r'(?:process\s+)?(?:named|for|by\s+name)\s+(\S+)', text, re.IGNORECASE)
        if m:
            params["name"] = m.group(1)
        elif action == "kill_name":
            m = re.search(r'kill\s+(\S+)', text, re.IGNORECASE)
            if m:
                params["name"] = m.group(1)

    elif action == "chmod_recursive":
        m = re.search(r'give\s+(\d+)', text, re.IGNORECASE)
        if m:
            params["mode"] = m.group(1)
        m = re.search(r'(?:to|for)\s+(\S[\w\-/.]+)', text, re.IGNORECASE)
        if m:
            params["path"] = m.group(1)

    elif action == "chmod_exec":
        m = re.search(r'(?:executable|chmod\s+\+x)\s+(\S+)', text, re.IGNORECASE)
        if m:
            params["path"] = m.group(1)

    elif action in ("tar_compress",):
        m = re.search(r'(?:compress|tar)\s+(\S[\w\-/.]+)', text, re.IGNORECASE)
        if m:
            params["source"] = m.group(1)

    elif action in ("tar_extract",):
        m = re.search(r'(?:extract|untar)\s+(\S[\w\-/.]+)', text, re.IGNORECASE)
        if m:
            params["archive"] = m.group(1)

    elif action == "docker_stop":
        m = re.search(r'stop\s+(?:docker\s+)?(?:container\s+)?(\S+)', text, re.IGNORECASE)
        if m:
            params["container"] = m.group(1)

    elif action == "git_commit":
        m = re.search(r'message[\s\"\']+([\w\s]+)[\"\']', text, re.IGNORECASE)
        if m:
            params["msg"] = m.group(1).strip()
        m = re.search(r'with\s+message\s+[\"\']?(\S[\w\s]+?)[\"\']?(?:\s*$|\.\s*$)', text, re.IGNORECASE)
        if m:
            params["msg"] = m.group(1).strip()

    return params
