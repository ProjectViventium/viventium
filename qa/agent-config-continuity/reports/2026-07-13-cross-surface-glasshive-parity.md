# Cross-Surface GlassHive Parity - 2026-07-13

## Summary

PASS for the reported GlassHive capability drift across Telegram, LibreChat web, and live voice.
The durable local runtime was activated, restarted, and verified with the same checkout as the
selected runtime, helper checkout, and live stack owner. All three real user surfaces were then
exercised after the final code changes.

## Root Causes Fixed

1. A Telegram-only keyword/length guard removed every tool and MCP instruction from terse turns.
2. Blanket GlassHive deferral left no dependable execution gateway when the model did not discover
   a lower-level schema.
3. An optional connected-account participant could fail initialization while its graph edge
   remained, breaking the healthy main graph.
4. Request-scoped schema binding fed its own dynamic tools back into the merge and duplicated every
   provider function; strict providers rejected the voice request.
5. The speech sanitizer and the linked-chat persistence sanitizer disagreed on email replacement,
   allowing `Email email available` into saved voice text.
6. Direct LibreChat startup ignored the full-stack launcher's selected Python interpreter, so a host
   Python upgrade could break prompt compilation during restart.

## Scope Run

| Surface | Result | Evidence |
| --- | --- | --- |
| Telegram | PASS | A native long request completed a local browser/file task and delivered its callback. After durable restart, the exact terse `Glass hive??` turn rendered a coherent text reply and a nonzero native audio bubble. Logs showed 46 canonical definitions, GlassHive MCP instructions, and 17 unique provider-bound tools; Mongo stored a finished, non-error reply. |
| LibreChat web | PASS | A real browser chat launched GlassHive and displayed its truthful dependency result, which survived refresh. The final durable-runtime marker turn rendered the exact requested reply, persisted in Mongo without error, and remained visible after a page reload. |
| Live voice | PASS | A real Modern Playground call completed transcript, semantic LLM, local TTS, linked persistence, and artifact checks. Another call invoked GlassHive launch/wait, completed a worker run, and created a synthetic public-safe proof file. The final durable-runtime call used scoped `tool_search`, grew the provider binding from 17 to 22 tools, invoked deferred `workspace_artifacts` in the same turn, received HTTP 200 tool evidence, rendered and persisted the result, and delivered nonzero audio. |

The first voice-to-worker acceptance exposed a QA-only false positive: the harness joined two
separate assistant messages before checking adjacent duplicate words, so `worker.` followed by
`Worker` looked like one duplicated phrase. The harness now evaluates each message independently;
the regression passes and the repeated real journey passes. The final deferred-artifact replay also
exposed a second QA-only heuristic that required canned response vocabulary. The harness now uses
structural provider-completion, visible-transcript, and persisted-output evidence; its regression
and the repeated real call both pass.

## Automated Evidence

- Focused LibreChat fallback, graph, MCP, schema-binding, persistence, and prompt regressions: PASS.
- Voice gateway sanitizer and LibreChat streaming regressions: PASS.
- Telegram bridge suite: PASS.
- Parent release contracts for prompt registry, no runtime NLU, and launcher interpreter parity:
  PASS.
- Voice artifact text regression, including cross-message boundary isolation and arbitrary custom
  prompt responses: PASS.

## Performance Observations

- Durable-runtime terse Telegram turn: 8.261 seconds to text completion; the native audio delivery
  path completed in 3.838 seconds.
- Durable-runtime LibreChat exact-answer turn: 6.972 seconds measured in the browser; the server
  completion trace was 3.884 seconds.
- Final deferred-discovery voice turn: 8.187-second stream with 4.478 seconds of delivered audio
  and a 2.996-second local-TTS time to first byte.

These are single-run user-path observations, not p50 or p95 measurements.

## Remaining External State

Unrelated connected-account integrations were outside this synthetic GlassHive case and were not
used. Their status was not collected for this public report.

No private logs, credentials, local usernames, hostnames, absolute home paths, or customer data are
included in this report.

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: cross-surface GlassHive capability continuity.
- Requirement: agent-config continuity, MCP discovery, graph resilience, and voice artifact parity.
- Use case: ask for GlassHive work from Telegram, LibreChat web, and live voice.
- QA case: the applicable continuity, GlassHive, Telegram, and modern-playground cases.
- Expected result: each surface can discover and complete the capability without duplicated tools or a broken graph.
- Actual evidence: the three real user journeys, persisted results, runtime logs, and focused regressions above passed.
- Remaining gap or fix: unrelated connected-account providers were outside this capability path and were not evaluated.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Requirement and use case | Agent continuity and GlassHive cases cover all three user surfaces. |
| Code owning path | Tool binding, graph initialization, deferred discovery, launcher interpreter, and artifact sanitization were inspected. |
| Docs and nested docs/repos | Root continuity/GlassHive docs and nested LibreChat/voice contracts agree. |
| Scripts or harnesses | Telegram, browser, modern-playground, and focused regression harnesses ran. |
| Local/external prerequisite state | The active durable runtime and required local GlassHive services were healthy. |
| Logs | Sanitized tool counts, completion timings, and terminal states matched the visible results. |
| DB/state/persistence | Mongo stored terminal non-error replies and browser results survived reload. |
| Generated/shipped artifact | The active generated runtime and selected checkout were aligned; clean-install proof is separate release work. |
| Real user path | Telegram, LibreChat browser, and Modern Playground voice were used directly. |
| Visual/UX comparison | Text, cards, artifacts, and delivered audio agreed with the backend state. |
| Not run / blocked | Unrelated connected-account providers were not evaluated or claimed. |

Supporting evidence cannot replace required user-path evidence; the Telegram, browser, and voice paths were run directly.

## User-Grade Evidence

- Surface exercised: Telegram, LibreChat browser, and Modern Playground voice.
- Real user path: sent terse and full requests, launched GlassHive, opened the result, and repeated after durable restart.
- Visible outcome: each surface returned a coherent terminal result; voice also delivered nonzero audio.
- Expanded/detail state: browser cards and workspace artifacts exposed the completed detail state.
- Persistence/reload result: web and linked-chat results remained visible after reload.
- Local/external prerequisite state: the active runtime and required GlassHive services were healthy.
- Backend/log/DB confirmation: unique provider-bound tools, terminal tool evidence, persisted replies, and audio artifacts agreed.
- Final model/runtime wording check: replies did not claim unavailable connected-account capabilities or expose internal routing.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting evidence, not substitutes for any required visible-UI, detail-state, persistence, or wording step.

## Findings

- Defects: six structural cross-surface defects are listed under Root Causes Fixed.
- Regressions: none remained in the repeated user journeys or focused suites.
- Flakes: two QA-only result heuristics were corrected and rerun.
- Environment issues: unrelated integrations were outside the synthetic case and were not inspected.
- Residual risks: the timing observations are single runs, not capacity percentiles.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timings, and conclusions only.
