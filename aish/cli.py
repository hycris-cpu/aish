"""Command-line interface for aish — shell and config management."""

from __future__ import annotations

import argparse
import textwrap
import sys

from . import __version__
from .config import (
    AishConfig, load_config, save_config,
    list_providers, get_provider, BUILTIN_PROVIDERS,
)
from .shell import run_shell
from .llm import translate


def _mask_key(key: str) -> str:
    if len(key) > 10:
        return key[:6] + "..." + key[-4:]
    return "(not set)"


def cmd_config(args):
    """Handle `aish config *` subcommands."""
    cfg = load_config()
    from .config import BUILTIN_PROVIDERS as BP

    if args.config_cmd == "show":
        provider = get_provider(cfg.provider)
        desc = provider.description if provider else "(custom)"
        print(f"Provider:      {cfg.provider}  ({desc})")
        print(f"Base URL:      {cfg.base_url}")
        print(f"Model:         {cfg.model}")
        print(f"API Key:       {_mask_key(cfg.api_key)}")
        return

    if args.config_cmd == "set":
        if args.key == "api-key":
            if not args.value:
                print("Usage: aish config set api-key <your-api-key>")
                sys.exit(1)
            cfg.api_key = args.value
        elif args.key == "api_key":
            cfg.api_key = args.value
        elif args.key in ("base-url", "base_url"):
            cfg.base_url = args.value
        elif args.key == "model":
            cfg.model = args.value
        elif args.key == "provider":
            # Look up provider preset
            provider = get_provider(args.value)
            if provider:
                cfg.provider = provider.name
                cfg.base_url = provider.base_url
                cfg.model = provider.model
                # Try env var for key
                if provider.api_key_env:
                    import os
                    env_val = os.environ.get(provider.api_key_env, "")
                    if env_val and not cfg.api_key:
                        cfg.api_key = env_val
            else:
                # Custom provider — just set name, URL+model must be set separately
                cfg.provider = args.value
        else:
            print(f"Unknown config key: {args.key}")
            print("Valid keys: provider, base-url, model, api-key")
            sys.exit(1)

        save_config(cfg)
        print(f"✓ {args.key} updated")
        return

    if args.config_cmd == "providers":
        print(f"{'Name':<18} {'Model':<35} Description")
        print("-" * 90)
        for p in BP:
            print(f"{p.name:<18} {p.model:<35} {p.description}")
        return

    if args.config_cmd == "test":
        text = args.text or "list files"
        command, err = translate(
            text, cfg.api_key, cfg.base_url, cfg.model
        )
        if err:
            print(f"✗ {err}")
            sys.exit(1)
        print(f"> {text}")
        print(f"  {command}")
        return

    if args.config_cmd == "learned":
        from .learn import list_learned, stats
        patterns = list_learned()
        s = stats()
        print(f"Learned patterns: {s['total']} (total hits: {s['total_hits']})")
        print("-" * 60)
        for p in sorted(patterns, key=lambda x: x.get("hits", 0), reverse=True):
            print(f"  [{p.get('hits', 0):3d}] {p['input'][:50]:50s} → {p['command'][:50]}")
        return

    if args.config_cmd in ("memory", "remember"):
        from .memory import list_all, add, remove, clear
        sub = getattr(args, 'key', None)
        val = getattr(args, 'value', None)
        if sub == "show" or not sub:
            print("Aish memories:")
            for m in list_all():
                print(f"  • {m['fact']}")
        elif sub == "add" and val:
            add(val)
            print(f"✓ Remembered: {val}")
        elif sub == "remove" and val:
            if remove(val):
                print(f"✓ Forgotten: {val}")
            else:
                print(f"Not found: {val}")
        elif sub == "clear":
            clear()
            print("✓ All memories cleared")
        return

    # Interactive wizard
    print("aish configuration (press Enter to keep current)\n")
    try:
        print("Available providers:")
        for p in BP:
            print(f"  {p.name:<16} {p.description}")
        print()
        provider = input(f"Provider [{cfg.provider}]: ").strip()
        if provider:
            p = get_provider(provider)
            if p:
                cfg.provider = p.name
                cfg.base_url = p.base_url
                cfg.model = p.model
                print(f"  → preset loaded: {p.base_url}, model={p.model}")
            else:
                cfg.provider = provider

        bu = input(f"Base URL [{cfg.base_url}]: ").strip()
        if bu:
            cfg.base_url = bu
        m = input(f"Model [{cfg.model}]: ").strip()
        if m:
            cfg.model = m
        key = input("API key: ").strip()
        if key:
            cfg.api_key = key
        save_config(cfg)
        print(f"\n✓ Saved to ~/.config/aish/config.json")
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)


def cmd_one_shot(args):
    """Handle one-shot mode: `aish <nl text>`."""
    cfg = load_config()
    text = " ".join(args.text)
    command, err = translate(text, cfg.api_key, cfg.base_url, cfg.model)
    if err:
        print(f"✗ {err}")
        sys.exit(1)

    if command.startswith("ERROR:"):
        print(f"✗ {command[6:].strip()}")
        sys.exit(1)

    is_dangerous = command.startswith("DANGEROUS:")
    if is_dangerous:
        command = command[len("DANGEROUS:"):].strip()
        print("⚠ DANGEROUS")

    print(f"  {command}")
    if args.yes:
        # Auto-run
        from .shell import _run_shell as run
        rc = run(command)
        sys.exit(rc)

    ans = input("Run? (Y/n) ").strip().lower() or "y"
    if ans in ("y", "yes", ""):
        from .shell import _run_shell as run
        rc = run(command)
        sys.exit(rc)


def main():
    # Manual dispatch: handle `aish config ...` etc. vs one-shot text
    args_list = sys.argv[1:] if len(sys.argv) > 1 else []

    if not args_list:
        # Interactive shell
        cfg = load_config()
        _check_key_and_run(cfg, start_ai=False)
        return

    cmd = args_list[0]

    if cmd == "config":
        # Build config parser
        cp = argparse.ArgumentParser(prog="aish config")
        cp.add_argument("config_cmd", nargs="?",
                        choices=["show", "set", "providers", "test", "learned", "memory", "remember"],
                        help="Config subcommand (omit for wizard)")
        cp.add_argument("key", nargs="?", help="Config key")
        cp.add_argument("value", nargs="?", help="Config value")
        cp.add_argument("--text", "-t", default=None, help="Test text")
        pargs = cp.parse_args(args_list[1:])
        cmd_config(pargs)
        return

    elif cmd == "skill":
        # Skill commands
        sub = args_list[1] if len(args_list) > 1 else "list"
        if sub == "list":
            from .skill import list_skills
            skills = list_skills()
            if not skills:
                print("No skills saved.")
                return
            print(f"{'Name':<20} {'NL Input':<40} {'Command':<40} {'Hits':<6}")
            print("-" * 110)
            for s in skills:
                print(f"{s['name']:<20} {s.get('nl_input','')[:38]:<40} {s['command'][:38]:<40} {s.get('hits',0):<6}")
        elif sub == "save" and len(args_list) >= 3:
            name = args_list[2]
            nl = " ".join(args_list[3:]) or name
            # Use one-shot translation to get the command, then save
            cfg = load_config()
            from .llm import translate
            from .skill import save as skill_save
            if len(args_list) > 3 and args_list[3] != "--cmd":
                cmd_text, err = translate(nl, cfg.api_key, cfg.base_url, cfg.model)
                if err or not cmd_text:
                    print(f"✗ Could not translate: {err}")
                    return
                result = skill_save(name, nl, cmd_text)
                print(f"✓ {result}")
                print(f"  Command: {cmd_text}")
            else:
                # --cmd flag: direct command save
                cmd_text = " ".join(args_list[4:]) if len(args_list) > 4 else input("Command: ")
                result = skill_save(name, nl, cmd_text)
                print(f"✓ {result}")
        elif sub == "run" and len(args_list) >= 3:
            from .skill import run as skill_run
            cmd = skill_run(args_list[2])
            if cmd:
                from .shell import _run_shell as run
                print(f"  {cmd}")
                run(cmd)
            else:
                print(f"✗ Skill '{args_list[2]}' not found")
        elif sub == "delete" and len(args_list) >= 3:
            from .skill import delete as skill_delete
            if skill_delete(args_list[2]):
                print(f"✓ Deleted skill '{args_list[2]}'")
            else:
                print(f"✗ Skill '{args_list[2]}' not found")
        else:
            print("Usage: aish skill [list|save <name> [nl]|run <name>|delete <name>]")
        return

    elif cmd == "cron":
        sub = args_list[1] if len(args_list) > 1 else "list"
        if sub == "list":
            from .cron import list_jobs
            jobs = list_jobs()
            if not jobs:
                print("No scheduled jobs.")
                return
            import time
            print(f"{'Name':<20} {'Command':<30} {'Schedule':<15} {'Next Run':<25}")
            print("-" * 95)
            for j in jobs:
                next_t = j.get('next_run', 0)
                next_str = time.ctime(next_t) if next_t else "N/A"
                print(f"{j['name']:<20} {j['command'][:28]:<30} {j.get('schedule',''):<15} {next_str:<25}")
        elif sub == "add" and len(args_list) >= 4:
            from .cron import add as cron_add
            name = args_list[2]
            sched = args_list[3]
            cmd_text = " ".join(args_list[4:]) if len(args_list) > 4 else input("Command: ")
            result = cron_add(name, cmd_text, sched)
            print(f"✓ {result}")
        elif sub == "remove" and len(args_list) >= 3:
            from .cron import remove as cron_remove
            if cron_remove(args_list[2]):
                print(f"✓ Removed job '{args_list[2]}'")
            else:
                print(f"✗ Job '{args_list[2]}' not found")
        else:
            print("Usage: aish cron [list|add <name> <schedule> <command>|remove <name>]")
        return

    elif cmd == "history":
        query = " ".join(args_list[1:]) if len(args_list) > 1 else ""
        from .history import search, recent, stats
        if query in ("--clear", "clear"):
            from .history import clear as hist_clear
            hist_clear()
            print("✓ History cleared")
            return
        if query in ("--stats", "stats"):
            s = stats()
            print(f"Total commands: {s['total']}")
            print(f"Unique commands: {s['unique_commands']}")
            return
        if query:
            results = search(query)
        else:
            results = recent(20)
        if not results:
            print("No history found.")
            return
        import time
        for r in results:
            ts = time.strftime("%H:%M:%S", time.localtime(r['time']))
            cmd = r['command'][:60]
            nl = r.get('nl_input', '')
            nl_s = f"[{nl[:30]}] " if nl else ""
            print(f"  {ts} {nl_s}{cmd}")
        return

    elif cmd == "remember":
        fact = " ".join(args_list[1:])
        if fact:
            from .memory import add as mem_add
            mem_add(fact)
            print(f"✓ Remembered: {fact}")
        else:
            from .memory import list_all
            mems = list_all()
            if not mems:
                print("No memories saved. Use: aish remember <fact>")
            else:
                print("Aish memories:")
                for m in mems:
                    print(f"  • {m['fact']}")
        return

    # One-shot mode: positional text given
    cfg = load_config()
    # Check for -y flag (auto-confirm)
    auto_yes = "-y" in args_list or "--yes" in args_list
    text_parts = [a for a in args_list if not a.startswith("-")]
    
    if text_parts:
        # Call one-shot with args
        class MockArgs:
            def __init__(self, text, yes):
                self.text = text
                self.yes = yes
        cmd_one_shot(MockArgs(text=text_parts, yes=auto_yes))
    else:
        # Check --ai flag
        start_ai = "--ai" in args_list
        if "--version" in args_list:
            from . import __version__
            print(f"aish {__version__}")
            return
        _check_key_and_run(cfg, start_ai=start_ai)
    return


def _check_key_and_run(cfg, text="", start_ai=False):
    """Check API key and run shell or one-shot."""
    # Skip API key check for local providers (no api_key_env)
    from .config import get_provider, BUILTIN_PROVIDERS
    needs_key = any(
        p.name == cfg.provider and p.api_key_env != ""
        for p in BUILTIN_PROVIDERS
    ) or not any(
        p.name == cfg.provider
        for p in BUILTIN_PROVIDERS
    )
    if needs_key and not cfg.api_key:
        print("✗ No API key configured.")
        print("  Run:  aish config")
        print("  Or set env: export NLSH_API_KEY=<your-key>")
        sys.exit(1)

    if text:
        args = type('Args', (), {'text': text.split(), 'yes': False})()
        cmd_one_shot(args)
    else:
        run_shell(cfg, start_ai=start_ai)


if __name__ == "__main__":
    main()
