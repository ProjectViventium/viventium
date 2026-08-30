# Call Modes And Concurrency QA - 2026-08-21

## Summary

- Result: `PASS-LIVE` for the installed local Call/mode/concurrency slice.
- Real Chrome and in-app Browser calls proved one-click join, useful visible transcript, terminal
  task state, delivered audio, Call/Wing/Listen-Only boundaries, same-room switching, simultaneous
  calls, durable ended-state rendering, and refresh persistence.
- The admitted-call, durable-state, terminal-auth, stale-notice, and terminal-mode defects found by
  real browser/log QA received structural fixes and post-restart proof.
- Full endurance, every provider fault, multi-speaker banks, clean install, and public release parity
  remain `PARTIAL`.

## Scope Run

| Case | Result | What ran |
| --- | --- | --- |
| `MPV-025` / `MPV-026` | `PARTIAL` | Happy-path one-click, transcript, task, and audio passed live; full permission/failure and latency distributions remain |
| `MPV-030` | `PARTIAL` | Real Call/Wing/Listen-Only behavior passed; 100-switch and multi-speaker authority matrix remain |
| `MPV-050` | `PASS-LIVE` | Same-room mode switching with addressed/passive Wing and strict Listen-Only silence |
| `MPV-051` | `PASS-LIVE` | Simultaneous Chrome and in-app Browser calls held beyond the escaped timeout window |
| `MPV-052` | `PASS-LIVE` | Durable ended state survived refresh; the exact worker read terminal state and stopped without false warnings |
| `MPV-053` | `PASS-LIVE` | Coherent browser LiveKit dependency update, build, and real runtime matrix |
| Release artifact | `PARTIAL` | Dirty installed checkout passed; clean clone/install, component pins, rollback, and endurance remain unrun |

## Traceability

`LibreChat Call -> signed call session -> modern playground -> LiveKit room -> admitted voice worker
-> mode-aware voice policy -> visible transcript/task/audio -> durable call state -> refresh`

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`.
- Cases: `MPV-025`, `MPV-026`, `MPV-030`, and `MPV-050` through `MPV-053`.
- Expected result: one action starts a usable call; modes change behavior without changing rooms;
  two calls remain independent; terminal state is durable.
- Actual result: both browser surfaces, gateway logs, call/task state, audio telemetry, and focused
  tests agreed.

## Full-View Evidence Checklist

| Evidence surface | Result |
| --- | --- |
| Real user surfaces | Chrome and in-app Browser |
| Visible outcome | Correct mode/status labels, one answer, terminal task, no duplicate output |
| Audible outcome | Real RTC audio delivery and TTS activity observed on the substantive Call turn |
| Mode policy | Addressed Wing answered; passive Wing used `{NTA}`; Listen-Only produced no answer/task/TTS |
| Concurrency | Two distinct rooms were live together; second ready in about 5.5 seconds |
| Persistence | Ended mode/status survived refresh; synthetic local records were removed after proof |
| Logs | Admission, prewarm, connection, mode, task, terminal worker read, and end paths correlated |
| Automated checks | Playground, voice gateway, and release-contract suites passed |
| Build/artifact | Modern playground production build passed and active local source was restarted |
| Release boundary | Clean install, pin parity, rollback, and endurance are not claimed |

## User-Grade Evidence

- Surface exercised: authenticated Chrome and in-app Browser against the installed local runtime.
- Real user path: start Call from LibreChat, use the real playground, open transcript, send a
  synthetic turn, switch modes, start a second call, keep both live, then end and refresh.
- Visible outcome: one coherent answer, authoritative task state, correct mode labels, independent
  rooms, and a durable ended screen.
- Expanded/detail state: transcript and task activity were opened; browser console and gateway logs
  were inspected.
- Persistence/reload result: terminal mode/status survived refresh; no stale active control returned.
- Local/external prerequisite state: LibreChat, playground, LiveKit, voice gateway, MongoDB, and the
  configured model/TTS routes were active.
- Evidence retrieval classification, if applicable: call state and logs were available; no empty
  success or hidden provider failure was substituted.
- Fallback path, if applicable: the accepted turns did not require model or TTS fallback.
- Backend/log/DB confirmation: distinct call identities and task/session state matched the visible
  browsers; the escaped serialized prewarm wait disappeared after the fix.
- Final model/runtime wording check: visible status described authoritative mode/state; it did not
  claim a call was active after durable end.
- Substitution check: tests, logs, and DB rows support but do not replace the two real browser runs
  and delivered audio.

## Automated Evidence

- Modern playground full Vitest: `147/147` passed.
- Voice gateway full suite: `502` tests plus `84` subtests passed.
- LibreChat call-session and voice-route suites: `148/148` passed.
- Release voice contracts: the affected focused set passed after the dependency and parity fixes.
- Modern playground production build passed with the final package lock.
- Browser dependencies: `@livekit/components-react` `2.9.21`; `livekit-client` `2.18.2`.

## Findings

- Root cause 1: replacement idle-worker prewarm correctly deferred during active calls, but the same
  wait was reused after LiveKit had already admitted a real call. That serialized the second call
  behind the first. The admitted path now initializes immediately; idle replacement still defers.
- Root cause 2: local LiveKit state could outlive the authoritative call session. A shared status hook
  now polls the owner-scoped session and drives degraded, failed, and ended presentation.
- Root cause 3: strict ended-session auth also rejected the exact bound worker's final state read.
  Only that worker may now read the terminal state; the read cannot renew or reclaim the call.
- Root cause 4: a successful End cleared the browser capability, and stale settings failures could
  cover the durable terminal screen. The bounded capability now remains for terminal refresh, and
  confirmed `ended` state suppresses stale launch/settings notices.
- Root cause 5: the worker's terminal callback returned no mode, which a shared loop could mislabel
  as unavailable or as `call -> none`. A structural outcome classifier now separates terminal,
  unavailable, and ordinary mode updates.
- Root cause 6: the older browser LiveKit client set hit a native buffer compatibility failure.
  Browser packages were upgraded together and accepted only after build plus real calls.
- Hygiene: the final fresh in-app Browser smoke used a separate synthetic QA account. One synthetic
  conversation, four messages, one call session, two speaker rows, and two task rows were backed up
  privately and removed; Meilisearch, recall, and saved-memory postconditions passed. Personal-account
  history was not changed by that smoke. The final terminal regression added two synthetic
  conversations, twelve messages, eight task rows, eight speaker rows, and two sessions; all were
  backed up and removed through owner services, with zero target search rows and unchanged saved
  memory.
- Remaining gaps: endurance, full reconnect/fault matrices, real multi-speaker banks, cancellation
  races, clean install, parent pins, and rollback remain open in the owning cases.

## Public-Safety Review

- [x] Synthetic QA account and public-safe prompts.
- [x] No transcript text, audio, screenshots, local paths, user IDs, session IDs, credentials, or
  private provider identifiers in this report.
- [x] Raw browser, audio, log, DB, and cleanup evidence stayed outside the public repository.
- [x] Results are scoped to what was actually run; remaining release gaps are explicit.
