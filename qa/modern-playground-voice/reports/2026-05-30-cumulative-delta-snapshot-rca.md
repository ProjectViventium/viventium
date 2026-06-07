<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-30 Cumulative Delta Snapshot RCA

## Scope

This report covers the escaped Modern Playground voice bug where a linked LibreChat conversation
showed malformed internal no-response text and adjacent duplicated assistant words after a voice
call.

Public-safe note: the user-reported raw call/session/conversation ids, account identifiers, private
transcript text, local absolute paths, provider request ids, and secrets are intentionally omitted.

## User-Visible Failure

- Modern Playground displayed a malformed no-response marker instead of silence.
- A later assistant line showed adjacent duplicate words caused by the same text being appended more
  than once.
- Reloading the linked LibreChat text chat showed the corrupted assistant rows, proving this was not
  just a browser transcript rendering issue.

## Root Cause

The voice stack assumed every `on_message_delta` text event was a pure incremental token delta.
Some LibreChat/agent stream events were actually growing cumulative snapshots of the assistant text.

That meant a sequence conceptually shaped like:

```text
I
I am
I am here
```

was treated as:

```text
II amI am here
```

The same failure mode malformed the internal no-response marker when snapshots grew from partial to
complete marker text. The malformed marker then escaped into the playground and persisted rows.

## Why It Was Missed

- Regression tests covered true incremental deltas, not cumulative snapshot deltas.
- Existing no-response tests covered split-marker input, but not growing partial snapshots that
  repeatedly re-sent already-seen text.
- The browser harness could mark a prompt as sent before the LiveKit agent participant was actually
  available, which weakened evidence that the real worker/chat route was exercised.
- The harness scanned broad page text and did not assert that the visible transcript, persisted
  assistant rows, and TTS/log artifacts were all free of internal no-response markers and adjacent
  duplicate words.

## Fixes Applied

- Voice gateway streaming now normalizes cumulative text snapshots to only the missing suffix before
  TTS, transcript streaming, no-response suppression, and collected response text.
- LibreChat voice persistence repair now uses the same missing-suffix behavior before appending
  missed text deltas to assistant rows.
- LibreChat voice aggregation also repairs the complementary write-path failure where the upstream
  aggregator already appended a cumulative snapshot as if it were incremental. In that exact
  before/after shape, the visible text parts are rewritten to the cumulative snapshot instead of
  allowing duplicated text to reach Mongo.
- The historical message read path now hides malformed historical voice no-response artifacts and
  normalizes obvious cumulative duplicate-word artifacts for user-visible reads. This is a read-side
  safety net only; it does not mutate existing Mongo rows.
- Voice messages now receive safe correlation metadata at persistence time so future QA can query
  normal saved user/assistant rows by call session without relying on private transcript text.
- The Modern Playground typed-input guard now blocks Enter-submit until the LiveKit agent participant
  is available.
- The TTS artifact browser QA harness now waits for the enabled send control, verifies the route was
  exercised, scans transcript text rather than the whole static page, checks for internal no-response
  markers and adjacent duplicate words, and requires persisted assistant evidence.

## Requirement / QA Trace

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md` (Live Response Streaming)
- Case: `qa/modern-playground-voice/cases.md` `MPV-018`
- User outcome: cumulative snapshots must speak/display/save the final answer once; `{NTA}` must
  remain exact and silent; linked LibreChat reload must not show malformed control text or adjacent
  duplicate-word artifacts.

## Automated Verification

```text
node -c qa/modern-playground-voice/scripts/tts_artifact_browser_qa.cjs
node -c viventium_v0_4/LibreChat/api/server/services/viventium/voiceMessageMetadata.js
node -c viventium_v0_4/LibreChat/api/server/services/viventium/historicalVoiceTextRepair.js
node -c viventium_v0_4/LibreChat/api/server/routes/messages.js
cd viventium_v0_4/LibreChat && npm run test:api -- --runTestsByPath api/server/services/viventium/__tests__/historicalVoiceTextRepair.spec.js api/server/controllers/agents/__tests__/requestPersistence.spec.js api/app/clients/specs/BaseClient.test.js api/server/services/viventium/__tests__/voiceDeltaAggregation.spec.js
cd viventium_v0_4/LibreChat && npm run test:api -- --runTestsByPath api/server/controllers/agents/client.test.js api/server/controllers/agents/speculativeParallelMainRun.spec.js api/server/services/viventium/__tests__/historicalVoiceTextRepair.spec.js api/server/services/viventium/__tests__/voiceDeltaAggregation.spec.js
cd viventium_v0_4/voice-gateway && .venv/bin/python -m pytest tests/test_librechat_llm.py -q
cd viventium_v0_4/agent-starter-react && pnpm exec tsc --noEmit
git diff --check && git -C viventium_v0_4/LibreChat diff --check && git -C viventium_v0_4/voice-gateway diff --check && git -C viventium_v0_4/agent-starter-react diff --check
```

Result: PASS for the focused automated checks above.

After the review-only Claude pass, an additional write-path regression was added for the exact case
where the raw aggregator appends cumulative snapshots and would otherwise persist duplicate text.
The focused rerun passed:

```text
cd viventium_v0_4/LibreChat && npm run test:api -- --runTestsByPath api/server/services/viventium/__tests__/voiceDeltaAggregation.spec.js
cd viventium_v0_4/LibreChat && npm run test:api -- --runTestsByPath api/server/services/viventium/__tests__/historicalVoiceTextRepair.spec.js api/server/controllers/agents/__tests__/requestPersistence.spec.js api/app/clients/specs/BaseClient.test.js api/server/services/viventium/__tests__/voiceDeltaAggregation.spec.js
cd viventium_v0_4/voice-gateway && .venv/bin/python -m pytest tests/test_librechat_llm.py -q
cd viventium_v0_4/agent-starter-react && pnpm exec tsc --noEmit
```

Result: PASS; 74 focused LibreChat tests, 58 voice-gateway tests, and the playground TypeScript
check passed.

## Runtime / User-Path QA

After activating the patched checkout into local prod and restarting the runtime:

- API, LibreChat web, and Modern Playground health endpoints responded.
- The user-reported linked conversation was checked through the normal messages read API and by
  reloading the conversation in a real Chrome browser.
- The linked conversation no longer rendered the malformed no-response marker.
- The two historically corrupted assistant rows displayed normalized text without adjacent duplicate
  words.
- The raw historical Mongo rows were not modified; this remains an explicit data-repair decision.

Modern Playground artifact harness run:

```text
VIVENTIUM_QA_ALLOW_LOCAL_JWT=1 VIVENTIUM_TTS_ARTIFACT_QA_PROMPT='<synthetic exact-answer prompt>' node qa/modern-playground-voice/scripts/tts_artifact_browser_qa.cjs
```

Evidence artifact:

```text
output/playwright/modern-playground-voice/tts-artifact-browser-qa-1780210504500.json
```

Observed:

- `callCreated=true`
- `pageOpened=true`
- `startClicked=true`
- `transcriptToggled=true`
- `promptSent=true`
- `agentSendReady=true`
- `transcriptMessageCount=2`
- `persistedAssistantCount=1`
- visible transcript artifacts: `internalNoResponseMarker=0`, `adjacentDuplicateWord=0`
- persisted assistant artifacts: `internalNoResponseMarker=0`, `adjacentDuplicateWord=0`
- TTS/provider log artifacts: `internalNoResponseMarker=0`, `adjacentDuplicateWord=0`
- synthetic cleanup removed the created messages, conversation, and call session

Verdict: PARTIAL PASS. The exact artifact did not reproduce after the fix and persisted fallback
assistant text was clean. A healthy primary-model cumulative-delta response was not live-proven
because the local model provider route failed before generating a normal assistant answer, then the
fallback provider was also unavailable. The gateway correctly fell back to a voice-safe service
message, and that fallback path was artifact-clean.

After the final runtime restart, the first harness attempt timed out waiting for an available agent
participant and did not reach the worker route. A second immediate rerun did reach the route, enabled
send, produced transcript/persisted assistant evidence, and remained artifact-clean. The transient
agent-availability miss is tracked as QA evidence but is not the duplicate-text RCA.

## Remaining Risks / Follow-Ups

- Existing raw Mongo rows from the escaped bug still contain historical corrupted text. The read path
  hides/normalizes them for user-visible chat, but recall/search contamination requires a separate
  backup plus data-repair migration decision.
- A healthy-provider `MPV-018` rerun is still required to mark this case full PASS: primary model
  must stream a normal answer through the patched cumulative-delta normalizer, then the playground,
  TTS/logs, linked chat reload, and persisted assistant row must all remain clean.
- The read-side historical repair is intentionally narrow. It should not be treated as a general
  duplicate-text corrector for ordinary assistant prose.

## Claude Review

Review-only Claude Opus 4.8 was attempted twice. The first pass could not inspect files because its
local tool-output channel returned empty results, so it correctly refused to fabricate findings. The
second pass used inline implementation snippets. Claude agreed the direction was sound, but flagged
one material gap: the original patch fixed missed-delta repair but did not prove the write-path
aggregator itself would de-duplicate cumulative snapshots if it had already appended them. That gap
was fixed and covered by the additional raw-aggregator duplicate regression above.
