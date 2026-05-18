# Viventium Prompt Workbench

Standalone local developer/QA app for seeing and reconciling Viventium prompt state.

It keeps three states visible:

- Source: prompt markdown/YAML under `LibreChat/viventium/source_of_truth`
- Live: LibreChat managed agent instructions compared through `viventium-sync-agents.js`
- Evaluated: prompt/eval runs tied to prompt hashes

Core surfaces include Prompt Atlas, Prompt Flow Dashboard, Monaco Prompt Detail, Live Drift Board,
Draft Review, Eval Designer/Results, Frame Observability, and the local LibreChat integration
contract panel.

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
- Source edits create reviewed drafts against source files only.
- Live push uses the existing guarded sync helper with `--prompts-only --dry-run` before reviewed
  apply.
- The sync ledger and drafts live under private App Support user data:
  `~/Library/Application Support/Viventium/private-user-data/prompt-workbench/`.
