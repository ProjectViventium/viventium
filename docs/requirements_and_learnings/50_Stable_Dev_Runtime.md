# 50. Stable Dev Runtime

## Purpose

Viventium developers need a stable installed runtime while they edit and test Viventium. The product
must support that without copying code into install paths, duplicating heavy local services, or
confusing upstream component boundaries.

## Product Contract

- The normal installed runtime remains the canonical local product runtime.
- `bin/viventium dev-env` creates side-by-side development state under App Support.
- Dev envs separate app-facing surfaces by default:
  - LibreChat API
  - LibreChat frontend
  - Modern LiveKit Playground (`agent-starter-react`)
  - voice health port when needed
- Dev envs also separate per-runtime sidecars that own mutable runtime-local state, including
  Scheduling Cortex.
- The classic `agents-playground` UI is not part of local prod or dev-env defaults. It remains an
  explicit classic-playground opt-in only, so default starts do not spend resources on the old UI.
- Heavy local services are shared singleton services by default:
  - Meilisearch conversation search
  - recall/RAG
  - SearXNG
  - Firecrawl
  - Google Workspace MCP
  - Microsoft 365 MCP
- Shared singleton services must not be duplicated merely because a developer starts a dev env.
- Full isolation is an explicit advanced future mode, not the default.
- Launcher-managed modern-playground runtimes should prewarm the voice startup API routes before
  starting the voice worker so local users and developers do not pay the first-hit Next.js dev
  compile cost on the call page. These prewarm requests are bounded and warn-only so a stuck dev
  compile does not delay the rest of runtime startup for minutes.
- The macOS helper must not keep the installed local-prod runtime healthy by repeatedly rendering
  expensive user-facing pages. Steady-state helper checks use one shared health snapshot per refresh
  cycle, probe the modern playground through a lightweight `/api/health` endpoint, and back off while
  the stack remains healthy. This keeps local prod running beside dev work without turning the helper
  into a background Next.js page renderer.

## Mental Model For Contributors

Viventium has two local modes that can exist on the same Mac:

- **Local prod** is the installed, user-facing Viventium runtime. It is what the helper starts and
  what normal users should rely on day to day.
- **Dev env** is an optional side-by-side developer runtime. It lets contributors test code without
  stealing the local prod app ports or rewriting installed source paths.

Local prod and dev envs must stay separate at the app boundary and shared at the expensive-service
boundary:

| Surface | Local Prod | Dev Env Default |
| --- | --- | --- |
| LibreChat API | canonical installed port | offset port |
| LibreChat frontend | canonical installed port | offset port |
| Modern LiveKit Playground | canonical installed port | offset port |
| voice health port | canonical installed port | offset port when needed |
| Scheduling Cortex MCP | canonical installed port and scheduler DB | offset port and dev-env scheduler DB |
| Meilisearch conversation search | shared singleton | use local prod singleton |
| recall/RAG | shared singleton | use local prod singleton |
| SearXNG | shared singleton | use local prod singleton |
| Firecrawl | shared singleton | use local prod singleton |
| Google Workspace MCP | shared singleton | use local prod singleton |
| Microsoft 365 MCP | shared singleton | use local prod singleton |

This is intentional. The default developer experience should avoid duplicate memory/search/MCP
services because those consume local resources and can make both runtimes flaky. If a future task
needs full isolation, it must be an explicit advanced path with separate ports, separate state, and
clear QA proving it did not become the default.

## Contributor Quickstart

Use this flow when developing Viventium while keeping the installed local product stable:

```bash
# See which checkout the installed helper/runtime uses.
bin/viventium dev-runtime status

# Create a side-by-side dev runtime with offset app-facing ports.
bin/viventium dev-env create dev

# Inspect what changed before starting it.
bin/viventium dev-env status dev

# Run a command inside the dev env.
bin/viventium dev-env run dev start
```

With the default offset, test the two local runtimes at different user-facing URLs:

| Runtime | Web | API | Playground |
| --- | --- | --- | --- |
| Local prod | `http://localhost:3190` | `http://localhost:3180/api` | `http://localhost:3300` |
| Dev env `dev` | `http://localhost:4190` | `http://localhost:4180/api` | `http://localhost:4300` |

Use local prod for normal installed/runtime QA and Telegram checks. Use the dev env for local code
experiments that should not steal the installed runtime's app-facing ports or state. If the dev env
needs conversation search, recall, search, Firecrawl, Google Workspace MCP, or Microsoft 365 MCP behavior, keep the
shared singleton service owner running; those services are intentionally not duplicated by default.

Use this flow when a local development checkout is ready to become the installed local runtime:

```bash
bin/viventium dev-runtime activate-current --validate --restart --allow-protected-folder
```

That command updates the existing runtime-checkout state, validates the checkout, compiles config,
runs doctor checks, refreshes the helper binding, and restarts when requested. It does not copy code
into an install directory.

Use this flow when checking whether the installed runtime can update safely:

```bash
bin/viventium upgrade --check --json
```

This is read-only. A real update still goes through:

```bash
bin/viventium upgrade --restart
```

Use this flow when opening the local prompt QA surface without touching the main runtime:

```bash
bin/viventium prompt-workbench open
bin/viventium prompt-workbench stop
```

`prompt-workbench stop` is intentionally scoped to the Prompt Workbench web app. It must not stop
the installed Viventium runtime or any shared singleton service.

Prompt Workbench can also be enabled as an optional local-runtime sidecar through
`runtime.prompt_workbench.enabled: true` in the canonical config. When enabled, the compiled runtime
sets `START_PROMPT_WORKBENCH=true`, the stack launcher starts Workbench during Viventium startup, and
a local watchdog restarts it if the loopback app dies. The launcher must not print the authenticated
Workbench URL or token into stack logs; users should open the app through `bin/viventium
prompt-workbench open`, the helper submenu, or the LibreChat account-menu entry. If the user stops
Workbench explicitly, the watchdog respects the local user-stopped marker instead of immediately
reopening it.

## Do And Do Not

- Do use `dev-env` when you need a side-by-side development runtime.
- Do use `dev-runtime activate-current --validate --restart` when promoting the current checkout to
  the installed local runtime.
- `dev-runtime activate-current --validate --restart` must fail closed before stop/restart when
  config compilation, doctor, or helper refresh fails. A missing optional prerequisite such as a
  required Docker daemon may block validation, but it must not schedule a delayed stop of the
  currently running stack.
- Do use `prompt-workbench open/start/stop/status` for the standalone prompt QA app.
- Do use `runtime.prompt_workbench.enabled: true` when Prompt Workbench should stay up with the
  local Viventium runtime.
- Do keep Scheduling Cortex per-runtime: local prod and each dev env get distinct scheduler DBs and
  distinct MCP ports. The default dev-env scheduler port is biased away from shared singleton ports
  so it does not collide with RAG.
- Do keep heavy singleton services shared unless the user explicitly asks for full isolation and QA
  proves the isolation.
- Do keep Viventium-owned Docker singleton services bounded with source-owned memory, CPU, PID, and
  log-rotation defaults; live-only container edits are not a durable product fix.
- Do keep helper-launched stack logs bounded on fresh starts so long-lived local prod runs do not
  accumulate unbounded dev-server output.
- Do treat Meilisearch indexes/tasks as derived conversation-search state and rebuild from Mongo
  only through the supported readiness/sync path.
- Do keep generated runtime state under App Support out of git.
- Do not edit generated App Support files and call that a product fix.
- Do not create a second active-checkout pointer; use the existing runtime-checkout state.
- Do not copy source into install paths to "push" a local build.
- Do not wire helper Prompt Workbench controls to the main `start` or `stop` commands.
- Do not silently pull, reset, or update nested repos from dev-env commands.
- Do not treat dirty local QA state as release-ready.

## Commands

```bash
bin/viventium dev-env create dev
bin/viventium dev-env list
bin/viventium dev-env status dev
bin/viventium dev-env run dev start
```

`dev-env create` copies the canonical config into a named dev App Support directory, offsets only
app-facing ports, and records the shared singleton services in `runtime.dev_env`.

Generated dev-env state lives under:

```text
~/Library/Application Support/Viventium/dev-envs/<name>/
```

That directory is local runtime state, not a tracked source-of-truth surface.

```bash
bin/viventium dev-runtime activate-current --validate --restart --allow-protected-folder
```

`dev-runtime activate-current` is a developer-friendly wrapper over the existing
`runtime-checkout` state. It does not copy source code. It selects the current checkout, compiles
config, runs doctor, refreshes the helper, and optionally restarts.

## Update Check

`bin/viventium upgrade --check --json` reports update availability and blockers without pulling,
compiling, installing helpers, or touching the running stack.

The helper uses this for **Check for Updates...**:

- Up to date
- Update available
- Update blocked
- Offline or git error

Installing an update still uses the canonical `bin/viventium upgrade --restart` path.
The check also reports and blocks on helper fallback rebuild need using the same package-source hash
contract as `install_macos_helper.sh`, so the helper does not present stale package state after source
changes.

## Safety Rules

- Do not add a second active-checkout pointer. Use the existing App Support `active-checkout.json`.
- Do not hide config changes in environment-only paths. Dev env config is written to that env's
  canonical `config.yaml`.
- Do not silently update nested repos or `components.lock.json`.
- Do not treat a dirty checkout as release-ready. Dirty local testing requires an explicit local-only
  acknowledgement.

## QA Requirements

Acceptance requires proving:

- dev env app-facing ports differ from the installed runtime
- singleton services are not duplicated by default
- update check is side-effect-free
- activate-current uses the existing runtime-checkout path
- helper update UX can report up-to-date, blocked, and update-available states
