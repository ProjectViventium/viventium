# Memory Continuity QA Cases

## Case ID Convention

Use stable `MEMCONT-NNN` IDs for memory continuity cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `MEMCONT-001` | Saved memory, recall, and continuity state survive restore/upgrade without confusing stale facts for live truth. | User-visible behavior matches source, docs, persisted state, and logs | browser chat, memory state, restore/continuity checks | `tests/release/test_continuity_audit.py` plus user-grade QA when visible | PASS/PARTIAL 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); current dedupe dry-run found zero duplicate groups/docs/deletes, focused continuity tests passed, and fresh continuity capture was not run because it writes App Support state |
| `MEMCONT-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); public report keeps raw runtime, DB, browser, transcript, memory, token, and account evidence out of the repo |
| `MEMCONT-003` | Chat-time saved-memory reads are bounded, writer work is detached, and OpenAI-first provider routing is honored when OpenAI auth exists. | Turning on memory does not inject the full store, wait on writer maintenance/auth failures, route the main chat through stale Anthropic config, or show a red retrieval-tail/finalization error after a valid answer. | browser chat, generated runtime config, live built-in agent state, deep timing logs, memory DB state, CLI migration | API/unit tests, compiler/source audits, browser QA, log timing review, `bin/viventium memory-dedupe --dry-run` | PASS (2026-05-20: read path, detach tests, OpenAI-first route, scoped retrieval-tail and post-stream finalization suppression, browser QA, restart, and dry-run PASS) |
| `MEMCONT-004` | Detached saved-memory writes are FIFO per user, revision protected across surfaces, and truthful when storage policy rejects a proposal. | A Telegram fact is not dropped by a nearby turn, falsely reported as stored after a budget rejection, or overwritten by stale web/voice/panel/hardener work, and a later new conversation can use it. | Telegram, browser chat, Memories panel, Modern Playground voice, Mongo, memory-writer audit | coordinator, bounded policy-retry, agent-memory, real-Mongo tombstone/CAS, hardener tests plus real cross-surface QA | PASS-LIVE 2026-07-14; native Telegram stored the marker after one bounded correction, new web and voice conversations recovered that identical marker with recall disabled, the linked voice transcript survived reload, and revision-guarded cleanup removed only the synthetic line while preserving intervening user state ([report](reports/2026-07-14-memory-continuity-incident-repair.md)) |
| `MEMCONT-005` | Mixed-corpus conversation recall keeps global evidence order, excludes the active thread, and completes safely through the configured voice route. | A new voice conversation recalls the prior synthetic event without blending an unrelated meeting, citing its own prompt, or failing in final-run telemetry. | owner browser, Modern Playground, linked chat, file-search sources, Mongo, runtime/TTS logs | file-search reranking/exclusion regressions plus agent-controller/feelings/voice suites and real audible QA | PASS-LIVE 2026-07-14; the current xAI route retrieved the earlier conversation first, answered every requested field, persisted and reloaded the linked chat, delivered non-cancelled audio, and left zero synthetic marker/content across persisted and search state after cleanup ([report](reports/2026-07-14-memory-continuity-incident-repair.md)) |
| `MEMCONT-006` | Runtime persistence identity, reviewed memory writes, and recall corpus completeness stay aligned. | Recovery does not silently reopen stale state or truncate the important end of a user's account. | native launcher, Telegram, browser, voice, Mongo/vector state | persistence-identity, hardener, recall, and user-grade recovery checks | PASS-LIVE 2026-07-15; see the detailed case and dated continuity report |
| `MEMCONT-007` | Cognitive evidence is available before behavioral prompting and failures remain honest. | The agent can use bounded saved memory or declared recall without entity-specific prompting. | browser, Telegram, LibreChat, GlassHive, Workbench/integrity state | memory/compiler/provider/provenance and live continuity gates | PASS-AUTOMATED/LIVE 2026-08-09; saved-memory read/write and broker recall pass, while the joined integrity command honestly remains blocked only on unobserved natural schedules. |
| `MEMCONT-008` | Continuity generalizes across fact classes, languages, providers, and weak/absent evidence. | A correct result is not inferred from one memorable entity test, lucky model knowledge, or workspace leakage. | LibreChat web/voice metadata, direct xAI voice route, GlassHive broker | frozen diverse broker matrix, direct-provider matrix, native-tool provenance, corpus-freshness and cleanup gates | PASS-AUTOMATED 2026-08-09: 12/12 GlassHive/main cases passed deterministic required/forbidden/tool contracts with zero retries. Direct xAI 4/4 remains supporting route evidence ([broad matrix](reports/2026-08-09-diverse-continuity-matrix.md)). |
| `MEMCONT-009` | An unavailable host-owned recall capability cannot be impersonated through native filesystem or hidden runtime-state discovery. | When recall is unavailable, the user gets an honest limitation; when enabled, the same product path retrieves through the authorized broker. | authenticated LibreChat UI, GlassHive conversation provider, broker audit | capability/resource-state regression plus paired browser happy/degraded runs and worker-tool provenance | PASS-LIVE 2026-08-08; disabled recall returned an honest limitation with zero broker/native commands, enabled recall returned exact cross-language evidence with one brokered `file_search` and zero native substitution, reload persisted the result, and synthetic state/preferences were cleaned up |
| `MEMCONT-010` | Saved-memory writing and fresh-conversation reading are proven per identity and kept separate from `/host` machine authorization. | Browser and Telegram can recover generic durable facts after conversation reset without sharing owner credentials or relying on same-thread history. | non-admin browser, native Telegram Desktop, connected-account health receipts, Mongo | real Luna writer/read runs, zero-history/reset evidence, exact cleanup, model-bank regressions | PASS-LIVE 2026-08-09; non-admin browser fresh-chat/reload and Telegram `/reset` recovered unrelated generic two-field facts through Luna/medium receipts, and exact synthetic state was removed/restored ([browser report](reports/2026-08-09-live-browser-saved-memory-model-route.md)) |
| `MEMCONT-011` | Saved-memory entry keys never collide with control endpoints. | A user can store, display, update, and remove a memory whose key is `preferences` while memory preferences remain independently configurable. | Memories panel, memory API, data provider, Mongo | route/client contracts plus real browser write/read/panel/reload/cleanup | PASS-LIVE 2026-08-09; the non-admin browser run wrote the ordinary synthetic fact to `preferences`, showed it in Memories, recovered it in a fresh chat, survived reload, used the canonical `/entries/:key` mutation contract, and restored prior state ([browser report](reports/2026-08-09-live-browser-saved-memory-model-route.md)) |
| `MEMCONT-012` | Memory renames can reuse a deleted destination generation without hiding read failures. | A deleted target key cannot permanently poison rename, and an unavailable memory store is never presented as an empty memory. | Memories UI/API/persistence, main Agent initialization, background cortex | real-Chrome disposable-user rename, real-Mongo tombstone/CAS test, main/background degraded-context tests | PASS-LIVE/AUTOMATED 2026-08-09; the Memories Edit dialog renamed into a deleted destination, preserved a monotonic revision after reload with zero console errors, and fully removed the disposable user state ([browser report](reports/2026-08-09-live-browser-tombstone-rename.md)). Access-check/load failures separately emit an explicit unavailable boundary instead of silent empty context. |
| `MEMCONT-013` | A configured model fallback remains useful and visible instead of silently impersonating the failed primary route. | The user receives the fallback answer plus an expandable disclosure that survives reload. | non-admin LibreChat browser, Agent runtime, message persistence | initialization/runtime fallback tests, sequential-pruning regression, real-browser forced-primary-failure QA | PASS-LIVE/AUTOMATED 2026-08-09; a disconnected primary route failed, the configured fallback answered, “Model fallback used” and its reason were visible and expandable, reload preserved both, persistence contained the structural event, zero console errors occurred, and fixtures were removed ([browser report](reports/2026-08-09-live-browser-fallback-disclosure.md)). |

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
- Preconditions: authenticated local Telegram and Chrome surfaces, memory enabled, synthetic marker,
  and a pre-run snapshot of the marker key/revision for cleanup.
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
- Last run: PASS-LIVE 2026-07-14; the native pre-repair journey reproduced a near-full-key
  rejection and false-success log with no revision advance. After repair, a new native Telegram
  write hit the same rejection, made exactly one bounded correction, applied a 471-token replacement,
  advanced the key revision from zero to one, and emitted a structured applied-write audit followed
  by `memory_run_done status=ok`. A brand-new owner-browser conversation with recall disabled
  recovered the exact synthetic marker and retained it after reload. A fresh owner-profile Modern
  Playground turn then asked for that identical Telegram-written marker with recall disabled. The
  visible answer was exact, the prompt frame contained saved-memory context and no conversation
  recall, the model made zero tool calls, xAI returned HTTP 200 on `grok-4.3` with
  `reasoning_effort=none`, and 1.57 seconds of non-cancelled xAI audio was delivered. The exact
  prompt and answer remained present after loading the linked conversation URL again. Cleanup used
  the current memory revision, removed exactly one synthetic line, preserved 34 legitimate Telegram
  messages, deleted only QA call/accounting rows, and rebuilt 798 recall chunks with zero marker
  occurrences ([report](reports/2026-07-14-memory-continuity-incident-repair.md)).

## `MEMCONT-005` - Mixed-Corpus Recall On The Current Voice Route

- Requirement: authorized resources share one evidence-based reranker; transcript coverage cannot
  override stronger chat history; the active runtime thread and its prompt are not prior evidence;
  voice finalization must use request-owned state without a controller exception.
- Escaped regression: a real current-route voice call first crashed before the provider because
  final-run Feelings telemetry referenced method-local state outside its scope. After that was
  corrected, the model called `file_search` but received an unrelated meeting transcript ahead of
  the stronger prior-chat event, while a `new` placeholder could mask the allocated thread id and an
  exact prompt echo received an exact-match bonus.
- Preconditions: authenticated owner Chrome profile; configured current voice route; conversation
  recall enabled; one synthetic natural event in a separate conversation; saved memory unchanged.
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
- Evidence: owner-profile browser state, visible transcript and expanded source detail, refresh,
  xAI provider/TTS telemetry, Mongo/Meilisearch/recall cleanup, focused Prompt Workbench eval, and
  the file-search plus controller regression suites.
- Automation: `fileSearch.test.js`, `client.test.js`, `feelingsTelemetry.spec.js`, and `voice.spec.js`.
- Last run: PASS-LIVE 2026-07-14. A fresh current-route call used xAI Chat Completions on
  `grok-4.3` with `reasoning_effort=none`, called `file_search`, ranked the prior conversation before
  transcript evidence, returned every synthetic event field, persisted the tool detail and answer,
  and remained correct after a linked-chat refresh. Chrome emitted audible playback and xAI streamed
  11.53 seconds of non-cancelled audio. Focused tests passed 49/49 and 178/178; cleanup left zero
  synthetic conversations, messages, call sessions, transactions, saved-memory value matches, or
  search-index documents. The saved-memory edit left zero tombstones, with recall enabled and
  source/upload digests aligned.

## `MEMCONT-006` - Persistence Identity And Three-Gate Recovery

- Requirement: startup must reject a Mongo listener backed by an unexpected data directory; saved
  memory hardening must preserve reviewed writes; recall must preserve the complete bounded primary
  user turn through corpus and result clipping.
- Escaped regression: a restored Mongo listener occupied the canonical port and was accepted as
  healthy. When that listener stopped, local prod reopened an older canonical data directory. Saved
  memory and recall had both processed the newer branch correctly, but the active runtime could no
  longer see those artifacts. During repair, generic post-apply maintenance also re-compacted a
  freshly reviewed context write and removed its follow-up detail.
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
     the owner account or public evidence.
- Expected result: persistence identity cannot drift silently; saved-memory and recall paths each
  recover the full synthetic event and follow-ups; reviewed nightly and Workbench proposals remain
  intact.
- Forbidden result: accepting readiness from port occupancy alone; assistant context clipping out
  the primary user turn; a successful hardener or Workbench governed apply immediately discarding
  its own proposal detail; mocks or same-thread output represented as cross-surface proof.
- Evidence: launcher regressions, recall/hardener suites, redacted hardener counts, real Chrome voice
  transcript and delivered audio, native Telegram persistence, Mongo/vector confirmation, and
  guarded QA cleanup.
- Last run: PASS-LIVE 2026-07-15; wrong-directory startup failed closed, repaired history produced a
  full recall corpus, saved-memory and recall-only web/Telegram/voice journeys recovered the complete
  synthetic event, and both reviewed apply paths preserved proposal-written keys without a same-pass
  rewrite. Owner recovery and final QA cleanup are recorded in the dated public-safe report.

## `MEMCONT-007` - Cognitive Availability Before Behavioral Prompting

- Requirement: `docs/requirements_and_learnings/01_Key_Principles.md` and
  `docs/requirements_and_learnings/20_Memory_System.md`.
- Risk covered: a durable fact exists but is clipped from the bounded memory frame, so the agent is
  blamed for failing to infer context it never received and a prompt-specific curiosity rule is
  proposed as a false fix.
- Steps:
  1. Place a synthetic durable fact near the former memory-read boundary and start a fresh turn.
  2. Verify whole-entry selection, explicit omission metadata, and the compiled 8,000-token ceiling.
     Exercise both a real-tokenizer value whose character estimate exceeds its cap and a single
     oversized unpunctuated value; the first remains whole and the second retains bounded head/tail.
  3. Exercise the same fact through a route whose provider needs brokered `file_search` fallback.
  4. Inspect runtime config, prompt drift, hardener health, and exact worker tool provenance.
- Expected result: the relevant fact is available through bounded saved memory or declared recall;
  if retrieval is degraded, the agent is told that the result is inconclusive rather than absent.
- Forbidden result: a branch on the entity or prompt wording, silent partial-entry clipping,
  invented tool availability, or claiming that an unretrieved fact does not exist.
- Last run: PASS-AUTOMATED/LIVE 2026-08-08. Memory/compiler/cognitive-integrity regressions passed;
  the provider-backed live recall gate recovered a nonce-isolated fact through brokered
  `file_search` with zero native command/dynamic-tool/web-search/file-change substitutions. A fresh
  Test Account browser turn then loaded 4,218 saved-memory tokens across all nine governed keys,
  rendered the truthful writer-reconnect detail, and persisted both answer and detail after reload.
  A native Telegram turn loaded 4,802 tokens across the same nine keys and preserved the established
  relationship while staying uncertain about an unverified detail; server completion was 7.9 s and
  the visible round trip was 12.4 s. A stricter native Telegram identity turn later exposed that
  conversation-mode workers received the signed broker but not its service-backed-resource routing
  guidance in developer authority. After repairing that structural seam, the retry verified the
  relationship from earlier-conversation evidence through one broker `file_search`, with zero
  native commands or runtime errors; the correlated provider run completed in 17.2 s. The final
  nonce-isolated provider gate repeated the same provenance contract in 15.2 s. See the
  [cognitive-continuity repair report](reports/2026-08-08-cognitive-continuity-capability-repair.md).

## `MEMCONT-008` - Diverse Continuity And Provider Parity

- Requirement: `docs/requirements_and_learnings/32_Conversation_Recall_RAG.md` and the Viventium
  outcome metric in `AGENTS.md`.
- Risk covered: a single named-entity success is mistaken for proof of general cognitive continuity;
  semantic misses, stale fixtures, provider routing differences, or worker transport races remain
  hidden.
- Steps:
  1. Insert isolated synthetic earlier-conversation evidence for relationship/role, preference,
     project state, a later correction, exact date/time/place, an exact numeric value, distractor
     disambiguation, and a cross-language paraphrase. Include an absent-evidence case.
  2. Wait until the recall source and uploaded corpus digests match before grading retrieval.
  3. Exercise every frozen continuity category through the GlassHive conversation-provider path
     using both web and voice surface metadata. Require the brokered `file_search` result and reject
     native evidence substitution; unrelated scoped context reads are not substitution.
  4. Independently exercise preference, time, number, and multilingual cases through the direct xAI
     voice route. Prove native `file_search` start/completion events and the configured provider.
  5. Restore the original recall preference and remove all synthetic conversations/messages. Keep
     raw evidence private; publish only hashes, counts, statuses, and sanitized errors.
- Expected result: required current evidence is present, superseded/distractor evidence is absent,
  absent evidence is not invented, exact requested tokens survive, both provider paths retrieve
  through their declared tools, and cleanup is verified.
- Forbidden result: an entity- or phrase-specific instruction, same-thread history, stale vector
  grading, model-only guessing, local workspace search as answer evidence, or retrying until a failed
  result disappears from the record.
- Last run: PASS-AUTOMATED 2026-08-09. The frozen GlassHive/main matrix passed 12/12 in one
  attempt per case; every case was nonce-bound with a negative control, semantic cases required
  fresh retrieval, and every broker case required zero native commands. The independent direct xAI
  matrix passed 4/4 after activation. Earlier runs exposed both a non-atomic heartbeat read and a correct multilingual
  answer preceded by an unauthorized native-shell discovery attempt; both failures remain in the
  RCA rather than being erased.

## `MEMCONT-009` - Unavailable Recall Must Not Become Filesystem Recall

- Requirement: host-owned evidence is accessible only through the authorized capability/resource
  projection for the current turn. Full-access workstation tools remain available for legitimate
  project work, but they are not an alternate path into app state, conversation exports, caches,
  logs, backups, hidden runtime folders, or unrelated workspace copies.
- Escaped regression: an authenticated browser query produced the exact synthetic answer even though
  the QA account had conversation recall disabled and the worker received no brokered `file_search`.
  The worker used eight native shell commands and found the marker in private runtime state. The
  visible answer was correct, but its evidence path was invalid.
- Steps:
  1. With recall disabled, create an isolated synthetic fact in one ordinary browser conversation
     and ask for it from a new conversation in another language.
  2. Require an honest limitation and correlate the exact GlassHive run: zero broker calls, zero
     native commands, and zero evidence substitution.
  3. Enable recall for the same QA account, create a different synthetic fact class in a separate
     conversation, wait for the authorized corpus to refresh, and ask cross-language from a new
     conversation.
  4. Require the exact answer, one completed brokered `file_search`, zero native commands, zero
     evidence substitution, visible harness activity, and persistence after reload.
  5. Delete only the synthetic conversations through the supported UI and restore the original
     recall preference.
- Expected result: unavailable recall is transparent and non-invasive; enabled recall is exact and
  provenance-backed. The behavior is determined by structured capability/resource state, not an
  entity name, prompt phrase, provider label, or account identity.
- Forbidden result: guessing, claiming recall ran when it did not, or mining application/private
  runtime state to simulate a missing host capability.
- Last run: PASS-LIVE 2026-08-08. Disabled path: honest Spanish limitation, 6.7 s server-side,
  zero broker calls, zero native commands, zero substitution. Enabled path: exact alias and numeric
  value in Spanish, 13.2 s server-side, one completed broker `file_search`, zero native commands,
  zero substitution, visible activity detail, and persisted reload. All six browser fixtures were
  deleted and the QA account's original disabled preference was restored. A separate Telegram
  Desktop run first proved that the browser QA and Telegram identities were different, then seeded
  the same synthetic class under the Telegram-mapped identity: the corrected turn returned the
  exact alias and number in 15.0 s with one broker call, zero native commands/substitution, and
  cleanup refreshed both affected identity corpora.

## `MEMCONT-010` - Account-Scoped Saved Memory Across Fresh Conversations

- Requirement: saved-memory read/write health is scoped to the signed-in Viventium identity. A
  connected GlassHive `/host` worker is machine/operator authorization and must neither substitute
  for nor silently receive a LibreChat user's connected-account credentials.
- Steps:
  1. Snapshot the selected non-admin QA identity's memory values and revisions privately.
  2. With conversation recall disabled, store a generic synthetic two-field fact through the real
     browser and confirm the immediate-writer receipt selects the configured model.
  3. Recover it in a fresh conversation, reload, and confirm visible answer, read receipt, and DB
     state agree.
  4. Repeat with a different generic fact through native Telegram Desktop. Send `/reset`, prove the
     new backend conversation has zero messages, and ask for both fields without restating them.
  5. Remove exact synthetic conversations/worker records and restore only the snapshotted memory
     revisions, failing closed on concurrent user changes.
- Expected result: both surfaces recover account-scoped saved memory after a true conversation
  boundary; writer/read receipts expose provider/model/status without raw memory or identifiers.
- Forbidden result: treating `/host` as the user's OAuth account, copying credentials across
  identities, same-thread context as memory proof, or a fact/entity-specific prompt rule.
- Last run: PASS-LIVE 2026-08-09. Browser and Telegram both passed through OpenAI/Luna; the Telegram
  recovery conversation had zero prior messages, and cleanup restored all governed keys without
  removing intervening user state.

## `MEMCONT-013` - Visible Model Fallback Recovery

- Requirement: a main-model fallback is a truthful recovery boundary, not a hidden provider swap.
- Steps:
  1. Create a disposable non-admin-owned Agent whose primary connected-account route is unavailable
     and whose configured fallback route is healthy.
  2. Send one ordinary browser turn and require the fallback to return the requested answer.
  3. Inspect and expand the visible fallback disclosure, then reload the conversation.
  4. Correlate the visible state with the persisted structural `fallback-recovery` part and remove
     the disposable Agent, ACL entries, conversation, messages, and session.
- Expected result: the answer remains useful, “Model fallback used” and the reason are visible, and
  answer plus disclosure survive reload.
- Forbidden result: a silent fallback, disclosure removed by sequential-output pruning, a false
  primary-success claim, or QA fixture residue.
- Last run: PASS-LIVE/AUTOMATED 2026-08-09. Real Chrome proved failed primary, fallback answer,
  expandable disclosure, persistence/reload, zero console errors, and exact cleanup; focused API
  fallback/pruning tests passed 34/34.

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
| `MEMCONT-UC-006` | Tell Viv a synthetic durable fact in Telegram, then ask for it in new web and voice conversations. | `20_Memory_System.md` / `MEMCONT-004` | real Telegram, Chrome LibreChat, Modern Playground voice | writer audit, Mongo revision, prompt frame, transcript/audio, cleanup state | Both new conversations recover saved memory without relying on same-thread history; cleanup preserves current user state while removing only the synthetic fact. | PASS-LIVE 2026-07-14; Telegram persisted the marker after one bounded correction, fresh web and voice conversations both recovered that exact marker with recall disabled and no retrieval call, the linked voice transcript survived reload, and guarded cleanup removed only the synthetic line while preserving current memory and legitimate Telegram history |
| `MEMCONT-UC-008` | In a fresh voice call, ask about a synthetic event from an earlier browser conversation while meeting transcripts are also attached. | `32_Conversation_Recall_RAG.md` / `MEMCONT-005` | owner Chrome, Modern Playground, linked LibreChat chat | visible/audible answer, expanded file-search sources, provider logs, Mongo/Meilisearch/recall state | The prior conversation is the leading source, the current prompt is absent, unrelated transcript evidence is not blended into the answer, and reload preserves the grounded result. | PASS-LIVE 2026-07-14; current xAI voice route, file-search detail, audible TTS, persistence, backend logs, DB/search state, and cleanup all agreed |
| `MEMCONT-UC-009` | Recover from an unexpected local Mongo persistence branch, then ask for one synthetic recent event through saved memory and recall-only voice. | `50_Stable_Dev_Runtime.md`, `20_Memory_System.md`, `32_Conversation_Recall_RAG.md` / `MEMCONT-006` | native launcher, QA Telegram transport, owner-profile Chrome, Modern Playground | listener `dbPath`, union counts, hardener proposal/apply, recall digest/chunks, visible transcript/audio, DB/tool provenance, cleanup | Startup rejects the wrong persistence identity; repaired saved memory and recall independently recover the full event and follow-ups without clipping or post-apply loss. | PASS-LIVE 2026-07-15; see dated memory-continuity report |
| `MEMCONT-UC-010` | Ask fresh conversations for different kinds of prior facts, including a correction, exact number/date, distractor, absent fact, ordinary operational wording, injection/noise, and a cross-language paraphrase. | `32_Conversation_Recall_RAG.md` / `MEMCONT-008` | GlassHive-backed main route plus direct voice-provider route | required/forbidden fragments, tool events, worker audit, source/upload digest, cleanup state | Both routes retrieve authorized evidence through declared tools, preserve requested literal spans, prefer corrected/current evidence, and do not invent an absent fact. | PASS-AUTOMATED 2026-08-09; latest GlassHive/main matrix passed 12/12 deterministic required/forbidden/tool contracts with zero retries. The post-activation direct xAI matrix passed 4/4 with preference restoration and exact cleanup. |
| `MEMCONT-UC-011` | Ask for a prior fact from a new browser chat once with recall disabled and once with recall enabled. | `32_Conversation_Recall_RAG.md` / `MEMCONT-009` | authenticated LibreChat UI and GlassHive-backed main route | visible answer, expanded activity, exact worker run, broker/native tool audit, reload, cleanup/preferences | Disabled recall states the limitation without searching hidden state; enabled recall uses the broker, returns exact evidence, and persists. | PASS-LIVE 2026-08-08; paired disabled/enabled browser runs and run-correlated tool audits passed with zero native substitution |
| `MEMCONT-UC-012` | Ask from Telegram Desktop for a synthetic fact stored under the same mapped Viventium identity. | `32_Conversation_Recall_RAG.md` / `MEMCONT-009` | native Telegram Desktop, Telegram bridge, GlassHive broker | identity mapping, corpus digest, visible text/audio, exact worker run and tool audit, cleanup | Cross-surface QA fails closed when identities differ; after same-identity setup, Telegram retrieves through the broker without native substitution. | PASS-LIVE 2026-08-08; the intentional mismatched-identity run was honestly inconclusive, while the same-identity rerun returned exact evidence with one broker call and zero native commands |
| `MEMCONT-UC-013` | Store a generic durable fact, reset/start a fresh conversation, and ask for it without repeating it in browser and Telegram. | `20_Memory_System.md` / `MEMCONT-010` | non-admin browser and native Telegram Desktop | visible answer/reload, zero-history boundary, Luna writer/read receipts, Mongo revisions, exact cleanup | Both surfaces recover the account-scoped fact without same-thread history, recall, host credential substitution, or entity-specific prompting. | PASS-LIVE 2026-08-09; both routes recovered distinct two-field fixtures and exact cleanup restored the pre-test memory state. |
| `MEMCONT-UC-014` | Store and edit a saved memory whose key matches a settings control name, then reload and ask for it in a fresh chat. | `20_Memory_System.md` / `MEMCONT-011` | non-admin browser, Memories panel, fresh chat | visible card, canonical entry route, API status, memory revision, reload, exact cleanup | The entry is edited as memory, never routed to the preferences controller; settings remain intact and the fresh answer uses the saved fact. | PASS-LIVE 2026-08-09; `preferences` entry was visible and usable after reload, and prior memory/preferences state was restored. |
| `MEMCONT-UC-015` | Send a normal turn when the configured primary model route is unavailable but its fallback is healthy. | runtime fallback contract / `MEMCONT-013` | non-admin LibreChat browser | visible answer, expanded disclosure, reload, persisted message part, console, cleanup | The fallback answer is delivered with an honest expandable disclosure that survives reload. | PASS-LIVE 2026-08-09; real Chrome, persistence, console, and cleanup all agreed. |
