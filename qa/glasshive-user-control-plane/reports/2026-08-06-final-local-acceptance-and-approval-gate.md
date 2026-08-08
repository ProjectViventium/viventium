# GlassHive User Control Plane Final Local Acceptance - 2026-08-06

## Summary

- Result: **PARTIAL**. The local source candidate, real browser control plane, durable state, and a
  real external Codex MCP discovery pass are accepted. Hosted release acceptance remains blocked.
- Build/source under test: uncommitted public-safe parent, GlassHive, and LibreChat candidate
  branches; no protected downstream source was changed.
- Runtime/artifact under test: source GlassHive runtime, Glass Drive UI, local MCP service, built
  LibreChat packages, and compiler output.
- Environment: isolated local development runtime with a temporary synthetic database and neutral
  test identities.
- Tester: Codex implementation and browser acceptance plus independent security/compiler,
  worker-isolation, and final-product review passes. A final Claude Opus 5 Extra review-only pass
  independently re-ran the compiler, Glass Drive, focused GlassHive, LibreChat, and Scheduling
  Cortex suites and returned local GO after its last documentation finding was corrected.
- Related change: `GH-UCP-001` through `GH-UCP-018` in the owning requirement document.
- Release boundary: no public commit, nested pin, push, identity-provider mutation, cloud mutation,
  installed-runtime activation, or hosted cutover was performed.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHUCP-001` | PARTIAL | Compatibility and nested test suites | Source compatibility passes; installed Viventium surfaces remain blocked. |
| `GHUCP-002`–`006` | PARTIAL | Browser OIDC failures, gateway tests, MCP OAuth tests, generated connection commands | Hosted IdP login and HTTPS OAuth clients remain blocked. |
| `GHUCP-007`–`010` | PARTIAL | Real browser lifecycle plus provider/account isolation suites | Synthetic provider exercised; real subscriptions remain blocked. |
| `GHUCP-011`–`014` | PASS locally | Browser catalog, duplicate, template, restart, DB integrity | Hosted two-user isolation remains a release gate. |
| `GHUCP-015`–`018` | PARTIAL | Browser Library approval/removal and broker suites | Real connected service and worker tool call remain blocked. |
| `GHUCP-019`–`020` | PASS locally | Desktop/mobile browser and external Codex MCP discovery | Hosted cross-client parity remains blocked. |
| `GHUCP-021`–`023` | PARTIAL | Browser create/run/history/pause/resume/recovery, restart, recurrence suites | Installed wall-clock fire remains blocked. |
| `GHUCP-024`–`033` | PARTIAL/BLOCKED | Source tests, compiler, rollout harness, public-safety scan | Installed and hosted provenance/cutover paths require explicit approval. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `GHUCP-UC-001` | Sign in, refresh, recover, and log out | Local browser gateway | PARTIAL | Unreachable issuer and forged callback state gave explicit retry/recovery copy | Gateway tests and session/state assertions passed | Real hosted IdP happy path, domain policy, MFA, and logout |
| `GHUCP-UC-002` | Connect a personal worker account and choose it for one workspace | Glass Drive browser | PARTIAL | Setup, ready, selection approval, observed run/failure/time and worker-reported token evidence, disconnect, reconnect-required, reset, and Forget were visible | Provider record count returned to zero; account policy/lease/usage tests passed | Real Codex and Claude subscription missions |
| `GHUCP-UC-003` | Create, find, rename, favorite, resume, duplicate, and template a workspace | Glass Drive browser | PASS locally | Human names, tags, filters, retained/paused states, favorite, copy, and template remained visible after restart | Three distinct workspaces, one template, DB integrity `ok` | Hosted two-user/browser-profile continuity |
| `GHUCP-UC-004` | Connect a service and let a worker use it | Browser plus broker tests | BLOCKED | The Connections UI exposed user-scoped connected-service readiness without claiming a connection | Broker grants and failure classes passed with synthetic providers | Authorized real connected-service consent and worker tool call |
| `GHUCP-UC-005` | Add, inspect, approve, cancel, and remove a Library item | Glass Drive browser | PARTIAL | Version, hash, permissions, browser-only approval, cancel, and confirmed removal were visible | Revoked audit record remained and active grants returned to zero | Real worker use and upgrade path |
| `GHUCP-UC-006` | Connect an existing AI client and inspect the same resources | Browser plus ephemeral Codex CLI | PARTIAL | The UI separated numbered add/sign-in commands from non-command registration references; Codex reported the renamed workspace and schedule | MCP auth, safe annotations, scoped tools, fresh assertions, and human `workspace_name` matched API state | Hosted OAuth plus real Claude client |
| `GHUCP-UC-007` | Create recurring work, run it, inspect history, pause, resume, and recover | Glass Drive browser plus scheduler | PARTIAL | The schedule card visibly showed `Latest result: completed`; one completed occurrence survived restart; disconnected-account retry showed actionable recovery and created no duplicate | One definition and one immutable completed occurrence; bounded retry suites passed | Installed automatic wall-clock fire and hosted revocation |
| `GHUCP-UC-008` | Continue an ordinary Viventium direct GlassHive conversation | Source compatibility suites | BLOCKED | No installed user conversation surface was changed or exercised | Additive provider/broker/scheduler regressions passed | Installed web/channel/voice user path |
| `GHUCP-UC-009` | Try missing auth, stale state, dependency outage, revoked account, retry, and cancel | Browser, MCP, API, tests | PARTIAL | OIDC recovery, catalog unavailable, Library cancel, and account reconnect guidance were visible and honest | Structured failures preserved distinct classes with no forbidden side effects | Complete hosted two-user/capacity/provider matrix |
| `GHUCP-UC-010` | Install, upgrade, restart, reopen, and roll back | Local runtime restart and rollout harness | PARTIAL | Browser state survived a real source-runtime restart | Compiler, migration, systemd stage/cutover/rollback tests passed | Fresh public install and installed artifact QA |
| `GHUCP-UC-011` | Stage, migrate, cut over, verify, and roll back all hosted services | Rollout source harness only | BLOCKED | No hosted surface was changed | Immutable release harness and readiness contract passed locally | Explicit approval, cloud stage, cutover, and hosted matrix |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: individual GlassHive control plane and persistent workspaces.
- Requirement: `GH-UCP-001` through `GH-UCP-018` in
  `docs/requirements_and_learnings/55_GlassHive_User_Control_Plane_and_Persistent_Workspaces.md`.
- Use case: secure entry, personal worker account, reusable workspace, connected capability,
  recurring work, and external MCP client without breaking existing Viventium behavior.
- QA case: `GHUCP-001` through `GHUCP-033` and `GHUCP-UC-001` through `GHUCP-UC-011`.
- Expected result: a private, user-scoped, recoverable control plane with explicit authorization,
  durable human-named resources, and compatible worker-native behavior.
- Actual evidence: real local browser actions, restart persistence, local MCP client output,
  database counts/integrity, complete/focused suites, package builds, and public-safety inspection.
- Remaining gap or fix: explicit mutation approval followed by nested publication, IdP/cloud rollout,
  and hosted two-user/provider/connector/schedule/direct-conversation acceptance.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Requirement 55, `GHUCP-001`–`033`, and the natural-use-case matrix above. |
| Code owning path | Which code path owns the behavior? | GlassHive runtime control plane/auth/MCP/scheduling, Glass Drive BFF/UI, LibreChat identity/provider/broker/scheduler bridge, and parent compiler/launcher. |
| Docs and nested docs/repos | Which docs or nested repo docs define expected behavior? | Requirement 55, architecture/system maps, GlassHive MCP/UI docs, and the owning nested runtime READMEs. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Playwright CLI, runtime/UI/MCP suites, LibreChat Jest/package builds, compiler tests, and immutable-rollout tests. |
| Local/external prerequisite state | Which prerequisite was proven healthy or degraded? | Local runtime/UI/MCP were healthy; synthetic provider and bearer auth were intentional; hosted IdP, real providers, and cloud release were not authorized. |
| Logs | Which sanitized logs confirm or contradict the result? | Runtime/UI/MCP process output contained no uncaught happy-path errors; the negative disconnected-account probe returned its expected structured conflict. |
| DB/state/persistence | Which state confirms it? | Integrity `ok`; three workspace identities, one template, one schedule, one completed occurrence, zero provider records after cleanup, and zero active Library grants. |
| Generated/shipped artifact | Which generated or built artifact was inspected? | Compiler output, built LibreChat API/client/data packages, MCP connection instructions, and systemd rollout unit/release layout. Installed/hosted artifacts remain blocked. |
| Real user path | Which real product path was used? | Headed Playwright browser across all six Glass Drive views plus an ephemeral Codex CLI connected to local authenticated MCP. |
| Visual/UX comparison | Did visible UX match expected behavior and evidence? | Yes locally: human names, readiness, recovery wording, history, confirmation boundaries, and persisted state matched API/DB evidence. |
| Not run / blocked | Which required surface was not run? | Hosted OIDC/two-user/provider/connector/HTTPS MCP/automatic fire/direct conversation and clean-clone installed release. |

## User-Grade Evidence

- Surface exercised: the real Glass Drive browser UI, human confirmation page, local OIDC gateway
  failures, local MCP service, and an ephemeral Codex CLI client.
- Real user path: navigated every designed view; renamed, filtered, favorited, duplicated, templated,
  approved, removed, connected, disconnected, scheduled, ran, paused, resumed, refreshed, restarted,
  and inspected details like a user.
- Visible outcome: workspaces remained human-named and discoverable; account/capability choices stayed
  user-scoped; observed usage was explicitly separated from worker-reported tokens; recurring history
  remained singular with a visible completed result; failures gave actionable recovery.
- Expanded/detail state: Library approval showed version/hash/permissions; workspace cards showed
  account/connection/tags/next-run; Connect AI showed distinct commands and registration references;
  schedule history showed exactly one completed occurrence and its latest result.
- Persistence/reload result: runtime restart preserved workspace names, tags, favorite, duplicate,
  template, schedule, and completed occurrence; cross-tab account readiness refreshed immediately.
- Local/external prerequisite state: local services and package builds were healthy; real hosted IdP,
  provider subscriptions, connected services, and cloud deployment were deliberately not mutated.
- Evidence retrieval classification, if applicable: the degraded workspace run was classified as
  local prerequisite unavailable; the disconnected schedule was classified as auth/config repair
  required, not as an empty result or success.
- Fallback path, if applicable: the UI retained navigation and retry guidance when the runtime was
  unavailable; no fake fallback account or connector success was claimed.
- Backend/log/DB confirmation: database integrity and scoped counts matched the visible catalog,
  account cleanup, Library revocation, and schedule history.
- Final model/runtime wording check: external Codex used only read-only GlassHive tools and reported
  the renamed workspace, hourly schedule, next run, and completed occurrence without mutation.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for required visible-UI, detail-state,
  persistence, or wording steps. Those local user paths were run; hosted ones remain blocked.

## Automated Evidence

```bash
cd viventium_v0_4/GlassHive && runtime_phase1/.venv/bin/python -m pytest -q runtime_phase1/tests
cd viventium_v0_4/GlassHive/frontends/glass-drive-ui && ../../runtime_phase1/.venv/bin/python -m pytest -q
cd viventium_v0_4/LibreChat && npm run test:api -- --runInBand api/server/routes/viventium
cd viventium_v0_4/LibreChat && npm run test:client -- --runInBand ConnectedAccounts.spec.tsx
cd viventium_v0_4/LibreChat && npm run build:packages
cd viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex && uv run --group test pytest -q
cd ../../../../.. && viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/python -m pytest tests/release -q
git diff --check
```

Final results after the Opus closeout: GlassHive runtime 1,063 collected (1,060 passed, 3 skipped);
Glass Drive 193 passed;
Scheduling Cortex 143 passed plus 16 subtests; LibreChat packages API 3,082 passed and 2 skipped;
parent release 2,308 passed and 9 skipped. The serial LibreChat package and client builds completed
successfully. The real-browser acceptance pass completed with no browser console errors or warnings.

## Findings

- Defects: six browser/client defects were found and fixed: catalog readiness overwrite, duplicate
  next-run copy, missing MCP workspace name, raw degraded-runtime error, missing read-only MCP
  annotations, and stale cross-tab account readiness/internal schedule recovery wording.
- Final adversarial closeout: host-native compatibility floors are now documented separately from
  fresh-workstation image pins and directly asserted; default auth-state placement uses the actual
  platform rather than a home-path heuristic. An alleged residual recurrence duplicate window was
  confirmed to belong only to the replaced two-transaction path: the current run insert and
  occurrence link share one SQLite transaction. A trigger-injected link failure regression proves
  that the run insert rolls back and the retry creates exactly one stable run.
- Regressions: each defect gained automated coverage in its owning runtime, API, MCP, or UI suite.
- Flakes: none accepted; the complete parent suite initially exposed a missing local built package
  prerequisite and a report-template violation. The package was built, the report corrected, and
  the complete parent suite then passed.
- Environment issues: real hosted IdP/provider/connector/cloud surfaces require explicit mutation
  approval and were not approximated as passes.
- Residual risks: clean-clone provenance, real multi-user isolation, worker subscriptions, connected
  services, HTTPS OAuth clients, wall-clock fire, installed conversations, and hosted rollback.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
