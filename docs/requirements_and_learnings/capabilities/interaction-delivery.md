# Interaction delivery

## User promise

Rapid input, streaming, callbacks, worker completion, and channel adaptation yield one current,
truthful Main presentation without losing or repeating durable work.

## Requirements

### Supersession

- **HARD-005 / CC-038:** The newest owner-scoped source received before presentation commit revises the open
  turn. Stale preview or output is suppressed or retracted.
- **CC-047:** Reload never restores superseded Web text. Telegram keeps distinct user sources,
  retracts stale preview when possible, and reports degraded retraction honestly.
- One send creates exactly one conversation and one logical turn. A route remount resumes the
  accepted stream; it never replays the start request or mints another conversation. A provider or
  isolation conflict is a typed terminal state, never a success and never a retry with new identity.

### Native continuation after retraction

- Removing an unfinished reply does not by itself prove a user changed branches. Native context
  may continue only when trusted Core receipts identify that exact removed predecessor and its
  next accepted revision, the predecessor has released execution, and all original input content,
  roles, tool bindings and order remain intact. The model receives the factual removal status.
- Missing, stale or conflicting proof preserves branch isolation. Genuine branch edits and
  regeneration still require fresh context. Continuation admission is idempotent and checks the
  latest admitted predecessor atomically; configured model, effort and permissions stay unchanged.

### Effect preservation

- **CC-043:** Presentation supersession never cancels or repeats committed effects, accepted
  missions, durable background work, or tool receipts.

### Telegram input

- **CC-048:** A Telegram voice-note transcript remains source input, preserves receipt order and file
  semantics, and receives one truthful unavailable response when transcription fails.

### Origin binding

- **HARD-021:** Completion returns only to its exact owner and origin, or to one governed account-
  level continuation when that origin no longer exists.

### Completion presentation

- **PW-076:** Useful completion is presented once through Main. Redundant results may become durably
  silent, and closely related completions may coalesce within one configured brief window.
- Durable completion adjudication retains each originating mission’s exact input and trusted
  result identity alongside its evidence. A later conversational question does not replace that
  mission’s request. Silent adjudication must not appear as a delivered user-facing result merely
  because an internal completion-status receipt was sent.
- Durable mission results use their own accepted-result authority. Optional evidence from an
  unfinished or failed foreground reply cannot block them; identity and branch checks still apply.
  Present the result in the current governed conversation without filling an obsolete foreground
  reply. Record an older accepted run’s delivery without replacing a newer run’s work status.
- Main can discover retained work history and read an exact owner-scoped stored result through
  the existing read-only work facade. Preserve the full output and accepted input. A retained
  terminal result does not prove that a later correction or current run is complete. Reading
  a result must not launch, retry, steer, or alter its delivery state.
- **PW-109:** If an origin disappears, useful completion uses its governed exact-owner continuation
  and never recreates the deleted origin.
- **PW-110:** Callback completion survives stream close, updates authoritative Active Work state
  immediately, and is durably adjudicated once as sent or silent.
- Independent conversation can be answered before unrelated worker launches settle. Launch status
  still requires a successful receipt; accepted work remains pending until its own completion.
- Failed optional follow-up synthesis must not turn raw internal insights into another Main
  answer. Preserve the failure record, existing empty-primary recovery, and durable callback retry;
  a provider failure is not a model decision that a required result should remain silent.

### Foreground and background execution

- Queen and preferred background workers have separate persisted model/effort and fallback
  preferences. Defaults apply to new work and preserve supported explicit task choices; changing
  preferences must not silently alter accepted workers or the other role.
- Responsiveness requires nonblocking accepted-work orchestration and no demonstrated avoidable
  application wait, retry/replay, or delayed forwarding. Correlate admission, queue, native startup,
  provider/CLI work, first public output, forwarding and channel acknowledgment. Mark unobserved
  intervals unknown; provider work is not evidence of hidden reasoning or client rendering.
  The quick-answer acceptance target remains at most ten seconds from Send to visible output
  under the configured healthy-route conditions while background work runs. Provider working time
  is measured separately; an acknowledgement, queued result or unobserved render cannot pass that
  target. Outside those conditions, report the measured delay and cause without claiming the target.
  A completed native commentary item is not a validated graph/delivery response envelope. Keep
  the existing output-contract guard; measure that format-contract wait separately from forwarding
  a valid envelope, and never describe public commentary as hidden reasoning.

### Recoverable pending

- **PW-111:** A recoverable provider or bridge condition remains pending after stream close; one
  recovery creates one final presentation instead of a committed generic error.

## Non-goals

- Do not infer authoring or supersession scope from provider, adapter, or channel names.
- Do not cancel a committed effect to make the transcript look cleaner.
- Do not expose internal turn, callback, worker, or delivery identifiers to ordinary users.

## Owners and QA

- Architecture: [interaction delivery](../../architecture/interaction-delivery.md)
- Core ordering and persistence: nested LibreChat message, turn, callback, and delivery services
- Channel adapters: nested LibreChat, Telegram bridge, and Voice gateway
- QA: `qa/main-continuity/`, `qa/agent-streaming-usage/`, `qa/no-response/`,
  `qa/citation-rendering/`, and `qa/agent-config-continuity/`
- Durable journeys: `qa/interaction-delivery/cases.yaml` (`cross-surface-supersession`,
  `main-natural-response`)

Acceptance includes rapid cross-surface input, false and stable Voice interruption, callback
completion, concurrent conversation isolation, restart and reload, transcription failure, and a
durable effect that committed before a later source.

## Detailed contracts

- [Telegram Bridge](../03_Telegram_Bridge.md)
- [Citation Rendering](../08_Citation_Rendering.md)
- [Agent Streaming Usage](../09_Agent_Streaming_Usage.md)
- [No Response Feature](../21_No_Response_Feature.md)
- [Parallel Work Orchestration](../55_Parallel_Work_Orchestration.md)
- [Main Continuity Kernel](../56_Main_Continuity_Kernel.md)
