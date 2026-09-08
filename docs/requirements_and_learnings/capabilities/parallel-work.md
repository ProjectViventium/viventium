# Parallel Work

## User promise

Main can keep talking while independent, substantial objectives run as durable work. The user sees
one coherent Viventium, can control exact work, and receives useful results once. Ordinary requests
need no parallel-mode toggle, special delegation prompt, extra configuration, or manual thread setup.

## Roles and mode

### Roles

- **PW-001 / PW-008:** The existing Main manages work and authors the final user response from
  neutral worker evidence.
- **PW-002:** Each independent durable objective has one saved mission root.
- **PW-007:** Workers cannot impersonate Main, address the user as separate personalities, or
  receive unrelated sibling work or private chat.

### Mode

- **PW-009 / PW-010:** Automatic parallel delegation is ordinary behavior for an authorized ready
  installation. One account-wide `focused` or `parallel` preference remains an optional explicit
  choice; Web and Telegram edit the same setting and Voice reads it. The user does not need to
  enable a mode first. Unavailable authorization, capability, or capacity is reported truthfully;
  it must not be disguised as a chosen focused preference.
- **PW-011 / PW-012 / PW-013:** Turning parallel mode off stops only new automatic delegation.
  Explicit delegation remains available; existing work stays visible, controllable, resumable, and
  deliverable; and setting changes require no model request or interruption.

## Delegation and responsiveness

### Delegation

- **PW-014:** Main keeps immediate conversational work and delegates independent, substantial
  objectives through the existing durable mission owner, so it remains available for more input.
- **PW-016:** Main uses model judgment in the same inference to distinguish a new independent
  objective from guidance for existing work. New objectives create separate missions once;
  relevant follow-ups update only the matching track. Unrelated input cannot interrupt, cancel,
  restart, or hide another mission. Runtime binds the chosen exact identity and authority; it
  does not classify prompt text, add a routing model, or invent a second orchestration layer.

### Responsiveness

- **PW-018:** Main remains responsive. Interactive replies and exact controls take priority over
  background execution and callback synthesis.

### Truthful status

- **PW-020 / PW-021 / HARD-004:** Stale or unavailable roster state is never shown as empty. Main reports only
  verified route, model, effort, Feeling, capability, state, and delivery facts.

### Turn integrity

- **PW-023 / PW-024 / PW-025:** Source segments are durable and ordered. Input received before
  presentation commit revises the unfinished response, and only one Main presentation survives.
- **PW-026 / PW-112:** Presentation revision never cancels or repeats committed work, and every
  enabled input handler remains nonblocking while Core preserves ordering and idempotency.
  An unfinished reply may be revised, but completed work and its useful result retain an owner
  and delivery path. Typing/progress cannot remain active after its response work has settled.

## Active Work and controls

### Active Work

- **PW-046 / PW-047:** Active Work is the primary control panel. It shows roster, queue, attention,
  delivery truth, safe detail, valid actions, and overflow. Settings holds only the mode.
- **PW-048 / PW-049:** Existing work stays reachable when admission is off. Web, Telegram, and Voice
  share one account-wide work record and behavior.

### Controls

- **PW-027:** Only an explicit Stop aimed at exact work cancels durable work.
- **PW-034:** Queue adds later work without interrupting the current run.
- **PW-035:** Message adds noninterrupting guidance now or at the next safe boundary and says which.
- **PW-036:** Steer interrupts only the exact active run and keeps its mission workspace.
- **PW-038:** Pause visibly holds the same mission; Resume continues it.
- **PW-039:** Stop remains `stopping` until the exact process tree is proved terminated. Unproved
  termination is a typed attention error, not false success.
- **PW-040 / PW-041:** Retry or Continue starts a new run in the same mission; Dismiss hides an
  acknowledged terminal item without deleting history. Archive or terminate is a separate operator
  action.
- **PW-042 / PW-043 / PW-044:** Actions cannot affect another item. Ambiguous references require one
  question; late cancelled output cannot become current; read-only links cannot control work; and
  control uses scoped, signed, one-use authority.

## Truth, isolation, and recovery

### Continuity

- **PW-028:** Restart, reload, reconnect, or chat continuation loses no accepted segment, mission,
  action, callback, result, or artifact. Execution complete, callback accepted, and result delivered
  remain distinct. A new unrelated message cannot strand an earlier completed result; useful Main
  synthesis reaches its authorized origin or existing governed continuation once.

### Capacity truth

- **PW-033 / HARD-008 / HARD-010 / PW-078:** Queued is not running. Execution admission requires
  atomic capacity reservation. Transient capacity shortage must still preserve an authorized
  objective or correction in the existing durable queue, without requiring user resubmission.
  Queued work consumes no execution lease until capacity is available; CLI probes remain fenced.
  Waiting state shows available and required capacity, shortage or reservation, age, blocker,
  next retry, and timeout; it never promises unverified future delivery.

### Exactly once

- **PW-069:** Exact replay of a Core-issued, tool-occurrence-scoped `effectOccurrenceRef` returns the
  same durable result; changed content under that reference fails closed, and similar objectives
  with distinct references remain distinct.

### Failure truth

- **PW-077:** Capacity, account limit, resource pressure, quota, authentication, provider outage,
  approval denial, missing capability, and roster unavailability stay distinct.

### Owner isolation

- **PW-081 / PW-082:** Work and artifacts are owner-isolated. References are not authority; service
  calls require signed owner scope and public summaries exclude private inputs and internals.

## Quality and rollout

### Quality

- **PW-080:** Never silently downgrade configured model or reasoning effort.
- **PW-095:** Direct, GlassHive-Codex, and GlassHive-Claude paths each meet the shared outcome metric
  for supported use cases.

### Rollout

- **PW-096:** Ordinary ready installations enable automatic delegation without user opt-in.
  An explicit focused preference or operational rollback may stop new automatic admission without
  killing, hiding, or losing the delivery of existing work. Historical dark/focused rollout wording
  is superseded for the ordinary user journey; real security, capacity and public-release gates remain.

### Release gate

- **PW-097 / HARD-001 / HARD-025:** Public release requires every applicable release gate. Configured local work
  uses authenticated owner readiness independently of certification. Missing or failed readiness
  cannot admit work; the saved preference and known work remain available.

## Owners and QA

- Runtime: [Parallel Work runtime](../../architecture/parallel-work-runtime.md)
- Mission authority: `viventium_v0_4/GlassHive/`
- Main and Active Work projection: `viventium_v0_4/LibreChat/`
- QA: `qa/parallel-orchestrator/`

The decisive installed journey starts without a mode change, runs two overlapping artifact missions, keeps one quick Main reply
responsive, Steers only one mission, opens two distinct artifacts, reloads Active Work, and checks
failure, restart, isolation, callback, and delivery evidence.

## Detailed contracts

- [Parallel Work Orchestration](../55_Parallel_Work_Orchestration.md)
