# Existing-User Upgrade and Settings Continuity

Date: 2026-07-25
Status: PARTIAL — the installed source-candidate path passed; universal public release gates remain.

## Summary

An established personalized Custom Settings installation now runs the exact reviewed local parent
and LibreChat component. The supported validation/activation/restart completed, API/web/scheduler
health probes passed, and the signed-in browser session survived.

After removing only the synthetic QA turn and its causally timestamped derived state with guarded
compare-and-swap restoration, the final complete snapshot matched the pre-activation snapshot across
all `22` recoverable Mongo collections. Canonical config and the complete schedules database were
also byte-identical. This includes users, conversations, messages, saved memory, feeling state,
files, agents, agent categories, public prompts/prompt groups, and the remaining snapshot-safe
collections.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `INST-034` | PARTIAL | Installed activation, complete snapshot equality, Chrome, Telegram Desktop, focused suites | Local source upgrade passed; immutable public release gates remain. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `INST-UC-020` | Upgrade, restart, inspect Accounts/Channels/scheduler, send one Telegram turn, then clean QA state | Supported activation, Chrome, Telegram Desktop, CLI | PARTIAL | Signed-in session, saved providers, managed Channels, connected scheduler, delivered reply | Exact safe-collection/config/schedule equality and parent/component identity | Signed/notarized immutable payload and clean physical/Intel matrix |

## Traceability

`existing-user upgrade -> Installer and Config Compiler requirement -> preserve personalized runtime -> INST-034 / INST-UC-020 -> exact state and healthy visible surfaces -> installed activation/browser/Telegram/snapshot evidence -> immutable release gates remain`

- Feature: established-user universal upgrade continuity.
- Requirement: Installer and Config Compiler existing-user preservation contract.
- Use case: activate reviewed code, restart, verify user surfaces, and prove no state drift.
- QA case: `INST-034`, `INST-UC-020`.
- Expected result: exact reviewed runtime with unchanged user-owned state and truthful integrations.
- Actual evidence: installed source path passed with exact recoverable-state equality.
- Remaining gap or fix: exact immutable signed artifact and physical compatibility/failure matrix.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement and cases are proven? | PASS — Installer/Config Compiler; `INST-034`, `INST-UC-020`. |
| Code owning path | Which path owns behavior? | PASS — snapshot, activation/restart, compiler/runtime state, nested Settings/routes. |
| Docs and nested docs/repos | What defines expected behavior? | PASS — Installer, Telegram, runtime QA map, continuity operations, and nested LibreChat source. |
| Scripts or harnesses | What exercised it? | PASS — public CLI, continuity snapshots, A/B/C agent compare, Chrome, Telegram sender, release/nested suites. |
| Local/external prerequisite state | What was healthy or degraded? | PASS — core API/web/scheduler/Telegram healthy; historical scheduler/memory receipts retained. |
| Logs | What confirms or contradicts? | PASS — startup and bridge evidence confirmed current health; prior rate limits and historical delivery failures remain explicit. |
| DB/state/persistence | What persisted? | PASS — all `22` recoverable collection fingerprints, config, and schedules matched after guarded cleanup. |
| Generated/shipped artifact | What artifact was inspected? | PARTIAL — running reviewed source and component pin passed; immutable signed payload was not rebuilt. |
| Real user path | What was used like a user? | PASS — supported activation/CLI, signed-in Chrome Settings, Telegram Desktop. |
| Visual/UX comparison | Does visible UX match? | PASS — installed Account, Channels, and scheduler plus phone/desktop geometry. |
| Not run / blocked | What remains? | PARTIAL — notarization/Gatekeeper, pristine physical/Intel, wider interruption matrix. |

## Acceptance matrix

| Surface | Result | Evidence |
| --- | --- | --- |
| Exact running code | PASS | Supported activation validated and restarted the selected source checkout; parent lock and native payload manifest point to the reviewed nested commit. |
| Config and schedules | PASS | Pre/final canonical config and schedule database SHA-256 values were identical. |
| Chats, memory, files, feelings, agents, prompts | PASS | All `22` recoverable logical collection counts and hashes were identical after QA cleanup. |
| Protected local agent customization | PASS | Read-only A/B/C compare still reported live drift on `13` agents, including instruction/model/tool/background-cortex fields; no sync or push was applied. Pre/final agent collection hashes were identical. |
| Provider credentials | PASS | OpenAI and Anthropic remained saved. Groq and xAI values were recovered from owner-only local backup state under explicit user authorization and stored persistently; refresh, restart, UI state, and secret-free DB metadata confirmed both. Values were never printed or tracked. |
| Settings responsive layout | PASS | Real Chrome at phone and desktop widths showed no page overflow and kept every account/channel action inside its card. Refresh and restart persisted state. |
| Channels | PASS | Telegram is visibly Custom Settings-managed with duplicate actions removed; Slack and WhatsApp remain independently available. Installed TTL metadata is healthy. |
| Scheduler | PASS | MCP UI visibly showed `scheduling-cortex - Connected` and health returned OK. CLI still truthfully surfaces a prior scheduled delivery failure from an earlier service-unavailable window; the ledger was preserved rather than rewritten. |
| Memory Hardening | PARTIAL | The latest scheduled run had failed while Mongo was unavailable. A current dry run connected to Mongo, probed the configured model successfully, and exited `0`; the historical scheduled receipt remains truthful until the next scheduled run. |
| Telegram latency | PASS | One synthetic Telegram Desktop turn produced one exact reply. Bridge receipt to stored assistant completion was about `12.8` seconds with no current rate-limit error. Historical evidence tied the earlier slow/failed turns to provider rate limiting. |

## Continuity-audit interpretation

A strict audit taken while the full runtime and signed-in browser were active reported changes in the
OAuth flow-log cache and, during the activation window, the active session record. A second idle
comparison showed continued flow-log churn. Those captures violated the quiesced-writer condition
required for a strict stopped-state comparison; they did not show lost durable state. The recoverable
snapshot comparison is the valid installed-user proof here and finished with zero differences.

The Telegram QA turn legitimately created two messages, two transaction rows, one conversation
update, one feeling update, one vector-file metadata update, and five saved-memory updates. Because
the prompt was synthetic QA and product rules say tests must not become memory, the exact pre-snapshot
records were restored only when every current document matched the expected post-QA version. Four
QA-created documents were deleted by exact ID and content match. A new complete snapshot then proved
zero differences from the pre-activation recoverable state.

## User-Grade Evidence

- Surface exercised: supported local-prod activation, signed-in Chrome Settings, MCP control panel, and Telegram Desktop.
- Real user path: validate/activate/restart, reopen Account and Channels, refresh, inspect scheduler, send one synthetic Telegram prompt, and observe its reply.
- Visible outcome: login persisted; four provider credentials appeared saved; managed Channels and connected scheduler loaded; one Telegram reply arrived.
- Expanded/detail state: provider rows, managed-channel explanation, phone/desktop action geometry, and MCP server detail were inspected.
- Persistence/reload result: account/channel state survived refresh and restart; final snapshot equality proved QA cleanup and user-state continuity.
- Local/external prerequisite state: local API/web/scheduler/Telegram/model probe were healthy; signed public artifact and external hardware matrix were unavailable.
- Evidence retrieval classification, if applicable: current success; historical provider rate limit and dependency-unavailable receipts retained.
- Fallback path, if applicable: real Chrome and Telegram Desktop were used; no mock substituted for user-visible proof.
- Backend/log/DB confirmation: exact collection/config/schedule equality, persistent credential metadata, process health, and bridge timestamps matched visible results.
- Final model/runtime wording check: Settings avoids false provider-health claims and delegates operator-managed Telegram health correctly.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit tests supported but did not replace the browser, CLI, MCP, or Telegram paths.

## Automated Evidence

- Parent targeted upgrade/payload slice: `347` passed.
- Complete parent release suite before final UI pin: `2,063` passed, `11` skipped.
- Connected-account client suite: `45` passed.
- Connected-channel API route suite: `11` passed.
- Wider channel persistence/route suite: `29` passed.
- Production frontend build: passed.
- Independent diff/QA review: approved after copy, API-guard, marker, and responsive-geometry issues
  were corrected.

## Findings

This closes the established-user local source-upgrade path. It does not make the universal public
upgrade artifact finished. Remaining gates are:

1. Rebuild the exact immutable dual-architecture Native payload from the reviewed pins.
2. Run the exact payload in a pristine disposable Mac through first install and existing-user
   upgrade/rollback/restore, including provider and channel reconnect semantics.
3. Developer ID sign, notarize, staple, and pass Gatekeeper plus Finder/helper/Keychain/TCC flows.
4. Run the physical Apple-silicon and Intel compatibility/failure matrix, including interruption,
   sleep/wake, low disk, network loss, and login-start recovery.
5. Repeat the byte-for-byte manifest, license/notice, privacy, and installed-artifact identity gates.

No cloud deployment, public push, provider revocation, or secret-bearing artifact was created.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
