# Modern Playground Voice QA: Delayed Question-Mark TTS Regression

## Scope

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`
- QA case: `qa/modern-playground-voice/cases.md` `MPV-012` and `MPV-014`
- Surface: Modern Playground voice through Voice Gateway, LibreChat streaming deltas, LiveKit TTS
- Status: automated regression PASS and local runtime live; live audible post-restart QA still
  required before release-ready closure

## Evidence Summary

- Runtime logs showed the active voice route used local PyWhisperCpp STT and xAI standalone TTS with OpenAI fallback.
- Runtime logs did not include `[VoiceTTSInput]` provider-bound payload lines because exact TTS input logging was not enabled for the current run. That remains an observability gap for incident forensics, although the source-level instrumentation exists.
- Database inspection confirmed the displayed/stored assistant response kept the final `?`, so the regression was after response storage/display and before provider-bound speech.
- Focused repro on the pre-fix code:
  - `["Good morning. Sleep okay ", "?"]` emitted `Good morning. Sleep okay ` and dropped the delayed `?`.
  - `["Good morning. Sleep okay", "?"]` emitted `Good morning. Sleep okay?`.
  - Provider-bound normalizer also suppresses standalone `?`, which is correct only when the LLM-side buffer prevents it from becoming orphaned.
- LiveKit 1.5.10 local source inspection confirmed `Agent.default.tts_node` forwards streaming TTS chunks directly, while non-streaming TTS uses `StreamAdapter` with a sentence tokenizer. The LiveKit sentence tokenizer preserves `?` when it receives it with the sentence.
- Follow-up RCA widened the bug from a question-mark-only failure to a boundary ownership issue:
  length-driven flushing could emit a whole buffer ending on a word and leave the next chunk's leading
  whitespace as the only thing preserving the word boundary. Provider continuation can collapse that
  boundary, causing strings such as `clearedis` or `what'syour`.

## Fix Applied

- `_VoiceTtsDeltaBuffer` now refuses the whitespace flush for a short unfinished sentence tail after a prior terminal sentence, allowing a delayed `?` or `!` token to attach before text is emitted to TTS.
- Whitespace and length-driven flushing now emit only through a safe whitespace boundary and keep
  the trailing word buffered, so the next word or punctuation attaches before provider TTS receives
  it.
- Low-latency whitespace flushing still starts speech early for single ongoing sentences and longer
  post-terminal tails, but it leaves the trailing word buffered for the next word or punctuation.
- Provider-bound final guard still prevents standalone periods from reaching providers where they may be
  spoken literally, but now preserves delayed `?`/`!` when a following text chunk lets them travel as
  prosody punctuation instead of disappearing.
- Cartesia streaming emotion parsing buffers incomplete bracket markers, so split controls such as
  `[laugh` + `ter]` do not leak literal marker fragments into TTS.

## Automated QA

- Focused repro after fix:
  - `["Good morning. Sleep okay ", "?"]` -> `Good morning. Sleep okay?`
  - `["Right. That landed ", "!"]` -> `Right. That landed!`
  - `["Nice, invoice cleared ", "is a real milestone."]` still preserves the inter-word space.
  - `["Nice, invoice cleared", " is a real milestone."]` with small max-char flushing emits
    `Nice, invoice ` then `cleared is a real milestone.`, preserving the word boundary.
  - `["Did you really mean the deployment should roll back tonight ", "?"]` preserves the final
    question mark instead of dropping it as orphan punctuation.
  - `["The answer is 3", ".", "14 today."]` preserves `3.14`.
  - `["She asked, “Sleep okay ", "?”"]` preserves `She asked, “Sleep okay?”`.
  - `["Supercalifragilistic", "."]` waits for punctuation when there is no safe whitespace split.
  - `["Ha ", "[laugh", "ter] okay?"]` normalizes the split marker as `[laughter]`; unmatched final
    `[laugh` is dropped instead of spoken.
- Focused tests:
  - `tests/test_librechat_llm.py::TestLibreChatStreamingRun`
  - `tests/test_librechat_llm.py::TestVoiceTtsDeltaBuffer`
  - `tests/test_fallback_tts.py`
  - `tests/test_cartesia_tts.py`
  - Result: `110 passed`
- Full voice-gateway tests:
  - Result: `313 passed, 1 warning, 20 subtests passed`
- Telegram voice/sanitizer parity checks:
  - `telegram-viventium/tests/test_tts.py`
  - `telegram-viventium/tests/test_stt_env.py`
  - Result: `58 passed`
- Browser/runtime checks:
  - Playwright opened `http://localhost:3300`; Modern Playground rendered with local Whisper.cpp
    listening and local Chatterbox speaking options.
  - Playwright opened `http://localhost:3190`; LibreChat local prod rendered the login page with no
    console errors.
  - `bin/viventium status` reported Viventium ready with local prod, Modern Playground, Telegram
    Bridge, Telegram Codex, recall, Google Workspace MCP, SearXNG, Firecrawl, and Microsoft 365 MCP
    running.
- Claude review-only second opinion confirmed the initial RCA and recommended the provider-bound
  `?`/`!` hardening while keeping the standalone-period guard. A fresh final review after the
  widened fix found one adjacent long-single-sentence delayed-question gap; that case was fixed and
  added to the regression suite.

## Remaining QA Gate

- Run a real Modern Playground voice call with exact TTS input logging enabled in the local private run.
- Confirm the audible result preserves question prosody and does not say `dot`/`period`.
- Correlate browser transcript, DB row, voice logs, and `[VoiceTTSInput]` lines.
