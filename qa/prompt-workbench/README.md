# Prompt Workbench QA

## Scope

Prompt Workbench is the local developer/QA surface for understanding and reconciling Viventium
prompt state across source markdown/YAML, live LibreChat managed agents, and eval results tied to
prompt hashes.

Owning docs:

- `docs/requirements_and_learnings/49_Prompt_Architecture_and_Token_Efficiency.md`
- `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`
- `qa/prompt-architecture/README.md`

## Surfaces

- Local API: `viventium_v0_4/prompt-workbench/backend/prompt_workbench/`
- Local UI: `viventium_v0_4/prompt-workbench/src/`
- Local lifecycle CLI: `bin/viventium prompt-workbench`
- macOS helper submenu: `Advanced > Prompt Workbench`
- LibreChat entry point: account dropdown `Connected Accounts` section > `Prompt Workbench`
- Source prompts: `viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/`
- Live sync helper: `viventium_v0_4/LibreChat/scripts/viventium-sync-agents.js`
- Eval harness: `qa/prompt-architecture/evals/run-exact-model-evals.cjs`
- Scheduled prompts: Scheduling Cortex private SQLite tables plus Prompt Workbench Schedules tab
- GlassHive execution: direct host `codex-cli` worker dispatch for Workbench scheduled prompts

## Quality Bar

- The workbench must reuse the existing prompt registry, agent sync helper, git history, and eval
  harness rather than creating a separate prompt database.
- Source edits must create reviewed drafts against source files only.
- Live pushes must be dry-run first and require a matching reviewed token.
- Public markdown imports must pass the existing prompt safety scan.
- Conflicts must be visible and block automatic overwrite.
- Browser QA must prove the dashboard, prompt detail, drift board, eval panel, and Prompt Traces
  panel are visible and usable.
- Evals must default to a human-readable linked-case view, distinguish no-live selection previews
  from live exact-model performance runs, and support reviewed create/edit drafts without broad
  formatting churn.
- Helper/CLI QA must prove `Open` starts then opens the workbench, and `Stop` stops only the
  workbench web app without changing the main Viventium runtime state.
- LibreChat account-menu QA must prove the admin/operator Prompt Workbench entry under Connected
  Accounts starts or reuses the managed local workbench and opens the returned same-host loopback URL
  without changing cloud state; non-admin users must not get launcher access.
- Scheduled prompt QA must prove admin auth, Prompt Flow object visibility, Drafts-tab scheduled
  prompt preview, variable wrapping/preview, enable/disable persistence, explicit GlassHive versus
  Viventium execution-route display, direct GlassHive dispatch, signed callback/run history, no raw
  DB credentials, governed memory writeback behavior, and topbar sync color states.

## Latest Status

The retained implementation and browser reports are
[`2026-05-15-implementation-qa.md`](reports/2026-05-15-implementation-qa.md) and
[`2026-05-16-usability-eval-flow-qa.md`](reports/2026-05-16-usability-eval-flow-qa.md). Five reports
formerly cited for the 2026-05-22 rendered-flow, scheduling-config, scheduled-GlassHive,
Connected-Accounts, and sidebar/diff/sidecar claims are not present in this repository. Those
claims are historical context only and are not current release evidence.

Current truth lives in [`cases.md`](cases.md): `PW-046` is installed-pass evidence, `PW-047` is
`NOT RUN / PRE-GATE`, `PW-048` is `PARTIAL`, `PW-049` is a pre-gate pass that is not release
readiness, and `PW-050` is `PARTIAL` with its
[`2026-08-28` report](reports/2026-08-28-nonterminal-view-steer-receipt-truth.md). Do not claim the
full prompt source tree or Workbench release gate is clean until every current case has valid,
linked evidence.

The 2026-05-16 pass intentionally did not run reviewed live sync or live exact-model evals. It
verified the safe no-live preview and dry-run paths plus the exact-model adapter command shape.
The 2026-08-28 retry4 regression now has source-level guards for canonical nonterminal
`View / Steer <task>` labels and per-execution hashed receipt evidence. Installed compilation,
activation, and one exact-model rerun remain pending; see `PW-050`.
