# GlassHive Workspaces QA Plan

Date: 2026-04-16

## Purpose

Define the acceptance contract for the user-facing GlassHive workspace model before implementation.

This QA plan covers the least-resistance v1 product direction:

- user-facing term is `Workspace`
- primary actions are `Open workspace`, `Duplicate workspace`, and `New workspace`
- workspace reuse preserves files, browser profile, and login continuity for the same underlying
  worker
- workspace duplication copies files/context into a new workspace without cloning browser-session
  state by default

## Scope

In scope:

- workspace naming in the glossy/operator UI
- reuse flow for existing named workspaces
- new clean workspace flow
- parent-side alias-to-worker reuse behavior
- pause/resume continuity
- user comprehension for non-technical flows

Out of scope for v1:

- browser-session cloning across duplicate workspaces
- shared cross-worker browser identity
- workspace rename UX
- deep archive / restore UX beyond existing pause-resume lifecycle
- enterprise multi-tenant policy controls

## Acceptance Criteria

1. A new user can understand what a workspace is without seeing `worker_id`, `sandbox`, or raw
   runtime jargon in the main flow.
2. Reopening the same named workspace returns the user to the same files, browser profile, and
   locally preserved login state when the site still accepts that session.
3. Duplicating a workspace creates a new workspace with copied files/context but does not silently
   clone browser-session state.
4. Creating a new workspace gives the user a clean environment that does not reuse another
   workspace's browser state.
5. The main launch / resume flow presents open-duplicate-new as the primary decision, not a generic list
   of runtime workers.
6. When the parent system already knows the right workspace alias for a task, it can reuse it
   without making the user manually search for a worker.
7. Pause and resume preserve continuity for the same workspace.
8. The system does not promise impossible guarantees; website-side logout, MFA, cookie expiry, or
   suspicious-login checks are still surfaced honestly.
9. `Open workspace` automatically resumes a paused workspace.
10. `Duplicate workspace` is exposed in the v1 UI with the documented safe semantics.
11. Failed launches still leave an explicit failure trail instead of a healthy-looking orphan
    workspace.

## Test Cases

### 1. First-Time User

1. Open the GlassHive glossy UI.
2. Confirm the main flow presents `New workspace` and does not require understanding worker IDs.
3. Create a workspace.
4. Confirm the watch flow lands in the desktop-first view.

Pass if:

- the user can start without technical explanation
- the primary terminology is `Workspace`

### 2. Reopen Existing Workspace

1. Create a named workspace.
2. Add a file in the workspace.
3. Log into a website inside the browser if possible with synthetic or safe test credentials.
4. Pause the workspace.
5. Reopen that same workspace.

Pass if:

- the file is still present
- the browser profile is preserved for the same workspace
- the UI presents this as reopening a workspace, not resuming an opaque worker ID

### 3. New Workspace Isolation

1. Create `Workspace A`.
2. Create `Workspace B`.
3. Add different files in each.
4. Verify the browser/profile state is isolated per workspace.

Pass if:

- each workspace has its own persistent state
- `New workspace` does not accidentally inherit another workspace's browser identity

### 4. Duplicate Workspace

1. Create `Workspace A`.
2. Add a file or small project artifact in `Workspace A`.
3. Duplicate `Workspace A` from the glossy UI.
4. Confirm the new duplicated workspace launches.
5. Confirm the file/artifact exists in the duplicate.

Pass if:

- the duplicate has the copied workspace files/context
- the duplicate is a new workspace, not a silent reopen of the source
- browser-session state is not implicitly cloned

### 5. Parent Auto-Reuse

1. Create a stable alias mapping for a known workflow such as `linkedin`.
2. Trigger the parent flow again for the same workflow.
3. Observe the selected underlying GlassHive worker.

Pass if:

- the parent reuses the correct workspace automatically
- the user does not need to manually pick from raw worker records

### 6. Non-Technical Comprehension

1. Show the launch / resume UI to a non-technical reviewer.
2. Ask:
   - how do you reopen the same environment?
   - how do you start clean?

Pass if:

- they correctly answer `Open workspace`
- they understand `Duplicate workspace` as “branch from this one”
- they correctly answer `New workspace`
- they do not need the concepts of `sandbox` or `worker` explained

### 7. Launch Failure Audit Trail

1. Trigger a synthetic or controlled failed launch after workspace creation.
2. Inspect the visible workspace/project state.

Pass if:

- the failure is explicit
- the user does not see a falsely healthy workspace that never actually launched

## Deferred For Later Review

If duplicate semantics are expanded later, QA must answer:

1. does it still default to files/context only, or can it optionally copy browser state?
2. how are cookie/session conflicts avoided if session cloning is ever introduced?
3. how is the user warned about what is and is not copied?
4. when rename is added, how is the display-label update kept separate from the stable routing alias?

## Latest Execution

Date executed: 2026-04-16

Execution summary:

1. Restarted the live stack with `bin/viventium stop` and `bin/viventium start`.
2. Verified the glossy UI bootstrap on `http://127.0.0.1:8780` now exposes:
   - `Open workspace`
   - `Duplicate workspace`
   - `New workspace`
3. Launched a new synthetic workspace through the glossy UI using:
   - project: `QA Workspace New Flow 2026-04-16 15:30`
   - success criteria: `The live watch page opens on the workspace desktop.`
4. Verified the watch handoff landed on `/watch/<worker_id>?surface=desktop` and rendered the
   workspace-first copy plus the `Open project workspace` action.
5. Paused that workspace, then relaunched via the glossy launch endpoint with
   `workspace_option=open:<worker_id>`.
6. Confirmed the same worker returned to `running` and the runtime recorded:
   - `worker.paused`
   - `worker.resumed`
   - a new `run.queued`
7. Added a synthetic workspace marker file and a separate synthetic home-state marker to the source
   workspace.
8. Launched `Duplicate workspace` through the glossy launch endpoint and confirmed:
   - the duplicate got a new worker ID and project ID
   - the duplicated workspace contained the workspace marker file
   - the duplicated workspace did not contain the home-state marker
   - the runtime recorded `worker.duplicated`
9. Verified the duplicated live desktop runtime still started the embedded terminal surface by
   inspecting the running container for:
   - `xterm ... -T WPR Live Run`
   - attached `screen` session for the active run

Automated checks:

1. `viventium_v0_4/GlassHive/frontends/glass-drive-ui/.venv/bin/python -m pytest viventium_v0_4/GlassHive/frontends/glass-drive-ui/tests -q`
2. `viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python -m pytest viventium_v0_4/GlassHive/runtime_phase1/tests -q`

Result:

- PASS: user-facing naming is `Workspace`
- PASS: primary flow is `Open workspace`, `Duplicate workspace`, `New workspace`
- PASS: `Open workspace` automatically resumes a paused workspace
- PASS: duplicate copies workspace files/context into a new workspace
- PASS: duplicate does not copy the tested home-state marker
- PASS: desktop-first watch remains the default handoff
- PASS: live terminal remains present inside the desktop-first runtime

Evidence note:

- QA artifacts were kept text-first to avoid committing screenshots that could reveal local runtime
  workspace titles or operator-specific state from the live environment.
