# Security Policy

This project demonstrates local AI agent workflows that can execute shell
commands and connect to Telegram. Treat it as automation infrastructure, not as
a toy script.

## Supported Versions

Security fixes are applied to the current `master` branch.

## Reporting a Vulnerability

Please open a GitHub issue with the label `security` if the report does not
contain secrets, private tokens, or exploit details that would put users at
risk.

If a report includes sensitive details, open a minimal public issue first and
state that private coordination is needed. Do not paste tokens, credentials,
cookies, private keys, or working exploit payloads into public issues.

## Secret Handling

- Never commit `.env` files.
- Use `.env.example` as the only committed configuration template.
- Rotate any token that may have been printed to logs or shared in a public
  place.
- Keep Telegram bot tokens and operator IDs in local environment variables.

## Runtime Boundaries

The local agent can execute shell commands through configured tools. Before
using this project in a shared or production-like environment:

- restrict the workspace directory,
- review the tool catalog,
- avoid running as an administrator or root user,
- keep Telegram access limited to trusted operators,
- inspect logs before sharing them publicly.

## Known Limitations

This repository is a reference implementation. It does not yet provide a full
sandbox, policy engine, or multi-user permission model.
