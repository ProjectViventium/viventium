# Telegram Detached API Stability

## Purpose

Verify that detached/direct LibreChat launches keep the API available for Telegram even if the
frontend dev server exits later.

## Acceptance Contract

- Detached launch brings up LibreChat API on `3180`.
- Telegram bridge can start chat requests against LibreChat after detached launch.
- Killing the frontend dev server does not take down the LibreChat API.
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
6. Confirm Mongo records the ingress and resulting conversation/message updates.

## Result

- 2026-04-03: launcher hardening added so the direct detached LibreChat fallback backgrounds both
  backend and frontend and waits on both, instead of `exec`-ing the frontend process.
- 2026-04-03 verification on the canonical App Support runtime:
  - `VIVENTIUM_DETACHED_START=1 bin/viventium start --restart` completed the detached launch path
    without the old direct-fallback supervision break.
  - `curl http://localhost:3180/health` returned `200` / `OK`.
  - `http://localhost:3190` was not reachable during verification, which made this a meaningful
    degraded-state proof for Telegram.
  - A synthetic `POST /api/viventium/telegram/chat` request returned `200` with a new `streamId`
    and `conversationId`.
  - Mongo `viventiumtelegramingressevents` recorded the new ingress at
    `2026-04-03T17:39:12.370Z` for Telegram user/chat `160553220`.
