# MCP Tooling QA Cases

## Case ID Convention

Use stable `MCP-NNN` IDs for mcp tooling cases.

## Case Catalog

| Case ID | Requirement | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- |
| `MCP-001` | Server/tool instructions reach the model | Prompt assembly, MCP metadata, model-visible tool context | test_prompt_registry.py and MCP service tests | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `MCP-002` | OAuth unavailable or stale grant is honest | Connected Accounts, MCP auth state, final model response | test_ms365_launcher_contract.py plus browser QA when visible | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |
| `MCP-003` | Tool result grounding | MCP tool call, chat answer, logs/state summary | feature-specific MCP harness | NOT YET RUN (cataloged 2026-05-17; run when feature changes) |

## `MCP-001` - Server/tool instructions reach the model

- Requirement: Server/tool instructions reach the model.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Verify MCP server instructions and tool descriptions are available for startup and non-startup MCPs without injecting booleans or raw implementation noise.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: test_prompt_registry.py and MCP service tests.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `MCP-002` - OAuth unavailable or stale grant is honest

- Requirement: OAuth unavailable or stale grant is honest.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Use synthetic missing/stale OAuth state; verify the tool response and final wording ask for reconnect/auth instead of pretending access.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: test_ms365_launcher_contract.py plus browser QA when visible.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `MCP-003` - Tool result grounding

- Requirement: Tool result grounding.
- Risk covered: Viventium claims the behavior works without proving the real user-visible surface and supporting state.
- Preconditions: local runtime or focused harness is available with synthetic public-safe data.
- Steps:
  1. Run a synthetic MCP tool result and verify the final answer cites only verified tool data, omits unsupported live facts, and persists the result state.
  2. Compare visible result with source/config, logs or persisted state summary, and the owning requirement doc.
  3. Save a public-safe dated report under `reports/` using the standard run-report template.
- Expected result: visible behavior, supporting evidence, and documentation agree.
- Forbidden result: mocks, backend logs, source inspection, or model output are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, state/log summary, and public-safety review.
- Automation: feature-specific MCP harness.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Mcp Tooling. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `MCP-UC-001` | On Prompt assembly, MCP metadata, model-visible tool context, verify that server/tool instructions reach the model. | owning requirement for `MCP-001` / `MCP-001` | Prompt assembly, MCP metadata, model-visible tool context | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MCP-001. | The visible result for MCP-001 matches the documented requirement. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `MCP-UC-002` | On Connected Accounts, MCP auth state, final model response, try oAuth unavailable or stale grant is honest with missing setup, missing auth/config, empty state, or a degraded dependency. | owning requirement for `MCP-002` / `MCP-002` | Connected Accounts, MCP auth state, final model response | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MCP-002. | The user sees an honest setup, retry, or degraded-state result for MCP-002; no fake success is accepted. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `MCP-UC-003` | After tool result grounding, refresh, restart, retry, or switch linked surfaces and verify persistence/parity. | owning requirement for `MCP-003` / `MCP-003` | MCP tool call, chat answer, logs/state summary | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MCP-003. | MCP-003 remains correct after the persistence or parity step and final wording matches evidence. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
