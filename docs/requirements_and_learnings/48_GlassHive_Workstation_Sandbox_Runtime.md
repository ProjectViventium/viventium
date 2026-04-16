# GlassHive: Workstation-Sandbox Runtime

**Purpose**: GlassHive is a first-party, standalone workstation-sandbox runtime that gives AI workers
a persistent, resumable execution environment with a real browser, terminal, filesystem, and live
operator visibility. It is composable with Viventium/LibreChat but architecturally independent.

**Repo**: `ProjectViventium/GlassHive` (first-party, no upstream fork boundary)
**License**: FSL 1.1 with Apache-2.0 future license
**Path**: `viventium_v0_4/GlassHive/` (gitignored from the public repo; separate git history)

---

## Core Concepts

| Term | Meaning |
|---|---|
| **Sandbox** | A Docker-backed workstation container with desktop, browser, terminal, and filesystem |
| **Worker** | The AI runtime operating inside a sandbox (profiles: `codex-cli`, `claude-code`, `openclaw-general`) |
| **Project** | An operator-defined mission with goal, success criteria, and continuity wrapper |
| **Bootstrap Bundle** | A portable preset containing auth, MCP config, instructions, env, and files that seeds a worker |

---

## Architecture

### Four Layers

1. **Control Plane** -- FastAPI API (port 8766), SQLite persistence, project-first operator web UI
2. **Worker Runtime** -- Profile-agnostic runtime supporting multiple worker types
3. **Sandbox Substrate** -- Docker containers with persistent volume mounts
4. **Client Adapters** -- HTTP API, MCP (streamable-http, stdio, sse), direct API calls

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

---

## Browser Session Persistence

- Browser profile data lives in the worker home directory and **persists across pause/resume**
- Same named worker = same browser identity (cookies, sessions, login state)
- Parent systems should use **stable worker aliases** for browser-authenticated work
  (e.g. `demo-linkedin-primary`, `demo-gmail-browser`)
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

---

## MCP Integration

- **Framework**: FastMCP
- **Transport**: Streamable-HTTP primary, stdio for local, sse for compatibility
- **Server name**: `glass-hive`
- **Ports**: MCP on 8767, control plane API on 8766

### Exposed MCP Tools

- **Project**: `projects_list`, `project_create`, `project_get`, `project_runs`, `project_events`
- **Worker**: `workers_list`, `worker_create`, `worker_get`, `worker_live`
- **Execution**: `worker_run` (queue instruction), `worker_message` (send operator message)
- **Lifecycle**: `worker_pause`, `worker_resume`, `worker_interrupt`, `worker_terminate`
- **Observation**: `worker_desktop_action`, `worker_takeover`, `run_get`
- **Metrics**: `metrics_summary`

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
- **User-facing naming**: the glossy/operator UI should present persistent personal environments as `Workspaces` rather than exposing raw worker IDs or `sandbox` terminology in the primary flow

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
| `GLASSHIVE_DEFAULT_LAUNCH_SURFACE` | `desktop` | Project-first UI default initial watch surface (`desktop`, `terminal`, `auto`) |
| `GLASSHIVE_SHOW_LIVE_TERMINAL_IN_DESKTOP` | `true` | When desktop-first watch is used, auto-open the active live run terminal inside the desktop |
| `WPR_IDLE_DESKTOP_PRIME_BROWSER` | `true` | Prime fresh worker desktops with the GlassHive placeholder browser page instead of the inherited base-image splash |

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
