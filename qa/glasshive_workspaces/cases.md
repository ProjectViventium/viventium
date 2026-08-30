# GlassHive Local Worker-Workspace Lifecycle QA Cases

These `GHWS-*` cases are the local worker-workspace foundation. They do not replace hosted personal
control-plane cases under [`qa/glasshive-user-control-plane/`](../glasshive-user-control-plane/).

## Case ID Convention

Use stable `GHWS-NNN` IDs for glasshive workspaces cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `GHWS-001` | Workspace/project lifecycle is resumable and maps tasks to the correct worker context. | User-visible behavior matches source, docs, persisted state, and logs | GlassHive projects, runs, workspaces, callbacks | `tests/release/test_stable_dev_runtime_workflows.py` plus user-grade QA when visible | PARTIAL 2026-08-29 documentation audit: embedded notes describe a 2026-05-23 browser run, but the cited dated report is absent; rerun the current candidate before PASS. |
| `GHWS-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | FAIL 2026-08-29 documentation audit: the cited public report is absent, so the reproducible-evidence requirement is not met. |
| `GHWS-003` | First-time workspace entry uses product language and primary actions | User starts without worker or sandbox concepts | Glass Drive launch and watch UI | Glass Drive server tests plus real browser QA | PARTIAL 2026-04-16: embedded execution notes prove the labels and one launch/watch handoff; no dated report or current-candidate rerun exists. |
| `GHWS-004` | Reopening a paused workspace preserves its identity and state | User returns to the same files, profile, and running workspace | Launch UI, runtime lifecycle, workspace state | Runtime lifecycle tests plus real browser/state QA | PARTIAL 2026-04-16: embedded notes prove same-worker pause/resume and a new queued run; browser-profile continuity and a dated report remain absent. |
| `GHWS-005` | A new workspace is isolated from every existing workspace | User starts clean without inheriting another workspace's files or browser identity | Launch UI, filesystem, browser profile | Sandbox isolation tests plus real two-workspace QA | PARTIAL 2026-04-16: duplicate-copy boundaries were sampled, but two independently new workspaces and browser-profile isolation were not proved. |
| `GHWS-006` | Duplicate copies approved files/context into a fresh identity only | User branches useful work without cloning private browser/home state | Launch UI, filesystem, runtime audit | Runtime/API and sandbox tests plus real browser/state QA | PARTIAL 2026-04-16: embedded notes prove a new worker/project, copied workspace marker, excluded home marker, and `worker.duplicated`; no dated report or current rerun exists. |
| `GHWS-007` | Parent routing reuses the known workspace alias | User is returned to the right workspace without choosing a raw worker | Parent launch, alias map, runtime audit | Runtime/API tests plus real parent-flow QA | NOT RUN — cataloged 2026-08-29: same-worker manual reopen exists, but no recorded parent-known-alias journey proves automatic selection. |
| `GHWS-008` | Non-technical users understand Open, Duplicate, and New | User can choose reopen, branch, or clean start without explanation of runtime internals | Launch UI | Moderated comprehension QA | NOT RUN — cataloged 2026-08-29: labels were inspected, but no non-technical reviewer result is recorded. |
| `GHWS-009` | Failed launch remains visibly failed and auditable | User sees an explicit failure instead of a healthy orphan | Launch/watch UI, runtime audit | Failure-injection tests plus real browser/state QA | NOT RUN — cataloged 2026-08-29: no controlled failed-launch user path is recorded. |

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
- Last run: PARTIAL 2026-08-29 documentation audit. The embedded 2026-05-23 notes say Playwright
  created a synthetic task, verified async completion, reopened Project workspace, restarted the
  runtime process, and verified retained workspace result state after reload. The cited dated
  report is absent, so these notes do not support a current PASS.

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
- Last run: FAIL 2026-08-29 documentation audit. The cited dated public report is absent; embedded
  summary text does not satisfy the reproducible-evidence requirement.

## `GHWS-003` - First-Time Workspace Entry

- Requirement: a first-time user sees `Workspace`, `Open workspace`, `Duplicate workspace`, and
  `New workspace` without worker IDs or sandbox language in the primary flow.
- Steps: open Glass Drive with no workspace context; create a new workspace; follow the watch handoff.
- Expected result: the user reaches the desktop-first workspace view without learning runtime terms.
- Forbidden result: the primary flow asks the user to select a worker, sandbox, or opaque runtime ID.
- Evidence to capture: launch and watch UI, route, runtime row, console/network state, and dated report.
- Last run: PARTIAL 2026-04-16. Embedded README notes prove the primary labels and one watch handoff;
  the dated report and current-candidate rerun are absent.

## `GHWS-004` - Reopen Existing Workspace

- Requirement: opening a paused named workspace resumes the same underlying workspace and preserves
  its files and browser profile when the remote site still accepts the session.
- Steps: create a workspace and marker; pause; use `Open workspace`; compare identity, files, profile,
  lifecycle events, and new run state.
- Expected result: the same workspace resumes with its state intact and without raw worker wording.
- Forbidden result: silent replacement, clean-state launch, false login guarantee, or lost marker.
- Evidence to capture: before/after identity, marker hash, browser-profile state, lifecycle events, UI,
  and dated report.
- Last run: PARTIAL 2026-04-16. Same-worker pause/resume and a new queued run are recorded; full
  browser-profile continuity and independent report evidence are missing.

## `GHWS-005` - New Workspace Isolation

- Requirement: each new workspace receives independent files and browser/profile state.
- Steps: create two new workspaces; place distinct files and synthetic browser state in each; inspect
  both directions for leakage.
- Expected result: neither workspace inherits or exposes the other's state.
- Forbidden result: reused home/profile, copied session, cross-workspace file, or shared opaque ID.
- Evidence to capture: two workspace identities, file hashes, profile roots, browser state, and audit.
- Last run: PARTIAL 2026-04-16. The embedded duplicate check sampled one home-state exclusion, but
  two independently new workspaces and full browser isolation were not run.

## `GHWS-006` - Safe Duplicate Workspace

- Requirement: duplicate creates a fresh workspace identity, copies approved workspace files/context,
  and does not silently copy browser-session or home state.
- Steps: seed approved workspace and home/profile markers; duplicate from the UI; compare source and
  destination identities, files, home/profile state, and audit events.
- Expected result: the approved marker exists under a new worker/project; private home/profile state
  is absent; `worker.duplicated` is recorded.
- Forbidden result: source reopen, copied credentials/cookies/home state, missing approved files, or
  duplicate launch without an audit event.
- Evidence to capture: source/destination IDs, hashes, excluded-state check, UI, audit, and dated report.
- Last run: PARTIAL 2026-04-16. Embedded notes prove the narrow marker/new-identity path; the dated
  report and current-candidate rerun are absent.

## `GHWS-007` - Parent Auto-Reuse

- Requirement: when the parent already has a stable workflow-to-workspace alias, it selects that
  workspace without asking the user to search raw workers.
- Steps: bind a synthetic workflow alias; invoke the parent flow twice; compare selected workspace,
  files, run records, and visible wording.
- Expected result: the second invocation reuses the bound workspace automatically and visibly.
- Forbidden result: random/new workspace, raw worker picker, or alias pointing to another workspace.
- Evidence to capture: alias map, parent request/result, workspace ID, runtime audit, and user view.
- Last run: NOT RUN — cataloged 2026-08-29. The recorded manual reopen does not prove parent-driven alias reuse.

## `GHWS-008` - Non-Technical Comprehension

- Requirement: a non-technical reviewer can identify reopen, branch, and clean-start actions from the
  interface alone.
- Steps: show the launch UI without coaching; ask how to reopen, branch, and start clean; record answers.
- Expected result: the reviewer chooses Open, Duplicate, and New and needs no worker/sandbox explanation.
- Forbidden result: reviewer confusion, runtime jargon dependency, or ambiguous action semantics.
- Evidence to capture: synthetic test script, answers, observed hesitation/confusion, viewport, and UI.
- Last run: NOT RUN — cataloged 2026-08-29. Label inspection is not a comprehension study.

## `GHWS-009` - Launch Failure Audit Trail

- Requirement: a launch failure remains explicit in both the user surface and durable audit state.
- Steps: inject a controlled failure after workspace creation; inspect launch/watch UI, workspace and
  project status, events, logs, and retry behavior.
- Expected result: one actionable failure is visible and the workspace never appears healthy.
- Forbidden result: healthy orphan, missing audit event, infinite spinner, or retry that duplicates work.
- Evidence to capture: visible error, durable state/event, bounded logs, retry outcome, and dated report.
- Last run: NOT RUN — cataloged 2026-08-29. No controlled failed-launch user journey is recorded.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Glasshive Workspaces. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `GHWS-UC-001` | On GlassHive projects, runs, workspaces, callbacks, verify that workspace/project lifecycle is resumable and maps tasks to the correct worker context. | owning requirement for `GHWS-001` / `GHWS-001` | GlassHive projects, runs, workspaces, callbacks | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHWS-001. | User-visible behavior matches source, docs, persisted state, and logs | PARTIAL 2026-08-29 documentation audit: historical notes exist, but the cited dated report is absent. |
| `GHWS-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `GHWS-002` / `GHWS-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHWS-002. | The user sees an honest setup, retry, or degraded-state result for GHWS-002; no fake success is accepted. | FAIL 2026-08-29 documentation audit: no dated public report is present. |
| `GHWS-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `GHWS-002` / `GHWS-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHWS-002. | GHWS-002 remains correct after the persistence or parity step and final wording matches evidence. | FAIL 2026-08-29 documentation audit: the public report and rerun evidence are absent. |
| `GHWS-UC-004` | Start a workspace for the first time without learning worker or sandbox concepts. | `GHWS-003` | Glass Drive launch and watch UI | UI, route, runtime row, console/network | Workspace-first desktop opens from clear primary actions. | PARTIAL 2026-04-16: labels and one handoff are embedded; dated/current evidence is absent. |
| `GHWS-UC-005` | Pause and reopen the same workspace with its files and valid browser state. | `GHWS-004` | Launch UI and workspace desktop | Identity, files, profile, lifecycle events, run state | The same workspace resumes honestly. | PARTIAL 2026-04-16: same-worker pause/resume passed; full profile continuity is unproved. |
| `GHWS-UC-006` | Create two clean workspaces and verify neither inherits the other's state. | `GHWS-005` | Launch UI and two workspace desktops | IDs, files, profiles, browser state, audit | Both environments remain isolated. | PARTIAL 2026-04-16: one duplicate home-state exclusion exists; the full two-new-workspace path is unrun. |
| `GHWS-UC-007` | Duplicate useful workspace files into a fresh workspace without copying private session state. | `GHWS-006` | Launch UI and source/destination desktops | IDs, hashes, excluded state, audit | Approved context is copied; home/profile state is not. | PARTIAL 2026-04-16: narrow marker/new-identity proof exists without a dated/current report. |
| `GHWS-UC-008` | Repeat a known parent workflow and return automatically to its bound workspace. | `GHWS-007` | Parent flow and workspace desktop | Alias, selected ID, runs, audit, UI | Correct reuse occurs without a raw worker picker. | NOT RUN — cataloged 2026-08-29. |
| `GHWS-UC-009` | Choose reopen, branch, or clean start from the launch UI without coaching. | `GHWS-008` | Moderated launch-UI review | Reviewer answers and UI state | A non-technical reviewer correctly selects Open, Duplicate, and New. | NOT RUN — cataloged 2026-08-29. |
| `GHWS-UC-010` | Trigger a controlled launch failure, inspect it, and retry. | `GHWS-009` | Launch/watch UI and runtime audit | Visible error, state, events, logs, retry | Failure stays explicit and no healthy orphan or duplicate appears. | NOT RUN — cataloged 2026-08-29. |
