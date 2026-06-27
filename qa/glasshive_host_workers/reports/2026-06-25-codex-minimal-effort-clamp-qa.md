# GlassHive Codex Minimal Effort Clamp QA - 2026-06-25

## Summary

- Result: PASS for the reported GlassHive failure mode.
- Build/source under test: active Viventium checkout with GlassHive runtime effort-clamp changes.
- Runtime/artifact under test: local GlassHive API/UI, host `codex-cli` worker runtime, config compiler output.
- Environment: local development runtime.
- Tester: Codex.
- Related change: default Codex effort allowlist excludes `minimal`; MCP schema and config compiler expose safer route-specific effort controls.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHHOST-008` | PASS | Focused and full impacted automated tests passed; two live synthetic host-worker runs completed. | Full doctor validation was blocked by local disk-space prerequisite. |
| `GHDR-005B` | PASS | Command evidence showed requested `minimal`, effective `medium`, and no provider rejection. | Cross-linked from effort-projection QA. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `GHHOST-UC-008` | Ask GlassHive to open a public website through a host Codex worker even when a low-effort override is supplied. | GlassHive API, host Codex worker, Google Chrome, Playwright-opened GlassHive worker UI. | PASS | Chrome active tab showed Yahoo Finance; GlassHive worker UI showed completed Yahoo Finance result. | Runtime log recorded effort clamp; DB showed two completed runs with no failure class; evidence JSON showed requested `minimal` and effective `medium`. | Full doctor validation blocked by local disk-space prerequisite. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: GlassHive host Codex worker effort projection.
- Requirement: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Use case: `GHHOST-UC-008`.
- QA case: `GHHOST-008`.
- Expected result: bad or stale host-model `effort=minimal` input clamps to a supported fallback before provider launch.
- Actual evidence: automated tests passed; live worker command evidence used `model_reasoning_effort="medium"`; Yahoo Finance opened in Chrome.
- Remaining gap or fix: free local disk space and rerun full doctor validation.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | `48_GlassHive_Workstation_Sandbox_Runtime.md`, `GHHOST-008`, `GHHOST-UC-008`, `GHDR-005B`. |
| Code owning path | Which code path owns the behavior? | `profile_runtime.py` clamps Codex effort; `mcp_server.py` describes effort contract; `config_compiler.py` renders route allowlist/fallback env. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | `01_Key_Principles.md`, `48_GlassHive_Workstation_Sandbox_Runtime.md`, and GlassHive runtime tests. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | GlassHive pytest suites and Viventium config compiler release tests. |
| Local/external prerequisite state | Which required local service, provider, Docker-backed sidecar, OAuth grant, API key, model, or hosted dependency was proven healthy or degraded? | GlassHive API/UI and LibreChat/playground health checks passed; local disk-space doctor gate was degraded. |
| Logs | Which sanitized logs confirm or contradict the result? | Runtime log recorded `Codex CLI reasoning effort clamped to provider-route fallback` for both live runs. |
| DB/state/persistence | Which sanitized state, DB count/hash, persisted message, config, or artifact confirms it? | DB showed both live runs completed with empty failure class; evidence JSON recorded requested `minimal`, effective `medium`. |
| Generated/shipped artifact | Which generated config, compiled bundle, prebuilt helper, or installed artifact was inspected when applicable? | Config compiler test proved first-class route effort fields render to runtime env. Runtime was restarted from active checkout. |
| Real user path | Which browser/computer, Telegram, voice, installer, CLI, MCP/tool, scheduler, or GlassHive path was used like a user? | GlassHive host worker opened Google Chrome to Yahoo Finance; Playwright opened GlassHive worker UI and confirmed completed result. |
| Visual/UX comparison | Does the visible UI/UX or delivered result match the expected behavior and supporting evidence? | Yes. Chrome showed Yahoo Finance and GlassHive UI reported the same completed result. |
| Not run / blocked | Which required surface was not run, and why is the result partial or blocked? | Full `dev-runtime --validate --restart` doctor gate was blocked by local disk-space prerequisite; restart and live QA still passed. |

## User-Grade Evidence

- Surface exercised: GlassHive host worker API/UI, Google Chrome, Playwright browser.
- Real user path: a synthetic host Codex worker was launched with requested `minimal` effort and asked to open Yahoo Finance in Chrome.
- Visible outcome: Chrome active tab was `https://finance.yahoo.com/` with Yahoo Finance title; GlassHive UI showed completed output.
- Expanded/detail state: GlassHive worker page showed latest output, recent run completed, recent event completed, runtime boundary `host` and `codex-cli`.
- Persistence/reload result: worker UI was opened after run completion and continued to show the completed result.
- Local/external prerequisite state: GlassHive API/UI, LibreChat API/frontend, and modern playground were healthy; disk-space doctor prerequisite was degraded.
- Evidence retrieval classification, if applicable: not applicable, no external evidence lookup was required.
- Fallback path, if applicable: unsupported requested effort clamped to configured fallback before provider launch.
- Backend/log/DB confirmation: DB showed both live runs completed with no failure class; evidence JSON showed requested `minimal`, effective `medium`; runtime log recorded the clamp.
- Final model/runtime wording check: worker final output accurately reported the Chrome/Yahoo Finance result and did not expose raw provider rejection text.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests were supporting evidence, not substitutes for visible UI, Chrome state, and GlassHive UI checks.

## Automated Evidence

```bash
cd viventium_v0_4/GlassHive/runtime_phase1
.venv/bin/python -m pytest tests/test_profile_runtime.py -q
.venv/bin/python -m pytest tests/test_mcp_server.py -q

cd /path/to/viventium
PYTHONPATH=. uv run --with pytest --with pyyaml pytest tests/release/test_config_compiler.py -q
```

Results:

- `tests/test_profile_runtime.py`: PASS
- `tests/test_mcp_server.py`: PASS
- `tests/release/test_config_compiler.py`: PASS, `112 passed`

## Findings

- Defects: original `minimal` provider rejection is fixed for the tested host Codex path.
- Regressions: none found in impacted automated suites.
- Flakes: none observed.
- Environment issues: full doctor validation blocked by local disk-space prerequisite.
- Residual risks: a future provider route with a narrower subset than `none,low,medium,high` should set the new first-class allowed-efforts config; runtime logs make fallback visible.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
