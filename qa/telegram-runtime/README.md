# Telegram Runtime QA

## Scope

This folder is the public-safe QA home for Telegram bridge and Telegram Codex runtime health. It
covers startup, restart, status reporting, polling-conflict detection, provider-auth failure
wording, and local evidence checks.

## Public-Safe Evidence Rules

- Do not include BotFather tokens, chat IDs, Telegram usernames, personal message content, local
  usernames, hostnames, or raw App Support paths.
- Use synthetic log snippets in automated tests.
- Summarize local live evidence by outcome and status class only.
- Keep private runtime logs, databases, and account screenshots outside this repo.

## Acceptance Contract

Telegram runtime changes are accepted only when:

1. `bin/viventium status` reports `Running with issues` or `Action Required` for known recoverable
   Telegram problems instead of claiming healthy `Running`.
2. Restart flows stop scoped Telegram Codex orphan processes before launching a new sidecar.
3. Public QA artifacts describe what was checked without leaking private Telegram or account data.
4. Real local runtime checks support the status wording, with any external-message test performed
   only when a user explicitly allows cloud interaction.
