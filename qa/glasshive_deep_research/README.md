# GlassHive Deep Research And Document Generation QA

## Scope

This folder owns public-safe QA for GlassHive workers used as universal deep-research and
document-generation workers. It covers Codex CLI, Claude Code, and supported workstation/host modes
without overfitting runtime behavior to one benchmark, one industry, one prompt, one provider, or one
artifact format.

## Owning Requirements

- [`docs/requirements_and_learnings/01_Key_Principles.md`](../../docs/requirements_and_learnings/01_Key_Principles.md)
- [`docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`](../../docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md)
- [`docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`](../../docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md)

## Quality Bar

- Workers receive the user's real request, explicit constraints, files, and capability context.
- Runtime code stays universal: no benchmark-specific, prompt-specific, provider-label, or
  domain-specific routing logic.
- Each run leaves `glasshive-run/constraint-ledger.json` and `glasshive-run/evidence.json`.
- Evidence JSON agrees with manual artifact inspection, logs, and final user-visible wording.
- Generated files open/render/download through the real user path when a visible surface is in scope.
- Codex and Claude parity is evaluated by outcome quality plus performance, not identical wording.

## Evidence Locations

- Public-safe reports: `qa/glasshive_deep_research/reports/`
- Private raw prompts, client context, screenshots, logs, or benchmark artifacts: outside this public
  repo in the approved private QA location.

## Local Deterministic Browser Harness

Run the provider-free browser QA harness from the repo root:

```bash
node qa/glasshive_deep_research/scripts/local_browser_user_grade_qa.cjs
```

An alternate Playwright-CLI harness exercises the same local fixture through the bundled Codex
Playwright wrapper:

```bash
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python qa/glasshive_deep_research/scripts/local_user_grade_browser_qa.py
```

The harness starts `local_user_grade_fixture.py`, drives Chromium with Playwright for Node, opens the
project/workspace/artifact surfaces, verifies tokenless short refs and redaction basics, downloads and
structurally checks the synthetic artifact matrix, refreshes `/w/{ref}`, and exercises an active-run
pause/resume/interrupt path. Local screenshots, downloads, and JSON evidence are written under
`output/playwright/glasshive-deep-research/`.

## Live Provider Browser Harness

When local provider credentials are available, run the public-safe live provider browser bridge:

```bash
WPR_CODEX_CLI_XHIGH_ROUTE_PROVEN=1 viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python qa/glasshive_deep_research/scripts/live_provider_browser_wait_continue_qa.py --profile codex-cli --execution-mode host --effort xhigh
```

This starts a temporary local GlassHive API/UI, launches a real provider-backed worker, observes the
active run from a browser-visible worker page, opens the generated artifact preview, follows the
tokenless workspace short ref, continues the same workspace, and writes ignored evidence under
`output/playwright/glasshive-live-provider-browser-wait-continue/`.
