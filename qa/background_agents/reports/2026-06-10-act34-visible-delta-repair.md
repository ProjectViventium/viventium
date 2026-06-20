<!-- qa-evidence-exempt: legacy sanitized RCA/QA note retained for historical context; current acceptance must use cases plus a fresh v2 report. -->

# ACT-34 Visible Delta Repair RCA and QA

Date: 2026-06-10

## Scope

This report covers the escaped Telegram follow-up regression where the user first received a safe
Phase A answer, then later received a contradictory Phase B fallback as if the first answer had not
existed.

The promoted regression is `ACT-34`: visible Phase A text emitted to a user surface but missed by
canonical aggregation must be repaired before Phase B, and Phase B must not synthesize a
deterministic fallback over that already-visible answer.

## RCA

- The initial assistant answer reached the Telegram surface.
- The canonical assistant parent in the Agents runtime did not retain that visible text in
  `contentParts`.
- Phase B therefore extracted an empty recent response and selected the deterministic fallback path.
- The fallback was promoted onto the parent/follow-up path, producing a second response that was
  not aware of the already-delivered Phase A wording.

The root cause was a missing durability bridge between user-visible stream deltas and canonical
parent text before Phase B adjudication. The issue was not the safety policy itself: the first
answer was aligned. The failure was that Phase B trusted an empty canonical parent even though the
user had already seen a valid answer.

## Fix

Implemented a structural, surface-neutral repair:

- Visible message deltas now carry an internal `visibleToUser` flag into aggregation.
- If upstream aggregation does not advance after an emitted visible delta, runtime repairs the
  canonical parent text from the already-emitted delta.
- If Phase B sees repaired visible parent text on a non-deferred turn, it records a terminal
  `suppressed` decision instead of generating or promoting fallback text.
- Deferred/no-answer paths still work normally because the suppression requires repaired visible
  text and a non-deferred main response.

No prompt-text, provider-label, agent-name, or user-identity heuristic was added.

## Second Opinion

ClaudeViv reviewed the RCA/proposed fix in review-only mode before implementation. The review agreed
with the failure chain and specifically validated the durable Phase A visible-text repair plus
fail-closed Phase B suppression. No code changes were delegated to ClaudeViv.

## Automated Checks

| Check | Result | Evidence |
| --- | --- | --- |
| Changed JS syntax checks | PASS | `node --check` passed for changed runtime files |
| Targeted LibreChat Jest | PASS | 4 suites, 210 tests passed |
| Telegram bridge tests | PASS | `tests/test_librechat_bridge.py`: 103 passed |
| Telegram stream preview tests | PASS | `tests/test_bot_stream_preview.py`: 18 passed |
| Voice gateway suite | PASS | 341 tests, 48 subtests passed |
| Local runtime restart | PASS | API health OK, LibreChat web 200, Modern Playground 200 |

## User-Path QA

| Surface | Result | Evidence |
| --- | --- | --- |
| LibreChat web, owner account | PASS | Synthetic marker `ACT34-WEB-20260610190934`; real browser send; one assistant child for the marked turn; text length 683; structured cortex parts persisted; Phase B decision `result=suppressed`, `suppressionReason=visible_delta_aggregation_repaired`; no second follow-up child for the marked turn |
| Telegram Desktop, owner account | PASS | Synthetic marker `ACT34-TG-20260610191637`; visible Telegram text answer appeared once; automatic audio attachment did not add contradictory text; Mongo showed one assistant child for the marked turn, text length 664, structured cortex parts, and suppressed Phase B decision; later unrelated chat turns were excluded from this assertion |
| Modern Playground voice | PARTIAL | Real browser call sessions were created on the owner account route; Start chat, transcript toggle, typed prompt send, and TTS provider metrics ran; voice-gateway automated suite passed. The live post-prompt visible transcript did not produce a second assistant transcript inside the QA window, so the full MPV-014 prompt-response proof remains partial and is tracked as a voice-channel QA gap rather than counted as an ACT-34 pass |

Temporary screenshots were captured under a local temp directory and are intentionally not committed.

## Acceptance

`ACT-34` passes for the escaped web/Telegram failure class:

- The already-visible Phase A answer is preserved in canonical parent text.
- Structured background cortex parts remain on the parent message.
- Phase B records a durable silent terminal decision.
- No contradictory deterministic fallback is delivered after the first response.

The remaining voice gap is not evidence of an ACT-34 contradiction; it is a separate Modern
Playground typed-prompt transcript proof gap discovered during cross-channel QA.
