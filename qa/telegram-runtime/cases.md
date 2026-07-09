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

## Case TR-005: Provider Rate Limit Is Not Shown Or Spoken As Connection Error

- **Expected outcome:** A Telegram turn whose primary provider is rate-limited before visible text
  retries the configured valid main-agent fallback LLM. Only an unavailable, invalid, or exhausted
  fallback may return clear provider-rate-limit copy, and that terminal bridge/provider error is
  marked non-spoken.
- **Forbidden result:** Telegram says only `Connection error. Please retry.`, implies Telegram
  transport is broken, skips a configured fallback, or synthesizes a voice note of the bridge error.
- **Evidence to capture:** main-agent fallback regression test, bridge stream regression test,
  sanitized runtime log class, and dated QA report.
- **Last run:** 2026-06-28, automated regression and live-runtime QA rerun. See
  `reports/2026-06-28-telegram-fallback-audio-table-qa-rerun.md`.

## Case TR-006: Telegram Markdown Tables Render Readably

- **Expected outcome:** Markdown pipe tables from main answers or worker callbacks are converted to
  readable Telegram HTML rows.
- **Forbidden result:** Telegram displays raw `| Name | ... |` and `|---|` table syntax.
- **Evidence to capture:** Telegram HTML renderer regression test plus a visual/browser rendering
  check with synthetic public-safe content.
- **Last run:** 2026-06-28, automated regression plus Playwright visual QA rerun. See
  `reports/2026-06-28-telegram-fallback-audio-table-qa-rerun.md`.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Telegram Runtime. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `TELEGRAM-UC-001` | Start or inspect Telegram runtime status while a synthetic polling-conflict log fixture is present. | `TR-001`, `TR-003` | Telegram status command, launcher/supervisor path, and sanitized logs | Status output, scoped process list, launcher tests, and dated QA report | Telegram is shown as running with issues, scoped restart clears only Viventium-owned pollers, and no broad process kill occurs. | 2026-05-14 automated synthetic coverage - passed |
| `TELEGRAM-UC-002` | Send or simulate a Telegram turn whose model provider rejects credentials. | `TR-002`, `TR-004` | Telegram bridge stream, user-visible reply, and sanitized logs | Stream regression test, provider-auth status output, sanitized logs, and QA report | The reply gives provider reconnect guidance instead of blaming Telegram transport or leaking raw provider errors. | 2026-05-14 bridge regression coverage - passed |
| `TELEGRAM-UC-003` | Restart Telegram runtime and compare status/log evidence before and after restart. | `TR-001`-`TR-004` | CLI launcher/status, process list, logs, and Telegram bridge state | Scoped process evidence, status output, sanitized logs, and tests | Restart removes only stale scoped pollers, preserves unrelated processes, and status after restart matches the actual bridge state. | 2026-05-14 static regression coverage - passed |
| `TELEGRAM-UC-004` | Simulate a primary provider-rate-limited Telegram turn while audio replies are enabled. | `TR-005` | Main-agent fallback classifier, Telegram bridge stream, and voice gate | Fallback regression test, stream regression test, sanitized log class, and QA report | A valid configured fallback produces the answer; otherwise the terminal provider-rate-limit blocker is visible text only and non-spoken. | 2026-06-28 automated regression and live-runtime QA rerun - passed automated, partial live external Telegram |
| `TELEGRAM-UC-005` | Render a worker-style Markdown table result for Telegram. | `TR-006` | Telegram Markdown-to-HTML renderer and visual fixture | Renderer regression test and browser screenshot/check with synthetic content | The user sees readable rows, not raw pipe-table syntax. | 2026-06-28 automated plus Playwright visual coverage - passed |

## Release Test Traceability

- `tests/release/test_telegram_codex_runtime_paths.py`
- `tests/release/test_telegram_lazy_startup_contract.py`
- `tests/release/test_telegram_transcription_error_contract.py`
