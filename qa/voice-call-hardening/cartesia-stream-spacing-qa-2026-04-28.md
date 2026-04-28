# Cartesia Stream Spacing QA - 2026-04-28

## Scope

- Live voice calls using Cartesia Sonic-3 over WebSocket continuations.
- Word-boundary spacing across streamed LLM deltas.
- Opt-in debug evidence for the exact text sent to Cartesia TTS and the text shown in the UI.

## Root Cause

Cartesia WebSocket continuations concatenate `transcript` chunks verbatim. The voice gateway's
streaming Cartesia path normalized each LLM delta with the same helper used by one-shot synthesis;
that helper stripped leading and trailing whitespace from every chunk. A stream shaped like
`["Hey, doing good. What's", " up?"]` could therefore reach Cartesia as `What'sup?`.

The user reproduced the same full sentence in Cartesia Playground without the pronunciation issue,
which is consistent with a local streaming-chunk boundary bug rather than a Sonic-3 voice/model
problem.

## Fix Summary

- Cartesia one-shot `/tts/bytes` normalization still strips surrounding whitespace.
- Cartesia live WebSocket streaming now preserves leading/trailing chunk whitespace after
  nonverbal-token and SSML normalization.
- Whitespace-only deltas are preserved as a single separator so `["Hello", " ", "world"]` remains
  `Hello world`.
- The streaming path now uses a shared helper that builds the exact Cartesia `transcript` and
  `generation_config.emotion` values, making the WebSocket payload shape testable.
- With `VIVENTIUM_VOICE_DEBUG_TTS=1`, voice logs use JSON-escaped strings for:
  - raw LLM deltas
  - TTS deltas
  - display-sanitized deltas
  - Cartesia WebSocket chunk transcript
  - joined Cartesia continuation transcript

## Automated Checks

Run from `viventium_v0_4/voice-gateway`:

```bash
for f in tests/test_*.py; do ./.venv/bin/python "$f"; done
./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
./.venv/bin/python -m py_compile cartesia_tts.py librechat_llm.py
```

Result: all voice-gateway unittest files passed; unittest discovery reported `176` tests passing.

Added regression coverage:

- streamed chunks preserve a leading boundary space: `What's` + ` up?`
- streamed chunks preserve trailing spaces before the next chunk
- whitespace-only deltas remain as a single separator
- the WebSocket `transcript` payload values preserve boundary spaces
- one-shot synthesis keeps the prior strip behavior

## Second Opinion

ClaudeViv review confirmed the root cause and the minimal streaming-only fix. It flagged two
pre-push gaps: whitespace-only deltas and payload-level coverage. Both were addressed before this
QA note was finalized.

## Residual Notes

- A live Cartesia debug capture with `VIVENTIUM_VOICE_DEBUG_TTS=1` remains useful after restart to
  verify real-call audio against the now-logged `joined_transcript_json`. Do not store API keys,
  account identifiers, call-session IDs, or private transcript content in public QA artifacts.
