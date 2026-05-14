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
  - Modern Playground
  - voice health port when needed
- Heavy local services are shared singleton services by default:
  - recall/RAG
  - SearXNG
  - Firecrawl
  - Google Workspace MCP
  - Microsoft 365 MCP
- Shared singleton services must not be duplicated merely because a developer starts a dev env.
- Full isolation is an explicit advanced future mode, not the default.

## Commands

```bash
bin/viventium dev-env create dev
bin/viventium dev-env list
bin/viventium dev-env status dev
bin/viventium dev-env run dev start
```

`dev-env create` copies the canonical config into a named dev App Support directory, offsets only
app-facing ports, and records the shared singleton services in `runtime.dev_env`.

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
