# Meeting Transcript Memory QA

## Scope

Validates the local transcript memory lane:

- `VIVENTIUM_MEMORY_TRANSCRIPTS_DIR` / config compiler ownership
- optional `VIVENTIUM_MEMORY_HARDENING_USER_EMAIL` account scoping
- on-demand `bin/viventium memory-harden ingest-transcripts`
- hardener transcript envelopes, deterministic state, cost caps, and evidence gates
- detailed summary transcript file_search resources under the `meeting_transcript` context
- real-user recall behavior from a QA account without touching the owner account

## Acceptance Criteria

1. Empty or invalid transcript env disables the lane without failing normal memory hardening.
2. New text-like files, including CSV, are passed through to the transcript summarizer without
   format-specific parsing or semantic string matching.
3. Unchanged files and rename-only changes are not reprocessed after content-hash state is marked
   processed.
4. Files deferred by per-run caps are retried on later runs even when file metadata is unchanged.
5. Normal transcripts are never sliced by a shared run-level character cap; oversized transcripts
   that would require partial input are deferred rather than stored as complete recall.
6. Single transcript evidence can write only meeting-scoped `moments` / `context`.
7. Stable memory keys require user-authored chat evidence for the exact claim whenever transcript or
   Listen-Only evidence is involved. Multiple transcript/ambient sources alone are not enough.
8. RAG-down apply, including configured-but-unhealthy RAG, defers transcript-dependent writes while
   preserving normal chat-only hardening.
9. Processed transcript summaries attach through `file_search`; raw transcript artifacts are not
   stored for default recall and transcripts are not inserted into Mongo conversation history.
10. Manual status-bar ingest surfaces the active account scope before and after the run so a scoped
   QA/operator run cannot look like owner-account ingestion.
11. QA evidence uses synthetic transcript content and the local QA account unless the acceptance
   case explicitly requires owner-account parity after backup.
12. The fixture evals are executable and fail when an expected transcript-quality assertion lacks a
    runner.
13. After an on-demand transcript ingest, broad questions such as "list my recent conversations
    based on transcripts chronologically and give me a 5 line summary based on the actual context"
    retrieve the transcript inventory, enumerate processed transcript entries with date/time,
    participants, and one-line context, and preserve the transcript caveat instead of answering from
    a few semantically lucky chunks.
14. Transcript summarization and hardening use a configurable candidate list. The default order is
    Claude Code `claude-opus-4-7` at `xhigh`, Claude Code `opus` alias at `xhigh`, Codex/OpenAI
    `gpt-5.5` at `high`, then Codex/OpenAI `gpt-5.4` at `high`; failed candidates are reported
    with redacted reason telemetry and the next candidate is tried.
15. Model probes are short, configurable, and advisory by default. Probe failure must not make an
    otherwise usable transcript run fail unless the explicit require-probe env flag is enabled.
16. Inventory artifacts include compact source-folder status counts so broad recall can distinguish
    processed summaries from pending/deferred/skipped source files without indexing raw transcript
    text.
17. Live browser QA must use the copied non-owner QA account with provider credentials; the harness
    fails before seeding artifacts if the selected account has no connected-account/key rows.
18. Transcript summaries receive bounded saved-memory and recent-conversation `reference_context`
    for disambiguation only. The prompt must forbid importing unsupported reference facts into the
    meeting summary.
19. On-demand `ingest-transcripts` defaults to zero saved-memory changes and may be run
    `--apply --until-caught-up` for bounded historical backfill; each batch must advance
    content-hash state rather than relying on one giant model call. Dry-run caught-up loops are
    rejected because they cannot persist progress.

### Item 7/8 RAG Quality Addendum

- Default runtime mode is detailed-summary-only: upload and attach `meeting_summary` artifacts and
  delete/skip raw `meeting_transcript` vector artifacts unless explicitly enabled for QA comparison.
- Transcript vector artifacts carry deterministic provenance headers before indexed content:
  artifact id, artifact kind, original filename, file mtime, source status, and optional calendar
  match.
- file_search retrieval output repeats transcript provenance headers in model-facing text and source
  artifacts so retrieved chunks remain auditable even when the vector sidecar returns only chunk
  content.
- Detailed transcript summaries must preserve who is on the call, visible speaker labels, subject,
  date/time context, decisions, commitments, unresolved items, and useful time ranges when present.
  They should not repeat timestamps for every utterance because that wastes recall tokens.
  Transcript content remains untrusted evidence, not instructions.
- Summary reference context is only a disambiguation aid. If saved memory/recent chat conflicts with
  the transcript, the summary should preserve the transcript faithfully and mark uncertainty instead
  of converting reference context into meeting facts.

## Automated Evidence

Run from the public repo root:

```bash
cd viventium_v0_4/LibreChat/api
npm test -- --runInBand test/scripts/viventium-memory-hardening.test.js
npm test -- --runInBand test/app/clients/tools/util/fileSearch.test.js

cd ../packages/api
npm run test:ci -- --runInBand src/agents/meetingTranscripts.test.ts src/agents/__tests__/initialize.test.ts --coverage=false

cd ../../..
uv run --with pytest --with pyyaml python -m pytest tests/release/test_config_compiler.py -q
```

## Manual / Browser QA

1. Create synthetic transcript fixtures in a temp folder outside the repo.
2. Export `VIVENTIUM_MEMORY_TRANSCRIPTS_DIR` to that folder.
3. Run `bin/viventium memory-harden ingest-transcripts --dry-run --user-email <qa@example.com>
   --ignore-idle-gate --skip-model-probe` with a synthetic proposal file when testing without a live
   model.
4. Apply only against the QA account.
5. Log in as the QA account and ask for recall of the synthetic meeting topic, then ask a stale-belief
   trap question. Expected: Viventium recalls meeting-scoped context but does not convert
   transcript-only language into stable identity unless corroborated.

The reusable live browser harness is:

```bash
VIVENTIUM_QA_ALLOW_LOCAL_JWT=1 \
VIVENTIUM_QA_OWNER_EMAIL=<owner-account-email> \
VIVENTIUM_QA_EMAIL=<qa-account-email> \
node qa/meeting-transcript-memory/evals/run-live-browser-qa.cjs --headless --client-base http://localhost:3190 --api-base http://localhost:3180
```

It fails closed unless an explicit owner-account refusal guard and an explicit non-owner QA account
are supplied or a local non-owner QA clone with provider credentials can be selected. It then seeds
synthetic summary-only transcript artifacts into that QA account, verifies the chronological
recent-transcripts inventory question, broad inventory recall, and focused detail recall through
the visible LibreChat UI, and writes public-safe results under
`qa/meeting-transcript-memory/reports/`.

## 2026-05-22 Operational QA Evidence

- Public-safe operational report:
  `qa/meeting-transcript-memory/reports/2026-05-22-transcript-memory-operational-qa.md`.
- QA clone live browser report:
  `qa/meeting-transcript-memory/reports/2026-05-22-live-browser-qa-2026-05-22T05-55-27-419Z.md`.
- The copied non-owner QA clone was selected only after the harness verified connected-account/key
  rows; the owner transcript count was unchanged during QA-clone seeding.
- Owner backup existed before owner mutation. The owner-scoped apply run cleared the remaining
  pending transcript, uploaded summary/inventory vectors, and left 0 missing vectors, 0 stale
  artifacts, and 0 vector-presence errors.
- Owner browser parity passed with visible file_search-backed transcript recall, inventory and
  summary sources attached, visible dates, and a transcript caveat.

## 2026-05-13 Chronological Transcript Recall Evidence

- `bin/viventium status`: ready; LibreChat frontend on `localhost:<port>`, API on
  `localhost:<port>`, and Conversation Recall/RAG on `localhost:<port>`.
- `node qa/meeting-transcript-memory/evals/run-evals.cjs`: pass, 11/11 executable public-safe evals,
  including `broad-chronological-inventory-retrieval-contract`.
- Live browser QA with the non-owner QA account passed:
  `qa/meeting-transcript-memory/reports/2026-05-13-live-browser-qa-2026-05-13T03-13-06-493Z.md`.
- The live browser answer for the chronological recent-transcripts prompt used `file_search`,
  retrieved the transcript inventory, listed all seeded transcript entries, ordered them
  chronologically, included visible dates, participants, and meeting context, stayed near the
  requested concise-summary shape, and preserved the transcript caveat. This prompt uses the raw
  user-facing wording from MTM-007 rather than an explicit "use file_search" instruction.
- Owner meeting-transcript count remained unchanged, prior synthetic QA artifacts were cleaned
  before seeding, and default recall mode still uploaded zero raw transcript artifacts.

## 2026-05-12 Local Live QA Evidence

- `bin/viventium status`: ready; LibreChat frontend on `localhost:<port>`, API on
  `localhost:<port>`, Conversation Recall/RAG on `localhost:<port>`, and Telegram surfaces running.
- RAG health and UI health checks passed before browser QA.
- `VIVENTIUM_QA_ALLOW_LOCAL_JWT=1 VIVENTIUM_QA_OWNER_EMAIL=<owner-account-email>
  VIVENTIUM_QA_EMAIL=<qa-account-email> node
  qa/meeting-transcript-memory/evals/run-live-browser-qa.cjs --headless --client-base
  http://localhost:3190 --api-base http://localhost:3180`: pass.
- Public-safe report:
  `qa/meeting-transcript-memory/reports/2026-05-12-live-browser-qa-2026-05-13T02-30-02-460Z.md`.
- QA account hash selected: `79232c0a29b5`; owner meeting-transcript count unchanged.
- Browser evidence: broad inventory prompt used file_search and retrieved one transcript inventory
  source on the first turn; focused detail prompt used file_search and retrieved meeting-summary
  sources with the synthetic marker present.
- Default mode still uploaded zero raw transcript artifacts for recall.
- Regression evidence: `node qa/meeting-transcript-memory/evals/run-evals.cjs` passed all 10
  public-safe evals; backend hardener/file_search tests passed 83/83; packages API transcript and
  RAG presence tests passed 44/44; packages API build regenerated `dist/`.
- Runtime fix covered by this pass: RAG document presence now uses a lightweight `/exists` check,
  meeting transcript RAG queries batch through `/query_multiple` with file-count-scaled top-k,
  transcript artifact presence is verified in one batch call, mixed transcript/recall results
  preserve matched transcript evidence, source-backed transcript inventory attaches without waiting
  on vector existence, and recall literal rescue excludes active prompt echoes.
- Reproducibility fix after Claude review: the LibreChat component changes were committed at
  `e1c71a8ec129238eff7a7c7c13e43d77f012bcc4`, and `components.lock.json` now pins that commit.
- Operational note: local Mongo crashed during an earlier QA attempt because the owner runtime data
  directory had a missing WiredTiger collection file. The original data directory was backed up
  outside the public repo, QA used a repaired clone, and the failure reason is preserved in local
  runtime Mongo logs rather than public artifacts.

## 2026-05-06 Final-Pass Evidence

- `node --check viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js`: pass
- `python3 -m py_compile scripts/viventium/config_compiler.py scripts/viventium/memory_harden.py`:
  pass
- YAML parse check for `config.schema.yaml`, `config.full.example.yaml`,
  `config.minimal.example.yaml`: pass
- Targeted backend hardener, file_search, and conversation-recall filter/service tests: 89 passed
- File search coverage includes meeting-transcript query budget/provenance overrides,
  relevance-preserving mixed-source ranking, and per-source output budgets.
- Packages API meeting transcript helper and initialize-agent attachment tests: 21 passed
- Memory-hardening contract and macOS helper release tests via
  `uv run --with pytest --with pyyaml`: 23 passed
- Data provider package build: pass
- Data schemas package build: pass
- Packages API build: pass, with existing unrelated TypeScript warnings
- macOS helper fallback build: pass; shipped universal helper binary contains `Advanced` and
  `Ingest Meeting Transcripts`.
- LaunchAgent schedule proof: generated schedule is `0 3 * * *`; installed plist has
  `Hour => 3`, `Minute => 0`, and the scheduled command invokes the memory-hardening wrapper
  directly instead of routing through the user-facing CLI lock.
- First scheduled apply safety: with `dry_run_first` enabled, the first scheduled run without a
  marker performs dry-run-only; later scheduled runs can apply.
- Executable eval harness: `node qa/meeting-transcript-memory/evals/run-evals.cjs` passed all 7
  public-safe fixture assertions, including an actual file_search mixed-source ranking check.
- Apollo/export proof: repo search found no Apollo/Apify transcript downloader or transcript export
  flow in this lane; ingestion is local-folder only.
- Manual status-bar helper proof: the shipped universal helper binary contains `Advanced`,
  `Ingest Meeting Transcripts`, `helper-transcript-ingest.log`, and the direct
  `scripts/viventium/memory_harden.py` wrapper path.
- Earlier Claude/ClaudeViv review passes completed and drove account scoping, executable evals,
  stricter schema-required transcript summaries, dry-run-first documentation, and Codex env hygiene
  fixes. The later adversarial review below reopened release-readiness and brittleness gaps that
  remain tracked here instead of being claimed complete.

## Eval Fixtures

Synthetic item 7/8 fixtures live under `qa/meeting-transcript-memory/evals/` and cover stale traps,
prompt injection, speaker/time visibility, raw-vs-summary mode, CSV/TXT/JSON/VTT/SRT/MD
pass-through, and mixed-source ranking where current transcript content outranks low-signal
assistant no-access recall disclaimers without a blanket source-class override.

```bash
node qa/meeting-transcript-memory/evals/run-evals.cjs
```

## 2026-05-06 Live QA Evidence

- Full local Mongo backup was captured outside the public repo before QA.
- Owner account was not used for transcript ingestion; owner meeting-transcript file count remained
  zero after QA.
- QA account was used for all transcript ingestion checks and had OpenAI/Anthropic connected-account
  keys present without exposing token values.
- Synthetic transcript fixtures included CSV plus edit-lifecycle content; automated fixtures also
  cover TXT, JSON, VTT, SRT, MD, stale-trap, prompt-injection, and zero-commitment cases.
- First clean apply uploaded one meeting-transcript summary RAG artifact for the QA account only and
  uploaded zero raw transcript artifacts in default mode.
- Immediate follow-up dry run reported no pending transcripts and fed zero transcript characters to
  the model.
- Rename/edit/delete lifecycle was covered by automated tests; live edit QA deleted the prior
  content-hash summary artifact and uploaded the updated summary.
- Direct RAG query returned the latest synthetic meeting transcript summary artifact.
- DB artifact inspection showed kind `summary`, original filename present, file mtime present,
  source status present, owner meeting-transcript file count zero, QA raw transcript file count zero,
  QA summary file count one.
- Runtime attachment now matches transcript artifacts to the currently configured source-folder hash
  so artifacts from a previous opt-in folder are not silently attached after a directory change.
- Runtime attachment also requires a healthy vector runtime; unavailable RAG leaves meeting
  transcript artifacts unattached instead of advertising dead file_search resources.
- Live hardener apply used the launch-ready Anthropic tuple `claude-opus-4-7` at `xhigh` and
  default `detailed_summary_only` RAG mode.
- Local runtime can scope helper/scheduled hardening through compiled
  `VIVENTIUM_MEMORY_HARDENING_USER_EMAIL`; QA used this account-scope path so owner data remained
  untouched.
- Scope proof: running transcript dry-run without an explicit `--user-email` used the compiled
  QA account scope, selected exactly one user, found no pending transcripts, and fed zero transcript
  characters to the model.
- Real-browser QA through the local QA account asked Viventium to use `file_search`; the answer
  attached the meeting transcript summary artifact, cited it as the source type, and rejected the
  stale Atlas sentence as meeting-scoped fixture language rather than stable personal direction.

## 2026-05-06 Local Status-Bar / OAuth Follow-Up

- Installed helper binary proof: the live `~/Applications/Viventium.app` executable contains
  `Advanced`, `Ingest Meeting Transcripts`, `helper-transcript-ingest.log`, and the direct
  `scripts/viventium/memory_harden.py` wrapper path.
- Native desktop proof: Computer Use was run against the live desktop, and macOS Accessibility
  opened the actual Viventium status-bar menu. The menu exposed `Advanced`, and its submenu exposed
  `Ingest Meeting Transcripts`.
- Manual menu execution proof: pressing the submenu action through the native menu wrote
  `Manual transcript ingest requested`, then `Manual transcript ingest completed` to the helper
  transcript-ingest log.
- Live DB proof after the menu action: QA account had four meeting-transcript summary artifacts,
  zero raw transcript artifacts, and the owner account had zero meeting-transcript artifacts.
- Local state proof: transcript bookkeeping recorded processed, deferred-cap, and skipped-non-text
  records without storing raw transcript text in public QA artifacts.
- 2026-05-06 incident follow-up: a local owner-account browser check exposed two gaps. First, the
  helper/menu run was still scoped to the QA account, so owner recall had no transcript artifacts.
  Second, unchanged files marked `deferred_cap` were incorrectly skipped on later scans before they
  could be retried. The fix requires account-scope visibility, owner-account live QA after backup
  when owner use is being claimed, and a regression test proving deferred files are retried.
- Follow-up owner-account proof after backup: repeated bounded ingest passes retried deferred files
  and uploaded a summary artifact for a later transcript that had previously been stranded by the
  cap. Browser QA from the owner account attached meeting transcript summary source documents
  through `file_search` and answered from the meeting summary instead of stale conversation recall.
  The new QA conversation had one root user message and no extra sibling branches.
- Installed helper proof after rebuild: the live status-bar menu exposed `Advanced > Ingest Meeting
  Transcripts`; pressing it opened a confirmation dialog that named the active account scope before
  any ingest work ran.
- Helper completion proof after follow-up: the rebuilt helper parses the wrapper's JSON result and
  reports public-safe counts such as files checked, pending-at-start, summaries uploaded, and files
  deferred by caps. The owner transcript queue was driven to zero deferred files: ten text
  transcripts processed as detailed summaries and one non-text file skipped.
- Adversarial review follow-up: subagent review found empty-evidence memory writes, source-folder
  processed-state reuse, manual helper idle-gate no-op risk, stale helper prebuilt hash risk, and
  over-broad recall-rescue/filtering behavior. Fixes added evidence-required validation,
  source-folder state reset, user-triggered helper `--ignore-idle-gate`, refreshed helper prebuilt
  hash, structural source-rescue routing, and transcript-specific no-match output.
- Second adversarial follow-up found canonical env drift, mixed-source ranking risk, and an
  overfit in a transcript-first ranking patch. Fixes made the direct memory hardening wrapper load
  the same generated env stack as `bin/viventium`, added active runtime checkout re-exec for
  `memory-harden`, removed the blanket transcript-first override, and added evidence-based
  mixed-source ranking/budget tests.
- OAuth redirect safety proof: `runtime.auth.connected_accounts_return_origin` now compiles to
  `VIVENTIUM_CONNECTED_ACCOUNTS_RETURN_ORIGIN`; tests prove the override changes only the
  connected-account OAuth browser return origin while leaving `DOMAIN_SERVER` intact.
- Local config proof: the operator config restored the normal public app/API origins and carries
  the localhost connected-account return override as the temporary off-network switch.
- Schedule proof: the installed 3am LaunchAgent uses App Support as `WorkingDirectory` and invokes
  the memory-hardening wrapper directly, avoiding protected-folder working-directory failures from
  developer checkouts under Documents/Desktop/Downloads.

## 2026-05-06 Adversarial Review Pass

- ClaudeViv structured review confirmed the main structural claims: the transcript lane does not
  parse transcript content for semantics or participants, does not blanket-prioritize transcript
  source class over stronger chat evidence, gates transcript attachment/writes on vector runtime
  health, and the scanned public QA/docs/tests do not expose private transcript text or credentials.
- ClaudeViv contradicted release-readiness: the nested LibreChat work is still dirty/untracked in
  the component repo, so the parent `components.lock.json` pin cannot reproduce this feature from a
  clean checkout yet.
- ClaudeViv flagged the assistant no-access/no-memory downranker as brittle because it is an
  English text pattern over assistant recall text. It is not transcript parsing, but it can still
  miss paraphrased stale-disclaimer turns.
- Natural browser QA against the local QA account asked a normal meeting-transcript recall question
  for a synthetic fixture. The visible answer attached both `conversation-recall-all.txt` and a
  `meeting-transcript-summary-*` source document, answered from the transcript summary, and stated
  the fixture was meeting-scoped rather than stable identity.
- DB proof for that browser run showed one QA conversation, one user message, one completed
  assistant message, and file_search source attachments including the meeting summary artifact.
- Oversized-transcript contradiction found by later review: partial transcript input must not be
  stored as complete recall. Regression coverage now verifies oversized text is deferred and normal
  transcripts are not sliced by a shared run-level character cap.
- Source-folder hygiene gap follow-up: the scanner still treats text-like files as transcript
  candidates by default, but operator/dowloader sidecars can now be excluded with deterministic
  relative-path ignore globs (`VIVENTIUM_MEMORY_TRANSCRIPTS_IGNORE_GLOBS` or
  `--transcript-ignore-glob`). This keeps semantic judgment with the summarizer while preventing
  known bookkeeping files from consuming transcript caps.

## 2026-05-12 Inventory + Observability Follow-Up

- Transcript summaries now carry optional agent-authored inventory metadata: display title,
  one-line context, date/time, and participants when knowable.
- Apply/no-op transcript runs refresh a source-scoped `meeting_inventory:*` file-search artifact
  from current processed summary rows. The inventory is recall metadata, not saved memory.
- Runtime file_search returns the inventory artifact directly from source metadata so broad
  “what recent transcripts do you see?” questions have a complete list/TOC surface before semantic
  summary retrieval.
- Failed hardening runs now persist redacted failure artifacts (`summary.json`,
  `failure.redacted.json`, `run-log.redacted.jsonl`) with phase/reason/status/timeout details.
- Synthetic regressions added for source-folder sidecar ignore, broad transcript inventory, and
  failed-run durability.

## 2026-05-07 Missing-Vector Repair Evidence

- Root cause reproduced against the live local runtime: Mongo held processed meeting-transcript
  summary rows marked `embedded=true`, while PGVector had no chunks for those `file_id`s. That made
  file_search return only unrelated conversation recall even after transcript ingest appeared
  successful.
- Fix: apply-mode transcript scanning now verifies current processed-content state against the
  vector store. Missing summary/raw documents requeue the full indexed content hash for repair;
  the shortcut no longer trusts Mongo `embedded=true` alone.
- Fix: the memory-hardening wrapper now loads generated runtime env without letting empty service
  placeholders erase real lower-level runtime values, and explicit operator env still wins.
- Fix: transcript vector metadata now stores the full source content hash plus completeness counts
  (`inputComplete`, raw/supplied/summary chars) so future repair and audits can reason from stable
  artifact metadata.
- Fix: orphan derived summary artifacts for the selected user/source that are no longer present in
  a non-empty current processed-content index are treated as stale lifecycle artifacts instead of
  being attached forever. Missing/empty indexes do not trigger bulk deletion.
- Live repair proof used the real configured model and local Mongo + PGVector. An intentionally
  deleted processed summary artifact was requeued (`files_pending=1`,
  `files_requeued_missing_vectors=1`), uploaded back to PGVector, and its Mongo metadata was
  rewritten with a full content hash and complete-input counters.
- Live consistency proof after repair used sanitized QA-account data: all currently processed
  transcript summary artifacts for that account were present in PGVector, with zero missing vector
  rows.
- Live no-op proof after repair showed no pending or requeued files and zero model-input chars,
  proving unchanged synced transcripts do not waste model/read tokens.
- Regression suite:
  - backend hardener tests: 44 passed
  - packages API transcript/initialize tests: 24 passed
  - release memory/config/helper tests: 25 passed
  - transcript eval harness: 7 passed, 0 failed
