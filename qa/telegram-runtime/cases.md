# Telegram Runtime Cases

## Case TR-021: Nested Provider Authentication Failure Remains Actionable

- **Expected outcome:** When Main hands a turn to a GlassHive-backed participant whose provider
  authentication is unavailable, the worker rejects before durable mission state, Core preserves
  the structured `provider_auth_missing` class through nested response envelopes and fallback
  selection, and Telegram tells the user to reconnect the AI provider and retry.
- **Forbidden result:** The generic model-provider failure, raw provider/CLI text, a false rate-limit
  instruction, a provider fallback loop that converges on the same unavailable route, or orphaned
  project/worker/run/provider-request rows.
- **Evidence to capture:** typed runtime preflight tests, no-residue Store assertions, Core nested
  error/fallback tests, Telegram mapping tests, installed Telegram bubble, runtime log class, and
  active-work/database absence for the rejected occurrence.
- **Last run:** PASS 2026-08-18. The focused failure was reproduced on installed Telegram, repaired
  across GlassHive/Core/Telegram, and rerun on the real bridge with actionable wording. The affected
  Telegram bridge/preview matrix passed 204 tests, Core provider/fallback passed 260, and GlassHive
  profile/conversation/API suites passed. Connected-account success remains separately blocked on
  account OAuth reauthorization. See the
  [extended-use result](../parallel-orchestrator/reports/2026-08-18-extended-use-acceptance.md).

## Case TR-019: Specialist Provider Failure Recovers Without Replaying Effects

- **Expected outcome:** Main may hand a turn to any graph participant by server-owned coordination.
  If that participant's primary model fails at the exact pre-authoring response boundary, even with
  an opaque adapter error, its configured participant fallback answers in the same graph and
  Telegram turn. Main remains free to coordinate other work.
- **Forbidden result:** The handoff is treated as an email, calendar, durable-work, or other external
  effect; Telegram receives the generic provider failure while a healthy participant fallback is
  configured; the whole Main turn is replayed after a real external action; or tool names, prompt
  text, provider names, or user identity decide whether replay is safe.
- **Evidence to capture:** structural graph-tool metadata, exact participant primary/fallback call
  counts, absence of external tool execution in the fault case, one delivered Telegram answer,
  persisted message identity, sanitized recovery class, and active runtime source identity.
- **Last run:** PARTIAL 2026-08-18. RED-to-GREEN automation proves opaque exact-boundary participant
  recovery, structural handoff classification, and fail-closed treatment of unmarked tools. A
  post-restart real Telegram turn and persisted/log correlation remain required. See the
  [dated result](reports/2026-08-18-participant-provider-fallback.md).

## Case TR-018: Parallel Work Controls Survive Interrupts And Lost Responses

- **Expected outcome:** A linked user can toggle the account-wide mode, inspect every retained
  mission, and Message, Queue, Steer, Pause, Resume, Stop, Retry, or Dismiss only when the
  server-returned action mask permits it. Every ingress and callback remains nonblocking. If an
  action or pagination response is lost, Telegram retries the same durable operation/cursor after
  restart rather than duplicating the effect or expiring the only recovery path.
- **Forbidden result:** A callback embeds a raw work ID; a second tap changes the operation ID;
  Stop reports success while a sibling run remains active; turning availability off hides existing
  work; a recoverable provider error is presented as a permanent connection failure; attachment
  ingress blocks the chat.
- **Evidence to capture:** real Telegram Desktop toggle/card/action flows, injected committed-then-
  timeout retry, bridge restart, Core/GlassHive action receipt and run counts, handler registration,
  delivery ledger, and public-safe screenshots/log summaries.
- **Last run:** PARTIAL 2026-08-18. Real Telegram passed Message, Queue, Resume, Stop confirmation,
  and Dismiss; a raced Pause truthfully returned unavailable. Real installed Chrome additionally
  passed one queued-work Message, exact completed action receipt, one same-work continuation, and
  reload persistence. Running Steer/Pause, Retry, the exact committed-response-lost retry after
  bridge/runtime restart, and full cross-surface action parity remain release gates. See the
  [extended-use result](../parallel-orchestrator/reports/2026-08-18-extended-use-acceptance.md).

## Case TR-001: Polling Conflict Is Visible

- **Expected outcome:** A running Telegram bridge or Telegram Codex sidecar with recent
  `getUpdates` conflict evidence is reported as `Running with issues`.
- **Forbidden result:** `bin/viventium status` says the service is simply `Running` while recent logs
  show another bot process is consuming the same token.
- **Evidence to capture:** synthetic unit test, sanitized status output, and a local runtime note.
- **Last run:** PARTIAL 2026-05-14: automated synthetic coverage was added.

## Case TR-002: Provider Authentication Failure Is Actionable

- **Expected outcome:** A running Telegram bridge with recent provider-auth evidence is reported as
  `Running with issues`; a stopped Telegram bridge with the same evidence is reported as
  `Action Required`. Both states use user-safe refresh guidance.
- **Forbidden result:** raw provider error text, token values, account identifiers, or private logs
  appear in public status or QA artifacts.
- **Evidence to capture:** synthetic unit test and public-safe QA report.
- **Last run:** PARTIAL 2026-05-14: automated synthetic coverage was expanded after the escaped user report.

## Case TR-003: Telegram Codex Restart Clears Scoped Orphans

- **Expected outcome:** `--restart` kills only Telegram Codex processes scoped to the configured
  Telegram Codex checkout before starting a new sidecar.
- **Forbidden result:** duplicate Telegram Codex pollers or broad process kills outside the Viventium
  checkout.
- **Evidence to capture:** static launcher regression test and local status after restart.
- **Last run:** PARTIAL 2026-05-14: static regression coverage was added.

## Case TR-004: Provider Rejection Is Not Shown As Connection Error

- **Expected outcome:** A Telegram turn whose LibreChat final event reports rejected model provider
  credentials returns clear reconnect guidance for the AI provider.
- **Forbidden result:** Telegram says only `Connection error. Please retry.` or otherwise implies
  the Telegram transport is broken when the root cause is model-provider auth.
- **Evidence to capture:** bridge stream regression test, local runtime restart, sanitized status/log
  class check.
- **Last run:** PARTIAL 2026-05-14: bridge regression coverage was added after the escaped user report.

## Case TR-005: Recoverable Provider Failure Is Not Shown Or Spoken As Connection Error

- **Expected outcome:** A Telegram turn whose primary provider returns a retryable quota, rate-limit,
  or terminal provider-response failure before visible text retries the configured valid main-agent
  fallback LLM. Only an unavailable, invalid, or exhausted fallback may return clear provider copy,
  and that terminal bridge/provider error is marked non-spoken.
- **Forbidden result:** Telegram says only `Connection error. Please retry.`, implies Telegram
  transport is broken, skips a configured fallback, or synthesizes a voice note of the bridge error.
- **Evidence to capture:** main-agent fallback regression test, bridge stream regression test,
  sanitized runtime log class, and dated QA report.
- **Last run:** PASS 2026-08-17. A controlled pre-authoring `provider_response_failed` fault on the
  real local Telegram surface switched exactly once to the configured Claude route and delivered one
  clean answer. The source-only fault seam was removed, the synthetic turn was backed up and purged,
  and local prod was restarted on the final source. See
  `../agent-config-continuity/reports/2026-08-17-main-agent-fallback-not-reached.md`.

## Case TR-023: GlassHive Lifecycle Start Does Not Suppress Provider Fallback

- **Requirement:** A GlassHive main Agent configured with Codex primary and Claude fallback must
  recover from an exact structured retryable pre-authoring quota, rate-limit, or terminal
  provider-response failure.
- **User outcome:** The same Telegram turn stays open and receives one Claude-authored answer without
  exposing the primary quota error.
- **Surfaces:** Telegram bot, LibreChat SSE, GlassHive conversation provider/state.
- **Preconditions:** Both harnesses are authenticated; main Agent carries GlassHive/Claude in its
  Agent Builder `fallback_llm_*` fields and has no provider-internal fallback enabled;
  a controlled fault produces an exact retryable provider failure before authored activity.
- **Steps:** Send synthetic public-safe text through the real bot, inspect the bubble, then correlate
  the same request/session/idempotency identity, primary termination, single replacement run,
  activity stream, and stored message. Repeat with cancellation and with authored-activity fixtures.
- **Expected result:** `queued`/`started`/`fallback` status alone does not lock recovery; Claude answers once on
  the same turn; cancellation wins before the switch; authored text/reasoning/plan/tool/file activity
  forbids the switch; an abandoned switch claim fails visibly instead of hanging the turn.
- **Forbidden result:** The rate-limit blocker reaches Telegram while the configured fallback is
  healthy, a second/overlapping author is launched, a new Telegram turn is invented, or fallback
  occurs after authoring evidence.
- **Evidence to capture:** real delivered Telegram bubble, sanitized SSE/activity classes, request/run
  counts and identity continuity, active config/artifact hashes, automated regressions, and dated report.
- **Last run:** PASS 2026-08-17. A controlled `provider_response_failed` fault on the real Telegram
  surface switched once to GlassHive/Claude, produced one visible and persisted answer, and exposed
  no primary error bubble. Runtime logs and the GlassHive run record confirmed Claude/Opus authored
  the replacement. See
  `../agent-config-continuity/reports/2026-08-17-main-agent-fallback-not-reached.md`.

## Case TR-012: `/call` Uses One-Time Launch Authority

- **Expected outcome:** the real bot returns the configured public HTTPS call URL only after the
  canonical Agent passes global `USE` and resource `VIEW`. The browser strips its one-time fragment
  bearer before same-origin exchange and auto-connects. A lost response retries only with the same
  browser-generated idempotency value; a different value or second browser replay is denied.
- **Forbidden result:** localhost/raw LAN is presented as supported remote access; raw session id or
  a consumed link authorizes call state; body agent metadata bypasses the canonical Agent ACL;
  capability material enters query/body, logs, referrers, cache, screenshots, or reports.
- **Evidence to capture:** real Telegram `/call` delivery, two-browser exchange/replay status matrix,
  fragment-strip order, cache/referrer/privacy audit, permission/revocation matrix, visible/audible
  call, linked-chat persistence, and active artifact identity.
- **Last run:** `PARTIAL` — 2026-08-09 — focused launch/ACL automation is supporting evidence; the
  real Telegram, second-browser, public-origin, audible, revocation, and persistence path is pending.

## Case TR-006: Telegram Markdown Tables Render Readably

- **Expected outcome:** Markdown pipe tables from main answers or worker callbacks are converted to
  readable Telegram HTML rows.
- **Forbidden result:** Telegram displays raw `| Name | ... |` and `|---|` table syntax.
- **Evidence to capture:** Telegram HTML renderer regression test plus a visual/browser rendering
  check with synthetic public-safe content.
- **Last run:** PASS 2026-06-28: automated regression plus Playwright visual QA rerun. See
  `reports/2026-06-28-telegram-fallback-audio-table-qa-rerun.md`.

## Case TR-007: Telegram Memory Capture Reaches New Conversations

- **Expected outcome:** An explicit synthetic durable fact sent through the real Telegram bot
  advances saved-memory state, while a separate natural event remains available through
  conversation recall; both can be recovered later from new authenticated Chrome/voice sessions.
- **Forbidden result:** Telegram reply success is counted as memory proof, same-thread history is
  reused, the detached writer drops a nearby turn, or saved memory and recall are conflated.
- **Evidence to capture:** visible Telegram send/reply, hashed writer audit, Mongo key/revision and
  message/corpus evidence, new Chrome answer, real voice transcript/audio, and cleanup.
- **Last run:** NOT RUN — cataloged 2026-07-11; real native journey required under `MEMCONT-004` and `RAG-005`.

## Case TR-008: Short Telegram Turns Preserve Tool And MCP Capability

- **Expected outcome:** A terse follow-up such as a GlassHive status question receives the same
  configured agent/MCP capability eligibility as a longer Telegram request. The eager GlassHive
  launch/status/wait gateway remains provider-bound and other operations remain discoverable through
  scoped `tool_search` in the same invocation.
- **Forbidden result:** message length, word count, or keywords return an empty tool set; Telegram says
  GlassHive is unavailable while the server is healthy; adding more intent keywords is accepted as a
  fix.
- **Evidence to capture:** exact long-then-short visible Telegram sequence, provider-binding logs,
  tool call content parts in Mongo, GlassHive run/events state, restart/reload proof, and latency.
- **Last run:** PASS 2026-07-13. Native long task completed with a workspace artifact; the exact
  post-restart `Glass hive??` follow-up retained 46 configured definitions, GlassHive instructions,
  and 16 unique provider-bound tools and returned a coherent visible reply.

## Case TR-009: Feeling-Aware Audio Is Natural, Capability-Scoped, And Observable

- **Expected outcome:** Natural positive and negative turns on an always-voice xAI route may use the
  smallest fitting supported xAI controls without a user request; a calm factual turn may correctly
  use none. Raw local/TTS content and structural counts agree, visible Telegram text stays clean,
  audio delivers, and prompt-frame telemetry accounts for the audio instruction under
  `surface_prompt` with no unknown layer.
- **Forbidden result:** The user must beg for emotional voice; every turn is forced to contain a
  tag; xAI markup appears in the bubble; unsupported provider dialects cross routes; audio delivery
  is inferred from logs without a visible file/playback path; or `telegram_audio_output` is recorded
  as an unknown prompt layer.
- **Evidence to capture:** synthetic natural prompts, visible text and audio files, native playback,
  raw marker counts, TTS gate/provider/bytes/timings, Current/Nature state evidence, prompt-frame
  layer summary, exact-model provider negatives, and a public-safe dated report.
- **Last run:** PASS 2026-07-14 for real positive/calm/negative xAI always-voice turns with control
  counts `2/0/2`, three delivered audio files, clean bubbles, positive native playback, fixed Nature,
  and a post-fix prompt frame with zero unknown layers. Real non-xAI delivery remains PARTIAL. See
  `../emotional-cortex/reports/2026-07-14-feelings-activation-and-telegram-acceptance.md`.

## Case TR-010: Disabled Telegram Does Not Touch An Unowned LaunchAgent

- **Expected outcome:** When Telegram is disabled, stop/restart/uninstall does not query or boot out
  the fixed Telegram LaunchAgent label unless an owner-only Viventium receipt proves that the
  current App Support target created it. A receipt-backed job is removed narrowly.
- **Forbidden result:** A disabled or alternate-target install calls `launchctl print` or
  `launchctl bootout` against a personal or unrelated job that happens to use the same label.
- **Evidence to capture:** synthetic launcher test with a launchctl recorder, receipt permissions,
  and an isolated Easy Install stop log.
- **Last run:** PASS 2026-07-20. Disabled/no-receipt and valid-receipt paths pass; isolated Easy
  Install stop produced no Telegram launchctl access.

## Case TR-011: Upgrade Handoff Preserves One Recognized Poller

- **Expected outcome:** A restart from a different checkout validates the stable token-hash owner
  receipt, process-start identity, command, cwd, uid, and rollback descriptor; it stops only that
  predecessor, then commits only after pinned PTB reports both its receive Updater and Application
  running with typed polling/webhook proof. The rollback guard covers the complete attach and
  bounded cold/network readiness budget plus recovery margin. A failure after `post_init` but
  before polling keeps rollback live and restores the predecessor, while an attached candidate
  process exit is detected immediately.
- **Forbidden result:** a bare pid file is treated as sufficient ownership, PID reuse is signalled,
  an unknown `bot.py` process is pattern-killed, a token enters a receipt/transaction, or a failed
  candidate leaves no recognized poller when safe rollback was available; the guard must not expire
  before the readiness deadline it is meant to protect.
- **Evidence to capture:** synthetic receipt/process cases, launcher contract, token-leak assertion,
  shell syntax check, bot readiness test, and an isolated two-checkout runtime exercise.
- **Last run:** PARTIAL 2026-07-25. Supporting automation passed exact post-init/pre-poll failure injection,
  premature-ready guard rejection, real pinned PTB 22.5 lifecycle state, source, and synthetic
  process/transaction coverage pass. A bounded live same-repo launchd handoff stopped one recognized
  predecessor and published candidate polling readiness, and direct clean-environment launch
  reached readiness. External Telegram message delivery remains pending. See
  `reports/2026-07-25-upgrade-handoff-readiness-qa.md`.

## Case TR-029: Delivery Dependency Failure Backs Off Without Delaying Healthy Polls

- **Expected outcome:** repeated LibreChat delivery-ledger failures wait 5, 10, 20 seconds up to the
  configured cap, emit one outage warning and one recovery message, then return to the normal
  five-second healthy empty-ledger poll.
- **Forbidden result:** the same dependency exception is logged every five seconds indefinitely,
  or healthy/late callback delivery inherits the failure backoff after recovery.
- **Evidence to capture:** async bridge test with deterministic attempts, delays, warning count, and
  recovery reset.
- **Last run:** PASS 2026-07-24. Supporting automation passed.

## Case TR-013: Loopback Delivery Polling Cannot Stall Telegram Ingress On TLS Setup

- **Expected outcome:** HTTPX clients for the local `http://127.0.0.1`/`localhost`/`::1` LibreChat
  hop skip proxy environment and the unused TLS verifier across bridge and attachment requests, so
  local request setup cannot synchronously block Bot API update handling while opening a CA bundle.
  Remote or HTTPS origins retain normal certificate verification.
- **Forbidden result:** any plain-HTTP loopback LibreChat request loads a CA bundle on the event
  loop, an incoming Telegram update stays queued while the bot process appears alive, or the local
  optimization disables certificate verification for a remote/HTTPS or lookalike host origin.
- **Evidence to capture:** loopback/remote option regressions, complete Telegram bridge suite, live
  process sample before repair, Bot API pending-update count, restart, visible synthetic
  send/reply timing, sanitized bridge log timing, and a second-turn/restart repeat.
- **Last run:** PARTIAL 2026-07-25. The escaped live process was sampled blocked
  in CA-bundle loading while a synthetic update remained queued; 347 Telegram tests pass with the
  shared loopback-only client policy. The sample proves the stall location but not which local
  caller initiated that anomalously slow open. Post-restart visible reply timing remains required. See
  `reports/2026-07-25-loopback-client-latency-recovery.md`.

## Case TR-014: Installed Telegram Is Source-Independent And Preserves Legacy Preferences

- **Expected outcome:** install, helper refresh, upgrade, and cross-checkout activation stage a
  code-and-dependency content-addressed Telegram runtime under private App Support. Detached macOS
  execution uses only its verified Python, code root, recovery launcher, and schema-2 execution
  identity. Legacy repo-local preferences migrate into canonical App Support without deleting the
  source; active legacy values, canonical-only values, explicit custom directories, and a byte-exact
  displaced canonical backup are preserved. Repeated startup performs no preference rewrite.
  Apple Silicon uses the compatible locked wheel while Intel uses the upstream-supported source
  build without broken wheel repair; both import the native transcription module before publishing.
  Recovery selections are immutable per attempt, custom/canonical root selection is durable across
  a cold start, migration/root receipt refresh happens before rollback, and helper supervision does
  not hash the full environment on its four-second UI poll. Each handoff seals the launcher and both
  sourced environment files as one hash-bound transaction package; commit/rollback removes the
  inactive credential-bearing package, and native predecessors cannot downgrade to legacy grace.
- **Forbidden result:** launchd reads Python, code, or preferences from a protected source checkout;
  a missing/tampered selection falls back to source; startup installs packages or rewrites defaults;
  an untracked allowed-suffix file enters the component; a failed candidate restores an older
  source-only launcher; a modified launcher/runtime-env/overlay executes during rollback; a native
  predecessor is accepted through legacy grace; stale secret-bearing launch attempts accumulate; or
  staging changes the live selection before its owning transaction. An Intel source build may not
  die in pywhispercpp wheel repair, and a failed sealed stage may not mask its root cause with a
  cleanup permission error.
- **Evidence to capture:** component/tree and dependency-manifest hashes, exact selection bytes
  before injected failure, schema-2 receipt cwd/Python, migration receipt/backup hashes, first and
  second start preference fingerprints, launch-package tamper/cleanup cases, helper/CLI tests, real
  message latency, native dependency import on arm64 and x86_64, and public-safe logs.
- **Last run:** PARTIAL 2026-07-31. Apple Silicon passed; hosted x86_64 remains pending. The complete 2,100-passed/8-skipped
  release suite, 18-case focused runtime-component set, fresh sealed Apple Silicon environment and
  native import probe, Intel environment selection, sealed-stage cleanup, exact shipped-predecessor
  matrix, process-group recovery, immutable staging, handoff, atomic ACL, and startup no-write
  regressions pass. The final public x86_64 easy-install job and post-change installed Telegram
  delivery/restart remain required; see
  `reports/2026-07-31-cross-architecture-dependency-assembly.md`.

## Case TR-015: Legacy Canonical Preferences Harden Without Byte Drift

- **Expected outcome:** an existing owner-controlled `0755` / `0644` canonical preference tree is
  accepted before publication, then hardened under stopped-writer control through no-follow
  descriptors. Content, custom roots, prompts, and unknown personalization fields remain exact.
- **Forbidden result:** first-upgrade refusal solely because of safe legacy read modes; default
  rewrite; mutation while a writer is active; symlink/hard-link traversal; or an outside chmod after
  a validation/open race.
- **Evidence to capture:** pre/post content fingerprint, modes, authority/journal selection,
  active-writer refusal, deterministic swap probe, installed restart, and real reply.
- **Last run:** PARTIAL 2026-07-25. Supporting automation passed all 22 migration cases and the
  descriptor-bound adversarial swap probe pass; installed candidate restart/reply remains required.

## Case TR-024: Nested Telegram Formatting Never Leaks Internal Placeholders

- **Requirement:** Nested supported Markdown in main answers and proactive/follow-up deliveries
  renders through the shared Telegram HTML path without exposing formatter internals.
- **User outcome:** A block quote containing bold or italic text shows the original emphasized words.
- **Surfaces:** Telegram main streamed reply, scheduled/proactive callback, and background follow-up.
- **Preconditions:** Telegram text delivery enabled; synthetic response contains formatted text
  before and inside a Markdown block quote.
- **Steps:** Render the synthetic fixture through the pure renderer, the main streamed bot path, and
  the follow-up bridge path; visually inspect the generated HTML; send the same shape through the
  real bot and inspect the delivered Telegram bubble.
- **Expected result:** Telegram receives valid HTML containing the original words and supported
  emphasis. No NUL-delimited placeholder or visible `PH<number>` token remains.
- **Forbidden result:** The quote contains `PH0`, `PH2`, another internal placeholder, missing source
  words, raw HTML, or a parse-mode fallback caused by the formatter.
- **Evidence to capture:** Focused Python regressions, affected Telegram suite, Playwright visual
  fixture, active runtime source/hash, real Telegram send/receive, sanitized runtime log class, and
  a dated public-safe report.
- **Last run:** PARTIAL 2026-07-27: the fixed source, shared main/follow-up paths, real Bot API
  acceptance, headed browser visual QA, and native Telegram rendering passed. The installed bridge
  remains incomplete: the active checkout has the same verified fix, but transactional activation stopped
  before restart because the target volume was below the required free-space threshold. See
  `reports/2026-07-27-nested-markdown-placeholder-rendering.md`.

## Case TR-025: Follow-Up Listening Uses Canonical Runtime Configuration

- **Requirement:** Telegram's raw SSE listener and DB-backed follow-up poller must share the
  compiler-owned background follow-up window and must not carry an independent implicit timeout.
- **User outcome:** Ordinary Telegram turns stop automatic follow-up listening at the configured
  boundary, while persisted Main/cortex work is not canceled and the separate GlassHive callback
  window remains available when a worker was actually launched.
- **Surfaces:** canonical config/compiler output and Telegram LibreChat bridge lifecycle.
- **Preconditions:** compile synthetic configs with default, explicit, zero, and invalid follow-up
  values; instantiate the bridge with canonical and deprecated compatibility env combinations.
- **Steps:** inspect generated env, initialize the bridge, exercise listener scheduling/cancellation,
  and run the affected Telegram bridge suite without a bot token or external account.
- **Expected result:** supported installs use `VIVENTIUM_TELEGRAM_FOLLOWUP_GRACE_S`; unset standalone
  bridges do not invent a wait; canonical zero disables ordinary listeners; invalid/out-of-range
  canonical config fails closed; legacy insight values cannot override canonical config; stopping
  the raw listener does not stop the persisted poll; GlassHive keeps its separate configured wait.
- **Forbidden result:** an implicit 180/210-second listener, prompt/agent/provider branching, Main or
  cortex cancellation, or collapse of the GlassHive callback window into the background window.
- **Evidence to capture:** compiler regressions, bridge unit/lifecycle regressions, source/example
  scan, generated env assertions, and a dated public-safe report.
- **Last run:** PARTIAL 2026-08-10: source and automated tests passed; live Telegram delivery was intentionally
  not run in this change and remains a separate user-surface acceptance step.

## Case TR-026: Rapid Segments Supersede One Unfinished Reply

- **Requirement:** Telegram source order is authoritative. A source segment observed before an open
  turn's presentation commits becomes its next revision even when host ingestion is delayed; a
  segment observed after commit starts a normal follow-up.
- **Surfaces:** Telegram text bridge, LibreChat logical-turn store, stream preview, Mongo history.
- **Steps:**
  1. Keep the existing preview-visible A → unfinished B → C branch.
  2. Run the escaped pre-presentation race with synthetic source sequence N+1 observed before bot
     presentation N, but delay its Core ingestion by 280 ms so the stale send reaches Telegram first.
  3. Repeat with N+1 observed only after presentation N commits as the control.
- **Expected outcome:** In the 280 ms race, source order binds N+1 as revision 2 of the same logical
  turn; any stale preview or final is retracted; both user source bubbles remain; one revision-2
  answer is current after reopen. This holds whether N or N+1 reaches Core admission first. A delayed
  lower source sequence receives the typed `source_order_superseded` result and is silently
  suppressed by the Telegram bridge. In the control, N+1 starts a new turn.
- **Forbidden result:** `Connection error. Please retry.`, stitched stale text, duplicate model
  answer, deleted user input, raw HTTP 409/conflict text, host-arrival order overriding source order,
  a second independent turn before commit, global cross-chat abort, or a stale answer restored after
  reopen.
- **Evidence to capture:** Telegram Desktop bubbles/screenshots, source watermark, bridge/Core
  revision and presentation-ack logs, in-memory/Redis parity, Mongo user/assistant ordering and
  tombstone metadata, refresh/reopen, and the focused 280 ms race test.
- **Last run:** PARTIAL 2026-08-22. The 2026-08-11 live A/B/C branch passed only after a preview was
  visible. It did not inject the escaped source-before-presentation race, so it cannot close this
  release gate
  ([prior report](../scheduling-cortex/reports/2026-08-11-consciousness-continuity-and-turn-coherence.md)).

## Case TR-027: Preview Deletion Failure Is Truthfully Degraded

- **Requirement:** Failed Telegram deletion cannot let a stale preview continue mutating or become a
  transport error for a successful current revision.
- **Expected outcome:** Later edits to the stale presentation are suppressed, delivery records
  `partial_removed`/degraded outcome, and D still arrives once.
- **Forbidden result:** stale preview edits continue, successful supersession emits connection
  error, or deletion retry duplicates the final response.
- **Evidence to capture:** synthetic Bot API deletion fault, bridge regression, channel outcome
  ledger, visible final state, and sanitized warning class.
- **Last run:** PARTIAL 2026-08-11; deletion-failure and failed-ack behavior
  passed fault regressions, while the real Telegram run covered successful preview retraction rather
  than an induced Bot API deletion fault
  ([report](../scheduling-cortex/reports/2026-08-11-consciousness-continuity-and-turn-coherence.md)).

## Case TR-028: Voice-Note And File Source Segments Survive Supersession

- **Requirement:** Final transcript/file receipt followed by clarification remains ordered user
  context; only assistant previews are retractable.
- **Expected outcome:** finalized transcript or file segment remains in history; pending
  transcription uses the bounded existing wait; failure lets later text proceed with a truthful
  unavailable-transcription state.
- **Forbidden result:** transcript/file source deleted as B, C answered before an earlier receipt
  resolves without truthful state, attachment semantics changed, or stale speech/preview delivered.
- **Evidence to capture:** real voice note and synthetic file+clarification in Telegram Desktop,
  transcription/file logs, Mongo message/attachment order, final bubble, and failure regression.
- **Last run:** NOT RUN — cataloged 2026-08-11; real native surface required after integration.

## Case TR-022: First-Turn Connected Tools Use Finalized Gateway Scope

- **Requirement:** A new Telegram conversation must refresh conversation-provider capabilities from
  the finalized run body after durable conversation and assistant message ids exist.
- **User outcome:** The first Telegram request can use every structurally declared, authorized MCP
  without a retry, screenshot request, or browser substitution.
- **Surfaces:** Telegram bridge, Agent run creation, provider capability projection, signed broker,
  MCP transport, Mongo persistence, text and audio delivery.
- **Steps:** Start a new marked Telegram conversation, ask for a short summary from an owner-only
  connected evidence source, inspect the visible reply, broker/MCP logs, and persisted final message;
  separately run missing-scope and non-owner regressions.
- **Expected result:** The broker accepts the exact finalized turn, invokes the declared MCP, and the
  response cites available dated evidence or the source's exact current blocker. Missing scope and
  non-owner access still fail closed.
- **Forbidden result:** `conversationId: new` is signed as real scope; the host claims provider auth
  failure without calling the provider; it browses or requests screenshots because the broker grant
  was malformed; a non-owner receives the host-wide health capability.
- **Evidence to capture:** focused broker/provider/gateway tests, real Telegram bubbles, Mongo final
  state, broker/MCP invocation logs, zero missing-scope warnings, and a dated public-safe report.
- **Last run:** PASS 2026-08-11; real marked Telegram request returned a persisted dated health
  summary, accurately named the separately degraded source sync, and delivered text plus audio after
  four successful health MCP calls.

## Case TR-020: Terse Follow-Up Retains Immediate Native Conversation Context

- **Requirement:** A GlassHive-backed Telegram conversation must preserve the immediately preceding
  assistant turn when a short user reply depends on it, without pinning time-varying turn context in
  durable worker authority or assigning native-session usage to one visible message.
- **User outcome:** After the assistant asks whether to prepare two synthetic draft replies, a terse
  approval such as `yes` continues that exact task instead of asking what the approval meant or
  drifting to an unrelated older topic.
- **Surfaces:** Telegram bridge, AgentClient visible-message pruning, GlassHive native conversation
  session, persisted canonical message chain, and local web parity surface.
- **Preconditions:** Use synthetic non-personal draft labels and a provider capability that
  structurally declares `workspace_binding=true` and `conversation_session=true`; test both direct
  provider IDs and a generic adapter with the native provider in `endpoint`.
- **Steps:** Establish an assistant question about two synthetic drafts, send a terse approval, then
  send a short correction. Inspect the visible reply, canonical parent chain, locally recomputed
  token counts, native worker/session identity, and developer-instruction snapshot across turns;
  refresh/reopen the conversation and repeat once.
- **Expected result:** The immediate assistant question remains in the model-visible history; the
  approval resolves both synthetic drafts; ordinary current-time changes do not replace the native
  worker; native aggregate usage never inflates a tiny visible message; refresh preserves the same
  coherent thread.
- **Forbidden result:** `What were you agreeing to?`, an unrelated older PDF/checklist/topic,
  prompt-text or recipient-specific routing, one worker replacement per turn, a five-digit token
  count on a tiny reply, or an external message/action during QA.
- **Evidence to capture:** focused token/time-context RED-to-GREEN regressions, Telegram and
  GlassHive adjacent suites, active installed artifact identity, synthetic user-visible turn and
  refresh evidence, sanitized worker/session and role-order trace, and a dated public-safe report.
- **Last run:** PASS 2026-08-20. Real private Telegram established a synthetic question and a
  terse `yeah`; the visible answer retained the exact referent. The same active candidate passed a
  non-admin browser continuity, native-tool detail, and refresh/persistence run.

## Case TR-030: Reply To A Scheduled Output Outranks Stale Interactive Ancestry

- **Requirement:** A Telegram reply to a durable scheduled Main output must resolve that exact
  logical assistant message even when the reusable Telegram conversation contains a newer or more
  salient unrelated interactive topic.
- **User outcome:** Replying `why did you say this?` to a scheduled message explains the scheduled
  message itself. It does not answer an older interactive exchange, deny authorship, or suggest
  spoofing.
- **Surfaces:** Telegram Desktop, owner/chat-scoped transport receipts, Core interaction context,
  session-backed provider turn-context admission, native delta instruction, and Mongo persistence.
- **Steps:** Establish one synthetic interactive topic, create one synthetic one-time Main schedule
  with a distinct exact output, reply to the delivered scheduled bubble, and inspect the visible
  answer plus sanitized receipt, message, provider-request, and native-instruction evidence.
- **Expected result:** `ReplyContextV1` is verified as `assistant_self` and `schedule_result`; the
  new user body contains only the new question; the bounded native delta contains the typed capsule
  and exact scheduled quote; the visible answer discusses that scheduled output.
- **Forbidden result:** The native delta omits the capsule; old interactive ancestry wins; quoted
  text is concatenated into user text; a second schedule is invented; or the assistant denies the
  message, blames another thread, or raises a security/spoofing theory.
- **Evidence to capture:** private Telegram before/after screenshots, sanitized Mongo reply context,
  schedule delivery state, provider replay decision, native-instruction membership checks, focused
  regression tests, active runtime identity, and a dated public-safe report.
- **Last run:** PASS 2026-08-20. The defect reproduced before the admission repair. After the
  supported restart, the same private Telegram path explained the exact scheduled output. Mongo and
  GlassHive agreed on verified schedule provenance, one delta attempt, and the exact per-turn quote.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Telegram Runtime. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `TELEGRAM-UC-001` | Start or inspect Telegram runtime status while a synthetic polling-conflict log fixture is present. | `TR-001`, `TR-003` | Telegram status command, launcher/supervisor path, and sanitized logs | Status output, scoped process list, launcher tests, and dated QA report | Telegram is shown as running with issues, scoped restart clears only Viventium-owned pollers, and no broad process kill occurs. | PARTIAL 2026-05-14: automated synthetic coverage passed |
| `TELEGRAM-UC-002` | Send or simulate a Telegram turn whose model provider rejects credentials. | `TR-002`, `TR-004` | Telegram bridge stream, user-visible reply, and sanitized logs | Stream regression test, provider-auth status output, sanitized logs, and QA report | The reply gives provider reconnect guidance instead of blaming Telegram transport or leaking raw provider errors. | PARTIAL 2026-05-14: bridge regression coverage passed |
| `TELEGRAM-UC-003` | Restart Telegram runtime and compare status/log evidence before and after restart. | `TR-001`-`TR-004` | CLI launcher/status, process list, logs, and Telegram bridge state | Scoped process evidence, status output, sanitized logs, and tests | Restart removes only stale scoped pollers, preserves unrelated processes, and status after restart matches the actual bridge state. | PARTIAL 2026-05-14: static regression coverage passed |
| `TELEGRAM-UC-004` | Simulate a primary provider-rate-limited Telegram turn while audio replies are enabled. | `TR-005` | Main-agent fallback classifier, Telegram bridge stream, and voice gate | Fallback regression test, stream regression test, sanitized log class, and QA report | A valid configured fallback produces the answer; otherwise the terminal provider-rate-limit blocker is visible text only and non-spoken. | PARTIAL 2026-06-28: automated regression passed; live external Telegram remained incomplete |
| `TELEGRAM-UC-005` | Render a worker-style Markdown table result for Telegram. | `TR-006` | Telegram Markdown-to-HTML renderer and visual fixture | Renderer regression test and browser screenshot/check with synthetic content | The user sees readable rows, not raw pipe-table syntax. | PASS 2026-06-28: automated plus Playwright visual coverage passed |
| `TELEGRAM-UC-006` | Send one explicit synthetic memory and one natural synthetic event, then ask about each from new Chrome/voice conversations. | `TR-007`, `MEMCONT-004`, `RAG-005` | real Telegram, Chrome, Modern Playground voice | DB revisions, recall source, logs, visible/audible results, cleanup | Saved memory and recall each work through their own lane and neither depends on the original Telegram thread. | NOT RUN — cataloged 2026-07-11; integrated rerun required |
| `TELEGRAM-UC-007` | Ask Telegram to launch a synthetic GlassHive task, then send a terse status/wait follow-up. | `TR-008`, `AGCFG-005` | synthetic Telegram identity and isolated LibreChat/GlassHive runtime | visible messages, provider-bound tools, persisted fixture calls, GlassHive run/events, logs, latency | Both turns retain tools, the task is launched and checked, and no false unavailable claim appears. | PARTIAL 2026-07-13: binding/discovery regressions passed; dedicated Telegram path was not run |
| `TELEGRAM-UC-008` | Send natural positive, calm, and negative always-voice turns without naming voice controls. | `TR-009`, `TGVOICE-005`, `EMO-036` | synthetic Telegram identity and configured TTS fixture | clean bubbles, delivered/played audio, marker counts, provider telemetry, prompt-frame layers, synthetic Feeling state | Expressive moments use fitting supported controls, calm delivery stays restrained, and no markup leaks. | PARTIAL 2026-07-16: provider-boundary fixtures passed; dedicated delivery/playback remained incomplete |
| `TELEGRAM-UC-009` | Stop or restart Viventium with Telegram disabled and no ownership receipt, then repeat with a synthetic valid receipt. | `TR-010` | launcher stop/restart path with synthetic launchctl recorder | recorder calls, receipt mode/content, isolated stop log, and release test | No-receipt state makes no launchctl call; valid ownership removes only the receipt-backed label and clears the receipt. | PASS 2026-07-20: automated two-sided test and isolated Easy Install stop evidence passed |
| `TELEGRAM-UC-010` | Upgrade/restart from a second checkout, then repeat with candidate failure, PID reuse, and an unknown process fixture. | `TR-011` | isolated launcher/poller state and synthetic process identities | owner/transaction receipts, process start identities, launcher logs, rollback result, and no-signal assertions | Exactly one recognized poller owns the token; readiness commits success, safe rollback restores failure, and unknown/reused PIDs remain untouched. | PARTIAL 2026-07-25: automated and bounded handoff passed; external delivery remained incomplete |
| `TELEGRAM-UC-011` | Hold the durable delivery API unavailable through repeated poll attempts, recover it, then enqueue a synthetic late callback. | `TR-029` | Telegram LibreChat bridge dispatcher | deterministic delays, warning/recovery logs, callback delivery timing and ledger status | Failure polling backs off without log spam; recovery restores normal polling and late delivery semantics. | PARTIAL 2026-07-24: automation passed; external callback delivery was not run |
| `TELEGRAM-UC-012` | Send a synthetic text turn while the empty GlassHive delivery poller is active, then repeat after a runtime restart. | `TR-013` | Telegram bot chat and promoted local runtime | visible timing, pending-update count, process sample, bridge/API logs, active checkout identity | Both updates leave the queue promptly and receive a visible reply; loopback polling performs no unused CA-bundle work. | PARTIAL 2026-07-25: automated coverage passed; visible post-restart reply timing remained incomplete |
| `TELEGRAM-UC-013` | Upgrade or activate from a checkout with legacy repo-local Telegram preferences, then force a candidate failure and restart twice. | `TR-014`, `CONT-014` | supported CLI/helper, installed Telegram component, App Support preference state, real Telegram | component/selection/receipt identities, migration backup hashes, source-tree no-write proof, visible replies and latency | Preferences remain exact, the source tree is untouched, and rollback and success execute from App Support. | PARTIAL 2026-07-25: automated contract passed; installed restart/message lane remained incomplete |
| `TELEGRAM-UC-014` | Send `/call`, open it in one browser, retry a lost exchange, then replay it from another browser and after Agent revocation. | `TR-012`, `MPV-052`, `MPV-053` | real Telegram bot, public HTTPS playground, two browser contexts, linked chat | delivered link class, fragment/exchange order, replay statuses, cache/referrer/log scan, ACL audit, audible call, persistence | The first browser enters one-click Call; retry is safe; replay and revoked Agent fail without disclosure or mutation. | PARTIAL 2026-08-09: real cross-surface journey remained incomplete |
| `TELEGRAM-UC-015` | Start a new Telegram conversation and ask for a short result from an authorized connected MCP. | `TR-022`, `GH-MCP-BROKER-023`, `VH-022` | real Telegram Desktop and active LibreChat/provider runtime | visible text/audio, finalized Mongo turn, broker/MCP logs, source status | The first turn uses the connected tool and reports dated evidence or its exact blocker. | PASS 2026-08-11: real owner health request, four MCP calls, persisted final response, text/audio delivery, and zero missing-scope warnings |
| `TELEGRAM-UC-016` | Send a turn whose primary returns an exact pre-authoring quota rejection while its configured fallback is healthy. | `TR-005`, `TR-023`, `GCP-031` | real Telegram bot, LibreChat SSE, GlassHive state | delivered bubble, fallback settings, attempt identity, replacement run, activity/error classes | The original turn stays open and receives one fallback-authored answer without exposing the primary error. | PASS 2026-08-04: real quota/provider-unavailable recovery passed without duplicate authoring |
| `TELEGRAM-UC-017` | Receive a main answer and follow-up containing emphasis inside a Markdown block quote. | `TR-024` | real Telegram bot plus shared renderer visual fixture | delivered bubbles, renderer output, regressions, active source/hash, sanitized logs | Original words remain visible and no internal placeholder or raw tag appears. | PARTIAL 2026-07-27: source and real rendering passed; installed bridge restart remained blocked |
| `TELEGRAM-UC-018` | Configure, disable, or omit the background follow-up window and run a synthetic Telegram turn. | `TR-025` | generated service env and bridge lifecycle harness | compiler output, listener/task state, focused regressions | Canonical config owns listening, zero disables it, and no implicit timeout remains. | PARTIAL 2026-08-10: automation passed; live delivery was not run |
| `TELEGRAM-UC-019` | Send rapid A/B/C text while B is unfinished, then repeat with a preview-deletion fault. | `TR-026`, `TR-027` | Telegram Desktop, bridge/core lifecycle, persisted history | bubbles, revision logs, ordering, delivery outcome, reopen | One current answer survives, stale preview mutation stops, and successful supersession is not a connection error. | PARTIAL 2026-08-22: prior visible-preview live path passed; exact source-before-presentation race remained open |
| `TELEGRAM-UC-020` | Send a voice note or file and then a clarification while an unfinished reply exists. | `TR-028` | Telegram Desktop, transcription/file path, persisted history | transcript/file receipt order, attachment state, final bubble, failure regression | Finalized source segments survive supersession and pending failure is truthful. | NOT RUN — cataloged 2026-08-11; real integrated surface required |
| `TELEGRAM-UC-021` | Approve or correct an immediately preceding assistant question with a terse reply. | `TR-020` | installed Telegram or synthetic local web parity path, then refresh/reopen | visible messages, canonical parent chain, token counts, native worker/session identity, provider role order | The reply resolves the immediate question and no older topic is substituted. | PASS 2026-08-20: Telegram and browser continuity, tool, refresh, and persistence paths passed |
| `TELEGRAM-UC-022` | Reply to a scheduled Main bubble while the reusable conversation contains an unrelated interactive topic. | `TR-030`, `MCK-005`, `MCK-006` | Telegram bot, outbound receipt ledger, Core, Mongo, GlassHive native session | visible scheduled bubble/reply, reply descriptor, provider delta, schedule delivery row | The reply explains the exact scheduled output and verified reply context outranks stale ancestry. | PASS 2026-08-20: before/after Telegram reproduction and runtime evidence passed |
| `TELEGRAM-UC-023` | Send a text turn, then a voice note whose transcription is delayed behind a later text receipt; repeat with transcription unavailable and one file. | `CC-048`, `TR-028` | Telegram bot, transcription route, ordered source ledger, linked file surface | receipt order, source classification, transcript status, assistant bubbles, file metadata, logs | The transcript remains source input; receipt order is preserved and failure produces one truthful combined-turn result. | NOT RUN — cataloged 2026-08-30 |
| `TELEGRAM-UC-024` | Toggle parallel work, recover after a lost action response, and inspect the retained mission after restart. | `TR-018`, `PWK-UC-016`, `PWK-UC-017` | Telegram Desktop, Core, GlassHive, persistence | visible cards/actions, idempotent receipts, run counts, delivery ledger | Retrying the same action never duplicates work and retained missions remain controllable. | PARTIAL 2026-08-18: Message, Queue, Resume, Stop, Dismiss, and one browser continuation passed; remaining actions and restart retry stayed open |
| `TELEGRAM-UC-025` | Ask a specialist worker for an answer while its primary provider fails before authoring. | `TR-019` | Telegram bot, graph participant, configured fallback | provider attempts, tool counts, one delivered reply, persisted identity | The configured participant fallback answers once without replaying external effects. | PARTIAL 2026-08-18: deterministic recovery passed; post-restart Telegram correlation remained incomplete |
| `TELEGRAM-UC-026` | Ask a nested worker to answer while its provider authentication is unavailable. | `TR-021` | installed Telegram, Core, GlassHive worker | structured error class, zero durable residue, actionable visible wording | The user is told to reconnect the provider and retry; no raw error, loop, or orphaned work appears. | PASS 2026-08-18: installed failure reproduction and focused runtime suites passed |

## Release Test Traceability

- `tests/release/test_telegram_codex_runtime_paths.py`
- nested Telegram `/call` route, call-launch exchange, and Voice Agent authorization suites
- `tests/release/test_telegram_lazy_startup_contract.py`
- `tests/release/test_telegram_launchctl_ownership.py`
- `tests/release/test_telegram_poller_handoff.py`
- `tests/release/test_telegram_runtime_component.py`
- `tests/release/test_telegram_transcription_error_contract.py`
- `tests/release/test_tr026_installed_journey_runner.py`
- `tests/release/test_tr026_installed_journey_semantic_verifier.py`
