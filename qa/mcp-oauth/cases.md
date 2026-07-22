# MCP OAuth QA Cases

## Case ID Convention

Use stable `MCPOAUTH-NNN` IDs for mcp oauth cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `MCPOAUTH-001` | OAuth-backed MCPs surface auth state, stale grants, and tool results without pretending access exists. | User-visible behavior matches source, docs, persisted state, and logs | Google/MS365 MCP auth, browser settings, tool failure copy | `tests/release/test_ms365_launcher_contract.py` plus user-grade QA when visible | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `MCPOAUTH-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `MCPOAUTH-003` | A down local OAuth MCP endpoint does not break status polling, warmup, or chat response generation | User sees a clear unavailable state while other MCPs and chat keep working | MCP status endpoint, Agent Builder panel, backend warmup logs, web chat | `api/server/routes/__tests__/mcp.spec.js` plus live status/browser QA | 2026-05-17 live runtime sanity - passed with MS365 endpoint down |
| `MCPOAUTH-004` | Connected status requires a decryptable credential and an early provider 401 gets one bounded refresh/replay. | Settings never claims a broken stored row is connected; valid reconnect restores real model use. | Connected Accounts settings, key store, OpenAI Codex route, scheduler generation | data-schema and API package tests plus sanitized browser/log/DB QA | PASS 2026-07-13; unreadable-row RCA reproduced safely, supported reconnect restored a decryptable record, and a real Sol/xHigh scheduled run completed without fallback |

## `MCPOAUTH-001` - Core User Flow

- Requirement: OAuth-backed MCPs surface auth state, stale grants, and tool results without pretending access exists.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_ms365_launcher_contract.py` plus any narrower feature tests discovered during implementation.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `MCPOAUTH-002` - Public-Safe Evidence Record

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

## `MCPOAUTH-003` - Local OAuth Endpoint Down Is Contained

- Requirement: if a configured local OAuth MCP server is not reachable, Viventium must show that state plainly without repeated warmup connection failures, 500 status responses, or chat breakage.
- Risk covered: one unavailable local MCP endpoint creates noisy `fetch failed` logs, status-panel failures, or blocks unrelated assistant responses.
- Preconditions: local runtime is up; at least one OAuth MCP is configured with an unreachable local endpoint; another non-OAuth MCP is reachable.
- Steps:
  1. Run the MCP status route/unit coverage for unreachable local OAuth endpoints.
  2. Start the local runtime and inspect sanitized backend logs for warmup behavior.
  3. Verify `bin/viventium status` reports the endpoint as Action Required rather than ready.
  4. In the browser, verify chat still answers a synthetic prompt and the Agent Builder MCP list remains usable.
- Expected result: unreachable local OAuth endpoint is skipped during persistent warmup, status remains available, other MCPs can connect, and chat response generation continues.
- Forbidden result: repeated `fetch failed`/`ECONNREFUSED` warmup loops, `Cannot read properties of null (reading 'get')`, `Cannot read properties of null (reading 'has')`, MCP status 500s, or misleading "ready" status.
- Evidence to capture: sanitized log summary, CLI status summary, browser response summary, and automated test output.
- Automation: `api/server/routes/__tests__/mcp.spec.js`.
- Last run: 2026-05-17 live runtime sanity - passed for containment; the unavailable endpoint itself remains Action Required until its local service is started/configured.

## `MCPOAUTH-004` - Truthful Stored Credential And Early-401 Recovery

- Unit-fixture a present/decryptable, present/unreadable, and missing encrypted key row.
- Verify status reports connected only for the decryptable row and never logs secret material.
- Unit-fixture an unexpired OAuth access token rejected with 401; refresh and replay exactly once.
- Verify that a replay rejected with a second 401 stops after that replay and surfaces the failure.
- Verify concurrent refresh is bounded per user and refresh failure preserves the original 401 for
  the existing authenticated fallback/reconnect classifier.
- On the real local surface, use the supported Settings reconnect, confirm status after reload, then
  complete a synthetic model-backed run and correlate logs/DB without publishing account details.
- Expected: stored-row presence alone never produces a false green; an early invalidation can
  recover once; a genuinely unreadable record requires reconnect.
- Forbidden: decrypting credentials in the browser, infinite retry, silent fallback presented as
  the requested provider, raw identifiers/tokens in QA, or editing Mongo by hand as the product fix.
- Last run: PASS 2026-07-13; focused key tests passed, the full API package suite passed, supported
  reconnect restored the local record, and the real scheduled Sol/xHigh control completed with no fallback.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Mcp Oauth. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `MCPOAUTH-UC-001` | On Google/MS365 MCP auth, browser settings, tool failure copy, verify that oAuth-backed MCPs surface auth state, stale grants, and tool results without pretending access exists. | owning requirement for `MCPOAUTH-001` / `MCPOAUTH-001` | Google/MS365 MCP auth, browser settings, tool failure copy | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MCPOAUTH-001. | User-visible behavior matches source, docs, persisted state, and logs | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `MCPOAUTH-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `MCPOAUTH-002` / `MCPOAUTH-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MCPOAUTH-002. | The user sees an honest setup, retry, or degraded-state result for MCPOAUTH-002; no fake success is accepted. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `MCPOAUTH-UC-003` | After a down local OAuth MCP endpoint does not break status polling, warmup, or chat response generation, refresh, restart, retry, or switch linked surfaces and verify persistence/parity. | owning requirement for `MCPOAUTH-003` / `MCPOAUTH-003` | MCP status endpoint, Agent Builder panel, backend warmup logs, web chat | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MCPOAUTH-003. | MCPOAUTH-003 remains correct after the persistence or parity step and final wording matches evidence. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `MCPOAUTH-UC-004` | Open Connected Accounts after restart, repair a disconnected provider through the supported reconnect, and run a synthetic model-backed automation. | `39_Installer_and_Config_Compiler.md` / `MCPOAUTH-004` | browser settings, provider callback, scheduler/model path, logs/DB | decryptability status only, sanitized callback/result, provider/model/effort trace, fallback state | Settings is truthful, reconnect persists, the requested provider actually answers, and no credential/account detail enters public evidence. | PASS 2026-07-13; browser reconnect and post-restart real scheduled control passed; private identifiers remained outside repo evidence |
