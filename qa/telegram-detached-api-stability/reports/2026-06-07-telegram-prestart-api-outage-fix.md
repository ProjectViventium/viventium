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
| Live outage send | PASS: with the LibreChat API intentionally unavailable, a synthetic Telegram message returned the visible text `Viventium's local API is starting or unavailable. Please retry in a moment.` |
| Logs | PASS: the outage turn logged a pre-ingress `ConnectError`, one safe retry attempt, then `TG_VOICE ... send=0`; the recovery retry logged normal TTS/audio only after the successful assistant response. |
| DB/state | PASS: the failed pre-ingress outage turn created no successful Telegram ingress row; the post-recovery retry created one Telegram ingress row and a normal persisted message pair in the live LibreChat database. |
| Browser | Playwright opened `http://localhost:3190/login`; page title was Viventium, visible login form rendered, and console had zero errors. Screenshot artifact: `output/playwright/telegram-api-outage-fix-post-restart-login-2026-06-07.png`. |
| Computer | Computer Use inspected Telegram desktop before and after the live run. Its click/type actions were unavailable in this session, so the confirmed synthetic Telegram messages were sent via local desktop automation; Computer visual inspection confirmed the outage response and the post-recovery retry response. |

## ClaudeViv Review

ClaudeViv review-only pass completed successfully after implementation. It agreed the fix is aligned
with the requirements and flagged two maintainability gaps: isolated coverage for the new error
classifier/event behavior and a stronger watchdog initial-recovery contract. Both were addressed
before final QA:

- added direct tests for safe retry classification, class-specific copy, and non-spoken bridge error
  event shape
- added a watchdog test that verifies initial probe failure flows into restart and recovery probing

ClaudeViv's remaining full-view gap was a live Telegram send under an induced API outage. That gap
was closed after user confirmation by running the real Telegram outage and recovery path.

## Remaining Gap

No remaining Telegram-specific gap for `TGAPI-005`. The overall local runtime status still reported
unrelated sidecar degradation outside this Telegram/API failure class. Computer Use visual
inspection worked, but its direct click/type action channel was unavailable; local desktop
automation was used only after user confirmation to send public-safe synthetic Telegram messages.

## Result

`TGAPI-005` is `PASS`: the product fix is implemented, compiled into the active local runtime, and
covered by automated tests, generated runtime checks, API/status health, logs, Mongo state,
Playwright browser QA, Computer visual inspection, and real Telegram outage/recovery send/receive.
