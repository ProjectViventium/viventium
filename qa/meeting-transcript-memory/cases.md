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
- Last run: 2026-05-13, automated regression passed in
  `api/test/scripts/viventium-memory-hardening.test.js`,
  `qa/meeting-transcript-memory/evals/run-evals.cjs`, and live QA confirmed the configured
  `_index.json` sidecar was pruned from primary/secondary QA transcript recall in
  `qa/meeting-transcript-memory/reports/2026-05-13-transcript-recall-repair-live-qa.md`.

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
- Last run: 2026-05-13, automated regression passed in
  `api/test/app/clients/tools/util/fileSearch.test.js`,
  `qa/meeting-transcript-memory/evals/run-evals.cjs`, and live browser report
  `qa/meeting-transcript-memory/reports/2026-05-13-transcript-recall-repair-live-qa.md`.

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
- Last run: 2026-05-12, live browser regression passed in
  `qa/meeting-transcript-memory/reports/2026-05-12-live-browser-qa-2026-05-13T02-30-02-460Z.md`.

## MTM-007: Chronological Recent Transcript Summary Must Use Inventory Context

- Scenario: After `Ingest Meeting Transcripts` or the equivalent on-demand hardener path has
  processed new transcript summaries, the user asks: "list my recent conversations based on
  transcripts chronologically and give me a 5 line summary based on the actual context."
- Expected outcome: The assistant uses `file_search`, retrieves the meeting transcript inventory,
  lists the processed transcript entries in the requested chronological order, includes visible
  date/time, participants, and one-line meeting context for each entry, and adds a transcript
  caveat line.
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
