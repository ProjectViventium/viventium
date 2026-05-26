# Claude Review Prompt: Streaming TTS Question-Mark Regression

You are review-only. Do not make code changes. Use maximum effort and challenge the proposed fix with evidence from the repo, LiveKit behavior, and tests.

## Objective

Review a Viventium LiveKit voice/TTS regression where displayed assistant text includes a question mark, but the spoken TTS can sound like it did not receive or honor the question mark. The immediate example is equivalent to:

- user text: `Hey dude good morning`
- assistant display / DB text: `Good morning. Sleep okay?`

The user also previously reported literal `dot` / missing-space TTS bugs, so the fix must preserve the prior "do not speak standalone period" behavior and must not slow normal response starts more than necessary.

## Required Repo Sources

Read these files first:

- `docs/requirements_and_learnings/01_Key_Principles.md`
- `docs/requirements_and_learnings/06_Voice_Calls.md`
- `viventium_v0_4/docs/VOICE_CALLS.md`
- `qa/modern-playground-voice/cases.md`
- `viventium_v0_4/voice-gateway/librechat_llm.py`
- `viventium_v0_4/voice-gateway/fallback_tts.py`
- `viventium_v0_4/voice-gateway/sse.py`
- `viventium_v0_4/voice-gateway/tests/test_librechat_llm.py`
- `viventium_v0_4/voice-gateway/tests/test_fallback_tts.py`
- `viventium_v0_4/voice-gateway/tests/test_sse.py`

## External/Runtime Evidence Already Collected

LiveKit Python Agents 1.5.10 is installed locally. LiveKit docs/reference state:

- The STT/LLM/TTS pipeline has a `tts_node` that synthesizes speech from text segments.
- If a TTS implementation does not support native streaming, LiveKit uses a sentence tokenizer for incremental synthesis.
- The default `tts_node` can be overridden for custom text chunking.

Local LiveKit source inspection showed:

- `Agent.default.tts_node` forwards text chunks directly to `stream.push_text(chunk)` when the TTS advertises streaming.
- For non-streaming TTS, it wraps with `tts.StreamAdapter(... SentenceTokenizer(retain_format=True))`.
- `StreamAdapterWrapper` tokenizes sentence text and calls wrapped `synthesize(text)` with the token stripped.
- The LiveKit sentence tokenizer preserves question marks when it receives them with the sentence, including split input such as `["Good morning. Sleep okay ", "?"]`, producing `Good morning. Sleep okay ?`; Viventium sanitizer can normalize the space before `?` to `Good morning. Sleep okay?`.

Runtime/log findings:

- The currently running voice worker is from this checkout and uses xAI standalone TTS with OpenAI fallback.
- Recent voice logs show the call used local PyWhisperCpp STT and xAI TTS.
- The exact provider-bound `[VoiceTTSInput]` payload logging is not enabled in the current run; only latency logging is present. That is an observability gap for this incident, but unit-level repro below isolates the text-boundary bug.
- DB contains the assistant message text with the final question mark, so the issue is not the stored/displayed response losing `?`; it is between streaming/chunking and provider-bound TTS.

Focused repro run against the current code:

```text
case ['Good morning. Sleep okay ', '?']
  'Good morning. Sleep okay ' => ['Good morning. Sleep okay ']
  '?' => []
 final [] joined= 'Good morning. Sleep okay '

case ['Good morning. Sleep okay', '?']
  'Good morning. Sleep okay' => []
  '?' => ['Good morning. Sleep okay?']
 final [] joined= 'Good morning. Sleep okay?'

provider boundary seq ['Sleep okay', '?']
  'Sleep okay' => 'Sleep okay'
  '?' => '' pending_punctuation_not_forwarded
 joined 'Sleep okay'
```

Existing focused tests currently pass, but they do not cover the delayed `?` after a whitespace flush:

```text
75 passed, 20 subtests passed
```

## Provisional Root Cause

There are two interacting guards:

1. `_VoiceTtsDeltaBuffer._should_flush()` flushes when the accumulated buffer is at least `min_first_chars + 8` and ends with whitespace, even if the current trailing sentence/clause has no terminal punctuation yet.
2. `_VoiceTtsDeltaBuffer` and `_ProviderTextBoundaryNormalizer` classify all punctuation-only chunks, including `?` and `!`, as orphan punctuation after speech has started and suppress them.

When LLM streaming produces something like `Good morning. Sleep okay ` followed by `?`, Viventium emits `Good morning. Sleep okay ` before seeing the `?`; then the standalone `?` is swallowed. That explains the screenshot/DB text having `?` while TTS may have received only `Good morning. Sleep okay `.

## Candidate Fix Under Review

Make the smallest LLM-side chunker change:

- Keep prior standalone-period/decimal protections.
- Do not whitespace-flush a short trailing sentence/clause after a previous terminal sentence if that trailing sentence lacks terminal punctuation and is still under the normal max chunk length.
- In practice, `Good morning. Sleep okay ` should wait for a following `?` and emit `Good morning. Sleep okay?`.
- A single ongoing first sentence like `Nice, invoice cleared ` should still be allowed to flush on whitespace for latency, preserving the existing low-latency behavior and the missing-space fix.
- Add tests for delayed `?` and delayed `!`; preserve existing dot and decimal tests.

Possible helper shape:

```python
@staticmethod
def _has_short_unterminated_post_terminal_tail(text: str) -> bool:
    stripped = strip_voice_control_tags(text).strip()
    if stripped[-1:] in ".!?;:":
        return False
    terminal_matches = list(re.finditer(r"[.!?;:]", stripped))
    if not terminal_matches:
        return False
    tail = stripped[terminal_matches[-1].end():].strip()
    return bool(tail) and len(tail) < self._max_chars
```

Then `_should_flush()` refuses the whitespace flush when that helper is true; max_chars still protects long chunks.

## Questions For Claude

1. Is the root cause supported by the code, docs, and repro, or is there a more likely culprit?
2. Is the proposed LLM-side chunker fix the least risky path?
3. Should provider-bound `_ProviderTextBoundaryNormalizer` also be changed for `?`/`!`, or should it remain a final guard that never forwards punctuation-only chunks?
4. What exact tests should be added to prevent regressions for:
   - question mark prosody preservation
   - no literal `dot`
   - decimal split preservation
   - missing-space prevention
   - no avoidable latency increase
5. What runtime QA must be run after patching before calling this fixed?

Return JSON with:

- `full_final_recommendations`
- `summary`
- `findings`
- `risks`
- `tests_to_add`
- `alternatives`
- `evidence`
