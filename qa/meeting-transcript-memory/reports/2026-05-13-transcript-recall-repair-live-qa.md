<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
# Meeting Transcript Recall Repair Live QA - 2026-05-13

Public-safe report. Private transcript text, local paths, screenshots, emails, reset tokens, and
raw account IDs are intentionally omitted.

## Scope

- Reproduce the broad transcript recall failure where the assistant answered as if only one
  transcript conversation existed.
- Repair the live local transcript corpus and verify the secondary QA account has equivalent transcript
  recall artifacts for QA.
- Prove the user-visible browser and Telegram-style surfaces can answer:
  "list my recent conversations based on transcripts chronologically and give me a 5 line summary
  based on the actual context."

## Findings

- Root cause 1: the primary QA account had processed transcript state, but current meeting transcript
  file/RAG artifacts were missing. The scanner correctly requeued missing vectors after the repair
  invariant was run.
- Root cause 2: broad transcript questions could lose the source-backed transcript inventory behind
  summary/conversation-recall results and citation relevance sorting.
- Root cause 3: source-only conversation recall could rescue the active prompt or older transcript
  QA prompts as evidence, which made broad transcript answers vulnerable to stale prompt echoes.

## Fixes Verified

- Missing transcript vectors are repaired before processed state is trusted.
- Meeting transcript summary/inventory evidence is front-loaded ahead of conversation recall for
  transcript answers.
- Source-only conversation recall rescue is skipped once meeting transcript evidence is already
  present.
- Recent active user prompts are excluded from source-only recall rescue when current conversation
  metadata is unavailable.
- Citation attachments preserve explicit tool source order instead of resorting transcript evidence
  behind higher-scored conversation recall snippets.
- Inventory rows were compacted by removing artifact/file IDs from the broad TOC while preserving
  title, date/time, participants, original filename, one-line context, and transcript caveat.

## Evidence

- Primary QA repair apply: 17 meeting transcript summaries plus 1 inventory artifact available; missing
  vector count 0 after repair.
- Primary QA no-op dry-run: 17 unchanged transcript files, 0 pending, 0 requeued, 0 transcript characters
  fed to the model.
- Secondary QA account corpus: 17 summary artifacts plus 1 inventory artifact available for QA.
- Live Telegram-style API replay on the secondary QA account: status 200, answer did not contain the
  "only one conversation" failure, source order began `meeting_summary`, `meeting_inventory`, then
  `conversation_recall`, and active prompt echo was absent from sources.
- Live browser QA on `localhost:3190`: logged into the secondary QA account, submitted the broad transcript
  prompt, visually confirmed a chronological dated transcript table, source cards led with meeting
  summary and meeting inventory, and the answer included a five-line contextual summary plus
  transcript caveat.
- Post-compact-inventory API replay: answer contained many dated transcript entries and did not
  answer as if only one transcript existed.
- Claude review found that low-relevance source-backed transcript inventory could be filtered out
  of citation cards in transcript-only paths. Fixed by allowing structured meeting transcript
  sources through the generic citation threshold and adding a realistic regression.
- Claude follow-up verified that the medium citation-threshold finding is resolved and found no
  release-blocking issue remaining.
- Final live Telegram-style replay after restart: many dated transcript entries, no "only one"
  failure, meeting summary then meeting inventory leading source order, and no active prompt echo.
- Follow-up primary QA dry-run on 2026-05-13: stale hardening lock from a dead PID was recovered by the
  hardener, the run completed with 19 files seen, 2 configured sidecars ignored, 17 unchanged
  transcripts, 0 pending, 0 missing-vector repairs, and 0 transcript characters fed to the model.
- Sidecar cleanup follow-up on 2026-05-13: canonical config now compiles
  `transcripts.ignore_globs` to `VIVENTIUM_MEMORY_TRANSCRIPTS_IGNORE_GLOBS`. The local transcript
  source ignores `_index.json`; primary QA apply pruned the already-ingested sidecar summary and refreshed
  inventory with 0 transcript characters fed to the model.
- Secondary QA account parity follow-up: the secondary QA account has 16 meeting summaries plus 1 inventory artifact,
  matching the primary QA account after sidecar cleanup. No `_index.json` artifact or inventory row remains.
- Final live browser replay on the secondary QA account listed 16 dated transcript meetings, retrieved
  meeting summary then meeting inventory before conversation recall, did not produce the "only one"
  failure, and included the transcript caveat.
- Final primary and secondary QA account dry-runs both reported 19 files seen, 3 ignored sidecars, 16
  unchanged transcript meetings, 0 pending, 0 removed, 0 missing-vector repairs, and 0 transcript
  characters fed to the model.
- Transcript inventory sustainment follow-up: the transcript summarizer prompt now explicitly tells
  the agent that inventory fields are human meeting context only, not a place for artifact IDs,
  stable file IDs, vector IDs, content hashes, or source-folder hashes. A real secondary QA account apply
  refreshed the live inventory vector with 0 transcript characters fed to the model and uploaded 1
  inventory artifact. Mongo metadata check confirmed 16 inventory entries with date/time,
  participant, and context lines, and confirmed no artifact ID label, meeting summary ID, meeting
  transcript ID, inventory ID, or source hash in the model-visible inventory body.
- ClaudeViv final review confirmed the core no-semantic-regex inventory design and private-data
  hygiene. Grounded findings addressed locally: stale-lock recovery now also handles old recycled
  PID locks, MTM-003 now has a literal `_index.json` regression, and the compiler doc notes that
  ignore globs are comma-separated. ClaudeViv's remaining release-readiness finding is intentionally
  unresolved in this run because no push was requested: nested LibreChat changes are local until the
  component repo is committed/pushed and the parent pin is updated.

## Automated Tests

- `npm test -- --runInBand test/scripts/viventium-memory-hardening.test.js test/app/clients/tools/util/fileSearch.test.js test/services/Files/processFileCitations.test.js`
- Result: 3 suites passed, 104 tests passed.
- `node qa/meeting-transcript-memory/evals/run-evals.cjs`
- Result: 11 evals passed, 0 failed.
- Transcript inventory sustainment regression added to
  `api/test/scripts/viventium-memory-hardening.test.js`; it inspects the exact mocked inventory
  vector upload body and verifies useful title/date/participants/context survive while lifecycle IDs
  stay out of model-visible TOC text.
- Stale-lock regression added to `api/test/scripts/viventium-memory-hardening.test.js`.
- Config compiler ignore-glob path verified directly with a focused Python import/assert because
  `pytest` was not installed in the local Python runtime.

## Residual Risk

- Conversation recall can still appear after transcript sources when it independently vector-matches
  a broad transcript query. Current mitigation is ordering and prompt-echo exclusion; the answer
  must stay grounded in transcript summary/inventory evidence first.
