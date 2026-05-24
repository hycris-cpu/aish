<p align="center">
  <img src="https://img.shields.io/badge/aish-AI%20Shell-00b4d8?style=for-the-badge&logo=gnubash&logoColor=white" alt="aish"/>
</p>

<h1 align="center">aish — AI Shell</h1>

<p align="center">
  <b>Type natural language, run bash commands.</b><br>
  Your Linux terminal, but you can just <i>say</i> what you need.
</p>

<p align="center">
  <a href="#quick-start"><img src="https://img.shields.io/badge/Quick%20Start-1a1a2e?style=flat-square"/></a>
  <a href="#features"><img src="https://img.shields.io/badge/Features-16213e?style=flat-square"/></a>
  <a href="#usage"><img src="https://img.shields.io/badge/Usage-0f3460?style=flat-square"/></a>
  <a href="#architecture"><img src="https://img.shields.io/badge/Architecture-e94560?style=flat-square"/></a>
  <a href="#license"><img src="https://img.shields.io/badge/License-533483?style=flat-square"/></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python"/>
  <img src="https://img.shields.io/badge/license-AGPL--3.0-purple?style=flat-square"/>
  <img src="https://img.shields.io/badge/voice-whisper.cpp-brightgreen?style=flat-square"/>
  <img src="https://img.shields.io/badge/local%20llm-llama.cpp-orange?style=flat-square"/>
</p>

---

```text
hycris@fedora ~ % [bash]      ← normal bash passthrough
hycris@fedora ~ % [ai]        ← AI mode
[ai] show disk space          → df -h
[ai] find all python files    → find . -type f -name "*.py"
[ai] kill process named nginx → pkill nginx
[ai] /listen                  → speak: "install nginx"
```

---

## Quick Start

```bash
pip install aish
aish config                      # pick your LLM provider
aish "show disk space"           # one-shot mode
aish -y "update all packages"    # auto-confirm
aish                             # interactive shell
```

**Built on a 0.6B model** — 610 MB Q8_0, runs instantly on any hardware.

**No cloud? No problem.** aish works with local models too:

```bash
# Start a local llama.cpp server with any GGUF model
llama-server -m Qwen3-0.6B-Q8_0.gguf --port 18098

# Point aish at it
aish config set provider llamacpp
aish "find all files larger than 100MB"
```

---

## Features

### 🧠 Natural Language → Bash
```text
"show me the 5 largest files"       → du -sh * | sort -rh | head -5
"what's listening on port 8080"     → ss -tlnp | grep :8080
"compress my project into tar.gz"   → tar -czf project.tar.gz myproject
```

### 🗣️ Voice Input
```text
aish --listen       # record 5s → transcribe → run
# or inside the shell:
[ai] /listen        # speak: "show disk space" → done
```

Powered by **whisper.cpp** tiny.en — **28 MB**, runs on CPU.

### 🔐 Safety First
- **Danger detection** — `rm -rf /`, `mkfs`, `dd` get a `DANGEROUS:` prefix
- **Confirm before running** — always shows the command, asks Y/n
- **Edit before execute** — press `e` to edit the command

### 📚 Self-Learning
aish remembers when it fixes mistakes:
```text
[ai] show memory usage
  → ps -ex | grep "memory"      (wrong — retry)
  → free -h                      (correct — LEARNED)
```
Next time: `aish config learned` shows the pattern, instantly recalled.

### ⚡ Skills — Save Workflows
```bash
aish skill save deploy "install nginx && enable nginx"
aish skill run deploy          # runs both commands
```

### ⏰ Cron — Schedule Tasks
```bash
aish cron add backup daily "tar -czf backup.tar.gz ~/projects"
aish cron list
```

### 📜 History — Search Past Commands
```bash
aish history                    # recent commands
aish history nginx              # search by keyword
```

### 🧠 Memory — Your Preferences
```bash
aish remember "use dnf not apt"
# Injected into every LLM prompt automatically
```

### 🔁 Multi-Model Fallback
```bash
aish config set fallback-provider deepseek
aish config set fallback-model deepseek-chat
# If local model fails, auto-retry with cloud
```

---

## Usage

### One-shot mode

```bash
aish "show disk space"
aish -y "update all packages"         # auto-confirm
aish --listen                          # voice input
```

### Interactive shell

```bash
aish                          # start in bash mode
aish --ai                     # start in AI mode
```

Inside the shell:

| Command | Action |
|---------|--------|
| `find large files` | → bash command |
| `!git log --oneline` | Raw bash (no AI) |
| `/ai` or `/a` | Switch to AI mode |
| `/bash` or `/b` | Switch to bash mode |
| `/listen` | Voice input (5s) |
| `/exit` or `/q` | Quit |
| `/help` or `/?` | Show help |

### Config

```bash
aish config                    # Interactive wizard
aish config show               # Current settings
aish config set provider deepseek
aish config set model deepseek-chat
aish config set base-url https://api.deepseek.com/v1
aish config set api-key <your-key>
aish config providers          # List built-in providers
aish config test "show disk"   # Quick API test
aish config learned            # Show auto-learned patterns
```

### Built-in providers

| Name | Default model | Description |
|------|--------------|-------------|
| `deepseek` | deepseek-chat | DeepSeek V3/V4 series |
| `openai` | gpt-4o-mini | OpenAI GPT-4o/mini |
| `openrouter` | qwen/qwen-2.5-coder-7b-instruct | 200+ models |
| `anthropic` | claude-3-haiku-20240307 | Claude Haiku/Sonnet/Opus |
| `gemini` | gemini-2.0-flash-exp | Google Gemini |
| `ollama` | qwen2.5-coder:7b | Local Ollama |
| `llamacpp` | Qwen3-0.6B-Q8_0 | Local llama.cpp server |

---

## Architecture

```text
User request
  │
  ├─ Chat-only?  → respond()      (greetings, thanks)
  │
  ├─ Skill?      → run workflow    (saved multi-step)
  │
  ├─ Learned?    → fuzzy recall    (auto-learned patterns)
  │
  ├─ Override?   → regex match     (services, packages, git, docker)
  │
  └─ LLM         → Qwen3-0.6B     (raw generation)
       │
       ├─ Guardrail retry → learn  (catches ERROR output)
       │
       ├─ Multi-model fallback     (try another provider)
       │
       └─ Danger scan             (DANGEROUS: prefix)
```

### Stack

| Component | Size | Role |
|-----------|------|------|
| **Qwen3-0.6B** (default) | **610 MB** Q8_0 | NL→Bash translation engine |
| **whisper tiny.en** (optional) | 28 MB | Voice→Text |
| **llama.cpp** | — | Local inference server |
| **aish** (Python) | 436 KB | CLI + harness + tools |

---

## Install from source

```bash
git clone https://github.com/hycris-cpu/aish
cd aish
pip install .
```

## Requirements

- Python 3.10+
- A running LLM backend (built-in: llama.cpp, free: DeepSeek API)

## License

**GNU Affero General Public License v3.0** — see [LICENSE](LICENSE).

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License. Use it, modify it, share it — but if you run it as a network service, you must share your source too.
