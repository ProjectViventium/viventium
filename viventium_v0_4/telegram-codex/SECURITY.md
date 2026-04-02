# Security Policy

## Supported builds

This project is intended for local, owner-controlled use. Treat it as
security-sensitive because it can execute local Codex tasks against local
workspaces.

## Reporting a vulnerability

- Do not open a public issue for vulnerabilities, secrets, or local-execution risks.
- Prefer GitHub Security Advisories / private vulnerability reporting once the repository enables it.
- If private reporting is not available, contact a Project Viventium maintainer through a private channel.

## Security boundaries

- Pairing is localhost-only by default.
- Access is restricted to a paired Telegram user id after bootstrap pairing.
- Telegram Bot API does not reveal which client device sent a message.
- This means the bot can bind to a Telegram account, but not cryptographically to one Telegram app or laptop.

## Secret handling

- Never commit `.env`, real bot tokens, or populated `config/settings.yaml` / `config/projects.yaml`.
- Keep runtime state under `runtime/` and keep it untracked.

