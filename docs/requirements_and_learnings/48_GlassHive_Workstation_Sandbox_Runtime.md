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
  outcome-focused acknowledgement in its own voice and stop the turn. The runtime must not force a
  literal canned status string. The agent should not immediately poll `worker_live`/`run_get` unless
  the user asked for diagnostics or live status; the callback channel owns completion and blockers.
- `worker_delegate_once` must not return project, worker, run, alias, or execution plumbing to the
  model by default. Those fields are available only through an explicit diagnostics flag or the
  lower-level status tools, so routine chat turns cannot accidentally leak internal IDs.
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
- `--shm-size 2g` (configurable via `WPR_SANDBOX_SHM_SIZE`)
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
  - `Open workspace`
  - `Duplicate workspace`
  - `New workspace`
- `Duplicate workspace` is allowed in the default v1 action set only with safe semantics:
  - copy workspace files/context
  - do not clone browser-session state by default
- Parent systems should auto-reuse the correct workspace when they already know the stable alias
  for the relevant service or job
- `Open workspace` should automatically resume paused workspaces
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
- **Canonical operator URL**: user-facing watch, steer, and takeover requests must surface the
  configured GlassHive operator `/watch/{worker}` URL. Raw noVNC desktop URLs are diagnostic-only
  implementation details and must not be the primary chat-visible view.
- **Completed deliverable promotion**: for Docker workers with structured webpage deliverables,
  GlassHive must open the deliverable in the sandbox browser once the run completes. Host-native
  workers must not auto-open the user's real browser without explicit consent and must not place
  `file://` host paths in callback payloads; host deliverables may expose a safe relative
  `workspace_path` plus `browser_url_available=false` instead.
- **Steer redirect semantics**: the glossy watch footer `Steer + send` path must interrupt the active run, kill the exact live run session/process tree, auto-start the replacement steer run, and keep that replacement run in execution mode until the redirected action is actually performed or a blocker is raised
- **Queue follow-up gestures**: the same footer must also support non-interrupting queued follow-ups through long-press `Send` and `Cmd/Ctrl+Enter` or modifier-click send; those gestures route through `worker_message`, preserve the current active run, and visibly explain the queue behavior in the footer UI
- **Queue follow-up lifecycle**: once a queued follow-up becomes the active run, GlassHive must keep the worker in `running` until that follow-up itself settles; healing/recovery paths must not regress the worker to `ready` while the replacement run is still executing

Operator brief is derived from the project goal and success criteria. Workers treat success criteria
as hard acceptance gates and pause before risky or irreversible external actions.

---

## Deployment Considerations

### Current Model (Local)

Docker containers on the operator's machine, managed by `viventium-librechat-start.sh`. Single-
operator use. Ports on loopback.

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
| `WPR_SANDBOX_IMAGE` | `workers-projects-runtime-workstation:phase1-node22` | Docker image |
| `WPR_SANDBOX_SHM_SIZE` | `2g` | Shared memory per container |
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
