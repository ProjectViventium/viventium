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
- Source prompts: `viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/`
- Live sync helper: `viventium_v0_4/LibreChat/scripts/viventium-sync-agents.js`
- Eval harness: `qa/prompt-architecture/evals/run-exact-model-evals.cjs`

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

## Latest Status

Implementation and follow-up browser QA are recorded in
`qa/prompt-workbench/reports/2026-05-15-implementation-qa.md` and
`qa/prompt-workbench/reports/2026-05-16-usability-eval-flow-qa.md`.

Current workbench checks pass, including browser prompt edit/draft/apply/revert, focused History
view, linked eval/QA visibility, eval case draft/discard, dry-run-only live sync review, pending
draft blocks for eval/push, stale/already-applied draft resolution, no-op eval draft prevention,
stale dry-run token protection, automatic light/dark mode, real Chrome eval-case create/discard
input behavior, and Prompt Traces copy that explains the former "frames" surface. The broader
prompt-registry regression bundle has previously shown
protected-source drift in the nested LibreChat prompt bundle; see the report before claiming the
full prompt source tree is clean.

The 2026-05-16 pass intentionally did not run reviewed live sync or live exact-model evals. It
verified the safe no-live preview and dry-run paths plus the exact-model adapter command shape.
