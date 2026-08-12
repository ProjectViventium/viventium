# Telegram Audio Formatting And Rate-Limit QA - 2026-06-27

<!-- qa-evidence-exempt: Historical focused Telegram regression record retained as supporting evidence; it predates the full-view report format. -->

## Scope

Public-safe QA for three escaped Telegram issues:

- Telegram audio turns with xAI TTS did not receive the xAI speech-tag prompt contract because
  Telegram intentionally used `voiceMode=false`.
- Worker-style Markdown pipe tables displayed literally in Telegram.
- A provider rate limit surfaced as `Connection error. Please retry.` and could be synthesized as
  a short Telegram voice note.
- Follow-up user evidence showed a deeper fallback-parity miss: the main-agent fallback LLM contract
  did not retry when the primary failure arrived as Viventium's own public hyphenated
  `rate-limited` wording.

## Evidence

- Runtime log class review: a sanitized Telegram runtime log showed a final LibreChat stream error
  classified as provider rate limiting, followed by xAI TTS synthesis of the generic connection
  error. No raw private transcript, chat id, token, account id, local path, or attachment evidence is
  included in this report.
- Code trace: `TelegramVivBot/bot.py` computes `telegram_audio_requested` while keeping
  `voiceMode=false`; `utils/librechat_bridge.py` now forwards `telegramAudioRequested`; the
  LibreChat Telegram route now injects the saved Speaking route `voiceProvider` when audio is
  requested; `surfacePrompts.js` now exposes Telegram audio-output xAI speech tags without using
  the LiveKit voice-mode prompt.
- Renderer trace: `utils/telegram_html.py` converts Markdown pipe tables to Telegram-readable
  bullet rows before HTML escaping and formatting.
- Fallback trace: `AgentClient.sendCompletion(...)` already retries configured fallback routes for
  recoverable provider failures before visible assistant text. The escaped wording
  `The model provider rate-limited this request...` was missing from both the completion error
  classifier and fallback text predicate, so it could be treated as a generic completion error and
  skip the fallback retry.
- Follow-up local review on 2026-06-28 found one adjacent route-boundary robustness gap:
  `voiceMode` was still checked as a literal boolean while the new Telegram audio-request flag used
  tolerant boolean parsing. The route now normalizes `voiceMode` before forwarding to AgentClient
  and before saved Speaking-route provider injection.

## Checks Run

- `npm test -- --runInBand server/services/viventium/__tests__/agentLlmFallback.spec.js server/controllers/agents/client.test.js`
  - PASS, 146 tests.
  - Covered public hyphenated rate-limit wording, completion error classification, and retrying a
    configured fallback LLM before returning a terminal blocker.
- `npm test -- --runInBand server/services/viventium/__tests__/surfacePrompts.spec.js`
  - PASS, 61 tests.
  - Covered xAI Telegram audio-output prompt contract and continued Telegram text-mode behavior.
- `npm test -- --runInBand server/routes/viventium/__tests__/telegram.spec.js`
  - PASS, 33 tests.
  - Covered `telegramAudioRequested=true` with `voiceMode=false` injecting saved xAI
    `voiceProvider`.
- `npm test -- --runInBand server/routes/viventium/__tests__/telegram.spec.js server/services/viventium/__tests__/surfacePrompts.spec.js server/services/viventium/__tests__/cortexFallbackText.spec.js`
  - PASS, 102 tests.
  - Rechecked Telegram route behavior and rate-limit class normalization after the fallback fix.
- `npm test -- --runInBand server/routes/viventium/__tests__/telegram.spec.js server/services/viventium/__tests__/surfacePrompts.spec.js`
  - PASS, 95 tests on 2026-06-28.
  - Covered string `voiceMode` normalization plus Telegram audio-request voice-provider injection.
- `TelegramVivBot/.venv/bin/python -m pytest tests/test_telegram_html.py tests/test_librechat_bridge.py -q`
  - PASS, 123 tests.
  - Covered Markdown table conversion, provider rate-limit copy, non-spoken bridge errors, and
    Telegram audio-request payload forwarding.
- `TelegramVivBot/.venv/bin/python -m pytest tests/test_voice_preferences.py tests/test_tts.py -q`
  - PASS, 62 tests.
  - Covered Telegram voice gate behavior and provider-specific TTS sanitization.
- Playwright visual check on synthetic public-safe table content:
  - PASS, visible text contained readable bullet rows.
  - PASS, `hasRawPipeTable=false`.
  - A temporary local screenshot was inspected during the run; no private or account-bearing
    screenshot is included in the public repo.
- Local runtime activation/restart:
  - PASS, `dev-runtime activate-current --validate --restart --allow-protected-folder
    --allow-dirty-local-testing` completed against the active checkout.
  - PASS, follow-up status showed LibreChat API, LibreChat frontend, modern playground, and Telegram
    Bridge running.
  - NOTE, overall status still reported attention needed for an unrelated scheduler issue and
    connected-account setup guidance.

## Not Run

- Live external Telegram send/listen and audible xAI playback were not run in this pass. The public
  repo evidence is therefore PASS for automated/visual synthetic coverage and PARTIAL for live
  external Telegram audio acceptance.
- A forced real provider rate-limit against the user's live accounts was not run. The fallback
  behavior is covered by deterministic AgentClient runtime tests, and the live runtime still needs
  a natural Telegram send/listen proof when a safe account/test prompt is available.
- A Claude review-only second-opinion pass was attempted on 2026-06-28, but the local Claude CLI was
  blocked by weekly quota until June 29 at 3pm America/Toronto. No independent Claude line-by-line
  review was completed for this pass.
- No cloud push, PR, or production sync was performed.

## Result

- `TR-005`: PASS automated, PARTIAL live external Telegram. Primary provider rate-limit failures
  now classify as fallback-eligible even when they use public hyphenated `rate-limited` wording, so
  a configured valid fallback LLM is retried before Telegram receives any terminal provider-rate
  blocker. Final bridge/provider blockers remain non-spoken.
- `TR-006`: PASS automated plus Playwright visual check. Markdown pipe tables now render as readable
  Telegram rows instead of raw table syntax.
- `TGVOICE-005`: PASS automated, PARTIAL live. Telegram text-mode audio turns now carry
  `telegramAudioRequested=true`, keep `voiceMode=false`, inject the saved xAI `voiceProvider`, and
  expose documented xAI speech tags for the audio-output prompt path.
