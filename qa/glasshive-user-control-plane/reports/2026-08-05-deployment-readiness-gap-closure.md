# 2026-08-05 GlassHive User Control Plane Deployment-Readiness Gap Closure

## Summary

- Result: **PARTIAL — release-blocking source guards were added; hosted deployment remains unrun.**
- Source under test: isolated uncommitted candidate working trees.
- Runtime/artifact under test: source test environments only; no installed or cloud artifact.
- Data: neutral synthetic values only.

An independent deployment review found four invariants that the earlier candidate only implied:
path-aware public routing, signer/runtime key isolation, rehearsed existing-database migration and
restore, and atomic runtime/MCP/BFF readiness. They are now explicit requirements and QA cases
`GHUCP-030`–`033`; they are not recorded as hosted passes.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| GHUCP-030 | PARTIAL | Route-ownership source guards and focused tests | Real hosted ingress was not changed or exercised. |
| GHUCP-031 | PARTIAL | Key-isolation source guards and focused tests | Installed process identities and rotation were not exercised in this run. |
| GHUCP-032 | PARTIAL | Schema/version and backup guards | A live database migration and restore were not run. |
| GHUCP-033 | PARTIAL | Atomic-readiness launcher tests | No immutable hosted cutover or rollback was run. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: GlassHive user control plane deployment safety.
- Requirement: requirement 55 hosted routing, key isolation, migration, and atomic rollout gates.
- Use case: an operator promotes one exact candidate without exposing the worker runtime or losing state.
- QA case: GHUCP-030 through GHUCP-033.
- Expected result: every service and data boundary is proven before ingress switches, with a tested rollback.
- Actual evidence: focused source tests and failure-injection contracts passed.
- Remaining gap or fix: run the installed, authenticated hosted cutover and rollback after approval.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Requirement and use case | Requirement 55 and GHUCP-030 through GHUCP-033. |
| Code owning path | Deployment launcher, schema ledgers, assertion boundary, and route contract. |
| Docs and nested docs/repos | Requirement 55, this QA catalog, and nested GlassHive runtime documentation. |
| Scripts or harnesses | Focused launcher, schema, and assertion tests described below. |
| Local/external prerequisite state | Source test environment only; hosted identity, ingress, and services were not provisioned. |
| Logs | Sanitized test summaries only; no live service logs were collected. |
| DB/state/persistence | Synthetic databases exercised schema guards; no hosted database was touched. |
| Generated/shipped artifact | Source candidate only; no installed artifact was claimed. |
| Real user path | BLOCKED because hosted browser, MCP, and operator cutover paths require approved deployment. |
| Visual/UX comparison | BLOCKED because no hosted UI candidate existed in this run. |
| Not run / blocked | Hosted identity, ingress, database restore, rollback, and authenticated browser/MCP paths. |

## User-Grade Evidence

- Surface exercised: local CLI and source-level GlassHive deployment harness.
- Real user path: an operator-style local validation was run; the required hosted browser and MCP path was BLOCKED.
- Visible outcome: terminal test results showed the source guards passing; no live UI outcome was claimed.
- Expanded/detail state: detailed failure-injection results were inspected for route, key, schema, and readiness guards.
- Persistence/reload result: synthetic schema behavior passed; hosted persistence and restart remained BLOCKED.
- Backend/log/DB confirmation: sanitized test counts and synthetic database assertions only.
- Final model/runtime wording check: the report says PARTIAL and does not claim the old hosted UI contains this candidate.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting evidence, not substitutes for any required visible-UI, detail-state, persistence, or wording step.

## Source Changes and Evidence

| Finding | Source guard now present | Focused evidence | Remaining acceptance gate |
| --- | --- | --- | --- |
| Runtime could inherit the private assertion-key path from a shared launcher environment | Runtime startup refuses a configured readable key; integrated launcher removes the key and prevents runtime-env reload; integrated multi-user launch fails when its shared user can read the key | Internal-assertion focused suite and launcher contract tests | Separate installed OS/container signer and verifier identities, worker denial probe, and rotation |
| Local launcher omitted MCP readiness and returned success after incomplete health | Runtime, MCP, and BFF are all probed; incomplete readiness stops the complete candidate group and returns failure | Launcher contract tests and shell parse | Immutable hosted staging, per-service failure injection, ingress switch, authenticated browser/MCP, rollback |
| Database mutations had no component version guard | Runtime and control-plane stores record independent schema versions and refuse a database created by newer code | Schema-version and control-plane focused suites | WAL-consistent backup, clone rehearsal, integrity/FK/count checks, cutover, injected restore |
| Hosted edge ownership was not enforceable from product truth | Exact browser/MCP/JWKS/runtime path ownership and trusted-header scrubbing are mandatory in requirement/case coverage | Documentation/QA traceability review | Install path-aware edge and run `GHUCP-030` on real browser/MCP surfaces |

The supported host-native requirement mechanism keeps the compatibility floors at Codex `0.144.1`
and Claude Code `2.1.178`, while fresh isolated workstation images are separately pinned to Codex
`0.146.1` and Claude Code `2.1.223`. Focused tests now assert this split and the latest-channel
Claude recovery instruction; clean installed capability comparison remains pending.

## Focused Test Truth

- Directly changed schema/internal-assertion/control-plane suite: **28 passed**.
- Three host-capacity tests that failed only during one large concurrent collection: **3 passed**
  when rerun together in isolation. They remain classified as load-sensitive test behavior, not
  proof of installed scale acceptance.
- Launcher verifier-only/readiness contract: **2 passed**.
- Shell syntax and all changed-tree diff checks: **passed**.

These results are source support. They do not substitute for the real hosted route, key isolation,
database migration/restore, identity, external MCP, provider, connector, scheduler, or compatibility
paths.

## Release Decision

**NO-GO until `GHUCP-030`–`033` and the existing pending hosted/installed gates run against one exact
committed, pinned, reproducible candidate.** No commit, push, component-pin update, deployment,
service restart, identity change, or cloud mutation was performed in this gap-closure pass.

## Automated Evidence

- Focused internal-assertion, schema, launcher-readiness, and shell-contract suites passed as counted above.
- Shell syntax and changed-tree diff checks passed.

## Findings

- Defects: the source previously implied four deployment invariants that were not enforceable; guards were added.
- Regressions: none found in the focused source suites.
- Environment issues: hosted identity, ingress, and service access were intentionally not mutated.
- Residual risks: all installed and real-user gates remain open until an approved rollout.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, channel chat IDs, database object ids, or raw provider request/response ids.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, database exports, application-support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
