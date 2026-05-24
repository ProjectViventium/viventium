# GlassHive Standard QA

## Scope

- Owning requirements doc: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`
- Runtime/code owners: `viventium_v0_4/GlassHive/runtime_phase1`,
  `viventium_v0_4/GlassHive/frontends/glass-drive-ui`, config compiler, and LibreChat MCP config.
- User-visible surfaces: direct GlassHive UI, direct GlassHive MCP, LibreChat config-only MCP, worker
  watch/takeover, artifacts/downloads, workspace desktop/browser, scheduling handoff, and enterprise
  auth gates.
- Out of scope: deploying or mutating cloud resources without explicit approval and a local backup.

## Quality Bar

- Primary user outcome: authenticated users can create, resume, steer, stop, watch, and use only
  their own workspaces and artifacts through GlassHive, LibreChat MCP, and direct MCP paths.
- Speed/latency expectation: dispatch is non-blocking; workspace spawn/resume is measured; idle
  compute is released automatically when configured.
- Persistence/reload expectation: named workspaces/workers preserve files and browser state across
  pause, idle termination, restart, and resume.
- Failure behavior: missing auth, wrong tenant/user, wrong token, missing provider keys, blocked web
  search, and unavailable worker profiles fail closed with clear user-facing copy.
- Public/private boundary: use synthetic data, placeholder accounts, public-safe files, and sanitized
  logs/reports only.

## Standard Trigger

When the user says "GlassHive Standard QA", run the procedure in `cases.md` across all required
surfaces unless an item is impossible in the current environment. Impossible items stay visible as
`BLOCKED` or `PARTIAL`; they do not disappear into a summary.

Common operator/user variants such as "run GlassHive QA", "run the standard QA suite", and "do the
GlassHive Standard QA" mean this same procedure. This is an agent/operator instruction, not a
runtime keyword-matching rule.

The raw original request included machine-local skill paths and approved-resource names. This
public-safe copy intentionally replaces those private values with placeholders while preserving the
test semantics and the wildcard wording:

```text
I and you should have these tests / QA sets that you can run and evaluate to ensure its always working:

repeat all via direct glasshive UI, Librechat, direct MCP usage
Cases:
1. Web Search: Quick easy test something about latest news "Who won the game between... x vs y on thursday"
2. File Upload / Download: Attach a file like a PDF or a Excel workbook, tastefully redesign this into a PowerPoint or Html file. (must successfully take your basic file upload and prompt, autonomously do the magic on its own, and delivers files where you will be able to like a user download, view, and validate these files and identify + report and gaps or issues or misalignments. as per our documentations the bootstraps agents.md that gets supplied and used in the workspace has instructions that gets the AI worker to check its own delivery to ensure full alignments and achievement of success critreia and such. so we do not wanna modify this agents.md spelling out all the cases (that is illegal overfitting), rather we want to give it a universal harness approach to make it fully independent and reliable
3. Scheduling: in 20 minutes (or on mondays for example) ...  do "xyz..." where xyz could be any prompt or workflow... (in this case, this is just about glasshive and must work for cases where its raw original Librechat or MCP being used - hence no scheduling cortex)
4. Persistance: in an existing workspace, name it and its worker as you'd like user friendly and pin it as favorite. have the AI in librechat run "Tell my worker JohnDoe... (example worker name I made up), to use my Marketing sandbox (example workspace name) to do XYZ" where you need to test saving files and browser customizations manually as a user via browser use and we expect turning off and on glasshive or its workers and everything, it would be possible to bring them back, efficiently and immediately resume them, and leverage the saved state and continue using those. (Cost = Efficiency = Idle = suspect to avoid accumulating cost... this is intended to be used by hundreds of enterprise users each spawning many workers, so we should have env vars and default vars to configure how many workers can be running simulatenosuly and how many workpaces)
5. Wild card (ensuring cases are covered based on general and universal compatibility and worker's own intelligence and no overfitting / no hardcoded crap) - search web, for usecases that you can do a quick version of but encompasses the same complexity of what people are using openclaw, codex, agents, codeinterpreter as of most latest and define 3 tests and run them via glasshive

beyond this, access, security, efficiency, performance, must be assessed, checked, and addressed to be aligned with requirements you shal find and outline in our glasshive docs.

the results and docs explaining expectations and requirements must be double checked by [Claude review skill] to ensure alignment, no gaps, no issues.

while doing each
closely observe, logs, db, code
```

## Required Suites

| Suite | Command or Manual Path | Required When | Last Run |
| --- | --- | --- | --- |
| GlassHive API/MCP/runtime automated | `uv run pytest tests/test_api.py tests/test_mcp_server.py tests/test_bootstrap.py tests/test_profile_runtime.py -q` from `viventium_v0_4/GlassHive/runtime_phase1` | Every runtime/security/lifecycle/MCP change | See latest GlassHive report. |
| GlassHive UI automated | `uv run pytest tests/test_server.py tests/test_prompt_template.py -q` from `viventium_v0_4/GlassHive/frontends/glass-drive-ui` | Every UI/auth proxy/launcher/watch change | See latest GlassHive report. |
| Config compiler | `python3 -m pytest tests/release/test_config_compiler.py -q` | Every config/compiler/deployment-mode change | See latest compiler report. |
| Direct GlassHive UI QA | Playwright or equivalent real browser against the local enterprise entrypoint | Every user-visible GlassHive change | See reports. |
| Direct MCP QA | Direct MCP client/tool calls before LibreChat when MCP behavior is in scope | Every MCP/tool-schema/worker-delegation change | See reports. |
| LibreChat MCP QA | LibreChat browser flow with config-only MCP integration | Every enterprise integration or end-to-end worker change | See reports. |
| Security/cost/performance QA | Synthetic two-user auth probes, signed-link probes, idle reaper, quotas, spawn/resume timing | Every enterprise/security/lifecycle change | See reports. |
| Claude/ClaudeViv review | Review-only prompt with sanitized evidence | Every non-trivial GlassHive architecture, enterprise, security, or release-readiness claim | See reports. |

## Current Status

- Last named QA: `2026-05-23`; see
  `qa/glasshive_standard_qa/reports/2026-05-23-standard-qa-current-run.md`.
- Current result: `PASS` for locally controllable enterprise GlassHive paths exercised in the
  current run; `PARTIAL` for the full every-profile/every-surface release matrix.
- Strongly covered: automated runtime/API/MCP/UI/config/LibreChat callback tests, direct MCP before
  LibreChat, direct UI upload/download and scheduling, LibreChat current-fact, upload/download,
  callback download links, raw GlassHive scheduling, local enterprise auth/scoping probes, idle
  reaper resume behavior, Workspaces hive, watch/takeover layout, and ClaudeViv review-only
  reconciliation.
- Known gaps before release-complete status: direct UI current-fact parity, the full LibreChat
  natural-language named/favorite persistence flow, three wildcard tasks across direct UI, direct
  MCP, and LibreChat in one fresh pass, provider-profile coverage for blocked credentials, and any
  cloud-only Azure validation after explicit approval.
- External blockers are recorded as `BLOCKED`, not hidden as passes: the Claude profile needs usable
  provider credit or equivalent routing, Portkey live verification needs a local Portkey key, and no
  Azure resource mutation was performed in the local-only run.
- Next required hardening: turn every escaped GlassHive regression into a durable synthetic case in
  `cases.md`, then add deterministic automation where the behavior can be checked without external
  provider state.
