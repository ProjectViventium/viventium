# GlassHive Host-Native Workers QA

## Purpose

This is the public-safe QA source of truth for GlassHive workers that run directly on the user's
host computer through local Codex, Claude, or OpenClaw CLIs.

Host-native workers are intentionally no-sandbox. QA must prove both capability and operator
visibility without publishing private logs, screenshots, local usernames, hostnames, secrets, or
absolute home-directory paths.

## Acceptance Gates

- Config compiler emits host-worker env only when GlassHive is enabled.
- When host workers are disabled, generated env/instructions force Docker defaults and GlassHive
  API/MCP reject host-native create/resume/run/action paths.
- GlassHive API/MCP accepts `execution_mode=host`, `alias`, and `workspace_root`.
- `worker_find_or_resume` reuses a stable alias instead of creating duplicate workers.
- Host worker bootstrap creates `project-definition.md`, `work-log.md`, `harness-prompt.md`, and
  agent context files under the configured user-scoped workspace root.
- Uploaded files and tool resources from the triggering request are projected into the GlassHive
  bootstrap bundle and materialized under the worker `uploads/` directory when a local path or
  extracted text is available.
- Request upload paths are constrained to the configured LibreChat uploads root. Arbitrary
  `source_path` values, symlink traversal, and oversized trusted-source copies must be rejected.
- `worker_live` exposes `work_log_tail`, `action_audit_tail`, `prompt_paths`, and `execution_mode`.
- Parent-visible logs are redacted; raw run logs stay local-only with restrictive permissions.
- Viventium agent source-of-truth routes explicit `@codex`, `@claude`, and `@openclaw` mentions
  through GlassHive MCP instead of controller-level parsing.
- GlassHive callbacks are signed and persist completion/blocker updates to the originating
  conversation when callback context is present.
- Callback receiver rejects stale signatures, replayed callback ids, and conversations not owned by
  the callback user before writing a follow-up message.
- Callback receiver ignores non-terminal lifecycle events, anchors visible terminal/actionable
  updates to the assistant response message id, and updates one status message for later visible
  callbacks from the same run, so worker lifecycle updates do not create LibreChat sibling branches.
- Callback receiver repairs callback message timestamps when a blank assistant anchor was created
  before the user message, so chronological and tree views both show the user request before the
  worker result.
- Telegram and voice surfaces use the same persisted GlassHive callback message plus a durable
  surface-delivery ledger so worker completion/blockers reach the originating chat/call without a
  manual status follow-up, even after the original in-turn poller exits.
- Web, Telegram, and voice arm the long GlassHive callback polling window only from structured
  GlassHive MCP/tool evidence, not from ordinary non-GlassHive tool calls.
- Missing host OpenClaw CLI degrades only `@openclaw`; Codex and Claude host workers remain usable.

## Destructive Confirmation Scope

When destructive confirmation is enabled, workers must checkpoint before:

- writes outside the host workspace
- `git push` or public publishing
- global package installs or system package changes
- launch agent, cron, shell profile, login item, or background service changes
- access to SSH keys, keychain, browser cookies, tokens, or credential stores
- killing processes not started by the worker
- broad network exfiltration or non-allowlisted bulk upload

## Test Matrix

- Unit: host workspace bootstrap and unwritable-root failure.
- Unit: Codex/Claude/OpenClaw host command construction.
- Unit: one active host worker per CLI family.
- Unit: parent-visible redaction for token-like strings.
- Unit: existing upload/file-resource metadata projects into `bootstrap_bundle.files`.
- Unit: virtual `/uploads/...` filepaths map to the configured uploads root, while arbitrary
  source paths and symlinks are rejected.
- Unit: host child env strips callback/provider/LibreChat secrets.
- API: `worker_create` host fields round-trip.
- API: `worker_find_or_resume` reuses an alias.
- MCP: host execution arguments and callback context are accepted.
- Compiler: host-worker env, callback URL/secret, and MCP request-context headers.
- Compiler/preflight: host-worker disable gate, absolute workspace root, and separate Codex,
  Claude, and OpenClaw doctor checks.
- Local QA: synthetic `@codex` and `@claude` tasks create/update `work-log.md` and complete.
- Local QA: `@openclaw` reports a clear unavailable message when the CLI is absent.
- Browser QA: a synthetic browser task uses host browser access without publishing screenshots.
- Callback QA: signed `run.completed`, `run.failed`, and `checkpoint.ready` callbacks appear in the
  originating conversation.
- Callback delivery QA: late Telegram-surface callbacks are enqueued, claimed, delivered once,
  retried on failure, and observable in backlog checks without relying on prompt text or in-memory
  request state.

## 2026-05-05 Regression: Telegram GlassHive Completion Delivery

Trigger: a Telegram user asked Viventium to delegate a GlassHive task and expected the worker result
to return automatically in the same Telegram chat. The worker completed, but the final result was
visible only after manual follow-up or local inspection.

Expected behavior:

- Telegram, web, API, and voice use the same agent/MCP path for GlassHive delegation.
- A GlassHive completion callback persists one same-conversation callback message and enqueues one
  durable Telegram delivery row.
- Telegram sends the result after the original in-turn poll window, process restart, or transient
  disconnect without requiring the user to ask what happened.

Public-safe root cause:

- Telegram had a short in-memory poller fast path, but no guaranteed delivery row for late
  GlassHive callbacks on the Telegram surface.
- LibreChat accepted and persisted a Telegram-surface callback even when delivery enqueue failed,
  so GlassHive marked the callback delivered while Telegram had no durable work item to claim.
- Duplicate callback handling checked process memory before DB repair, so a recently accepted
  callback could block repair of a missing Telegram delivery row until the replay cache expired.
- A local provider token expiry surfaced to Telegram as a generic connection error, masking that no
  GlassHive worker had actually been started for that turn.
- Local Telegram sidecar logs could include token-bearing Bot API URLs when third-party HTTP logs
  were enabled.

Regression coverage added or re-run:

- LibreChat callback route tests now cover retryable delivery-enqueue failure, persisted duplicate
  repair, and repair while the callback id is still in the in-memory replay cache.
- GlassHive callback delivery service tests cover sanitized full-text enqueue behavior and the
  conflict-free Mongo upsert contract.
- OpenAI connected-account initialization tests cover refreshing expired OpenAI subscription
  credentials and returning reconnect guidance when refresh is impossible.
- Telegram bridge tests cover provider-authentication error mapping to user-actionable reconnect
  guidance instead of a generic connection error.
- Telegram sidecar logging tests cover redaction of token-bearing Bot API URLs.
- Live user-path QA with synthetic text verified:
  - a Telegram request reached Viventium and created a host `codex-cli` GlassHive worker
  - the worker completed on the host execution path
  - the callback outbox posted `run.completed`
  - the Mongo delivery ledger row reached `sent`
  - the final callback appeared in the same Telegram chat without manual follow-up

Known operational follow-up:

- The local developer stack can still be made unhealthy by multiple stale LibreChat nodemon
  supervisors competing for the API port. That is a launcher/supervision hygiene issue, not a
  GlassHive callback correctness issue, but it can still cause Telegram to report a temporary
  reachability failure while the API is restarting.

## 2026-05-08 Regression: Operator Handoff And Callback Branching

Trigger: a web-chat user asked Viventium to run a Docker GlassHive worker without blocking chat,
then watch, steer, and receive the result in the same conversation. The worker could complete, but
the visible handoff was unreliable: the model could expose the raw workstation/noVNC page instead of
the operator page, completed HTML deliverables could remain on the GlassHive placeholder page,
GlassHive tool rows could disappear after completion, and late callbacks could appear as sibling
assistant branches instead of continuing the active chat.

Expected behavior:

- Web chat can delegate long-running GlassHive work without blocking normal follow-up messages.
- The model receives and surfaces the operator `watch` URL for web/API surfaces; raw noVNC URLs are
  diagnostic-only.
- The operator page exposes watch, pause/play, interrupt, steer, and takeover controls while the
  worker is running or ready.
- When a worker creates a browser-deliverable page, the sandbox browser opens that page so the
  operator view shows the result, not the placeholder.
- GlassHive tool calls remain visible and expandable after completion, like other tool calls.
- Late GlassHive callbacks append to the active conversation leaf. If the user has just typed a
  follow-up and the assistant response is not persisted yet, the receiver returns a retryable status
  instead of writing a sibling branch.

Public-safe root cause:

- GlassHive exposed multiple URL concepts to the model, and the raw workstation URL could be chosen
  even when the product contract required the operator URL.
- The runtime detected the completed result text but did not structurally promote a generated HTML
  deliverable into the visible workstation browser for Docker workers.
- LibreChat had a GlassHive-specific display optimization that could hide completed GlassHive tool
  rows.
- The callback receiver used the original request/assistant anchor too aggressively as the visible
  tree parent. Once the user had continued the conversation, a late completion could be stored as an
  alternate assistant sibling.
- Docker Codex resume output did not share the host-native final-report contract, so a resumed steer
  run could repeat stale previous-result text even when the workspace file changed correctly.

Regression coverage added or re-run:

- GlassHive runtime tests cover operator URL emission for web/API surfaces, URL omission for
  non-web surfaces, deliverable payloads, worker takeover URL shape, Docker final-report command
  injection, and final-report parsing on resume.
- LibreChat callback route tests cover leaf-aware callback append, retryable callback handling while
  a moved-on user message is the current leaf, repeated status update for the same run, and distinct
  later runs from the same worker appending without overwriting earlier results.
- LibreChat frontend tests cover persistent GlassHive tool rows and clearer GlassHive tool labels.
- Config compiler tests cover generated `GLASSHIVE_OPERATOR_BASE_URL`.
- Browser QA with synthetic content verified:
  - chat remained usable while a Docker worker ran
  - the model surfaced an operator watch URL
  - the operator page exposed ready status, pause/play, interrupt, menu, and steer controls
  - the sandbox browser opened the delivered `index.html` page
  - a steer request changed the workspace file and visible page state
  - a late signed callback appended to the active conversation line without sibling navigation
  - a second callback from the same worker but a different run appended after the first callback

Second-opinion review:

- A review-only local Claude pass agreed with the operator/deliverable direction and flagged the
  same-worker callback overwrite risk. The implementation now scopes callback updates by both
  worker and run id, while distinct later runs append as new results.

## Latest Public-Safe QA Snapshot

Executed with synthetic data and temporary runtime directories only:

- GlassHive runtime suite: full runtime test suite passed with expected skips.
- Parent compiler/preflight/runtime-NLU slice: host-worker and no-runtime-NLU checks passed.
- LibreChat callback route: invalid HMAC, valid completion, early-response anchoring, in-place
  status update, silent lifecycle events, stale callback, replay, and cross-conversation rejection
  passed.
- LibreChat MCP env placeholders: request-scoped upload headers and DB-sourced placeholder blocking
  passed.
- API user-flow QA: created a host project, created/resumed a Codex host worker by alias,
  materialized a synthetic upload into `uploads/`, completed a run, exposed live work-log/action
  audit/prompt paths, and returned a clear missing-OpenClaw message.
- Browser QA: opened the worker console, verified `Host Computer Tools`, workspace file listing,
  nested prompt path rendering, and submitted a browser run that completed.
- Callback QA: browser-submitted run delivered `worker.ready`, `run.queued`, `run.started`, and
  `run.completed` callbacks with fresh timestamps and valid per-run HMAC signatures.
- Regression QA: host-worker disabled config rejects host create/run, callback outbox replay does
  not block service startup, and non-GlassHive tool turns do not start GlassHive callback polling.

## 2026-04-28 Regression: Host Browser Delegation

Trigger: a user asked Viventium to use GlassHive/Codex to open Chrome on the main computer and
navigate to Investing.com. The visible chat reported only that the run was queued.

Public-safe root cause:

- The worker created for a main-computer browser task used `execution_mode=docker`, so it targeted a
  sandbox workstation instead of the host Chrome session.
- The Docker Codex run then failed while starting its attached `screen` session because the container
  screen runtime directory was not prepared before use.
- The running MCP process did not have generated callback/upload env loaded, so the failed run could
  not report back into the originating conversation.

Regression coverage added or re-run:

- Compiler/preflight now default GlassHive host workers on when GlassHive is enabled and emit
  `WPR_DEFAULT_EXECUTION_MODE=host`, host workspace root, upload-root projection, and callback env.
- Direct local stack launcher now loads the canonical compiled runtime env before starting
  GlassHive.
- MCP `worker_create` and `worker_find_or_resume` default to the configured execution mode when the
  caller omits `execution_mode`.
- Docker screen attach/session startup prepares the runtime screen directory before invoking
  `screen`.
- Synthetic live MCP QA created a Codex worker without `execution_mode`, verified it became a host
  worker under `~/viventium`, materialized an existing LibreChat upload into `uploads/`, exposed
  prompt paths/work-log/action-audit via `worker_live`, and launched a host browser URL.
- Real host Codex `worker_run` QA completed a task that opened a new Chrome tab at Investing.com and
  reported the final URL/title.
- Callback route tests passed for valid completion, invalid signature, stale callback, replay, and
  wrong-conversation rejection.
- Second-opinion review raised two immediate hardening items that were folded into this pass:
  GlassHive callback secrets compile as a scoped derivative instead of the raw call-session secret,
  and one-active-host-worker-per-CLI-family plus per-run callback binding now have explicit
  regression tests.
- Real UI QA from the local QA account then exposed an owner-context gap: the model can omit
  `owner_id` even though Viventium passes user context in MCP headers. GlassHive MCP now defaults
  project/worker ownership from `X-Viventium-User-Id` so chat, API, and voice paths do not depend on
  the model guessing an owner id.
- Real UI QA also exposed a conversation-branching gap: GlassHive callbacks used the original parent
  context as the visible tree parent, so status messages became sibling assistant branches. The
  callback receiver now prefers the assistant response id as the initial tree anchor and updates the
  existing worker status message for repeated visible callbacks from the same run.

## 2026-04-28 Regression: Host Worker Proof Flow

Trigger: a user asked Viventium to prove host-native GlassHive/Codex control by driving the main
computer browser. The main worker launched, but visible chat output was noisy, contradictory, and
did not receive a clean worker completion report.

Public-safe root cause:

- Several non-operational background cortices activated on a direct proof-by-execution request and
  produced unsupported claims. One background insight fabricated a dispatch transcript instead of
  grounding itself in a tool result.
- GlassHive callback signing escaped Unicode in the JSON body while the Viventium callback receiver
  verified the literal UTF-8 stable JSON body, so normal task text containing punctuation could fail
  HMAC verification with `401 Unauthorized`.
- The host worker reached the browser task result, but screenshot proof failed when a local helper
  script was executed directly under macOS quarantine instead of through a shell interpreter.
- Parent-visible `worker_live` output exposed image/base64 console payloads that should remain in
  local raw logs only.
- Startup/admin reconcile counted an old `running` run after its worker process was gone, leaving
  stale active-work noise in status views.

Regression coverage added or re-run:

- GlassHive callback signing now uses literal UTF-8 canonical JSON and has a byte-level regression
  test.
- Viventium callback route tests still pass for invalid signatures, valid completion, early-response
  anchoring, in-place callback updates, stale callbacks, replay, and wrong-conversation rejection.
- A live synthetic Unicode callback probe returned a scoped conversation rejection instead of an
  HMAC rejection, proving the Unicode signature path is accepted before persistence.
- Host workspaces now materialize a capture helper, clear macOS quarantine best-effort, warn if
  helper permission setup fails, and instruct workers to invoke shell helpers through `bash`.
- `worker_live` redacts parent-visible data URLs, image payloads, long base64 blobs, and
  credential-looking values before returning console/log tails.
- Startup/admin reconcile now interrupts orphan `running` runs only if the row is still in the
  expected state, preventing stale active-run counts without regressing a run that completed during
  reconciliation.
- Generic cortex output rules now forbid claims about tool, worker, browser, email, file, or OS
  actions unless the cortex has a verified tool result from the current run.
- Source-of-truth activation prompts for the implicated non-operational cortices were tightened so
  direct proof-by-execution requests stay with the main agent and GlassHive worker path.

Known live-sync status:

- The source-of-truth activation prompt fix was not written into the live agent database during this
  incident because the operator explicitly disallowed pushes. A narrow activation-config-only dry
  run showed the intended scoped update path; applying it requires an explicit reviewed local sync.

## 2026-04-28 Follow-Up: Callback And Activation UX Hardening

Additional RCA from the browser-proof and Telegram follow-up flows found four product gaps:

- Background activation needed a shared, source-of-truth direct-action policy instead of per-cortex
  GlassHive-specific wording.
- Empty or `{NTA}` cortex outputs were still emitted as visible "Insight from ..." cards.
- `run.started` callbacks and fallback text exposed worker plumbing in the user conversation.
- A stale run stop reason could cancel a later successful host run after stdout had already been
  written.

Required acceptance coverage:

- Activation policy is rendered from configured direct-action surfaces and exact attached tool
  names, not user-text heuristics or tool-name suffix parsing.
- Empty and exact `{NTA}` background outputs are silent and do not produce visible insight cards.
- User-visible GlassHive callbacks do not show worker IDs, run IDs, ports, terminal URLs, or
  `queued/running` status unless explicitly requested.
- GlassHive MCP can recover callback URL/secret from canonical runtime env if the sidecar was
  launched without those variables in process env.
- A run-scoped stop reason from one run cannot poison a later successful run.
- If `WorkerTerminatedError` fires after completed artifacts exist, the service recovers the run
  output before choosing a cancelled state.
- User-facing worker/project names are natural task labels; stable aliases may remain internal.

## 2026-04-29 Follow-Up: Surface Completion And Activation Policy

Additional QA from call/Telegram worker delegation found that persisted GlassHive callbacks were
visible in the web conversation but were not treated as speakable/same-surface follow-ups by voice or
Telegram. Background activation also needed a generic direct-action policy rather than wording tied
to any one named background agent.

Fixes verified with synthetic data:

- The global activation policy now says the main agent owns the turn, direct-action surfaces own live
  execution/status/results, and background agents activate only for separately scoped analysis they
  explicitly own. The wording avoids per-agent-name overfitting.
- GlassHive lifecycle events such as worker ready, queued, started, paused, interrupted, and
  terminated are silent by default; only completion/failure/approval/takeover/cancel states are
  user-visible.
- Repeated visible callbacks for the same run update one GlassHive status message.
- Visible callbacks without the assistant response anchor are ignored/retried instead of creating
  sibling assistant branches.
- GlassHive retries transient callback delivery failures with the same callback id; Viventium marks
  a callback id as seen only after the status message is saved or updated.
- Viventium also checks persisted callback metadata for replayed callback ids after process restart
  and sanitizes callback text before chat/voice persistence.
- Voice and Telegram have DB-backed GlassHive callback polling endpoints keyed by the assistant
  message id and conversation, matching the existing persisted follow-up pattern.
- Request surface, stream, voice-call, Telegram identity, and existing upload/file-resource context
  are projected into the GlassHive bootstrap bundle through the same MCP request path.

Regression coverage run:

- LibreChat route/service/controller tests for callback HMAC, UTF-8 callback text, required
  assistant anchor, silent lifecycle events, visible event copy, callback text sanitization, status
  update, replay from persisted metadata, retry-after-persistence-failure, voice/Telegram GlassHive
  polling endpoints, activation policy rendering, and upload/context projection.
- GlassHive runtime tests for callback context projection, upload projection, signed callback
  payloads, transient callback retry, and configurable retry budget.
- Voice worker follow-up tests, including speaking a persisted GlassHive callback.
- Telegram bridge follow-up tests, including delivering a GlassHive callback without cortex parts.

## 2026-04-29 Follow-Up: Browser QA Tool Rows And Live Callback Polling

Additional real-browser QA against a synthetic GlassHive status request found two user-visible gaps:

- Streamed duplicate snapshots for the same tool call rendered as extra `Cancelled` rows before the
  completed tool result. The renderer and shared content sanitizer now collapse repeated
  `tool_call.id` snapshots to the latest part, so historical conversations clean up on refresh and
  future completions persist only the final snapshot. The primary conversation read route and branch
  creation path also apply the same sanitizer so the fix is not only a render-time mask.
- Out-of-band direct-action callbacks could be persisted correctly but stay invisible in an already
  open chat until manual reload. The existing post-stream polling hook now also polls after recent
  tool-using assistant responses and stops when a structured Viventium callback message appears.

Regression coverage run:

- Shared `@librechat/api` content sanitizer tests for malformed tool calls and duplicate streamed
  snapshots.
- Client renderer tests for duplicate tool-call snapshot suppression.
- Client follow-up polling tests for post-tool callback discovery and stop-on-callback behavior.
- Browser QA with Computer Use verified a GlassHive status request stayed on the main tool path
  without background-agent insight cards and, after refresh, showed only the two completed tool rows.

## 2026-04-29 Follow-Up: Telegram Host Worker Completion Drop

Live Telegram QA with a host-native browser/profile lookup exposed a delivery gap: the worker
completed and stored the final summary in GlassHive, but Telegram only delivered an interim
"still working" message and never returned the result.

Root causes:

- The compiled MCP server headers in the generated runtime were missing surface, stream, voice, and
  Telegram identity metadata even though the source-of-truth YAML already had them. This meant
  GlassHive workers were created without enough same-surface callback context.
- The GlassHive worker bootstrap had conversation/message context but no callback URL or HMAC
  secret, so completion stayed in GlassHive state and was not pushed back to Viventium.
- Telegram's GlassHive callback polling inherited the shorter background-follow-up window. The
  host browser run finished after that window, so the bridge stopped polling before the final
  callback/result could appear.

Fixes:

- Config compiler now emits the full GlassHive MCP request-context header set from the canonical
  source of truth.
- GlassHive service recovers callback URL and HMAC secret from canonical runtime env when a worker
  has callback context but was created before those values were materialized into the bundle.
- Telegram and voice compile a separate `glasshive_followup_timeout_s` window, defaulting to 600s,
  and Telegram defaults to 600s even when the env is absent.
- Main-agent wording now tells GlassHive delegations not to push manual watching/follow-up onto the
  user when the product can report completion automatically.

## 2026-04-29 Follow-Up: Host CLI Timeout And Blank Callback Rendering

Live QA of a host-native browser/billing task exposed two separate regressions:

- The host Codex CLI runner still had a hard 300 second process wait, so a valid long-running
  background worker could be killed even after it had discovered useful results.
- A GlassHive callback status update could save `text` while leaving an older tool-call-shaped
  `content` payload on the same assistant message. The chat renderer then treated the message as
  non-text content, producing an empty or blocked-looking response.

Fixes:

- Host-native CLI runners now have no default hard run timeout. An explicit deployment timeout is
  still available through runtime env when an operator wants one.
- Docker CLI workers also no longer inherit the old hard 300s run timeout by default; `GLASSHIVE_RUN_TIMEOUT_SEC`
  / `WPR_RUN_TIMEOUT_SEC` provide the explicit operational cap when needed.
- GlassHive writes outbound callbacks to a local SQLite outbox before delivery and replays pending
  callbacks on restart and on a periodic retry loop with the same callback id, fresh timestamp, and
  fresh HMAC signature.
- Viventium callback persistence writes displayable structured text content whenever it writes
  user-visible callback text, including updates to an existing status message.
- Client message rendering now tolerates legacy malformed object content and keeps polling after
  non-terminal GlassHive lifecycle callbacks until a terminal callback is visible.
- Background/worker result delivery follows the same non-blocking adjudication contract as
  scheduled follow-ups: background systems provide durable evidence tied to the originating
  assistant message; the main-agent continuation/follow-up path decides whether to surface a concise
  result or stay silent with `{NTA}`.

Regression coverage run:

- GlassHive CLI runtime tests cover no-default-timeout for host and Docker workers, explicit disabled
  host timeout values, and configured timeout values.
- GlassHive callback delivery tests cover duplicate callback acknowledgements (`409`) as delivered
  no-ops, so replay-safe receiver behavior does not create false `callback.failed` noise.
- GlassHive callback delivery tests cover failed callback persistence in the local outbox,
  replay-after-service-restart delivery, and non-blocking pending replay behavior.
- LibreChat callback route tests cover visible callback content updates, in-place status update, and
  retryable rejection of visible callbacks that lack the assistant response anchor needed for
  branch-safe same-conversation delivery.
- Background follow-up prompt tests cover the main-agent continuation as the adjudicator for
  background evidence and `{NTA}`.
- Parent config compiler/preflight tests cover `runtime.glasshive_followup_timeout_s` compiling to
  Web, Telegram, and Voice timeout env vars and rejecting values outside the 30-86400 second range.
- Client renderer tests cover malformed legacy content without `content.forEach` crashes.
- Client follow-up polling tests cover startup-config-driven GlassHive callback polling windows.
- Browser QA created a synthetic callback conversation, verified `run.started` and `run.completed`
  visibility after reload, verified malformed content rendered safely, and recorded zero fatal
  frontend errors.
- Browser Use QA loaded the local Viventium QA account, opened a synthetic GlassHive callback
  conversation, confirmed the completed callback and legacy malformed content render, and recorded
  zero fatal frontend errors. Earlier Computer Use visual QA loaded the original affected
  conversation in Chrome and verified the page renders without the `content.forEach` crash or a
  blank blocked bubble.

## 2026-04-30 Follow-Up: Result Quality, Discoverability, And Visual Layout

Live QA of a host-native browser/listing task exposed three additional public-safe product issues:

- The worker completed and produced the requested extracted data, but the completion callback used
  the beginning of accumulated CLI progress output instead of the final result. The user saw a
  mid-word fragment and did not receive the useful result.
- The primary web renderer path could still collapse content-array callback text into narrow,
  hard-to-read lines when the message wrapper had no `min-width: 0`/full-width constraints.
- The main agent and GlassHive MCP descriptions relied too much on users naming implementation
  details. Users should be able to ask for a real-browser/local-computer outcome, and the
  source-of-truth prompts plus MCP schemas should steer the structured GlassHive call.

Fixes:

- Host harness prompts now require a `FINAL REPORT:` block for every run. GlassHive completion
  callbacks select that block when present, or the useful output tail for older workers.
- GlassHive and Viventium use the same visible callback text budget, and the callback receiver
  preserves paragraphs while still redacting common local/private path forms.
- All known message-rendering paths now include full-width/min-width guards around assistant
  callback content.
- Source-of-truth Viventium and GlassHive MCP prompts describe real-computer capabilities directly:
  signed-in browser sessions, desktop apps, local files/projects, installed CLIs, OS/window control,
  long-running work, and same-chat callbacks. Runtime code still relies on structured arguments,
  not keyword or provider-name heuristics.

Regression coverage added:

- GlassHive unit coverage proves a completed run callback posts the `FINAL REPORT:` result instead
  of progress chatter.
- LibreChat callback coverage proves multiline result text is preserved, local details are
  redacted, and long result text within the shared callback budget is not truncated a second time.
- GlassHive profile-runtime coverage proves default host workspace prompts require a `FINAL REPORT:`
  block in the harness and agent context files.
- GlassHive parser coverage proves accumulated Codex progress messages do not mask the latest
  assistant result or explicit `FINAL REPORT:` section.
- GlassHive API coverage proves alias-based worker reuse refreshes callback metadata before the
  next run, so reusable workers return results to the current originating conversation instead of
  a stale or missing callback target.
- Web client coverage proves consecutive GlassHive MCP calls collapse into one visible worker row and
  progress labels truncate cleanly instead of overflowing or creating unreadable line breaks.
- Web client coverage proves routine `worker_delegate_once` rows are hidden from normal chat
  rendering; users should see the short human acknowledgement and final result, not internal
  GlassHive plumbing.
- Config/runtime QA must verify host-worker conversations produce user-friendly titles based on
  the task or outcome, not URL accessibility failures or worker/runtime terminology.
- MCP schema coverage proves worker tools advertise host-native execution mode, the Codex/Claude
  profile choices, and desktop action enums.
- Visual QA must include a callback message with multiline text plus a long unbroken token/URL-like
  string and verify that the web chat remains readable after reload.

## 2026-04-30 Follow-Up: Live Host Browser Same-Chat QA

A live local QA pass used a synthetic localhost page and the local QA account. The user prompt did
not mention GlassHive, Codex, Computer Use, or local machine:

```text
Open http://127.0.0.1:<port>/qa in a new Chrome tab and tell me the page title here. Keep it short.
```

Observed and fixed gaps:

- Non-terminal callbacks (`worker.ready`, `run.queued`, `run.started`) were delivered successfully
  but no longer created or updated visible chat messages.
- LibreChat can create a blank assistant anchor before the user message timestamp. Callback updates
  now override immutable timestamps when repairing that anchor, so persisted messages sort as user
  request first, worker result second.
- The main-agent-to-GlassHive instruction must preserve response-format constraints. Runtime and
  MCP instructions now explicitly require short/exact-answer constraints to be passed to the worker.
- Callback redaction now preserves Markdown delimiters when redacting local URLs and local artifact
  paths, avoiding broken-looking link text.

Verified live behavior:

- The main agent selected the GlassHive host worker path from a normal real-browser task request.
- The generated worker instruction preserved "only the page title" and "keep it short".
- Routine `worker_delegate_once` tool results stay compact by default; run, project, worker, alias,
  and execution-mode details are only returned when diagnostics are explicitly requested.
- The host worker opened the synthetic page in the real Chrome session and left the Chrome tab on
  the requested page.
- The same chat received exactly the synthetic page title as the final assistant callback.
- Mongo message ordering was correct: user message first, terminal GlassHive callback second.
- The callback message content was a normal text array and contained only the concise title.
- GlassHive callback outbox showed lifecycle callbacks delivered as internal 2xx acknowledgements
  and the terminal completion delivered once.
- The conversation contained no extra visible background insight messages.

Release prerequisite:

- Before claiming this flow is shipped in a live install, run the documented live-vs-source agent
  compare and sync the source-of-truth agent/MCP prompt changes intentionally. The new
  `worker_delegate_once` tool entry and GlassHive prompt rules must be present in the live agent
  bundle, not only in tracked YAML.

Regression coverage added or re-run:

- LibreChat callback receiver tests cover silent non-terminal callbacks, terminal callback
  persistence, blank-anchor timestamp repair, Markdown-safe redaction, replay, stale HMAC, and
  conversation ownership rejection.
- LibreChat message model tests cover explicit timestamp override for callback anchor repair.
- GlassHive runtime/API/MCP tests cover host worker delegation, callback context, no default hard
  CLI timeout, and `FINAL REPORT:` callback selection.
- Web client tests cover malformed callback content normalization so legacy callback rows cannot
  crash rendering with array-method errors.
- Telegram and Voice tests cover long GlassHive callback polling and same-surface completion
  delivery after a newer user turn.

## 2026-05-06 Follow-Up: Durable Telegram GlassHive Callback Delivery

Telegram QA for a long-running GlassHive research task exposed a restart-safe delivery gap. The
worker completed and LibreChat accepted the signed callback, but Telegram did not send the result
until the user manually asked for status much later.

Public-safe root cause:

- Telegram same-surface delivery depended on an in-memory per-turn poller. The poller expired before
  the worker's terminal callback arrived.
- LibreChat had persisted the `glasshive_worker_callback`, but there was no DB-backed Telegram
  delivery ledger or dispatcher to claim and send late callbacks after the poller ended.
- Long worker output was selected after a fixed CLI-output truncation point, so a `FINAL REPORT:`
  block could be lost before callback extraction. That would have reduced a long research result to
  a short tail even if delivery succeeded.
- Local Telegram HTTP logs could expose bot-token URLs; logs must redact those before they leave the
  process.

Fixes:

- LibreChat now writes a `ViventiumGlassHiveCallbackDelivery` row when a visible Telegram or live
  voice GlassHive callback is accepted. The row has stable delivery ids, claim leases, retry/backoff,
  sent/failed/suppressed states, full-text payload support, and backlog observability.
- Telegram keeps the in-turn poller as a fast path, but both the fast path and the background
  dispatcher claim the same delivery row before sending. That prevents duplicate delivery while
  allowing late callback delivery after timeout or bot restart.
- Voice claims the same ledger for live-call callback speech. If the call is no longer active, the
  persisted callback and delivery state remain observable rather than disappearing into an expired
  in-memory task.
- GlassHive completion callback extraction preserves the selected `FINAL REPORT:` content before
  truncating retained CLI output. Visible web text remains bounded; sanitized full text can be
  delivered through the surface ledger.
- Telegram Bot API token-bearing URLs are redacted in bot logs.
- Coder was reviewed only for control-plane patterns. The adopted pattern is explicit queue/claim
  state and auditability; no Coder description routing, workspace preset naming, AGPL code/schema,
  or macOS-host firewall promise was copied.
- ClaudeViv review identified two production blockers during this pass: a duplicate-delivery race
  while the delivery row was becoming claimable, and handler-bypassing token redaction. The poller
  now waits for the ledger for callback-id-bearing terminal results, and token redaction is attached
  to the configured log handlers.
- A follow-up review also found that a short claim lease could allow a second dispatcher to reclaim
  a long Telegram delivery while the first dispatcher was still chunk-sending it. Delivery claims now
  use a 10-minute lease by default, and stale claim status updates return/log a conflict instead of
  being treated as silent success.
- Delivery failure/suppression reasons are redacted before Mongo persistence, so token-bearing Bot
  API URLs do not land in the durable callback ledger.
- Telegram fast-path terminal callback handling now includes `artifact.created`, matching the
  LibreChat callback receiver's user-visible event set. Delivery status transitions log
  sent/failed/suppressed state changes for operator observability.

Regression coverage added or re-run:

- LibreChat callback route tests cover enqueueing a durable delivery row and preserving sanitized
  full-text callback metadata.
- LibreChat delivery service tests cover claim-by-surface without prompt matching, 10-minute default
  leases, failure-reason redaction, and prove raw callback `full_message` text is not used as a
  fallback after route sanitization.
- Telegram and voice route tests cover bridge-secret delivery claims, claim-id status updates, and
  lost-claim conflict responses.
- Telegram bridge tests cover fast-path durable claim before sending and late dispatcher delivery
  without stream state. They also cover the race where a callback message is visible before its
  delivery row is claimable; the in-turn poller waits for the ledger instead of legacy-sending, and
  `artifact.created` is treated as a terminal callback for the fast path.
- Voice route and gateway tests cover scoped delivery claim plus full-text speech from the claimed
  callback row, including capping long reports before TTS while leaving the full text in chat.
- GlassHive runtime tests cover long `FINAL REPORT:` preservation and terminal callback full-text
  selection before visible preview truncation.

## 2026-04-29 Key-Principles Check

Checked against `docs/requirements_and_learnings/01_Key_Principles.md` before local commit:

- Study before acting: traced the failing path across background activation, GlassHive runtime,
  callback persistence, web rendering/polling, Telegram, Voice, compiler, and docs before final
  edits.
- Separation of concerns: direct execution remains in GlassHive, conversation persistence remains in
  LibreChat/Viventium, same-surface delivery remains in Web/Telegram/Voice adapters, and background
  agents remain evidence producers.
- No hardcoded runtime NLU: activation fixes live in source-of-truth activation policy and prompt
  contracts. Runtime changes use structured metadata, callback ids, message ids, env/config fields,
  and content shapes.
- Canonical config: `runtime.glasshive_followup_timeout_s` is the single timeout source and now
  compiles to Web, Telegram, and Voice env surfaces.
- Public/private boundary: QA evidence uses synthetic conversations and public-safe summaries only;
  raw logs, screenshots, credentials, local paths, and private runtime artifacts are excluded.
- Documentation first: existing owning docs were extended instead of creating duplicate feature
  docs.
- Verification: automated coverage includes LibreChat API/client, GlassHive runtime/API/MCP,
  parent compiler/preflight/source-of-truth, Telegram, Voice, and Browser Use QA.

## Evidence Rules

- Use synthetic task data only.
- Do not paste raw CLI logs into this repo.
- Replace local filesystem paths with placeholders such as `<workspace-root>` or `~/viventium`.
- Do not include credentials, API keys, browser cookies, personal emails, hostnames, or screenshots
  that reveal private state.
