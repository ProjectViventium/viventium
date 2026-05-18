# Red Team Cortex QA Cases

## Case ID Convention

Use stable `REDTEAM-NNN` IDs for red team cortex cases.

## Case Catalog

| Case ID | Requirement | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- |
| `REDTEAM-001` | Explicit pressure-test activation | Web background cards, activation logs summary, final answer | test_background_agent_governance_contract.py plus browser harness | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `REDTEAM-002` | Non-owned emotional/simple turns stay quiet | Web/Telegram final answer and activation state | background-agent eval/browser harness | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `REDTEAM-003` | Final answer integration is evidence-bounded | Visible cards, expanded detail, final answer, persisted message | test_background_agent_browser_qa_harness.py | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |

## `REDTEAM-001` - Explicit pressure-test activation

- Requirement: Explicit pressure-test activation.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Ask for red-team/pressure-test/strongest counter-case on a synthetic plan; verify Red Team activates, visible card appears, and result identifies evidence gaps.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: test_background_agent_governance_contract.py plus browser harness.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `REDTEAM-002` - Non-owned emotional/simple turns stay quiet

- Requirement: Non-owned emotional/simple turns stay quiet.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Send emotional support or simple factual questions; verify Red Team does not activate and no duplicate correction appears.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: background-agent eval/browser harness.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `REDTEAM-003` - Final answer integration is evidence-bounded

- Requirement: Final answer integration is evidence-bounded.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. When Red Team produces a finding, verify main answer integrates the correction without claiming unsupported sources or that a hidden agent ran if no runtime card exists.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: test_background_agent_browser_qa_harness.py.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Red Team Cortex. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `REDTEAM-UC-001` | On Web background cards, activation logs summary, final answer, verify that explicit pressure-test activation. | owning requirement for `REDTEAM-001` / `REDTEAM-001` | Web background cards, activation logs summary, final answer | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to REDTEAM-001. | The visible result for REDTEAM-001 matches the documented requirement. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `REDTEAM-UC-002` | On Web/Telegram final answer and activation state, try non-owned emotional/simple turns stay quiet with missing setup, missing auth/config, empty state, or a degraded dependency. | owning requirement for `REDTEAM-002` / `REDTEAM-002` | Web/Telegram final answer and activation state | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to REDTEAM-002. | The user sees an honest setup, retry, or degraded-state result for REDTEAM-002; no fake success is accepted. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `REDTEAM-UC-003` | After final answer integration is evidence-bounded, refresh, restart, retry, or switch linked surfaces and verify persistence/parity. | owning requirement for `REDTEAM-003` / `REDTEAM-003` | Visible cards, expanded detail, final answer, persisted message | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to REDTEAM-003. | REDTEAM-003 remains correct after the persistence or parity step and final wording matches evidence. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
