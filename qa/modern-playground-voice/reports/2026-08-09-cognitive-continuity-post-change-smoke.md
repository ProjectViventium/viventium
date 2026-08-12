# Cognitive Continuity Post-Change Voice Smoke - 2026-08-09

## Summary

- Result: PASS-DELIVERY; the real Modern Playground browser path produced and persisted one
  complete uncancelled TTS response. Human semantic listening was not scored.
- Scope: post-change smoke for cross-surface cognitive-continuity work; this was not a full voice
  provider, microphone, interruption, or fallback matrix.
- Environment: active local-prod Viventium runtime with synthetic non-personal content.
- Initial harness result: BLOCKED before UI because the bundled Chromium executable was absent.
  The reusable harness now selects the installed Chrome channel and the exact failed call-session
  state was cleaned before rerun.

## Scope Run

| Case | Result | Evidence | Remaining gap |
| --- | --- | --- | --- |
| `MPV-014` | PASS-DELIVERY | Real Chrome call, visible transcript/prompt, completed TTS metric, persisted assistant result, zero console errors | No human semantic-listening score |
| First failed harness attempt | BLOCKED/CLEANED | Browser launcher stopped before UI; two messages, one conversation, one ingress row, and one call-session row were removed exactly | None |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Supporting evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `MPV-UC-014` | Start a call, send a synthetic prompt, and receive a voice answer after the continuity changes. | Modern Playground in installed Chrome | PASS-DELIVERY | The call started and the transcript showed the prompt and completed assistant response. | One completed uncancelled TTS metric covering 78 characters; one persisted assistant result; zero console errors or unexpected artifacts; exact cleanup completed. | Audible bytes were delivered through the browser path, but a human did not score semantic audio quality. |

## Traceability

`cross-surface continuity -> voice parity requirement -> MPV-UC-014 -> MPV-014 -> delivered and persisted response -> no human listening score`

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md` and the repository verification
  contract require a real post-change user path rather than instrumentation-only evidence.
- Expected result: the active Modern Playground runtime starts a call, delivers TTS, persists the
  assistant result, exposes no browser error, and permits exact synthetic-state cleanup.
- Actual result: the expected browser, TTS, persistence, and cleanup signals agreed.
- Remaining gap: this focused smoke does not replace the broader audible provider matrix or a
  human semantic-listening assessment.

## Full-View Evidence Checklist

| Evidence surface | Result |
| --- | --- |
| Requirement and QA case | `MPV-UC-014` / `MPV-014` |
| Owning harness | `qa/modern-playground-voice/scripts/tts_artifact_browser_qa.cjs` |
| Active runtime | Local-prod Modern Playground and voice services used by the browser call |
| Real user path | Installed Chrome opened the call, started it, and submitted a synthetic prompt |
| Visible state | Call/transcript/prompt/assistant completion were visible |
| Logs/metrics | One completed, uncancelled TTS metric for 78 characters |
| DB/persistence | One assistant result persisted for the call |
| Browser health | Zero console errors and zero unexpected artifacts |
| Cleanup | Exact synthetic call/message/conversation/ingress state removed |
| Not run | Human semantic listening, microphone/STT, interruption, multi-provider and fallback matrix |

## User-Grade Evidence

- Surface exercised: Modern Playground voice in the installed Chrome browser against local-prod.
- Real user path: Open the call surface, start the call, submit a synthetic prompt, inspect the
  visible transcript and completed answer, then close and clean the synthetic run.
- Visible outcome: The browser showed the started call, prompt, transcript, and completed assistant
  response with zero console errors or unexpected artifacts.
- Expanded/detail state: The call transcript and completion state were inspected; the focused smoke
  did not exercise the microphone, interruption controls, or provider picker matrix.
- Persistence/reload result: One assistant result persisted and agreed with the delivered turn;
  this focused call smoke did not require a linked-chat reload.
- Backend/log/DB confirmation: One complete uncancelled TTS metric covered 78 characters, the
  assistant persistence count was one, and exact synthetic-state cleanup removed the call rows.
- Final model/runtime wording check: The visible completed response matched the persisted assistant
  outcome; no unavailable-capability or delivery claim contradicted runtime evidence.
- Substitution check: TTS metrics, DB state, and automated assertions supported the real Chrome call;
  they did not replace it. Human semantic listening remains explicitly unscored.

The first launcher failure was classified as a missing local browser prerequisite rather than a
product pass. Selecting the installed Chrome channel repaired the harness, and the clean rerun
supplied the acceptance evidence.

## Automated Evidence

```bash
node qa/modern-playground-voice/scripts/tts_artifact_browser_qa.cjs
```

Observed on the successful run: one TTS completion, zero cancellations, 78 delivered characters,
one persisted assistant result, zero console errors, zero unexpected artifacts, and exact cleanup.

## Findings

- Product path: no regression found in this focused voice-delivery smoke.
- QA harness: hard dependence on downloaded Playwright Chromium was an environment blind spot;
  selecting the installed Chrome channel makes the real-browser acceptance path usable on this
  supported local setup.
- Residual risk: delivery telemetry proves browser audio generation/delivery but not human-rated
  pronunciation, naturalness, or semantic listening quality.

## Public-Safety Review

- [x] Synthetic non-personal content only.
- [x] No credentials, tokens, cookies, private prompts, chats, or attachments.
- [x] No raw conversation, message, call, ingress, or provider identifiers.
- [x] No local username, hostname, private path, or machine-specific state dump.
- [x] Evidence is limited to public-safe counts, classifications, and outcomes.
