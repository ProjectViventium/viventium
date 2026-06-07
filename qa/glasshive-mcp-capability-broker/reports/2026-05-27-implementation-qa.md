<!-- qa-evidence-exempt: legacy implementation report from the initial broker pass; superseded by the standard connected-account isolation run report for the latest QA rerun. -->

# GlassHive MCP Capability Broker Implementation QA - 2026-05-27

## Scope

Implemented and tested the first brokered MCP projection path for GlassHive workers:

- LibreChat marks reviewed source-of-truth MCP servers as eligible for autonomous GlassHive use through server-managed `viventiumGlassHive` policy.
- LibreChat injects a single `glasshive-user-capabilities` broker MCP into GlassHive bootstrap bundles for workspace launch/run/schedule paths.
- The broker route lists and invokes currently connected LibreChat MCP tools as the authenticated user without exposing provider tokens to the worker.
- GlassHive accepts per-run bootstrap bundles and materializes host-native `.mcp.json`, Claude settings, and Codex config files with owner-only permissions.

## Automated Evidence

PASS:

- `npm --prefix viventium_v0_4/LibreChat/api test -- --runInBand server/services/viventium/__tests__/GlassHiveCapabilityBroker.spec.js server/routes/viventium/__tests__/glasshiveCapabilities.spec.js server/services/MCP.spec.js server/routes/viventium/__tests__/glasshive.spec.js`
  - 4 suites, 89 tests passed.
- `npm --prefix viventium_v0_4/LibreChat/packages/data-provider run test:ci -- --runInBand src/mcp.spec.ts src/schemas.spec.ts`
  - 2 suites, 77 tests passed.
- `npm --prefix viventium_v0_4/LibreChat/packages/data-provider run build`
  - build completed.
- `cd viventium_v0_4/GlassHive && runtime_phase1/.venv/bin/python -m pytest runtime_phase1/tests/test_mcp_server.py runtime_phase1/tests/test_profile_runtime.py::test_host_runtime_materializes_project_mcp_bootstrap_with_owner_only_files runtime_phase1/tests/test_docker_sandbox.py::test_seed_bootstrap_writes_project_scope_files -q`
  - passed.
- `viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python -m pytest tests/release/test_config_compiler.py tests/release/test_prompt_registry.py tests/release/test_productivity_activation_source_of_truth.py -q`
  - 145 tests passed.
- `node -c` on the new/modified LibreChat broker route and service files.
  - passed.
- `runtime_phase1/.venv/bin/python -m py_compile` on the modified GlassHive runtime files.
  - passed.

Notes:

- `python3 -m pytest ...` with the system Python was not usable because that interpreter did not have `pytest`; the same release subset passed under the project/runtime venv.
- The release prompt-registry subset exposed a pre-existing drift where the GlassHive FastMCP instruction builder referenced dynamic worker capability context that the registry prompt could not represent. The fix adds a runtime placeholder, keeps the registry deterministic, and preserves deployment-specific capability injection.

## Browser / Runtime Evidence

PASS:

- `bin/viventium dev-runtime status`
  - active runtime checkout, helper checkout, live stack owner, and command checkout all point at the same public checkout.
- Playwright CLI opened `http://localhost:3180/api/viventium/glasshive/capabilities/health` in a real browser.
  - visible body: `{"status":"ok","service":"glasshive-capability-broker"}`
  - screenshot artifact: `output/playwright/glasshive-capability-broker-health.png`
- `curl -i http://localhost:3180/api/viventium/glasshive/capabilities/health`
  - `HTTP/1.1 200 OK`
  - body: `{"status":"ok","service":"glasshive-capability-broker"}`
- Runtime log tail showed no broker-route errors. It did show transient Vite pre-transform errors while `librechat-data-provider` was being cleaned/rebuilt; the package build completed afterward and the expected dist artifact is present.
- GlassHive runtime DB inspection showed the expected runtime tables and current counts:
  - `workers=11`
  - `runs=12`
  - `broker_bootstrap_workers=0`

The `broker_bootstrap_workers=0` result is expected for this local state because no authenticated end-user launch was performed after enabling the broker.

## Security Evidence

PASS / PARTIAL:

- Broker grants are HMAC-signed, short-lived, user-bound, audience-scoped, and replay-checked by invocation id.
- Write-capable broker calls cannot be authorized by a worker-set confirmation flag; they require a separate signed host confirmation token bound to the grant, server, tool, invocation id, and argument hash.
- Provider secrets are not copied into the worker bootstrap; workers receive only the broker MCP endpoint and bearer grant.
- Server-managed `viventiumGlassHive` policy is omitted from user-authored MCP config input.
- User DB MCP configs are not projected unless an explicit reviewed policy allows them.
- Confirmed write calls require an invocation id, and broker-only intent metadata is stripped before the provider MCP call.
- Reviewed Google/MS365 projection defaults to content-read intent rather than metadata-only trust; structured MCP destructive/non-read-only annotations escalate tools into the write-confirmation path.
- Scheduled broker grants are extended for delayed runs within a conservative cap; far-future or recurring connected-account work still needs a grant-renewal design before background-agent retirement.
- Host and sandbox bootstrap materialization write broker-bearing `.mcp.json`, Claude settings, and Codex config files with owner-only permissions.
- Targeted changed-file scan found only synthetic test secrets and existing schema field names, not real bearer tokens, local usernames, or provider credentials.

## Case Results

- GH-MCP-BROKER-001: PARTIAL. Bootstrap injection and workspace file materialization are tested, but no authenticated end-user launch was run.
- GH-MCP-BROKER-002: PARTIAL. Grants and policy filtering are covered; no two-live-user browser test was run.
- GH-MCP-BROKER-003: PARTIAL. Broker resolves current LibreChat MCP auth on list/invoke; no real Google/MS365 revoke-refresh cycle was run.
- GH-MCP-BROKER-004: PASS. Read/write policy gates and signed host write-confirmation behavior are covered.
- GH-MCP-BROKER-005: PASS. Run/schedule propagation and host materialization are covered.
- GH-MCP-BROKER-006: PARTIAL. Secret projection is covered by tests/scan/log/DB inspection; no real connected-account workspace was inspected.
- GH-MCP-BROKER-007: BLOCKED by design. Background agent retirement remains gated on shadow parity, OAuth, isolation, and security evidence.

## Remaining Gaps Before Retiring Productivity Background Agents

- Run an authenticated LibreChat-to-GlassHive launch with real or synthetic connected Google/MS365 accounts and inspect the worker-visible `glasshive-user-capabilities` MCP.
- Run a two-user isolation test in the browser with separate accounts.
- Run OAuth revoke/refresh behavior against the real configured Google Workspace and Microsoft 365 MCP services.
- Classify provider tools into metadata/content/write policy tiers before enabling broad content access.
- Add an end-user UI flow for issuing signed write-confirmation tokens when an actual human approves a mutation.
- Run shadow-mode paired evals before disconnecting Deep Research, Google, or MS365 background agents.

## Claude Review Follow-Up

Claude review-only pass completed on max effort. Findings addressed in this implementation pass:

- Worker self-confirmation for writes was unsafe. Fixed by requiring a separate signed host write-confirmation token bound to grant/tool/invocation/argument hash.
- Sandbox `.mcp.json` and config files could have default-readable permissions. Fixed owner-only modes for sandbox and host materialization.
- Claude project MCP shape needed the `mcpServers` envelope and HTTP `type`. Fixed for generated broker config and both materialization paths.
- Scheduled grants could expire before delayed runs. Improved with schedule-aware grant TTL and documented the remaining far-future/renewal gap.
- Broker HMAC secret reused callback secret. Fixed by adding a dedicated config-compiler generated broker secret and removing callback-secret fallback.

Findings intentionally left as gated follow-up before background-agent retirement:

- Real browser two-user isolation and real OAuth revoke/refresh loops.
- Multi-process replay-store hardening.
- Rate limiting and richer downstream error classes on the broker route.
- Full host-app-agnostic broker contract packaging beyond the LibreChat implementation.
