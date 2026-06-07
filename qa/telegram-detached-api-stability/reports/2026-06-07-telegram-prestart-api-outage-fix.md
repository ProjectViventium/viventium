<!-- qa-evidence-exempt: Public-safe implementation QA summary; raw local logs, private chat text, secrets, and App Support paths are intentionally excluded. -->

# Telegram Pre-Start API Outage Fix QA - 2026-06-07

## Scope

Implemented and tested the fix for Telegram pre-start LibreChat API outages that previously emitted
the generic plain-text fallback `Failed to reach Viventium. Please retry.` and allowed always-voice
to synthesize that transport failure as audio.

## Requirement Links

- `docs/requirements_and_learnings/01_Key_Principles.md`: user-facing errors must identify the
  correct failure class, and runtime fixes must be verified through code, logs, DB/state, generated
  artifacts, and user-facing paths.
- `docs/requirements_and_learnings/03_Telegram_Bridge.md`: Telegram must return complete responses
  or clear errors, local/detached launches must recover the LibreChat API, and status must not claim
  Telegram is healthy while its configured API origin is unreachable.
- `qa/telegram-detached-api-stability/cases.md`: `TGAPI-005`.

## Code Changes Under Test

- `TelegramVivBot/utils/librechat_bridge.py`
  - Pre-start `_start_chat` failures now yield structured `bridge_error` events with `speak=false`
    instead of plain assistant-style text.
  - Safe automatic retry is limited to pre-ingress connect failures: connect error, connect timeout,
    and pool timeout.
  - Ambiguous or possibly-ingressed failures, including read timeout and HTTP status errors, do not
    auto-retry.
  - Non-200 chat-start responses preserve HTTP status through `httpx.HTTPStatusError`.
  - Default local LibreChat origin is `http://127.0.0.1:3180`.
- `scripts/viventium/config_compiler.py`
  - Generated `VIVENTIUM_LIBRECHAT_ORIGIN` now defaults to explicit IPv4 loopback.
- `viventium_v0_4/viventium-librechat-start.sh`
  - Detached API watchdog probes the configured LibreChat origin when available.
  - Initial API health failure now enters backend recovery instead of passively waiting and exiting.
- `scripts/viventium/install_summary.py` and `bin/viventium`
  - Telegram health/status now requires the bot process and the LibreChat API route to be reachable.

## Automated Results

| Check | Result |
| --- | --- |
| Python syntax | PASS: `py_compile` passed for the edited Python runtime/compiler/status files. |
| Telegram focused bridge slice | PASS: `103 passed`. |
| Full Telegram test folder | PASS: `305 passed`. |
| Release/status/watchdog/config slice | PASS: `218 passed`. |
| Runtime activation | PASS: current checkout was recompiled and restarted through the supported dev-runtime activation path. |

## Runtime Evidence

| Layer | Evidence |
| --- | --- |
| Generated runtime | `VIVENTIUM_LIBRECHAT_ORIGIN` is now `http://127.0.0.1:3180` in both runtime and Telegram service env output. |
| API health | Both `http://127.0.0.1:3180/health` and `http://localhost:3180/health` returned HTTP 200 after restart. |
| Status | `bin/viventium status` reported LibreChat API, LibreChat Frontend, Modern Playground, and Telegram Bridge running. Overall status still needed attention because unrelated sidecars were degraded. |
| Logs | Telegram bot restarted cleanly after the runtime restart. Historical pre-fix failure/audio log entries remain in old log history, but no new pre-start failure was produced during this QA run. |
| DB/state | Mongo ingress query returned zero recent Telegram ingress rows, expected because no live Telegram message was transmitted during QA. |
| Browser | Playwright opened `http://localhost:3190/login`; page title was Viventium, visible login form rendered, and console had zero errors. Screenshot artifact: `output/playwright/telegram-api-outage-fix-post-restart-login-2026-06-07.png`. |
| Computer | Computer Use inspected Telegram desktop and confirmed the Viventium bot chat was responsive after restart. No message was sent. |

## ClaudeViv Review

ClaudeViv review-only pass completed successfully after implementation. It agreed the fix is aligned
with the requirements and flagged two maintainability gaps: isolated coverage for the new error
classifier/event behavior and a stronger watchdog initial-recovery contract. Both were addressed
before final QA:

- added direct tests for safe retry classification, class-specific copy, and non-spoken bridge error
  event shape
- added a watchdog test that verifies initial probe failure flows into restart and recovery probing

ClaudeViv's remaining full-view gap is the same policy-bound gap below: no live Telegram send was
transmitted during this run.

## Remaining Gap

Live Telegram send/receive of a synthetic message was not run. Sending a message through Telegram
would be representational communication through a third-party service and requires action-time
confirmation under the Computer Use policy. This QA run therefore proves the implementation,
generated runtime, restart, status, logs, DB non-ingress, browser surface, and desktop readiness,
but not a post-fix live Telegram message delivery.

## Result

`TGAPI-005` is `PARTIAL/PASS`: the product fix is implemented, compiled into the active local
runtime, and covered by automated/runtime/browser/Desktop evidence. The only unproven leg is live
Telegram send/receive under an intentionally induced API outage.
