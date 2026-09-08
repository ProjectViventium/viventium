# GlassHive

## User promise

GlassHive may serve as an authorized Main provider or as durable worker execution. Both paths must
produce useful results, preserve the user's full task, and expose honest fallback and recovery.

## Provider and workspace

### Provider outcome

- **GHM-001 / GHM-004:** GlassHive can be selected as the real Main or cortex provider; conversation
  and mission paths each meet the outcome metric and expose fallback truth.

### Provider contract

- **GHM-002 / GHM-003:** One selected authoring intelligence receives the authorized identity,
  context, workspace, model, tools, memory, and Feelings for the turn and reuses canonical per-user
  LIFE without duplicating context or runs.

### Non-goals

- **GHM-005:** Implement the concrete provider path without speculative platform expansion.

### Identity and connections

- **GHU-001:** Users get standards-based sign-in under the deployment's configured account-creation
  policy.
- **GHU-003 / GHU-004:** Users can connect, verify, renew, reconnect, or remove a personal supported
  provider without changing another user or the deployment default. Contention, quota, and expiry
  each provide one truthful recovery action.

### Tenant safety

- **GHU-002:** Persistent workspace and state are isolated by enforced owner and tenant boundaries.

### Workspace experience

- **GHU-006 / GHU-007:** Workspaces have clear editable names and are easy to find, favorite, link,
  reopen, and reuse at one canonical URL without needless reauthorization.
- **GHU-013:** Home opens the canonical dashboard. Opening a result shows the exact scoped artifact
  without restarting compute; Watch and Continue remain explicit actions.
- **GHU-009:** The primary workspace UI is sparse, accessible, responsive, and truthful without raw
  terminal output.

### Workspace control

- **GHU-014:** Users can view, Steer, and control parallel workers from one bounded workspace
  surface; inactive cards remain truthful without unbounded streams.

### External client setup

- **GHU-015:** Native clients offer an accessible automatic setup path plus advanced manual setup,
  with end-to-end reconnect and recovery.

## Mission boundary

### Mission envelope

- **PW-054:** The mission receives the complete task, constraints, inputs, exclusions, output shape,
  and success condition without semantic loss.
- **PW-055 / PW-056:** Context and capabilities are limited to what the mission needs and exclude
  unrelated private data, credentials, host secrets, and sibling context.
- **PW-057:** Descendants may inherit but never expand authority; a missing broker never permits a
  native bypass.

### Native harness boundary

- **GHU-005:** Use native harness capabilities inside the isolated workspace. The host does not copy
  credentials or reimplement connector behavior.

### Interaction

- **GHU-008:** A short request starts the smallest goal-relevant action and reports work without
  exposing plumbing.

### Typed capabilities

- **PW-059:** Routes, models, effort, fallback, surfaces, and capabilities come from current typed
  metadata, not prose or tool-name inference.

## Inputs, results, and fallback

### Artifact provenance

- **PW-060 / PW-061:** Inputs preserve exact identity, bytes, order, grouping, captions, and owner
  scope. Missing, unreadable, or unauthorized bytes fail truthfully; captions never replace files.

### Result delivery

- **PW-062 / PW-063 / PW-064:** One authoritative envelope returns text, sources, structured output,
  files, media, and artifacts exactly once. Results remain available at the origin and Active Work;
  unsupported rendering gets a stable handoff, and absent, duplicate, dead, or foreign artifacts
  are never claimed.

### Fallback and authority

- **PW-065 / PW-066:** Fallback preserves mission, workspace, controls, inputs, capabilities, output
  ability, and authority ceiling or reports blocked. Admission mints authority; revalidation cannot
  expand it and expired or revoked authority pauses for input.
- **PW-067:** Long-running authority is time-bounded by
  `config.schema.yaml` → `integrations.glasshive.orchestration.authorization_horizon_seconds`;
  `scripts/viventium/config_compiler.py` → `resolve_glasshive_orchestration_settings` validates and
  compiles it to `VIVENTIUM_GLASSHIVE_AUTHORIZATION_HORIZON_SECONDS`. Resuming after expiry needs
  user authorization. The schema range is 60–86,400 seconds; deployments choose the value.

### Lifecycle truth

- **PW-113:** Project lifecycle comes only from provider events. Unsupported child visibility stays
  absent while observed root output remains available.

## Owners and QA

- Provider and mission runtime: `viventium_v0_4/GlassHive/`
- Host brokerage and user presentation: `viventium_v0_4/LibreChat/`
- Mission lifecycle architecture: [Parallel Work runtime](../../architecture/parallel-work-runtime.md)
- QA: `qa/glasshive-core-provider/`, `qa/glasshive-mcp-capability-broker/`,
  `qa/glasshive-user-control-plane/`, `qa/glasshive_host_workers/`, and related GlassHive folders

Real acceptance uses an owner-scoped installed account, a natural request, provider and broker
evidence, visible progress, exact artifact delivery, reconnect, restart, and fallback or blocker
wording. A reachable host endpoint alone does not pass.

## Detailed contracts

- [GlassHive Workstation Sandbox Runtime](../48_GlassHive_Workstation_Sandbox_Runtime.md)
- [GlassHive Workflows Self Healing and Feature Requests](../51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md)
- [GlassHive User Control Plane and Persistent Workspaces](../57_GlassHive_User_Control_Plane_and_Persistent_Workspaces.md)
