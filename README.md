# aish — AI Shell

**Type natural language, run bash commands.**

aish is a zsh-like shell wrapper that lets you switch between normal bash mode and AI mode. In AI mode, type plain English and aish translates it to a bash command using your preferred LLM — showing you the command and asking for confirmation before execution.

```text
hycris@fedora ~ % [bash]      ← normal bash passthrough
hycris@fedora ~ % [ai]        ← AI mode: "find all python files larger than 1MB"
```

## Quick start

```bash
pip install aish

# Configure your provider
aish config

# Start the shell
aish
```

Or one-shot mode:
```bash
aish "show disk usage"
aish -y "update all packages"    # auto-confirm
```

## Features

- **Two modes** — `/ai` for natural language → command, `/bash` for normal bash
- **Multiple LLM providers** — DeepSeek, OpenAI, OpenRouter, Anthropic, Gemini, Ollama, llama.cpp, or any OpenAI-compatible endpoint
- **Safe execution** — shows the command and asks Y/n before running
- **Dangerous command detection** — extra red warning for risky operations
- **Self-learning** — remembers successful retries via `aish config learned`
- **Skills** — save multi-step workflows: `aish skill save deploy "setup nginx"`
- **Cron** — schedule recurring tasks: `aish cron add backup daily "tar -czf ..."`
- **History** — search past commands: `aish history nginx`
- **Memory** — user preferences inject into prompts: `aish remember "use dnf not apt"`
- **Voice input** — speak commands: `aish --listen` or `/listen` in shell
- **Multi-model fallback** — auto-retry with another provider if primary fails
- **Inline editing** — `e` to edit a command before running it
- **Zsh-like prompt** — user@host cwd % [mode]
- **History** — separate history for bash and AI modes

## Provider setup

```bash
# List available providers
aish config providers

# Quick provider switch
aish config set provider deepseek
aish config set model deepseek-chat

# Or set your API key
aish config set api-key sk-xxxxx

# Test it works
aish config test "list running docker containers"
```

Or set environment variables (auto-detected per provider):
```bash
export DEEPSEEK_API_KEY=sk-xxxxx
```

## Built-in providers

| Name | Default model | Description |
|------|--------------|-------------|
| `deepseek` | deepseek-chat | DeepSeek V3/V4 series |
| `openai` | gpt-4o-mini | OpenAI GPT-4o/mini |
| `openrouter` | qwen/qwen-2.5-coder-7b-instruct | 200+ models |
| `anthropic` | claude-3-haiku-20240307 | Claude Haiku/Sonnet/Opus |
| `gemini` | gemini-2.0-flash-exp | Google Gemini |
| `ollama` | qwen2.5-coder:7b | Local Ollama |
| `llamacpp` | Qwen3-0.6B-Q8_0 | Local llama.cpp server (default) |

## Commands

### Inside the shell

| Command | Action |
|---------|--------|
| `/bash` or `/b` | Switch to bash mode |
| `/ai` or `/a` | Switch to AI mode |
| `/listen` | Voice input (speak → transcribe → run) |
| `/exit` or `/q` | Quit |
| `/help` or `/?` | Show help |

### In AI mode

| Input | Action |
|-------|--------|
| `find large files` | → translated to `find / -size +100M` |
| `!git log --oneline` | Raw bash passthrough (no AI) |
| `/listen` | Record 5s of voice → transcribe → run |

### Config CLI

```bash
aish config                  # Interactive wizard
aish config show             # Current settings
aish config set provider deepseek
aish config set model deepseek-chat
aish config set base-url https://api.deepseek.com/v1
aish config set api-key sk-xxxxx
aish config providers        # List built-in providers
aish config test "show disk" # Quick API test
aish config learned          # Show auto-learned patterns
```

### Skills

```bash
aish skill list              # List saved workflows
aish skill save deploy "install nginx && enable nginx"
aish skill run deploy        # Execute saved workflow
aish skill delete deploy
```

### Cron

```bash
aish cron list               # Show scheduled jobs
aish cron add backup daily "tar -czf backup.tar.gz ~"
aish cron remove backup
```

### History

```bash
aish history                 # Recent commands
aish history nginx           # Search by keyword
aish history --stats         # Statistics
```

### Memory

```bash
aish remember "use dnf not apt"  # Save preference
aish remember                    # Show all memories
```

## Architecture

```text
User request
  ├─ Chat? → respond() (no command)
  ├─ Skill match? → run saved workflow
  ├─ Learned pattern? → fuzzy recall (auto-learned)
  ├─ Override rule? → regex (services/packages/git/docker)
  ├─ LLM generation (Qwen3-0.6B)
  │    └─ Guardrail retry → learns if succeeds
  └─ Danger scan → DANGEROUS: prefix if unsafe
```

## Install from source

```bash
git clone https://github.com/hycris/aish
cd aish
pip install .
```

## License

GNU Affero General Public License v3.0. See [LICENSE](LICENSE).
