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
