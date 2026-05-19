# 2026-05-18 Synthetic Audio LiveKit Continuation QA

## Summary

- Result: PASS for synthetic TTS/fake-microphone LiveKit QA of local Whisper Listen-Only transcript
  continuation.
- Runtime under test: local development runtime promoted/restarted from the current checkout.
- Voice route under test: Modern Playground -> LiveKit -> `librechat-voice-gateway` ->
  Whisper.cpp Local `large-v3-turbo` -> LibreChat Listen-Only persistence.
- Core acceptance: speech split by `0.7s` and `1.5s` pauses persisted as one continued transcript
  message inside the continuation window.
- Remaining gap: this harness proves backend persistence/log behavior. It did not prove a visible
  opened transcript panel in the playground UI, and it does not claim full-agent barge-in message
  editing for an assistant response stream.

## What Changed

- Added a reusable synthetic speech generator:
  `qa/modern-playground-voice/scripts/generate_synthetic_speech_fixtures.py`.
- Added a real LiveKit fake-microphone QA harness:
  `qa/modern-playground-voice/scripts/livekit_synthetic_audio_qa.js`.
- Hardened LiveKit dispatch compatibility so the default connection-details path creates explicit
  dispatch and does not embed token room config; token-room-config dispatch remains opt-in.
- Changed Listen-Only ingress continuation to key by call session, not the latest transcript parent.
- Added `messageId` and `saved` to the real `ViventiumVoiceIngressEvent` schema so Mongo preserves
  the fields needed to update an existing transcript row.

## Evidence Matrix

| Case | Result | Transcript rows | Sanitized session | Notes |
| --- | --- | ---: | --- | --- |
| short speech | PASS | 1 | `9666d48713a6` | Complete synthetic text persisted under ordered-token matching after the Mongo guard/output cleanup hardening. |
| long speech | PASS | 1 | `d9902e0b38ae` | No-loop long-tail rerun captured the full ending in one row. |
| `0.7s` pause | PASS | 1 | `5b33d3102943` | Two STT endpointed segments became one ordered message. |
| `1.5s` pause | PASS | 1 | `1487b3b08bec` | Resumed thought stayed one ordered message. |

## Important Failures Found Before Pass

- Token room config alone was not enough on the local LiveKit server. The browser connected, then
  reported that the agent did not join. LiveKit logs showed no worker assignment until explicit
  dispatch was force-created by the claim-winning request.
- The first backend continuation fix passed mocks but failed real Mongo because the ingress schema
  did not declare `messageId`/`saved`; strict Mongoose writes dropped those fields.
- Claude review found that the saved-message audit update was initially fire-and-forget; it now
  awaits the update before the response returns so rapid continuations can observe the `messageId`
  handshake deterministically.
- A permissive long-utterance token threshold let the harness close the call early. The harness now
  checks ordered tokens instead of only bag-of-words containment.
- Chromium fake-microphone audio can loop WAV files. The generator now adds a long silent tail by
  default so a failed match fails cleanly instead of matching repeated audio.
- Python 3.14 removed `audioop`; the generator now falls back to `ffmpeg` for WAV normalization.
- Parallel fake-microphone calls are noisy for this single-worker local setup; final acceptance runs
  were sequential.

## Timing Evidence

Recent successful synthetic runs showed local Whisper final transcription delays in this range:

| Case | Final STT segments observed |
| --- | --- |
| `0.7s` pause | `2.96s`, then `1.98s` |
| `1.5s` pause | `3.14s`, then `2.20s` |
| short speech | `3.77s` |
| long speech | `1.61s` |

These timings include the local VAD endpoint, final-only Whisper.cpp inference, and LiveKit/route
handoff. They are not UI render delays.

## Commands Run

```bash
python3 qa/modern-playground-voice/scripts/generate_synthetic_speech_fixtures.py
node --check qa/modern-playground-voice/scripts/livekit_synthetic_audio_qa.js
npm run test:api -- server/routes/viventium/__tests__/voice.spec.js --runInBand
uvx pytest tests/release/test_voice_playground_dispatch_contract.py -q
VIVENTIUM_AGENT_STARTER_REACT_DIR=tmp/voice-upstream-refresh/agent-starter-react uvx pytest tests/release/test_voice_playground_dispatch_contract.py -q
cd viventium_v0_4/voice-gateway && .venv/bin/python -m pytest tests -q
uvx pytest tests/release/test_project_boundary_contamination.py -q
```

Additional checks:

- Current and upstream-refresh `agent-starter-react` TypeScript checks passed.
- The upstream-refresh dispatch contract command is reproducible with a relative
  `VIVENTIUM_AGENT_STARTER_REACT_DIR` path after the test now resolves the env path to an absolute
  directory before invoking Node.
- The synthetic harness rejects non-local `MONGO_URI` values unless explicitly overridden, and a
  guard smoke test failed closed before any DB connection.
- Local runtime promotion/restart completed with dirty-local-testing allowance and health checks for
  API, frontend, playground, and voice worker.
- Voice worker registered after restart and accepted explicit LiveKit dispatch jobs.
- A review-only Claude pass was completed after implementation; the must-fix feedback above was
  applied and the remaining findings are tracked as follow-up risk, not handoff blockers.

## Public-Safety Review

- [x] Uses synthetic non-personal transcript text only.
- [x] Raw call IDs, message IDs, user IDs, and local machine paths are excluded from this report.
- [x] Result JSON and screenshots remain under `output/` and are not public evidence artifacts.
- [x] Synthetic DB records created by the harness were cleaned after each accepted run.
