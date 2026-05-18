# GlassHive Delegation Contract QA Run - 2026-05-18

## Summary

- Result: PARTIAL pass for MCP/runtime contract, nested tests, parent release guard, and public-safety
  scan; visible callback delivery remains required before closing the browser/chat user case.
- Build/source under test: current local checkout plus nested GlassHive runtime.
- Runtime/artifact under test: `worker_delegate_once` MCP result contract and source-of-truth
  GlassHive worker instructions.
- Environment: local development runtime with synthetic public-safe checks.
- Tester: Codex.
- Related change: remove forced canned status and expose sanitized delegation audit.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHHOST-003` | PARTIAL PASS | Nested MCP test suite, parent release guard, ClaudeViv review follow-up | Browser callback path not run. |
| `GHHOST-UC-004` | PARTIAL PASS | Tool contract tests prove `acknowledgement_guidance`, `delegation_audit`, and diagnostics-only submitted instruction | Same-chat callback UX still needs a synthetic browser run. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `GHHOST-UC-004` | Delegate a precise one-shot lookup/action and inspect returned audit before callback arrives. | MCP harness and Playwright local surface smoke. | PARTIAL | Local Viventium surfaces rendered; no private task dispatched through chat. | Nested GlassHive tests and parent release guard prove no routine `user_status`, presence of `acknowledgement_guidance`, sanitized `delegation_audit`, and diagnostics-only `submitted_instruction`. | Browser chat callback delivery still needs a public-safe synthetic run. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: GlassHive one-shot delegation.
- Requirement: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Use case: `GHHOST-UC-004`.
- QA case: `GHHOST-003`.
- Expected result: assistant writes its own acknowledgement, can self-check the delegated instruction,
  and routine output avoids worker/run/project plumbing.
- Actual evidence: dispatched and blocked tool paths no longer return routine `user_status`; tool
  result includes acknowledgement guidance and sanitized audit; diagnostics gate full submitted
  instruction.
- Remaining gap or fix: browser chat callback delivery needs a synthetic public-safe run.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | GlassHive workstation runtime, `GHHOST-UC-004`, `GHHOST-003`. |
| Code owning path | Which code path owns the behavior? | Nested GlassHive `mcp_server.py`. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | GlassHive requirement doc, GlassHive QA README/cases, source-of-truth MCP prompt. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | GlassHive pytest suite and parent release QA contract. |
| Local/external prerequisite state | Which required local service, provider, Docker-backed sidecar, OAuth grant, API key, model, or hosted dependency was proven healthy or degraded? | Local runtime surfaces rendered; this MCP contract test does not require external provider auth. |
| Logs | Which sanitized logs confirm or contradict the result? | Test runner output showed nested and parent release suites passing. |
| DB/state/persistence | Which sanitized state, DB count/hash, persisted message, config, or artifact confirms it? | No DB mutation performed in this contract pass. |
| Generated/shipped artifact | Which generated config, compiled bundle, prebuilt helper, or installed artifact was inspected when applicable? | Prompt registry/source-of-truth checks passed for GlassHive MCP instructions. |
| Real user path | Which browser/computer, Telegram, voice, installer, CLI, MCP/tool, scheduler, or GlassHive path was used like a user? | MCP harness exercised `worker_delegate_once`; Playwright rendered local Viventium surfaces. |
| Visual/UX comparison | Does the visible UI/UX or delivered result match the expected behavior and supporting evidence? | Visible callback framing was not run; result remains partial. |
| Not run / blocked | Which required surface was not run, and why is the result partial or blocked? | Same-chat browser callback was not run to avoid dispatching a task through a private local account. |

## User-Grade Evidence

- Surface exercised: MCP harness and Playwright local web surfaces.
- Real user path: GlassHive tool contract exercised through MCP tests; local Viventium pages rendered.
- Visible outcome: local web surfaces rendered; no forced canned status reached a private chat.
- Expanded/detail state: diagnostics-only submitted instruction tested through explicit diagnostics
  flag.
- Persistence/reload result: not applicable for this partial contract pass.
- Local/external prerequisite state: no external provider dependency required for the MCP contract
  test; local runtime surfaces were reachable.
- Evidence retrieval classification, if applicable: not applicable to this GlassHive contract case.
- Fallback path, if applicable: not applicable; callback delivery remains the unrun user path.
- Backend/log/DB confirmation: nested GlassHive tests and parent release guard passed.
- Final model/runtime wording check: runtime returns guidance for assistant-owned acknowledgement,
  not a literal `user_status` phrase, on dispatched and blocked paths.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Automated Evidence

```bash
uv run --with pytest python -m pytest tests/test_mcp_server.py -q
uv run --with pytest --with pyyaml python -m pytest tests/release/test_qa_operating_contract.py tests/release/test_prompt_registry.py tests/release/test_config_compiler.py::test_source_of_truth_mcp_instructions_match_prompt_architecture_contract -q
```

## Findings

- Defects: blocked and dispatched paths now avoid routine forced `user_status`.
- Regressions: none found in targeted or parent release suites.
- Flakes: none observed.
- Environment issues: none for this contract pass.
- Residual risks: visible same-chat callback delivery must still be run with synthetic public-safe
  data.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
