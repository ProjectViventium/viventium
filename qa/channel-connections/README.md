# Channel Connections QA

## Scope

- Owning requirements: `docs/requirements_and_learnings/03_Telegram_Bridge.md` and
  `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`.
- User surfaces: Easy Install, Settings > Channels, the Custom Settings Telegram compatibility
  path, Telegram, Slack, and WhatsApp Business Cloud.
- Runtime owners: encrypted admin-managed browser records and in-process LibreChat workers for all
  three browser channels, plus the existing operator-managed Telegram adapter.

## Quality Bar

- Core browser chat is useful before any optional channel is connected.
- Browser-entered credentials use an authenticated AES-256-GCM envelope whose HKDF key domain is
  separated from other LibreChat credentials, and never enter browser storage, generated env files,
  logs, API responses, docs, or public evidence. Authentication failure and the unreleased
  unauthenticated legacy format fail closed to reconnect; they are never silently promoted to
  trusted ciphertext.
- Provider setup is admin-only; pairing is self-service for every authenticated user and can bind
  only to the signed-in account that created the one-use code.
- Credential validation, provider activation, worker readiness, and real message delivery are
  separate states. WhatsApp remains action-required until Meta verifies its public HTTPS callback.
- An optional channel failure never blocks install, first answer, restart, upgrade, or restore.
- Native channel-to-Agent delivery uses only the validated private API Unix socket and the existing
  signed gateway routes; missing/stale sockets remain retryable and never trigger loopback fallback.
- External acceptance uses dedicated synthetic accounts only.

## Required Suites

| Suite | Command or manual path | Required when |
| --- | --- | --- |
| Parent readiness | `tests/release/test_brain_readiness.py` | Readiness wording or ownership changes |
| Nested API and transport | Channel schema/admin/gateway/transport/webhook suites | Channel lifecycle or delivery changes |
| Built artifact | Production nested builds plus Native payload inspection | Before source changes are called shipped |
| Browser lifecycle | Easy Install > first chat > Settings > Channels > connect/test/restart/disconnect | Channel UI/API/persistence changes |
| Real channel delivery | Dedicated synthetic Telegram bot, Slack workspace, or Meta Business app | Before any transport is called Ready |
| Public-safety scan | QA/report and changed-diff scanners | Before public review |

## Evidence Rule

Record actual results in a dated report only after the exact combined artifact is exercised. Source
inspection, provider credential probes, mocks, and parent compiler tests do not substitute for a
headed lifecycle, restart persistence, or real synthetic inbound/outbound delivery.
