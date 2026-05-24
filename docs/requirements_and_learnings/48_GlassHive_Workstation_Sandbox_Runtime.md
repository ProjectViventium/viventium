# GlassHive: Workstation and Host-Native Worker Runtime

**Purpose**: GlassHive is a first-party, standalone worker runtime that gives AI workers persistent,
resumable execution environments with browser, terminal, filesystem, and operator visibility. It
supports Docker workstation sandboxes and host-native workers. It is composable with
Viventium/LibreChat but architecturally independent.

**Repo**: `ProjectViventium/GlassHive` (first-party, no upstream fork boundary)
**License**: FSL 1.1 with Apache-2.0 future license
**Path**: `viventium_v0_4/GlassHive/` (gitignored from the public repo; separate git history)

---

## Core Concepts

| Term | Meaning |
|---|---|
| **Sandbox** | A Docker-backed workstation container with desktop, browser, terminal, and filesystem |
| **Host Worker** | A no-sandbox worker that runs local CLIs directly on the user's main computer |
| **Worker** | The AI runtime operating inside a sandbox or on the host (profiles: `codex-cli`, `claude-code`, `openclaw-general`) |
| **Project** | An operator-defined mission with goal, success criteria, and continuity wrapper |
| **Bootstrap Bundle** | A portable preset containing auth, MCP config, instructions, env, and files that seeds a worker |

---

## Architecture

### Four Layers

1. **Control Plane** -- FastAPI API (port 8766), SQLite persistence, project-first operator web UI
2. **Worker Runtime** -- Profile-agnostic runtime supporting multiple worker types
3. **Execution Substrate** -- Docker workstation containers or host-native process execution
4. **Client Adapters** -- HTTP API, MCP (streamable-http, stdio, sse), direct API calls

### Execution Modes

| Mode | Behavior |
|---|---|
| `docker` | Existing Docker workstation sandbox with noVNC, persistent home, and isolated browser profile |
| `host` | No-sandbox host-native process execution using local `codex`, `claude`, or `openclaw` CLIs |

Host-native workers are intentionally powerful. They act on the user's main computer and inherit the
local OS, filesystem, browser, and CLI auth posture. The selected mode is a structured runtime
decision, not a free-text runtime heuristic: `execution_mode=host` means the real computer/session,
and `execution_mode=docker` means isolated workstation. Deployments may configure either mode as the
MCP default; when the user request depends on the real browser profile, desktop apps, local files,
installed CLIs, or OS/window control, GlassHive-facing prompts and schemas should steer the main
agent to host mode unless the user explicitly asks for an isolated sandbox or the host-worker gate is
disabled.

### Host-Native Discoverability Contract

- Users should not need to say "GlassHive", "Codex", "computer use", or "on this local machine" for
  every real-computer task. Viventium's main agent prompt and the GlassHive MCP tool descriptions
  should advertise concrete capabilities such as signed-in browser sessions, desktop apps, local
  files/projects, installed CLIs, OS/window control, long-running work, and callbacks.
- Runtime code must not infer intent from prompt text, provider names, or tool-substring matching.
  The main agent chooses structured tool arguments (`execution_mode`, `profile`, `workspace_root`,
  `alias`, callback metadata) from source-of-truth prompts, MCP schemas, and config.
- If host vs sandbox is genuinely ambiguous and both are available, the user-facing question should
  be short and outcome-oriented: ask whether to use the real computer/session or an isolated
  sandbox. If the task clearly requires an existing login/session or local file/app, default to host.
- Prefer `codex-cli` for available host browser, desktop, file, and code execution. Use
  `claude-code` when the user asks for Claude or when configured as the preferred local CLI. Use
  `openclaw-general` only when installed/configured or explicitly requested.
- Fresh one-off host/browser/desktop/local tasks should go through a high-level MCP delegation
  surface such as `worker_delegate_once`. The main agent should not have to manually list projects,
  create or resume workers, and queue runs for routine tasks; low-level tools remain available for
  explicit status, resume, steering, diagnostics, and multi-worker orchestration.
- When `worker_delegate_once` reports callback readiness, the main agent should write one short
  outcome-focused acknowledgement in its own voice, include the returned View / Steer link when the
  surface supports web links, and stop the turn. The runtime must not force a literal canned status
  string. The agent should not immediately poll `worker_live`/`run_get` unless the user asked for
  diagnostics or live status; the callback channel owns completion and blockers.
- `worker_delegate_once` must return model-visible `follow_up_context` containing the created
  project, worker, and run identifiers plus the status/takeover tool hints needed for a later
  follow-up question. Those identifiers are context for tool calls, not routine user-facing text:
  the assistant must not print raw IDs unless diagnostics were requested. User-facing turns should
  surface the View / Steer URL instead of standalone project/worker/run plumbing.
- CLI worker prompts, including Docker and host-native CLI workers, must require a final
  user-facing completion block, headed `FINAL REPORT:`, so callback delivery can surface results
  instead of progress chatter or stale resumed-session summaries.
- CLI output parsing must treat intermediate assistant messages as progress. For Codex/Claude-style
  workers, GlassHive should publish the explicit `FINAL REPORT:` section when present, otherwise the
  latest assistant result, not a concatenation of every progress message.

### Why Selenium's Docker Image (Not Selenium Grid)

GlassHive uses **`selenium/standalone-chromium:latest`** as the **Docker base image** for worker
containers. This is not Selenium Grid (the multi-node browser-test orchestrator). The image is used
because it bundles:

- Chromium browser
- Xvfb virtual display server
- VNC server and noVNC web viewer
- Proper shared-memory and signal handling

Building this from scratch would be significant work for no benefit. The Selenium standalone image
is well-maintained, regularly updated, and gives a working graphical desktop environment inside
Docker without custom display-server plumbing.

**What GlassHive actually uses from Selenium**:

- The **Docker image** as a base layer (packaging convenience)
- The **Selenium Python client** (`pip3 install selenium`) for WebDriver-based browser control
- **Port 4444** (standard WebDriver port) exposed per container for remote browser automation

**What GlassHive does NOT use**:

- Selenium Grid hub/node topology
- Multi-browser distribution or parallel test orchestration
- Any Selenium test framework features

The actual desktop interaction is primarily through direct Chromium launch and desktop automation
tools (xdotool, wmctrl, xterm).

---

## Docker Infrastructure

### Generated Dockerfile

The Dockerfile is dynamically generated at runtime by `docker_sandbox.py`. Key layers on top of the
Selenium base:

- **System**: bash, curl, git, jq, ripgrep, screen, tmux, vim, wmctrl, xdotool, xterm, pcmanfm
- **Node.js 22.x** via nodesource
- **npm globals**: `@openai/codex`, `@anthropic-ai/claude-code`, `openclaw@latest`
- **Python**: selenium library
- **Image tag**: `workers-projects-runtime-workstation:phase1-node22`

### Container Configuration

| Port | Purpose |
|---|---|
| 7900/tcp | noVNC desktop viewer (web-based VNC) |
| 4444/tcp | Selenium WebDriver endpoint |
| 18789/tcp | OpenClaw runtime |

- All ports bound to **loopback only** (127.0.0.1) by default
- Docker resource caps are applied by default: memory `3g`, swap `3g`, CPUs `2`, pids `4096`,
  and shared memory `1g`. Operators can tune these with `WPR_SANDBOX_MEMORY`,
  `WPR_SANDBOX_MEMORY_SWAP`, `WPR_SANDBOX_CPUS`, `WPR_SANDBOX_PIDS_LIMIT`, and
  `WPR_SANDBOX_SHM_SIZE`.
- `--init` for proper signal handling
- User: `seluser`, display: `:99.0`

### Volume Mounts

```
{workspace_dir} -> /workspace/project    # project files
{home_dir}      -> /workspace/.wpr-home  # persistent user home
```

---

## Worker Lifecycle

### State Machine

```
created -> starting -> ready -> running
                                  |
                               paused <-> active
                                  |
                          failed / terminated / completed
```

Workers can be **paused** (freeze sandbox, preserve filesystem and processes), **resumed** (restart
from paused state), **interrupted** (signal to stop current task), or **terminated** (remove
container and data).

### Worker Profiles

| Profile | Runtime |
|---|---|
| `codex-cli` | OpenAI Codex CLI |
| `claude-code` | Claude Code desktop |
| `openclaw-general` | OpenClaw CLI |

### Host-Native Worker Contract

Host-native workers use the same project/worker/run control plane and MCP tools as Docker workers,
but run directly on the host machine.

Host-worker UX and callback requirements:

- Chat-facing status should focus on the real task outcome. Worker IDs, run IDs, project IDs,
  terminal URLs, ports, and `queued/running` plumbing are diagnostic details and should only be
  shown when the user asks for them.
- Immediate dispatch messages should be plain, short, and composed by the assistant in its own
  voice. The tool may return acknowledgement guidance, but not a literal phrase that the assistant
  must quote. Do not expose internal provider/tool/runtime labels such as Codex, worker, run, host
  mode, queue, or terminal unless the user asks for diagnostics.
- Delegation results should include a sanitized `delegation_audit` preview so the assistant can
  self-check the target, success condition, and response constraints it sent to the worker. The full
  submitted instruction is diagnostics-only and should appear only when diagnostics were explicitly
  requested.
- Worker execution must be non-blocking for the main assistant turn. The main agent may dispatch or
  steer a worker and then stop the chat turn; completion, blockers, approvals, and takeover requests
  return through signed callbacks or same-surface polling.
- The dispatch acknowledgement should not include rich `worker_live` output. Live state and logs are
  for explicit status/diagnostic requests, not routine one-off delegation.
- Host-native execution must obey the compiled runtime gate. If
  `GLASSHIVE_HOST_WORKERS_ENABLED=false`, API and MCP paths must reject host worker creation,
  find-or-resume, resume, run, steer, and desktop actions instead of treating the flag as advisory.
- The callback path is a durable communication line between GlassHive and the originating Viventium
  conversation. It must be signed, replay-protected, anchored to the assistant response message,
  persisted in a local callback outbox until delivered, persisted in the conversation store after
  receiver acceptance, and projected into a durable surface-delivery ledger for non-web surfaces
  such as Telegram and live voice.
- Surface delivery state must be DB-backed and idempotent. Telegram and voice can still poll during
  the original turn for low latency, but terminal/actionable callbacks must survive the poll window,
  bot/gateway restart, and LibreChat process restart. Delivery rows need claim leases, retry/backoff,
  sent/failed/suppressed states, and backlog observability.
- This communication line must work after the original chat request has ended, after UI refresh,
  and across long-running or parallel workers. The user should not have to ask "what happened?" for
  GlassHive to return the result.
- Worker callbacks provide verified execution evidence. They must stay structured and sanitized so
  the main agent/follow-up layer can decide whether to surface the information, summarize it, or
  remain silent with `{NTA}` when the information is redundant or irrelevant.
- Callback/result surfacing should follow the same high-level pattern as Scheduling Cortex
  follow-ups: backend services inject bounded verified context into the conversation path, and the
  main agent/user-visible layer owns whether the content is useful to show or should be suppressed
  as `{NTA}`/irrelevant. Do not create a second conversation-specific reporting path.
- Worker lifecycle and queue events remain internal lifecycle/audit events and are not posted into
  the user conversation. The main assistant turn owns any immediate "working on it" status. The
  GlassHive callback receiver surfaces only terminal/actionable events: completion, failure,
  approval/checkpoint, artifact, takeover/help-needed, and cancellation states.
- Completion callbacks should carry the concise final result. Failure callbacks should say what got
  stuck and what help is needed. Approval callbacks should state the specific decision required.
- Completion callback text is selected from the worker's `FINAL REPORT:` block when present, or from
  the useful tail of the run output when older workers omit that marker. Receiver-side callback
  rendering preserves paragraphs, redacts common local/private path forms, and uses the same visible
  length budget as the GlassHive terminal callback selector so the selected result is not truncated
  again.
- Long completion reports may have a short visible web preview plus a sanitized full-text delivery
  payload for Telegram/voice or document-style follow-up. Raw callback payloads, raw logs, local
  absolute paths, screenshots, and secret-bearing command output must not be copied into the public
  callback message or delivery ledger.
- Completion selection must happen before truncating stored CLI output. Long progress streams should
  never push the final assistant result out of the retained text window.
- Host CLI output retention may cap the already-selected/redacted user-facing output for storage,
  but that cap must keep the selected result, not arbitrary progress chatter. If selector behavior
  changes, rerun long `FINAL REPORT:` callback QA before shipping.
- Repeated visible callbacks for one worker run update a single task-status message instead of
  creating a chain of callback branches.
- Visible callbacks must include the assistant response `message_id` for the originating turn.
  Unanchored visible callbacks are ignored/retried rather than being attached to the user message
  as a sibling assistant branch.
- Visible callbacks must not update a blank assistant anchor while preserving a timestamp that
  predates the user request. If the web stack creates a blank assistant anchor before the user row
  is timestamped, callback persistence must repair the callback message timestamp so chronological
  and tree views both show the user request before the worker result.
- Worker delegation must preserve the user's stated success condition and response-format
  constraints. If the user asks for a short/exact result or asks to leave the local computer in a
  specific visible state, that requirement must be passed into the worker instruction and into the
  final callback; screenshots, run logs, IDs, local artifact paths, and extra evidence stay out of
  the user-visible result unless requested or required to explain a blocker.
- Conversation titles for host-worker tasks should summarize the user-visible task or outcome.
  Title generation must not reinterpret local/private URLs as failed browsing targets or expose
  internal worker mechanics.
- Message rendering must tolerate callback/status content stored as an array, single object, string,
  `null`, or legacy malformed tool-call shape. Renderers must normalize before iterating so a bad
  persisted callback cannot crash the chat with array-method errors.
- Callback URL and HMAC secret are resolved from the canonical runtime environment. The GlassHive
  MCP/API processes should inherit those values from the launcher; they also load the generated
  Viventium runtime env as defense-in-depth when started without the expected process env.
  Preflight must fail closed when host workers are enabled without a callback secret source,
  because unsigned or unverifiable callbacks would recreate the "worker finished but user never
  heard back" failure mode.
- CLI stop reasons are scoped to the active run so a timeout or termination marker from one run
  cannot cancel a later successful run. If a worker reports termination after stdout/exit artifacts
  were written, the service must attempt `collect_completed_run(worker, run_id)` before marking the
  run cancelled.
- CLI worker runs are long-running background work by default. Host and Docker workers must not
  inherit a short synchronous request timeout or a hard-coded 300 second worker timeout. Deployments
  may set an explicit run timeout through runtime env for operational policy, but the default worker
  behavior is to keep running until completion, cancellation, checkpoint, or process failure.

- `worker_create` and `worker_find_or_resume` accept `execution_mode=host`.
- `codex-cli` uses local Codex CLI full-access/no-approval execution.
- `claude-code` uses local Claude Code bypass-permission execution.
- `openclaw-general` requires `openclaw` on `PATH`; if missing, the capability must degrade with a
  clear operator-readable message.
- v1 permits only one active host worker per CLI family unless explicit per-worker CLI auth
  isolation is later proven.
- Host process lifecycle uses a per-run process group with terminate/kill cleanup.
- Parent-visible logs are redacted; raw per-run logs are local files with restrictive permissions.
- Host child processes receive a minimal runtime environment. Provider keys, callback secrets,
  LibreChat secrets, and broad parent process env are not inherited by default.

### Host Workspace Layout

The host workspace root is compiled from canonical config:

```yaml
integrations:
  glasshive:
    host_worker:
      enabled: true
      default_execution_mode: host
      workspace_root: ~/viventium
```

Each host worker initializes:

```text
<workspace_root>/<agent-type>/<YYYY-MM-DD>-<slug>/
  project-definition.md
  work-log.md
  harness-prompt.md
  agents.md / AGENTS.md
  claude.md / CLAUDE.md
  codex.md / CODEX.md
```

`/viventium` at filesystem root is allowed only when doctor/preflight proves it is user-writable.
The default must stay user-scoped.

### Host Harness Prompt

Docker prompts must keep sandbox wording. Host-native prompts must say explicitly that the worker is
running on the real host computer and that destructive host changes require a checkpoint when the
confirmation policy is enabled.

The harness prompt is materialized as `harness-prompt.md` for operator visibility.

---

## Browser Session Persistence

- Browser profile data lives in the worker home directory and **persists across pause/resume**
- Same named worker = same browser identity (cookies, sessions, login state)
- Parent systems should use **stable worker aliases** for browser-authenticated work
  (e.g. `demo-browser-primary`, `demo-mail-browser`)
- Chromium launched with: `--no-sandbox`, `--disable-dev-shm-usage`, `--start-maximized`

## User-Facing Workspace Model

- In user-facing GlassHive and Viventium surfaces, the reusable persistent environment should be
  called a **Workspace**
- Internal runtime terms remain:
  - `worker` for the AI runtime identity
  - `sandbox` for the isolated workstation container
- Same named workspace = same underlying worker alias = same files, browser profile, and login
  continuity
- Least-resistance v1 action model:
  - `Run Project` from the launcher
  - `Open workspace` from a saved workspace tile or watch header
  - `Duplicate workspace`
  - `Resume workspace` for idle or paused compute
- `Duplicate workspace` is allowed in the default v1 action set only with safe semantics:
  - copy workspace files/context
  - do not clone browser-session state by default
- Parent systems should auto-reuse the correct workspace when they already know the stable alias
  for the relevant service or job
- `Open workspace` should automatically resume paused workspaces
- The launcher should call the environment selector `Workspace Type`, default to
  `Sandboxed Workspace`, and only expose `Your Computer` when host-native workers are actually
  available in that deployment.
- if workspace rename is added later, it should update the display label, not silently rewrite the
  stable routing alias used by the parent

### Practical Product Promise

- reopen the same workspace and you return to the same environment
- duplicate a workspace when you want a branch that starts from the same files/context
- create a new workspace when you want a clean start
- do not promise that every website will keep the login forever; site-side expiry and MFA can still
  happen

---

## Bootstrap and Auth Projection

### Projection Modes

| Mode | Behavior |
|---|---|
| `clean-room` | No host login state |
| `host-login` | Minimal local Codex/Claude auth projection |
| `codex-host` | Codex-specific auth |
| `claude-host` | Claude-specific auth |
| `full-local` | Complete host home projection (not recommended) |

### Materialization

- `env` -> `~/.glasshive/runtime.env` (sourced in .bashrc)
- `claude_project_mcp` -> workspace `.mcp.json`
- `claude_settings_local` -> workspace `.claude/settings.local.json`
- `claude_md` / `agents_md` -> workspace `CLAUDE.md` / `AGENTS.md`
- `files` -> workspace or home by scope
- `codex_config_append` -> `~/.codex/config.toml`

### Critical Boundary

GlassHive must **NOT** directly depend on or read LibreChat/parent internals (Mongo schemas, token
storage, config formats). The `bootstrap_bundle` is the only crossing point between parent and
sandbox.

Host file materialization is allowlisted. `bootstrap_bundle.files[*].source_path` is copied only
when it is an absolute path under `WPR_BOOTSTRAP_SOURCE_ROOTS`, does not traverse through symlinks,
and stays below the configured size cap. Request-derived upload metadata must not become arbitrary
host file reads.

LibreChat local uploads use the existing upload path: request headers carry the same `files`,
`attachments`, `tool_resources`, and `file_ids` context that MCP already receives. When a file has
a virtual `/uploads/...` path and `WPR_LIBRECHAT_UPLOADS_ROOT` is configured, GlassHive maps it to
the local uploads root and then still applies the trusted-source allowlist before copying it into
the worker workspace. If only extracted text is present, GlassHive materializes that text; if only
metadata is available, it writes an attachment metadata manifest under `uploads/`.

If the GlassHive MCP server config is DB-sourced, request-context placeholders are resolved only
when the reviewed Viventium-managed server config carries `viventiumRequestContext: true`.
Arbitrary DB-sourced MCP servers must not receive user/body placeholder expansion, env secrets, or
OpenID tokens through this path.

Callbacks are signed per worker/run. The parent callback receiver derives a per-run HMAC key from
the compiled callback secret plus `worker_id` and `run_id`, rejects stale timestamps and duplicate
callback ids after successful persistence, verifies conversation ownership, and then writes the
follow-up message into the originating conversation. GlassHive first writes each callback to a local
SQLite outbox, dispatches the first delivery attempt off the user-facing request thread, retries
delivery with the same callback id, treats duplicate `409` responses as delivered, and replays
pending callbacks on service restart so a temporary parent outage does not silently drop the
result. A periodic retry loop must also replay pending callbacks without requiring a GlassHive
restart. Replay refreshes `callback_ts` and re-signs the payload while preserving `callback_id`.
First-attempt delivery and outbox replay must run in the background and must not block worker
create/run APIs or GlassHive service startup if the callback receiver is slow or unavailable. The
retry attempt count, base backoff, and periodic replay interval are runtime-configurable.

Callback signing uses the canonical JSON body encoded as literal UTF-8. GlassHive must not sign an
ASCII-escaped JSON variant while the parent receiver verifies a literal-Unicode stable JSON body,
because normal task text containing punctuation or non-ASCII characters would otherwise fail HMAC
verification with `401 Unauthorized`.

Callback persistence must be branch-safe in LibreChat's message tree. GlassHive callback payloads
carry both the original parent context and the assistant response `message_id` for the turn that
started the worker. The callback receiver requires the assistant response id as the tree anchor for
visible callbacks. If that anchor is still the active leaf and is a blank assistant placeholder, the
receiver may update it. If an existing GlassHive status message for the same run is the active leaf,
later visible callbacks for that run update the same status message. If the conversation has moved
on, the callback must append under the current conversation leaf and keep the original request parent
and anchor in metadata. Distinct later worker runs append linearly rather than overwriting an earlier
run result. If the current moved-on leaf is a user message, the receiver returns retryable `425` so
GlassHive can deliver after the assistant reply is persisted. Metadata must distinguish
`parentMessageId` (original semantic request parent), `treeParentMessageId` (actual persisted chat
parent), and `anchorMessageId` (assistant response anchor). This prevents worker callbacks from
rendering as sibling branches under older messages while preserving the original execution lineage.

Voice and Telegram must surface the same persisted callback message after the main stream ends.
They should poll the callback state by assistant message id and conversation id, just as they poll
persisted follow-ups, so a worker completion or blocker reaches the same call/chat without a user
having to manually ask for status.
Same-surface GlassHive polling must be armed by structured GlassHive MCP/tool evidence from the
turn, not by the presence of any generic tool call. Ordinary non-GlassHive tool turns should keep
their normal cortex follow-up window and must not inherit the long GlassHive callback wait window.

Host-native browser and desktop runs can take longer than ordinary background insight follow-ups.
The same-surface callback wait is therefore owned by `runtime.glasshive_followup_timeout_s`, compiled
to Web, Telegram, and Voice GlassHive timeout env vars, and defaults to 600 seconds. This timeout
must not silently inherit the shorter background-follow-up grace window.

---

## MCP Integration

- **Framework**: FastMCP
- **Transport**: Streamable-HTTP primary, stdio for local, sse for compatibility
- **Server name**: `glass-hive`
- **Ports**: MCP on 8767, control plane API on 8766

### Exposed MCP Tools

- **High-level launch**: `workspace_launch` for normal user-facing delegation with `description`,
  required `success_criteria`, and optional `context`; `worker_delegate_once` for lower-level
  one-call delegation when the caller already has a precise title/instruction.
- **Project**: `projects_list`, `project_create`, `project_get`, `project_runs`, `project_events`
- **Worker**: `workers_list`, `worker_create`, `worker_get`, `worker_live`
- **Worker reuse**: `worker_find_or_resume` for stable aliases
- **Execution**: `worker_run` (queue instruction), `worker_message` (send operator message)
- **Lifecycle**: `worker_pause`, `worker_resume`, `worker_interrupt`, `worker_terminate`
- **Observation**: `worker_desktop_action`, `worker_takeover`, `run_get`
- **Metrics**: `metrics_summary`

`worker_live` includes host worker visibility fields when applicable:

- `work_log_tail`
- `action_audit_tail`
- `prompt_paths`
- `runtime_details.execution_mode`

Parent-visible log and console tails must be redacted before returning through `worker_live`.
Image payloads, data URLs, long base64 blobs, secrets, and credential-looking values stay in local
raw logs only and must not be surfaced into chat, QA reports, or public docs.

File attachments are projected through the existing LibreChat/Viventium upload path, not a new
GlassHive upload route. The first-party GlassHive MCP configuration passes request `files`,
`attachments`, `tool_resources`, and `file_ids` metadata in request-scoped headers. GlassHive folds
local `filepath`/`source_path` references or extracted text into `bootstrap_bundle.files`, then
materializes them under `uploads/` in the worker workspace.

### Callback Reporting

Callbacks are optional and parent-owned. GlassHive accepts callback metadata in `bootstrap_bundle`
and emits signed lifecycle events to the parent URL:

- `run.started`
- `run.completed`
- `run.failed`
- `checkpoint.ready`
- `artifact.created`
- `takeover.requested`

GlassHive must not read LibreChat Mongo or channel internals. Viventium/LibreChat owns the callback
receiver, visible-event allowlist, same-conversation persistence, and surface fanout. Non-terminal
worker lifecycle events are audit/status data, not chat messages.

### Optional Bearer Auth

Set `WPR_API_TOKEN` env var; authenticated via `Authorization: Bearer {token}` or `X-WPR-Token`.
Unauthenticated paths: `/health`, `/docs`, `/openapi.json`.

---

## Operator UX and Takeover

- **noVNC desktop view**: Live X11 display in the browser; operator sees exactly what the worker sees
- **Desktop interaction**: Mouse and keyboard via VNC
- **Terminal takeover**: WebSocket bridge to `screen` multiplexer sessions
- **Desktop surfaces**: `terminal`, `files` (PCManFM), `browser`, `focus_browser`, `codex`,
  `claude`, `openclaw`
- **Default project launch handoff**: the GlassHive project-first UI now defaults to the desktop watch surface
- **Live terminal inside desktop**: when the desktop-first default is on, GlassHive opens an xterm attached to the active `screen` run session so the operator can watch the real live run without leaving the desktop
- **Idle desktop priming**: fresh worker desktops are primed with a GlassHive-owned placeholder page so operators do not land on the inherited Selenium splash as the default visible surface
- **Launch failure audit trail**: if a project launch fails after worker creation but before the first run is queued, the worker is marked failed and a `worker.launch_failed` event is recorded instead of leaving an orphaned ready worker
- **Orphan active-run cleanup**: startup/admin reconcile marks a `running` run as interrupted when the associated worker process is no longer alive, so stale runtime rows do not appear as current active work
- **User-facing naming**: the glossy/operator UI should present persistent personal environments as `Workspaces` rather than exposing raw worker IDs or `sandbox` terminology in the primary flow
- **Workspace hive view**: the `Workspaces` tab is an operator console for the authenticated user's
  active work. With `Inactive Workspaces` off, retained/completed/idle workspaces must not appear as
  active tiles. With it on, retained workspaces can be reviewed and resumed without being confused
  with currently running compute.
- **Workspace tile density**: wide desktop viewports should use the available width for two readable
  workspace columns before wasting empty panel space. Tile watch previews and status reports are
  user-controlled view options (`Watch`, `Status Report`) so power users can choose live visual
  monitoring, textual latest output, or both.
- **Canonical operator URL**: user-facing watch, steer, and takeover requests must surface the
  configured GlassHive operator `/watch/{worker}` URL. Raw noVNC desktop URLs are diagnostic-only
  implementation details and must not be the primary chat-visible view.
- **Signed operator links**: enterprise Workspaces, watch, project, desktop, and artifact links must
  use short-lived, worker-scoped signed URLs or a trusted proxy user assertion. A full watch link
  that falls back to `GlassHive enterprise UI requires an authenticated user assertion` is a failed
  UX/security integration because the user was given a link that cannot carry its own authorization.
- **Completed deliverable promotion**: for Docker workers with structured webpage deliverables,
  GlassHive must open the deliverable in the sandbox browser once the run completes. Host-native
  workers must not auto-open the user's real browser without explicit consent and must not place
  `file://` host paths in callback payloads; host deliverables may expose a safe relative
  `workspace_path` plus `browser_url_available=false` instead.
- **Completed state copy**: completed work should be labeled `Completed` in the hive/watch UI. It
  may remain resumable for follow-up work, but the UI must not present a completed deliverable as
  an idle failure or require manual play/pause actions before ordinary launch/run behavior.
- **Steer redirect semantics**: the glossy watch footer `Steer + send` path must interrupt the active run, kill the exact live run session/process tree, auto-start the replacement steer run, and keep that replacement run in execution mode until the redirected action is actually performed or a blocker is raised
- **Queue follow-up gestures**: the same footer must also support non-interrupting queued follow-ups through long-press `Send` and `Cmd/Ctrl+Enter` or modifier-click send; those gestures route through `worker_message`, preserve the current active run, and visibly explain the queue behavior in the footer UI
- **Multiline steering**: steer inputs in both the Workspaces hive and full watch view must be
  expanding textareas. `Enter` sends; `Shift+Enter` inserts a newline so detailed steering
  instructions remain readable before submission.
- **Queue follow-up lifecycle**: once a queued follow-up becomes the active run, GlassHive must keep the worker in `running` until that follow-up itself settles; healing/recovery paths must not regress the worker to `ready` while the replacement run is still executing

Operator brief is derived from the project goal and success criteria. Workers treat success criteria
as hard acceptance gates and pause before risky or irreversible external actions.

---

## GlassHive Standard QA

GlassHive Standard QA is the mandatory acceptance procedure for any non-trivial GlassHive change,
enterprise deployment change, MCP wiring change, worker profile change, workspace UX change,
artifact/upload/download change, auth/security change, lifecycle/cost-control change, or release-
readiness claim. When the user says "do the GlassHive Standard QA", this section and
`qa/glasshive_standard_qa/` are the source of truth.

The procedure must run across the three real user entrypoints unless a surface is explicitly marked
`BLOCKED` with the missing prerequisite:

- direct GlassHive UI
- direct GlassHive MCP usage, tested before LibreChat when MCP behavior is involved
- LibreChat config-only MCP integration, with no LibreChat application-code modification

Supporting evidence is required from logs, DB/state, code, docs, generated config, and artifacts,
but it cannot replace real user-path evidence. Every case result must be marked `PASS`, `FAIL`,
`PARTIAL`, or `BLOCKED`.

### Mandatory Cases

1. Web search/current fact: ask a simple current-events question such as who won a named game on a
   specific recent date. The result must distinguish successful-empty from provider unavailable,
   timeout, rate limit, auth/config missing, request rejected, unsupported configuration, or local
   prerequisite unavailable.
2. File upload/download: upload a public-safe PDF or workbook, ask the worker to tastefully redesign
   it into a PowerPoint or HTML file, then download, open, and validate the produced files as a
   user. The worker must use a universal self-check harness through its bootstrap instructions and
   success criteria; do not overfit `AGENTS.md` to these exact QA prompts.
3. Scheduling: create a natural-language scheduled GlassHive task such as "in 20 minutes do X" or
   "on Mondays do X". This must work for raw LibreChat/MCP paths without relying on Scheduling
   Cortex-only behavior.
4. Persistence: create or reuse a named workspace and named worker, mark it favorite when the UI
   supports favorites, manually change files/browser state through the workspace, stop/restart
   GlassHive or the worker, then resume efficiently and prove the saved state is still available.
5. Wildcard: research current user patterns for tools like Codex, Claude, OpenClaw, agentic code
   interpreters, and browser/computer-use workers. Define three quick but representative tests and
   run them through GlassHive without hardcoded prompt or intent rules.
6. Security/access: prove enterprise auth fails closed, user/tenant scoping prevents cross-user
   listing/resume/watch/download/inference, signed links expire or reject tampering, raw local/VM
   internals are hidden from member users, provider secrets are not surfaced, and access logs do not
   retain raw `gh_token`, bearer/service-token values, or opaque artifact signed-link paths.
7. Efficiency/performance: prove idle workspaces automatically release compute while preserving
   workspace data, active/queued/checkpoint work is not killed, quotas are enforced, and spawn/resume
   paths are measured against the documented responsiveness target.
8. Professional UX: preserve the designed GlassHive UI, keep workspace/takeover views space
   efficient, avoid overlapping layers, make constrained screens scroll, present persistent
   environments as `Workspaces`, show the launcher title `Define the project once. Watch the
   worker deliver.`, and keep documented launch fields (`Describe your project`, required
   `Success Criteria`, optional `Context`) instead of drifting to ad hoc fields.
9. Review-only second opinion: after Codex completes its own evidence-backed assessment, run a
   Claude/ClaudeViv review-only pass with sanitized evidence and ask it to classify claims as
   `confirmed`, `partially_confirmed`, `cannot_confirm`, or `contradicted`.

Common variants such as "run GlassHive QA", "run the standard QA suite", or "do the GlassHive
Standard QA" should resolve to this same procedure in agent/operator behavior. Runtime product code
must still avoid prompt-string or keyword heuristics; this is an operator/agent instruction, not a
runtime intent classifier.

### Operating Preferences Captured From Enterprise QA

- Local proof comes before cloud mutation, deployment, push, or public release.
- Cloud work may use only the approved enterprise tenant/resources for the task; unrelated customer
  tenants/resources are off-limits.
- Any cloud target metadata must be backed up locally outside the public repo before mutation.
- Enterprise VM mode uses same-account UX through a locked-down first-party assertion from
  LibreChat/reverse proxy. It must not require users to connect separate accounts in the default
  enterprise path, and it must not break the existing connected-account mode used outside that path.
- Long-running workers and workspaces are non-blocking. Dispatch should return promptly; completion,
  blockers, approvals, artifacts, and takeover requests return through signed callbacks or the
  same-surface status UI.
- Raw GlassHive scheduling must be present in both runtime MCP tools and the LibreChat/config
  source-of-truth allowlists. A chat response that claims a schedule was created without a
  GlassHive scheduler tool result is a failed QA case, not an acceptable natural-language
  acknowledgement.
- Worker prompts and QA harnesses must be general and capability-based. Do not hardcode QA case
  names, exact user prompt text, provider labels, or one owner's environment into runtime behavior.
- Idle/cost controls are product requirements, not operator nice-to-haves. Default enterprise
  configuration must make the cost risk visible and configurable.
- Public QA artifacts must sanitize local paths, personal emails, account ids, subscription ids,
  raw logs, DB exports, screenshots with private content, and secret-bearing commands.
- Enterprise service managers must disable raw uvicorn access logs or prove redaction before logs
  leave the VM. Signed View / Steer links and artifact signed-link paths are credentials until they
  expire, so journald, reverse-proxy logs, Azure diagnostics, and QA reports must never preserve
  them verbatim.

The durable QA owner is [`../../qa/glasshive_standard_qa/README.md`](../../qa/glasshive_standard_qa/README.md).

---

## Deployment Considerations

### Current Model (Local)

Docker containers on the operator's machine, managed by `viventium-librechat-start.sh`. Single-
operator use. Ports on loopback.

### Azure Enterprise VM Mode

`azure_enterprise_vm_docker` is the v1 enterprise deployment mode. It keeps the current Docker
worker substrate and moves the control plane to an Azure VM inside one enterprise resource group.
The security model is **one GlassHive deployment per enterprise tenant**. Multiple enterprise
customers must use separate deployments or a later stronger isolation substrate such as ACI,
per-user VMs, gVisor, or Kata.

Default enterprise auth is `first_party_assertion`:

- LibreChat remains unmodified and connects to GlassHive through MCP config only.
- The default LibreChat MCP config sends `X-Viventium-Tenant-Id`, `X-Viventium-User-Id`, and
  request-context/upload headers; the service token is injected by the trusted reverse proxy unless
  `service_token_delivery=client_header` is explicitly selected.
- GlassHive fails closed when `GLASSHIVE_ENTERPRISE_MODE=true` and `WPR_API_TOKEN` is missing.
- GlassHive derives owner scope from the authenticated request context and ignores caller-supplied
  `owner_id` for project and worker creation in enterprise mode.
- GlassHive pins tenant scope to the configured deployment tenant. A mismatched inbound tenant
  assertion fails closed instead of creating a second logical tenant partition on the same VM.
- Enterprise bootstrap does not copy the VM account's host Codex, Claude, or git identity files into
  workers; cloud workers receive only explicit bootstrap content and allowlisted provider env vars.
- Enterprise model/provider access should use tenant/server-side API key env vars or a broker
  (`OPENAI_*`, `ANTHROPIC_*`, `PORTKEY_*`, Azure Foundry-compatible routes). Per-user connected
  accounts remain supported elsewhere, but they are not the default enterprise VM mode.
- OpenClaw Docker workers in enterprise mode must source both GlassHive's worker `runtime.env` and
  their per-worker `openclaw.env`, declare an explicit local loopback OpenClaw gateway, use
  env-backed SecretRefs with the default env provider, honor configured OpenAI-compatible model
  lists, and point OpenClaw's workspace/repo root at the mounted GlassHive project workspace so
  generated files are artifact-visible.
- Enterprise bootstrap `source_path` file materialization requires a server-signed source token tied
  to the authenticated tenant/user. Model- or caller-supplied absolute paths under a shared upload
  root are rejected unless they came from the trusted LibreChat upload projection path.
- Enterprise callbacks emit opaque, short-lived signed links for artifact download and View / Steer
  access instead of putting raw project/worker ids in user-visible text. The signed-link/member worker UI
  hides VM paths, session keys, container names, and live command diagnostics while preserving the
  useful state, controls, output, workspace file list, live refresh, and takeover/action controls
  for the signed link's lifetime.
- `/health` is the only intentionally unauthenticated cloud route. UI, docs, OpenAPI, takeover,
  artifacts, terminal websocket, metrics, admin, and MCP/control-plane routes require service auth
  plus a user assertion.

Spec-compliant MCP OAuth/OIDC remains an optional mode for clients that accept a separate MCP
consent flow. It must validate audience/resource correctly; do not pass LibreChat's own login token
to GlassHive as if it were a GlassHive-audience token. Until an external token validator is wired,
the GlassHive runtime accepts only `first_party_assertion` for request authorization by default;
the optional MCP OAuth block is a client connection flow, not server-side token validation.

The Azure setup guide, sample config, reverse-proxy expectations, provider env examples, scripts,
and acceptance checklist live in the private enterprise deployment repo under
`glasshive-azure-enterprise-vm/`. Public product docs keep only reusable product requirements and
public-safe QA cases.

Cloud validation rule: do not mutate an enterprise Azure resource before exporting a local backup of
the target metadata outside this public repo and proving the equivalent change locally. Backups must
avoid public secret exposure; cloud commands must pin the approved subscription/tenant explicitly.
Provider env projection has been verified with Azure AI Foundry OpenAI-compatible and
Anthropic-compatible routes, but Portkey remains a configuration-dependent path that requires an
approved key or virtual key in the enterprise deployment overlay.

### Prerequisites

- Docker daemon running and accessible
- Port availability: 7900, 4444, 18789 (per container); 8766, 8767 (service)
- Disk space for sandbox state directories
- 2 GB shared memory per sandbox

### Scaling Options

| Model | Notes |
|---|---|
| **Single server / VM** | Same Docker setup on remote machine; reverse proxy + auth in front of noVNC and API |
| **Container orchestration** (K8s / Swarm) | Each worker = pod/service; PVCs for workspace/home; ingress for per-worker port routing |
| **Cloud container services** (ECS, Cloud Run, ACI) | Per-worker containers with attached persistent volumes; load balancer for port routing |

The main deployment constraint is **state persistence**: browser profiles and workspaces need
durable storage that survives container restarts — already designed into the architecture via
persistent home and workspace mounts.

### Security Posture

- Phase-1 boundary: good for owner-controlled local isolation
- **Not yet** designed for hostile multi-tenant isolation
- Bearer token recommended for any non-loopback exposure
- Secrets must never be logged or returned in API responses
- Enterprise VM mode adds application-level tenant/user scoping, authenticated artifact/download
  routes, and idle compute termination, but sibling Docker containers still share one host daemon.
  Treat v1 as trusted users inside one enterprise tenant, not a boundary for mutually hostile
  tenants.

---

## Installer Integration

- GlassHive is **not part of the minimum public first-run contract** (see doc 39)
- Optional component: `START_GLASSHIVE=true|false`, `--skip-glasshive` flag
- The start script auto-disables GlassHive when the runtime directory is absent
- Seeded built-in agents must not keep dead GlassHive tool IDs when `START_GLASSHIVE=false`
- A missing local GlassHive MCP can surface as a generic error to fresh users if not compiled out

---

## Key Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `WPR_DB_PATH` | `{base}/runtime_phase1.db` | SQLite database |
| `WPR_RUNTIME_BACKEND` | `openclaw` | Worker runtime type |
| `WPR_API_TOKEN` | (none) | Optional bearer auth |
| `GLASSHIVE_ENTERPRISE_MODE` | unset | Enables fail-closed enterprise request scoping |
| `GLASSHIVE_AUTH_MODE` | `local` | `first_party_assertion` for v1 enterprise VM mode; OAuth modes are optional |
| `GLASSHIVE_ENTERPRISE_TENANT_ID` | `local` | Single-tenant deployment identifier used when the request does not carry a tenant header |
| `WPR_SANDBOX_IMAGE` | `workers-projects-runtime-workstation:phase1-node22` | Docker image |
| `WPR_SANDBOX_MEMORY` | `3g` | Docker memory cap per worker container |
| `WPR_SANDBOX_MEMORY_SWAP` | `3g` | Docker memory+swap cap per worker container |
| `WPR_SANDBOX_CPUS` | `2` | Docker CPU cap per worker container |
| `WPR_SANDBOX_PIDS_LIMIT` | `4096` | Docker process cap per worker container |
| `WPR_SANDBOX_SHM_SIZE` | `1g` | Shared memory per container |
| `WPR_DOCKER_IMAGE_BUILD_TIMEOUT_SEC` | `900` | Cold sandbox image build timeout; separate from short Docker inspect/exec timeouts |
| `WPR_MODEL_HOST_CODEX_CLI` | unset | Optional host-native Codex model override when the logged-in local Codex account supports a newer model than the server-side Docker provider deployment |
| `WPR_OPENCLAW_START_GATEWAY` | `false` | Opt-in OpenClaw loopback gateway process; task runs use `openclaw agent --local` directly for lower overhead and to avoid session contention |
| `WPR_SANDBOX_VNC_PASSWORD` | `secret` | VNC access password |
| `WPR_SANDBOX_VNC_NO_PASSWORD` | `1` | Disable VNC password |
| `WPR_MCP_HOST` | `127.0.0.1` | MCP server bind |
| `WPR_MCP_PORT` | `8767` | MCP server port |
| `WPR_MCP_BASE_URL` | `http://127.0.0.1:8766` | Control plane URL |
| `GLASSHIVE_OPERATOR_BASE_URL` | `http://127.0.0.1:8780` | User-facing GlassHive operator UI origin used for `/watch/{worker}` links |
| `GLASSHIVE_DEFAULT_LAUNCH_SURFACE` | `desktop` | Project-first UI default initial watch surface (`desktop`, `terminal`, `auto`) |
| `GLASSHIVE_SHOW_LIVE_TERMINAL_IN_DESKTOP` | `true` | When desktop-first watch is used, auto-open the active live run terminal inside the desktop |
| `WPR_IDLE_DESKTOP_PRIME_BROWSER` | `true` | Prime fresh worker desktops with the GlassHive placeholder browser page instead of the inherited base-image splash |
| `GLASSHIVE_CALLBACK_RETRY_ATTEMPTS` | `3` | Callback delivery attempts before GlassHive records `callback.failed` |
| `GLASSHIVE_CALLBACK_RETRY_BASE_DELAY_S` | `0.5` | Linear callback retry base delay in seconds |
| `GLASSHIVE_CALLBACK_RETRY_INTERVAL_S` | `30` | Periodic pending-callback replay interval in seconds |
| `GLASSHIVE_RUN_TIMEOUT_SEC` / `WPR_RUN_TIMEOUT_SEC` | unset | Optional explicit timeout for long-running CLI worker runs; unset means no default hard cap |
| `GLASSHIVE_HOST_RUN_TIMEOUT_SEC` / `WPR_HOST_RUN_TIMEOUT_SEC` | unset | Optional host-specific override for host-native CLI runs |
| `GLASSHIVE_IDLE_TERMINATE_AFTER_S` | `0` | When positive, stop idle worker compute while preserving workspace/home state |
| `GLASSHIVE_IDLE_REAPER_INTERVAL_S` | `60` | Idle reaper interval |
| `GLASSHIVE_MAX_ACTIVE_WORKERS_PER_USER` | `0` | When positive, cap active workers per authenticated user |
| `GLASSHIVE_MAX_ACTIVE_WORKERS_PER_TENANT` | `0` | When positive, cap active workers across the tenant deployment |
| `GLASSHIVE_MAX_WORKSPACES_PER_USER` | `0` | When positive, cap retained non-terminated workspaces per authenticated user |
| `GLASSHIVE_MAX_WORKSPACES_PER_TENANT` | `0` | When positive, cap retained non-terminated workspaces across the tenant deployment |
| `GLASSHIVE_ALLOWED_WORKER_PROFILES` / `WPR_ALLOWED_WORKER_PROFILES` | unset | Optional comma-separated worker profile allowlist such as `codex-cli,claude-code`; disallowed profiles fail closed and are hidden from the launcher |
| `GLASSHIVE_ARTIFACT_DOWNLOAD_MAX_BYTES` | `104857600` | Owner-scoped artifact download size cap |
| `GLASSHIVE_PROJECT_PROVIDER_ENV` | enterprise: `true` | Project allowlisted provider env vars into workers |
| `GLASSHIVE_WORKER_ENV_ALLOWLIST` | provider defaults | Extra comma-separated worker env keys allowed in enterprise |

---

## Key Source Files

| File | Purpose |
|---|---|
| `runtime_phase1/src/workers_projects_runtime/docker_sandbox.py` | Docker container lifecycle, Dockerfile generation, port mapping, desktop actions |
| `runtime_phase1/src/workers_projects_runtime/bootstrap.py` | Auth projection, env seeding, file materialization |
| `runtime_phase1/src/workers_projects_runtime/api.py` | FastAPI control plane routes |
| `runtime_phase1/src/workers_projects_runtime/mcp_server.py` | MCP tool definitions and client |
| `runtime_phase1/src/workers_projects_runtime/service.py` | Orchestration and state management |
| `runtime_phase1/src/workers_projects_runtime/store.py` | SQLite persistence |
| `runtime_phase1/src/workers_projects_runtime/models.py` | Pydantic data models and state enums |

### Documentation (inside GlassHive repo)

- `docs/01_Vision_Requirements_and_Terminology.md`
- `docs/02_Architecture_and_Components.md`
- `docs/03_Bootstrap_Auth_and_Identity_Projection.md`
- `docs/04_MCP_Publication_and_Client_Compatibility.md`
- `docs/05_QA_Quick_Power_Playbook.md`
- `docs/09_Dynamic_MCP_Projection_and_Bidirectional_Availability.md`
- `docs/10_Browser_Session_Persistence_and_Login_Model.md`

---

## Learnings

- The Selenium standalone-chromium image is infrastructure packaging, not a test framework
  dependency. Do not confuse it with Selenium Grid.
- GlassHive's independence from LibreChat is a hard architectural boundary. The bootstrap bundle
  is the only legal crossing point; do not add direct Mongo reads or LibreChat config imports.
- Browser session persistence depends on stable worker naming. Ephemeral worker IDs break login
  continuity for authenticated browser tasks.
- For non-technical users, the right product label is `Workspace`; internal worker/sandbox terms
  should stay behind the scenes in the primary UX.
- The MCP layer must not duplicate runtime logic; it delegates to the control plane API.
- Phase-1 security posture is local-only. Any network exposure requires auth in front.
- Deliverable detection must ignore GlassHive scaffold/helper files case-insensitively, such as
  `AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `work-log.md`, `project-definition.md`, and
  `glasshive-host-tools/*`; watch/workspace UI should promote the user's actual artifact, not
  framework support files that changed later by mtime.
