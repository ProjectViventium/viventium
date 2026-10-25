# GlassHive Standard QA

This is a retained GlassHive QA reference. For the current managed xPerfect component, use the
[owning capability and QA links](../../docs/requirements_and_learnings/capabilities/glasshive.md)
and the approved QA scope. Historical commands below are not the current component entrypoint.

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

Use the [case catalog](cases.md) as the public requirement: varied text or file inputs,
substantive native-worker research and analysis, and usable answers or artifacts. Exercise the
applicable success, failure and recovery paths within the agreed QA scope. Keep raw requests,
machine-specific setup and unsanitized evidence outside the public repository.

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

- Last named historical QA: `2026-05-23`. Its formerly cited dated report is not present in this
  repository, so the embedded summary below is context, not reproducible acceptance evidence.
- Current result: `PARTIAL` pending a current rerun and a valid linked report. Do not restate the
  historical local-path summary as a current `PASS`.
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
