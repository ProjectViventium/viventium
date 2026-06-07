<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# Scheduling Cortex / Workbench Nightly RCA - 2026-05-27

## Status

- `SCHED-002` trigger and delivery ledger: `PASS` for the 2026-05-27 synthetic
  Workbench/GlassHive manual proof.
- `SCHED-007` stale GlassHive project cache recovery: `PASS`.
- `PW-029` scheduled GlassHive prompts: `PASS` for the active-runtime stale-cache proof.
- Transcript RAG/vector runtime: `PASS` for service health and transcript vector-presence repair;
  browser recall answer QA remains a separate `RAG-001`/meeting-recall follow-up.

The 2026-05-27 nightly audit correctly failed the overnight routine, but the follow-up RCA found a
more specific Scheduler/GlassHive cause than the original summary: the built-in Workbench scheduled
prompt carried a cached GlassHive project id that no longer existed in the live GlassHive runtime.
GlassHive returned HTTP 404 correctly; Scheduling Cortex was wrong to reuse the stale cached id
without validating or replacing it.

## What The Prior QA Missed

1. The prior synthetic scheduled-prompt QA exercised newly-created synthetic rows, not the existing
   built-in Workbench nightly row with its persisted GlassHive project cache.
2. Source/runtime health checks proved the Scheduler and GlassHive API were listening, but did not
   validate that the row-specific cached project still existed.
3. The RAG/Ollama failure was recorded as a dependency outage, but the audit did not complete a
   supported runtime bring-up and post-start health check before closing.

## Evidence Checked

Public-safe evidence only:

- GlassHive API health endpoint returned healthy on the runtime API port.
- GlassHive OpenAPI contained `POST /v1/projects/{project_id}/workers/find-or-resume`, proving the
  404 was not a missing route.
- The built-in Workbench scheduled prompt was active, advanced to its next scheduled run, and
  recorded a terminal dispatch failure with an HTTP 404 class.
- A direct lookup of the cached project id returned 404 `Project not found`; the raw project id is
  intentionally omitted from this public report.
- The generated runtime config selected Ollama embeddings and the local RAG API, but the nightly
  audit found no healthy RAG/PGVector service and transcript vector checks failed.
- Ollama is currently reachable and has the configured embedding model installed.
- Docker capacity was repaired with a builder-cache prune only. The supported RAG compose pull/start
  then succeeded.
- The first PGVector start exposed a corrupt local PG data directory. That directory was preserved
  under a private automation backup outside the public repo, then the supported RAG compose stack was
  started against a fresh local PG data directory.
- RAG health returned `UP`; Ollama had the configured embedding model; PGVector exposed the
  `vector` extension and the LangChain collection/embedding tables.
- Transcript ingest was rerun through the supported transcript-only CLI path with zero saved-memory
  changes. The final apply-mode presence check reported `files_seen=26`,
  `files_ignored_by_config=3`, `files_unchanged=23`, `files_requeued_missing_vectors=0`,
  `files_skipped_by_cap=0`, and `vector_presence_error_count=0`.
- Final memory-hardening status reported `lock_held=false` and transcript aggregate state
  `processed=47`.

## Fix Implemented

Scheduling Cortex now validates a cached Workbench `glasshive_project_id` before reuse:

- if the cached task-level project exists, reuse it;
- otherwise check the definition-level cached project;
- if GlassHive returns 404 for the cached project, create a replacement project;
- persist the replacement id back to both the scheduled prompt definition metadata and the task
  `workbench_scheduled_prompt` metadata;
- re-raise non-404 GlassHive validation errors so auth/network/runtime failures do not get hidden.

This keeps ownership in Scheduling Cortex, where the cache is stored, and does not make GlassHive
pretend that a missing project exists.

## Tests Run

```text
uv run --with pytest --with pyyaml --with pydantic --with croniter --with fastapi --with fastmcp python -m pytest tests/release/test_scheduled_glasshive_prompts.py -q
```

Result: `12 passed, 1 warning`.

The new regressions cover stale-cache and validation-error paths:

- both task metadata and definition metadata point at a missing project, so dispatch creates a
  replacement project, updates both caches, and queues the run against the replacement project;
- task metadata points at a missing project while definition metadata points at a valid project, so
  dispatch reuses the valid definition project and repairs the stale task cache without creating an
  unnecessary replacement project;
- cached project validation returns a non-404 HTTP error, so dispatch fails loud and does not create
  a replacement project.

Additional check:

```text
uv run --with pytest --with pyyaml --with pydantic --with croniter --with fastapi --with fastmcp python -m pytest tests/release/test_scheduling_mcp_supervision.py -q
```

Result: `2 passed, 1 warning`.

Final combined focused run: `14 passed, 1 warning`.

## Active-Runtime Repair Proof

### RAG / Transcript Vectors

Result: `PASS` for RAG service health and transcript vector lifecycle.

- Docker build cache cleanup reclaimed enough local capacity for the supported RAG API image pull.
- RAG API and PGVector were running through `rag.yml` with local ports bound to loopback.
- The corrupted PGVector data directory was not deleted into the public repo; it was moved to a
  private automation backup outside the repo before the fresh vector store was started.
- The transcript-only backfill path was run in bounded batches because the machine was on battery
  and large model-backed batches exceeded the interactive terminal window. The required operator
  power override was explicit for those repair batches.
- The final transcript apply-mode check completed with no missing vectors, no cap backlog, no
  vector-presence errors, and no saved-memory changes.
- PGVector embedding rows increased to `555` after repair and final inventory refresh.

One transient vector-presence error occurred in an intermediate bounded batch, but the batch did not
delete live artifacts or mark the corpus empty. Later batches and the final presence check reported
zero vector-presence errors.

### Scheduler / Workbench / GlassHive

Result: `PASS` for the stale-cache runtime proof.

The active runtime was restarted from the dirty local checkout that contains the Scheduler fix. The
first live synthetic proof still failed because the standalone Prompt Workbench backend had been
running for hours and had imported the old `scheduling_cortex.dispatch` module before the fix. After
restarting Prompt Workbench, the same synthetic row with stale task and definition project caches
completed successfully.

Public-safe proof:

- Synthetic Workbench-private prompt used memory write mode `off` and was left inactive.
- Stale project cache was injected into both task metadata and definition metadata; only a hash of
  that fake project id is recorded here.
- Before Workbench restart, manual run failed and both caches still matched the stale hash. This
  identified the missed live artifact: the Workbench backend process, not the Scheduler sidecar.
- After Workbench restart, manual run queued and completed through GlassHive.
- Task metadata, definition metadata, and run ledger all share the replacement project hash
  `85fc856c639b6fff`, which differs from the injected stale hash `ff7f61d9d5a35c30`.
- Workbench API run history showed the latest run as `completed` with a private detail pointer,
  GlassHive project/worker/run ids present, and result summary:
  `GlassHive run completed. Private details are stored in the run detail file.`
- Playwright opened the real Prompt Workbench UI, selected the synthetic schedule row, and verified
  the visible `Recent Runs` panel showed the latest run as `completed` with the same summary. No
  screenshot was saved because the visible pane contains private/local content.

## Claude Review

ClaudeViv review-only pass agreed that the RCA is supported by the evidence, the fix belongs in
Scheduling Cortex, and the `PARTIAL` classifications are correct until live runtime delivery proof
exists. It also flagged code/test edges:

- avoid string-matching `HTTP 404` for cache invalidation;
- make non-404 validation failures fail loud without replacement;
- repair asymmetric task/definition cache drift when one cache is still valid;
- add tests beyond the both-caches-stale path;
- keep RAG/vector remediation separate from the Scheduler fix.

The patch was tightened after that review with typed HTTP status handling, explicit non-404
regression coverage, and task-cache repair from a valid definition cache. Remaining implementation
risks are low-level durability edges: a partial metadata-write failure or parallel dispatch race
could still orphan an unused GlassHive project. Those do not justify a PASS without live evidence
and should be considered in the next hardening pass.

## Remaining Gaps

The stale-cache and transcript-vector gaps that kept `SCHED-002`, `SCHED-007`, `PW-029`, and the
transcript vector lifecycle partial are now closed for the active local runtime.

Remaining risks were separate known gaps at the time of this stale-cache report. They were
revisited later on 2026-05-27 in
[`2026-05-27-real-account-glasshive-backpressure-ledger-qa.md`](2026-05-27-real-account-glasshive-backpressure-ledger-qa.md):

- `SCHED-005` moved to `PARTIAL`: GlassHive host-worker overlap/backpressure has a source/runtime
  requeue fix and regressions, but still needs a live overlapping host-worker stress proof.
- `SCHED-006` moved to `PASS`: terminal callback-to-parent-ledger parity passed for the real
  built-in Workbench nightly completion path, with source regressions for capacity-wait and callback
  ordering.
- `PW-032` remains `FAIL`: one-time schedule UI state parity still needs a product fix.
- `RAG-001` remains `PARTIAL`: RAG service and transcript vector presence are healthy now, but a
  browser chat recall answer with visible source grounding was not run in this repair pass.
- The Workbench backend must be restarted or otherwise hot-reloaded when Scheduler dispatch code
  changes; otherwise it can keep an old imported dispatch module even when the Scheduler sidecar has
  restarted.
