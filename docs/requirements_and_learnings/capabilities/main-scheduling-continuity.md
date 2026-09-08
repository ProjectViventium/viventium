# Main scheduling and continuity

## User promise

### Outcome

- **CC-001:** The same Main gets recurring opportunities to orient, judge, act or remain silent,
  observe results, and continue.

### Truth

- **CC-002:** This is functional continuity. Viventium never claims phenomenal consciousness.

### Architecture

- **CC-003:** Continuity composes existing Main, Feelings, scheduler, memory, tools, delivery, and
  work surfaces. It owns no duplicate subsystem.

## Judgment and safety

### Judgment

- **CC-004 / CC-020 / CC-021 / CC-022:** Feelings and relevant current context inform Main, which
  assesses material change, relevance, blockers, opportunity, conflict, and uncertainty, then
  chooses an authorized action, plan, question, communication, or silence.
- **CC-061:** Recurring appraisal stays private unless Main has one useful authorized result,
  question, plan, or action for the user.

### Safety

- **CC-062:** Never optimize for engagement, guilt, dependence, hidden quotas, or higher Feeling
  values. Silence is valid.

### Non-goals

- **CC-032 / CC-063:** No message quota, cooldown, keyword prefilter, or product-wide outreach
  default replaces Main judgment. Activation is explicit and scoped.
- **CC-005 / CC-037:** Do not build duplicate continuity agents, state stores, private-thought
  streams, policy layers, or control UI.

## Trusted context and authority

### Trusted context

- **CC-007:** Only the server asserts origin, owner, approval, revision, and delivery state.
- **CC-008:** Scheduler wakes are typed system-origin events; they do not create user reactions or
  automatic user-memory writes.
- **CC-009:** Each genuine external-user source segment creates exactly one reaction.
- **CC-010:** Runtime decisions use typed origin and context. Legacy text detection is read-
  compatibility only.

### Routing

- **CC-017 / CC-051:** Scheduled Main resolves the persisted Main route, fallback, and the same
  authorization-derived capability intersection at execution time.

### Authority

- **CC-018 / CC-023:** Unattended work never opens approval dialogs or auto-confirms. It acts only
  within current authority and persists actual outcomes for later judgment.

## Occurrence contract

- **CC-011 / CC-012:** Every executor uses one durable occurrence identity containing lease,
  attempt, execution snapshot, outcome, delivery receipts, and interaction reference. Legacy rows
  remain readable.
- **CC-013:** In-progress, intentional silence, delivered or partial success, superseded, failed,
  and cancelled stay distinct.
- **CC-014:** Claim is atomic, concurrency is bounded, only one active execution may own an
  occurrence, and saturated work remains eligible.
- **CC-015:** Expired leases recover after interruption; recurring catch-up dispatches only the
  latest eligible occurrence.
- **GHU-010:** GlassHive recurring work reuses this occurrence, idempotency, overlap, recovery, and
  fire-time authorization contract.

### Compatibility

- **CC-016:** Existing schedules retain behavior until the owner opts into newer window semantics.

## Configuration, prompts, and delivery

### Prompt ownership

- **CC-024 / CC-025:** Continuity, run-envelope, and channel-neutral output prompts have explicit
  Workbench owners and verifiable source-to-live equality.

### Configuration

- **CC-026 / CC-028:** Schedules are editable and versioned and use typed metadata, not display
  names, for activation or control.
- **CC-029:** Private continuity uses one durable schedule object and conversation; the public
  product ships no active owner schedule.
- **CC-030:** Timezone, active window, and cadence are owner-selected private configuration values.
- **CC-031:** Private recovery policy may choose latest-only catch-up inside an active window and
  defer recovery outside it.

Exact typed owners:

| Requirement | Public schema or runtime owner | Private boundary |
| --- | --- | --- |
| `CC-029` | `viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex/scheduling_cortex/models.py` → `CreateScheduleArgs.conversation_policy`, `CreateScheduleArgs.conversation_id`, and `ScheduleRule`; durable columns live in `scheduling_cortex/storage.py` → `scheduled_tasks.schedule_json`, `conversation_policy`, and `conversation_id` | The owner schedule row, prompt key, activation state, and conversation ID stay private. |
| `CC-030` | `models.py` → `ScheduleRule.timezone`, `ScheduleRule.interval`, `ScheduleRule.active_window`, and `IntervalActiveWindow.cadence` | Timezone, interval, and wall-clock bounds stay private; public examples and tests use synthetic values. |
| `CC-031` | `models.py` → `ScheduleRule.active_window`; `scheduling_cortex/scheduler.py` → `_latest_active_window_occurrence`, `_next_active_window_occurrence`, and `_resolve_misfire_policy` | The selected window and recovery posture stay private. |

### Activation

- **CC-034:** Public schedule templates are inactive and contain no private owner settings; private
  activation follows its acceptance gates.

### Delivery

- **CC-033 / CC-050:** Author one canonical result, adapt it to authorized destinations, and use
  Workbench as an audit sink rather than another author. Voice never implies unsolicited calling.

For `conversation_policy: same`, the existing scheduler resolver takes the authenticated current
conversation from `X-Viventium-Conversation-Id`. Both direct and brokered MCP calls must carry that
request-scoped header; a missing transport declaration must not silently turn a same-chat request
into a new delivery chat.

The open chat also observes persisted messages from scheduling and other channels after local
work has ended. Its existing query refreshes every ten seconds while visible and idle, and on
reconnect or focus. An active response keeps SSE ownership and cancels any older query so a
refresh cannot replace the streaming answer. Background-cortex polling retains its faster cadence.

Independent background invocations explicitly retain the trusted caller context, adapter capabilities
and delivery policy. Prototype inheritance alone must not turn scheduled or system-origin work into
an interactive user request; untrusted body fields cannot supply this authority.

### Visibility

- **CC-035 / CC-036:** Control events and no-output decisions remain auditable but hidden from user
  UI and recall. A continuity conversation becomes discoverable only after a visible result.

### Failure semantics

- **CC-052:** Authorization, provider, unsupported configuration, timeout, confirmation, rejection,
  and healthy-empty results remain distinct.

## Owners and QA

- Scheduler: `viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex/`
- Core delivery/callback bridge: `viventium_v0_4/LibreChat/api/server/services/viventium/`
- Main continuity: nested LibreChat Main context and continuity services
- Prompt sources: Prompt Workbench registry
- QA: `qa/scheduling-cortex/`, `qa/continuity-ops/`, and `qa/main-continuity/`

Acceptance covers natural due delivery, shutdown catch-up, atomic claim, restart and lease recovery,
exactly-once effects, lifecycle edits, channel delivery, and cleanup on the installed candidate.

## Detailed contracts

- [Scheduling Cortex](../11_Scheduling_Cortex.md)
- [Main Continuity Kernel](../56_Main_Continuity_Kernel.md)
