# Claude Review Prompt: Streaming TTS Boundary Final Review

You are review-only. Do not make code changes. Use maximum effort.

## Objective

Review the current working tree fix for Viventium modern LiveKit playground TTS boundary regressions:

- assistant text displays and persists punctuation such as `?`, but spoken TTS can miss it
- prior fixes for literal spoken `dot` / standalone period must remain intact
- prior fixes for missing spaces between streamed words must remain intact
- emotion markers such as `[laughter]` can be split across model deltas and must not leak partial marker text into TTS
- do not overcomplicate the runtime path or add prompt-text/provider-name heuristics
- leave `sync_transcription` behavior unchanged

## Required Local Sources

Read these repo files and current uncommitted diffs:

- `docs/requirements_and_learnings/01_Key_Principles.md`
- `docs/requirements_and_learnings/06_Voice_Calls.md`
- `viventium_v0_4/docs/VOICE_CALLS.md`
- `qa/modern-playground-voice/cases.md`
- `viventium_v0_4/voice-gateway/librechat_llm.py`
- `viventium_v0_4/voice-gateway/fallback_tts.py`
- `viventium_v0_4/voice-gateway/cartesia_tts.py`
- `viventium_v0_4/voice-gateway/tests/test_librechat_llm.py`
- `viventium_v0_4/voice-gateway/tests/test_fallback_tts.py`
- `viventium_v0_4/voice-gateway/tests/test_cartesia_tts.py`

## Current Fix Shape

The intended root cause is not just one punctuation token. The old LLM-side stream buffer could max-length flush a whole buffer when it ended on a word, making downstream provider continuation depend on a following chunk retaining leading whitespace. Some provider paths can collapse that boundary, yielding speech/text like `clearedis`, `what'syour`, or missing question prosody. The current fix should make `_VoiceTtsDeltaBuffer` own safe phrase boundaries:

- emit max-length chunks only through safe whitespace boundaries
- keep the trailing word buffered so the next word or punctuation can attach
- preserve delayed `?` and `!`, including quote-wrapped forms
- keep standalone `.` dropped unless it is decimal/contextual
- preserve decimal splits like `3` + `.` + `14`
- buffer split bracket emotion markers in Cartesia and drop unmatched final bracket tails

## Evidence Already Run

Focused and full voice-gateway tests passed locally after the current fix:

- `55 passed in 1.08s`
- `312 passed, 1 warning, 20 subtests passed in 2.01s`

Synthetic matrix outputs after the current fix:

- delayed question: `["Good morning. Sleep okay ", "?"]` -> `Good morning. Sleep okay?`
- quoted question: `["She asked, “Sleep okay ", "?”"]` -> `She asked, “Sleep okay?”`
- decimal split: `["The answer is 3", ".", "14 today."]` -> `The answer is 3.14 today.`
- missing-space resilience: `["Nice, invoice cleared", " is a real milestone."]` with small max -> chunks `["Nice, invoice ", "cleared is a real milestone."]`
- no-safe-whitespace: `["Supercalifragilistic", "."]` -> `Supercalifragilistic.`
- provider quoted punctuation: `Sleep okay?" she asked.`
- Cartesia split marker: `Ha [laughter] okay?`
- Cartesia dangling final marker: `Ha [laugh` final -> `Ha `

Runtime alignment after restart:

- local prod web is reachable at `http://localhost:3190`
- modern playground is reachable at `http://localhost:3300`
- LiveKit is running at `ws://localhost:7888`
- voice worker registered with LiveKit under `librechat-voice-gateway` from the current checkout

Audible user-grade playground QA is still a separate completion gate; review the code/tests now and explicitly state any remaining runtime QA requirement.

## Questions

1. Is the current fix root-cause-aligned, or did it overfit/overcomplicate the symptom?
2. Are there remaining punctuation, spacing, quote, decimal, or emotion-marker cases that can still leak bad text into provider TTS?
3. Did the fix preserve latency intent by only holding text where speech correctness requires it?
4. Are docs and QA cases aligned with the implementation?
5. What exact additional tests or live QA are required before calling this fully done?

Return JSON with:

- `full_final_recommendations`
- `summary`
- `findings`
- `risks`
- `tests_to_add`
- `alternatives`
- `evidence`
