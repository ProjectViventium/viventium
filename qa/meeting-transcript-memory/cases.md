# Meeting Transcript Memory QA Cases

Living regression cases for local transcript ingestion, summary-only RAG, and runtime recall.
Use synthetic transcript fixtures and public-safe placeholders only.

## MTM-001: Chat Input Cap Must Not Drop Transcript Lifecycle

- Scenario: A user has new local transcript files and a large chat lookback that exceeds the memory
  hardener full-lookback input cap.
- Expected outcome: Chat memory writes are blocked, but already generated transcript summaries and
  stale transcript vector lifecycle actions remain in the private proposal for apply.
- Forbidden result: The run returns `input_cap_exceeded` and discards transcript vector uploads or
  deletes after feeding transcript text to the model.
- Evidence to capture: redacted run summary, `chars_fed_to_model`, transcript proposal count, no
  accepted stable-memory operations.
- Last run: 2026-05-12, automated regression passed in
  `api/test/scripts/viventium-memory-hardening.test.js`.

## MTM-002: Meeting Transcript Result Names Must Be Stable

- Scenario: Runtime file search returns a meeting transcript summary whose vector metadata source is
  an internal temporary upload name.
- Expected outcome: The model-visible `File:` label and source artifact use the stable LibreChat
  file name, while transcript provenance headers preserve original filename, mtime, artifact ID,
  source status, and calendar match when available.
- Forbidden result: The assistant sees or cites internal temporary source names instead of the
  stable summary artifact name.
- Evidence to capture: file_search formatted output and source artifact.
- Last run: 2026-05-12, automated regression passed in
  `api/test/app/clients/tools/util/fileSearch.test.js`.

## MTM-003: Source Folder Sidecars Must Not Pollute Meeting Recall

- Scenario: The configured transcript folder contains downloader bookkeeping files alongside real
  transcript files.
- Expected outcome: Product behavior is explicit: either the folder is documented as
  transcript-artifacts-only, or configurable ignore rules prevent known bookkeeping sidecars from
  being summarized as meetings.
- Forbidden result: Assistant answers include index/log files as if they were meeting transcripts.
- Evidence to capture: redacted transcript scan counts and model-visible recall output.
- Last run: PASS 2026-07-11
  ([owner import report](reports/2026-07-11-owner-private-transcript-import-and-recall.md)); six
  configured sidecars were ignored, eight meeting files were processed, and the final index
  contained no underscore-prefixed sidecar artifact.

## MTM-004: Broad Recent-Transcript Questions Need Inventory Coverage

- Scenario: The user asks for a recent transcript/conversation inventory rather than a narrow topic
  lookup.
- Expected outcome: The assistant can enumerate processed transcript summaries at a useful level,
  then answer with transcript caveats. For narrow follow-up questions, focused transcript summary
  hits should outrank the broad inventory when they are clearly more relevant. The inventory body
  contains meeting title/date/participants/context, not artifact IDs, stable file IDs, content
  hashes, or source-folder hashes.
- Forbidden result: Semantic search returns only a few high-scoring chunks, causing the answer to
  imply incomplete visibility over the processed transcript set.
- Evidence to capture: file_search tool calls, retrieved sources, and final assistant answer.
- Last run: PASS 2026-07-11
  ([owner import report](reports/2026-07-11-owner-private-transcript-import-and-recall.md)); the
  focused metadata retrieval regression and all 12 transcript evals passed, and live browser recall
  placed the exact matching summary first while retaining inventory context.

## MTM-005: Failed Hardening Runs Must Leave Redacted Failure Evidence

- Scenario: The memory-hardening/transcript-ingest command fails before a normal summary can be
  written, for example because Mongo configuration is absent or a model call times out.
- Expected outcome: The run directory contains `summary.json`, `failure.redacted.json`, and
  `run-log.redacted.jsonl` with phase, reason, error class/status/timeout when available, and
  redacted message hash/preview.
- Forbidden result: Empty run directories or generic failures that cannot explain where the run
  failed.
- Evidence to capture: redacted failure artifact and status output counts.
- Last run: 2026-05-12, automated regression passed in
  `api/test/scripts/viventium-memory-hardening.test.js`.

## MTM-006: Live RAG Runtime Must Be Proven Before Browser Recall Signoff

- Scenario: Mongo file rows say meeting transcript artifacts exist, but the local RAG/PGVector
  runtime is unhealthy or has been rebuilt.
- Expected outcome: QA checks RAG health before browser signoff, repairs or re-seeds scoped QA
  transcript vectors, and records whether only synthetic QA artifacts or broader transcript repairs
  were verified.
- Forbidden result: Browser QA claims transcript recall works while RAG is down, while vector rows
  are missing, or after a derived vector rebuild without a scoped repair/reseed.
- Evidence to capture: redacted RAG health, primary QA count unchanged check, QA-account source counts,
  file_search source attachments, and public-safe recovery note.
- Last run: PASS 2026-07-11
  ([owner import report](reports/2026-07-11-owner-private-transcript-import-and-recall.md)); QA found
  the vector API process alive without its PGVector dependency, restored only the missing declared
  dependency, completed two bounded transcript-only repair batches, proved all eight new summaries
  with direct authenticated document checks, and then passed browser source-card and persistence QA.

## MTM-007: Chronological Recent Transcript Summary Must Use Inventory Context

- Scenario: After `Ingest Meeting Transcripts` or the equivalent on-demand hardener path has
  processed new transcript summaries, the user asks: "list my recent conversations based on
  transcripts chronologically and give me a 5 line summary based on the actual context."
- Expected outcome: The assistant uses `file_search`, retrieves the meeting transcript inventory,
  lists the processed transcript entries in the requested chronological order, includes visible
  date/time, participants, and one-line meeting context for each entry, and adds a transcript
  caveat line. In a copied QA account that also contains real transcript memories, it is acceptable
  and preferred for the assistant to identify synthetic QA fixtures as synthetic and exclude them
  from the user's real recent-transcript timeline, as long as focused fixture prompts can still
  retrieve the fixture details.
- Forbidden result: The answer relies on only a few semantic summary chunks, omits known processed
  transcripts from the current source folder, loses who/when/context, or treats transcript-only
  statements as durable user beliefs.
- Evidence to capture: visible browser answer, file_search tool call, inventory source count,
  source-backed inventory payload, answer-shape checks, and primary QA account untouched check.
- Last run: 2026-05-13, executable eval and live browser QA passed in
  `qa/meeting-transcript-memory/evals/run-evals.cjs` and
  `qa/meeting-transcript-memory/reports/2026-05-13-transcript-recall-repair-live-qa.md`.

## MTM-008: Active Prompt Echo Must Not Become Recall Evidence

- Scenario: A broad transcript question is saved as the latest user message while source-only
  conversation recall is also attached.
- Expected outcome: The active user prompt is excluded from source-backed recall rescue even when
  current conversation metadata is unavailable, and transcript evidence remains available.
- Forbidden result: The assistant cites the user's just-submitted prompt as conversation recall
  evidence for the answer.
- Evidence to capture: source attachment IDs/content checks and final answer shape.
- Last run: 2026-05-13, automated regression passed in
  `api/test/app/clients/tools/util/fileSearch.test.js` and live QA passed in
  `qa/meeting-transcript-memory/reports/2026-05-13-transcript-recall-repair-live-qa.md`.

## MTM-009: Transcript Sources Must Lead Broad Transcript Answers

- Scenario: Meeting transcript inventory/summary evidence and conversation recall evidence both
  match a broad transcript inventory question.
- Expected outcome: Model-visible output and persisted citation attachments list meeting transcript
  summary/inventory sources before conversation recall, and source-only recall rescue is skipped
  once transcript evidence is present.
- Forbidden result: Older chat or QA prompts outrank transcript inventory/summary evidence and
  steer the answer away from the processed transcript corpus.
- Evidence to capture: model-facing `File:` order, stored source order, and visible source cards.
- Last run: 2026-05-13, automated regressions passed in
  `api/test/app/clients/tools/util/fileSearch.test.js`,
  `api/test/services/Files/processFileCitations.test.js`, and live QA passed in
  `qa/meeting-transcript-memory/reports/2026-05-13-transcript-recall-repair-live-qa.md`.

## MTM-010: Stale Hardening Lock Must Not Block Recovery

- Scenario: A prior memory-hardening process exits without removing its local lock directory, and a
  later manual transcript ingest or dry-run starts.
- Expected outcome: If the recorded lock PID is no longer alive, the hardener clears the stale lock,
  acquires a fresh lock, runs normally, and removes the lock after completion. Very old locks also
  recover even if the PID has been recycled to an unrelated process.
- Forbidden result: A dead PID permanently blocks transcript ingest until an operator manually
  edits local state.
- Evidence to capture: stale-lock fixture, dry-run exit status, run summary, and post-run lock
  absence.
- Last run: 2026-05-13, automated regressions passed in
  `api/test/scripts/viventium-memory-hardening.test.js`; live primary QA dry-run completed with 0
  transcript characters fed to the model.

## MTM-011: Model Candidate Fallback Must Be Configurable And Observable

- Scenario: The preferred transcript summarization/hardening model is unavailable, overloaded, rate
  limited, or not present in the local CLI account.
- Expected outcome: The hardener tries the configured ordered candidate list, defaults to Claude
  Opus 4.7 `xhigh`, the Claude Code `opus` alias `xhigh`, OpenAI GPT-5.5 `high`, then OpenAI
  GPT-5.4 `high`, and records redacted attempt reason/status/timeout metadata.
- Forbidden result: The run silently remaps to a different model, fails on the first unavailable
  model despite a configured fallback, or logs raw transcript/prompt text.
- Evidence to capture: redacted model-attempt telemetry and selected provider/model/effort.
- Last run: 2026-05-22, owner-scoped apply run selected Claude Code `claude-opus-4-7`
  `xhigh`, recorded the default fallback candidate list, and completed with 1 successful model
  attempt and 0 model-attempt failures.

## MTM-012: Model Probe Must Not Be A False Hard Failure

- Scenario: A short model probe times out or the provider is temporarily overloaded, but the real
  fallback candidate path may still be usable.
- Expected outcome: Probe attempts are short and visible in telemetry; by default they are
  advisory and can select a healthy candidate, while `VIVENTIUM_MEMORY_HARDENING_REQUIRE_MODEL_PROBE`
  is the only hard-gate mode.
- Forbidden result: A scheduled or manual transcript ingest fails before scanning/summarizing only
  because an advisory probe timed out.
- Evidence to capture: probe timeout value, attempt reasons, selected candidate, and run status.
- Last run: 2026-05-22, owner-scoped apply run recorded a 30s advisory probe, selected a healthy
  candidate, and completed the transcript run instead of failing at probe time.

## MTM-013: Inconclusive Vector Presence Checks Must Not Cause Destructive Repair

- Scenario: Mongo contains processed transcript artifacts, but the vector-presence check itself
  errors because the vector runtime is transiently unreachable or rejects the check.
- Expected outcome: The run records redacted vector-presence error telemetry, avoids stale deletes,
  and does not mark processed content missing unless the vector store definitively reports absence.
- Forbidden result: A transient presence-check error causes bulk reprocessing, deletes current
  transcript artifacts, or lets the assistant claim no transcript evidence exists.
- Evidence to capture: vector-presence error count/reasons, content hashes requeued, stale-artifact
  count, and follow-up health check.
- Last run: PASS 2026-07-11
  ([owner import report](reports/2026-07-11-owner-private-transcript-import-and-recall.md)); one
  bounded repair batch recorded inconclusive vector-presence checks without destructive repair, the
  next batch recorded zero presence errors, and direct checks proved all eight target summaries.

## MTM-014: Live Browser QA Must Select A Real Connected QA Account

- Scenario: Multiple local non-owner accounts exist, including empty synthetic accounts and a copied
  QA account with provider credentials/memories.
- Expected outcome: The live browser QA harness uses an explicit QA account when supplied, otherwise
  selects a non-owner account with provider credential rows and enough local state; it fails before
  seeding artifacts when no such QA account exists.
- Forbidden result: The harness picks an empty synthetic account, seeds artifacts, then fails later
  with an avoidable `401 invalid_api_key` or claims transcript recall is broken because auth was
  absent.
- Evidence to capture: public-safe QA account hash, provider-credential row count, owner-unchanged
  guard, visible browser answer, and source attachments.
- Last run: 2026-05-22, live browser QA auto-selected the connected non-owner QA clone, detected
  9 provider-credential rows, kept the owner transcript count unchanged, and passed all browser
  transcript-recall checks.

## MTM-015: Transcript-Only Identity Or Person-Role Misattribution Must Not Enter Stable Memory

- Scenario: A meeting transcript or detailed transcript summary contains ambiguous first-person
  language, unreliable speaker attribution, or collapsed speaker labels, and the hardener proposes a
  durable employer/role/identity fact for the user based only on transcript or Listen-Only evidence.
- Expected outcome: Single-transcript evidence may write meeting-scoped `context` or `moments`.
  Transcript-only or ambient-only evidence is rejected for stable durable keys (`core`, `me`,
  `preferences`, `world`, `signals`) unless there is user-authored chat corroboration. Assistant
  restatements do not count as corroboration. A user correction in normal chat can corroborate and
  correct the durable memory.
- Forbidden result: Two transcript artifacts, two ambient sources, assistant restatements, or broad
  project-topic overlap promote stable durable memory without user-authored chat evidence for that
  exact claim.
- Evidence to capture: validator rejection reason, accepted chat-corroborated correction path,
  transcript summary diarization caveat, sanitized incident notes, and live browser answer showing
  the corrected memory is used instead of the stale transcript-derived claim.
- Last run: 2026-05-22, automated validator/eval regressions passed and owner-scoped browser QA
  showed the corrected saved-memory answer; see
  `qa/meeting-transcript-memory/reports/2026-05-22-transcript-identity-misattribution-qa.md`.

## MTM-016: Transcript Summaries Use Reference Context Without Importing Unsupported Facts

- Scenario: A transcript uses ambiguous names, collapsed speakers, or project jargon while current
  saved memory and recent chat contain relevant corrections or boundary context.
- Expected outcome: The summarizer prompt includes bounded `reference_context` with saved-memory
  keys and recent messages by role. The summary uses that context only to disambiguate or flag
  uncertainty; it does not add facts that the transcript itself does not support.
- Forbidden result: Runtime code uses content regex/keyword matching, or the summary silently turns
  reference-only facts into transcript facts.
- Evidence to capture: prompt snapshot/eval output showing `reference_context`, no unsupported fact
  import, and no content-specific runtime heuristic.
- Last run: 2026-05-22, prompt/unit regression passed in the LibreChat memory-hardening Jest suite
  and real QA summarizer isolation passed in
  `qa/meeting-transcript-memory/reports/2026-05-22-reference-context-isolation-qa.md`.

## MTM-017: Historical Transcript Backfill Is Bounded And Resumable

- Scenario: Existing processed summaries become stale because the transcript summarizer prompt
  version changes, or a user installs Viventium with many existing transcript files.
- Expected outcome: `ingest-transcripts` defaults to zero saved-memory changes, processes a bounded
  number of pending files, writes processed content state by hash, uploads summary/inventory vectors
  on apply, and can repeat with `--apply --until-caught-up` until no files are skipped by the batch
  cap. Dry-run caught-up loops are rejected because they cannot persist progress.
- Forbidden result: A single giant all-history hardener prompt/model call is required to make
  historical summaries current, or the status-bar transcript ingest mutates stable saved memory by
  default.
- Evidence to capture: redacted run summaries across at least one capped batch, transcript index
  processed counts by prompt version, vector upload counts, and no durable memory writes.
- Last run: PASS 2026-07-11
  ([owner import report](reports/2026-07-11-owner-private-transcript-import-and-recall.md)); two
  bounded transcript-only apply batches repaired five then three summaries, made zero saved-memory
  changes, and finished with all 57 transcript index rows processed and no cap skips.

## MTM-018: Transcript Folder Selection Uses Canonical Config

- Scenario: A user installs Viventium, then chooses a local transcript folder from the macOS
  status-bar helper before ingesting transcripts.
- Expected outcome: The helper opens a directory picker, calls the public CLI/config patcher,
  updates only `runtime.memory_hardening.transcripts.source_dir` in canonical `config.yaml`, writes
  a local config backup, recompiles generated runtime files, and then lets the user run bounded
  transcript ingest. Runtime recall attaches only artifacts whose source-folder hash matches the
  currently configured folder.
- Forbidden result: Source code hardcodes a user email/path, the helper edits generated env files,
  old-folder artifacts remain attached after a folder switch, or `--help`/cancel creates side
  effects.
- Evidence to capture: helper menu/picker QA, CLI JSON output on a synthetic config, runtime env
  compiled value, source-folder-hash attachment filter test, and no private path in public QA.
- Last run: PASS 2026-05-22; see
  `qa/meeting-transcript-memory/reports/2026-05-22-transcript-folder-picker-batching-qa.md`.

## MTM-019: Installer Transcript Ingest Readiness

- Scenario: A new Express or Advanced user either has no transcript folder yet, chooses a valid
  folder during setup, or tries a missing folder.
- Expected outcome: Installer/status marks an empty source as `Needs setup`, persists a valid folder
  only through canonical `runtime.memory_hardening.transcripts.source_dir`, compiles the generated
  env, and guides the user to bounded transcript-only ingest. Missing folders fail softly into setup
  pending instead of writing a bad path.
- Forbidden result: A developer path or email is hardcoded, generated env is edited directly, a
  missing folder is treated as ready, or public QA includes raw transcript text/file names/private
  source paths.
- Evidence to capture: wizard/setup selection result, config diff with path redacted or synthetic,
  generated env key presence, bounded ingest readiness, status row, and public-safety scan.
- Last run: PARTIAL 2026-05-31; wizard/status automation added under `INST-004`, browser/helper
  clean-install proof remains.

## MTM-020: Focused Summary Retrieval Must Supplement The Global Vector Batch

- Scenario: A narrow meeting question names date/title/participant metadata that identifies one
  processed summary, but the global multi-document vector batch returns only semantically similar
  meetings.
- Expected outcome: Structured transcript metadata selects a small focused candidate set, queries
  those summaries in addition to the global batch, deduplicates the merged results, and ranks the
  exact matching summary ahead of broad inventory or distractor evidence.
- Forbidden result: The assistant claims the target transcript is unavailable even though its
  processed summary and vector document both exist, or focused retrieval replaces the broad batch
  and loses useful supporting context.
- Evidence to capture: synthetic metadata-match regression, global and focused RAG calls, source
  order, visible browser answer/source cards, and persistence after reopening the conversation.
- Last run: PASS 2026-07-11
  ([owner import report](reports/2026-07-11-owner-private-transcript-import-and-recall.md)); the full
  42-test file-search suite passed, and the real browser answer led with the exact summary, separated
  the requested meeting phases, preserved uncertainty, and survived reopen with zero console errors.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Meeting Transcript Memory. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `MEETING-UC-001` | Ask a browser chat question that should use processed meeting transcript memory, then inspect visible answer sources and backend evidence. | `MTM-001`-`MTM-009`, `MTM-015`, `MTM-016`, `MTM-020` | Browser chat, file/source cards, processed transcript index, and sanitized logs | Model-facing file/source order, stored source order, visible source cards, memory hardening output, and dated QA report | The answer is grounded in processed transcript evidence, not attached raw files or unrelated memory, and sources are visible. Identity/person-role claims are not invented from transcript-only evidence. | PASS 2026-07-11 ([owner import report](reports/2026-07-11-owner-private-transcript-import-and-recall.md)); exact-summary-first source order and answer quality were visually verified in a real browser |
| `MEETING-UC-002` | Try transcript ingest or recall when the sidecar/index/lock/provider/vector runtime is missing, stale, or degraded. | `MTM-010`-`MTM-017`, `MTM-020`, and degraded-state cases | CLI ingest/dry-run, browser chat degraded state, and sanitized logs | Stale-lock fixture, dry-run exit status, run summary, lock cleanup, model/vector telemetry, logs, and QA report | The system clears stale locks when safe, reports degraded prerequisites honestly, tries configured model fallbacks, processes bounded backfill batches, and does not fabricate transcript recall or identity. | PASS 2026-07-11 ([owner import report](reports/2026-07-11-owner-private-transcript-import-and-recall.md)); missing vector dependency and inconclusive presence checks recovered without destructive work |
| `MEETING-UC-003` | After ingest/repair, rerun the browser recall question and compare persistence/state across refresh or retry. | `MTM-001`-`MTM-017`, `MTM-020` | Browser chat, persisted message/source state, transcript index, and logs | Stored source order, visible source cards, memory hardening summary, and dated QA report | Recall remains grounded after retry/refresh and final wording matches persisted evidence; corrected chat memory outranks stale transcript-derived identity. | PASS 2026-07-11 ([owner import report](reports/2026-07-11-owner-private-transcript-import-and-recall.md)); all eight target vectors were present and the grounded answer/source cards survived conversation reopen |
| `MEETING-UC-004` | Choose a transcripts folder from the status-bar helper, then ingest transcripts. | `MTM-018` | macOS helper menu/picker, CLI config patcher, generated runtime env, and transcript ingest summary | Picker visible state, config backup, runtime env value, source-folder-hash filter, bounded ingest output, and dated QA report | The chosen folder is persisted through canonical config for this install without hardcoded owner data, and ingest processes the current folder only. | PASS 2026-05-22; see `qa/meeting-transcript-memory/reports/2026-05-22-transcript-folder-picker-batching-qa.md` |
| `MEETING-UC-005` | During Express/Advanced setup, leave transcript ingest pending, choose a valid folder, and try a missing folder. | `39_Installer_and_Config_Compiler.md` / `MTM-019`, `INST-004` | installer wizard, `bin/viventium status`, generated env, transcript source CLI | Wizard choices, canonical config, generated env, status row, source-folder-hash readiness, public-safety scan. | Empty source is pending, valid source is configured, missing source is not marked ready, and no private path or transcript text is published. | PARTIAL 2026-05-31; automated wizard/status coverage added, user-grade clean install remains |

## Release Test Traceability

- `tests/release/test_config_settings.py`
