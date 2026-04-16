# GlassHive Workspaces QA Plan

Date: 2026-04-16

## Purpose

Define the acceptance contract for the user-facing GlassHive workspace model before implementation.

This QA plan covers the least-resistance v1 product direction:

- user-facing term is `Workspace`
- primary actions are `Open workspace` and `New workspace`
- workspace reuse preserves files, browser profile, and login continuity for the same underlying
  worker
- `Duplicate workspace` is not required for v1 acceptance

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
- deep archive / restore UX beyond existing pause-resume lifecycle
- enterprise multi-tenant policy controls

## Acceptance Criteria

1. A new user can understand what a workspace is without seeing `worker_id`, `sandbox`, or raw
   runtime jargon in the main flow.
2. Reopening the same named workspace returns the user to the same files, browser profile, and
   locally preserved login state when the site still accepts that session.
3. Creating a new workspace gives the user a clean environment that does not reuse another
   workspace's browser state.
4. The main launch / resume flow presents reuse-or-new as the primary decision, not a generic list
   of runtime workers.
5. When the parent system already knows the right workspace alias for a task, it can reuse it
   without making the user manually search for a worker.
6. Pause and resume preserve continuity for the same workspace.
7. The system does not promise impossible guarantees; website-side logout, MFA, cookie expiry, or
   suspicious-login checks are still surfaced honestly.
8. `Open workspace` is the only primary reuse verb and automatically resumes a paused workspace.
9. Renaming a workspace updates the display label without silently breaking the parent-side routing
   alias.
10. `Duplicate workspace` is not exposed in the v1 UI.
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

### 4. Parent Auto-Reuse

1. Create a stable alias mapping for a known workflow such as `linkedin`.
2. Trigger the parent flow again for the same workflow.
3. Observe the selected underlying GlassHive worker.

Pass if:

- the parent reuses the correct workspace automatically
- the user does not need to manually pick from raw worker records

### 5. Non-Technical Comprehension

1. Show the launch / resume UI to a non-technical reviewer.
2. Ask:
   - how do you reopen the same environment?
   - how do you start clean?

Pass if:

- they correctly answer `Open workspace`
- they correctly answer `New workspace`
- they do not need the concepts of `sandbox` or `worker` explained

### 6. Rename Semantics

1. Create a named workspace that has a stable parent-side alias.
2. Rename the workspace from the glossy UI.
3. Trigger the parent auto-reuse flow again.

Pass if:

- the visible workspace label updates
- the same underlying workspace is still reused
- no silent routing break occurs

### 7. Duplicate Not Exposed In V1

1. Open the main launch / resume UI.
2. Inspect the primary and secondary workspace actions.

Pass if:

- `Duplicate workspace` is not shown as a v1 action
- the main decision remains reuse-or-new

### 8. Launch Failure Audit Trail

1. Trigger a synthetic or controlled failed launch after workspace creation.
2. Inspect the visible workspace/project state.

Pass if:

- the failure is explicit
- the user does not see a falsely healthy workspace that never actually launched

## Deferred For Later Review

Do not approve `Duplicate workspace` until product semantics are explicitly defined.

If it is proposed later, QA must answer:

1. does it copy files only, or files plus browser state?
2. how are cookie/session conflicts avoided?
3. how is the user warned about what is and is not copied?
