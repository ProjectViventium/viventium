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
- Last run: 2026-05-12, automated regression passed in
  `api/test/scripts/viventium-memory-hardening.test.js` and
  `qa/meeting-transcript-memory/evals/run-evals.cjs`.

## MTM-004: Broad Recent-Transcript Questions Need Inventory Coverage

- Scenario: The user asks for a recent transcript/conversation inventory rather than a narrow topic
  lookup.
- Expected outcome: The assistant can enumerate processed transcript summaries at a useful level,
  then answer with transcript caveats. For narrow follow-up questions, focused transcript summary
  hits should outrank the broad inventory when they are clearly more relevant.
- Forbidden result: Semantic search returns only a few high-scoring chunks, causing the answer to
  imply incomplete visibility over the processed transcript set.
- Evidence to capture: file_search tool calls, retrieved sources, and final assistant answer.
- Last run: 2026-05-12, automated regression passed in
  `api/test/app/clients/tools/util/fileSearch.test.js` and
  `qa/meeting-transcript-memory/evals/run-evals.cjs`.

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
