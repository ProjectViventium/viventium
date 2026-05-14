# Telegram Provider Reconnect Message QA - 2026-05-14

## Scope

Regression QA for the Telegram Bridge path that previously surfaced rejected model-provider
credentials as a generic connection error.

## Evidence

- Local Telegram Bridge logs showed a recent Telegram turn reaching LibreChat and receiving a
  provider-credentials rejection from the model path. The bridge process was polling successfully,
  so this was not a Telegram Bot API polling outage.
- `python3 -m py_compile TelegramVivBot/utils/librechat_bridge.py` passed.
- `uv run --with pytest --with pytest-asyncio --with httpx python -m pytest
  tests/test_librechat_bridge.py -q` passed: 92 tests.
- `uv run --with pytest --with pyyaml pytest tests/release/test_install_summary.py
  tests/release/test_telegram_codex_runtime_paths.py -q` passed: 38 tests.
- `PYTHONPATH=. uv run --with pytest --with pyyaml pytest tests/release/ -q` passed: 532 tests,
  1 skipped.
- `bin/viventium dev-runtime activate-current --validate --restart --allow-protected-folder
  --allow-dirty-local-testing` restarted the local installed runtime from the active checkout.
- `bin/viventium status` reported Telegram Bridge and Telegram Codex as `Running` after restart.

## Result

- TR-004: Passed by stream-level regression. The bridge now maps the provider rejection wording to
  actionable reconnect guidance instead of the generic connection-error fallback.
- TR-002: Expanded. Running Telegram services with recent provider-auth evidence stay visible as
  `Running with issues`; stopped services with the same evidence remain `Action Required`.

## Boundary

No raw Telegram chat IDs, bot tokens, provider keys, local absolute paths, or private transcript text
are included in this public-safe report. No real Telegram message was sent during this pass because
that is externally visible and should be run only with explicit operator approval.
