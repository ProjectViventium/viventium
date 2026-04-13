# Telegram Media Downloads QA Report

Date: 2026-04-07

## Summary
The Telegram bridge now classifies Telegram's hosted-Bot-API oversize failure honestly, keeps that failure out of LibreChat submission, hardens oversize classification for multiple Telegram/HTTP 413 phrasings, and restarts cleanly on the live machine after launcher parity fixes.

## Automated Checks
- Passed: `python3 -m py_compile scripts/viventium/config_compiler.py viventium_v0_4/telegram-viventium/TelegramVivBot/utils/scripts.py viventium_v0_4/telegram-viventium/TelegramVivBot/config.py viventium_v0_4/telegram-viventium/TelegramVivBot/bot.py`
- Passed: `bash -n viventium_v0_4/viventium-librechat-start.sh`
- Passed: `python3 -m pytest tests/release/test_config_compiler.py -q`
- Passed: `python3 -m pytest tests/release/test_telegram_transcription_error_contract.py -q`
- Passed: `python3 -m pytest tests/release/test_stack_port_probe_timeouts.py -q`
- Passed: `python3 -m pytest viventium_v0_4/telegram-viventium/tests/test_voice_preferences.py -q`

## Live Runtime Evidence
- Fresh stack start reached LibreChat API readiness at 19:57:44 local time.
- Fresh Telegram bridge startup lines appeared at 19:57:45-19:57:47 local time in `telegram_bot.log`.
- Live endpoints after restart returned `200`:
  - `http://localhost:3180/health`
  - `http://localhost:3190/`
  - `http://localhost:3300/`

## Oversize Reproduction
- Direct reproduction against the real failing Telegram `file_id` through `download_telegram_file_result(...)` returned:
  - `file_too_large`
- Direct reproduction against the same `file_id` through `transcribe_video(..., media_label="video")` returned:
  - `error_code = file_too_large`
  - `error_text = This video is too large to transcribe in Telegram right now.`

## Product Truth
- Hosted Telegram Bot API installs cannot download media above Telegram's hosted `getFile` ceiling.
- The product now reports that condition honestly instead of saying only `Temporarily unable to download this video from Telegram. Please retry.`
- If oversized Telegram videos must truly download and transcribe, the install still needs a local Telegram Bot API server configured through canonical config under `integrations.telegram`.

## Remaining Limitation
This QA pass proves the live bridge now gives the correct oversized-media outcome on this machine. It does not prove unlimited Telegram media downloads, because this install is still using Telegram's hosted Bot API rather than a local Bot API server.

## Second Opinion
- Claude review-only pass found no blockers for telling the user the live hosted-Bot-API oversized-file behavior is now correct.
- Claude suggested broadening oversize exception matching beyond the exact `File is too big` wording; that hardening was added and retested in this pass.
