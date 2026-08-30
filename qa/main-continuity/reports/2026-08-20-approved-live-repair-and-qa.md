<!-- qa-evidence-exempt: Historical pre-v2 run report retained without retroactively inventing evidence; the 2026-08-21 v2 report owns current acceptance. -->

# Main Continuity Approved Live Repair And QA

**Date:** 2026-08-20
**Private source anchor:** `MC-SRC-001`
**Candidate:** active local dirty checkout; not a clean release artifact
**Overall:** `PARTIAL`, with the reported Telegram continuity failure repaired and proved live

## User-visible result

Viventium now keeps the immediate Telegram referent for both ordinary terse replies and replies to
a separately delivered scheduled Main message. The escaped scheduled-reply defect reproduced once
on the active candidate: durable provenance was correct, but the answer discussed an older
interactive topic. After the admission repair and supported restart, the same private Telegram path
explained the scheduled output itself.

The final schedule-level attribution is also clear. The unexpected original question was produced
from an enabled schedule's saved prompt by the configured Main Agent Builder route. It was not
cross-thread prompt leakage and it was not an isolated worker. The bad experience was the next turn:
Main denied authorship because it did not receive the scheduled Telegram referent. The intended
schedule remains enabled; no prompt was rewritten to make the test pass.

The repeated schedule-noise source was also contained: seven reviewed exact duplicates are paused,
not deleted. Five intended schedules remain active. Recall is running again after an in-place
PostgreSQL credential repair with a verified backup and unchanged collection/embedding counts.

## Root cause and repair

The Telegram adapter and Core correctly persisted a typed, verified `schedule_result` reply
descriptor. Core also kept the new user body as only the new question. The failure occurred at the
provider admission boundary:

1. the reusable Telegram conversation retained unrelated interactive ancestry;
2. Core appended the fresh reply capsule to mutable developer instructions;
3. the resumed native session consumed its delta from the bounded invocation-local channel;
4. that delta contained the terse question but not the scheduled referent;
5. the model therefore answered the stale interactive ancestry.

The repair moves `ReplyContextV1` into the shared bounded per-turn context. It is the first atomic
capsule in that channel and remains outside user-authored text and persistent session identity.
The capsule is capped at 12 KiB: oversized attachment text is omitted first with explicit byte and
item counts, while ownership IDs and the current quote are preserved whenever they fit. The Active
Work budget reserves those reply bytes before loading its roster. If the 16 KiB shared context is
still under pressure, lower-priority time, Active Work, and source-selection capsules are removed
before the reply referent. Session providers receive the exact admitted context in the per-turn
header; a direct fallback receives the same text in its developer-context carrier.

The three encoded context headers have a separate 512 KiB aggregate HTTP request-head limit. It
covers the declared 128 KiB bootstrap, 128 KiB developer-tail, and 32 KiB turn-context bounds plus
a 64 KiB envelope reserve. Uvicorn is pinned to h11 with that buffer; a lower override makes
GlassHive fail closed while the optional-service launcher reports degraded startup. GlassHive
returns HTTP 431 above the aggregate limit and counts the full request target, including query
bytes. The application guard is required because a complete oversized h11 event can be parsed
without exhausting the incomplete-event buffer.

## Approved live changes

| Change | Result | Recovery |
| --- | --- | --- |
| Pause seven exact duplicate schedules | `PASS` — seven inactive, five intended active, no deletion | Re-enable the retained task records |
| Repair Recall/RAG database authentication | `PASS` — API health `UP`; one collection and 1,555 embeddings retained | Verified PostgreSQL dump captured before repair |
| Activate current candidate | `PASS` — supported developer-runtime validation and restart completed; app ports and services responded | Previous source state remains in git/worktree history; local backup evidence retained privately |
| Run private Telegram and browser QA | `PASS` for cases listed below | Synthetic records and screenshots are private; the focus incident below is recorded separately |

No live-agent sync, schedule deletion, database reset, or public push occurred.

During the final Telegram restart smoke, the desktop app reported the Viventium window while its
composer was actually focused on a real-contact chat. One synthetic QA marker was accidentally sent
there. It contained no personal content. Codex stopped, did not delete it or send a correction
without authorization, navigated back through search, visually confirmed the `Viventium` header,
and only then ran the bot-only pass. This is an operator QA incident, not Viventium product output.

## Evidence

| Case | Result | Actual evidence |
| --- | --- | --- |
| Terse Telegram follow-up | `PASS-LIVE` | The assistant asked a synthetic question; `yeah` continued that exact topic in the same conversation |
| Scheduled Main delivery | `PASS-LIVE` | A one-time `viventium_agent/new` task became inactive after `success/sent/delivered` and delivered one exact bubble |
| Reply to scheduled output | `PASS-LIVE` | Visible reply explained the scheduled instruction; Mongo stored verified `assistant_self` / `schedule_result` provenance and separate user text |
| Native admission before repair | `FAIL-REPRODUCED` | Delta instruction contained the terse question but not `ReplyContextV1` or the scheduled quote |
| Native admission after repair | `PASS` | The final restarted candidate produced a 17.8 KiB bounded instruction containing the capsule, exact scheduled quote, and user question; the visible answer correctly prioritized that referent over older ancestry |
| Session-to-direct fallback carrier | `PASS-AUTOMATED` | Real `chatCompletion` wiring preserved the immutable snapshot digest, exact reply capsule, and tool ceiling while changing only the carrier; a forced live fallback remains open |
| Browser continuity | `PASS-LIVE` | Three real UI turns retained a marker, used a native file/shell tool, exposed Harness activity, survived refresh, kept one visible reply per turn, and logged zero console errors |
| Recall recovery | `PASS-HEALTH` | RAG API and vector database are healthy after restart; grounded real-surface older-fact retrieval remains open |
| Restart | `PASS` | Config compilation, dirty-candidate validation, helper refresh, scoped stop/start, frontend, API, provider, Telegram, and Recall completed |
| Context-header transport | `PASS-LIVE` | The restarted process pinned h11 at 512 KiB; real 20 KiB and 300 KiB request heads returned HTTP 200, while a 550 KiB header and a 550 KiB query each returned HTTP 431 |
| Post-transport Telegram smoke | `PASS-LIVE` | Telegram Desktop sent a synthetic exact-reply request and visibly received exactly `TRANSPORT_OK`; Mongo contained one user message and one finished, non-error assistant result |
| Post-review exact Telegram smoke | `PASS-LIVE` | On the final query-aware guard candidate, Telegram Desktop twice visibly confirmed the Viventium recipient, then received exactly `EXACT_OK`; Mongo contained one finished user/assistant pair with no error |
| Post-review exact browser continuity | `PASS-LIVE` | On the same final candidate, the non-admin browser flow retained its marker, used a native tool, showed Harness details, survived refresh, kept the Agent selected, and logged zero console errors |
| Managed isolated schedule policy | `PASS-LIVE` | Startup reconciliation changed an existing memory-off managed schedule from stale host metadata to Docker with no host workspace root; its real run used the requested and effective Docker lane, completed, imported a validated artifact, and survived Workbench reload |
| Main manual-run receipt | `PARTIAL` | Workbench atomically created one leased `manual/workbench_manual` receipt and used the same ID for occurrence and provider idempotency. A real scheduled claim was rejected while the real configured Main run held its lease; that run closed `silent`, cleared the lease, and persisted after reload. All three synchronous Run Now paths now heartbeat the identity-bound lease. Queued/`waiting_external` retention, long-run renewal, forced terminal clearing, stale active-state recovery, defer-past-misfire, and runtime-metadata-safe structural identity pass automation. The complete long-overlap defer path has not been forced on the live user schedule. |
| Exact active Main schedule | `PASS-LIVE` | After the final supported restart, the enabled Workbench-defined Main schedule ran with its real registered prompt and configuration. A competing scheduled claim was rejected while the bound manual receipt held a live lease. The receipt closed once as `completed/silent`, cleared the lease, both channels were `suppressed/nta`, the result persisted after browser reload, and Telegram visibly received no failure or noise bubble. |
| Active scheduled output ownership | `PASS-LIVE` | An existing active Main schedule delivered through the configured Main route; a natural Telegram follow-up made Main identify it as its own automated prompt and explain the timing and intent instead of denying authorship |
| Post-restart automatic Main continuity | `PASS-LIVE` | A real one-time `viventium_agent` occurrence ran through the scheduler after restart, delivered once to LibreChat and Telegram, stored one sent Telegram receipt, cleared its lease, deactivated itself, and produced no retry. Telegram visibly showed the marker; the next natural follow-up got a direct scheduled-QA ownership answer. Mongo stored one finished non-error assistant reply, trusted scheduler context, and `memoryEligible:false`. |
| One-time failure wording | `PASS-LIVE` | A controlled private Telegram fixture displayed the exact timestamp at which the same occurrence would retry |
| Recurring failure wording | `PASS-LIVE` | A controlled private Telegram fixture stated that the failed occurrence ended and only the next scheduled occurrence remained enabled |

Fresh post-repair automated evidence:

- owning LibreChat API regressions: 247 passed;
- complete GlassHive conversation-provider suite: 150 passed;
- launcher and stable-runtime release regressions: 58 passed;
- continuity registry release tests: 2 passed;
- source formatting and diff checks: passed;
- post-restart non-admin browser script: passed all 12 assertions;
- continuity registry generation/check: passed.
- complete Prompt Workbench release suite after the policy and receipt repairs: 188 passed;
- complete scheduler storage and engine suites for the manual/scheduled lease and stale-state
  recovery blast radius: 101 passed plus 10 subtests;
- scheduler occurrence-idempotency, multi-chunk acknowledgement, no-resend, and ambiguous-send
  regressions: 5 passed.

A wider adjacent API batch passed the three owning continuity suites but failed three existing
`surfacePrompts.spec.js` voice-prompt expectations. The continuity repair did not change the voice
prompt source or renderer. Those failures are recorded as separate dirty-worktree debt and are not
misreported as a continuity pass.

## Remaining acceptance gaps

This candidate is usable for the reproduced paths, but it is not release-ready. The remaining work
is the same bounded continuity program, not another Telegram-only patch:

- persist a validated semantic long-horizon summary and canonical accepted-turn CAS cursor;
- implement one overflow compact-and-retry with the same authority/capability ceiling;
- prove exact Phase-B and a forced real primary/fallback run; automated carrier parity now passes;
- add compact `RecurrenceStateV1` for long-running schedules;
- run grounded real-surface recall, unknown/foreign/group Telegram reply, and repeated same-root
  failure-coalescing cases;
- repair the separately reported Memory Hardening `execution_mismatch` through its owning path;
- run forced crash/recovery and a 100+ turn real-surface soak;
- reconcile protected live-agent drift only after a separate A/B/C review;
- split, commit, pin, build, clean-install, and verify the nested components before any release claim.

The live status after these repairs shows LibreChat, the scheduler, GlassHive, Prompt Workbench,
Telegram, and Conversation Recall running. Overall status still needs attention only because the
separate Memory Hardening path reports `execution_mismatch`; this is not treated as proof that the
continuity program or the release chain is complete.

Private screenshots, full local identifiers, backups, and prompt history stay in the separate
private evidence repository.
