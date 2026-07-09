# Telegram Fallback, Audio Prompt, And Table QA Rerun - 2026-06-28

## Scope

Follow-up public-safe QA after the Telegram bridge/audio/table fixes and the follow-up fallback
classifier fix. This rerun covers:

- `TR-005`: primary provider rate-limit before visible text must retry configured fallback LLM
  before Telegram receives a terminal blocker.
- `TR-006`: Markdown pipe tables must render as readable Telegram rows.
- `TGVOICE-005`: Telegram text-mode audio turns must expose the selected TTS provider speech-control
  contract without switching to LiveKit voice mode.
- Runtime readiness for the live local Viventium surfaces that own Telegram delivery.

## Checks Run

- Live runtime status:
  - PASS: LibreChat API, LibreChat frontend, Modern Playground, Telegram Bridge, Telegram Codex,
    Conversation Recall, SearXNG, Firecrawl, Google Workspace MCP, Microsoft 365 MCP, and macOS
    helper were running.
  - PASS: `Secondary/Fallback AI` showed `Ready`.
  - NOTE: Overall status still reported attention needed for an unrelated scheduler issue and
    primary connected-account setup guidance.
- LibreChat automated regression suite:
  - Command: `npm test -- --runInBand server/routes/viventium/__tests__/telegram.spec.js server/services/viventium/__tests__/surfacePrompts.spec.js server/services/viventium/__tests__/agentLlmFallback.spec.js server/controllers/agents/client.test.js server/services/viventium/__tests__/cortexFallbackText.spec.js`
  - PASS: 249 tests.
  - Covered fallback retry for public hyphenated `rate-limited` wording, Telegram audio-request
    voice-provider injection, string `voiceMode` normalization, xAI Telegram audio prompt contract,
    route behavior, and deferred fallback text class normalization.
- Telegram Python regression suite:
  - Command: `TelegramVivBot/.venv/bin/python -m pytest tests/test_librechat_bridge.py tests/test_telegram_html.py tests/test_tts.py tests/test_voice_preferences.py tests/test_bot_stream_preview.py -q`
  - PASS: 203 tests.
  - Covered bridge error classification, non-spoken bridge errors, Telegram HTML table conversion,
    provider-specific TTS sanitization, voice preferences, and bot preview/audio handling.
  - Follow-up fix: the suite initially exposed order-dependent test pollution between
    `test_librechat_bridge.py` and `test_bot_stream_preview.py`; the stream-preview test now clears
    stale vendored `md2tgmd` import/path state before importing the full bot.
- Parent release-test attempt:
  - Command: `python3 -m pytest tests/release/test_telegram_transcription_error_contract.py tests/release/test_telegram_lazy_startup_contract.py tests/release/test_telegram_codex_runtime_paths.py -q`
  - BLOCKED: the default parent `python3.14` environment did not have `pytest` installed.
  - This is not counted as pass evidence.
- Playwright live browser check:
  - PASS: the local Viventium web URL opened to the Viventium login surface in a real browser.
  - PASS: snapshot showed the login form and page title `Viventium`.
  - NOTE: console contained a favicon 404 after test-content rendering; no console error was tied to
    the checked Telegram table content.
- Playwright Telegram-table visual fixture:
  - PASS: real `markdown_to_html(...)` output for a synthetic pipe table rendered as bullet rows.
  - PASS: browser DOM check returned `hasRawPipeTable=false` and `hasRows=true`.
  - PASS: snapshot showed readable `Name`, `Title`, `Company`, and `Evidence` rows instead of raw
    table pipes.

## Case Results

| Case | Result | Evidence | Remaining gap |
| --- | --- | --- | --- |
| `TR-005` | PASS automated, PARTIAL live | LibreChat fallback/client tests, Telegram bridge tests, live runtime status with fallback AI ready | A real external Telegram turn with an actual provider rate-limit was not forced against live accounts. |
| `TR-006` | PASS automated and visual | Telegram HTML tests plus Playwright DOM/screenshot evidence with synthetic public-safe table content | Real Telegram client rendering was not re-sent externally. |
| `TGVOICE-005` | PASS automated, PARTIAL live audio | Surface prompt tests, Telegram route tests, bridge payload tests, TTS sanitizer tests | Live external Telegram send/listen and audible xAI playback were not run. |
| Parent release tests | BLOCKED | Default parent Python lacks `pytest` | Needs a parent release-test environment or documented command using the intended venv. |
| Claude second opinion | BLOCKED | Local Claude CLI quota reached | Reset reported for June 29 at 3pm America/Toronto. |

## Result

This QA pass is stronger than the earlier one: it includes repeated affected suites, live runtime
status, real-browser visual evidence, and the previously order-sensitive bot preview tests. It still
does not justify a full live Telegram/audio acceptance claim because the external Telegram send/listen
and forced real provider-rate-limit paths were not run.
