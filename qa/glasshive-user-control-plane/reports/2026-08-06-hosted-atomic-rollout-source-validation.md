# 2026-08-06 Hosted Atomic Rollout Source Validation

## Summary

- Result: PARTIAL.
- Source under test: isolated uncommitted public-source candidate.
- Runtime/artifact under test: macOS source harness and clean Debian synthetic deployment image.
- Environment: synthetic release, state, database, services, and ingress adapters only.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| GHUCP-032 | PARTIAL | 36 macOS and 36 Debian failure-injection cases | Source harness passed; real hosted state migration remains unrun. |
| GHUCP-033 | PARTIAL | Clean Debian systemd verification and route-contract tests | Real ingress cutover and rollback remain unrun. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: atomic hosted GlassHive rollout and recovery.
- Requirement: requirement 55 immutable deployment and rollback.
- Use case: an operator stages and validates a candidate before a single ingress switch, then can restore the predecessor.
- QA case: GHUCP-032 and GHUCP-033.
- Expected result: exact provenance, three-service health, state-safe migration, atomic ingress, and complete rollback.
- Actual evidence: all 36 macOS and 36 clean-Debian synthetic cases and Debian unit verification passed.
- Remaining gap or fix: install the exact pinned candidate and run authenticated live cutover/failure/rollback after approval.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Requirement and use case | Requirement 55, GHUCP-032, and GHUCP-033. |
| Code owning path | Immutable staging, backup/clone, service orchestration, ingress adapter, journal, and rollback. |
| Docs and nested docs/repos | Requirement 55, hosted rollout runbook, and nested GlassHive runtime contract. |
| Scripts or harnesses | macOS and Debian rollout suites plus systemd unit verification. |
| Local/external prerequisite state | Clean Debian container and local macOS harness; no hosted cloud prerequisites were changed. |
| Logs | Sanitized pass/failure-injection summaries only; no live service log capture. |
| DB/state/persistence | Synthetic WAL/backup/restore and invariant hashes; no hosted database. |
| Generated/shipped artifact | Synthetic immutable releases and verified unit files; not a live installed candidate. |
| Real user path | Operator-style harness ran; authenticated browser and MCP paths were BLOCKED. |
| Visual/UX comparison | BLOCKED because a live candidate was not routed to a browser. |
| Not run / blocked | Real identity, providers, ingress, browser, MCP, service loss, and rollback persistence. |

## User-Grade Evidence

- Surface exercised: local CLI rollout harness and clean Debian systemd validation.
- Real user path: an operator-style synthetic stage, accept, switch, failure, and rollback path ran; browser/MCP users were BLOCKED.
- Visible outcome: terminal acceptance and injected failures produced the expected pass or rollback result; no hosted UI was claimed.
- Expanded/detail state: release manifests, provenance, route ownership, key/log rules, journal phases, and rollback receipts were inspected.
- Persistence/reload result: synthetic database/state restore and service-group recovery passed; hosted persistence remained BLOCKED.
- Backend/log/DB confirmation: sanitized synthetic counts, hashes, unit verification, and route assertions confirmed the harness outcome.
- Final model/runtime wording check: this report remains PARTIAL and explicitly says the hosted environment is unchanged.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting evidence, not substitutes for any required visible-UI, detail-state, persistence, or wording step.

## Automated Evidence

- macOS rollout suite: 36 passed.
- Clean Debian rollout suite: 36 passed.
- Debian systemd unit verification, relocation smoke, Ruff, Python parse, and artifact-hygiene checks passed.

## Findings

- Defects: Python-version-dependent archive extraction was found on the first clean-Debian run and replaced by explicit member validation.
- Regressions: none found after the corrected macOS and Debian reruns.
- Environment issues: no hosted identity, service, state, database, or ingress access was mutated.
- Residual risks: installed authentication, user persistence, process isolation, cutover, and rollback remain unproven.

## Outcome

Result: **PARTIAL — the portable rollout and failure-injection harness passes on macOS and clean
Debian; no hosted release or real ingress was changed.**

This run validates source support for `GHUCP-032` and `GHUCP-033`: immutable release staging,
WAL-consistent database backup and clone rehearsal, all-three-service readiness before ingress,
and journaled database/state/release/ingress rollback. It is not installed or live-user acceptance.

## Evidence Run

| Surface | Result | Evidence |
| --- | --- | --- |
| macOS rollout suite | PASS | 36 synthetic cases passed |
| Clean Debian Bookworm rollout suite | PASS | 36 synthetic cases passed with the repository mounted read-only |
| Clean Debian unit verification | PASS | `systemd-analyze verify` accepted the target and runtime, UI, and MCP units with all referenced paths staged |
| Real uv relocation smoke | PASS | A frozen relocatable synthetic environment still executed after its project directory moved |
| Static quality | PASS | Ruff passed; four changed Python files parsed successfully |
| Generated artifact hygiene | PASS | No source-tree bytecode cache remained; deployment bytecode is ignored |

The first clean-Debian run found that immutable staging used a tar extraction parameter unavailable
on its Python version. The staging path now validates every archive member itself, rejects traversal,
unsafe links, duplicates, link-parent traversal, and unsupported entries, and uses the optional
standard-library filter only where supported. The Debian and macOS suites then passed.

## Behaviors Proven by Synthetic Failure Injection

- A staged release binds the clean committed parent, exact nested GlassHive pin, complete file/mode
  manifest, and two relocatable frozen virtual environments; mutation, residue, or a changed
  external interpreter target fails verification.
- Active and candidate ports cannot overlap; slot files reject secrets, whitespace, malformed keys,
  and unsafe ownership/modes.
- Rootless Docker must be reached through the runtime user's exact socket and report `rootless`;
  rootful, unavailable, malformed, or ambiguous results fail closed.
- Writers stop before database/state capture. SQLite backup includes committed WAL, restores into a
  clean file, and checks quick/integrity/foreign keys, schema ledger, counts, and hashed owner/tenant
  invariants without recording raw identities.
- The candidate first migrates cloned state on alternate ports. Runtime, UI/auth registry, MCP, and
  authenticated acceptance must all pass before the ingress adapter may switch.
- Candidate slot environments carry the manifest release id and exact parent/component revisions;
  candidate readiness requires exact matching provenance from runtime, UI, nested runtime, and MCP.
- Ingress switch and status attest a SHA-256-bound route contract: root, login, auth, static, API,
  confirmation, short-link, watch, desktop, noVNC/websocket, runtime UI/API proxy, favicon, and health paths to one Glass
  Drive release; `/mcp` and MCP protected-resource metadata directly to MCP without an
  `oauth2-proxy` HTML redirect; JWKS to Glass Drive; no public runtime; and scrubbing all client
  identity headers in the `X-Viventium-`, `X-GlassHive-`, and `X-LibreChat-` families.
- The UI unit disables access logs, and candidate/live acceptance requires sanitized UI and edge log
  capture proving that OIDC callback `code` and `state` query values were not persisted.
- Failures during clone rehearsal, candidate start, candidate acceptance, live start, ingress
  switch, or post-switch acceptance restore the preceding ingress, state, verified databases,
  release pointer, slot files, and complete service group.
- A first managed auth database is rehearsed on the clone and removed on failed live cutover when no
  predecessor database existed. An unfinished journal blocks a new deployment until recovery.
- UI auth-registry readiness precedes MCP startup, eliminating first-start OAuth enrollment against
  an uninitialized auth schema without creating a dependency cycle.

## Not Run / Release Gate

The following remain mandatory and are **not** replaced by these tests:

- build and install one exact committed/pinned release on the intended Linux host;
- implement and independently review the real state, ingress, and authenticated-acceptance adapters;
- provision and verify the documented tenant-specific Entra web/API/Claude/Codex registrations,
  exact loopback redirects, v2 API audience/scope, client preauthorization, and role/group policy;
- exercise real browser login, designed Glass Drive root, authenticated MCP initialize, public JWKS,
  trusted-header overwrite, and proof that the runtime has no public route;
- inject service, state, database, edge, and process-loss failures on the installed release;
- prove browser/MCP persistence after cutover and after database-restoring rollback;
- inspect sanitized service logs, database/state receipts, process provenance, monitoring, and the
  final public/private boundary.

Until those gates pass, `GHUCP-032` and `GHUCP-033` remain `PARTIAL`, and hosted release readiness is
`NO-GO`.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, channel chat IDs, database object ids, or raw provider request/response ids.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, database exports, application-support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
