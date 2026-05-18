# GlassHive Host Workers QA Cases

## Case ID Convention

Use stable `GHHOST-NNN` IDs for glasshive host workers cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `GHHOST-001` | Host-native workers act on the intended local/browser/file surface and report completion without exposing plumbing. | User-visible behavior matches source, docs, persisted state, and logs | GlassHive MCP/API, host worker, browser/desktop/file surfaces | `tests/release/test_stable_dev_runtime_workflows.py` plus user-grade QA when visible | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `GHHOST-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `GHHOST-003` | One-shot delegation preserves instruction precision without forced canned status | Assistant can self-check the delegated instruction and acknowledges in its own voice | MCP tool result, web chat, callback result | GlassHive `test_mcp_server.py` plus browser callback QA | PARTIAL (2026-05-18 MCP/runtime QA; browser callback run pending) |

## `GHHOST-001` - Core User Flow

- Requirement: Host-native workers act on the intended local/browser/file surface and report completion without exposing plumbing.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_stable_dev_runtime_workflows.py` plus any narrower feature tests discovered during implementation.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `GHHOST-002` - Public-Safe Evidence Record

- Requirement: public QA artifacts must be reproducible and free of secrets, personal data, local paths, raw IDs, and private screenshots.
- Risk covered: a useful local QA run cannot be safely reviewed or published.
- Preconditions: a dated QA report is created for this feature.
- Steps:
  1. Review the report and related diffs for local absolute paths, account identifiers, tokens, raw logs, raw DB rows, private chats, and screenshots with private content.
  2. Keep raw/private evidence outside the public repo and summarize only public-safe counts, statuses, hashes, and conclusions.
  3. Link the report back to this case and the owning requirement doc.
- Expected result: the public report proves the behavior without leaking private/local data.
- Forbidden result: a report includes private transcripts, account identifiers, raw runtime dumps, local home paths, tokens, or secret-bearing command lines.
- Evidence to capture: public-safety scan result and link to the sanitized report.
- Automation: public-safety pattern scan plus relevant release tests.
- Last run: NOT YET RUN (cataloged 2026-05-17; run on each new public report).

## `GHHOST-003` - Delegation Acknowledgement And Instruction Audit

- Requirement: `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`.
- Risk covered: the tool forces a prefabricated user-facing status line, or the assistant cannot
  inspect what it actually delegated and misses a wrong target/scope.
- Preconditions: callback context is available; synthetic public-safe task with a specific target,
  success condition, and short final-answer constraint.
- Steps:
  1. Call `worker_delegate_once` through the real chat/MCP path with a precise synthetic task.
  2. Verify the tool result contains `acknowledgement_guidance` rather than a literal `user_status`
     for dispatched work.
  3. Verify `delegation_audit.instruction_preview` preserves the target and success condition after
     redaction.
  4. When `expose_diagnostics=true`, verify `submitted_instruction` is present for explicit
     diagnostics; otherwise worker/run/project ids and full instruction remain hidden from routine
     user-facing output.
  5. Let the callback deliver the final result and verify it is self-contained enough to be useful
     without dumping raw worker logs.
- Expected result: the assistant writes its own acknowledgement, can self-check the delegated
  instruction, and receives a concise final callback.
- Forbidden result: the user sees a forced canned phrase; routine output exposes worker/run/project
  ids or raw instruction text; the final callback is only a naked list with no user-useful result or
  blocker.
- Evidence to capture: sanitized tool result keys, visible acknowledgement, callback text, log/state
  summary, and public-safety review.
- Automation: `viventium_v0_4/GlassHive/runtime_phase1/tests/test_mcp_server.py` plus browser
  callback QA when visible.
- Last run: PARTIAL (2026-05-18 MCP/runtime QA in
  `reports/2026-05-18-delegation-contract-runtime-qa.md`; browser callback run pending).

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Glasshive Host Workers. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `GHHOST-UC-001` | On GlassHive MCP/API, host worker, browser/desktop/file surfaces, verify that host-native workers act on the intended local/browser/file surface and report completion without exposing plumbing. | owning requirement for `GHHOST-001` / `GHHOST-001` | GlassHive MCP/API, host worker, browser/desktop/file surfaces | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHHOST-001. | User-visible behavior matches source, docs, persisted state, and logs | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `GHHOST-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `GHHOST-002` / `GHHOST-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHHOST-002. | The user sees an honest setup, retry, or degraded-state result for GHHOST-002; no fake success is accepted. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `GHHOST-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `GHHOST-002` / `GHHOST-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to GHHOST-002. | GHHOST-002 remains correct after the persistence or parity step and final wording matches evidence. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `GHHOST-UC-004` | Delegate a precise one-shot lookup/action and inspect the returned audit before the callback arrives. | `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md` / `GHHOST-003` | Web chat or MCP harness with `worker_delegate_once` | Tool result `acknowledgement_guidance`, sanitized `delegation_audit`, diagnostics-only `submitted_instruction`, callback final result, logs/state | Assistant writes its own short acknowledgement, does not quote a canned template, and the audit preserves the specific target/success condition enough to catch wrong-worker/wrong-scope dispatch. | PARTIAL (2026-05-18 MCP/runtime QA; browser callback run pending) |
