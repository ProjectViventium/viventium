# Memory Continuity Incident Repair - 2026-07-14

## Summary

Status: **PASS for the three-system incident scope**. The repaired scheduler, saved-memory, and
conversation-recall paths pass source, automated, CLI, DB/log, live-runtime, native Telegram,
primary-profile Chrome, Prompt Workbench, exact same-marker voice, persistence, and cleanup checks. The
final primary-profile current-route conversation-recall voice lane took 17.1 seconds end to end, so
performance remains an open residual without weakening the correctness result.

## Findings

1. The 03:00 hardener did fire and finish successfully, but its LaunchAgent could not find the
   configured Codex executable and immediately fell back to a much slower provider path. The
   scheduler itself was not missing.
2. Saved-memory failed at two earlier boundaries before concurrency was even exercised. The compiler
   inverted configured foundation priority and selected an unavailable secondary provider. After
   correcting that, the real writer still crashed during initialization because the agent client
   omitted the revision-bearing state method required by the shared memory processor. Saved-memory
   writes also lacked a complete concurrency contract: same-user detached turns could be coalesced,
   prompt content and expected revisions could come from separate reads, delete/recreate could reset
   state, stale panel/artifact updates could regress visible state, and online duplicate migration
   bypassed guarded revisions. The native Telegram journey then exposed another independent failure:
   a valid replacement for a nearly full key exceeded that key's configured budget, no durable row
   changed, but the completed provider call was still logged as a successful memory run. Separately,
   the chat-time read profile capped `preferences` below its governed write budget, so a successfully
   stored fact in the middle of the value could be omitted from the injected memory context.
3. The historical recent event existed in chat history. The original failed turn did not call
   recall, but that was not the complete root cause: a fresh production-path replay did call
   `file_search` repeatedly and still produced an incomplete answer. The venue, names, and
   relationship had been stated in adjacent short messages, while lexical rescue returned each
   matching message as an isolated turn. Recall also had false-green health and failure-coupling
   paths that could turn provider failure into apparent no-match. Persisted assistant rows could
   also sort a few milliseconds before their parent user rows. Finally, the canonical recall prompt
   had been updated while two source YAML files still carried an older duplicated literal, so the
   generated live prompt kept the stale tool-deflection behavior.
4. Workbench could repair nested execution metadata while leaving the dispatch-owned top-level
   executor stale. Public status accepted arbitrary HTTP 200 responses as scheduler readiness, and
   the built-in Workbench timezone stayed pinned to its first compiled city.
5. Voice exposed two independent acceptance failures. First, a valid fresh call had recall enabled,
   healthy RAG, the canonical prompt, and `file_search`, yet did not search on the first explicit
   recall turn and answered incorrectly; a later successful search proved the corpus and tool were
   available. Second, an earlier repair proposal accidentally drifted source from the established
   dedicated `xai / grok-4.3 / none` route and OpenAI Terra voice fallback. When the owner restored
   xAI in Agent Builder, the shared optional-model panel retained OpenAI's
   `useResponsesApi: true` parameter. Logs proved the resulting xAI call carried the incompatible
   transport flag and stalled. The established source contract was correct; provider-specific form
   state was not isolated across a provider change.
6. Final current-route QA exposed two deeper runtime failures. Final-run Feelings telemetry read a
   method-local `feelingSnapshot` outside the method that created it, so an otherwise valid voice
   request could throw before reaching the provider. Once corrected, xAI called `file_search` but
   mixed the right prior-chat event with an unrelated meeting: transcript reservation forcibly
   frontloaded its source class after reranking. In the same path, the transport placeholder `new`
   masked the concrete runtime thread id, and a verbatim active-question echo received an exact-query
   bonus. Those ranking/exclusion defects could turn current input and unrelated transcript text into
   apparently strong prior evidence.

## Surgical Repairs

- Compiler-owned primary-first memory-provider selection and the complete revision-bearing memory
  store interface are now exercised by the real writer path.
- Per-user FIFO memory writing, one-query state snapshots, retained tombstones, atomic revisions,
  guarded panel/hardener/proposal writes, authoritative client reconciliation, monotonic set/delete
  artifacts, fail-closed proposal results, and public-safe audit data.
- The bounded chat-time read profile now carries the complete governed `preferences` value and a
  correspondingly larger total budget, without initializing the writer or placing maintenance on the
  main response path.
- One bounded correction attempt for structured, model-correctable storage-policy rejections when
  zero writes applied. Error artifacts take precedence over earlier batch successes, partial batches
  are never replayed, only the final artifact is delivered, and unresolved rejection is classified
  as a failed detached writer run.
- Semantic RAG health, independent lexical/vector retrieval, inconclusive dual-failure handling,
  runtime source-only mode preserved for already-known authorized corpus rows, and bounded
  same-conversation adjacent-turn expansion around lexical source hits.
- Stable same-conversation parent-first corpus order with freshness computed from the maximum
  eligible timestamp, plus a regression for timestamp-inverted persisted rows.
- One canonical recall prompt referenced from both source YAML bundles with `promptRef`. The model
  owns `file_search`, retries one weak result once, and asks one focused clarification when evidence
  remains inconclusive. Compiler coverage proves generated live YAML matches the registry source.
- LaunchAgent executable resolution repaired without adding another cadence. The single
  `StartCalendarInterval` remains 03:00 system-local time. Trigger receipts now expose requested
  and effective model tuples, and a provider fallback mismatch cannot report healthy.
- Workbench reconciles the authoritative executor, preserves user prompt/schedule/active/history,
  tracks system-local timezone only for the managed default, omits schedule data from unrelated
  saves, and keeps explicit timezone edits fixed.
- Public status verifies Scheduler status/service/ledger identity and reads Memory Hardening from
  its dedicated loaded/receipt/run health.
- Authenticated scheduled Sol/xHigh runs remove request-scoped model fallbacks after applying the
  exact tuple. An unavailable exact route now fails truthfully without changing ordinary chat.
- The established dedicated voice route is restored unchanged as `xai / grok-4.3` with
  `reasoning_effort: none`, no Responses flag, and `openAI / gpt-5.6-terra` as its explicit voice
  fallback. Agent Builder now clears only the prior optional route's parameter bag on a real provider
  change while preserving initial hydration, including a mounted empty-to-value form reset. Optional
  route panels are keyed to the form's agent id, so switching agents while a detail panel remains
  open also resets provider-history state without erasing the newly loaded route. The
  exact-model recall fixture temporarily enables conversation recall only for its isolated QA user
  and restores the original preference in `finally`, so an eval cannot silently test a
  recall-disabled account or leave user state changed.
- Final-run Feelings telemetry now reads the request-owned instance snapshot used by the voice
  controller, so telemetry cannot fail the model call by crossing method scope.
- Mixed-resource file search preserves the shared rerank order. Transcript coverage may occupy a
  bounded tail slot but cannot jump ahead of stronger chat evidence unless transcript evidence
  already ranks first. The `new` placeholder yields to the concrete runtime thread for active-chat
  exclusion, and verbatim prompt echoes remain low-priority provenance without an exact-match bonus.

## Scope Run

- Final post-fix regression pass: 153 compiler/governance/config-sync tests, 168 Prompt Workbench/
  scheduler-semantics/prompt-registry/eval-harness tests, 64 memory-hardening contract tests, 79
  package memory-agent/policy tests, and 10 memory-route/write-coordinator tests passed. The focused
  Agent Builder helper suite passed 11/11 after the initial hydration guard. The final optional-panel
  component/helper pass then passed 17/17, including same-agent persistence and different-agent
  remount behavior, and the production client rebuilt with post-build verification. Three stale
  governance assertions from the superseded Sol/Opus voice proposal were the only failures in this
  pass; aligning those tests with the established xAI/Grok plus Terra contract made the complete
  153-test group pass.
- Memory/recall package suites: 92 passed.
- Final focused memory suites: 49 package tests, 145 API client tests, 12 data-schema/key tests, and
  87 hardener/proposal/route tests passed. The package build passed and the rebuilt runtime artifact
  contains the correction path.
- File-search hybrid suite: 49 passed; recall prompt/filter/service suite: 40 passed; recall package
  suite: 13 passed.
- Agent controller, Feelings telemetry, and voice route suites: 178 passed after the final-run
  snapshot-scope repair.
- Hardener/proposal suites: 80 passed; memory data-schema suite: 9 passed.
- Memories route/coordinator/token suites: 16 passed.
- Client artifact-ordering suite: 5 passed; production client build passed.
- Focused Memories stale edit/delete/atomic-rename route suite: 7 passed; client conflict
  invalidation suite: 2 passed.
- Memory-hardening wrapper/health contract suite: 61 passed, including provider-mismatch health.
- Prompt Workbench suite: 113 passed; install-summary suite: 60 passed.
- Scheduling Cortex suite: 113 passed; Scheduler route/override suite: 19 passed.
- Config compiler suite: 121 passed, including both primary-provider orderings, single-provider,
  connected-account memory selection, and registry-to-live recall-prompt equality. Prompt registry
  suite: 25 passed.
- Telegram bridge suite: 323 passed. Voice gateway suite: 342 passed plus 48 subtests.
- Release memory/no-runtime-NLU suite: 64 passed.
- Real runtime: core surfaces running, Recall reports semantic `UP`, Memory Hardening reports
  `healthy`, and Scheduler readiness matches the configured ledger identity.
- Real Chrome: the enabled built-in task visibly shows 03:00, GlassHive host, Sol/xhigh, completed
  history, and persists after restart/reload.
- Real scheduler generation: authenticated OpenAI/Sol/xhigh tuple applied, exact synthetic marker
  returned, two messages persisted, supporting transaction rows existed, and all synthetic rows
  were removed afterward.
- Real saved-memory writer: active generated configuration selected the configured primary; writer
  initialization succeeded, the shared processor completed, and a no-store control left memory
  unchanged. A native pre-repair write reproduced a real near-full-key policy rejection: the
  assistant acknowledged the request, but Mongo showed no revision/value change and logs falsely
  reported success. Post-repair, a new native Telegram write hit the same limit, logged one bounded
  correction, applied a 471-token replacement, advanced the revision exactly once, contained the
  synthetic fact, and ended with `memory_run_done status=ok`.
- Native Telegram recall seed: the ordinary synthetic event persisted in chat history and appeared
  in the authorized conversation-recall vector corpus, while the durable preference remained absent
  from saved memory after the rejected pre-repair write. This proves the two continuity surfaces
  diverged exactly as the product model requires investigators to distinguish.
- Real historical-recall replay: before adjacent-turn expansion, a fresh full-tool run searched for
  about 6 minutes 43 seconds and omitted facts present in neighboring source turns. After the fix,
  a fresh run retrieved the venue, both people, and relationship together and answered completely in
  about 53 seconds. Exact synthetic probe rows were removed and the recall corpus was rebuilt.
- Live corpus order: the rebuilt authorized vector corpus places the native Telegram parent before
  its assistant child despite the child's earlier persisted timestamp. The corpus metadata advanced
  after the latest native turn and reports matching source/upload digests.
- Owner-Chrome recall: a brand-new conversation recovered the native event on its first turn, visibly
  showed `Ran file_search` and the recall sources, and still showed the same grounded answer and
  sources after a fresh URL load.
- Corrected Prompt Workbench exact-model recall evals: OpenAI Sol/medium passed 3/3 with semantic
  score 1.0 in 12.4-13.3 seconds; Terra/low also passed 3/3 but was not faster overall. The final
  post-cleanup Sol case passed with semantic score 1.0 in 13.4 seconds, made its own retrieval calls,
  and restored the isolated QA user's recall preference exactly.
- Focused Prompt Workbench mixed-corpus voice eval: the live semantic case completed in one attempt,
  invoked `file_search`, produced an honest clarification when its isolated fixture had no evidence,
  passed its semantic judge with high confidence, and restored the fixture state.
- First automatic post-repair hardener: launchd fired at 03:00:01 system-local time, the guarded run
  started at 03:00:05, and it completed at 03:01:32 with success. The requested/effective OpenAI
  Sol/xhigh tuple matched, one model attempt succeeded, two guarded updates applied with zero
  conflicts, and current schedule health is healthy with no missed expected window.
- First automatic post-repair Workbench run: fired at 03:00:04 system-local time and completed at
  03:08:10 through GlassHive. The child run, parent task, delivery, and callback state all completed
  without an active callback backlog; real Chrome showed the persisted completed run, the artifact
  generated at 03:03, and the next occurrence at Jul 15, 03:00.
- Broader scheduler audit: the owner account's Workbench definition is active at daily `03:00`,
  `schedule_timezone_mode=local`, and the current system-local timezone. All owner tasks
  have future next-run timestamps and no failed or partial status. One long-interval user task keeps
  a truthful historical `missed` occurrence after its misfire window elapsed and has a valid next
  run. Four `partial_success` rows in the system-wide ledger belong to other local accounts whose
  Telegram channel has no mapping; they are explicit delivery degradation, not false scheduler
  success, and this repair does not rewrite those users' schedules.
- Saved-memory browser gate: with conversation recall disabled and saved memory enabled, a brand-new
  owner-profile conversation recovered the exact native Telegram marker without `file_search`; a
  fresh URL load preserved the answer.
- Saved-memory voice gate: with conversation recall disabled, a fresh Modern Playground turn
  recovered a known baseline saved preference from the injected memory context with zero
  `file_search` calls. The visible transcript was correct, xAI streamed 1.25 seconds of
  non-cancelled audio, and the turn completed in 6.4 seconds end to end.
- Conversation-recall voice gate: with recall enabled, a fresh owner-profile call recovered the
  separate native Telegram event on its first explicit recall turn using a temporary OpenAI Sol LLM
  route. The visible answer contained all synthetic event fields, three `file_search` sources
  persisted in the linked chat and remained after reload, and xAI TTS streamed 5.53 seconds of
  non-cancelled audio. The turn took 16.9 seconds end to end, including 15.0 seconds to first model
  text. This proved recall and audio, but did not prove the configured xAI LLM route.
- Direct configured-route probe: after the mixed-corpus repair, an isolated actual
  `xai/grok-4.3` voice request called `file_search`, ranked the relevant prior conversation first,
  excluded the active prompt, returned the people, venue, and marker without blending an unrelated
  meeting, and completed in 6.2 seconds. Its temporary state and preference change were removed in
  `finally`.
- Current-route owner voice gate: in the existing signed-in browser profile, Agent Builder still
  displayed `grok-4.3`. A fresh Modern Playground call used xAI Chat Completions with
  `reasoning_effort=none`, invoked `file_search`, and visibly returned every field from the earlier
  synthetic browser event. The linked chat showed the prior conversation first in expanded sources,
  kept unrelated transcript results below it, and preserved both sources and answer after refresh.
  Chrome showed active speaker playback; xAI TTS streamed 11.53 seconds of non-cancelled audio. The
  provider completed both calls with HTTP 200, and the escaped Feelings `ReferenceError` was absent.
- Exact same-marker voice gate: with conversation recall disabled, a fresh owner-profile Playground
  call asked for the exact durable marker written through native Telegram. The saved-memory prompt
  layer was present, conversation-recall context was absent, the model made zero tool calls, and xAI
  Chat Completions returned HTTP 200 from `grok-4.3` with `reasoning_effort=none` and no Responses
  transport. The visible answer was exact, xAI delivered 1.57 seconds of non-cancelled audio, and the
  exact prompt/answer pair remained after a fresh linked-conversation load.
- Runtime/config correlation: source agent config, compiled config, live agent config, Agent Builder,
  outbound-provider telemetry, Mongo, and TTS logs agree on `xai / grok-4.3 / none`, no Responses
  flag, and the configured OpenAI Terra voice fallback. A real UI regression check switched from
  OpenAI Responses to xAI and observed the incompatible parameter clear before save. After the
  final production build, owner-profile Chrome still showed both continuity preferences enabled and
  the detailed voice panel persisted xAI, `grok-4.3`, None, Responses disabled, and Terra fallback.
  The final helper regression also proves a mounted empty-to-value form reset preserves persisted
  route parameters rather than clearing them as a user-initiated switch.
  The real signed-in browser then kept the voice panel open, loaded a second agent, selected an
  unsaved OpenAI provider, and returned to the original agent. Its xAI/Grok route remained intact
  before and after a full reload; the fallback detail still showed OpenAI Terra. Mongo independently
  showed the original route unchanged and the second agent's voice fields still unset, proving the
  unsaved form state neither persisted nor leaked across agents. The agent-scoped panel regression
  additionally proves that a same-agent rerender preserves the mounted panel while a different-agent
  form hydration remounts it with clean provider history.
- Cleanup gate: exactly the synthetic/local QA conversations, messages, transactions, call sessions,
  and local Telegram ingress row were removed. Cleanup read the current saved-memory revision and
  removed exactly one synthetic line rather than restoring an older snapshot; the revision advanced
  from 10 to 11 while all non-synthetic content remained. The real Telegram conversation and its 34
  legitimate messages remained. Mongo and Meilisearch reached exact parity, recall was rebuilt with
  matching source/upload digests, all 798 vector-source chunks contained zero marker occurrences,
  and owner Chrome plus Mongo showed Saved Memory ON and Recall ON. The final current-route seed and
  two voice calls were then removed through the authenticated conversation path plus exact
  call/accounting cleanup. Mongo and Meilisearch contain zero final synthetic records, while saved
  memory contains zero synthetic-marker matches. The saved-memory cleanup revision-edited an
  existing active key rather than deleting a key; a final live DB check found zero tombstones. The
  active recall corpus rebuilt to 702 eligible turns with matching source/upload digests and Recall
  still ON.
- ClaudeViv Opus 4.8 completed a max-effort review-only pass over the governing docs, owning code,
  tests, and runtime evidence. It accepted local incident closeout with no must-fix code defect or
  overcomplicated design. Its one cleanup-wording ambiguity was reconciled against the live DB state
  above.
- A final post-delta Opus 4.8 review then confirmed all five agent-scoping claims and accepted the
  unset-regression repair with no must-fix finding. It verified that the key uses the watched form id,
  that the current single form reset hydrates id and provider atomically, and that applying the same
  lifecycle boundary to all three shared optional panels is surgical rather than scope expansion.

## Residual Risk

- First-turn voice recall is correct but variable: the temporary Sol LLM run took 16.9 seconds, the
  final owner-profile xAI run took 17.1 seconds, and the isolated xAI probe took 6.2 seconds. The
  corrected Terra eval was not faster than Sol, so this repair does not trade recall quality for
  lower latency. Continue profiling retrieval-round count and first-token latency under the existing
  outcome metric.
- Managed-local Workbench timezone follows the operating system at startup reconciliation; a timezone
  change while that backend remains continuously running takes effect on its next restart. An
  explicit schedule or timezone edit intentionally changes the managed built-in row to fixed mode and
  is then preserved.
- The owner/system schedules in this incident are healthy, but the full multi-account ledger also
  contains four active tasks for other local accounts whose latest runs are truthful
  `partial_success` deliveries because those accounts have no Telegram mapping. Every active task has
  a future next-run timestamp and none is overdue. This repair did not guess another account's desired
  channels or mutate its schedule state.
- The separate Brain Setup summary can still say the account-scoped primary AI needs setup when its
  status path cannot prove the signed-in user's OAuth state, even though live provider calls succeed.
  This is a status-copy truth issue, not a failure of the repaired memory, recall, scheduler, or voice
  paths.
- This incident repair is proven on the active local runtime. It is not a public-release signoff for
  unrelated dirty-worktree changes, nested-repo publication, or clean-machine installation.

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: continuity across saved memory, scheduled hardening, and conversation recall.
- Requirement: memory-system, recall/RAG, scheduler, and installer/runtime identity contracts.
- Use case: recover a recent event correctly across browser, Telegram, voice, and nightly maintenance.
- QA case: the affected memory-continuity, hardening, recall, scheduler, Telegram, and voice cases.
- Expected result: each memory layer remains distinct, durable, revision-safe, and traceable to the active persistence branch.
- Actual evidence: the automated and live evidence run above passed with exact synthetic cleanup.
- Remaining gap or fix: voice recall latency remains variable; clean-install publication is a separate release gate.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Requirement and use case | Memory, recall, scheduling, and runtime-identity requirements were mapped to affected cases. |
| Code owning path | Compiler, native Mongo launcher, writer revisions, recall ranking, scheduler, Workbench, and voice were traced. |
| Docs and nested docs/repos | Root memory/scheduler docs and nested LibreChat/runtime contracts agree. |
| Scripts or harnesses | Release suites, Workbench evals, Telegram ingress, browser, and voice harnesses ran. |
| Local/external prerequisite state | Active Mongo, RAG, scheduler, browser, Telegram, voice, and model routes were verified. |
| Logs | Provider, scheduler, recall, memory, and voice summaries matched the observed behavior. |
| DB/state/persistence | Revisions, corpus digests, messages, sources, schedules, and exact synthetic cleanup were checked. |
| Generated/shipped artifact | Compiled API/client/runtime artifacts were inspected; clean install remains outside this incident report. |
| Real user path | Chrome, native Telegram ingress, Modern Playground voice, Workbench, and CLI status were exercised. |
| Visual/UX comparison | Answers, sources, memory controls, schedule state, and audio agreed with persistence. |
| Not run / blocked | This report does not claim unrelated dirty-worktree publication or clean-machine install. |

Supporting evidence cannot replace required user-path evidence; browser, Telegram, voice, Workbench, and CLI paths were run directly.

## User-Grade Evidence

- Surface exercised: Chrome, native Telegram transport, Modern Playground voice, Prompt Workbench, and CLI status.
- Real user path: created synthetic facts, recalled them with each memory layer isolated, inspected sources, refreshed, and observed scheduled maintenance.
- Visible outcome: the complete synthetic event was recovered through the intended layer and truthful failures no longer appeared as success.
- Expanded/detail state: recall sources, agent route panels, schedule history, and memory revisions were inspected.
- Persistence/reload result: answers and sources survived reload; exact synthetic state was removed without reverting legitimate state.
- Local/external prerequisite state: Mongo, RAG, scheduler, model routes, Telegram ingress, and voice services were healthy for the accepted runs.
- Backend/log/DB confirmation: revisions, corpus digests, provider routes, schedule rows, call state, and cleanup all matched the UI.
- Final model/runtime wording check: tested answers used evidence, clarified inconclusive recall, and did not conflate saved memory with recall.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting evidence, not substitutes for any required visible-UI, detail-state, persistence, or wording step.

## Automated Evidence

The exact regression totals and production builds are recorded in Scope Run. All affected final groups passed after the listed repairs; this report does not convert the clean-install gap into a pass.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timings, and conclusions only.
