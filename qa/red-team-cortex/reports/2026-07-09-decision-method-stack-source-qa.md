# Red Team Decision-Method Stack QA
<!-- qa-evidence-exempt: Historical local QA format retained without retroactively inventing evidence; current release acceptance is recorded separately. -->

- Date: 2026-07-09
- Feature: Red Team Cortex decision-method activation and execution
- Requirement: `REDTEAM-004`, `ACT-35`, `docs/requirements_and_learnings/29_Red_Team_Cortex.md`
- Result: PARTIAL

## What Changed

- Red Team activation now covers explicit Socratic/no-bullshit/premortem/inversion/assumption-mapping/reference-class/Bayesian/kill-criteria/stage-gate/stakeholder/FMEA/OODA asks when attached to a concrete plan, claim, decision, or viability question.
- Red Team execution now carries a method-lens output contract and a decision-quality stack instead of only claim/evidence/verdict/action.
- Red Team source and runtime normalization now preserve `web_search` when enabled and OpenAI `reasoning_effort: xhigh`.

## Automated Evidence

- PASS: `test_red_team_activation_prompt_covers_explicit_pressure_test_requests`
- PASS: `test_red_team_execution_uses_decision_quality_stack_and_xhigh_openai_bag`
- PASS: `test_red_team_ships_with_web_search_and_openai_reasoning_effort`
- PASS: `test_public_prompt_registry_validates_and_compiles`
- PASS: `test_source_yaml_prompt_refs_resolve_to_runtime_strings`
- PASS: `test_js_sync_resolves_full_source_agent_yaml_prompt_refs`
- PASS: `test_background_agent_execution_models_stay_within_launch_ready_families`
- PASS: `test_no_runtime_nlu.py`
- PASS: nested LibreChat `viventium-agent-runtime-models.test.js`

## Broader Suite Findings

The broader Python bundle was run and produced 67 passes / 4 failures. The failures were existing
contract drift outside this Red Team change:

- GlassHive prompt-registry helper extraction missing an instruction helper in the test namespace.
- Confirmation/support activation prompts drifted from current governance expectations.
- Confirmation Bias fallback provider expectation differs from live source.
- Activation decision-subject raw source expected `promptRef`, while current source is already resolved inline.

These are not counted as Red Team decision-stack failures, but they remain open release-test drift.

## User-Grade Browser QA

- Playwright CLI opened the local web UI and observed the login screen, proving the browser surface was reachable but unauthenticated.
- The project browser harness was run with a synthetic Red Team/Confirmation Bias prompt.
- BLOCKED: the default synthetic QA user fixture was not present, so no authenticated conversation could be created.
- Evidence: `qa/red-team-cortex/reports/2026-07-09-decision-method-live-browser-qa.md`

## Live Config / Sync State

- PASS: the live user-level Red Team bundle was updated with a narrow sync from a temporary live-derived bundle, not a broad source push.
- PASS: dry-runs were completed for `activation-config-only`, `prompts-only`, `tools-only`, and `model-config-only`.
- PASS: before applying, a fresh live snapshot showed the fields that this push could touch were stable: main agent, Red Team standalone agent, and Red Team activation.
- PASS: applied `activation-config-only` for the Red Team activation prompt, `prompts-only` for the Red Team standalone instructions, and `tools-only` for Red Team tools.
- PASS: post-sync live pull verified only Red Team standalone `instructions/tools` and the Red Team activation config changed; no non-Red-Team background agents or non-cortex main-agent fields changed.
- PASS: live Red Team now includes the decision-quality stack, Socratic activation trigger, pure-education negative control, `web_search`, and OpenAI `reasoning_effort: xhigh`.
- NOTE: model config was already `xhigh` in live state, so no separate live model-config write was needed after verification.

## Second Opinion

Claude CLI review-only was attempted twice: once at max effort with explicit file context, then once
in safe mode with a shorter prompt. Both runs stalled without returning findings and were stopped.
No second-opinion findings are available for this run.

## Public-Safety Review

This report uses only synthetic prompt summaries, hashes, and public-safe placeholders. Raw live
account identifiers, local absolute paths, and private sync artifacts were not copied into the report.
