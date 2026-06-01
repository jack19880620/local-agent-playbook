# Contributing

Thanks for improving Local AI Agent Playbook.

## Good First Contributions

- Improve documentation and examples.
- Add tests around task classification and tool selection.
- Add safer execution policies for shell tools.
- Convert experiment notes into reproducible scripts.
- Improve Telegram operator approval flows.

## Development Setup

Install Python 3.8+ and Ollama. Copy local environment settings from the
example file:

```bash
cp .env.example .env
```

Never commit `.env`.

Run the syntax check before opening a pull request:

```bash
python -m py_compile \
  my-agent.py \
  engine/local-agent-engine.py \
  engine/telegram-bot.py \
  tools/full-toolkit.py
```

Files under `examples/` may intentionally contain bugs for review tasks and are
not part of the syntax check.

## Pull Request Guidelines

- Keep changes small and focused.
- Explain the maintainer workflow or safety improvement.
- Include tests or a manual verification note.
- Do not commit secrets, local logs, private conversations, cookies, API keys,
  or generated runtime state.

## Code Style

Prefer boring Python and explicit control flow. This repository is meant to be
read and adapted by people learning how local agents work.
