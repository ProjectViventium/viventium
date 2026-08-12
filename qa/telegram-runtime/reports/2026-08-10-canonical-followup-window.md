# Telegram Canonical Follow-Up Window — 2026-08-10

## Scope

This run covered the Telegram bridge's automatic follow-up listener configuration only. It did not
start the bot, use a token/account, restart a runtime, or send a Telegram message.

## Root Cause

The bridge started a raw SSE listener whenever a delivery callback existed. That listener defaulted
to a 180-second post-response grace and a 210-second total lifetime. The DB-backed follow-up poller
also inherited that total, even though the config compiler already emitted one canonical background
follow-up window for Web, Voice, and Telegram. The duplicate implicit defaults could retain an
ordinary Telegram listener well beyond the configured product window.

## Implemented Contract

- The compiler validates `runtime.background_followup_window_s` from 0 through 86400 seconds and
  emits `VIVENTIUM_TELEGRAM_FOLLOWUP_GRACE_S`.
- Telegram's raw SSE listener and ordinary DB-backed poll use that canonical value by default.
- Unset standalone configuration invents no listener lifetime; explicit zero disables ordinary
  listeners; invalid canonical runtime values fail closed.
- A bounded explicit `VIVENTIUM_TELEGRAM_FOLLOWUP_TIMEOUT_S` may extend total listening.
- Deprecated insight-window inputs remain standalone compatibility only and cannot override the
  canonical compiler value.
- Raw-listener cleanup does not cancel the persisted follow-up poll. GlassHive continues to use its
  independent callback window.

## Evidence

- RED: ten focused bridge regressions failed against the old defaults and lifecycle.
- GREEN: the focused bridge cases passed after the implementation.
- The complete Telegram LibreChat bridge test file passed.
- Focused compiler tests passed for default, override, zero, invalid, and out-of-range inputs.
- The tracked Telegram example no longer supplies 180/210-second values.

## Status

`PARTIAL`: source and automated acceptance pass. A real bot delivery was outside this run's explicit
non-live boundary, so this report does not claim live Telegram acceptance.
<!-- qa-evidence-exempt: Historical or specialized supporting artifact retained without retroactively inventing missing evidence; current release acceptance requires a fresh full-view report. -->
