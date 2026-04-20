# Telegram Detached API Stability Report

## Date
- 2026-04-07

## Scope
- Prevent Telegram media transcription failures from being treated as real transcript text.
- Prevent detached Telegram/LibreChat runs from being stranded when the real API child dies but a
  parent `npm`/`nodemon` process still survives.

## Code-Level Evidence
- `TelegramVivBot/utils/scripts.py`
  - voice/video transcription now returns structured `TelegramTranscriptionResult`
  - oversized/download failures map to clean Telegram media errors instead of raw `error:` strings
- `TelegramVivBot/bot.py`
  - voice/video transcription failures now abort before LibreChat submission
  - transcript display is only used for successful transcription text
- `viventium-librechat-start.sh`
  - detached LibreChat API watchdog pid/log contract added
  - watchdog restarts backend when detached API health drops after startup

## Automated Verification
- Passed:
  - `python3 -m pytest tests/release/test_detached_librechat_supervision.py tests/release/test_detached_librechat_api_watchdog.py tests/release/test_telegram_transcription_error_contract.py -q`
  - `python3 -m pytest tests/test_voice_preferences.py -q`
- Syntax-checked:
  - `python3 -m py_compile tests/test_bot_stream_preview.py`

## Runtime Evidence
- Original Telegram bridge failure evidence from the canonical App Support runtime:
  - `telegram_bot.log` at `2026-04-07 15:58:45,088`:
    `LibreChatBridge failed to start chat: All connection attempts failed`
  - `telegram_bot.log` at `2026-04-07 16:00:14,388`:
    `LibreChatBridge failed to start chat: All connection attempts failed`
- Original detached-runtime API evidence from the same investigation:
  - `curl http://localhost:3180/health` failed
  - `curl http://127.0.0.1:3180/health` failed
  - `curl http://[::1]:3180/health` failed
  - `lsof -nP -iTCP:3180 -sTCP:LISTEN` returned no listener
- Original launcher/runtime evidence:
  - `helper-start.log` showed frontend dev-server teardown while parent launcher/runtime processes still existed
  - `pgrep -P <nodemon-pid>` showed no surviving API child under the live parent process tree
- Fix-alignment evidence:
  - watchdog contract now covers the dead-child/live-parent case
  - Telegram media errors now stop before LibreChat chat submission instead of being rendered as transcript text

## Notes
- Full live detached-runtime kill/recovery QA was not re-executed in this turn.
- Existing runtime evidence from `telegram_bot.log` and `helper-start.log` was used to confirm the
  original failure mode before implementing the structural fix.
