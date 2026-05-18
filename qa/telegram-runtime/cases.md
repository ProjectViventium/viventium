# Telegram Runtime Cases

## Case TR-001: Polling Conflict Is Visible

- **Expected outcome:** A running Telegram bridge or Telegram Codex sidecar with recent
  `getUpdates` conflict evidence is reported as `Running with issues`.
- **Forbidden result:** `bin/viventium status` says the service is simply `Running` while recent logs
  show another bot process is consuming the same token.
- **Evidence to capture:** synthetic unit test, sanitized status output, and a local runtime note.
- **Last run:** 2026-05-14, automated synthetic coverage added.

## Case TR-002: Provider Authentication Failure Is Actionable

- **Expected outcome:** A running Telegram bridge with recent provider-auth evidence is reported as
  `Running with issues`; a stopped Telegram bridge with the same evidence is reported as
  `Action Required`. Both states use user-safe refresh guidance.
- **Forbidden result:** raw provider error text, token values, account identifiers, or private logs
  appear in public status or QA artifacts.
- **Evidence to capture:** synthetic unit test and public-safe QA report.
- **Last run:** 2026-05-14, automated synthetic coverage expanded after escaped user report.

## Case TR-003: Telegram Codex Restart Clears Scoped Orphans

- **Expected outcome:** `--restart` kills only Telegram Codex processes scoped to the configured
  Telegram Codex checkout before starting a new sidecar.
- **Forbidden result:** duplicate Telegram Codex pollers or broad process kills outside the Viventium
  checkout.
- **Evidence to capture:** static launcher regression test and local status after restart.
- **Last run:** 2026-05-14, static regression coverage added.

## Case TR-004: Provider Rejection Is Not Shown As Connection Error

- **Expected outcome:** A Telegram turn whose LibreChat final event reports rejected model provider
  credentials returns clear reconnect guidance for the AI provider.
- **Forbidden result:** Telegram says only `Connection error. Please retry.` or otherwise implies
  the Telegram transport is broken when the root cause is model-provider auth.
- **Evidence to capture:** bridge stream regression test, local runtime restart, sanitized status/log
  class check.
- **Last run:** 2026-05-14, bridge regression coverage added after escaped user report.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Telegram Runtime. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `TELEGRAM-UC-001` | Start or inspect Telegram runtime status while a synthetic polling-conflict log fixture is present. | `TR-001`, `TR-003` | Telegram status command, launcher/supervisor path, and sanitized logs | Status output, scoped process list, launcher tests, and dated QA report | Telegram is shown as running with issues, scoped restart clears only Viventium-owned pollers, and no broad process kill occurs. | 2026-05-14 automated synthetic coverage - passed |
| `TELEGRAM-UC-002` | Send or simulate a Telegram turn whose model provider rejects credentials. | `TR-002`, `TR-004` | Telegram bridge stream, user-visible reply, and sanitized logs | Stream regression test, provider-auth status output, sanitized logs, and QA report | The reply gives provider reconnect guidance instead of blaming Telegram transport or leaking raw provider errors. | 2026-05-14 bridge regression coverage - passed |
| `TELEGRAM-UC-003` | Restart Telegram runtime and compare status/log evidence before and after restart. | `TR-001`-`TR-004` | CLI launcher/status, process list, logs, and Telegram bridge state | Scoped process evidence, status output, sanitized logs, and tests | Restart removes only stale scoped pollers, preserves unrelated processes, and status after restart matches the actual bridge state. | 2026-05-14 static regression coverage - passed |

## Release Test Traceability

- `tests/release/test_telegram_codex_runtime_paths.py`
- `tests/release/test_telegram_lazy_startup_contract.py`
- `tests/release/test_telegram_transcription_error_contract.py`
