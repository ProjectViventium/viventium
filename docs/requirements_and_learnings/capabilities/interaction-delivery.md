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

- Automatic conversation reuse must not select an assistant still generating its reply as a
  stable parent. Its text can change while another reply runs. A stopped partial with the existing
  typed interruption marker remains a stable parent, so Main can see where it was interrupted.
  Select without waiting, changing stored history, or hiding active work. Explicit parent proofs
  still reject real source edits. Callback ownership must still see the raw latest leaf so it can
  detect an active Main reply.
- Removing an unfinished reply does not by itself prove a user changed branches. Native context
  may continue only when trusted Core receipts identify that exact removed predecessor and its
  next accepted revision, the predecessor has released execution, and all original input content,
  roles, tool bindings and order remain intact. The model receives the factual removal status.
- Missing, stale or conflicting proof preserves branch isolation. Genuine branch edits and
  regeneration still require fresh context. Continuation admission is idempotent and checks the
  latest admitted predecessor atomically; configured model, effort and permissions stay unchanged.
- A newer source can revoke publication before its replacement reply is admitted. An error from
  the old producer must not overwrite the adapter's successful removal receipt with `failed`.
  Recheck source ownership after asynchronous failure presentation; actual removal failure remains
  a failure and cannot authorize native continuation.
- Send one noncommitted receipt per revision. Persist that receipt before transport and retry the
  same payload through the existing durable acknowledgment queue after an outage or restart.
  Retrying a receipt must not send another answer, invent removal proof, or change its outcome.
- Completing a superseded response does not close its logical turn before the successor is
  claimed. Confirmed removal lets that successor carry the original ordered inputs; a genuine
  failed receipt still starts fresh. Expiry must not discard retained unadmitted inputs.
- A saved input can resume after confirmed removal even if its first admission never reached the
  store. Require the exact current removal receipt and revoked native publication identity.
  Existing native release and source-recovery checks still gate execution; a live, unmatched or
  unconfirmed predecessor stays busy.
- Rolling back an unadmitted replacement must not reactivate a reply whose delivery already
  committed or failed. Retain unanswered source segments and their original author ownership in
  the existing turn ledger so a later retry neither loses input nor repeats accepted work.
- A terminal failed reply does not block later input or supply removal proof. Admit new input
  and retained unadmitted sources without inheriting that failed reply's native continuation.
  Keep its original input, failed state and accepted effects discoverable; do not silently replay
  its work. A failure receipt does not require an assistant Message that was never published.
  Successful delivery still requires its exact saved presentation.
- Refused native publication must leave its exact response terminal through the native owner.
  A system error snapshot cannot silently leave it pending. Preserve committed publication,
  stopped partials, revocation and source identity; later background augmentation cannot reopen
  the failed answer or replace its terminal body.
- Report a typed internal conversation-context conflict as a context failure. Provider-failure
  wording requires a provider failure; do not infer the class from message text.

### Effect preservation

- **CC-043:** Presentation supersession never cancels or repeats committed effects, accepted
  missions, durable background work, or tool receipts.
- A committed effect receipt is internal control data. It cannot authorize an obsolete
  assistant reply or generate conversational text or speech. The existing superseded terminal
  closes that stream; the surviving Main and normal worker follow-ups own useful conversation.
  The durable effect, its replay fence and current mixed-answer authoring remain intact.

### Telegram input

- **CC-048:** A Telegram voice-note transcript remains source input, preserves receipt order and file
  semantics, and receives one truthful unavailable response when transcription fails.

### Attachment-only input

- A completed authorized attachment is valid user input without a caption. Web send, saved user
  edits and regeneration use the files selected for that operation; unrelated history cannot make
  an empty new message valid. Pending or invalid uploads remain blocked.
- Saved user files remain visible and editable when the message has no structured content parts.
  Existing file controls render the canonical file list; an empty content array must not hide it.
- Main and worker handoff preserve the original empty authored text, source order and authorized
  files. They neither drop the source nor invent a caption. The same source identity and file
  access checks apply to text, image, audio and document inputs. This does not force transcription
  or delegation; the configured model chooses its existing tools.

- Saved input file cards use the same authenticated download path as result files. Original stored
  files return their exact bytes. Upload-as-Text returns its retained extraction as plain text with
  a `.txt` download name; a removed temporary original is not required or falsely reconstructed.
  Explicit empty extraction is a valid file. Missing retained content returns an unavailable result.
- Main, background agents and workers receive the same declared file representation: original,
  extracted text, or unavailable metadata. A binary original filename must not hide usable declared
  extraction. Reading extraction does not prove access to original bytes.

### Origin binding

- **HARD-021:** Completion returns only to its exact owner and origin, or to one governed account-
  level continuation when that origin no longer exists.

### Completion presentation

- **PW-076:** Useful completion is presented once through Main. Redundant results may become durably
  silent. Committed worker results enter the existing conversation lane without a fixed collection
  wait. Results already pending may coalesce; later independent results use the next durable pass.
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
- A silent Main decision may still owe an accepted output file. Core emits that file with empty
  text and audio disabled through the existing attachment carrier. Telegram preserves its normal
  dispatch permit, per-file authorization, and delivery receipt; it adds no placeholder message or
  speech. An empty result without files and a literal no-response control remain suppressed.

### Foreground and background execution

- Queen and preferred background workers have separate persisted model/effort and fallback
  preferences. Defaults apply to new work and preserve supported explicit task choices; changing
  preferences must not silently alter accepted workers or the other role.
- Responsiveness requires nonblocking accepted-work orchestration and no demonstrated avoidable
  application wait, retry/replay, or delayed forwarding. Correlate admission, queue, native startup,
  provider/CLI work, first public output, forwarding and channel acknowledgment. Mark unobserved
  intervals unknown; provider work is not evidence of hidden reasoning or client rendering.
  Provider working time may exceed ten seconds; this journey has no fixed end-to-end deadline.
  A completed native commentary item is not a validated graph/delivery response envelope. Keep
  the existing output-contract guard; measure that format-contract wait separately from forwarding
  a valid envelope, and never describe public commentary as hidden reasoning.

### Recoverable pending

- **PW-111:** A recoverable provider or bridge condition remains pending after stream close; one
  recovery creates one final presentation instead of a committed generic error.

### Finished reply after connection expiry

- A completed host reply, whether produced through Direct or a native handoff, remains recoverable
  from its existing saved Message after the temporary job expires. Recovery uses the exact saved
  source, owner, conversation, revision, text and files. It does not rerun the model or its tools.
- The private completion receipt is saved with the final answer. A partial message, Stop,
  acknowledgment alone, or an old branch is not proof of completion. Changed or deleted source,
  payload, attachment or ownership must fail the same recovery check on Web, Telegram and Voice.
  Acknowledgment is idempotent and bound to that exact presentation. Native-owned completed
  responses keep their existing replay authority; host recovery cannot restore revoked authority.
- An unavailable recovery proof must not make ordinary answer persistence fail. Keep the existing
  Stop, supersession and native publication controls; real persistence failures still fail.

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
  `main-natural-response`, `attachment-only-input`, `finished-reply-after-connection-expiry`)

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
