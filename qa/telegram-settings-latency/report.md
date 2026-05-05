# Telegram Settings Latency QA Report

Date: 2026-05-02

## Findings Addressed

- `/info` previously awaited delayed message cleanup, which slept for 60 seconds inside the command
  handler and could queue the Preferences callback.
- The `/info` menu was part of the delayed deletion list, so delayed cleanup could remove the
  interactive menu before the callback was processed.
- Preferences Back rendering could synchronously fetch the call-link URL.
- Voice preference toggles synchronously posted preference updates to LibreChat.
- The config compiler had drifted from the documented Telegram STT boundary by inheriting local
  Whisper when Telegram STT was omitted.

## Checks

- `cd viventium_v0_4/telegram-viventium && uv run python -m py_compile TelegramVivBot/bot.py TelegramVivBot/config.py TelegramVivBot/utils/scripts.py TelegramVivBot/utils/singleton.py TelegramVivBot/utils/stt_env.py`
  - Result: passed.
- `uv run --with pyyaml python -m py_compile scripts/viventium/config_compiler.py`
  - Result: passed.
- `bash -n viventium_v0_4/viventium-librechat-start.sh`
  - Result: passed.
- `cd viventium_v0_4/telegram-viventium && TelegramVivBot/.venv/bin/python -m pytest tests -q`
  - Result: `232 passed`.
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_config_compiler.py -q`
  - Result: `68 passed`.
- `uv run --with pytest python -m pytest tests/release/test_telegram_lazy_startup_contract.py tests/release/test_telegram_media_prereqs.py tests/release/test_telegram_transcription_error_contract.py -q`
  - Result: `14 passed`.
- `bin/viventium compile-config`
  - Result: generated Telegram service env must use `VIVENTIUM_TELEGRAM_STT_PROVIDER=whisper_local`
    when the global voice STT provider is local Whisper and Telegram has no explicit override.
- Runtime file mode check
  - Result: generated `telegram.config.env` and `runtime.env` were `0600`.
- Detached runtime restart and status check
  - Result: Viventium returned to ready; Telegram Bridge, Telegram Codex, LibreChat API, LibreChat
    frontend, and Modern Playground were `Running`.
- Real Telegram Desktop `/info` -> Preferences QA
  - Result: Preferences opened in-place; bot log reported `open_menu edit=620ms total=621ms`.
  - Result: Computer Use screenshot capture confirmed the Preferences menu remained visible well
    past the old delayed-cleanup window.
  - Note: Computer Use could capture Telegram state, but its coordinate click action returned
    `noWindowsAvailable` for this window; coordinate clicks were driven through native macOS events.
- ClaudeViv review
  - Result: no blockers. Claude flagged a possible race where the deferred Call button refresh
    could overwrite an already-open Preferences menu.
  - Follow-up action taken in this pass: pending `/info` refreshes are now cancelled on Preferences,
    toggle, and Back callbacks, and a regression test asserts the refresh does not edit after
    navigation.

## Residual Observations

- A non-acceptance keyboard-navigation attempt generated a synthetic one-character Telegram turn.
  No acceptance claim in this report depends on that turn.
