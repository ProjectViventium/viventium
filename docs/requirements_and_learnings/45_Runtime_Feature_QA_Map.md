# 45. Runtime Feature QA Map

## Purpose

This document maps runtime feature areas to their owning public QA records so release work, install
verification, and regression checks stay grounded in one place.

## Core Runtime Surfaces

### Installer / Startup / Local Runtime

- `qa/installer-resilience/README.md`
- `qa/installer-piped-bootstrap/README.md`
- `qa/installer-wait-taglines/README.md`
- `qa/continuity-ops/README.md`
- `qa/remote-access/README.md`

Use these when changing:

- `install.sh`
- `bin/viventium`
- start/stop/status/doctor flows
- public remote-access posture surfaced by the local runtime
- first-account browser onboarding on clean installs
- clean-install helper/bootstrap behavior
- continuity-aware snapshot / restore / upgrade behavior
- helper manual backup affordances
- recall rebuild-marker behavior after restore or continuity repair

### Background Agents / Activation / Follow-Up

- `qa/background_agents/README.md`
- `qa/background_agents/01_catalog.md`
- `qa/background_agents/03_eval_prompt_bank.md`
- `qa/background_agents/05_coverage_matrix.md`
- `qa/background_agents/06_agent_signoff_manifest.md`
- `qa/background_agents/activation_reliability_2026-04-12.md`

Use these when changing:

- background-agent activation detection
- execution/follow-up routing
- activation provider/model selection
- user-scoped Google Workspace / Microsoft 365 auth behavior that can block a live tool run after
  activation already succeeded
- background-agent source-of-truth prompts or runtime model families

### Anthropic Runtime Compatibility

- `qa/background_agents/report.md`

Use this when changing:

- Anthropic initialization
- thinking / temperature compatibility
- shipped Anthropic background-agent defaults

## Minimum Release Check Expectation

When a change touches one of the runtime surfaces above:

1. update the owning doc if product truth changed
2. run the narrowest relevant automated tests
3. record or refresh public-safe QA evidence when behavior changed materially
4. verify at least one real user-visible surface where relevant
5. when the feature depends on connected accounts, prove both layers independently:
   - activation / routing health
   - user-scoped service auth health

## Notes

- This file is a map, not the deep source of truth for each feature.
- Do not duplicate detailed requirements here; extend the owning docs and QA artifacts instead.
