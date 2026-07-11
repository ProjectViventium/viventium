# QA Memory Contamination Prevention
<!-- qa-evidence-exempt: Historical local QA format retained without retroactively inventing evidence; current release acceptance is recorded separately. -->

## Outcome

The owner-targeted synthetic QA contamination was surgically removed and the affected derived state
was rebuilt. The prevention fix keeps browser QA on a non-owner account, isolates memory/recall,
persists structured QA provenance, and cleans both canonical and search state in `finally`.

## Root cause

A local browser harness accepted an arbitrary account email, minted local QA auth, and lacked both an
owner refusal guard and mandatory cleanup. Running it against the owner allowed the synchronous
Memory Agent to save a synthetic premise. A later independent memory pass re-promoted related
context. A real schedule then merged that false premise with legitimate context and delivered it.

Ruled out: cross-user QA-account leakage, the batch hardener as the original writer, Telegram text
re-ingestion, and Prompt Workbench as the writing path.

## Cleanup evidence

- A timestamped immutable pre-cleanup backup passed archive CRC, logical database restore dry-run,
  persistence checks, and SHA-256 verification. It remains intentionally classified as contaminated.
- Item-level preimages were captured before mutation.
- Fifty-five QA-only conversations and 217 QA messages were removed. Four mixed conversations were
  surgically repaired so legitimate user content survived. Three exact synthetic file rows and nine
  inactive QA schedules were removed.
- The real schedule was preserved while contaminated generated/delivery fields were cleared.
- Mongo, Meilisearch, scheduler primary/mirror state, and conversation-recall vectors were reconciled.
- The canonical all-scope owner recall corpus remains one 404-vector resource. After background
  processing resumed, the owner recall store contained 607 vectors in total; zero vectors matched
  known incident canaries, and the owner message/saved-memory baselines did not move.

Private evidence contains exact IDs, raw preimages, hashes, and restore artifacts outside this public
repository.

## Prevention

- Fail closed when the owner guard is unset.
- Refuse requested or resolved owner selection.
- Stamp each QA request with a bounded structured run ID.
- Persist `qaRun=true` and `memoryEligible=false` on saved messages.
- Skip saved-memory writes, recall sync, and feelings reactions for the QA request.
- Exclude expired/QA-ineligible rows from the delayed hardener, recall corpus, and Meilisearch.
- Remove an already-indexed Meili document when it becomes ineligible.
- Mark recall metadata unembedded before replacement upload and invalidate the in-process digest cache
  so failed replacement cannot look current.
- Always delete run-scoped Mongo and Meili artifacts in `finally`.

## Verification

- Owner-path QA refused before browser creation.
- Real connected non-owner browser run: required setup cards visible; follow-up ready; the latest simple
  turn answered exactly `TEST_OK`; no stale cortex parts/Phase-B visible children; answer survived
  reload; structured `qaRun` / `memoryEligible=false` provenance was present in Mongo before cleanup;
  cleanup passed.
- Owner and QA saved-memory hashes and message/conversation counts were identical before and after the
  accepted run; persisted QA-run rows and exact final-run search markers were zero after cleanup.
- Post-cleanup comparison against the private item-level preimages confirmed all 19 reviewed
  surgical-delete rows are absent, all four retained legitimate rows match their original payloads,
  and all four parent repairs plus three title repairs match the approved manifest.
- Targeted API/hardener/recall tests passed (`275`), Meili eligibility tests passed (`51`), release
  harness tests passed (`3`), and the data-schemas build passed.

## Restore warning

The immutable backup predates sanitation. A restore must reapply the approved sanitation manifest and
rebuild recall/search derived state before the restored runtime is allowed to deliver schedules or
user responses.
