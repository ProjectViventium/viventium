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
- GlassHive delegation should stay sparse and faithful. The host assistant passes the user's real
  goal, explicit constraints, files/uploads, MCP/tool capability context, and success conditions; it
  must not turn those capabilities into a made-up plan, rubric, artifact requirement, or provider
  checklist. If MCP/tool data is unavailable or unproven, pass that fact instead of pretending the
  worker already has evidence.
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
- CLI worker prompts, `AGENTS.md`, `CODEX.md`, `CLAUDE.md`, and other bootstrap instructions must
  include a universal completion self-check before that final report. The worker should inspect the
  concrete output it produced, compare it with the user's request and success criteria, fix or
  continue when the output is incomplete, and report only remaining blockers. This is a general
  harness rule, not a prompt-specific list of file types, providers, UI surfaces, or QA phrases.
- `AGENTS.md` is the canonical Codex project-instruction file. Compatibility files such as
  `CLAUDE.md` and `CODEX.md` may still be materialized for non-Codex workers and older clients, but
  they should import or mirror the same concise rules instead of growing separate product truth.
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
- CLI worker metadata must stay aligned with structured profile/execution-mode selection. A
  `codex-cli` worker must not be created or reported as OpenClaw just because the control-plane row
  has not yet been reconciled with the live runtime. Before a run is executed, the service must
  persist runtime/workspace metadata when available so failure/status/artifact paths can report the
  actual worker and generated files.
- A non-zero CLI exit is not proof that the worker produced no useful files. When stdout/stderr
  contains structured provider evidence such as `response.failed` or `turn.failed`, GlassHive must
  classify from that run evidence before falling back to generic runtime-error text. Failed terminal
  status and callbacks should still expose owner-scoped artifact links when workspace files exist
  and should guide retryable work toward `workspace_continue` in the same workspace.
- CLI worker runs are long-running background work by default. Host and Docker workers must not
  inherit a short synchronous request timeout or a hard-coded 300 second worker timeout. Deployments
  may set an explicit run timeout through runtime env for operational policy, but the default worker
  behavior is to keep running until completion, cancellation, checkpoint, or process failure.
- MCP `workspace_wait` is a user-requested completion wait, not the worker runtime limit. Its
  default must be long enough for ordinary research, coding, and file-work completion checks,
  including user requests to wait up to 30 minutes, and must be capped by deployment policy. The
  LibreChat MCP server timeout for GlassHive must exceed the GlassHive wait cap so a legitimate wait
  is not converted into a transport failure. A timed-out wait means "still running/check again", not
  "failed". The model-facing follow-up context must carry the run/worker ids and the configured
  completion-wait timeout so the host model does not lose the task between turns. If the model
  accidentally omits ids in a same-conversation wait/status call, MCP may resolve the most recent
  dispatch only inside the authenticated tenant/user/conversation scope. If a conversation-scoped
  launch was remembered and the follow-up omits the conversation assertion, the tool must fail
  closed instead of using a same-user global fallback. Enterprise launches without a conversation
  assertion must not create a remembered user-wide fallback; explicit `run_id`/`worker_id` follow-up
  still works. Scheduled launches return schedule handles rather than active worker/run dispatches,
  so the recent-dispatch wait/status fallback intentionally does not attach until scheduled work
  starts. Local non-enterprise mode is a best-effort developer convenience and must not be
  treated as enterprise isolation unless user/conversation headers are present. Normal long waits
  must use an efficient configurable polling cadence, not rapid browser or status loops. The runtime
  must enforce the configured poll cadence as a floor so a misbehaving caller cannot overload the
  operator API with sub-second or one-second long-run polling. Browser surfaces must also be
  state-aware: active workers may refresh quickly, but retained/completed workspace tiles must back
  off, avoid embedded desktop iframes by default, and use non-overlapping timers. The Workspaces
  hive may cap embedded live desktop previews for active workers to protect browser resources; every
  tile must still show status text and a Full watch path. When launch and wait happen in the same
  turn, the host model should
  surface the View / Steer link before entering the long wait whenever its chat protocol allows
  assistant text before the next tool call, and must include that link in the final answer.
- GlassHive delegation fidelity is a product requirement. The host model must not shorten,
  summarize, paraphrase, or water down the user's request when delegating to `workspace_launch` or
  `worker_delegate_once`. Titles and descriptions may be concise labels, but the worker-facing
  instruction/context must include the full available user request, success criteria, constraints,
  examples, links, file references, exclusions, and background. The `context` field exists to carry
  that full picture when the outcome description would otherwise be too thin.
- CLI/provider failure handling is part of the standalone MCP contract. When a worker process exits
  non-zero, GlassHive must persist a sanitized failure taxonomy when structured CLI events expose
  one, such as provider rate limit, content filter, provider auth/config, response failure, or
  unknown. `workspace_status` and `workspace_wait` must return the class, retryability, user-facing
  message, diagnostic summary, and recovery hint so the host model does not invent a blocker or
  relaunch from scratch.
- Host-worker capability must be checked before creating or resuming a worker or queuing a run. If a
  requested host profile requires a missing CLI, GlassHive returns a structured
  `runtime_dependency_missing` blocked response and creates no worker/run row. The model may recover
  by using an available profile or sandbox/workstation execution only when that does not contradict
  the user's explicit request.
- Host-worker preflight must cover incompatible versions and missing runtime substrate, not only
  absent binaries. If a local CLI/runtime such as Node, Python, Codex, Claude, browser automation, or
  a helper sidecar is present but too old or misconfigured for the selected profile, GlassHive should
  classify it as a runtime dependency problem, try configured safe recovery first, and preserve the
  same user task. Runtime version requirements and recovery branches must come from profile metadata
  or runtime configuration, not hardcoded prompt or provider-name rules. Safe recovery includes using
  GlassHive-managed/bundled dependencies, a worker-local toolchain, another available profile, or
  sandbox/workstation mode when that does not contradict the user's request. Deployments must declare
  which of those recovery branches are actually available; unavailable branches are skipped rather
  than simulated with ad hoc shell commands. If recovery creates a replacement worker/run, the
  model-visible `follow_up_context` must reference the active recovered run, and blocked preflight
  attempts must not become the conversation's current dispatch. A chat-visible "install or change
  your global machine environment" instruction is allowed only after configured recovery paths are
  unavailable, unsafe, or explicitly rejected.
- Sandbox routing is a structured tool argument, not runtime prompt matching. If the user asks for
  `sandbox`, `sandboxed workspace`, `Codex Workspace`, `workstation`, a disposable browser, or risky
  untrusted browsing, the GlassHive MCP instructions must guide the host model to set
  `execution_mode=docker` even when the deployment default is host. Host-default Viventium behavior
  remains correct for real-browser/profile/local-computer requests.
- `run_get` is a diagnostic/debugging tool. General user-result follow-up should use
  `workspace_status` for non-blocking checks and `workspace_wait` for explicit waits, using the
  returned `follow_up_context` ids and wait timeout so results do not get lost across turns.
- Retrying or continuing failed work must be explicit and workspace-preserving. `workspace_continue`
  queues a new run on the same worker with the original instruction, current workspace files/state,
  and the user's continuation request. It is not an automatic retry loop and must not encode a
  specific customer prompt, file type, website, provider name, or QA phrase in runtime logic.
- Continuation prompts must preserve the original user request without recursively nesting prior
  GlassHive continuation wrappers. Each retry should carry the base task once, the current
  workspace state, the latest failure class/recovery hint, and the user's newest continuation
  instruction. This prevents prompt bloat, unnecessary provider cost, and degraded reliability while
  still honoring the full-context requirement.
- If a provider stream or retryable runtime I/O capture failure happens after the worker created a
  fresh user-facing deliverable in `artifacts/` or `index.html`, GlassHive may promote the run to
  completed with an honest warning and signed artifact links. Arbitrary partial files outside the
  user-facing artifact locations remain failed and retryable; this avoids hiding real incomplete
  work while preventing a finished file delivery from being reported as "no artifacts" or failed.
- Codex effort values are provider-route dependent. GlassHive accepts `none`, `minimal`, `low`,
  `medium`, `high`, and `xhigh`, but deployments must set
  `WPR_CODEX_CLI_ALLOWED_REASONING_EFFORTS` when the selected OpenAI-compatible route supports only
  a subset. Unsupported requested efforts must fall back through
  `WPR_CODEX_CLI_REASONING_EFFORT_FALLBACK` instead of failing the user task.

- `worker_create` and `worker_find_or_resume` accept `execution_mode=host`.
- `codex-cli` uses local Codex CLI full-access/no-approval execution. Host-native Codex defaults to
  the logged-in local Codex CLI configuration when no host-specific model override is set; it must
  not silently inherit the server-side Docker/OpenAI-compatible provider model just because that
  model is configured for sandbox workers.
- `claude-code` uses local Claude Code bypass-permission execution.
- `openclaw-general` requires `openclaw` on `PATH`; if missing, the capability must degrade with a
  clear operator-readable message.
- v1 permits only one active host worker per CLI family unless explicit per-worker CLI auth
  isolation is later proven.
- Host process lifecycle uses a per-run process group with terminate/kill cleanup.
- Parent-visible logs are redacted; raw per-run logs are local files with restrictive permissions.
- Host child processes receive a minimal runtime environment. Provider keys, callback secrets,
  LibreChat secrets, and broad parent process env are not inherited by default.
- Host and sandbox workers may receive a run-scoped GlassHive capability broker grant through
  project MCP config when the host opts in. That grant is not a provider credential, must be
  short-lived, should be written with owner-only file permissions, and must be redacted from
  snapshots, support bundles, callbacks, and public QA evidence.
- Both sandbox and host-native materialization paths must enforce owner-only permissions for broker
  MCP config, Claude local settings, and Codex config files because any of them can carry
  grant-bearing project configuration.
- Docker sandbox workers must be able to reach the host-owned broker endpoint on Linux as well as
  Docker Desktop. The sandbox launch must provide a `host.docker.internal` alias via Docker
  `host-gateway` unless the deployment explicitly overrides the broker URL or disables the alias.

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

### Speed, Warm Workers, and Cost Controls (User Options)

GlassHive worker tasks are inherently heavier than a same-process agent hand-off (a worker is a real
agent loop in its own sandbox). For **interactive connected-account reads** (the user's own Gmail /
Outlook inbox, calendar, or file lookups), the fast path is the dedicated **Connected Accounts
hand-off agent** (`qa/connected-accounts-handoff/`), which answers inline in seconds without spawning
a worker. GlassHive owns **delegated, long, multi-step, Deep Research, and computer/browser** work,
where the levers below make it as fast as it can be without being resource-hungry. Every lever is
config-driven and must not be hardcoded or overfitted to one profile, model, effort, or policy:

- **Where the time actually goes (measured).** A cold `codex-cli` host worker answering
  "any new emails today?" took **~5m01s wall-clock**, decomposed from the runtime events + codex
  rollout as: **queue→start 0.0s** (always-on runtime, instant host spawn) + **~301s agent loop** =
  ~30 sequential broker tool calls at ~6.5s each (~195s, fetching messages largely one-by-one) +
  model reasoning turns (~80s) + final summarize (~15s). For comparison the Connected Accounts
  hand-off (claude-opus, in-process) answered the same question in **~35–45s** with just **3** tool
  calls including a *batched* content fetch. So the gap is the worker's granular autonomous loop +
  reasoning, **not** spawn/bootstrap.
- **Warm worker resume (favorite workspaces) — helps docker, not host.** A worker/workspace can be
  flagged `favorite` (`update_worker_metadata(favorite=...)`), and idle reaping is **off by default**
  (`GLASSHIVE_IDLE_TERMINATE_AFTER_S=0`), so workers stay warm and `Resume`/`Open workspace` reuses
  the warm worker. But for **host** workers the cold-start penalty is already ~0s (measured 0.0s
  queue→start), so warm-resume saves little — its real value is **docker/sandbox** workers, where
  container cold-start is a genuine cost, and continuity (preserved files/browser/login). Do not sell
  warm-resume as the host-mode speed lever.
- **The host-mode speed levers are the agent loop, not the sandbox:** fewer/batched tool calls,
  reasoning effort (`high` over `xhigh`), and a faster quality worker model (below). Interactive
  connected-account reads should use the hand-off agent; GlassHive is for delegated/Deep Research
  work where the loop is the point.

### Results Quality vs Speed — the metric that matters most (measured)

Speed is necessary but **not** the deciding metric — the deciding metric is whether the *answer* is
accurate, complete, and useful for the user's intent. For the same "any new emails today?" query
(2026-05-28, both inboxes):

| | Hand-off agent (claude-opus, in-process) | GlassHive worker (gpt-5.4 codex, autonomous loop) |
| --- | --- | --- |
| Latency | ~40s | ~5m01s |
| Output | 1316 chars, 12 bullets | 3036 chars, 27 bullets |
| Shape | prioritized: "Worth your attention" / "Calendar churn" / "Noise", with synthesized context (e.g. David's multiple actions merged into one bullet) + an explicit "main thing to action" | exhaustive: "Important/Time-Sensitive" + "Other New Mail", every item source-labeled (Gmail/Outlook) + subject + gist, incl. a duplicate-thread note |
| Completeness | selective (newsletters grouped, not all enumerated) | **higher** — enumerated ~26 items incl. every newsletter, caught the 2nd YC match + a GitHub migration the hand-off folded into "noise" |
| Precision on literal details | risk: compressed a meeting time (showed Myk Pono Calendly **1:00 PM** vs the worker's **10 AM** — a synthesis/precision discrepancy) | **higher** — read each message, so literal subjects/times were verbatim |
| Usefulness for "a quick rundown" | **higher** — scannable, prioritized, actionable | lower for triage (a thorough dump), higher for an audit/full sweep |

**Decision / value (do not re-litigate per session) — PARITY, not routing rubrics:**
- Both paths must independently meet the Core Outcome Metric (`01_Key_Principles.md` §0): Quality
  (Intelligence, Relevance, Usefulness, Alignment) + Performance (Fast, Smooth, Reliable). Do **not**
  hardcode "quick rundown → hand-off, full sweep → worker." Whether a result is turned into a rundown is
  the Main Agent's and the user's call, not a runtime rubric. GlassHive's own job is **truth and
  completeness**; the worker's intelligence decides the shape.
- So the gap above is a **GlassHive quality+speed gap to close, not a reason to route around it.** Close
  it by (a) running the worker on a capable model (**Claude Code CLI**; codex was both slower here and,
  separately, weekly-credit-limited — see [[codex-credits-claude-fallback]]) and (b) giving the worker the
  **same memory + conversation-recall context the Main Agent receives**, so its results are as relevant and
  useful, not merely complete.
- **Faster is not automatically better.** A faster, synthesized answer can drop/compress a literal detail
  (the meeting-time discrepancy above). When literal accuracy matters (times, amounts, names), verify the
  specific field against the source rather than trusting a synthesized summary.
- Evaluate every speed change against the **full metric**, not just wall-clock. A latency win that degrades
  Quality is a regression. QA the *result*, not only the clock (`qa/connected-accounts-handoff/`).

### Closing the GlassHive usefulness gap (memory + recall context)

The worker today does **not** receive the user's saved **memory** — the "# Existing memory about the user"
block the Main Agent injects (`api/.../agents/client.js` `useMemory` → `memoryContext`, gated by
`user.personalization.memories`, the `MEMORIES` USE permission, and `appConfig.memory` token limits). It
*does* receive conversation-**recall** file IDs in the launch bundle
(`glasshive_upload_context.tool_resources.file_search.file_ids`: `conversation_recall:*`, `meeting_summary:*`),
but those only help if the worker has a tool to query them. This is why the worker — lacking user-context —
produced an exhaustive dump while the memory-equipped Main Agent prioritized by what matters to the user.

To give the worker **parity** on Quality (Relevance, Usefulness, Alignment) — by strengthening the path, not
routing around it:
- **Inject the user's memory into the worker bootstrap**, the same source the Main Agent uses
  (`db.getFormattedMemories`, gated by the same memory permission + `appConfig.memory` token limit), appended
  as a "what you know about the user" block when the capability-broker bundle is built
  (`GlassHiveCapabilityBootstrapService`). It is the user's own worker, so the user's own memory is in-scope;
  honor `user.personalization.memories` / `appConfig.memory.disabled` (config-driven, never forced).
- **Make recall queryable:** confirm the worker has a `file_search`/recall tool that can read the passed
  `file_search.file_ids` (via the broker or the worker runtime). Passing IDs without a tool to query them is
  inert; expose recall through the same broker so the worker can ground in prior context like the Main Agent.
- Then judge the worker on the **full outcome metric** — complete *and* relevant/useful, not just complete —
  measuring result quality before/after, not only latency. The worker stays the decider of shape; this only
  gives it the same context the Main Agent has so its intelligence has something to prioritize with.

**Status:** memory-injection **implemented** (`client.js` threads `config.configurable.glasshive_worker_memory`
from the same `memoryResult` the Main Agent uses → `GlassHiveCapabilityBootstrapService.workerMemoryBlock`
appends it to the worker `agents_md`/`claude_md`/`codex_md` when present; broker spec covers inject/omit).
Claude-Code-worker before/after **measured** — see next subsection.

### Claude Code worker switch — measured results + two interop fixes (2026-05-29)

**Switch mechanism (no restart, config-driven, reversible).** Worker profile resolves as: explicit
tool arg → per-user preference (`default_worker_profile`) → env `GLASSHIVE_DEFAULT_WORKER_PROFILE`
(`mcp_server.py` `_resolve_profile_from_preferences`). Setting the per-user preference
(`PATCH /v1/preferences {"default_worker_profile":"claude-code"}`, owner `demo-owner`/`local` for
non-enterprise) flips the worker to claude-code with **no restart** and no broker-secret risk, because
the Main Agent omits the profile arg. The env var is the alternative (needs a restart).

**Measured ("any new emails today?", host workers, both inboxes; runs table timing):**

| | Hand-off (claude-opus) | GlassHive worker — codex gpt-5.4 | GlassHive worker — claude-code sonnet-4-6 |
| --- | --- | --- | --- |
| Worker duration | ~40s (in-process) | 301s (5m01s) | **88–144s (~2 min; 3 runs)** |
| Providers read | Gmail + Outlook | Gmail + Outlook | Gmail + Outlook *(after fix #2)* |
| Quality | prioritized, occasionally compresses a detail | complete + verbatim, verbose | complete, prioritized, action-items surfaced, **honest about gaps** |
| Speed vs codex | — | baseline | **~2.5–3.4× faster** |

So switching the worker to claude-code **does** improve speed (~2–3.5×) while meeting the Core Outcome
Metric on Quality (both providers, prioritized + actionable, literal meeting time correct: 1 PM ET = 10 AM
PDT). Faster *and* complete once the two bugs below are fixed.

**Cold vs warm:** the Main Agent spawns a **fresh** worker per request (it did not auto-`workspace_continue`
even for "refresh and check again"). For **host** workers spawn ≈ 0s, so there is no container-warmth
penalty; run-to-run variance (88/120/144s) reflects Claude prompt-cache warmth + output verbosity, not
cold/warm container state. Conversation continuity still works because the Main Agent threads prior context
into the new worker's instruction (the warm follow-up correctly answered "nothing new since… the two items
still stand"). The dedicated `workspace_continue` resume path exists but is not triggered by a natural
re-check; warm-resume remains a docker-startup lever, not a host one (consistent with the section above).

**Bug #1 — claude-code host worker auth: "Not logged in · Please run /login" (fixed).**
`profile_runtime.py` `_host_env` built the worker subprocess env from a small allowlist that **omitted
`USER`/`LOGNAME`**. On macOS the claude CLI's subscription auth lives in the **login Keychain** and resolves
the credential item **by user**; with `USER` absent the worker exits in ~15–20 ms with "Not logged in".
Codex is unaffected because its auth is a portable file (`~/.codex/auth.json`) the runtime copies into the
worker — claude has no equivalent provisioning. Verified by isolation matrix: full-env worked with **and
without** `start_new_session=True` (so setsid was a red herring); stripped-env failed both ways; adding
`USER` alone fixed it. **Fix:** add `USER`/`LOGNAME` (identity, not secrets — secret-stripping unchanged) to
the host-env allowlist. Verified live (worker authed + completed the read) + `test_profile_runtime.py`
asserts the passthrough.

**Bug #2 — MS365/Outlook unreadable for the claude worker: `expected record, received array at
structuredContent` (fixed).** The broker route (`routes/viventium/glasshiveCapabilities.js`, `tools/call`)
set `structuredContent: result` unconditionally. MS365 `list_mail_messages` returns an **array**, but per MCP
`structuredContent` must be a JSON **object**, so a strict client (claude-code worker) rejected every Outlook
read; codex's lenient MCP client tolerated the array, which is why codex got Outlook and claude did not. No
broker tool advertises an `outputSchema`, so `structuredContent` is optional. **Fix:** emit
`structuredContent` only for plain objects; arrays/scalars travel in the `content[0].text` block (which
codex already consumes). Verified live (claude worker then read Gmail **and** Outlook) + a route regression
test. This is the claude-side manifestation of the broker-result-shape contract — not the F3 timeout case.

**Durability of the auth fix (production / Panorad).** The macOS helper is a GUI menu-bar app
(`LSUIElement`/`NSApplication`), so it runs in the user's Aqua session with login-Keychain access; its child
runtime inherits that access, which is why the original failure was the `USER` env-strip **alone**, not
missing Keychain — making the `USER`/`LOGNAME` fix the complete fix for the helper-launched runtime. The
measurement runtime was relaunched from a keychain-attached shell and reparented to launchd (structurally
matching the helper's detached launch) and authed workers. **Residual gate:** re-verify after a real helper
restart. For session-independent durability (a future launchd job that detaches the security session, or
enterprise/headless Panorad), provision a **headless token** — `claude setup-token` (user-run OAuth) →
inject `CLAUDE_CODE_OAUTH_TOKEN` into the worker env via the bootstrap, the file/token parity codex already
has. Do **not** extract or persist the Keychain token.
- **Reasoning effort.** The codex worker's effort is config-driven via
  `WPR_CODEX_CLI_REASONING_EFFORT` (per-worker bootstrap env or global), constrained by
  `WPR_CODEX_CLI_ALLOWED_REASONING_EFFORTS` with `WPR_CODEX_CLI_REASONING_EFFORT_FALLBACK`
  (default `medium`). Prefer `high` over `xhigh` for everyday tasks where the extra budget does not
  change the outcome; reserve `xhigh` for genuinely hard work. A user/operator option, never a
  hardcoded constant.
- **Worker model.** Config-driven via `WPR_MODEL_CODEX_CLI` (default `gpt-5.4`) and
  `WPR_MODEL_OPENCLAW_CLAUDE` (default `claude-sonnet-4-6`). Choose from a launch-ready quality family
  (model governance in `01_Key_Principles.md`); never use a low-tier model (GPT-mini / Haiku class)
  as a speed lever. A faster quality model is a supported option, not a silent default override.
- **Keep-awake vs cost (default OFF for always-on prewarm).** Keeping workers warm has ongoing
  compute cost. Workers stay warm by default for responsiveness; enable idle / paused / max-duration
  reaping (`GLASSHIVE_IDLE_TERMINATE_AFTER_S` and equivalents) to release compute. For **enterprise**,
  treat an always-on prewarmed-workspace pool as an explicit, default-off opt-in with a documented
  cost — surfaced as a clear per-workspace "keep awake for fast responses" toggle next to the existing
  `favorite` flag, so the path of least resistance never silently incurs standing compute.

The product surface should expose `favorite` and a "keep awake" toggle as simple, clearly-labeled
per-workspace options (the runtime metadata and idle-reaper config already back them). Interactive
connected-account answers go through the hand-off agent; GlassHive stays the engine for delegated and
Deep Research work, tuned for speed via warm resume + effort/model options rather than a hardcoded
fast path.

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
- `claude_md` / `agents_md` / `codex_md` -> workspace `CLAUDE.md` / `AGENTS.md` / `CODEX.md`
- `files` -> workspace or home by scope
- `codex_config_append` -> worker-local `$CODEX_HOME/config.toml` and a workspace `.codex/config.toml`
  diagnostic mirror. Host-native Codex workers must run with `CODEX_HOME` pointed at that
  worker-local directory so Codex CLI loads the projected MCP config without leaking broker grants
  into process arguments. Minimal Codex auth may be copied from the host Codex home into the
  worker-local Codex home with owner-only permissions.
- Run-scoped env and MCP/client config must be refreshed before each worker run, including reused
  workers. Broker grants can rotate between runs; stale Claude `.mcp.json` headers, stale Codex MCP
  blocks, or duplicate MCP server sections are security and reliability bugs.
- Claude project MCP config must not persist literal broker bearer grants when an env-indirected
  form is available. The bootstrap writer should materialize broker `Authorization` headers as
  `Bearer ${GLASSHIVE_CAPABILITY_BROKER_TOKEN}` and keep the grant itself in the worker runtime env.

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

For connected-account MCP access inside GlassHive, use the host-owned broker pattern: the worker
talks to `glasshive-user-capabilities`, and the host invokes reviewed user-authorized MCPs server-side.
Do not pass raw Google Workspace, Microsoft 365, or other provider tokens into the worker workspace.
If a host-native runtime also exposes its own connected-account app connector, the broker remains the
first choice when it covers that provider; host app connectors are fallback only after the broker path
is missing, unavailable, auth-blocked, or explicitly requested.

A connected-account worker may treat brokered content access as available only when the bootstrap
contains a complete host-signed broker bundle: broker MCP server config, a projected broker grant
token in the worker env/config, and declared scope such as content-read for the requested operation.
A caller-authored intent flag, prompt wording, or provider name is never enough. If the complete
bundle is absent, incomplete, expired, or scope-limited, GlassHive must inject an honesty guard that
requires the worker to report the limitation instead of claiming Gmail, Google Workspace, Outlook,
Microsoft 365, or other brokered MCP reachability. Enterprise env allowlists may expose the broker
grant token needed to call the host broker, but they must not expose raw provider OAuth tokens or API
keys. Host broker endpoints should rate-limit by grant/user/tenant and redact grant/token fields in
logs and audit previews.

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
- **Artifact link semantics**: the default user-facing file-delivery link must open a GlassHive
  file preview/landing page, not trigger a surprise raw browser download. Raw artifact downloads
  remain supported, but they must be labeled explicitly as `Download file`; chat callbacks and MCP
  guidance should prefer the scoped open/preview URL and expose raw download as a secondary action.
  The preview route must work universally for text, image, and binary artifacts: text is safely
  escaped and previewed, supported small images are shown inline, and every other file type gets a
  clear "File is ready" landing page with a separate explicit download action. This page is a
  user-facing artifact surface and must send restrictive security headers such as `nosniff`,
  `no-referrer`, no-store cache headers, and a tight Content Security Policy. In enterprise mode,
  buttons inside that preview page must also be self-authorizing signed actions: opening the
  preview through a signed link and then clicking `Download file` or `View workspace` must not fall
  back to an unsigned raw route that requires hidden proxy headers.
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
   user. The default artifact link must open a GlassHive file preview/landing page first, while a
   separately labeled `Download file` action downloads the raw artifact. The worker must use a
   universal self-check harness through its bootstrap instructions and success criteria; do not
   overfit `AGENTS.md` to these exact QA prompts.
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
10. Failure recovery and continuation: run a synthetic long-form worker task that fails through a
    structured provider/runtime failure, verify `workspace_status` and `workspace_wait` return the
    right failure class and do not call it success, then ask to continue and verify GlassHive queues
    `workspace_continue` against the same worker/workspace with the original task preserved.
11. Host/sandbox capability routing: with host workers enabled, prompt through LibreChat using
    public-safe language such as "use sandbox" or "use Codex Workspace" and verify the model launches
    `execution_mode=docker`. Separately request an unavailable host profile and verify GlassHive
    returns `runtime_dependency_missing` before creating any worker or run.
12. Delegation fidelity and efficient waiting: use a long public-safe prompt with constraints,
    examples, links, and exclusions, then verify the MCP tool payload preserves the full available
    brief in `context`/instruction instead of a watered-down paraphrase. Verify same-turn wait/status
    can recover a same-conversation recent dispatch when ids are accidentally omitted, that the
    fallback is tenant/user/conversation scoped, that enterprise launches without a conversation
    assertion do not create user-wide remembered fallbacks, that View / Steer is visible before or at
    least in the final answer around long waits, and that polling cadence is not an aggressive
    local/browser loop. Include a browser-network check that completed Workspaces tiles do not keep
    mounting desktop iframes or refreshing every few seconds. If the user prompt also asks the host
    to verify tool selection, View / Steer visibility, callback delivery, wait cadence, or post-run
    inspection from the host UI, preserve those checks as context but keep them out of the worker's
    workspace-internal blocker criteria; the host assistant/operator must verify them with
    browser/log/DB evidence.

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
- Worker prompts must not confuse host/application orchestration with workspace deliverables.
  GlassHive should let the worker use its own intelligence to finish files, browser-visible results,
  research, code, or other workspace tasks, while the host assistant verifies View / Steer delivery,
  MCP tool choice, callbacks, wait/status cadence, and cross-surface inspection externally.
- Worker prompts must also make the worker responsible for checking its own deliverable before
  completion. The final `FINAL REPORT:` should follow a local self-check of the actual files,
  artifacts, browser-visible result, command/test output, or researched facts when those are relevant
  to the task. The worker should continue or repair mismatches it can fix, and report a blocker only
  when the remaining blocker is real and specific.
- GlassHive harness/runtime recovery must happen below the worker intelligence when the worker cannot
  even start. Version mismatches, missing CLIs, broken sidecars, or unavailable managed dependencies
  are not user-facing project goals and must not be delegated as "fix this on your end" unless the
  configured managed/profile/sandbox recovery options have been exhausted or would require an unsafe
  global host mutation.
- GlassHive MCP caller instructions must expose brokered MCP/tool capability as context, not as
  invented workspace goals. Unless the user explicitly specified them, callers must not manufacture
  success criteria, provider lists, output formats, artifacts, ranking rules, or workflow steps for
  the worker. Use minimal acceptance criteria when needed and trust the GlassHive worker to choose
  the best path from the user's request, available MCPs/tools, and runtime context.
- Callers must also avoid injecting memory-derived priorities, active-thread/contact/deal lists, or
  guessed urgency rubrics into `description`, `success_criteria`, or `context` unless the user
  explicitly asked GlassHive to use remembered or prior-chat context.
- For vague user adjectives such as "urgent" or "important", callers must pass the adjective
  through instead of defining a private rubric unless the user defines the rubric.
- User-facing dispatch tools, including `workspace_launch`, `workspace_schedule`, and
  `worker_delegate_once`, must inject the worker-side host-orchestration separation rule into the
  assigned run instruction unless it is already present. This keeps lower-level delegation paths from
  reintroducing host UI checks as workspace-internal blockers.
- For complex multi-source research, large file transformation, coding, comparison, or executive-
  quality deliverables, GlassHive MCP instructions should guide the host model to select higher
  effort settings (`high`/`xhigh` for Codex-style profiles, `max` for Claude-style profiles, or the
  configured equivalent) unless the user explicitly asks for a quick/cheap pass. The runtime must
  still treat effort as structured configuration, not prompt-string intent matching.
- Idle/cost controls are product requirements, not operator nice-to-haves. Default enterprise
  configuration must make the cost risk visible and configurable.
- Paused/idle compute release must be idempotent. Once GlassHive has stopped worker compute while
  preserving workspace state, the worker record must carry a durable release marker so periodic
  reaper passes do not repeatedly stop the same already-released compute or emit duplicate lifecycle
  events. Starting/resuming compute clears that marker.
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
- Enterprise MCP result and recovery tools (`workspace_status`, `workspace_wait`,
  `workspace_continue`, `workspace_artifacts`, and `workspace_artifact_download`) must re-check
  tenant and owner scope before returning run text, View / Steer links, artifact listings, or signed
  download links. A guessed run or worker id is not sufficient authorization.
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
and acceptance checklist live in the private enterprise deployment repo. Public product docs keep
only reusable product requirements and public-safe QA cases.

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
| `WPR_MODEL_HOST_CODEX_CLI` | unset | Optional host-native Codex model override when the logged-in local Codex account should use a deployment-specified model instead of its local Codex config |
| `CODEX_MODEL` | unset | Optional generic host-native Codex CLI model override; honored when `WPR_MODEL_HOST_CODEX_CLI` is unset |
| `GLASSHIVE_HOST_CODEX_INHERIT_PROVIDER_MODEL` | unset | Opt-in compatibility switch for host-native Codex to inherit `WPR_MODEL_CODEX_CLI`; leave unset so host workers use local Codex config by default |
| `WPR_OPENCLAW_START_GATEWAY` | `false` | Opt-in OpenClaw loopback gateway process; task runs use `openclaw agent --local` directly for lower overhead and to avoid session contention |
| `WPR_CODEX_CLI_ALLOWED_REASONING_EFFORTS` | `none,minimal,low,medium,high,xhigh` | Comma-separated Codex effort values supported by the configured Codex provider route; set this when a deployment route rejects a value such as `minimal` |
| `WPR_CODEX_CLI_REASONING_EFFORT_FALLBACK` | `medium` | Codex effort used when the requested per-run/user default effort is not allowed by `WPR_CODEX_CLI_ALLOWED_REASONING_EFFORTS` |
| `WPR_SANDBOX_VNC_PASSWORD` | `secret` | VNC access password |
| `WPR_SANDBOX_VNC_NO_PASSWORD` | `1` | Disable VNC password |
| `WPR_MCP_BLOCKING_WAIT_DEFAULT_SEC` | `1800` | Default MCP `workspace_wait` completion wait when the model/user asks to wait for results and omits an explicit timeout; enterprise deployments that expect 25+ minute research/file jobs may raise this, for example to `2700` |
| `WPR_MCP_BLOCKING_WAIT_MAX_SEC` | `1800` | Hard cap on MCP blocking wait duration; prevents a chat request from blocking longer than policy while the worker continues in the background; enterprise deployments may raise this with a matching LibreChat MCP `timeout` cushion, for example to `3600` |
| `WPR_MCP_BLOCKING_WAIT_POLL_INTERVAL_SEC` | `5` | Efficient polling cadence and floor for `workspace_wait`; models should omit per-call poll intervals for normal long work, and the runtime must not allow lower long-run polling values |
| `WPR_MCP_RECENT_DISPATCH_TTL_SEC` | `14400` | In-process recent-dispatch fallback TTL for same authenticated user/conversation wait/status recovery |
| `WPR_MCP_RECENT_DISPATCH_MAX_ENTRIES` | `1024` | Safety cap on in-process recent-dispatch fallback entries |
| GlassHive LibreChat MCP `timeout` | `1860000` ms | Config-level timeout for the GlassHive MCP server, intentionally longer than the 30-minute wait cap plus overhead; deployments should keep a generous cushion above `WPR_MCP_BLOCKING_WAIT_MAX_SEC` plus proxy/runtime latency |
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
| `GLASSHIVE_PAUSED_TERMINATE_AFTER_S` | `0` | When positive, stop manually paused worker compute after the configured age; already-released paused compute must be skipped until the worker is resumed |
| `GLASSHIVE_IDLE_REAPER_INTERVAL_S` | `60` | Idle reaper interval |

For long enterprise research/file jobs, the wait defaults should be treated as a chat transport
policy, not a worker-kill policy. Raising `WPR_MCP_BLOCKING_WAIT_DEFAULT_SEC` to 2700 and
`WPR_MCP_BLOCKING_WAIT_MAX_SEC` to 3600 is valid when the LibreChat MCP transport timeout has a
larger cushion; the worker continues in the background if the chat wait exits early.
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
