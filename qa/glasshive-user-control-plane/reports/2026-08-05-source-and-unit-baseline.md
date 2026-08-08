# 2026-08-05 GlassHive User Control Plane Source and Unit Baseline

## Summary

- Result: **PARTIAL — focused automated baseline passes; user and release acceptance not run.**
- Build/source under test: uncommitted nested GlassHive working tree in an isolated parent checkout
- Runtime/artifact under test: source-level test environments only; no installed artifact
- Environment: local synthetic test environments
- Tester: Codex documentation/QA pass
- Related change: GlassHive user control plane and persistent workspaces

The latest focused rerun completed with 78 passing tests across the user-control runtime,
recurrence, identity gateway, and selected Glass Drive BFF/UI contracts. This proves selected source
contracts only. It does not prove a real identity-provider login, provider subscription, browser
workspace, MCP client connection, connected service, scheduled fire, Viventium direct conversation,
installed artifact, fresh install, upgrade, or rollback.

## Scope Run

- Parent component lock: not updated or verified for this baseline.
- Compiled/built/installed artifact: not created or tested for this baseline.
- Data: neutral synthetic fixtures only.

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHUCP-001`–`014` | PARTIAL | 46 selected runtime tests plus relevant gateway/UI tests | Source support only; real user paths pending |
| `GHUCP-017`–`022` | PARTIAL | 18 recurrence and selected Library/BFF/UI tests | Source support only; browser and schedule fire pending |
| `GHUCP-025` | PARTIAL | Synthetic owner-scope and secret-boundary assertions | Two-user browser and final artifact scan pending |
| `GHUCP-015`–`016`, `023`–`024`, `026`–`029` | PENDING | No candidate-specific real-surface evidence | Execute the owning cases before acceptance |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `GHUCP-UC-001` | Sign in, refresh, and log out | No real browser/IdP; TestClient only | PARTIAL | None; no visible browser path run | Gateway assertions and source docs | Real hosted IdP/browser/session/log path |
| `GHUCP-UC-002` | Connect a personal account and run one mission | No real provider/worker; synthetic runtime only | PARTIAL | None | Account/home/lease unit assertions | Native login and live worker mission |
| `GHUCP-UC-003` | Create/find/rename/resume/duplicate a workspace | No real browser; synthetic API/filesystem only | PARTIAL | None | Catalog/duplicate test state | Glass Drive/desktop/restart path |
| `GHUCP-UC-004` | Connect a service and use it through a worker | No real broker/provider surface | PENDING | None | Requirements and existing specialized owner links | Live connection/grant/tool/result audit |
| `GHUCP-UC-005` | Add/update/disable/remove a Library item | No real browser/adapter | PARTIAL | None | Pending-change/grant unit assertions | Browser confirmation, adapter/probe/rollback |
| `GHUCP-UC-006` | Connect real Codex and Claude MCP clients | No real MCP client; TestClient only | PARTIAL | None | OAuth metadata/verifier assertions | Copy/paste, consent, tools, reconnect in both clients |
| `GHUCP-UC-007` | Create recurring work and observe one fire | No real scheduler/user surface | PARTIAL | None | Recurrence store/API/MCP assertions | Clock-triggered worker/grant/lease/callback/result |
| `GHUCP-UC-008` | Continue a direct Viventium GlassHive conversation | Not exercised | PENDING | None | Requirement/architecture inspection | Installed web/channel/voice/scheduler path |
| `GHUCP-UC-009` | Exercise unhappy/retry/cancel/cross-user paths | Synthetic tests only | PARTIAL | None | Selected negative assertions | Complete real-surface failure matrix |
| `GHUCP-UC-010` | Fresh install, upgrade, restart, and rollback | Not exercised | PENDING | None | No artifact evidence | Public clean-room/installed continuity path |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: GlassHive user control plane and persistent workspaces.
- Requirement: `GH-UCP-001`–`GH-UCP-018`.
- Use case: authenticated user manages personal accounts, workspaces, connections, Library items,
  MCP clients, and recurring work without breaking direct conversations or release boundaries.
- QA case: `GHUCP-001`–`GHUCP-029`.
- Expected result: complete owner-scoped user journeys on the designed UI/MCP surfaces and exact
  installed artifact.
- Actual evidence: 78 selected source-level tests pass on the latest rerun.
- Remaining gap or fix: execute every applicable browser/provider/MCP/scheduler/conversation/install
  case and correlate visible outcomes with state and artifact provenance.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Requirements `GH-UCP-001`–`018`; cases `GHUCP-001`–`029`; selected source support only |
| Code owning path | Which code path owns the behavior? | Nested GlassHive identity gateway, runtime control plane, mission binding, workspace catalog, MCP OAuth, and recurrence modules |
| Docs and nested docs/repos | Which docs define expected behavior? | Requirements 01, 07, 11, 39, 40, 45, 48, 50, 51, and 55 plus specialized QA owners |
| Scripts or harnesses | Which suites exercised it? | Three focused pytest command families listed below |
| Local/external prerequisite state | Which provider/runtime prerequisite was proven? | Local test environments only; no external prerequisite claimed healthy |
| Logs | Which sanitized logs confirm the result? | Pytest summaries only; no installed runtime logs inspected |
| DB/state/persistence | Which persisted state confirms it? | Synthetic temporary stores asserted by tests; no live persistent database inspected |
| Generated/shipped artifact | Which artifact was inspected? | None; working-tree source only |
| Real user path | Which browser/MCP/scheduler/GlassHive path was used like a user? | None; all real user surfaces remain open |
| Visual/UX comparison | Does visible UX match expected behavior? | Not evaluated; no real browser run |
| Not run / blocked | Which required surface was not run? | IdP, provider, browser, external MCP clients, broker, scheduler fire, direct conversation, installer, installed runtime, upgrade, rollback, scale, and accessibility |

## User-Grade Evidence

- Surface exercised: no real browser, computer, MCP client, scheduler, provider, Viventium channel,
  installer, or installed GlassHive surface was exercised; source-level TestClient/pytest only.
- Real user path: not run; all browser/IdP, provider, MCP client, workspace, schedule-fire, direct
  conversation, and installer paths remain `PARTIAL` or `PENDING`.
- Visible outcome: none; no screenshot, DOM, accessibility tree, or delivered user result was used.
- Expanded/detail state: not inspected because no real UI surface was run.
- Persistence/reload result: not run against a real workspace or installed runtime; synthetic state
  persistence is supporting evidence only.
- Local/external prerequisite state: no hosted IdP, provider subscription, broker connection,
  external MCP client, scheduler process, channel, voice runtime, or installed build was asserted
  healthy.
- Evidence retrieval classification, if applicable: local prerequisite unavailable for this
  documentation-only baseline; no retrieval result is claimed.
- Fallback path, if applicable: browser/computer/local-delegation was not used; real user-path QA is
  explicitly deferred rather than replaced.
- Backend/log/DB confirmation: synthetic stores and API responses were asserted by focused tests; no
  installed logs, database, or persistent runtime state was inspected.
- Final model/runtime wording check: not applicable to the source-level baseline; no user-visible
  model or runtime result was produced.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Automated Evidence

```text
uv run pytest tests/test_control_plane.py tests/test_internal_assertions.py \
  tests/test_mcp_oauth.py tests/test_mission_provider_accounts.py \
  tests/test_public_compatibility_contract.py tests/test_workspace_catalog.py -q

uv run pytest tests/test_recurring_schedule_api.py tests/test_recurring_schedule_mcp.py \
  tests/test_recurring_schedules.py -q

uv run pytest tests/test_auth_gateway.py tests/test_server.py -q \
  -k 'control_plane_bff or recurring_schedule or connect_ai or provider_account or \
      internal_assertion or multi_user_security or session_authenticated_writes'
```

Latest result: 46 + 18 + 14 = **78 passed**.

An earlier focused invocation, while other implementation work was still being reconciled in the
shared working tree, observed an MCP recurrence structured-content expectation mismatch and an older
Glass Drive schedule-render function-name expectation. After the implementation owners reconciled
those paths, the exact recurrence and UI command families above were rerun and passed. The latest
explicit reruns, not the initial failing invocation, are the evidence cited here.

## Findings

- Defects: no defect remains in the latest selected automated rerun.
- Regressions: no regression is claimed absent installed real-user evidence.
- Flakes: none in the latest selected rerun.
- Environment issues: the first root-level QA-contract invocation used a Python environment without
  pytest; the nested test environment was then used successfully. This did not affect product tests.
- Residual risks: every external/user/installed gate listed above remains open.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails,
  account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, channel chat IDs, database object ids, or
  raw provider request/response ids.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, database
  exports, application-support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.

Synthetic `.invalid` domains and neutral ids are used by the focused tests. This report does not
claim that working-tree source is shipped, installed, or release ready.

## Remaining Work

1. Execute `GHUCP-002`–`029` on every applicable real surface, starting with identity login,
   workspace lifecycle, personal account setup, MCP clients, and scheduled fire-time renewal.
2. Save dated public-safe browser/provider/scheduler reports and correlate visible results with
   sanitized logs, database/state, and activity evidence.
3. Resolve the nested source commit and parent lock, then prove bootstrap/compiler/launcher and the
   exact installed artifact.
4. Run fresh clone/install, upgrade, restart/restore, rollback, scale, accessibility, and final
   public/private/license scans before release acceptance.
