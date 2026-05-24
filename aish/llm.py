"""Multi-provider LLM client for aish.

Sends natural language to any OpenAI-compatible chat API
and returns a bash command.
"""

from __future__ import annotations

import json
import textwrap
from typing import Optional

from .config import BUILTIN_PROVIDERS, load_config

SYSTEM_PROMPT = textwrap.dedent("""\
You are a bash command translator for Linux. Convert natural language requests into bash commands.

RULES:
- Respond with ONLY a single bash command.
- NO explanations, NO markdown, NO code blocks, NO backticks.
- NO introductory or concluding text.
- Just the raw command, nothing else.
- For multi-step tasks, chain with && or ;.
- Use standard GNU/Linux tools (ls, find, grep, awk, sed, ps, systemctl, etc.).
- If ambiguous, pick the safest reasonable interpretation.
- If the request is dangerous (rm -rf, dd, mkfs, writing to /dev/, poweroff
  without flags), prefix with DANGEROUS: so aish can force confirmation.
- If untranslatable, output ERROR: followed by brief explanation.

EXAMPLES:
User: list all files
Assistant: ls
User: find all python files
Assistant: find . -type f -name "*.py"
User: check disk space
Assistant: df -h
User: kill process named nginx
Assistant: pkill nginx
User: make script.sh executable
Assistant: chmod +x script.sh
User: search for error in log files
Assistant: grep -r "error" /var/log/
User: compress mydir into tar.gz
Assistant: tar -czf mydir.tar.gz mydir
User: list running docker containers
Assistant: docker ps
User: give everyone read access to file.txt
Assistant: chmod o+r file.txt
User: find all files larger than 100MB
Assistant: find / -type f -size +100M
User: show system info
Assistant: uname -a
User: check memory usage
Assistant: free -h
User: find text in all files
Assistant: grep -r "searchterm" .
User: update all packages
Assistant: sudo dnf update -y
""")


def translate(nl_input: str, api_key: str, base_url: str, model: str,
              verbose: bool = False) -> tuple[Optional[str], Optional[str]]:
    """Send natural language to LLM → return (command, error).

    Returns:
        (command, None) on success
        (None, error_message) on failure
    """
    if not api_key and not any(
        p.name == load_config().provider and p.api_key_env == ""
        for p in BUILTIN_PROVIDERS
    ):
        return None, "No API key. Set via:  aish config set api-key <key>"
    if not base_url:
        return None, "No API base URL. Set via:  aish config set base-url <url>"
    if not model:
        return None, "No model. Set via:  aish config set model <name>"

    import requests as req

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": nl_input},
        ],
        "temperature": 0.05,
        "max_tokens": 512,
        "stream": False,
    }

    base = base_url.rstrip("/")

    if verbose:
        print(f"  [API] POST {base}/chat/completions")
        print(f"  [API] model={model}")

    try:
        resp = req.post(
            f"{base}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        return raw, None
    except req.exceptions.Timeout:
        return None, "API request timed out after 30s"
    except req.exceptions.ConnectionError as e:
        return None, f"Cannot connect to {base} — {e}"
    except req.exceptions.HTTPError as e:
        return None, f"HTTP {e.response.status_code}: {e.response.text[:200]}"
    except (KeyError, json.JSONDecodeError) as e:
        return None, f"Bad API response: {e}"
