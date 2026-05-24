# Viventium Prompt Workbench

Standalone local developer/QA app for seeing and reconciling Viventium prompt state.

It keeps three states visible:

- Source: prompt markdown/YAML under `LibreChat/viventium/source_of_truth`
- Live: LibreChat managed agent instructions compared through `viventium-sync-agents.js`
- Evaluated: prompt/eval runs tied to prompt hashes

Core surfaces include Prompt Atlas, Prompt Flow Dashboard, Monaco Prompt Detail, Live Drift Board,
Draft Review, Eval Designer/Results, Scheduled Prompts, Frame Observability, and the local
LibreChat integration contract panel.

Scheduled Prompts live as prompt objects at the top of Prompt Flow, with the same object-context
tabs as source prompts. The resizable Prompt Flow pane keeps its header and add button fixed while
the tree scrolls. It shows Workbench-private GlassHive schedules and existing user-level Scheduling
Cortex tasks for the authenticated admin, with source/executor/channel metadata so operators can
tell whether a row runs through GlassHive host execution or the regular Viventium agent scheduler.
The Drafts tab shows the selected scheduled prompt body plus rendered variables and snapshot
hashes, while the Schedules tab remains the edit, enable/disable, run, delete, route/config, and
run-history surface. Pull Live and Push Dry-run color themselves green when live/source are current
and orange when pull, push, conflict, or blocking-draft work is pending, so sync status is visible
without opening the drift board.
Manual runs for user-level Viventium schedules require a route-aware confirmation because they may
deliver through their stored channels; Workbench-private scheduled prompts queue GlassHive directly.
The built-in private nightly schedule is labeled `Subconscious Deep Thought`; `Nightly subconscious
thought formation` remains the template/legacy alias.
Standalone Workbench launches load the canonical local runtime env first so schedule DB paths,
Scheduling Cortex callback ports, GlassHive settings, and helper-bound admin identity match the
installed runtime.

The UI follows the operating system color scheme automatically, including Monaco editor theme,
flow canvas, tables, and drift/status panels.

## Run

```bash
npm install
npm run build
npm run serve
```

The installed Viventium helper and CLI use the managed lifecycle command:

```bash
bin/viventium prompt-workbench open
bin/viventium prompt-workbench stop
```

To keep Prompt Workbench running alongside the local Viventium runtime, enable it in canonical
config with `runtime.prompt_workbench.enabled: true`. The compiler emits `START_PROMPT_WORKBENCH`,
the stack launcher starts the same loopback Workbench server, and its watchdog restarts only the
Workbench sidecar.

For frontend development with hot reload:

```bash
npm run dev:api
npm run dev
```

Open `http://127.0.0.1:5179` in dev mode or `http://127.0.0.1:8781` after `npm run build && npm run serve`.

## Safety Rules

- No new prompt database.
- No generated runtime file writes.
- No silent Mongo writes.
- Scheduled prompt bodies, rendered variable snapshots, and run details stay in private App
  Support/Scheduling Cortex state, not public prompt registry files.
- Source edits create reviewed drafts against source files only.
- Live push uses the existing guarded sync helper with `--prompts-only --dry-run` before reviewed
  apply.
- The sync ledger and drafts live under private App Support user data:
  `~/Library/Application Support/Viventium/private-user-data/prompt-workbench/`.
