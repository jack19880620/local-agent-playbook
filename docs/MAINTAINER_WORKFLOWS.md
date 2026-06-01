# Maintainer Workflows

This project focuses on local-first maintainer automation. The examples are
small on purpose so maintainers can inspect the control flow and adapt it to
their own repositories.

## 1. Local Issue Triage

Goal: summarize a bug report, identify missing reproduction details, and draft
follow-up questions.

Relevant pieces:

- `engine/local-agent-engine.py`
- `memory-template/project/current.md`
- `memory-template/reference/`

## 2. Code Review Assistance

Goal: inspect a small patch or file, identify likely bugs, and produce a
reviewer-style checklist.

Relevant pieces:

- `examples/review-test.py`
- `examples/buggy-code.py`
- `tools/full-toolkit.py`

`examples/buggy-code.py` intentionally contains problems. It is a review target,
not a runnable example.

## 3. Release Checklist Generation

Goal: convert local project notes into a release checklist with verification
steps and rollback notes.

Relevant pieces:

- `memory-template/project/current.md`
- `docs/LOG.md`
- `engine/local-agent-engine.py`

## 4. Telegram Operator Approval

Goal: allow a trusted maintainer to ask for local diagnostics or summaries from
Telegram while keeping tokens outside git.

Relevant pieces:

- `engine/telegram-bot.py`
- `.env.example`
- `SECURITY.md`

## 5. Local Model Evaluation

Goal: compare local model behavior for tool calling, latency, and debugging
tasks before using a model in a maintainer workflow.

Relevant pieces:

- `data/test-results-20260403.md`
- `data/test-results-gemma4-20260403.md`
- `models/Modelfile.gemma4-agent`

## Future Work

- Add reproducible scripts for the model comparison logs.
- Add fixtures for issue triage and release checklist generation.
- Add tests for task classification and tool selection.
- Add a stricter command policy for shared or multi-user deployments.
