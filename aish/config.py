"""Multi-provider configuration for aish.

Supports any OpenAI-compatible API endpoint.
Built-in provider presets for quick setup.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".config" / "aish"
CONFIG_FILE = CONFIG_DIR / "config.json"

# ── Provider presets ──────────────────────────────────────────────────────

@dataclass
class Provider:
    """A single LLM provider configuration."""
    name: str
    base_url: str
    model: str
    api_key_env: str  # env var name to check for the API key
    description: str = ""


BUILTIN_PROVIDERS = [
    Provider(
        name="deepseek",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        api_key_env="DEEPSEEK_API_KEY",
        description="DeepSeek (deepseek-chat, deepseek-v4-flash, etc.)",
    ),
    Provider(
        name="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        description="OpenAI (GPT-4o, GPT-4o-mini, etc.)",
    ),
    Provider(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        model="qwen/qwen-2.5-coder-7b-instruct",
        api_key_env="OPENROUTER_API_KEY",
        description="OpenRouter (route to 200+ models)",
    ),
    Provider(
        name="anthropic",
        base_url="https://api.anthropic.com/v1",
        model="claude-3-haiku-20240307",
        api_key_env="ANTHROPIC_API_KEY",
        description="Anthropic (Claude Haiku, Sonnet, Opus)",
    ),
    Provider(
        name="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        model="models/gemini-2.0-flash-exp",
        api_key_env="GEMINI_API_KEY",
        description="Google Gemini (via OpenAI-compat endpoint)",
    ),
    Provider(
        name="ollama",
        base_url="http://localhost:11434/v1",
        model="qwen2.5-coder:7b",
        api_key_env="OLLAMA_API_KEY",
        description="Local Ollama (qwen2.5-coder, llama3.1, etc.)",
    ),
    Provider(
        name="llamacpp",
        base_url="http://localhost:18098/v1",
        model="Qwen3-0.6B-Q8_0.gguf",
        api_key_env="",
        description="Local llama.cpp server — set port/model in 'aish config set'",
    ),
    Provider(
        name="custom",
        base_url="",
        model="",
        api_key_env="",
        description="Custom OpenAI-compatible endpoint",
    ),
]


# ── Config loading/saving ─────────────────────────────────────────────────

@dataclass
class AishConfig:
    """Runtime config."""
    provider: str = "llamacpp"
    api_key: str = ""
    base_url: str = "http://localhost:18098/v1"
    model: str = "Qwen3-0.6B-Q8_0.gguf"
    # Fallback provider for multi-model retry
    fallback_provider: str = ""
    fallback_base_url: str = ""
    fallback_model: str = ""
    fallback_api_key: str = ""


def load_config() -> AishConfig:
    """Load config from file + env, with fallback chain."""
    cfg = AishConfig()

    # 1) File
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            cfg.provider = data.get("provider", cfg.provider)
            cfg.api_key = data.get("api_key", cfg.api_key)
            cfg.base_url = data.get("base_url", cfg.base_url)
            cfg.model = data.get("model", cfg.model)
            cfg.fallback_provider = data.get("fallback_provider", cfg.fallback_provider)
            cfg.fallback_base_url = data.get("fallback_base_url", cfg.fallback_base_url)
            cfg.fallback_model = data.get("fallback_model", cfg.fallback_model)
            cfg.fallback_api_key = data.get("fallback_api_key", cfg.fallback_api_key)
        except (json.JSONDecodeError, OSError):
            pass

    # 2) Env override for api_key (NLSH_API_KEY takes priority)
    env_key = os.environ.get("NLSH_API_KEY") or ""
    if env_key:
        cfg.api_key = env_key
    elif not cfg.api_key:
        # 3) Auto-detect from provider presets + their env vars
        for p in BUILTIN_PROVIDERS:
            if p.name == cfg.provider and p.api_key_env:
                val = os.environ.get(p.api_key_env, "")
                if val:
                    cfg.api_key = val
                    break

    # 4) Also try Hermes .env fallback
    if not cfg.api_key:
        hermes_env = Path.home() / ".hermes" / ".env"
        if hermes_env.exists():
            for line in hermes_env.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith("DEEPSEEK_API_KEY="):
                    cfg.api_key = stripped.split("=", 1)[1].strip("\"'")
                    break

    return cfg


def save_config(cfg: AishConfig):
    """Persist config to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({
        "provider": cfg.provider,
        "api_key": cfg.api_key,
        "base_url": cfg.base_url,
        "model": cfg.model,
        "fallback_provider": cfg.fallback_provider,
        "fallback_base_url": cfg.fallback_base_url,
        "fallback_model": cfg.fallback_model,
        "fallback_api_key": cfg.fallback_api_key,
    }, indent=2))


def list_providers() -> list[Provider]:
    """Return built-in provider presets."""
    return BUILTIN_PROVIDERS


def get_provider(name: str) -> Optional[Provider]:
    """Get a built-in provider by name."""
    for p in BUILTIN_PROVIDERS:
        if p.name == name:
            return p
    return None
