# Meeting Transcript Import And Recall QA Run - 2026-07-11

## Summary

- Result: PASS for the requested owner-private import, hardening, vector repair, browser recall, and
  persistence path; PARTIAL for unrelated full installer/helper and cross-surface release coverage.
- Build/source under test: local public checkout plus the active nested LibreChat checkout.
- Runtime/artifact under test: installed local Viventium runtime and generated private runtime config.
- Environment: local macOS runtime on AC power with no observed thermal constraint.
- Tester: Codex, with a review-only Claude pass required before final acceptance.
- Related change: import eight owner-private meeting transcripts, harden their derived memory, and
  repair escaped retrieval/runtime defects discovered during end-to-end QA.

Private transcript text, meeting names, participant names, Calendar details, account identifiers,
conversation identifiers, screenshots, source paths, and raw runtime records are intentionally
omitted.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `MTM-003` | PASS | 8 meeting files processed; 6 configured sidecars ignored | No underscore-prefixed sidecar remained in the final processed index. |
| `MTM-004` | PASS | 12/12 transcript evals; focused and inventory sources visible | Narrow recall led with the exact summary while retaining broader context. |
| `MTM-006` | PASS | 8/8 direct authenticated summary-document checks returned present | Browser signoff followed physical vector proof, not process health alone. |
| `MTM-013` | PASS | One inconclusive-presence batch, then zero errors and 8/8 direct proof | No destructive repair was triggered by an inconclusive check. |
| `MTM-015` | PASS | Final answer preserved transcript/speaker uncertainty | No durable identity or unsupported decision was invented. |
| `MTM-017` | PASS | Two bounded transcript-only batches; 0 saved-memory writes | Five then three summaries were repaired without cap skips. |
| `MTM-020` | PASS | 42/42 file-search tests plus real browser/source-card QA | Exact metadata retrieval supplements rather than replaces the global batch. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `MEETING-UC-001` | Ask a narrow question grounded in a newly imported meeting. | Real local browser chat | PASS | Answer separated the requested meeting phases, showed source cards, stated uncertainty, and did not invent a decision. | Exact summary was source 1; all target summary documents were present; model turn completed without browser console errors. | None for this owner-private path. |
| `MEETING-UC-002` | Recover ingest when transcript sidecars and a missing vector dependency interfere. | Public CLI, generated config, Docker-backed local RAG, browser chat | PASS | Final browser answer remained grounded after recovery. | Canonical ignore rules compiled; only the missing declared vector dependency was restored; bounded batches completed without memory writes. | Semantic dependency-health behavior is covered by concurrent runtime work and needs its own release signoff. |
| `MEETING-UC-003` | Reopen the completed conversation and verify the answer and sources persist. | Real local browser reopen | PASS | Grounded answer and source cards reappeared; no console errors were observed. | Persisted conversation state matched the visible result. | None for this path. |
| `MEETING-UC-004` | Choose a transcript folder through the status-bar helper. | Canonical config/compiler path only | PARTIAL | Not exercised through the helper picker in this run. | Config backup and generated runtime value were verified privately. | Existing helper-picker result remains the latest user-grade proof. |
| `MEETING-UC-005` | Configure transcript ingest during a clean install. | Not run | PARTIAL | Not part of the owner import request. | Existing installer automation was not rerun. | Clean-install browser/helper proof remains outside this run. |

## Traceability

`meeting transcript memory -> memory and recall requirements -> owner import and narrow recall -> MTM-003/004/006/013/017/020 -> organized, processed, physically present, grounded, persistent -> installer/helper release proof remains separate`

- Feature: meeting transcript import, summary-only RAG, and runtime recall.
- Requirement: `20_Memory_System.md`, `32_Conversation_Recall_RAG.md`, and
  `45_Runtime_Feature_QA_Map.md`.
- Use case: organize eight private transcripts, enrich only from private Calendar evidence, process
  them, and retrieve one exact meeting faithfully in the product.
- QA case: `MTM-003`, `MTM-004`, `MTM-006`, `MTM-013`, `MTM-017`, and `MTM-020`.
- Expected result: eight valid meeting artifacts; no sidecar pollution; successful bounded
  summarization and vector upload; exact-summary-first grounded browser recall that persists.
- Actual evidence: 8/8 source/hash preservation, 8/8 direct vector-document presence, 57 processed
  index rows, zero final pending/cap/vector errors, and a persisted real-browser answer with visible
  sources and zero console errors.
- Remaining gap or fix: unrelated clean-install/helper and broader cross-surface release signoff were
  not part of this run.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Memory/recall docs; `MEETING-UC-001` through `MEETING-UC-003`; cases listed above. |
| Code owning path | Which code path owns the behavior? | Config compiler, memory-hardening wrapper/Node hardener, nested LibreChat file search, schema-tool binding patch, and RAG Compose declaration. |
| Docs and nested docs/repos | Which docs define expected behavior? | Project principles, memory system, installer/compiler, runtime QA map, meeting transcript QA cases, and nested runtime docs. |
| Scripts or harnesses | Which scripts, fixtures, or suites exercised it? | Public memory-hardening CLI, transcript eval runner, focused Jest suites, release tests, and a private Playwright harness. |
| Local/external prerequisite state | Which dependency was healthy or degraded? | AC power and thermal state passed; vector API was initially alive without PGVector, then PGVector was restored and direct document checks passed. |
| Logs | Which sanitized logs confirm or contradict the result? | Hardener summaries recorded 8 transcript attempts with 0 failures, then two bounded repair batches with 0 summary failures. |
| DB/state/persistence | Which state confirms it? | Final index: 57 processed; target corpus: 8/8 vectors present; persisted browser conversation reopened successfully. |
| Generated/shipped artifact | Which generated artifact was inspected? | Generated runtime config contained the canonical source and sidecar-ignore rules; local runtime hot-loaded the nested fixes for browser QA. |
| Real user path | Which path was used like a user? | Real local browser chat, source-card inspection, and conversation reopen. |
| Visual/UX comparison | Did the visible result match supporting evidence? | Yes. Exact summary led; answer structure and uncertainty matched the source-backed request; source cards persisted. |
| Not run / blocked | Which surface was not run? | Status-bar picker, clean installer, Telegram, and voice were not required for this owner import and remain separate release gates. |

## User-Grade Evidence

- Surface exercised: installed local browser chat.
- Real user path: submit one narrow private meeting-recall question, inspect the completed answer and
  source cards, then reopen the existing conversation without issuing a second model request.
- Visible outcome: the answer used the correct meeting, separated formal discussion from private
  follow-up, preserved uncertainty, and did not invent a final decision.
- Expanded/detail state: visible source cards included the exact target summary first plus inventory
  and supporting recall evidence.
- Persistence/reload result: the completed answer and source cards reappeared after reopen.
- Local/external prerequisite state: primary OpenAI route worked; local RAG and PGVector both served
  the verified target documents after repair.
- Evidence retrieval classification: local prerequisite unavailable, repaired, then successful.
- Fallback path: no fallback was required for the final browser turn.
- Backend/log/DB confirmation: exact source order, 8/8 physical target documents, and persisted state
  agreed with the UI.
- Final model/runtime wording check: grounded, useful, uncertainty-aware, and free of unsupported
  decisions or identity claims.
- Substitution check: browser-visible completion and persistence were both run; supporting state and
  tests were not used as substitutes.

## Automated Evidence

```bash
node qa/meeting-transcript-memory/evals/run-evals.cjs
# 12 passed, 0 failed

# From the nested LibreChat `api/` package
npm test -- --runInBand test/app/clients/tools/util/fileSearch.test.js
# 42 passed

npm test -- --runInBand server/services/viventium/__tests__/agentSchemaToolBindingPatch.spec.js
# 6 passed

uv run --with pytest --with PyYAML==6.0.2 pytest tests/release/test_memory_hardening_contract.py -q
# 52 passed

uv run --with pytest --with PyYAML==6.0.2 pytest tests/release/test_config_compiler.py -q -k 'memory_hardening_rejects_non_launch_ready_openai_model or memory_hardening_accepts_gpt56_sol_for_overnight_automation or memory_hardening_accepts_installed_gpt55_during_model_rollout'
# 3 passed

uv run --with pytest --with PyYAML==6.0.2 pytest tests/release/test_rag_api_override_contract.py -q
# 7 passed

bash -n viventium_v0_4/viventium-librechat-start.sh
docker compose -f rag.yml config -q
# Both passed
```

- The repository-wide QA operating-contract suite finished with 21 passing and 2 failing tests.
  Both failures came from unrelated concurrent worktree state: older reports outside this feature
  that have not migrated to the evidence template, and one unrelated release test missing its
  central ownership-map entry. Direct validation of this report returned zero violations.

## Findings

- Defects: source bookkeeping sidecars were eligible for summarization; the owner's canonical local
  ignore rules now exclude them. The shared fresh-install default remains empty and is not claimed
  fixed by this run. The compiler rejected an installed launch-ready model during rollout; the
  overnight hardening route now accepts GPT-5.5 and GPT-5.6-sol while continuing to reject GPT-5.4
  for that route. Interactive memory-agent model selection is separate. Request-scoped schema-tool
  binding could recurse; a guarded accessor and realistic concurrency regressions now cover it.
  Narrow meeting retrieval could miss an exact existing summary when the global vector batch
  returned distractors; focused metadata retrieval now supplements the batch.
- Regressions: all escaped defects above have synthetic tests or living QA cases.
- Flakes: the first persistence screenshot used a fixed short delay and captured an intermediate
  loading state; the browser harness was corrected to wait for stable visible answer content before
  acceptance.
- Environment issues: the vector API process returned healthy while its PGVector dependency was
  absent. QA restored only the missing declared dependency and required direct target-document
  checks before browser signoff. A final closeout replay reproduced the gap when foreground-launcher
  cleanup removed PGVector while the old RAG process stayed reachable; after scoped restoration, the
  final target-document result returned to 8/8.
- Residual risks: the vector API health endpoint can still look reachable without proving its
  PGVector dependency; `MTM-006` passes only for this run because all eight target documents were
  checked directly. Shared default sidecar ignores remain a product-policy decision. An Anthropic
  connected-account reconnect is still an account-action item, but it did not block the built-in
  OpenAI hardening or browser contract. Nested/public release and parent component-pin delivery were
  not requested and are not claimed.

## Independent Review

- ClaudeViv was not available, so local Claude CLI ran review-only with read/grep/glob access and no
  edit tools.
- Verdict: accept with named residual risks. It confirmed the request-scoped re-entry fix and
  additive metadata retrieval design are sound.
- Findings incorporated: corrected the reproducible compiler command/count, clarified the
  hardening-only GPT-5.4 rejection, made the owner-only sidecar scope explicit, and added an
  overlapping dynamic-binding regression plus the synchronous getter contract comment.
- Unresolved release risk: dependency-aware RAG health must be accepted separately before claiming
  durable unattended recovery. Tracked source and its seven contract tests enforce semantic `UP`,
  real 503 failures, PGVector readiness, and serialized recovery, but the long-running local recovery
  container has not reloaded that source and is not Compose-managed. The direct 8/8 vector proof is
  sufficient for this owner import, not a substitute for live-artifact release signoff.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
