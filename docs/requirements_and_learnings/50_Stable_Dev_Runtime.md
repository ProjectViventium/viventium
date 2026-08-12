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
- Prompt Workbench is a first-class app-facing dev port. The compiler owns
  `runtime.ports.prompt_workbench_port`, applies the dev offset when no explicit override exists,
  and exports the resulting runtime-specific port.
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
- A listener on the configured Mongo port is not sufficient persistence readiness. Before reusing an
  existing Mongo process, the native launcher must query the running server's parsed command-line
  options and verify that `storage.dbPath` resolves to the configured Viventium data directory. A
  listener backed by restored, development, or otherwise unexpected state must fail closed instead
  of silently switching the user's conversation and memory history.
- Launcher-managed modern-playground runtimes should prewarm the voice startup API routes before
  starting the voice worker so local users and developers do not pay the first-hit Next.js dev
  compile cost on the call page. These prewarm requests are bounded and warn-only so a stuck dev
  compile does not delay the rest of runtime startup for minutes.
- The macOS helper must not keep the installed local-prod runtime healthy by repeatedly rendering
  expensive user-facing pages. Steady-state helper checks use one shared health snapshot per refresh
  cycle, probe the modern playground through a lightweight `/api/health` endpoint, and back off while
  the stack remains healthy. This keeps local prod running beside dev work without turning the helper
  into a background Next.js page renderer.
- Helper recovery must remain compatible with older owner-owned helper logs. A secure append opener
  may tighten an already-open, single-link, owner-owned regular log from legacy `0644` to `0600`; it
  must still reject symlinks, foreign owners, extra hard links, and unsafe file types. Stack launch
  itself is single-flight for the entire health-wait operation. The detached process-group receipt
  can be briefly replaced during `start --restart`, so receipt polling alone is not sufficient to
  prevent overlapping recovery launches during long search-index or client-build warm-up. A manual
  CLI start publishes an owner/PID/repository-bound startup claim before releasing the CLI lock and
  clears it only after the launcher has handed off startup ownership. Helper `launch` treats a valid,
  live claim as already starting; dead, foreign, symlinked, multi-link, or expired claims do not block
  recovery.
- The installed macOS helper owns a durable desired-state supervisor for local prod. A healthy stack
  that dies after login must be relaunched with bounded exponential backoff, not left down until the
  next login. Helper **Stop** and **Quit** persist intentional `stopped` state; a later helper **Start**
  persists `running` state and resumes supervision. Helper reinstall, checkout activation, and upgrade
  must preserve this state and unknown future helper-config fields. A developer checkout inside a
  macOS-protected folder still requires the user's one-time operating-system folder approval before
  the installed helper can execute it.

## Mental Model For Contributors

Viventium has two local modes that can exist on the same Mac:

- **Local prod** is the installed, user-facing Viventium runtime. It is what the helper starts and
  what normal users should rely on day to day.
- **Dev env** is an optional side-by-side developer runtime. It lets contributors test code without
  stealing the local prod app ports or rewriting installed source paths.

Local prod and dev envs must stay separate at the app boundary and shared at the expensive-service
boundary:

| Surface                         | Local Prod                                     | Dev Env Default                           |
| ------------------------------- | ---------------------------------------------- | ----------------------------------------- |
| LibreChat API                   | canonical installed port                       | offset port                               |
| LibreChat frontend              | canonical installed port                       | offset port                               |
| Modern LiveKit Playground       | canonical installed port                       | offset port                               |
| Prompt Workbench                | canonical installed port and App Support state | offset port and dev-env App Support state |
| voice health port               | canonical installed port                       | offset port when needed                   |
| Scheduling Cortex MCP           | canonical installed port and scheduler DB      | offset port and dev-env scheduler DB      |
| Meilisearch conversation search | shared singleton                               | use local prod singleton                  |
| recall/RAG                      | shared singleton                               | use local prod singleton                  |
| SearXNG                         | shared singleton                               | use local prod singleton                  |
| Firecrawl                       | shared singleton                               | use local prod singleton                  |
| Google Workspace MCP            | shared singleton                               | use local prod singleton                  |
| Microsoft 365 MCP               | shared singleton                               | use local prod singleton                  |

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

| Runtime       | Web                     | API                         | Playground              | Prompt Workbench        |
| ------------- | ----------------------- | --------------------------- | ----------------------- | ----------------------- |
| Local prod    | `http://localhost:3190` | `http://localhost:3180/api` | `http://localhost:3300` | `http://localhost:8781` |
| Dev env `dev` | `http://localhost:4190` | `http://localhost:4180/api` | `http://localhost:4300` | `http://localhost:9781` |

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

The stack-managed Workbench owns its configured canonical loopback port. During startup it may
reclaim that port only from the exact process recorded by the current runtime's App Support state,
when the recorded PID, checkout, and port all still match. A different checkout, an untracked prior
launch, or any other listener is foreign and must be left untouched; startup fails closed instead.
This keeps a healthy-looking restored/dev Workbench from silently serving stale code while the
active runtime reports the sidecar as ready.

### Side-By-Side Lifecycle Ownership

- A dev runtime owns mutable state under its own App Support root, its recorded PID files, and its
  compiled ports. Prompt Workbench uses all three signals; a healthy listener alone is not ownership.
- The `dev-env run` wrapper sets dev-scope identity before compilation. A supported dev stop then
  recompiles the named dev config, export-loads both its generated `runtime.env` and selected
  `runtime.local.env` override layer, and fails closed unless the compiled runtime still identifies
  itself as that dev environment. Start, stop, and removal cleanup pass the same selected runtime
  ownership to native child processes: wrapper identity, App Support root, base/profile state roots,
  ports, native credential inputs, and MongoDB/Meilisearch/LiveKit data/config paths. Ambient values
  inherited from local prod must never make a dev child inspect or manage canonical state, and local
  path expressions are evaluated only after the selected structural roots exist.
- Dev stop is strict and runtime-scoped: stop its own Prompt Workbench sidecar, PID-owned services,
  unique listeners, and local Compose project, but never use same-checkout or workspace-wide process
  sweeps that could terminate local prod or shared singletons.
- Recall/RAG remains shared by default. When a dev environment explicitly owns local RAG, the
  compiler offsets the vector-database host port and gives the dev stack a distinct Compose project
  name so start/stop cannot claim the product RAG containers.
- Native support-service PID files are hints, not authority. Stop must verify that the live PID still
  matches the expected MongoDB, Meilisearch, or LiveKit runtime identity before signalling it; stale
  or reused PIDs are removed without killing the unrelated process. Process identity inspection must
  read the complete argv: MongoDB and Meilisearch place their runtime-owned data paths late in long
  command lines, and a display-width-truncated argv must not make an exact selected-runtime PID look
  foreign. Ownership requires the exact service executable identity and exact option/value boundaries;
  a lookalike executable, prefixed data/config path, or similarly named LiveKit option stays foreign.
  On macOS, `ps ... -o comm=` is not executable-path authority because the kernel field is truncated;
  legacy MongoDB, Meilisearch, and LiveKit compare their short exact `ucomm` basenames instead. Easy
  Install MongoDB resolves the running process's primary `lsof -d txt` image and compares its
  canonical real path with the canonical pinned binary path, failing closed when that proof is
  missing or ambiguous.
- An already-listening native service is adopted only when its configured TCP port resolves to one
  unique PID and that PID passes the same executable, port, and runtime-state identity checks. Start
  atomically restores the selected runtime's PID receipt for an exact MongoDB, Meilisearch, or
  metadata-aligned LiveKit listener, including over a stale receipt. Zero, multiple, or foreign
  listener PIDs fail closed; a healthy port alone is never adoption authority.

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
- Do verify that the stack-managed Workbench process and state file resolve to the active runtime
  checkout; a loopback health response from another checkout is not sufficient readiness.
- Do prove side-by-side Workbench ownership through distinct visible pages plus stable watchdog PIDs;
  HTTP health alone is supporting evidence.
- Do keep Scheduling Cortex per-runtime: local prod and each dev env get distinct scheduler DBs and
  distinct MCP ports. The default dev-env scheduler port is biased away from shared singleton ports
  so it does not collide with RAG.
- Do report Scheduling Cortex as running only when `/health` has the expected semantic status,
  service identity, and hash of the configured scheduler ledger. An arbitrary HTTP 200 is not
  readiness. Report Memory Hardening from its dedicated loaded/receipt/run health state rather than
  configuration presence alone.
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
- Do not let a dev stop fall back to canonical or stale generated identity; refuse before any stop
  when the named dev config cannot compile and prove dev scope.
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

Mutable provider state follows that same boundary. In particular, the generated GlassHive
`WPR_DB_PATH` is derived from the active `VIVENTIUM_STATE_ROOT`; a dev environment must never fall
back to the canonical installed runtime's GlassHive database. This keeps consultant sessions,
provider requests, Stop fences, and QA runs isolated even when the source checkout is shared.
The local `GLASSHIVE_MCP_URL` must likewise follow the compiled `GLASSHIVE_MCP_PORT` when no
explicit MCP URL is configured. An offset dev port with a canonical-port URL silently reconnects
LibreChat to the wrong GlassHive MCP and is not an isolated test environment.

```bash
bin/viventium dev-runtime activate-current --validate --restart --allow-protected-folder
```

`dev-runtime activate-current` is a developer-friendly wrapper over the existing
`runtime-checkout` state. It does not copy source code. It selects the current checkout, compiles
config, runs doctor, refreshes the helper, and optionally restarts.

## Update Check

`bin/viventium upgrade --check --json` reports update availability and blockers without pulling,
writing Git metadata, creating App Support state, compiling, installing helpers, or touching the
running stack. Remote observation uses `git ls-remote`; when the remote commit is not already in the
local object database, `commits_behind` is a lower-bound signal and `remote_history_complete` is
false rather than pretending an exact history count was available. The check requires the current
branch's explicit remote+merge configuration; it does not silently assume `origin`, and the mutating
pull uses that same configured pair.

The helper uses this for **Check for Updates...**:

- Up to date
- Update available
- Update blocked
- Offline or git error

Installing an update still uses the canonical `bin/viventium upgrade --restart` path.
The check also reports and blocks on helper fallback rebuild need using the same package-source hash,
binary SHA-256, executable, and universal-architecture contract as `install_macos_helper.sh`, so the
helper does not present missing, corrupted, single-architecture, or stale package state as aligned.

The machine-readable exit contract is:

- `0`: inspection completed and an update/repair can safely be attempted; this includes clean
  selected components that need refresh to their configured pins
- `2`: remote or Git inspection could not complete
- `3`: a policy/safety blocker exists, including a dirty selected component, invalid/unverifiable
  lock entry, dirty parent checkout, or stale helper artifact

The JSON keeps `component_lock_drift` for blocking component states and reports safe clean movement
under `component_refresh_required`. When canonical config exists, only components selected for that
installation block its upgrade; other managed checkouts remain release diagnostics. The helper must
require schema version 1 and typed readiness/update/blocker/count/component fields, then parse valid
JSON even when the process returns `2` or `3`, so a person sees the concrete blocker instead of a
generic command failure. Parent dirtiness includes untracked user work while declared managed
component roots are classified by the component inspector rather than double-counted as parent files.
A stray untracked parent file is therefore an intentional fail-closed upgrade refusal: the CLI must
tell the user to preserve/remove the file and retry, or use the explicitly local-only
`--skip-pull --allow-dirty` path. The synthetic regression must prove refusal occurs before App
Support creation or source/component mutation and that the untracked file remains unchanged.

The mutating upgrade path refuses a running stack without `--restart` before pull or continuity
mutation, runs the structured local-safety inspection before pull/stop/component mutation, captures
and gates a trustworthy pre-upgrade continuity baseline while services are still available, and
fails if the stack cannot stop. `--allow-dirty` is accepted only with `--skip-pull`. Automatic
service recovery after a later failure is availability compensation from the current on-disk state,
not a rollback; the CLI must say that the upgrade may be partially applied. A post-upgrade
continuity `error`, `unknown`, malformed result, or capture failure disables that automatic restart.
For a running stack, stop succeeds before pull. Helper refresh remains unlaunched until an accepted
post-audit and successful runtime restart, preventing helper login auto-start from racing the gate.
After component bootstrap, the CLI reruns structured component alignment; stdout wording is never a
safety gate.

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
- Prompt Workbench receives a distinct compiler-owned port and App Support/PID state in each runtime
- a supported dev stop closes every runtime-owned dev listener/container, including its Workbench
  and optional local RAG, while prod process identities and prod RAG container identities stay unchanged
- stale native PID files never authorize stopping a process that fails runtime identity validation

The 2026-08-10 post-fix `SDR-013` evidence is **PARTIAL**. A supported isolated-runtime stop/start
restored the selected stack while local prod remained healthy, and the automated complete-argv,
executable, path-boundary, unique-listener, stale-PID, selected-child-environment, and ambient-
credential guards pass. The retained runtime logs do not preserve the preceding exact-listener
adoption event. Repeat the complete supported start -> adopt -> stop -> start sequence with a
sanitized durable ledger before promoting `SDR-013` or `STABLEDEV-UC-009` to PASS.
