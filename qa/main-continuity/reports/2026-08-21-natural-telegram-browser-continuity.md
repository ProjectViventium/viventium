# Main Continuity QA Run - 2026-08-21

## Summary

- Result: `PARTIAL`. The final repaired source closes the two incident-blocking defects with focused
  automation and a real headed-Chrome offline/resume/refresh run. The exact natural Telegram reply
  object passed on repaired pre-final source; no new Telegram generation was sent after final activation.
  The full Main Continuity program and release chain remain partial.
- Final build/source under test: parent HEAD `c9ce8dde116cab7338d78d81ac82e6d2f278abe5`
  with status-z hash `efc08f1dc1dd55932001e277b479841148d4879546cfb3812cb9879d9fa08306`;
  LibreChat HEAD `1b59b20b6fb0e3098aba1a527f47f8a36281c2fd` with status-z hash
  `f1698438edb6471d5216525ffa314e9501f93ca1bbd25fc45de70cc4a4542bb2`, robust diff and
  untracked-content fingerprint `d23aece22f84e00ea5951c16a3f2cc32ac9d0957d1782f187f61a78e7d21d917`,
  and final projection hash `6819106bcd67a41f849a50196d2770f2b9c3174001bbba4ca06c2a2a72b26f48`;
  GlassHive HEAD `6167132ad0aa1d8d6d30746fe9c9631f56310d9f` with status-z hash
  `b3f9793ec68aa22976f0b7861e16e230cd20e1f7039b0269498d356f11581d9b`.
- Final runtime/artifact under test: this dirty checkout was activated through the supported path at
  14:42 local on 2026-08-21; API started at 14:42:38 and frontend at 14:42:43 after source and build
  completion. This is exact installed-source proof, not a clean release artifact.
- Runtime telemetry: LibreChat source `94a23f691958f17b`, Agent Builder agent `fa9d01796812e14e`,
  compiled/live config `931aae799e3b4343`, and compiler `3f03818390bca5f8`.
- Telegram boundary: the natural typed reply-object run occurred at 11:07-11:08 on repaired source
  before the final browser-only liveness edit. Visual inspection after final restart showed the exact
  reply and voice persisted with no error bubble; this is not a final-source Telegram generation.
- Environment: installed local production, private Telegram, Chrome, Prompt Workbench, GlassHive,
  MongoDB, Meilisearch, and recall/RAG.
- Tester: Codex with an independent review-only pass.
- Related change: provider-neutral Main continuity, bounded replay, typed Telegram provenance,
  final-Main presentation, and structured visible-text persistence.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `MC-001` | `PASS-LIVE` | Repaired pre-final natural Telegram reply object resolved the automated result as Viventium-authored | Exact reply and voice persisted after final restart; final edit was browser-only and no new Telegram generation was sent |
| `MC-002` | `PASS-LIVE` | Pre-P0 terse Telegram follow-up stayed on the active recommendation objective | One concise Main answer; one accepted delta; no unrelated topic, fallback, or failure bubble; does not prove later repairs |
| `MC-007` | `PARTIAL` | Synthetic overlapping-turn admission reserves and accepts each stable input once | Real simultaneous-turn acceptance is unrun; this is not the durable A/B/background-work/quick-C journey |
| `MC-010` | `PASS-LIVE` | A pre-final configured-Main Workbench run delivered once to LibreChat and Telegram | New visible schedule conversation; configured Agent Builder GlassHive route; does not prove later repairs |
| `MC-016` | `PASS-AUTOMATED` | Final-source tests preserve foreign-bot, anonymous-admin, and third-party sender roles and exclude group captions from owner-authored text | Real group user path remains unrun |
| `MC-020` | `PARTIAL` | Current internal schedule envelope was hidden and memory-ineligible | Manual Run Now did not refresh recurrence advancement; legacy history can still show an internal marker |
| `MC-023` | `NOT RUN` | Current-candidate durable background-work journey was not repeated | Historical adjacent proof is linked below |
| `MC-036` | `PASS-LIVE` | Exact final-source isolated headed Chrome recovered offline FINAL without reload, cleared Stop, showed one assistant without a phantom branch, and preserved the Stop-flow partial and one assistant after refresh | Exact lost-terminal/404 is automated-only because live recovery replayed FINAL; provider abort/tombstone remains partial or not run |
| `MC-042` | `PARTIAL` | Main-to-specialist-to-Main produced one final Main answer in Chrome | Real run preceded the latest fragment repair |
| `MC-044` | `PARTIAL` | Two participant-owned browser columns survived refresh | Real run preceded the latest fragment repair |
| `MC-045` | `PASS-AUTOMATED` | Final candidate includes the repaired StandardGraph ownership and multi-agent hiding regressions | Owning files passed 302 API plus 40 frontend assertions before a later nonconflicting liveness-only edit; live forced interleaving remains unrun |

The complete registry contains 46 cases: 12 `PASS-LIVE`, 10 `PASS-AUTOMATED`, 12 `PARTIAL`, and
12 `NOT RUN`. All 12 requirements remain `partial_candidate_unverified`.

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `MC-UC-001` | Receive configured Main schedule output, reply to that exact Telegram bubble, then ask a terse follow-up | Prompt Workbench + Telegram | `PARTIAL` | Repaired pre-final natural exact-reply run attributed ownership correctly; pre-P0 terse follow-up passed | Delivery ledger, Main continuity, provider session, persisted messages, and post-restart visual persistence correlated | Send a new exact reply object and terse follow-up after final activation |
| `MC-UC-002` | Continue the same objective across Telegram and browser, use an internal specialist, and refresh | Telegram + Chrome + GlassHive | `PARTIAL` | Final-source normal chat resumed after forced offline time and survived refresh; pre-final cross-surface and multi-agent runs also passed | Final Chrome DOM, isolated persistence, active-stream state, and GlassHive completion agreed | Exact lost-terminal/404 and provider abort/tombstone are automated or unrun; expanded details and multi-agent final-source live proof remain open |
| `MC-UC-003` | Send overlapping turns, corrections, and substantial independent work while Main stays available | Telegram + Chrome + Active Work | `NOT RUN` | No current-candidate end-to-end A/B/background-work/quick-C journey | Synthetic admission and historical adjacent parallel-work evidence only | Run the complete journey on the repaired source |
| `MC-UC-004` | Use long conversations through compaction, overflow, restart, provider fallback, and recall degradation | Browser + Telegram + GlassHive + recall/RAG | `PARTIAL` | Pre-P0 bounded replay and compaction automation exists | Context manifests, fallback parity, recall health, and synthetic soak | Revalidate repaired source; forced live degradation and real 100-plus-turn paths remain open |
| `MC-UC-005` | Exercise unknown, deleted, foreign, group, multipart, retry, and crash-window Telegram provenance | Telegram | `PARTIAL` | Repaired pre-final known-owner reply passed; final-source group and anonymous boundaries pass focused automation | Typed reply evidence and final-source sender-role regressions are registered separately | Run real unknown, deleted, foreign, group, multipart, retry, and crash cases on final source |
| `MC-UC-006` | Prove exact source, pin, built artifact, installed process, restart, and public/private boundary | CLI + installed runtime + clean checkout | `PARTIAL` | Exact dirty source, installed processes, restart, and current runtime are identified | Candidate registry records final, pre-final, historical, and not-run evidence per case | Clean nested commits, parent pins, built artifact, clean install, and rollback remain open |

## Traceability

`Main continuity -> same cognitive Main across Telegram/browser/schedules -> terse and scheduled
follow-up use cases -> MC-001/002/010/020 -> correct referent, one useful answer, bounded context ->
repaired pre-final Telegram plus final-source browser/UI, logs, and DB -> incident blockers pass their
recorded levels; final-source Telegram generation, background-work, degraded, long-run, performance,
and release gaps remain`

- Feature: Main Continuity Kernel.
- Requirement: [Main Continuity Kernel](../../../docs/requirements_and_learnings/56_Main_Continuity_Kernel.md).
- Use case: receive Main work now or later, then continue naturally without losing the referent.
- QA case: `MC-001`, `MC-002`, `MC-010`, and `MC-020` for the incident family; the remaining
  registry covers browser, fallback, memory, parallel work, restart, and long-run behavior.
- Expected result: one cognitive Main, one admitted context snapshot per turn, truthful provenance,
  bounded growth, one useful visible answer, and no repeated generic failure notices.
- Actual evidence: repaired pre-final Telegram, final-source Chrome, and focused final-source
  automation correlate visible results with persisted messages, delivery receipts, active-stream
  state, continuity state, provider requests, and recall health.
- Remaining gap or fix: run final-source Telegram generation and the broad matrices. The full feature
  and release stay partial as listed in Findings.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Requirement 56, this folder's `cases.md`, and the case table above |
| Code owning path | Which code path owns the behavior? | Core snapshot/continuity/provenance services, scheduler dispatch, GlassHive provider/store, and shared visible-content projection |
| Docs and nested docs/repos | Which docs define expected behavior? | Requirements 01, 11, 55, and 56; architecture/system maps; nested runtime architecture |
| Scripts or harnesses | Which checks exercised it? | Main-continuity generator/release contract, focused LibreChat suites, complete GlassHive provider/store suites |
| Local/external prerequisite state | Were dependencies healthy? | Core services, Telegram, Workbench, GlassHive, recall, MongoDB, and Meilisearch were healthy during accepted runs |
| Logs | What confirms or contradicts the result? | First turn used four reconnects, SYNC, CREATED, and replayed FINAL; two GlassHive requests returned HTTP 200 on one session with bootstrap sequence 1 then delta sequence 2, no omission, error, retry, or fallback |
| DB/state/persistence | What persisted? | Correlation found one Mongo assistant per turn; the Stop partial measured 459 live, 465 persisted, and 445 refreshed characters with one visible assistant and no Stop after refresh |
| Generated/shipped artifact | What installed artifact was inspected? | Active checkout and running process were checked; clean build/install and parent-pin parity remain open |
| Real user path | What was used like a user? | Pre-final Prompt Workbench and Telegram; final-source headed Chrome generation, forced offline interval, online resume, and refresh |
| Visual/UX comparison | Did visible behavior match evidence? | Yes for the final Chrome liveness slice and repaired pre-final exact Telegram reply; broad acceptance remains partial |
| Not run / blocked | What is missing? | Final-source Telegram generation; exact live lost-terminal/404; provider abort/tombstone; expanded final browser details; forced fallback/degradation; current background journey; crash boundary; real long soak; clean release |

## User-Grade Evidence

- Surface exercised: Telegram Desktop, Prompt Workbench, and Chrome.
- Real user path: a genuine configured-Main schedule delivered once and received a natural exact reply;
  final-source isolated headed Chrome recovered a backend-completed turn through four network
  reconnects without reload, then exercised a second visible-partial Stop and refresh turn.
- Visible outcome: the repaired pre-final Telegram reply was attributed to Viventium; final-source
  Chrome showed Stop during generation, cleared Stop after recovery, and displayed exactly one answer.
- Expanded/detail state: Workbench and pre-final participant presentation were inspected. The final
  liveness run did not repeat expanded native-tool details.
- Persistence/reload result: final screenshots show one branch after FINAL recovery and one Stop-flow
  partial after refresh, with one assistant and no post-refresh Stop. The second turn measured 459 live,
  465 persisted, and 445 refreshed characters. The repaired pre-final Telegram reply and voice remained
  visible after final restart without an error bubble.
- Local/external prerequisite state: the local stack and recall service were healthy. No external
  recipient was contacted and no connected-account write was performed.
- Evidence retrieval classification, if applicable: recall was available and embedded for accepted
  runs; forced unavailable/auth/timeout branches were not used as user-path substitutes.
- Fallback path, if applicable: automated parity and historical live recovery exist; forced
  exact-candidate primary/fallback QA remains partial.
- Backend/log/DB confirmation: both turns had one Mongo assistant. GlassHive used one session, two
  HTTP 200 requests, completed in 8.95 and 7.16 seconds, advanced bounded Main context from bootstrap
  sequence 1 to delta sequence 2 with zero omitted messages, and recorded no error, retry, or fallback.
  Core latency was 12.44 and 7.71 seconds. Provider abort/tombstone remains `PARTIAL` or `NOT RUN`.
- Final model/runtime wording check: Viventium attributed the automated work in the repaired pre-final
  reply path. Final-source group/anonymous boundaries pass automation; no real final-source group reply
  or new Telegram generation was substituted for that missing user path.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for the unrun real-user paths listed above.

## Automated Evidence

```bash
# Exact final candidate: client SSE 76/76; GenerationJobManager 42/42;
# affected agents route 13/13; client production build and post-build passed.
# Full Telegram 457/457; full GlassHive provider/store two-file suite passed.
# Main continuity release contract 6/6; QA operating 28 passed with one
# unrelated stale-catalog failure; Claude Opus final review passed activation.
# Repaired provenance source also passed Core provenance/recall 71/71 and
# adjacent file-search/request 84/84.
# Repaired persistence owning files: API 302/302 and frontend 40/40 before
# the later nonconflicting liveness-only edit.
python3 scripts/viventium/main_continuity_contract.py generate
viventium_v0_4/glasshive/runtime_phase1/.venv/bin/python -m pytest tests/release/test_main_continuity_contract.py -q
```

The focused final-source lifecycle suites, client build, full Telegram suite, and full two-file
GlassHive provider/store suite completed. The StandardGraph owning suites ran before later
nonconflicting terminal-stream edits. One broader integration command was stopped and is not counted.
Historical pre-P0 coverage remains 426 isolated LibreChat assertions and 186 GlassHive provider/store
assertions; one historical 274-test command printed a full passing summary but retained an open handle
and required manual termination. Historical totals do not replace final-candidate proof.

## Findings

- Defects: the group/anonymous ownership boundary and StandardGraph lost-final defect are repaired in
  the final registered source. `MC-016` and `MC-045` pass focused automation; `MC-036` passes a real
  final-source offline/resume/refresh run.
- Regressions: none remain failed in the registry. The broad program is not accepted because applicable
  real user paths and the clean delivery chain remain partial or not run.
- Flakes: one combined Jest process showed cross-suite timer/mock leakage; isolated owning suites pass.
- Environment issues: the final two Core turns took 12.44 and 7.71 seconds. Earlier schedule delivery
  took about 44 seconds, terse turns took about 10–18 seconds, and a specialist path took about 33 seconds.
- Residual risks: final-source Telegram generation; real unknown, foreign, group, deleted, and multipart
  replies; expanded final browser details; forced live fallback and recall-down behavior; current
  durable background-work journey; process-crash recovery;
  semantic-summary field coverage; real 100-plus-turn soak; lower prompt occupancy and latency; clean
  nested commits, parent pins, built artifacts, install, rollback, and public release parity.
- Observability warning: unknown-agent visible-delta repair warnings occurred while visible and
  persisted output remained correct; they require monitoring but are not a current acceptance failure.
- Hygiene: cleanup was manifest-scoped and backed by private permission-restricted preimages. Earlier
  personal Chrome QA cleanup removed exactly two proven conversations and four messages, preserved
  saved memory and the natural Telegram pair, rebuilt continuity and recall, terminated three linked
  workers, and retained audit rows. The final isolated run had zero personal impact: CAS removed one
  orphan continuity document; target conversations, messages, agent, temporary session, ACL, recall
  file, RAG file, synthetic queries, and search hits were all absent; three isolated saved-memory row
  digests were unchanged; and the exact worker accepted termination. The active project, provider
  session, and exactly two requests and two runs remain as audit because no supported non-destructive
  provider-session retirement exists. A personal-sidebar visual cleanup check remains `BLOCKED` by
  login and hosted-session timeout; no credentials were used. Backend cleanup postconditions pass.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
