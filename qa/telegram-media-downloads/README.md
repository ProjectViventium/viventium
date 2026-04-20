# Telegram Media Downloads QA

## Purpose
Validate Telegram voice/video download handling, especially when Telegram rejects oversized media before transcription.

## Scope
- Telegram bridge media download classification
- user-facing Telegram media error contract
- canonical config/compiler wiring for optional local Telegram Bot API settings
- launcher parity for generated Telegram service env
- live local runtime restart and health

## Test Cases
1. Oversized Telegram media rejected by hosted Bot API maps to `file_too_large` instead of a generic retry-only download error.
2. Failed Telegram media download does not surface as `🎤 Transcription: error: ...`.
3. Canonical config fields under `integrations.telegram` compile to Telegram Bot API env vars.
4. Public runtime startup prefers generated `runtime/service-env/telegram.config.env` over legacy repo-local/private Telegram env files.
5. Local launcher startup does not hang on an unbounded `mongosh` ping when Mongo is already listening locally.
6. Live stack restarts cleanly and brings Telegram back after the launcher changes.

## Evidence Rules
- Use public-safe logs only.
- Do not include bot tokens, personal chat content, or private runtime secrets.
- Redact or omit user message bodies.
