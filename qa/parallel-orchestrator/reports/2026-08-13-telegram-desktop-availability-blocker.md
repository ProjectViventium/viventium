# Parallel Work Telegram Desktop Availability QA Run - 2026-08-13

## Summary

- Result: BLOCKED.
- Real surface inspected: Telegram Desktop with the installed local production bot, read-only.
- Isolated surface inspected: the Parallel Work QA runtime's API, Web, agent state, and process ownership.
- User-state safety: no Telegram message, toggle, callback, or work action was sent; no production or QA account state was changed.
- Related source repair: startup agent seeding now retains the agent-owned
  `glasshive_options.orchestration` declaration on clean seed and reseed.

The installed bot was the only process polling the configured Telegram account, and it was running
an older artifact without the Parallel Work handlers. The isolated QA runtime was healthy but had
no dedicated Telegram poller and shared the same account credential. Starting a second poller would
create an unsafe update-consumer conflict, so the visible toggle, Active Work, callback/action, and
reload flows were not exercised.

This run found one source defect while tracing that boundary: the startup seed field allowlist
omitted `glasshive_options`. Consequently, a clean seed stripped the source agent's orchestration
declaration and a later seed could not preserve it. A test-first source repair now covers both the
initial seed and reseed. The isolated QA database was deliberately not mutated after the fix, so a
live restart/reseed check remains required.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `PWK-001` | BLOCKED | Telegram Desktop process and bot ownership inspection | No safe independent QA poller was available, so no toggle was pressed. |
| `PWK-018` | FAIL | Installed bot source/hash capability scan, runtime environment, safe agent-state projection | Installed Telegram and production agent state are behind the source implementation. |
| `PWK-026` | PARTIAL | RED/GREEN clean-seed and reseed regression plus broader seeder suites | Source retains the declaration; the QA database still shows its pre-fix state and live restart/reseed was not run. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Supporting state evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `PWK-UC-001` | Enable Parallel Work and send rapid synthetic work while Main remains responsive. | Telegram Desktop, read-only | BLOCKED | The installed Viventium chat was present; no synthetic message was sent. | Only the installed production bot owned polling; the QA runtime had no independent bot. | Promote the feature artifact or provide a dedicated QA account/poller, then run the complete flow. |
| `PWK-UC-008` | Inspect installed layers, enable the feature, and roll it back. | Installed Telegram process plus isolated API/Web runtime | BLOCKED | Installed Telegram lacked the new controls; no enable/rollback action was taken. | Installed artifact, runtime flag, and agent declaration were not aligned. | Build/promote aligned artifacts, seed the declaration, then run install/restart/rollback evidence. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: account-wide Parallel Work control and Active Work supervision in Telegram.
- Requirement: a linked user can toggle the mode, inspect/control durable missions, reload, and see
  state consistent with Web and backend truth.
- Use case: enable the mode, launch synthetic work, keep chatting, inspect and control the work, and
  confirm persistence after reload.
- QA cases: `PWK-001`, `PWK-018`, `PWK-026`, `PWK-UC-001`, and `PWK-UC-008`.
- Expected result: the installed bot exposes the current controls and the agent declaration survives
  startup seeding.
- Actual evidence: the QA runtime requested availability, but its agent declaration had been
  stripped by seeding; the only active Telegram poller was the older installed artifact.
- Remaining gap: ship aligned artifacts, give the isolated runtime a non-conflicting Telegram
  account or perform an approved reversible cutover, reseed/restart, and run the full synthetic flow.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which contract is being tested? | Telegram toggle, Active Work, installed-artifact parity, and clean-seed declaration retention. |
| Code owning path | Which path owns declaration persistence? | LibreChat startup agent seeder field selection and preserve logic. |
| Installed artifact | Does the running bot contain the current feature? | No; the installed bot lacked the Parallel Work handlers. |
| Runtime config | Does each runtime request availability? | The isolated runtime did; installed production did not. |
| Process ownership | Can QA poll Telegram without conflict? | No; the installed bot was already the sole poller for the shared account credential. |
| DB/state/persistence | Does the agent carry the declaration? | Safe projections showed it absent in both installed production and the pre-fix QA seed. |
| Automated regression | Does clean seed and reseed retain it? | Yes in source tests; live restart/reseed was intentionally not performed. |
| Real user path | Was Telegram Desktop opened? | Yes, read-only; no message or state mutation was performed. |
| Visual/UX comparison | Were toggle, cards, and actions exercised? | No; BLOCKED before mutation by artifact/poller mismatch. |
| Logs | Were runtime errors correlated? | Sanitized log counts and process state were inspected; no raw private content was retained. |

## User-Grade Evidence

- Surface exercised: Telegram Desktop and the installed local bot, read-only.
- Real user path: opened the installed Viventium chat in Telegram Desktop and inspected the available
  controls without sending a message, pressing a callback, or changing account state.
- Visible outcome: the installed chat existed, but the current feature could not be safely exercised.
- Expanded/detail state: not run because the installed bot had no current Active Work implementation.
- Persistence/reload result: not run because no account state was changed.
- Backend/log/DB confirmation: process ownership, installed feature symbols, runtime flags, and safe agent
  field projections consistently showed the artifact/declaration mismatch.
- Final model/runtime wording check: no model turn was submitted and no success wording was accepted;
  the visible absence of current controls agreed with the installed-artifact inspection.
- Substitution check: source tests, logs, and database projections support the blocker; they do not
  substitute for the required Telegram toggle/action/reload flow.
- Evidence hygiene: temporary desktop captures were discarded after inspection; no screenshots,
  private messages, account identifiers, tokens, raw logs, or database exports were retained.

## Automated Evidence

The exact local runtime paths and credentials are intentionally omitted. Commands below are
public-safe shapes.

```sh
npx jest -c api/jest.config.js --runInBand \
  api/test/scripts/viventium-seed-agents.test.js \
  -t 'clean seed persists GlassHive orchestration and reseed retains the declaration'

npx jest -c api/jest.config.js --runInBand --silent \
  api/test/scripts/viventium-seed-agents.test.js \
  api/test/scripts/viventium-sync-agents.test.js \
  api/test/scripts/viventium-agent-runtime-models.test.js
```

- Focused RED: the clean-seed projection omitted `glasshive_options`.
- Focused GREEN: 1 test passed after adding the field to the owned seed/preserve contract.
- Seeder suite: 13 tests passed.
- Broader relevant suites: 3 suites, 87 tests passed.
- Full LibreChat script-test directory: 8 suites, 193 tests passed.

## Findings and Release Boundary

- Fixed in source: startup seeding no longer strips `glasshive_options`; reseed preserves the
  existing declaration.
- Release blocker: installed Telegram and production agent state do not contain the current feature.
- QA blocker: the isolated runtime has no safely independent Telegram poller.
- Still not run: visible toggle, Active Work empty/running/attention states, callback delivery,
  Message/Queue/Steer/Pause/Resume/Stop/Retry/Dismiss, reload/restart persistence, and backend
  correlation for a synthetic Telegram turn.
- Required next run: promote or build the intended artifacts, use a dedicated QA Telegram account
  or an explicitly approved reversible poller cutover, restart/reseed, then execute every applicable
  Telegram case with synthetic content.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots, emails, account identifiers, or customer data.
- [x] No message IDs, chat IDs, user IDs, agent IDs, database IDs, or raw request/response IDs.
- [x] No local absolute paths, hostnames, machine names, raw logs, database exports, or App Support dumps.
- [x] Temporary desktop captures were moved to Trash and are not part of the repository or report.
