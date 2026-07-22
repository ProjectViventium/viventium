# Memory Continuity QA Cases

## Case ID Convention

Use stable `MEMCONT-NNN` IDs for memory continuity cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `MEMCONT-001` | Saved memory, recall, and continuity state survive restore/upgrade without confusing stale facts for live truth. | User-visible behavior matches source, docs, persisted state, and logs | browser chat, memory state, restore/continuity checks | `tests/release/test_continuity_audit.py` plus user-grade QA when visible | PASS/PARTIAL 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); current dedupe dry-run found zero duplicate groups/docs/deletes, focused continuity tests passed, and fresh continuity capture was not run because it writes App Support state |
| `MEMCONT-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); public report keeps raw runtime, DB, browser, transcript, memory, token, and account evidence out of the repo |
| `MEMCONT-003` | Chat-time saved-memory reads are bounded, writer work is detached, and OpenAI-first provider routing is honored when OpenAI auth exists. | Turning on memory does not inject the full store, wait on writer maintenance/auth failures, route the main chat through stale Anthropic config, or show a red retrieval-tail/finalization error after a valid answer. | browser chat, generated runtime config, live built-in agent state, deep timing logs, memory DB state, CLI migration | API/unit tests, compiler/source audits, browser QA, log timing review, `bin/viventium memory-dedupe --dry-run` | PASS (2026-05-20: read path, detach tests, OpenAI-first route, scoped retrieval-tail and post-stream finalization suppression, browser QA, restart, and dry-run PASS) |
| `MEMCONT-004` | Detached saved-memory writes are FIFO per user, revision protected across surfaces, and truthful when storage policy rejects a proposal. | A synthetic channel fact is not dropped by a nearby turn, falsely reported as stored after a budget rejection, overwritten by stale web/voice/panel/hardener work, or corrupted by an unsafe legacy rollback; a later new conversation can use it. | isolated channel, browser chat, Memories panel, Modern Playground voice, Mongo, memory-writer audit | coordinator, bounded policy-retry, agent-memory, fixture tombstone/CAS/schema-v2 rollback, and hardener tests plus isolated-account cross-surface QA | PASS-AUTOMATED/PARTIAL 2026-07-20; focused memory/recall API 137/137, complete API 3,365 pass/19 skip, data schemas 405 pass/3 skip plus build; isolated channel-to-web/voice proof is NOT RUN |
| `MEMCONT-005` | Mixed-corpus conversation recall keeps global evidence order, excludes the active thread, and completes safely through the configured voice route. | A new voice conversation recalls the prior synthetic event without blending an unrelated meeting, citing its own prompt, or failing in final-run telemetry. | isolated browser, Modern Playground, linked chat, file-search sources, fixture DB/search, runtime/TTS logs | file-search reranking/exclusion regressions plus agent-controller/feelings/voice suites and isolated audible QA | PASS-AUTOMATED/PARTIAL 2026-07-14; reranking, active-thread exclusion, and controller regressions pass; isolated audible/browser persistence proof is NOT RUN |

## `MEMCONT-001` - Core User Flow

- Requirement: Saved memory, recall, and continuity state survive restore/upgrade without confusing stale facts for live truth.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_continuity_audit.py` plus any narrower feature tests discovered during implementation.
- Last run: PASS/PARTIAL 2026-06-05
  ([nightly review](../memory-hardening/reports/2026-06-05-nightly-routines-health-review.md));
  continuity audit completed, focused release tests passed, and memory dedupe dry-run found no
  duplicate groups in the overnight review. This supports restore/continuity health, but
  user-facing recall behavior still requires separate browser/chat recall QA, and today's scheduled
  hardener skipped on battery before fresh continuity updates.

## `MEMCONT-002` - Public-Safe Evidence Record

- Requirement: public QA artifacts must be reproducible and free of secrets, personal data, local paths, raw IDs, and private screenshots.
- Risk covered: a useful local QA run cannot be safely reviewed or published.
- Preconditions: a dated QA report is created for this feature.
- Steps:
  1. Review the report and related diffs for local absolute paths, account identifiers, tokens, raw logs, raw DB rows, private chats, and screenshots with private content.
  2. Keep raw/private evidence outside the public repo and summarize only public-safe counts, statuses, hashes, and conclusions.
  3. Link the report back to this case and the owning requirement doc.
- Expected result: the public report proves the behavior without leaking private/local data.
- Forbidden result: a report includes private transcripts, account identifiers, raw runtime dumps, local home paths, tokens, or secret-bearing command lines.
- Evidence to capture: public-safety scan result and link to the sanitized report.
- Automation: public-safety pattern scan plus relevant release tests.
- Last run: PASS 2026-05-27
  ([report](../memory-hardening/reports/2026-05-27-nightly-routines-health-review.md)); the public
  report uses sanitized counts, timestamps, statuses, and feature identifiers only.

## `MEMCONT-003` - Use Memory Latency And Writer Detach

- Requirement: chat-time saved-memory reads are bounded by `memory.readProfile`, deduped by key,
  do not initialize or await the memory writer on the main response path, and compile the main
  chat plus memory writer onto OpenAI-first provider routing when OpenAI auth exists.
- Escaped regression: a newly stored preference in the middle of an additive value must remain
  visible in a fresh chat with conversation recall disabled; head/tail-only truncation is forbidden.
- Risk covered: the `Use memory` toggle makes TTFT or post-text finalization slow because the app
  injects the full memory store, runs maintenance, retries a broken writer on every chat, leaves
  the live main agent on stale Anthropic provider config, or appends a local-retrieval timeout as a
  model-provider error after a valid assistant answer.
- Preconditions: local runtime with memory enabled and synthetic/public-safe saved-memory rows.
- Steps:
  1. Verify source/runtime config exposes `memory.readProfile` with a global read budget, key order,
     per-key caps, and cache TTL.
  2. Run API tests proving the read path uses `getAllUserMemories`, dedupes duplicates, applies the
     budget, and does not call formatted-memory or maintenance helpers.
  3. Run agent-client tests proving `useMemory()` only reads and `runMemory()` initializes the
     writer lazily after the main response path.
  4. Verify generated runtime config and the live built-in main agent both use the expected
     OpenAI-first provider/model when OpenAI auth is available.
  5. Exercise a real browser chat with memory enabled and compare visible response behavior with
     deep timing/log evidence for `build_messages_use_memory`, `chat_completion_done`, and
     `memory_writer_*`.
  6. Run `bin/viventium memory-dedupe --dry-run --json` and confirm it reports duplicate counts
     without applying changes or printing private identifiers.
- Expected result: the user receives the main answer without waiting for memory writer work; memory
  read prompt content is bounded, duplicate-safe, and public-safe QA records only counts/statuses.
- Forbidden result: a memory-enabled chat injects every saved-memory row, runs deterministic
  maintenance before the main model, awaits the writer during finalization, repeats provider 401
  writer attempts every chat with no degraded state, or shows an Anthropic connected-account
  failure, late local-retrieval timeout, or post-stream finalization failure as a model-provider
  error on a mixed install where OpenAI auth is available.
- Evidence to capture: sanitized test output, visible browser result or limitation, deep timing/log
  phase summary, dedupe dry-run counts, and public-safety scan result.
- Automation: targeted API/client/data-provider/script tests plus real browser QA when an
  authenticated local surface is available.
- Last run: PASS (2026-05-20; read path, detached-writer scheduling, OpenAI-first provider routing,
  and browser-visible scoped retrieval-tail/post-stream-finalization suppression passed).

## `MEMCONT-004` - Ordered Cross-Surface Saved Memory

- Requirement: same-user detached writer turns run FIFO without coalescing; prompt and revision data
  come from one snapshot; set/delete/create use monotonic tombstone revisions; a model-correctable
  storage-policy rejection gets at most one retry only before any write applies; final structured
  failure is never logged as success; Memories panel actions submit the revision they read; audit
  evidence is public-safe.
- Preconditions: dedicated isolated channel and browser QA accounts, memory enabled, synthetic
  marker, and a fixture snapshot of the marker key/revision for cleanup.
- Steps:
  1. Send an explicit synthetic “remember this across future conversations” Telegram turn, followed
     immediately by a second benign turn.
  2. Poll the memory-writer audit and Mongo until the target key revision advances; confirm neither
     turn was dropped and no raw user/conversation/message id appears in the structured audit.
  3. Start a new Chrome conversation with conversation recall isolated/disabled and ask for the
     marker; repeat through a real Modern Playground voice turn.
  4. Create a stale competing write in the harness and confirm it returns a revision conflict while
     preserving the newer value. Restore the pre-run state through the guarded write path.
  5. Delete and recreate a synthetic key, then replay stale set/delete/absent-create operations from
     the pre-delete snapshot. Confirm all conflict and the tombstone remains hidden from GET/prompt
     formatting. Repeat a stale edit/delete and atomic key rename through the Memories API contract.
     Rename onto a hidden tombstone and confirm both rows remain unchanged with a choose-another-key
     response. Replay schema-v2 write-only rollback safely, then prove any v2 delete/mixed snapshot
     fails closed.
  6. Fill the target key close to its configured budget, submit a valid durable fact whose first
     full-key proposal exceeds the limit, and verify either one corrected in-budget write or one
     truthful final structured failure. Confirm there is no retry after a partial batch apply.
- Expected result: the marker is stored once at a newer revision and recalled naturally in new web
  and voice conversations; stale writes and rollback attempts preserve newer user state.
- Forbidden result: queued turns coalesce, delete/recreate resets a revision, a stale panel tab
  bypasses CAS, a storage rejection logs success, an intermediate failed artifact reaches the user,
  a partial batch is replayed, same-thread history is counted as saved-memory proof, or QA leaves the
  synthetic marker behind.
- Evidence: visible Telegram send/reply, Mongo key/revision delta, hashed writer audit, new web answer,
  audible voice plus transcript, persistence after reload, and cleanup confirmation.
- Automation: `memoryWriterCoordinator.spec.js`, packages API memory suites,
  `memory.spec.ts`, Memories route/client conflict suites, and hardener rollback/CAS regressions.
- Last run: PASS-AUTOMATED/PARTIAL 2026-07-20; focused memory/recall API 137/137, complete API
  3,365 pass/19 skip, and data schemas 405 pass/3 skip plus build cover FIFO, bounded correction,
  revision/CAS, delete-recreate tombstones, truthful rename conflicts, schema-v2 rollback safety,
  and cleanup. Dedicated isolated
  channel, browser reload, and audible voice acceptance remain NOT RUN.

## `MEMCONT-005` - Mixed-Corpus Recall On The Current Voice Route

- Requirement: authorized resources share one evidence-based reranker; transcript coverage cannot
  override stronger chat history; the active runtime thread and its prompt are not prior evidence;
  voice finalization must use request-owned state without a controller exception.
- Escaped regression fixture: final-run telemetry must not reference request-local state after its
  scope ends; transcript coverage must not outrank stronger prior-chat evidence; allocated thread
  IDs must not be masked by placeholders; and prompt echoes must not receive an exact-match bonus.
- Preconditions: isolated QA browser account; configured synthetic voice route; conversation recall
  enabled; one synthetic event in a separate fixture conversation; saved memory unchanged.
- Steps:
  1. Enter the synthetic event in one ordinary browser conversation and wait until recall source and
     uploaded digests align.
  2. Start a fresh Modern Playground call and ask it to search earlier conversations for the event's
     people, venue, and marker.
  3. Verify the outbound provider/model/parameters match the configured voice route and that
     `file_search` runs without a controller exception.
  4. Inspect persisted sources: the relevant prior conversation ranks first; unrelated transcripts
     remain below it; the active prompt/current thread is absent as evidence.
  5. Confirm the visible answer, audible delivery, linked-chat detail state, refresh persistence,
     Mongo rows, and runtime logs agree.
  6. Delete only the synthetic conversations/call rows through supported paths, wait for recall
     rebuild, and confirm zero marker state in Mongo, Meilisearch, saved memory, and recall.
- Expected result: the answer contains only the grounded prior-event fields, persists after reload,
  and is audibly delivered through the configured voice route.
- Forbidden result: transcript source-class frontloading; a blended unrelated meeting; the current
  question cited as its own evidence; a pre-provider `ReferenceError`; typed/API-only acceptance;
  provider drift; or synthetic state left behind.
- Evidence: isolated-account browser state, visible transcript and expanded source detail, refresh,
  provider/TTS telemetry, fixture DB/search cleanup, focused Prompt Workbench eval, and the
  file-search plus controller regression suites.
- Automation: `fileSearch.test.js`, `client.test.js`, `feelingsTelemetry.spec.js`, and `voice.spec.js`.
- Last run: PASS-AUTOMATED/PARTIAL 2026-07-14. Focused file-search/controller fixture suites passed
  49/49 and 178/178. Dedicated isolated-account browser detail, audible voice, refresh persistence,
  and runtime DB/search cleanup remain NOT RUN.

## `MEMCONT-006` - Persistence Identity And Three-Gate Recovery

- Requirement: startup must reject a Mongo listener backed by an unexpected data directory; saved
  memory hardening must preserve reviewed writes; recall must preserve the complete bounded primary
  user turn through corpus and result clipping.
- Failure-mode fixture: a listener backed by the wrong data directory must not be accepted as
  healthy; changing listeners must not select an older fixture branch; and post-apply maintenance
  must not immediately recompact a reviewed context write and remove its tail detail.
- Preconditions: two synthetic Mongo data directories with distinct histories; isolated QA user;
  one long user-authored event with important tail detail; memory, recall, Telegram, Chrome, and
  Modern Playground available.
- Steps:
  1. Put a Mongo listener with the wrong `storage.dbPath` on the configured port and verify native
     startup refuses it; repeat with the configured directory and verify startup reuses it.
  2. Build recall from a synthetic long user turn preceded by a long assistant turn. Verify the user
     source ranks first and its important tail survives the final result budget.
  3. Run reviewed nightly-hardener and Prompt Workbench governed proposals while deterministic
     maintenance is due. Verify proposal-written keys and conversation-owned `working` receive no
     same-pass maintenance rewrite, while eligible untouched keys can still be maintained.
  4. Through native Telegram, a new Chrome chat, and real Modern Playground calls, prove saved-memory
     and recall-only recovery separately; inspect persisted tool provenance, transcript/audio, logs,
     Mongo, and vector state.
  5. Restore the isolated QA account from its pre-run snapshot and verify no synthetic residue reaches
     non-QA state or public evidence.
- Expected result: persistence identity cannot drift silently; saved-memory and recall paths each
  recover the full synthetic event and follow-ups; reviewed nightly and Workbench proposals remain
  intact.
- Forbidden result: accepting readiness from port occupancy alone; assistant context clipping out
  the primary user turn; a successful hardener or Workbench governed apply immediately discarding
  its own proposal detail; mocks or same-thread output represented as cross-surface proof.
- Evidence: launcher regressions, recall/hardener suites, synthetic fixture counts, isolated browser
  transcript/audio when run, fixture DB/vector confirmation, and guarded QA cleanup.
- Last run: PASS-AUTOMATED/PARTIAL 2026-07-15; wrong-directory startup, complete-turn clipping, and
  reviewed-apply preservation fixtures pass. Isolated channel/web/voice recovery remains NOT RUN.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Memory Continuity. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `MEMCONT-UC-001` | On browser chat, memory state, restore/continuity checks, verify that saved memory, recall, and continuity state survive restore/upgrade without confusing stale facts for live truth. | owning requirement for `MEMCONT-001` / `MEMCONT-001` | browser chat, memory state, restore/continuity checks | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MEMCONT-001. | User-visible behavior matches source, docs, persisted state, and logs | PASS/PARTIAL 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); dedupe dry-run and focused continuity tests passed, while fresh continuity capture was not run to preserve read-only audit posture |
| `MEMCONT-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `MEMCONT-002` / `MEMCONT-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MEMCONT-002. | The user sees an honest setup, retry, or degraded-state result for MEMCONT-002; no fake success is accepted. | PASS 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)) |
| `MEMCONT-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `MEMCONT-002` / `MEMCONT-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MEMCONT-002. | MEMCONT-002 remains correct after the persistence or parity step and final wording matches evidence. | PASS 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)) |
| `MEMCONT-UC-004` | Turn on memory and send a normal browser chat message with existing saved memories present. | owning requirement for `MEMCONT-003` / `MEMCONT-003` | browser chat, generated runtime config, live built-in agent state, deep timing logs, memory DB state | Source, runtime config, live agent model/provider, logs, tests, saved-memory row counts, and dedupe dry-run output. | Main response is visible on the OpenAI-first route without waiting on memory writer work or showing a post-answer provider error; logs/state show bounded read timing and detached writer timing. | PASS (2026-05-20: QA account browser run returned and persisted a `gpt-5.4` answer with no red local-retrieval tail or post-stream finalization error after wait or reload) |
| `MEMCONT-UC-005` | Run saved-memory/provider-key dedupe as dry-run before enabling unique indexes. | owning requirement for `MEMCONT-003` / `MEMCONT-003` | `bin/viventium memory-dedupe --dry-run --json` | CLI output, DB duplicate counts, public-safety scan | Dry-run reports counts only, applies no writes, and does not print private identifiers. | PASS 2026-06-07 ([repair follow-up](../memory-hardening/reports/2026-06-07-nightly-repair-follow-up.md)); dry-run reported zero duplicate groups/docs/deletes and applied no writes |
| `MEMCONT-UC-007` | Start or upgrade an install whose saved-memory/provider-key collections are either clean or contain synthetic duplicate rows. | owning requirement for `MEMCONT-003` / `MEMCONT-003` | generated runtime environment, launcher, Mongo migration harness | Compiled `MONGO_AUTO_INDEX`, launcher logs, dry-run JSON, index list, row counts | Automatic Mongoose indexing stays off; clean state receives unique indexes, while duplicate state remains unchanged and startup warns how to review it. | PASS 2026-07-11 for compiler, launcher-contract, and synthetic migration regressions; real clean installed-runtime restart remains part of release acceptance |
| `MEMCONT-UC-006` | Tell Viv a synthetic durable fact in an isolated channel, then ask for it in new web and voice conversations. | `20_Memory_System.md` / `MEMCONT-004` | isolated channel, LibreChat, Modern Playground voice | writer audit, fixture revision, prompt frame, transcript/audio, cleanup state | Both new conversations recover saved memory without relying on same-thread history; cleanup preserves non-QA state while removing only the synthetic fact. | PARTIAL 2026-07-14; synthetic writer/revision fixtures pass, but isolated channel-to-web/voice acceptance is NOT RUN |
| `MEMCONT-UC-008` | In a fresh voice call, ask about a synthetic event from an earlier isolated browser conversation while transcript fixtures are also attached. | `32_Conversation_Recall_RAG.md` / `MEMCONT-005` | isolated browser, Modern Playground, linked LibreChat chat | visible/audible answer, expanded file-search sources, provider logs, fixture DB/search state | The prior conversation is the leading source, the current prompt is absent, unrelated transcript evidence is not blended into the answer, and reload preserves the grounded result. | PARTIAL 2026-07-14; focused reranking and controller tests pass, but isolated audible/persistence proof is NOT RUN |
| `MEMCONT-UC-009` | Recover from an unexpected synthetic persistence branch, then ask for one fixture recent event through saved memory and recall-only voice. | `50_Stable_Dev_Runtime.md`, `20_Memory_System.md`, `32_Conversation_Recall_RAG.md` / `MEMCONT-006` | native launcher fixture, isolated channel, browser, Modern Playground | listener `dbPath`, fixture union counts, hardener proposal/apply, recall digest/chunks, transcript/audio, provenance, cleanup | Startup rejects the wrong persistence identity; repaired saved memory and recall independently recover the full event and follow-ups without clipping or post-apply loss. | PARTIAL 2026-07-15; automated failure-mode fixtures pass, isolated cross-surface proof is NOT RUN |
