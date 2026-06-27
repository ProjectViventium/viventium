# GlassHive Host Workers First-Principles Path Coverage Audit

Date: 2026-06-25
Status: PASS/PARTIAL

## Scope

This audit covers the local GlassHive host-worker path from user request to worker launch, evidence
classification, callback delivery, and visible chat wording. It focuses on the escaped failures where
users saw generic failure text even though a worker produced output, browser evidence was mislabeled as
provider failure, or steering created invalid worker URLs.

## First-Principles Path Map

1. User surface: LibreChat web, voice, or Telegram asks for delegated work.
2. Host agent: chooses GlassHive with structured arguments and passes the user's real goal and constraints.
3. MCP/API boundary: validates project, worker, run, schedule, and action ids before HTTP.
4. Worker runtime: launches the selected host/workstation worker and records logs, artifacts, final report,
   run state, evidence, and callback outbox rows.
5. Evidence gate: decides whether the run is completed, failed, partial, or blocked using structured run
   evidence, not incidental browser/accessibility labels.
6. Callback receiver: verifies HMAC, conversation ownership, replay/staleness, and branch-safe message
   placement.
7. User-visible result: web, Telegram, and voice surfaces show truthful wording and do not expose worker
   plumbing, raw local paths, or private runtime ids.

## Happy Paths

- Worker completes with a `FINAL REPORT:` and no evidence defects: callback says the work completed and
  updates the current chat branch or pending placeholder.
- Fresh one-shot delegation omits `project_id`, supplies a scoped owner, and GlassHive creates the
  project/worker/run instead of requiring the caller to invent ids.
- Worker completes browser/computer work whose logs include page labels like numeric menu/button ids:
  evidence stays non-failure unless there is contextual provider/status evidence.
- User steers a known worker id: MCP/API sends a well-formed route and the worker receives the message.
- Callback arrives while an unfinished assistant placeholder is active: the placeholder is replaced in place
  and `unfinished=false` is persisted.
- Callback arrives while an unrelated assistant response is still in progress: the receiver returns retryable
  `425` and waits rather than overwriting another response's placeholder.
- Telegram and voice claim persisted callback-delivery rows and mark them sent/failed through their own
  delivery APIs after the main response stream ends.

## Unhappy Paths

- Missing owner or missing/blank/path-shaped worker id: rejected before HTTP; forbidden result is a
  `/workers//...` request or a fake project/worker id.
- Non-existent explicit `project_id`: rejected as a missing project; the fresh-task path is to omit
  `project_id` and let GlassHive create the project.
- Failed evidence gate with a real deliverable: run remains failed, callback explains that output exists but
  final verification failed.
- Total/provider failure: callback remains clear failure wording even if a stray deliverable-shaped field is
  present.
- Callback receiver outage: GlassHive outbox retains retryable callback rows and replays them later.
- Telegram/voice follow-up waits expire: the user should get the same persisted callback on later polling,
  not hallucinated completion text.
- Concurrent unrelated generation: a background worker callback must not clobber the unrelated active
  `Generation in progress.` response.

## RCA Summary

The root problem was not that the voice model was "dumb." It exposed three runtime contract gaps:

- Evidence classification was too willing to treat standalone status-like text from browser/computer output
  as provider failure evidence.
- Low-level API paths trusted caller-supplied ids too late, so one missed validation could still form broken
  routes such as empty worker-id segments.
- Callback UX collapsed two different states, "nothing useful delivered" and "output exists but verification
  failed," into the same generic stuck wording.

## Fixes Covered By This Audit

- Low-level GlassHive API client now validates path ids and guards every request path for empty, relative,
  traversal, slash, or backslash-shaped segments.
- Evidence classification ignores browser/page/accessibility status-like text for successful final-report runs.
- GlassHive callbacks include machine-readable failure metadata.
- LibreChat callback copy distinguishes failed evidence gates with deliverables from total failures, while
  preserving failed run semantics.
- LibreChat callback placeholder resolution updates only its own callback anchor or same-run status message;
  unrelated active placeholders return retryable `425`.

## Tests Run

- PASS: GlassHive affected Python suite collected 363 tests and exited cleanly:
  `runtime_phase1/tests/test_run_evidence.py`,
  `runtime_phase1/tests/test_mcp_server.py`,
  `runtime_phase1/tests/test_api.py`.
- PASS: LibreChat route suites:
  `server/routes/viventium/__tests__/glasshive.spec.js`,
  `server/routes/viventium/__tests__/telegram.spec.js`, and
  `server/routes/viventium/__tests__/voice.spec.js` with 112 passing tests.
- PASS: Telegram bridge focused GlassHive delivery tests: 16 passed.
- PASS: Voice gateway focused GlassHive delivery tests: 5 passed.
- PASS: Focused regressions for successful final-report status-like browser text, blank/path-shaped ids,
  centralized request-path guard, evidence-failed callback payload metadata, and failed-deliverable callback
  wording.
- PASS: Live restarted runtime rejected blank `worker_message` at the MCP boundary with no downstream
  `/workers//...` request.
- PASS: Live worker delegation through GlassHive MCP created a fresh synthetic project/worker/run after
  omitting `project_id`, completed successfully, returned no failure class, returned zero active runs after
  completion, listed the expected relative artifact, and served the artifact content exactly:
  `# GlassHive Live QA Result` plus the synthetic callback-evidence sentence.
- PASS: Playwright opened the GlassHive artifact preview page in a real browser. The visible page title was
  the Markdown filename, the page showed `text/plain` with the expected byte size, and the visible content
  matched the synthetic Markdown artifact.
- PASS: Live signed callback through the real LibreChat API updated a synthetic unfinished web placeholder
  in place with the new "worker output exists, final verification failed" wording, `unfinished=false`, and
  failed-run metadata.
- PASS: After restart, a live signed callback arriving while a synthetic unrelated
  `Generation in progress.` placeholder was active returned retryable `425`, left that placeholder
  unchanged and unfinished, and wrote no callback or delivery rows.
- PASS: Live Telegram and voice callback delivery-ledger parity used real signed callbacks, real claim
  endpoints, and real mark-sent endpoints. Both surfaces claimed one synthetic delivery row with the same
  partial-delivery wording, marked it `sent`, and the synthetic conversation/session/delivery rows were
  cleaned afterward.
- PASS: Chrome visual QA showed the synthetic web conversation with the new wording and no visible spinner.
  The screenshot was not saved in this public repo because the browser page also showed private memory-panel
  content.
- PASS: Synthetic Mongo cleanup removed the temporary conversation and messages after visual QA.
- PASS: ClaudeViv review-only second opinion confirmed the RCA and structural alignment for a
  PASS/PARTIAL local conclusion. It identified the unrelated-placeholder clobber risk and placeholder-text
  coupling guard; both now have focused tests, and the no-clobber path passed live after restart.

## Coverage Result

- `GHHOST-003`: PASS/PARTIAL. Live MCP one-shot delegation, diagnostics, completion, and artifact result
  passed; browser chat callback acceptance for this exact one-shot path remains open.
- `GHHOST-004`: PASS/PARTIAL. Provider-backed live artifact creation, download, and real-browser preview
  passed through GlassHive artifact APIs; callback artifact delivery remains an open gate.
- `GHHOST-007`: PASS/PARTIAL. Deterministic GlassHive and LibreChat callback coverage now exists, the
  restarted local web surface passed live synthetic callback QA, and Telegram/voice delivery-ledger parity
  passed. Real external Telegram send and audible voice delivery for this exact failed-evidence artifact
  case were not run to avoid side effects.
- `GHHOST-009`: PASS. Existing placeholder, blank steering, and browser-status evidence coverage remains valid
  and the broader affected suites still pass. The same pass now includes unrelated active-placeholder
  no-clobber behavior.

## Second-Opinion Reconciliation

- ClaudeViv confirmed the core RCA and local PASS/PARTIAL conclusion.
- ClaudeViv flagged a commit-scope risk: the current dirty `run_evidence.py` diff also contains a separate
  Nightly Insights/private-scratchpad workstream. That should be split or separately narrated before any
  surgical public commit.
- ClaudeViv flagged host evidence-gate regex growth as a future false-failure risk. The immediate user-facing
  damage is reduced by the new partial-delivery wording, but longer-term work should lean harder on worker
  self-checks and keep host verification advisory where possible.
- ClaudeViv flagged the unrelated-placeholder clobber edge case and placeholder-text coupling. Focused tests
  were added, the callback route now returns retryable `425` for unrelated active placeholders, and the live
  restarted runtime probe passed.

## Remaining Gaps

- Run one provider-backed end-to-end worker that produces an artifact and fails final evidence verification,
  then verify real external Telegram send and audible voice delivery show the same partial-delivery wording.
- Keep `GHHOST-003` browser callback QA open until a full one-shot delegation callback is rerun through the
  current web chat path, not only the MCP harness.
- Keep `GHHOST-004` callback artifact path open until real provider output, signed artifact links, visible
  preview, and callback delivery are verified together in one callback-driven flow.

## Public Safety

This report intentionally omits raw conversation ids, local usernames, absolute paths, private transcripts,
tokens, callback signatures, and raw database rows.
