<!-- qa-evidence-exempt: legacy sanitized RCA/QA note retained for historical context; current acceptance must use cases plus a fresh v2 report. -->

# Telegram GlassHive Callback Dedupe RCA - 2026-06-15

## Scope

- Feature area: Telegram detached API stability plus GlassHive callback delivery.
- Trigger: a local Telegram GlassHive turn produced two visible copies of the same worker completion.
- Public-safety posture: this report summarizes sanitized DB/log/code evidence only. It does not
  include raw chat ids, personal account ids, private message text, screenshots, tokens, or local
  absolute paths.

## Root Cause

The duplicate was not caused by poor worker intelligence or duplicate user ingress. The live state
showed one Telegram ingress event, one GlassHive callback message, and one durable callback delivery
row for the affected turn.

The failure was a delivery race between two legitimate Telegram callback paths:

- the same-turn Telegram poller could see the latest GlassHive callback quickly and send it to the
  user;
- the durable callback dispatcher later claimed the pending delivery row and sent the same callback.

The bridge already knew how to claim and mark a delivery row when `callbackId` was present, but the
authenticated LibreChat callback polling response did not expose that opaque callback id. Without the
id, the poller took its legacy send path and could not mark the durable row before the dispatcher saw
it as pending.

## Fix

- `GlassHiveCallbackMessageService.toPublicCallback()` now includes the opaque `callbackId` for
  authenticated bridge polling while continuing to omit internal worker/run ids from the public
  response.
- Telegram bridge regression coverage now proves `_poll_for_followup()` claims the callback id
  before sending and marks the delivery row after a successful send.
- The bridge waits for the durable ledger first, then falls back to one legacy same-turn send only
  if a callback-id-bearing terminal callback still has no durable delivery row by timeout; this
  prevents silent non-delivery without returning to the duplicate-by-default race.
- LibreChat route regressions now prove Telegram and voice callback polling include `callbackId`
  without exposing `workerId` or `runId`.
- The owning Telegram requirements doc now states that same-turn polling and durable dispatch must
  share the delivery ledger and must not legacy-send a callback that has a durable row.

## Related GlassHive Substrate Fixes

This incident occurred during broader GlassHive worker QA, so the same pass also fixed substrate
misalignments that could make workers look less capable than they are:

- Docker/workstation Claude now receives the universal self-review and `FINAL REPORT:` contract in
  the command sent to the CLI, not only in project files.
- High-level GlassHive launch/assign now preserves resolved effort and bootstrap context when
  assigning the worker run.
- Scheduled GlassHive runs preserve bootstrap context.
- Host-native worker preflight now enforces stable version/capability floors for built-in CLI worker
  types before a run is created.
- Requirements docs now reinforce simple file handoff by accessible full path, native worker
  capability projection, mode-scoped runtime facts, and professional document defaults.

## Verification Run

Automated verification run locally on 2026-06-15:

```text
LibreChat Telegram route spec: PASS (32 passed)
LibreChat voice route spec: PASS (28 passed)
Telegram bridge regression file: PASS (109 passed)
GlassHive Docker/host profile + MCP target files: PASS
Running local runtime callback polling endpoint: PASS
```

Verification commands:

```bash
cd viventium_v0_4/LibreChat/api
npm test -- --runInBand server/routes/viventium/__tests__/telegram.spec.js
npm test -- --runInBand server/routes/viventium/__tests__/voice.spec.js

cd ../telegram-viventium
PYTHONPATH=. TelegramVivBot/.venv/bin/python -m pytest tests/test_librechat_bridge.py -q -ra

cd ../GlassHive/runtime_phase1
PYTHONPATH=src ./.venv/bin/python -m pytest tests/test_profile_runtime.py tests/test_mcp_server.py -q -ra
```

Post-restart runtime probe:

```text
LibreChat API health: PASS
LibreChat frontend health: PASS
GlassHive API health: PASS
Modern Playground health: PASS
Authenticated Telegram callback polling endpoint: PASS; latest callback included callbackId and did not expose workerId/runId.
```

ClaudeViv review-only sanity check:

```text
ClaudeViv confirmed the Telegram duplicate RCA and callbackId exposure as correct, minimal, and safe.
ClaudeViv found that the earlier narrow GlassHive test selection missed stale test harness failures.
Follow-up fix: updated stale MCP test doubles to accept bootstrap_bundle/effort and updated fake host
Codex probes to answer --version. Full target files were rerun afterward and passed.
```

## Remaining Acceptance Gap

This is `PASS/PARTIAL`, not full live acceptance yet. The deterministic regressions and sanitized
incident state prove the root and fix, but a rebuilt/restarted local runtime still needs a real
post-fix Telegram GlassHive turn to prove the user-visible duplicate is gone on the live surface.
That rerun should record:

- one inbound Telegram turn;
- one GlassHive callback id;
- one sent delivery row;
- one visible Telegram callback;
- no raw tool/worker plumbing in the visible message;
- no private content in public QA evidence.
