# Telegram Poller Handoff And Latency Resilience

<!-- qa-evidence-exempt: Source and synthetic process-handoff note; real Telegram delivery evidence belongs in the universal-upgrade run report. -->

Date: 2026-07-24

Result: **PASS-AUTOMATED / PARTIAL USER PATH**

## Scope And Outcome

The source runtime now uses stable, owner-only Telegram poller receipts and a transactional
cross-checkout handoff. Receipts and transactions contain only a BotFather-token SHA-256 hash,
never the token. PID reuse, cwd/command mismatch, unsafe files, and unknown processes fail closed.
Candidate readiness commits the handoff only after pinned PTB reports both its receive Updater and
Application running and the receipt carries typed polling/webhook proof. `post_init` can only
schedule that observation. Candidate failure, including the exact gap after `post_init` but before
polling/application start, or an interrupted handoff invokes a detached rollback guard and restores
only a previously recognized safe launch descriptor.

The five-second GlassHive delivery-ledger loop now applies capped exponential backoff only while
its dependency is failing. Duplicate failure logs are suppressed, recovery is logged once, and
healthy empty-ledger polling resets to the normal interval.

## Evidence Run

- `PASS`: Telegram handoff release tests covered token secrecy, owner-only modes, PID reuse,
  unknown-process refusal, identity recheck immediately before signal, safe rollback, unsafe
  rollback rejection, typed polling/webhook proof, premature `ready=true` refusal, and launcher
  integration.
- `PASS`: detached launcher supervision regressions covered receipt-backed stop/restart and removed
  Telegram `bot.py` pattern kills.
- `PASS`: singleton and bridge tests covered pending/ready receipt lifecycle, deterministic failure
  after `post_init` but before polling, a real locked PTB 22.5 `Application`/`Updater`, capped delays
  of 5/10/20 seconds, one outage warning, one recovery log, and reset to the healthy five-second
  poll.
- `PASS`: the complete Telegram repository suite passed (`340 passed`) through the Telegram
  component's locked dependency project.
- `PASS`: all Telegram/detached release tests passed (`48 passed`).
- `PASS`: launcher shell syntax and affected Python modules compiled.

No App Support state, personal Telegram account, live BotFather token, private logs, or external
Telegram delivery was used. A real installed two-checkout restart and visible external reply remain
required before claiming the user path fully live.
