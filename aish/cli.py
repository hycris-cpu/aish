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
    # Manual dispatch: handle `aish config ...` vs one-shot text
    # without argparse subparser conflicts
    if len(sys.argv) > 1 and sys.argv[1] == "config":
        args = sys.argv[2:]
        # Build config parser
        cp = argparse.ArgumentParser(prog="aish config")
        cp.add_argument("config_cmd", nargs="?",
                        choices=["show", "set", "providers", "test", "learned"],
                        help="Config subcommand (omit for wizard)")
        cp.add_argument("key", nargs="?", help="Config key")
        cp.add_argument("value", nargs="?", help="Config value")
        cp.add_argument("--text", "-t", default=None, help="Test text")
        pargs = cp.parse_args(args)
        # Wrap in a namespace-like object for compatibility
        cmd_config(pargs)
        return

    parser = argparse.ArgumentParser(
        prog="aish",
        description="AI Shell — type natural language, run bash commands",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              aish                          Interactive shell (bash mode)
              aish --ai                     Interactive shell (AI mode)
              aish "find large files"       One-shot: translate + run
              aish config show              Show current config
              aish config set provider deepseek
              aish config set model deepseek-chat
              aish config test "show disk usage"

            Providers built-in:
              deepseek, openai, openrouter, anthropic, gemini, ollama, llamacpp

            Environment variables:
              NLSH_API_KEY          API key (takes priority)
              DEEPSEEK_API_KEY      Auto-detected for deepseek provider
              OPENAI_API_KEY        Auto-detected for openai provider
              OPENROUTER_API_KEY    Auto-detected for openrouter provider
              etc. per provider
        """),
    )
    parser.add_argument(
        "--version", action="version", version=f"aish {__version__}"
    )
    parser.add_argument("--ai", action="store_true",
                        help="Start in AI mode (instead of bash mode)")
    parser.add_argument("text", nargs="*",
                        help="Natural language input (one-shot mode)")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Auto-confirm command execution")

    args = parser.parse_args()

    # One-shot mode: positional text given
    if args.text:
        cmd_one_shot(args)
        return

    # Interactive shell
    cfg = load_config()
    
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

    run_shell(cfg, start_ai=args.ai)


if __name__ == "__main__":
    main()
