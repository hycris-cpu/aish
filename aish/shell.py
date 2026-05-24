"""Interactive shell — zsh-like prompt with bash passthrough and AI mode."""

from __future__ import annotations

import atexit
import os
import readline
import signal
import subprocess
import sys
from pathlib import Path

from .config import AishConfig
from .llm import translate

HIST_DIR = Path.home() / ".local" / "share" / "aish"
HIST_BASH = HIST_DIR / "history_bash"
HIST_AI   = HIST_DIR / "history_ai"

try:
    from rich.console import Console
    from rich.syntax import Syntax
    from rich.panel import Panel
    from rich.prompt import Prompt
    con = Console()
    RICH = True
except ImportError:
    RICH = False
    con = None


def _hist_path(mode: str) -> Path:
    return HIST_BASH if mode == "bash" else HIST_AI


def _load_history(mode: str):
    hp = _hist_path(mode)
    hp.parent.mkdir(parents=True, exist_ok=True)
    try:
        readline.read_history_file(str(hp))
    except FileNotFoundError:
        pass
    readline.set_history_length(2000)


def _save_history(mode: str):
    hp = _hist_path(mode)
    hp.parent.mkdir(parents=True, exist_ok=True)
    try:
        readline.write_history_file(str(hp))
    except OSError:
        pass


def _run_shell(cmd: str) -> int:
    """Execute a bash command, streaming output."""
    import time
    start = time.time()
    try:
        proc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True,
        )
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
        proc.wait()
        rc = proc.returncode
        # Record in history
        try:
            from .history import record as hist_record
            hist_record("", cmd, rc, time.time() - start)
        except Exception:
            pass
        return rc
    except KeyboardInterrupt:
        print("^C")
        return -1
    except Exception as e:
        print(f"error: {e}")
        return -1


def _show_command(command: str, dangerous: bool):
    """Display the translated command."""
    if dangerous:
        if RICH:
            con.print("[bold red]⚠ DANGEROUS[/bold red]")
        else:
            print("⚠ DANGEROUS")
    if RICH:
        con.print(Syntax(command, "bash", theme="monokai",
                         background_color="default"))
    else:
        print(f"  {command}")


def _confirm(command: str, dangerous: bool) -> str:
    """Ask for confirmation. Returns 'run' / 'skip' / 'edit:<text>'."""
    label = "DANGEROUS run" if dangerous else "Run"
    while True:
        if RICH:
            ans = Prompt.ask(
                f"[{'bold red' if dangerous else 'bold yellow'}]{label}?[/]",
                default="y"
            )
        else:
            ans = input(f"{label}? (Y/n/e/d) ").strip().lower() or "y"

        if ans in ("y", "yes", ""):
            return "run"
        if ans in ("n", "no"):
            return "skip"
        if ans in ("e", "edit"):
            if RICH:
                edited = Prompt.ask("Edit", default=command)
            else:
                edited = input(f"Edit [{command}]: ").strip()
            return f"edit:{edited}" if edited else "skip"
        if ans in ("d", "display"):
            _show_command(command, dangerous)
            continue
        print("  y=run  n=skip  e=edit  d=display-again")


def _handle_ai(text: str, config: AishConfig):
    """Process AI-mode input."""
    # ! prefix → raw bash
    if text.startswith("!"):
        cmd = text[1:].strip()
        if cmd:
            _run_shell(cmd)
        return

    command, err = translate(text, config.api_key, config.base_url,
                             config.model)
    # Chat-only query (no command needed)
    if err is None and command is None:
        return

    if err:
        if RICH:
            con.print(f"[red]✗[/red] {err}")
        else:
            print(f"✗ {err}")
        return

    if command.startswith("ERROR:"):
        msg = command[6:].strip()
        if RICH:
            con.print(f"[red]✗[/red] {msg}")
        else:
            print(f"✗ {msg}")
        return

    is_dangerous = command.startswith("DANGEROUS:")
    if is_dangerous:
        command = command[len("DANGEROUS:"):].strip()

    _show_command(command, is_dangerous)

    result = _confirm(command, is_dangerous)
    if result == "run":
        _run_shell(command)
    elif result.startswith("edit:"):
        edited = result[5:].strip()
        if edited:
            _run_shell(edited)


def _print_help():
    text = """\
[bold]Aish modes:[/bold]

  [green]bash mode[/green] — direct bash passthrough
  [cyan]ai mode[/cyan]   — natural language → command (via LLM)

[bold]Mode switching:[/bold]
  [cyan]/bash[/cyan] [green]/b[/green]    Switch to bash mode
  [cyan]/ai[/cyan] [green]/a[/green]      Switch to AI mode
  [cyan]/exit[/cyan] [green]/q[/green]   Quit

[bold]AI mode:[/bold]
  [cyan]<anything>[/cyan]  Natural language → bash command
  [cyan]!command[/cyan]    Run raw bash without AI
  [cyan]$var[/cyan]        Environment variables work as in bash

[bold]Bash mode:[/bold]
  Everything passes through to bash directly.

[bold]Config:[/bold]
  [cyan]aish config --help[/cyan]  Manage providers, keys, models
"""
    if RICH:
        con.print(Panel(text))
    else:
        import re
        print(re.sub(r'\[/?\w+\]', '', text))


def _get_hostname() -> str:
    try:
        return os.uname().nodename.split(".")[0]
    except Exception:
        return "localhost"


def _prompt(user: str, host: str, cwd: str, mode: str) -> str:
    """Build a zsh-style prompt string."""
    short = cwd.replace(Path.home(), "~")
    colors = {"bash": "green", "ai": "cyan"}
    c = colors.get(mode, "white")
    return (f"[bold]{user}[/bold][dim]@[/dim][bold]{host}[/bold] "
            f"[dim]{short}[/dim] % [[bold {c}]{mode}[/bold {c}]] ")


def run_shell(config: AishConfig, start_ai: bool = False):
    """Main interactive shell loop."""
    mode = "ai" if start_ai else "bash"
    user = os.environ.get("USER", "user")
    host = _get_hostname()

    _load_history(mode)
    atexit.register(lambda: _save_history(mode))
    prev_mode = mode

    welcome = Panel(
        "[bold cyan]aish[/bold cyan] — AI Shell\n"
        f"[dim]provider:[/dim] {config.provider}\n"
        f"[dim]model:[/dim]    {config.model}\n"
        f"[dim]switching:[/dim] /bash → bash mode  |  /ai → AI mode  |  /help",
        border_style="cyan",
    ) if RICH else (
        "┌─ aish ──────────────────────────────┐\n"
        f"│ provider: {config.provider}\n"
        f"│ model:    {config.model}\n"
        f"│ /bash /ai /help /exit\n"
        "└──────────────────────────────────────┘"
    )
    if RICH:
        con.print(welcome)
    else:
        print(welcome)

    while True:
        cwd = os.getcwd()

        try:
            if RICH:
                line = con.input(_prompt(user, host, cwd, mode))
            else:
                line = input(f"{user}@{host} {cwd.replace(Path.home(), '~')} % [{mode}] ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        raw = line.strip()
        if not raw:
            continue

        # Slash commands
        if raw in ("/exit", "/quit", "/q"):
            break
        if raw in ("/help", "/?"):
            _print_help()
            continue
        if raw in ("/bash", "/b"):
            if mode != "bash":
                _save_history(prev_mode)
                mode = "bash"
                prev_mode = "bash"
                _load_history("bash")
                if RICH:
                    con.print("[dim]→ [green]bash[/green] mode[/dim]")
                else:
                    print("→ bash mode")
            continue
        if raw in ("/ai", "/a"):
            if mode != "ai":
                _save_history(prev_mode)
                mode = "ai"
                prev_mode = "ai"
                _load_history("ai")
                if RICH:
                    con.print("[dim]→ [cyan]AI[/cyan] mode[/dim]")
                else:
                    print("→ AI mode")
            continue
        if raw.startswith("/"):
            if raw == "/listen":
                from .voice import listen_and_transcribe
                print("  Listening for 5s... (speak now)")
                voice_text = listen_and_transcribe(duration=5)
                if voice_text:
                    print(f"  You said: {voice_text}")
                    _handle_ai(voice_text, config)
                else:
                    print("  No speech detected.")
                continue
            print(f"Unknown: {raw}  (try /help)")
            continue

        # Dispatch
        if mode == "bash":
            _run_shell(raw)
        else:
            _handle_ai(raw, config)

    _save_history(mode)
