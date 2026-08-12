# Three-Gate Memory Continuity Repair - 2026-07-15

## Summary

PASS for the repaired persistence-identity, saved-memory, scheduled-hardening, and recall paths on
the active local runtime. The run used synthetic content and restored the isolated fixture exactly;
clean-machine publication remains a separate release gate.

## Scope Run

Investigate one recent-event miss across saved memory, nightly routines, and conversation recall;
repair the affected local primary-profile state; add reusable regressions; and prove the result through an isolated QA
account on native Telegram transport, Chrome, and Modern Playground voice.

Private conversations, account identifiers, logs, database exports, screenshots, and rollback
archives remain outside the public repository. This report uses only public-safe counts and synthetic
QA content.

## Research Alignment

The repair keeps the existing three layers instead of adding another memory subsystem:

- [LongMemEval](https://openreview.net/forum?id=pZiyCaVuti) evaluates information extraction,
  multi-session reasoning, temporal reasoning, knowledge updates, and abstention as distinct
  long-term-memory capabilities.
- [BEAM](https://openreview.net/forum?id=y59hf5lrMn) treats episodic memory, working memory, and a
  scratchpad as complementary rather than interchangeable.
- [Mem0](https://arxiv.org/abs/2504.19413) emphasizes dynamic extraction, consolidation, and
  retrieval; [Zep/Graphiti](https://arxiv.org/abs/2501.13956) emphasizes temporal provenance and
  changing relationships.
- [Letta's context hierarchy](https://docs.letta.com/guides/core-concepts/memory/context-hierarchy)
  keeps high-value facts in always-visible context while larger episodic history remains externally
  retrievable.

Viventium's saved memory, scheduled consolidation, and conversation recall already match that
shape. The incident required persistence identity, provenance, clipping, and consolidation fixes,
not a fourth competing store.

## Findings

The event was written correctly on one local Mongo persistence branch. A restored Mongo process was
already listening on the canonical port, and the native launcher accepted port occupancy as
readiness without verifying the server's data directory. When that process stopped, local prod
started from the configured canonical directory, which contained an older history branch.

The three apparent failures therefore had different explanations:

1. The live saved-memory writer had stored the event on the branch that later disappeared from the
   active runtime. The scheduled hardener had run successfully at 03:00 local time, before the event
   was told to Viventium.
2. The nightly insight routine was healthy but intentionally used `memoryWriteMode=off`; its private
   risk-radar output is not saved-memory consolidation.
3. Conversation recall invoked `file_search`, but its active corpus had been rebuilt from the older
   branch and honestly lacked the event.

During recovery, one additional defect was reproduced: generic deterministic maintenance ran after
a reviewed hardener apply and re-compacted a freshly written `context` key, discarding follow-up
detail. The same unprotected boundary remained in Prompt Workbench governed proposal apply. Long
adjacent assistant context could also consume the recall result budget, and a primary user turn
larger than that budget could lose its decisive tail.

## Surgical Fixes

- Native Mongo startup now queries `getCmdLineOpts` and fails closed unless the running listener's
  canonical `storage.dbPath` matches the configured data directory.
- Conversation recall keeps larger bounded user turns at the source, preserves the matched primary
  turn when adjacent context exceeds the result budget, keeps both the head and tail when the
  primary turn itself exceeds that budget, and uses structured author provenance as a small
  reranking tie-breaker.
- Nightly hardening and Prompt Workbench governed apply both protect conversation-owned `working`
  and every key written by the reviewed proposal from same-pass deterministic maintenance.
- The missing primary-profile history was unioned into the canonical database without replacing newer rows;
  recall was rebuilt, and a reviewed high-effort hardening proposal restored the saved-memory event.

## Evidence

| Gate | Actual run | Result |
| --- | --- | --- |
| Persistence | Two archived branches were checksummed; 91 missing messages and 10 conversations were inserted only when absent; zero restored rows remained unmatched. | PASS |
| Schedule | LaunchAgent installed and loaded with one `03:00` calendar trigger; timezone resolved from the current system; latest scheduled run fired at 03:00:02 local and completed successfully on the configured model/effort. | PASS |
| Saved-memory formation | A natural synthetic project event advanced QA memory revisions; a fresh Chrome chat with recall disabled recovered the outcome and two follow-ups with no retrieval source. | PASS |
| Nightly hardening | A 585-message, 44-conversation full-lookback proposal completed in one high-effort model attempt with no omissions or rejected writes. Apply changed three reviewed keys with zero conflicts and zero post-apply maintenance rewrites. | PASS |
| Conversation recall | The rebuilt affected-profile corpus contained 350 chunks. A recall-only Chrome turn returned the original synthetic user account and both follow-ups with persisted `file_search` provenance. | PASS |
| Native Telegram | Signed local Telegram ingress produced persisted saved-memory-only and recall-only conversations on the isolated QA user; responses contained the synthetic outcome and both follow-ups with the expected source count. | PASS |
| Modern Playground | Real Chrome/LiveKit calls delivered audible local TTS. Saved-memory-only and recall-only transcript turns each recovered the complete synthetic event; recall-only persisted retrieval sources. | PASS |
| Prompt Workbench | The `memory_recall` family completed 3/3 cases; semantic judging passed 3/3 at score 1.0, including the recent-relatives voice case and model-owned recall-tool case. | PASS |
| Cleanup | QA user document, 318 messages, 97 conversations, 9 memories, 6 files, and feeling state matched the pre-run backup exactly. Temporary sessions, transactions, calls, ingress rows, mappings, recall vectors, and synthetic Meilisearch documents were removed. | PASS |

The first spoken synthetic project-name probe was mistranscribed by local STT. The same live call then
used the playground transcript input and produced the correct audible answer. This was recorded as an
STT observation rather than misclassified as a memory failure.

The external Telegram Desktop chat was not used for synthetic writes because the isolated QA user
does not own a separate external bot conversation. Native signed Telegram ingress, persistence, and
streaming were exercised instead; no synthetic message was sent from the primary-profile Telegram account.

## Automated Evidence

- `130` parent launcher, continuity, hardening-contract, and upgrade tests passed.
- `163` LibreChat recall, corpus, file-search, hardener, and Workbench governed-proposal tests
  passed.
- `14` shared memory-policy tests passed.
- The compiled API package build and native launcher syntax check passed.
- Live health returned healthy, continuity audit reported `ok`, and the active Mongo database list
  contained only the canonical product and system databases after temporary forensic cleanup.

## Acceptance

This closes `MEMCONT-006` and adds coverage for persistence identity, primary-turn preservation,
same-pass hardener preservation, cross-surface saved-memory/recall parity, and guarded QA cleanup.

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: three-gate memory continuity.
- Requirement: persistence identity, saved-memory revision safety, scheduled consolidation, and bounded recall provenance.
- Use case: recover one recent synthetic event through the appropriate memory surface across browser, Telegram, and voice.
- QA case: `MEMCONT-006` and its linked hardening, recall, Telegram, Workbench, and voice cases.
- Expected result: the active database branch is verified, reviewed writes survive maintenance, and recall preserves decisive source context.
- Actual evidence: every gate in the Evidence table passed and cleanup matched the pre-run fixture.
- Remaining gap or fix: this incident report does not itself prove a fresh public install or every unrelated feature.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Requirement and use case | `MEMCONT-006` links the three memory layers and cross-surface user path. |
| Code owning path | Native Mongo identity, hardener/proposal preservation, and recall clipping/ranking were inspected. |
| Docs and nested docs/repos | Root memory/recall docs and nested LibreChat memory contracts agree. |
| Scripts or harnesses | Parent/LibreChat regressions, Workbench evals, Chrome, Telegram ingress, and voice ran. |
| Local/external prerequisite state | Active Mongo, recall corpus, scheduler, browser, Telegram, and voice services were verified. |
| Logs | Schedule, provider, recall, and cleanup summaries matched the visible results. |
| DB/state/persistence | Branch checksums, inserted counts, revisions, corpus counts, and restoration were checked. |
| Generated/shipped artifact | Compiled API package and launcher syntax passed; clean install remains a release-level gate. |
| Real user path | Chrome, native Telegram transport, Modern Playground voice, and Workbench were exercised. |
| Visual/UX comparison | Answers, retrieval sources, audible delivery, and history agreed with persistence. |
| Not run / blocked | A separate external Telegram account was intentionally not used for synthetic writes. |

Supporting evidence cannot replace required user-path evidence; the browser, Telegram, voice, and Workbench paths were run directly.

## User-Grade Evidence

- Surface exercised: Chrome, native Telegram transport, Modern Playground voice, and Prompt Workbench.
- Real user path: seeded a synthetic event, recalled it with saved memory and recall isolated, inspected sources, refreshed, and heard voice delivery.
- Visible outcome: each path returned the complete event through the intended layer with no false success.
- Expanded/detail state: persisted retrieval sources and Workbench semantic results were inspected.
- Persistence/reload result: browser and voice-linked results persisted, then all synthetic state was restored exactly.
- Local/external prerequisite state: active Mongo, recall, scheduler, browser, Telegram ingress, and voice services were healthy.
- Backend/log/DB confirmation: branch identity, revisions, messages, corpus chunks, schedule evidence, and cleanup agreed.
- Final model/runtime wording check: answers remained evidence-grounded and did not collapse the three memory layers into one.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting evidence, not substitutes for any required visible-UI, detail-state, persistence, or wording step.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timings, and conclusions only.
