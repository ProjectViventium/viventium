# GlassHive MCP Capability Broker Connected-Account Isolation QA - 2026-05-27

## Summary

- Result: PASS/PARTIAL. The broker passed user-scope, grant-security, missing-auth, UI, and privacy-minimized provider-call checks. A full chat-to-GlassHive worker launch remains the last end-to-end cutover gate.
- Build/source under test: local public checkout with the GlassHive MCP capability broker changes.
- Runtime/artifact under test: local dev runtime after supported `dev-runtime activate-current --validate --restart`.
- Environment: local development runtime with synthetic QA account state and existing provider OAuth grants.
- Tester: Codex local QA.
- Related change: GlassHive MCP capability broker and zero-tool unavailable catalog hardening.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GH-MCP-BROKER-002` | PASS/PARTIAL | Live broker catalog matrix, DB token-count inspection, tampered/expired grants rejected | QA account saw MS365 tools only; primary account saw Google Workspace and MS365. |
| `GH-MCP-BROKER-003` | PASS/PARTIAL | Live discovery refreshed access-token rows through LibreChat token methods; unavailable Google for QA reported explicitly | Real upstream provider revoke/re-consent was not run. |
| `GH-MCP-BROKER-004` | PASS | Negative live calls returned `content_read_requires_explicit_intent` and `write_requires_host_confirmation` | Provider data was not fetched for blocked calls. |
| `GH-MCP-BROKER-006` | PASS/PARTIAL | Playwright health/UI screenshots, DB token counts, privacy-minimized provider calls | No real connected-account worker filesystem was launched in this pass. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `GH-MCP-BROKER-UC-002` | A QA user opens MCP settings and expects only their own connected MCPs. | Playwright browser against local LibreChat UI | PASS | MCP Settings showed MS365 connected for QA and Google Workspace not connected/connecting. | Mongo token counts showed QA-owned MS365 rows and no QA-owned Google rows. | None for this isolation check. |
| `GH-MCP-BROKER-UC-003` | A worker broker call lists current user capabilities. | Live broker MCP JSON-RPC endpoint | PASS | Broker health visible in browser; live catalog response summarized with counts only. | Primary catalog: Google Workspace and MS365 available. QA catalog: MS365 available; Google Workspace unavailable with zero tools. | None for list/discovery. |
| `GH-MCP-BROKER-UC-004` | A worker tries to overreach into another user's MCPs or mutate without approval. | Live broker MCP JSON-RPC endpoint | PASS | Tampered/expired grants returned unauthorized; blocked calls returned structured block reasons. | Negative-call responses were sanitized and no provider data was printed. | None for tested negative paths. |
| `GH-MCP-BROKER-UC-006` | A connected-account provider call succeeds without leaking private payloads into QA output. | Live broker MCP calls to Google Workspace and MS365 | PASS/PARTIAL | Provider calls returned `ok` with response lengths only. | Google synthetic search returned zero results in sanitized logs; MS365 call used `excludeResponse=true`. | Real chat-to-worker launch not run. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: GlassHive MCP capability broker for LibreChat-managed MCP access.
- Requirement: user-scoped, security-gated, provider-token-free MCP projection to GlassHive workers.
- Use case: a signed-in user configures Google Workspace/MS365 in LibreChat and expects GlassHive workers to use only that user's current MCP capabilities.
- QA case: `GH-MCP-BROKER-002`, `GH-MCP-BROKER-003`, `GH-MCP-BROKER-004`, `GH-MCP-BROKER-006`.
- Expected result: no raw token copying; current user capabilities are discovered live; missing auth fails closed; content reads and writes require the correct broker gates.
- Actual evidence: live two-account broker matrix, Playwright UI, DB token counts, rejected tampered/expired grants, blocked overreach/write calls, privacy-minimized provider calls.
- Remaining gap or fix: full authenticated LibreChat prompt that launches a real GlassHive worker and inspects the materialized broker MCP inside that worker workspace.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | `docs/requirements_and_learnings/07_MCPs.md`, `48_GlassHive_Workstation_Sandbox_Runtime.md`, and `GH-MCP-BROKER-002/003/004/006`. |
| Code owning path | Which code path owns the behavior? | LibreChat broker auth/policy/service/route files under `api/server/services/viventium/` and `api/server/routes/viventium/`; GlassHive bootstrap/materialization paths remain covered by prior tests. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | Key principles, MCP requirements, GlassHive runtime requirements, installer/config compiler requirements, and this QA folder. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Live shell probes, Playwright CLI, Mongo metadata queries, and Jest broker tests. |
| Local/external prerequisite state | Which required local service, provider, Docker-backed sidecar, OAuth grant, API key, model, or hosted dependency was proven healthy or degraded? | LibreChat API/UI, Google Workspace MCP, MS365 MCP, Mongo, and GlassHive runtime were reachable; QA Google capability was degraded/unavailable as expected. |
| Logs | Which sanitized logs confirm or contradict the result? | Google MCP log showed the synthetic Gmail query with zero messages and redacted token/user fields. |
| DB/state/persistence | Which sanitized state, DB count/hash, persisted message, config, or artifact confirms it? | Token metadata counts by user/type/identifier; no raw token values read or copied. |
| Generated/shipped artifact | Which generated config, compiled bundle, prebuilt helper, or installed artifact was inspected when applicable? | Generated runtime config included the dedicated broker secret after supported activation/restart. |
| Real user path | Which browser/computer, Telegram, voice, installer, CLI, MCP/tool, scheduler, or GlassHive path was used like a user? | Playwright browser opened broker health, authenticated local QA UI, account menu, Connected Accounts, and MCP Settings. |
| Visual/UX comparison | Does the visible UI/UX or delivered result match the expected behavior and supporting evidence? | Yes. UI showed MS365 connected and Google not connected/connecting for QA, matching DB and broker catalog results. |
| Not run / blocked | Which required surface was not run, and why is the result partial or blocked? | Full chat-to-GlassHive worker launch was not run; this remains a cutover gate before background-agent retirement. |

## User-Grade Evidence

- Surface exercised: local LibreChat UI, broker MCP route, Google Workspace MCP, MS365 MCP, Mongo metadata, generated runtime config.
- Real user path: Playwright authenticated as the local QA user, opened account menu, Connected Accounts, and MCP Settings.
- Visible outcome: QA user saw MS365 connected and Google Workspace not connected/connecting.
- Expanded/detail state: MCP Settings list exposed per-server connection states and connect/reconnect/revoke actions.
- Persistence/reload result: after runtime restart, the frontend reloaded authenticated QA state and the generated broker secret remained present.
- Local/external prerequisite state: Google Workspace and MS365 MCP sidecars responded; QA Google auth was unavailable by design; primary Google and MS365 auth were available.
- Evidence retrieval classification, if applicable: Google synthetic search was successful-empty; QA Google capability was auth/config missing for that user; tampered and expired grants were request rejected.
- Fallback path, if applicable: local-QA JWT was used only for development browser auth and required explicit opt-in.
- Backend/log/DB confirmation: Mongo token metadata remained user-scoped; Google MCP logs showed zero synthetic-query results with token/user fields redacted during inspection.
- Final model/runtime wording check: no final model wording was generated in this pass.
- Substitution check: the visible UI path was run; logs, DB rows, API responses, and unit tests are supporting evidence and do not replace the remaining full chat-to-worker launch gate.

## Automated Evidence

```bash
bin/viventium dev-runtime activate-current --validate --restart --allow-protected-folder --allow-dirty-local-testing
curl -sS -i http://localhost:3180/api/viventium/glasshive/capabilities/health
npm --prefix viventium_v0_4/LibreChat/api test -- --runInBand server/services/viventium/__tests__/GlassHiveCapabilityBroker.spec.js
npm --prefix viventium_v0_4/LibreChat/api test -- --runInBand server/services/viventium/__tests__/GlassHiveCapabilityBroker.spec.js server/routes/viventium/__tests__/glasshiveCapabilities.spec.js server/services/MCP.spec.js server/routes/viventium/__tests__/glasshive.spec.js
npm --prefix viventium_v0_4/LibreChat/packages/data-provider run test:ci -- --runInBand src/mcp.spec.ts src/schemas.spec.ts
npm --prefix viventium_v0_4/LibreChat/packages/data-provider run build
cd viventium_v0_4/GlassHive && runtime_phase1/.venv/bin/python -m pytest runtime_phase1/tests/test_mcp_server.py runtime_phase1/tests/test_profile_runtime.py::test_host_runtime_materializes_project_mcp_bootstrap_with_owner_only_files runtime_phase1/tests/test_docker_sandbox.py::test_seed_bootstrap_writes_project_scope_files -q
viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python -m pytest tests/release/test_config_compiler.py tests/release/test_prompt_registry.py tests/release/test_productivity_activation_source_of_truth.py -q
git diff --check
```

## Findings

- Defects: fixed one broker catalog issue where a reviewed server with zero usable tools could look silently healthy; fixed replay-cache fallback so invocation-id-bearing broker calls fail closed when the shared replay cache is unavailable unless an explicit local-only fallback flag is set.
- Regressions: none observed in the scoped broker test.
- Flakes: Playwright element references changed after closing the settings modal; a fresh snapshot resolved it.
- Environment issues: none blocking after the supported runtime restart generated the broker secret.
- Residual risks: provider-side OAuth revoke/re-consent, host-side write-confirmation UI/API, grant revocation/cleanup beyond TTL, and full chat-to-GlassHive worker launch remain before retiring Google/MS365 background agents.

## Second-Opinion Review

Claude review-only pass completed after the local QA run.

- Confirmed: connected-account isolation proof is sound; zero-tool unavailable hardening addresses the QA missing-Google case; QA report is public-safe.
- Addressed from review: shared replay-cache outage now fails closed by default, and broker guidance is no longer appended to worker `role` labels.
- Deferred as cutover hardening: host-side write-confirmation mint UI/API, grant revocation/cleanup beyond TTL, per-run/worker binding enforcement, duplicate workspace broker cleanup, rate limits/budgets, and full chat-to-worker launch evidence.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
