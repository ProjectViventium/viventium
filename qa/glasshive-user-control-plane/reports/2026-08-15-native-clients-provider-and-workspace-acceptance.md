# GlassHive Native Clients, Provider Routes, and Workspace Acceptance

Date: **2026-08-15**
Result: **PASS for the tested hosted release; broader completion remains PARTIAL**

## Exact build tested

- Parent source: `c4f01c9592b6b960297a2058ae7339c6e70742d4`
- GlassHive source: `4d4a3545fca9921148d2c3113bc313e527a78f3b`
- Installed release: `glasshive-20260815-workspace-control-room-15`
- The nested commit was pinned by the exact parent manifest, staged as a sealed release, activated as
  one runtime/UI/MCP group, held for browser acceptance, and committed only after the checks below.

## What was actually run

### Browser and identity

- Used the already-open organization Edge profile selected for GlassHive QA.
- Completed the organization sign-in and returned to the intended GlassHive page.
- Navigated Run project, Workspaces, Connections, Library, Schedules, and Activity.
- Refreshed the browser after delivered-file inspection and retained the signed-in session and output.

### Native client setup and MCP

- Connections showed one plain Automatic instruction and a Manual fallback.
- The visible Codex setup used the official GlassHive marketplace/plugin commands; no callback URL
  was presented as a user action.
- Automatic/Manual keyboard switching worked.
- A fresh Codex process made exactly one `workspace_list` MCP call and returned its owner-scoped
  catalog; its transcript contained no attempted or denied config, catalog, nested-client, or polling
  action.
- A fresh Claude Code process made exactly one successful `workspace_list` MCP call and returned its
  own owner-scoped catalog. The first headless attempt selected only that tool but was denied by the
  ordinary permission boundary. The successful retry explicitly allowed only `workspace_list`, the
  headless equivalent of the normal one-time interactive approval. It proves the one-call connection
  path, but the narrow allowlist is not evidence that Claude would decline unrelated tools if they
  were also preapproved.

### Personal and deployment-managed worker routes

- Launched one deployment-managed Codex workspace from the browser.
- The worker created `work-ai-check.txt` containing exactly `WORK_AI_OK`; Watch reached Completed,
  Open displayed the exact 10-byte file, and refresh preserved it.
- Launched one personal-subscription Codex workspace with `Only my account; never fall back`.
- The worker created `personal-ai-check.txt` containing exactly `PERSONAL_AI_OK`; Watch reached
  Completed, Open displayed the exact 14-byte file, and refresh preserved it.
- Workspaces displayed the deployment route as organization-managed and the personal route as the
  ready personal account. No personal route was silently substituted for the deployment run.

### Workspace and schedule controls

- Renamed the deployment workspace to `QA Work AI route` and observed the new human name.
- Duplicated it and observed one fresh `QA Work AI route copy` without starting compute.
- Opened the existing paused daily schedule, requested one run, viewed its history, refreshed, and
  observed the occurrence progress from Queued to Completed.

### Runtime, authorization, and isolation correlation

- Runtime, UI, and MCP health returned the exact release/parent/component triplet.
- The deployment-provider bridge was committed; its provider file was `root:root 0600` and its
  runtime-only systemd drop-in was `root:root 0644`.
- Both tested runs had terminal Completed run rows with no recorded run error.
- The deployment-managed run had no personal provider-account lease.
- The personal run had a personal lease and released it after completion.
- The schedule row was Completed; active runs, provider requests, unexpired leases, and delivering
  callbacks were all zero.
- One running rootless container remained and was mapped to the retained, idle deployment workspace;
  it was not orphaned and had no active run. This is compatible with persisted/resumable workspace
  behavior.
- Runtime and MCP logs after readiness contained no provider-auth failure, `invalid_target`, Entra
  mismatch, traceback, or critical error. UI connection tracebacks occurred only in the short
  pre-readiness startup window; bounded release health converged and the post-readiness window was
  clean.
- Stable ingress remained unchanged while the canary was tested.

## Acceptance decision

The release was explicitly accepted only after all checks above. The acceptance helper re-proved
local release health, canary edge provenance, and unchanged stable ingress, then recorded
`activation=committed_after_explicit_browser_acceptance`.

This closes the prior deployment-managed upstream-401 incident for the tested route and proves the
personal-account route stayed isolated and functional in the same installed release.

## What this does not prove

- A real SharePoint or other connected-service sign-in and worker tool call.
- A real personal Claude **worker** subscription; Claude Code was proven here as an external MCP
  controller.
- A second user's browser/MCP/provider denial matrix.
- Full reconnect, disconnect, forget, rotation, and contention for two healthy personal accounts.
- A clock-triggered occurrence across restart/DST/expiry; this run used the visible **Run now** action.
- Clean public install, full database restore, upgrade from every supported predecessor, or rollback
  after this committed acceptance.
- A real sourced Library package install/upgrade/rollback used by a worker.

Those remain PARTIAL or PENDING in the living coverage matrix and are not implied by this PASS.

## Operational follow-up before another rollout

- The committed rollback snapshot consumes enough space that the next release is expected to fail
  the existing disk-safety gate unless the reviewed committed-snapshot pruning procedure runs first.
- The retained idle Work AI container is correct for this accepted resumable workspace, but the next
  activation intentionally refuses any `wpr-*` container. Pause/clear that QA workspace through the
  supported lifecycle before the next rollout.

These are next-rollout prerequisites, not defects in the accepted user flow.

## Final automated and review evidence

- Complete Glass Drive UI `test_server.py`: PASS.
- Focused runtime public-compatibility, readiness, dispatch/steer, schedule, bootstrap, and real
  command-environment slice: **23 passed**.
- Parent compiler/provider-artifact and installed systemd ownership slice: **7 passed**.
- Markdown relative links, public-safety scan, and parent/nested `git diff --check`: PASS.
- Independent visible Claude review: **GO**, no P0/P1; it agreed the exact release acceptance and
  broader PARTIAL classification are honest.
