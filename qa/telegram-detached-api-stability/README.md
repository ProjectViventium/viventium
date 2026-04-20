# Telegram Detached API Stability

## Purpose

Verify that detached/direct LibreChat launches keep the API available for Telegram even if the
frontend dev server exits later.

## Acceptance Contract

- Detached launch brings up LibreChat API on `3180`.
- Telegram bridge can start chat requests against LibreChat after detached launch.
- Killing the frontend dev server does not take down the LibreChat API.
- Killing the real LibreChat API child while a parent `npm`/`nodemon` process survives must trigger
  launcher-owned recovery instead of leaving Telegram pointed at a dead `3180` origin.
- A synthetic Telegram ingress request still succeeds after the frontend is stopped.

## Public-Safe Evidence

- Investigation evidence:
  - `~/Library/Application Support/Viventium/state/runtime/isolated/logs/telegram_bot.log`
  - `~/Library/Application Support/Viventium/logs/helper-start.log`
  - Mongo database `LibreChatViventium`
- Root symptom captured:
  - `2026-04-03 13:21:49` in `telegram_bot.log`: `LibreChatBridge failed to start chat: All connection attempts failed`
  - No listener on `localhost:3180` during failure
  - No Telegram-created message persisted for the failed request

## Verification Steps

1. Restart through `bin/viventium start --restart` or the helper-detached path that sets `VIVENTIUM_DETACHED_START=1`.
2. Confirm `curl -s -o /dev/null -w "%{http_code}" http://localhost:3180/health` returns `200`.
3. Submit a synthetic Telegram chat request with the configured shared secret and confirm `{ streamId, conversationId }` is returned.
4. Kill only the LibreChat frontend dev server process.
5. Re-check `http://localhost:3180/health` and repeat the synthetic Telegram chat request.
6. Kill only the real LibreChat API child process and leave any parent `npm`/`nodemon` process alive.
7. Confirm the detached LibreChat API watchdog restores `http://localhost:3180/health`.
8. Repeat the synthetic Telegram chat request and confirm Mongo records the ingress and resulting conversation/message updates.

## Result

- 2026-04-03: launcher hardening added so the direct detached LibreChat fallback backgrounds both
  backend and frontend and waits on both, instead of `exec`-ing the frontend process.
- 2026-04-07: launcher hardening added a detached LibreChat API watchdog for the dead-child/live-parent
  backend failure mode, and Telegram media transcription failures were split from normal transcript text.
- 2026-04-03 verification on the canonical App Support runtime:
  - `VIVENTIUM_DETACHED_START=1 bin/viventium start --restart` completed the detached launch path
    without the old direct-fallback supervision break.
  - `curl http://localhost:3180/health` returned `200` / `OK`.
  - `http://localhost:3190` was not reachable during verification, which made this a meaningful
    degraded-state proof for Telegram.
  - A synthetic `POST /api/viventium/telegram/chat` request returned `200` with a new `streamId`
    and `conversationId`.
  - Mongo `viventiumtelegramingressevents` recorded the new ingress for the linked Telegram test
    account.
- 2026-04-07 automated verification:
  - release contract tests now assert the detached watchdog pid/log contract and restart probes
  - Telegram voice-media tests now assert oversized/download-failure paths return structured media
    errors instead of raw transcript text
- 2026-04-19 live helper-path re-verification:
  - The live installed checkout under `~/viventium` had drifted from tracked source and was missing
    the detached watchdog launcher logic until it was re-aligned with the current source launcher.
  - `bin/viventium launch` on the installed checkout created the detached watchdog pid contract and
    helper logs reported `Started detached LibreChat API watchdog`.
  - Killing only the real `node api/server/index.js` child dropped `http://localhost:3180/health`
    immediately while nodemon wrapper processes still survived.
  - About 22 seconds later the detached watchdog had restored a fresh backend child, logs reported
    `LibreChat API after detached backend restart ready`, and `http://localhost:3180/health`
    returned `OK` again.
  - A signed synthetic `POST /api/viventium/telegram/chat` request returned `200` with
    `status=started`, a `streamId`, and a `conversationId` after the recovery.
