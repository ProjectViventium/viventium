# Telegram Local Bot API QA

## Purpose
Validate the supported product path for Telegram large-media downloads when Viventium manages a
same-Mac local `telegram-bot-api` service.

## Scope
- canonical config for `integrations.telegram.local_bot_api`
- compiler output for Telegram local Bot API env and Telegram media-size policy
- preflight detection for `telegram-bot-api`, `api_id`, and `api_hash`
- launcher lifecycle for the local `telegram-bot-api` service
- Telegram bot local-mode wiring

## Acceptance Contract
1. Hosted Telegram mode still fails oversized media honestly without leaking `error:` transcript text.
2. Enabling `integrations.telegram.local_bot_api` creates one owning path for the feature:
   config -> compiler -> generated Telegram env -> preflight -> launcher -> Telegram bot.
3. Managed local Bot API mode must not silently fall back to hosted Telegram if the local server
   is configured but missing or broken.
4. Telegram media size policy must come from canonical config, with a documented higher default in
   managed local Bot API mode.
5. QA reports must distinguish code readiness from live credential/operator readiness.

## Evidence Rules
- Keep all evidence public-safe.
- Do not record Telegram bot tokens, Telegram API hashes, private chats, or local attachment files.
- If live end-to-end validation is blocked by missing operator credentials, record that explicitly.
