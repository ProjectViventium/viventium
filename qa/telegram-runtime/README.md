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
2. Restart flows stop only receipt-backed, revalidated Telegram pollers; PID reuse and unknown
   processes are left untouched, and interrupted cross-checkout handoffs restore the recognized
   predecessor when its owner-only launch descriptor is safe.
3. Public QA artifacts describe what was checked without leaking private Telegram or account data.
4. Real local runtime checks support the status wording, with any external-message test performed
   only when a user explicitly allows cloud interaction.
5. Repeated delivery-dependency failures use capped backoff and deduplicated logs while successful
   empty-ledger polling returns to the normal reply-delivery interval.
