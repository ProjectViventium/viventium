# GlassHive Workspaces QA Cases

## Case ID Convention

Use stable `GHWS-NNN` IDs for glasshive workspaces cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `GHWS-001` | Workspace/project lifecycle is resumable and maps tasks to the correct worker context. | User-visible behavior matches source, docs, persisted state, and logs | GlassHive projects, runs, workspaces, callbacks | `tests/release/test_stable_dev_runtime_workflows.py` plus user-grade QA when visible | PASS 2026-05-23 for local enterprise launcher/project workspace flow; see `qa/glasshive_azure_enterprise/reports/2026-05-23-launcher-watch-enterprise-qa.md`. |
| `GHWS-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-05-23 for sanitized report; see `qa/glasshive_azure_enterprise/reports/2026-05-23-launcher-watch-enterprise-qa.md`. |
| `GHWS-003` | The modern Workspaces surface owns normal navigation and output inspection. | Brand, workspace, and output actions stay in the glossy app; inspecting a result never resumes compute. | Glass Drive Workspaces, Watch, artifact landing | UI/API regressions + Playwright | PASS 2026-08-11 in the local synthetic browser harness; exact installed-release rerun remains PARTIAL. |
| `GHWS-004` | Workspaces is a bounded multi-worker control room. | User can scan, open, and steer many workers without an offscreen poll/WebSocket storm or accidental input capture. | Workspaces overview, compact live API, desktop preview | UI/API/performance regressions + Playwright network trace | PARTIAL 2026-08-11: local 1/4/5/25 browser matrix and parallel steering pass; a real noVNC desktop stream on the exact installed release remains open. |
| `GHWS-005` | Duplicate/template capability review is durable and human controlled. | Copied work cannot run with missing or silently broadened capabilities; refresh restores exact actions. | Duplicate, templates, Library, Connections, confirmation | Runtime transaction/concurrency tests + Playwright | PARTIAL 2026-08-11: local duplicate, storage-loss restore, human waiver, atomic/crash/legacy/template and concurrency coverage pass; installed two-user execution remains open. |
| `GHWS-006` | Terminal workspace recovery stays actionable. | A failed, cancelled, or interrupted workspace keeps the Pause action named by recovery guidance, while Resume stays unavailable until a corrected follow-up exists. | Workspaces, Watch, provider-account recovery | UI policy regression + installed browser/provider mission | PARTIAL 2026-08-11: policy regression passes; exact installed failure-to-recovery rerun remains open. |

## `GHWS-001` - Core User Flow

- Requirement: Workspace/project lifecycle is resumable and maps tasks to the correct worker context.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_stable_dev_runtime_workflows.py` plus any narrower feature tests discovered during implementation.
- Last run: PASS 2026-05-23 for the local enterprise launcher/project workspace path. Playwright
  created a synthetic task, verified async completion, reopened Project workspace, restarted the
  runtime process, and verified retained workspace result state after reload.

## `GHWS-002` - Public-Safe Evidence Record

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
- Last run: PASS 2026-05-23. Public report is synthetic and sanitized.

## `GHWS-003` - Modern Navigation And Non-Mutating Output

- Requirement: normal users remain in Glass Drive and can inspect output directly.
- Risk covered: brand text is inert, a primary action exposes `/ui/projects/*`, a hosted delivery
  exposes an unusable worker-local `file:///workspace/...` target, two labels open the same Watch
  page, or clicking a completed result unexpectedly resumes compute.
- Steps: open Home, Workspaces, Watch, and a completed artifact; use brand, Open workspace, Open
  output, and Download by pointer and keyboard; complete run A, observe run B start elsewhere, then
  complete B without rebuilding the grid; inspect lifecycle calls and refresh.
- Expected result: brand returns Home/Workspaces; one primary workspace action opens Watch; output
  uses the exact scoped artifact/result action; B replaces A's links after its completion; no
  inspection sends resume/start/message. Output disclosure exposes matching `aria-controls` and
  changes View/Hide copy truthfully.
- Forbidden result: normal navigation reaches the legacy runtime UI, exposes raw ids/tokens/JSON or
  a worker-local file URL, or restarts work without an explicit Continue/Send action.
- Evidence: browser URL/DOM, lifecycle network log, worker state before/after, artifact bytes/headers,
  console, narrow-layout screenshots.
- Last run: PASS 2026-08-11 in a real local Chromium session with synthetic state. Brand and Watch
  returned to the modern app; the preview opened Watch by pointer and the one visible Open workspace
  action did so by keyboard; run B replaced run
  A's delivery after a running transition without grid rebuild; keyboard View/Hide exposed matching
  `aria-controls`; Open rendered B, Download remained distinct, and the lifecycle ledger stayed empty.
  The exact installed-release rerun remains open.

## `GHWS-004` - Bounded Multi-Worker Control Room

- Requirement: Workspaces presents an executive overview without unbounded live surfaces.
- Risk covered: every card opens an interactive noVNC socket, offscreen cards poll forever, or card
  rerenders duplicate streams and capture user input.
- Steps: exercise 1, 4, 5, and 25 mixed-state workspaces; scroll/filter/resize/refresh; inspect
  requests, WebSockets, focus, preview interaction, state groups, and click-through behavior. Resolve
  an enterprise opaque desktop-preview ref and verify its stored redirect retains `preview=1`.
- Expected result: only visible cards poll compact state, calls do not overlap, no more than three
  visible active cards receive view-only previews, signed and unsigned previews are both view-only,
  and every other card has truthful state/output. No dead artifact thumbnail is promised where the
  runtime has only a safe landing-page URL rather than raw image bytes.
- Forbidden result: offscreen storm, more than the configured preview bound, duplicate sockets,
  pointer/keyboard capture, or a fabricated desktop thumbnail.
- Evidence: Playwright network/WebSocket counts, DOM/card states, browser performance trace, backend
  compact/full request counters, console, mobile/tablet/desktop screenshots.
- Last run: PARTIAL 2026-08-11. Real local Chromium exercised 1, 4, 5, and 25 cards, compact
  visible-only refresh, the three-preview bound, 320/768/1024 layouts, and parallel steering of two
  workers without lifecycle mutation. Active-to-idle transition also hid the preview overlay and
  exposed a keyboard Resume action that emitted one exact lifecycle request. The synthetic harness had no noVNC backend, so a real desktop
  stream and installed-release network trace remain open.

## `GHWS-005` - Atomic Duplicate/Template Reapproval

- Requirement: copied capability references require an exact destination decision before execution.
- Risk covered: a legacy route, crash window, refresh, template instantiation, scope widening, or
  browser-storage loss permits execution with global/fallback credentials.
- Steps: duplicate through canonical and legacy routes; pause file copy mid-flight; instantiate a
  template; refresh/restart; place the copied workspace beyond the first 100 favorite catalog rows;
  attempt execution before decisions; omit and widen requested Library scopes; approve the exact
  source scopes/select a concrete provider; duplicate an account-less preferred-fallback workspace;
  disconnect and forget a selected account and repeat under preferred and required policy;
  confirm Continue without for a non-transferable legacy connection/provider grant; race two
  confirmations; repeat as another owner.
- Expected result: the new workspace is born review-pending, server catalog restores stable action
  ids, exact owner lookup restores review beyond the first catalog page, execution returns conflict
  until every action resolves, omitted scopes bind to the copied subset, widened scopes fail,
  account-less/disconnected/forgotten preferred fallback remains runnable, an unready required
  selection blocks copy with reconnect-or-choose recovery, provider selection cannot be waived, non-transferable
  legacy grants never claim setup, and one human confirmation resolves one action once.
- Forbidden result: action disappears on message dispatch, sessionStorage is the authority, direct
  connection grant is fabricated, a legacy route bypasses the gate, an unready account creates an
  impossible review, or one user's labels reach another.
- Evidence: visible review/confirm UI, refresh state, API conflicts/success, persisted report/grants,
  concurrent confirmation result, two-owner isolation, no fallback provider execution.
- Last run: PARTIAL 2026-08-11. Local Chromium duplicated a workspace, lost tab storage, restored
  the exact review from the server catalog, opened the human-confirmation page, and resolved one
  waivable action. Atomic/crash/legacy/template/concurrency tests pass; installed two-user execution
  remains open.

## `GHWS-006` - Terminal Workspace Recovery

- Requirement: recovery instructions and available actions must agree on every normal user surface.
- Risk covered: a real provider mission reports that its sandbox isolation is stale and tells the
  user to pause, while both Workspaces and Watch hide Pause because the latest run is failed.
- Steps: run a provider-backed task against a deliberately stale synthetic sandbox; observe the
  failed card in Workspaces and Watch; activate Pause by pointer and keyboard; if the account becomes
  action-required, use Check connection; retry with a corrected follow-up; refresh after completion.
- Expected result: failed/cancelled/interrupted cards show one enabled Pause action and no Resume;
  Pause releases the stale substrate; Check connection restores Ready without setup when credentials
  remain valid; the retry creates a clean substrate and completes with a durable output.
- Forbidden result: guidance names an action that is hidden or disabled, Pause restarts the old run,
  output inspection mutates lifecycle, or account recovery requires unnecessary OAuth.
- Evidence: visible controls and messages, lifecycle request count, account state, container/mount
  correlation, completed output, refresh persistence, and exact installed release provenance.
- Last run: PARTIAL 2026-08-11. The installed candidate reproduced the hidden-Pause failure and a
  no-OAuth Check connection recovery; the corrected exact-release browser rerun remains required.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Glasshive Workspaces. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `GHWS-UC-001` | On GlassHive projects, runs, workspaces, callbacks, verify that workspace/project lifecycle is resumable and maps tasks to the correct worker context. | owning requirement for `GHWS-001` / `GHWS-001` | GlassHive projects, runs, workspaces, callbacks | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHWS-001. | User-visible behavior matches source, docs, persisted state, and logs | PASS 2026-05-23 local enterprise project/workspace flow. |
| `GHWS-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `GHWS-002` / `GHWS-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHWS-002. | The user sees an honest setup, retry, or degraded-state result for GHWS-002; no fake success is accepted. | PASS 2026-05-23 sanitized report. |
| `GHWS-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `GHWS-002` / `GHWS-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHWS-002. | GHWS-002 remains correct after the persistence or parity step and final wording matches evidence. | PASS 2026-05-23 after runtime reload and report update. |
| `GHWS-UC-004` | From Workspaces, open several workers, inspect a completed output, and return Home without entering the legacy runtime UI or resuming work. | `GHWS-003` | Glass Drive Workspaces/Watch/artifact | Browser URL/network/state + artifact headers | Smooth modern navigation; output is direct and non-mutating. | PASS 2026-08-11 local synthetic Chromium; installed release open. |
| `GHWS-UC-005` | Monitor and steer 1/4/5/25 active, starting, completed, failed, and unavailable workers from one overview. | `GHWS-004` | Glass Drive Workspaces | Network/WebSocket counts, DOM, compact/full API logs | Bounded view-only previews and truthful cards with no offscreen storm. | PARTIAL 2026-08-11: local browser matrix/parallel steer pass; installed live desktop stream open. |
| `GHWS-UC-006` | Duplicate or instantiate a workspace with copied capabilities, refresh, resolve or explicitly waive each exact action, then run. | `GHWS-005` | Workspaces, Library, Connections, confirmation | Browser/API/DB/concurrency evidence | Execution is blocked until server-owned review completes; no silent fallback or scope widening. | PARTIAL 2026-08-11: local browser restore/waiver plus automated server gates pass; installed two-user run open. |
| `GHWS-UC-007` | From a failed/cancelled/interrupted workspace, pause the stale sandbox named by recovery guidance, repair the account if needed, and retry. | `GHWS-006` | Workspaces, Watch, Connections | Browser controls/network, lifecycle state, provider account, container/mount state, output | Pause is visible and non-resuming; repair is setup-free when credentials remain valid; retry completes and persists. | PARTIAL 2026-08-11: escaped hosted failure and policy regression recorded; corrected installed-release rerun open. |
