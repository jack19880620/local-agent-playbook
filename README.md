# Local AI Agent Playbook

Local AI Agent Playbook is a small, local-first reference implementation for
building inspectable AI agents on top of Ollama, Python, shell tools, Telegram,
and simple file-based memory.

The project is intentionally lightweight. It is designed for maintainers and
independent developers who want to study and adapt agent workflows without
starting from a hosted platform or a large framework.

## What This Repository Includes

- `engine/local-agent-engine.py` - the main local agent runtime.
- `engine/telegram-bot.py` - a Telegram control layer for a local agent.
- `engine/factory-watchdog.sh` - a shell watchdog for long-running local runs.
- `memory-template/` - project, user, reference, and feedback memory folders.
- `models/Modelfile.gemma4-agent` - an example Ollama model configuration.
- `examples/` - small files for code review and debugging demonstrations.
- `data/` - experiment notes and local model comparison logs.
- `docs/LOG.md` - development notes from local agent experiments.
- `.env.example` - environment variables required by the Telegram bridge.

See `docs/MAINTAINER_WORKFLOWS.md` for concrete workflows this repository is
intended to support.

## Why It Exists

Most AI coding-agent examples either depend on a hosted service or hide too much
of the execution loop. This repository keeps the loop visible:

1. classify the task,
2. select a small set of tools,
3. run the model locally,
4. execute only explicit tool calls,
5. compress noisy tool output,
6. preserve lightweight memory,
7. report results back through a local or Telegram interface.

That makes it useful for learning, debugging, and adapting maintainer
automation workflows such as issue triage, code review, release checklists,
local diagnostics, and operator-approved automation.

## Quick Start

Install Ollama and pull a local model:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3.5:9b
```

Run the core engine:

```bash
python3 engine/local-agent-engine.py "summarize this repository"
```

Optional Telegram bridge:

```bash
cp .env.example .env
# Edit .env with your own bot token and operator ID.
python3 engine/telegram-bot.py
```

Do not commit `.env` or runtime logs. Tokens belong only in your local
environment.

## Verified Scope

The core engine and Telegram bridge are kept syntactically valid with the CI
workflow in this repository. Some files under `examples/` are intentionally
buggy inputs for review tasks and should not be treated as runnable examples.

Local model behavior varies by hardware, Ollama version, and model family. The
files in `data/` are experiment logs, not benchmark claims.

## Maintainer Automation Use Cases

This project is most useful as a base for:

- local pull request review helpers,
- issue and bug triage assistants,
- release checklist generation,
- repo health checks,
- Telegram-based operator approval flows,
- memory-backed local developer agents,
- experiments comparing local model behavior.

## Safety Model

The runtime is intentionally explicit: tools are listed in code, secrets are
loaded from environment variables, and the Telegram bot accepts commands only
from the configured operator ID. Review `SECURITY.md` before adapting the
project for a shared environment.

## Development

Run the lightweight syntax check used by CI:

```bash
python -m py_compile \
  my-agent.py \
  engine/local-agent-engine.py \
  engine/telegram-bot.py \
  tools/full-toolkit.py
```

The intentionally broken examples are excluded from this command.

Please read `CONTRIBUTING.md` before opening a pull request and `SECURITY.md`
before adapting the Telegram or shell-tool pieces.

## Roadmap

- Add unit tests around task classification and tool selection.
- Add safer command execution policies for shared deployments.
- Improve experiment logs into reproducible benchmark scripts.
- Add a threat model for Telegram and shell-tool automation.
- Document more maintainer workflows using this runtime.

## License

Code is released under the MIT License. See `LICENSE`.
