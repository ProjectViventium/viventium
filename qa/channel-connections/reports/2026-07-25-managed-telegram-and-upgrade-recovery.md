# Managed Telegram and Upgrade Recovery

Date: 2026-07-25
Status: PASS for the installed Custom Settings user path.

## Summary

This run closed the escaped Settings failures where an operator-managed Telegram installation could
appear unavailable or offer a second browser-owned setup path after upgrade. It also reran the real
Telegram text path because the installed bridge had recently produced slow or failed replies.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `CHANNEL-019` | PASS | Installed restart, exact TTL metadata, real Chrome, and refresh | Legacy index recovery is complete. |
| `CHANNEL-020` | PASS | Real Chrome, route regressions, Telegram Desktop, DB timestamps | Custom Settings ownership and delivery passed. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `CHANNEL-019` | Reopen Channels after upgrade/restart | Chrome Settings > Channels | PASS | Channel cards loaded and remained after refresh | TTL index metadata and readiness logs were healthy | None for the installed migration |
| `CHANNEL-020` | Inspect managed Telegram and exchange one turn | Chrome and Telegram Desktop | PASS | Managed badge, no duplicate actions, one exact reply | Route suite, bridge log, stored synthetic message timestamps | Slack/WhatsApp external delivery remains separately partial |

## Traceability

`channel ownership -> installer/runtime requirement -> established-user upgrade -> CHANNEL-019/020 -> truthful non-duplicate UI and one reply -> installed browser/Telegram evidence -> external Slack/WhatsApp matrix remains`

- Feature: connected messaging channels and operator-managed Telegram.
- Requirement: installer/compiler and Telegram bridge ownership contracts.
- Use case: upgrade, reopen Channels, refresh, and exchange one Telegram turn.
- QA case: `CHANNEL-019`, `CHANNEL-020`.
- Expected result: healthy migrated persistence, no duplicate ownership path, one delivered reply.
- Actual evidence: installed Chrome, Telegram Desktop, DB metadata, logs, and focused suites passed.
- Remaining gap or fix: dedicated external Slack and WhatsApp provider acceptance.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement and cases are proven? | PASS — installer/channel ownership contract; `CHANNEL-019/020`. |
| Code owning path | Which path owns behavior? | PASS — channel persistence migration, channel routes, Settings cards/pairing. |
| Docs and nested docs/repos | What defines expected behavior? | PASS — Telegram Bridge and Installer/Config Compiler requirements plus nested LibreChat route/UI. |
| Scripts or harnesses | What exercised it? | PASS — focused Jest/Vitest suites, production build, supported activation, desktop QA sender. |
| Local/external prerequisite state | What was healthy or degraded? | PASS — local API/web/scheduler/Telegram healthy; Slack/WhatsApp provider accounts not in scope. |
| Logs | What confirms the result? | PASS — sanitized bridge timestamps show one current success and historical provider rate limits. |
| DB/state/persistence | What persisted? | PASS — exact TTL option, no duplicate link rows/indexes, stored synthetic completion timestamp. |
| Generated/shipped artifact | What artifact was inspected? | PARTIAL — generated runtime state and running reviewed nested source passed; immutable public payload remains open. |
| Real user path | What was used like a user? | PASS — Chrome Settings and Telegram Desktop. |
| Visual/UX comparison | Does visible UX match? | PASS — responsive cards, managed badge, independent Slack/WhatsApp actions. |
| Not run / blocked | What remains? | PARTIAL — external Slack/WhatsApp delivery and immutable release artifact. |

## User-path evidence

| Use case | Result | Evidence |
| --- | --- | --- |
| Reopen Channels after installed upgrade and restart | PASS | A signed-in real Chrome session loaded availability and connected-channel state; refresh preserved it. |
| Distinguish operator-managed Telegram from browser-managed channels | PASS | Telegram showed `Managed by Custom Settings Install`, no pairing/connect/test/disconnect controls, and no claim that delivery health had been proven. Slack and WhatsApp retained their own setup actions. |
| Responsive Settings layout | PASS | Account and Channels had no page-level horizontal overflow at phone and desktop widths; all provider/channel actions stayed inside their cards. |
| Prevent duplicate operator/browser ownership | PASS | The API route regression returned the stable externally-managed conflict for Telegram mutations before credential or worker work. Eleven focused route tests passed. |
| Deliver a real Telegram response | PASS | Telegram Desktop sent one synthetic text prompt to the Viventium bot and visibly received one exact synthetic response. The stored assistant turn completed about 12.8 seconds after bridge receipt. |

## User-Grade Evidence

- Surface exercised: Chrome Settings > Channels and Telegram Desktop.
- Real user path: restart, open Channels, refresh, inspect Telegram ownership, send one synthetic bot prompt, and read the reply.
- Visible outcome: channel state loaded; Telegram was managed without duplicate controls; one exact reply arrived.
- Expanded/detail state: Telegram card and pairing region both showed Custom Settings ownership; Slack and WhatsApp retained setup actions.
- Persistence/reload result: Settings remained healthy after refresh and full runtime restart.
- Local/external prerequisite state: local API/web/scheduler/Telegram were healthy; prior rate limits were historical and absent from the current turn.
- Evidence retrieval classification, if applicable: historical provider rate limit; current request succeeded.
- Fallback path, if applicable: macOS desktop QA was the required real Telegram surface; no substitute was used.
- Backend/log/DB confirmation: TTL metadata, bridge receipt/completion timestamps, and one stored assistant turn matched the visible reply.
- Final model/runtime wording check: Settings does not claim Telegram delivery is healthy; it correctly delegates health to Custom Settings Install.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit tests supported but did not replace Chrome and Telegram Desktop evidence.

## Findings

The unavailable Channels page came from a legacy same-name/same-key Mongo index that lacked the
required TTL option. The in-place guarded migration repaired it without rewriting channel records.
The UI now derives operator ownership from structured runtime state and removes duplicate actions;
the API independently fails closed.

The prior Telegram delays were not polling failure in the repaired runtime. Historical bridge
evidence showed provider rate-limit failures, including a failed text turn and a failed voice turn.
After the runtime/component upgrade, the real synthetic text turn used the configured main agent,
returned once, and showed no rate-limit or bridge error. The measured result is a recovery proof,
not a claim that every future provider request will complete within the same latency.

## Automated Evidence

- Focused connected-account client tests: `45` passed.
- Focused connected-channel API route tests: `11` passed.
- Wider channel persistence and route tests: `29` passed.
- Production frontend build: passed.
- Installed scheduler MCP card: visibly `Connected` after restart.
- Secret safety: provider values were never printed or placed in tracked QA artifacts.

## Remaining external coverage

Slack and WhatsApp vendor-side delivery still require dedicated test accounts and provider approval.
Those external matrices remain tracked by their existing partial cases; they do not invalidate this
installed operator-managed Telegram pass.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
