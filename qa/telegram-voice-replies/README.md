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

Observed drift at the time, superseded by the 2026-05-30 correction below:

- Telegram voice-note turns requested LibreChat voice-call mode, but text turns with
  `ALWAYS_VOICE_RESPONSE=true` only synthesized audio after the LLM completed.
- That meant always-voice text replies could be spoken without the main agent receiving the
  voice-mode Cartesia prompt before generation.
- Proactive follow-up voice synthesis used rendered display text instead of the raw assistant text,
  so Cartesia voice-control tags could be lost before TTS.
- Telegram display rendering did not have the modern voice display sanitizer, so model-authored
  voice-control markers could appear in user-visible text.
- Telegram Cartesia TTS preserved SSML in the transcript, but did not set
  `generation_config.emotion` from the LLM-selected `<emotion value="..."/>` tag.

Historical fix, superseded by the 2026-05-30 correction below:

- Telegram formerly computed the voice-call-mode generation route from the same preferences used
  for final audio delivery. Current product truth has split those concerns: preferences control
  audio delivery only, while Telegram keeps LibreChat voice-call mode false.
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
  - LibreChat receives the turn with `voiceMode=false`, `viventiumSurface=telegram`, and
    `viventiumInputMode=voice_note`.
  - Telegram receives the text-mode reply.
  - Telegram also receives an audio reply synthesized with Cartesia Sonic-3 and the Lyra voice ID.
- Turn on always-voice replies and send a Telegram text message.
- Expected:
  - LibreChat receives the turn with `voiceMode=false`, `viventiumSurface=telegram`, and
    `viventiumInputMode=text`.
  - The main agent uses the normal Telegram text prompt/model path; always-voice does not opt into
    the LiveKit Voice Call LLM override or voice-call prompt.
  - Telegram text hides voice-control markup.
  - Telegram audio uses the selected saved Speaking voice after speech-safe cleanup.
- Turn off voice replies and send either text or voice input.
- Expected:
  - No Telegram audio reply is sent.
  - LibreChat is not put into voice-call mode for that turn.

## 2026-05-30 Product-Truth Correction

The 2026-04-28 parity follow-up treated Telegram audio replies as if they should request LibreChat
`voiceMode=true`. That interpretation is now corrected: Telegram voice-note and always-voice replies
are text-mode turns with optional audio delivery on top. The shared Speaking route is only a TTS
route-sharing contract; it is not the LiveKit Voice Call LLM override contract.

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

## 2026-04-28 Saved Route Cache Drift

Observed state:

- A Telegram voice-note turn reached LibreChat with voice-mode enabled and produced an assistant
  response containing a model-authored nonverbal marker.
- Telegram-visible text correctly hid the marker.
- The linked user's saved modern Speaking route was Cartesia/Lyra, but the Telegram bot TTS log
  reported `route_cached=0` and then loaded the local Chatterbox runtime.
- The exact text synthesized on that turn was the assistant raw text after deterministic TTS
  cleanup; because no Cartesia request happened, Cartesia emotion tags/config could not apply.

Root cause:

- LibreChat returned the resolved voice route to the Python bridge.
- The bridge cached it under the per-user conversation key used for history.
- Final Telegram audio delivery looked up the route by raw Telegram chat id.
- Those keys differ for the LibreChat-backed Telegram runtime, so the route lookup missed and TTS
  fell back to process defaults.

Fix:

- Cache the resolved voice route under all stable delivery keys: conversation key, raw Telegram chat
  id, and LibreChat conversation id.
- Final Telegram TTS also falls back to the conversation key when reading the cache.
- `[TG_VOICE]` now logs the effective resolved TTS provider/source, so a future route miss shows the
  actual provider being used instead of only `default`.

Verification:

- Added regression coverage that `ask_stream_async` caches the resolved route under all delivery keys.
- Added regression coverage that final Telegram TTS prefers the per-user conversation route when
  the raw Telegram chat id cache entry is absent.
- Passed: `uv run --with pytest --with pytest-asyncio python -m pytest ../tests/test_bot_stream_preview.py ../tests/test_librechat_bridge.py ../tests/test_tts.py ../tests/test_voice_preferences.py ../tests/test_singleton.py -q`
- Live local restart verified that the helper/stack owner, Telegram bot process, and bot working
  directory all point to the active development checkout, with no stale Telegram launchctl job left.

## 2026-04-28 Cartesia Segment WAV Click Incident

Observed state:

- A fresh Telegram voice-note turn used the saved Cartesia route:
  `provider=cartesia source=saved route_cached=1`.
- The generated TTS input was long enough to produce multiple Cartesia emotion segments.
- Runtime failed while merging Cartesia WAV chunks, then returned raw byte concatenation.
- The user heard sharp clicks/flicks around sentence boundaries.
- The user heard different emotions, but did not hear an obvious laugh.

Root cause:

- Cartesia WAV chunks may carry placeholder frame metadata.
- The merge helper copied the whole input WAV params, including input frame count, into the output
  writer before writing all joined frames.
- Python's WAV writer rejected that header state and the fallback concatenated complete WAV files.
- Raw-concatenated WAV files contain embedded RIFF headers between audio bodies, which explains the
  audible clicks.

Laughter evidence:

- The turn did reach Cartesia, so this was not the earlier route-cache drift.
- Runtime did not have raw TTS transcript debug enabled for that turn.
- Persisted assistant text and Telegram-visible text are intentionally sanitized, so they cannot
  prove whether `[laughter]` was present in the actual Cartesia transcript.

Fix:

- The Cartesia WAV merge now writes a fresh output WAV header from stable audio params only:
  channel count, sample width, and frame rate.
- The merge no longer copies the input chunk frame count into the output writer.
- Merge failures no longer fall back to raw-concatenating complete WAV files.
- Telegram voice logs now include non-secret structural marker counts for the raw TTS text and each
  Cartesia segment, including `[laughter]` count and emotion/break/speed/volume/spell tag counts.
- TTS debug text now uses JSON-escaped strings so future opt-in transcript logs preserve markup and
  whitespace shape.

Verification:

- Added a regression that reproduces Cartesia-style placeholder WAV/data sizes and verifies the
  merged result has one RIFF header and playable joined frames.
- Added regression coverage that mismatched WAV segment params are rejected instead of raw-concatted.
- Added regression coverage for structural voice-marker counts.
- Passed: `uv run --with pytest --with pytest-asyncio python -m pytest ../tests/test_bot_stream_preview.py ../tests/test_librechat_bridge.py ../tests/test_tts.py ../tests/test_voice_preferences.py ../tests/test_singleton.py -q`

## 2026-05-07 xAI Wrapper Tag Display Leak

Observed state:

- A Telegram voice-mode reply displayed an xAI wrapper closing tag (`[/soft]`) in the visible text.
- The same class of leak could also expose well-formed xAI angle wrapper tags in Telegram HTML
  rendering because Telegram display cleanup had Cartesia coverage but no xAI wrapper coverage.

Root cause:

- xAI wrapping tags are documented as angle tags such as `<soft>TEXT</soft>`.
- The Telegram display sanitizer stripped generic lowercase bracket stage directions like `[soft]`
  but did not recognize slash-prefixed malformed wrapper remnants like `[/soft]`.
- Telegram display sanitizer also did not strip well-formed xAI angle wrappers, even though the
  LibreChat/web display sanitizer did.

Fix:

- Telegram display cleanup now reads the shared xAI capability contract and strips xAI wrapping
  tags for user-visible text:
  - well-formed angle wrappers preserve inner text
  - orphan angle wrapper tags are removed
  - square pseudo-wrapper tags such as `[soft]` and `[/soft]` are removed
- xAI Telegram TTS cleanup strips malformed square pseudo-wrapper tags before calling xAI REST TTS.
  Well-formed documented xAI tags remain available for xAI synthesis.
- xAI Telegram TTS cleanup also strips Cartesia-only bracket aliases such as `[soft laugh]`,
  `[gentle sigh]`, and `[breath out]` so a Cartesia-trained response cannot leak unsupported
  stage directions into xAI audio.
- LiveKit voice display/fallback cleanup now strips the same malformed xAI pseudo-wrapper tags so
  transcript display and non-xAI fallbacks do not regress independently.
- The LiveKit xAI plugin endpoint/sample-rate override now fails loudly if the pinned plugin stops
  exposing the constants the runtime patches.

Verification:

- Synthetic reproduction `Hello.[/soft] Next sentence.` sanitizes to `Hello. Next sentence.` for
  Telegram display/rendering.
- Passed: `python3 -m py_compile TelegramVivBot/utils/librechat_bridge.py TelegramVivBot/utils/tts.py voice-gateway/sse.py voice-gateway/worker.py`
- Passed: `TelegramVivBot/.venv/bin/python -m pytest tests/test_librechat_bridge.py tests/test_tts.py -q`
- Passed: `TelegramVivBot/.venv/bin/python -m pytest -q` (`264 passed`)
- Passed: `voice-gateway/.venv/bin/python -m pytest tests/test_sse.py tests/test_worker_ref_audio_validation.py -q`
- Passed: `voice-gateway/.venv/bin/python -m pytest tests -q` (`221 passed`, one existing `audioop` deprecation warning)
- Passed: LibreChat `surfacePrompts` and Telegram route Jest tests.
