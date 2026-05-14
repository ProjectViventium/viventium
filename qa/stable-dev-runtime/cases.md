# Stable Dev Runtime Cases

## SDR-001: Dev Env Uses Separate App-Facing Ports

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: CLI, generated config
- Preconditions: canonical config exists
- Steps: run `bin/viventium dev-env create dev --port-offset 1000`, then inspect the dev config
- Expected Result: LibreChat API, frontend, playground, and voice health ports are offset
- Forbidden Result: heavy singleton service ports are unnecessarily offset or duplicated
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed

## SDR-002: Singleton Services Are Not Duplicated By Default

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: CLI, compiler, launcher
- Preconditions: dev env exists with default shared singleton policy
- Steps: compile the dev env and inspect generated runtime env
- Expected Result: shared singleton markers are present and start flags for shared services are false
- Forbidden Result: dev start launches duplicate recall/RAG, SearXNG, Firecrawl, Google MCP, or MS365 MCP by default
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed

## SDR-003: Activate Current Uses Runtime Checkout

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: CLI, helper config
- Preconditions: developer checkout is valid
- Steps: run `bin/viventium dev-runtime activate-current --validate --allow-protected-folder`
- Expected Result: existing runtime-checkout state is updated; no code is copied into an install path
- Forbidden Result: parallel active checkout state, physical source copy, or unreviewed nested repo pin change
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - structurally covered; live helper activation not run

## SDR-004: Upgrade Check Is Side-Effect-Free

- Requirement: `50_Stable_Dev_Runtime.md`
- Surfaces: CLI, helper
- Preconditions: git checkout with upstream
- Steps: run `bin/viventium upgrade --check --json`
- Expected Result: JSON reports update status and blockers without pull, compile, helper install, or restart
- Forbidden Result: working tree, generated runtime files, helper bundle, or running stack changes
- Evidence: dated report under `reports/`
- Last Run: 2026-05-14 local implementation QA - passed by CLI smoke and native helper modal QA
