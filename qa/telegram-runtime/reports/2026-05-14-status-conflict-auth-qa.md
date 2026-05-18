<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
# Telegram Runtime QA - 2026-05-14

## Scope

Local QA for Telegram Bridge and Telegram Codex status reporting, restart cleanup, and public-safe
evidence handling.

## Evidence

- `uv run --with pytest --with pyyaml pytest tests/release/test_install_summary.py
  tests/release/test_telegram_codex_runtime_paths.py tests/release/test_stable_dev_runtime_workflows.py
  tests/release/test_cli_upgrade.py -q` passed: 90 tests.
- `PYTHONPATH=. uv run --with pytest --with pyyaml pytest tests/release/ -q` passed: 537 tests,
  1 skipped.
- `npm run test:api -- --runInBand` in the LibreChat nested repo passed: 172 suites passed, 2
  skipped; 2,978 tests passed, 19 skipped.
- `bin/viventium dev-runtime activate-current --validate --restart --allow-protected-folder
  --allow-dirty-local-testing` restarted the local installed runtime.
- `bin/viventium status` reported Telegram Bridge and Telegram Codex as `Running`.
- Recent local Telegram Bridge and Telegram Codex log tails were scanned for polling-conflict and
  provider-auth classes without printing raw logs. Both classes were clear after restart.
- Process inspection showed Telegram Codex had the expected launcher/runtime process pair, not
  multiple independent pollers from the same checkout.

## Results

- TR-001: Passed by synthetic status tests. Recent `getUpdates` conflict evidence now changes status
  to `Running with issues` with user-safe guidance instead of exposing raw log text.
- TR-002: Passed by synthetic status tests. Recent provider-auth evidence on a stopped Telegram
  service now reports `Action Required` without leaking raw provider error text.
- TR-003: Passed by static launcher test and local restart. `--restart` clears scoped Telegram Codex
  sidecar orphans before starting a fresh sidecar.

## Boundary

No Telegram message was sent in this pass. Sending a real Telegram message is externally visible, so
that final user-level Telegram send/receive test should be run only with explicit operator approval.
