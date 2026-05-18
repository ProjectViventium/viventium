<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
# Stable Dev Runtime Local QA - 2026-05-14

## Scope

Local implementation QA for stable developer runtime commands, compiler behavior, helper update
state, local runtime activation, and release-test coverage.

## Evidence

- `python3 -m py_compile` passed for the new runtime/workflow/compiler scripts.
- `uv run --with pytest --with pyyaml pytest tests/release/test_stable_dev_runtime_workflows.py -q`
  passed: 19 tests.
- `PYTHONPATH=. uv run --with pytest --with pyyaml pytest tests/release/ -q` passed: 535
  tests, 1 skipped.
- `swift build` passed for the macOS helper package.
- `test_prebuilt_helper_fallback_matches_current_sources` passed as part of the release suite,
  proving `prebuilt/source.sha256` matches the helper package sources.
- `scripts/viventium/build_macos_helper_fallback.sh` rebuilt the helper fallback artifact and source
  hash.
- `bin/viventium upgrade --check --json` completed without installing an update and reported no
  component-lock drift.
- The installed helper opened Advanced > Check for Updates and rendered the blocked update modal
  for the current dirty QA checkout without pulling, installing, or restarting.
- `git diff --check` passed.
- A local `bin/viventium dev-env create` smoke created a dev env with offset app-facing ports and
  the default shared singleton service list.
- `bin/viventium dev-runtime activate-current --validate --restart --allow-protected-folder
  --allow-dirty-local-testing` re-bound the helper to the active checkout, compiled config, ran
  doctor, refreshed the helper, restarted the local stack, and returned to healthy status.
- `bin/viventium install-helper` refreshed the installed helper from the shipped prebuilt. The
  installed helper is ad-hoc signed locally, so its executable hash differs after signing; installed
  strings were checked for the new Advanced workflow labels.
- Generated App Support `librechat.yaml` was parsed after activation; it loaded as YAML and included
  the expected runtime sections and MCP server entries.
- Native helper menu QA showed **Check for Updates...** under **Advanced**, with only Open,
  Start/Stop, status, Advanced, and Quit at top level.
- Native helper Advanced submenu QA enumerated Check for Updates, Create Backup Snapshot, Heal
  Viventium, Report a Bug, Request a Feature, Approve Build or Fix, Cancel Active Workflow, Open
  Work Artifacts, transcript ingest, Start at Login, and Show Status Bar Icon.
- Playwright opened the local web surface at `http://localhost:3190`, created a synthetic local QA
  account, signed in, captured the authenticated Viventium chat UI, and confirmed the signed-in UI
  persisted after browser refresh.
- `bin/viventium password-reset-link <synthetic-qa-email>` completed after the local password-reset
  script was corrected to close its Mongo connection before exit.
- The nested LibreChat fix was committed locally and `components.lock.json` was updated to the
  fixed nested commit so clean installs using the lock receive the same behavior.

## Results

- SDR-001: Passed by release test and CLI smoke. Dev envs offset app-facing ports while preserving
  singleton service ports.
- SDR-002: Passed by compiler test. Shared singleton service flags prevent duplicate recall/RAG,
  SearXNG, Firecrawl, Google Workspace MCP, and Microsoft 365 MCP starts by default.
- SDR-003: Passed. Live activation used the existing runtime-checkout state, did not copy code into
  install paths, and restarted the installed local runtime from the active checkout.
- SDR-004: Passed by upgrade-check smoke and native helper modal QA. The command used `--no-fetch`
  in unit coverage and the public `upgrade --check --json` path locally.
- SDR-005: Passed. The installed helper rendered the blocked update state with a dirty-checkout
  reason and did not mutate the runtime.

## Remaining Manual QA

Testing an actual **Install Update** confirmation was intentionally not run because the checkout has
local QA edits. The safe check path reports that blocker instead of mutating the runtime.
