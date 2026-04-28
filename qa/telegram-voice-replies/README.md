# Telegram Voice Replies QA

## Scope

Validate that Telegram voice-note replies reuse the linked user's saved modern voice Speaking route
and do not drift from the browser voice selector.

## 2026-04-28 RCA

Observed state:

- The linked Telegram user's saved voice route had `tts.provider=cartesia`.
- The saved Cartesia variant was a voice ID for the Lyra persona.
- The Telegram route correctly returned the saved voice route to the bot.
- The Telegram TTS utility incorrectly treated the Cartesia variant as `model_id`.

Impact:

- Cartesia received a voice ID in the `model_id` field.
- Voice-note text could still reach LibreChat, but TTS synthesis could fail before Telegram sent
  audio back.

Fix:

- Cartesia Telegram TTS now treats variants as voice IDs.
- Cartesia Telegram TTS always sends `model_id=sonic-3`.
- Legacy saved Cartesia model variants (`sonic-2`/`sonic-3`) fall back to the configured voice ID
  instead of being sent as voice IDs.
- Telegram Cartesia defaults now use `Cartesia-Version=2026-03-01`.

## Verification

- Passed: `python3 -m py_compile TelegramVivBot/config.py TelegramVivBot/utils/tts.py TelegramVivBot/bot.py`
- Passed: `uv run --with pytest --with pytest-asyncio --with httpx --with requests --with pillow --with fastapi python -m pytest tests/test_tts.py tests/test_voice_preferences.py tests/test_stt_env.py -q`
- Passed: real Telegram TTS adapter smoke against Cartesia with saved Cartesia/Lyra route returned
  non-empty WAV bytes.
- Broader Telegram suite ran with ephemeral dependencies and reached `188 passed`; the remaining
  failure is the pre-existing `test_no_response_tag.py::TestStripTrailingNTA::test_nta_in_middle_not_stripped`,
  unrelated to TTS route selection.
- Blocked: requested ClaudeViv second-opinion review could not run because the local Claude CLI was
  rate-limited during this QA pass.

## Acceptance Contract

- Change the modern voice Speaking route to Cartesia / Lyra.
- Send a Telegram voice note from the linked account.
- Expected:
  - Telegram transcribes the voice note.
  - LibreChat receives the turn with `voiceMode=true`.
  - Telegram receives the text reply.
  - Telegram also receives an audio reply synthesized with Cartesia Sonic-3 and the Lyra voice ID.
