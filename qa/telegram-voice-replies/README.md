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

## 2026-04-28 Parity Follow-Up

Observed drift:

- Telegram voice-note turns requested LibreChat `voiceMode=true`, but text turns with
  `ALWAYS_VOICE_RESPONSE=true` only synthesized audio after the LLM completed.
- That meant always-voice text replies could be spoken without the main agent receiving the
  voice-mode Cartesia prompt before generation.
- Proactive follow-up voice synthesis used rendered display text instead of the raw assistant text,
  so Cartesia voice-control tags could be lost before TTS.
- Telegram display rendering did not have the modern voice display sanitizer, so model-authored
  voice-control markers could appear in user-visible text.
- Telegram Cartesia TTS preserved SSML in the transcript, but did not set
  `generation_config.emotion` from the LLM-selected `<emotion value="..."/>` tag.

Fix:

- Telegram now computes the voice-mode generation route from the same preferences used for final
  audio delivery:
  - voice note + voice enabled -> `voiceMode=true`
  - text + always voice + voice enabled -> `voiceMode=true`
  - voice disabled -> no voice-mode prompt and no audio reply
- `input_mode` stays tied to actual input type, so always-voice text messages still send
  `input_mode=text`.
- Raw assistant text is preserved for TTS while Telegram-visible text uses a deterministic display
  sanitizer for Cartesia markup.
- Proactive callbacks use `raw_message` for TTS and sanitized HTML for display.
- Telegram Cartesia requests parse model-authored emotion tags and set the matching
  `generation_config.emotion`; multiple emotion regions are synthesized as separate WAV segments
  and merged.

Verification:

- Passed: `python3 -m py_compile TelegramVivBot/bot.py TelegramVivBot/utils/voice.py TelegramVivBot/utils/librechat_bridge.py TelegramVivBot/utils/tts.py`
- Passed: `uv run --with pytest --with pytest-asyncio --with httpx --with requests --with pillow --with fastapi python -m pytest tests/test_tts.py tests/test_voice_preferences.py tests/test_librechat_bridge.py -q`

## Acceptance Contract

- Change the modern voice Speaking route to Cartesia / Lyra.
- Send a Telegram voice note from the linked account.
- Expected:
  - Telegram transcribes the voice note.
  - LibreChat receives the turn with `voiceMode=true`.
  - Telegram receives the text reply.
  - Telegram also receives an audio reply synthesized with Cartesia Sonic-3 and the Lyra voice ID.
- Turn on always-voice replies and send a Telegram text message.
- Expected:
  - LibreChat receives the turn with `voiceMode=true` and `input_mode=text`.
  - The main agent may emit Cartesia Sonic-3 markup because the voice prompt was present before
    generation.
  - Telegram text hides voice-control markup.
  - Telegram audio preserves the raw markup for Cartesia and uses the selected saved Speaking
    voice.
- Turn off voice replies and send either text or voice input.
- Expected:
  - No Telegram audio reply is sent.
  - LibreChat is not put into voice-mode output for that turn.

## 2026-04-28 Delayed Voice Reply Incident

Observed state:

- A Telegram voice note was transcribed and the text reply was delivered quickly.
- The matching audio reply arrived roughly two minutes later.
- Runtime process inspection found two `bot.py` polling processes for the same BotFather token:
  one supported live process and one stale process from a source checkout.
- Both logs showed repeated Telegram `getUpdates` conflict errors during the incident window.
- A direct Cartesia Lyra smoke test for comparable text returned WAV bytes in about one second, so
  Cartesia synthesis was not the source of the two-minute delay.

Fix:

- The Telegram bot now acquires a same-token singleton lock before polling begins.
- A second local process for the same BotFather token exits before calling Telegram `getUpdates`,
  preventing split/competing pollers across checkouts or stale helpers.
- The lock is stored under a durable Viventium runtime lock directory and records only the owner
  PID, never the BotFather token.
- If Telegram still reports a `getUpdates` conflict at runtime, the error handler now logs the
  duplicate-poller cause directly instead of a generic traceback.
- Normal runtime logs now include non-secret `[TG_VOICE]` phase logs for gate decisions, TTS chunk
  durations/bytes, and Telegram audio send duration.

Verification:

- Passed: `python3 -m py_compile TelegramVivBot/bot.py TelegramVivBot/utils/singleton.py TelegramVivBot/utils/voice.py TelegramVivBot/utils/librechat_bridge.py TelegramVivBot/utils/tts.py`
- Passed: `uv run --with pytest --with pytest-asyncio --with httpx --with requests --with pillow --with fastapi python -m pytest tests/test_singleton.py tests/test_tts.py tests/test_voice_preferences.py tests/test_librechat_bridge.py -q`
- Passed: process cleanup left one Telegram bot process.
- Passed: second source-checkout startup with the same token exited before polling with code 78.
