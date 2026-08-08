# 2026-08-05 GlassHive User Control Plane Implementation and Local Browser QA

## Summary

- Result: **PARTIAL — the source candidate and local user journeys pass; release acceptance is open.**
- Build/source under test: uncommitted candidate in an isolated public-source checkout.
- Runtime under test: source runtime and Glass Drive UI in local synthetic mode; no installed artifact.
- Data: neutral synthetic users, workspaces, schedules, skills, and provider state only.

The candidate adds the user control plane to the designed Glass Drive UI without replacing the basic
runtime surfaces or Viventium's direct GlassHive conversation provider. The complete affected source
suites pass, and Playwright exercised the principal local workflows like a user. External identity,
real provider/connector consent, real external MCP clients, multi-user personal-subscription compute
isolation, installed automatic scheduled execution, and the source-to-installed delivery chain were not proven and
are not represented as complete. Versioned templates and the complete standalone recurrence
definition contract are implemented and source-tested; their installed real-worker paths remain
partial.

## Scope Run

| Case range | Result | Evidence | Notes |
| --- | --- | --- | --- |
| GHUCP-001 through GHUCP-029 local synthetic paths | PARTIAL | Local Playwright journey and automated suites below | Core local UI paths passed; external and installed paths remained open. |
| GHUCP-030 through GHUCP-033 hosted delivery paths | BLOCKED | Source inspection only in this run | Hosted acceptance was not performed. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: GlassHive individual-user control plane and persistent workspaces.
- Requirement: requirement 55.
- Use case: a signed-in user creates, keeps, finds, resumes, duplicates, connects, and schedules private work.
- QA case: GHUCP-001 through GHUCP-029.
- Expected result: user-visible state is owner scoped, clear, persistent, resumable, and honest about unavailable external prerequisites.
- Actual evidence: the local Playwright journey and complete affected source suites passed as recorded below.
- Remaining gap or fix: hosted OIDC, real providers/connectors, external MCP clients, installed schedules, and deployment acceptance.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Requirement and use case | Requirement 55 and the GHUCP case catalog. |
| Code owning path | Glass Drive UI, GlassHive runtime, MCP resource, scheduler bridge, and LibreChat capability owner. |
| Docs and nested docs/repos | Requirement 55, parent architecture/system maps, and nested GlassHive/LibreChat source docs. |
| Scripts or harnesses | Playwright browser harness plus UI, runtime, compiler, and LibreChat suites listed below. |
| Local/external prerequisite state | Local synthetic services were available; external identity/provider/connector prerequisites were not configured. |
| Logs | Sanitized local server and browser assertions were inspected. |
| DB/state/persistence | Synthetic workspace, schedule, account, connection, and library state was checked after refresh. |
| Generated/shipped artifact | Local source runtime only; no installed or hosted artifact was claimed. |
| Real user path | Local browser path exercised New, Workspaces, Library, Schedules, Accounts, and Connect AI. |
| Visual/UX comparison | Visible local state matched API and stored state for the recorded paths. |
| Not run / blocked | Hosted login, real consent, real connector, real client MCP login, installed firing, and rollout. |

## User-Grade Evidence

- Surface exercised: Playwright in a real local browser against Glass Drive.
- Real user path: create fresh work, keep, rename, search, resume, duplicate, template, configure a synthetic account and connection, add/remove a Library item, create a schedule, and inspect Connect AI.
- Visible outcome: all six product areas rendered and the principal local workflow results matched the table below.
- Expanded/detail state: workspace details, account/connection readiness, schedule details, and generated client instructions were inspected.
- Persistence/reload result: kept names and owner-scoped catalog state remained visible after refresh in the synthetic local environment.
- Backend/log/DB confirmation: browser assertions were correlated with sanitized local API and persisted-state checks.
- Final model/runtime wording check: unavailable external paths remained visibly unavailable and no response claimed a connector or subscription had been connected.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting evidence, not substitutes for any required visible-UI, detail-state, persistence, or wording step.

## Automated Evidence

- Glass Drive UI, GlassHive runtime/API/MCP, compiler, scheduler, and LibreChat integration suites passed with the counts recorded later in this report.
- Python compilation, JavaScript syntax, and changed-tree checks passed for the candidate at that point in the run.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, channel chat IDs, database object ids, or raw provider request/response ids.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, database exports, application-support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.

## What Was Implemented

- OIDC Authorization Code with PKCE/state/nonce, stable issuer+subject ownership, domain policy,
  session/CSRF controls, asymmetric internal assertions, public JWKS, role/scope checks, and a
  fail-closed trusted-proxy boundary.
- OAuth-protected MCP resource metadata and owner-scoped UI/MCP operations for workspaces, accounts,
  connections, Library items, confirmations, schedules, and Activity.
- Personal provider-account metadata, provider-native isolated homes, setup/status/default/disconnect,
  mission leases, a narrow provider-setup environment allowlist, setup capacity bounds, and private
  credential-tree permissions. Multi-user personal subscriptions remain unavailable until a real
  per-worker isolation substrate is proven.
- A user-scoped LibreChat inference broker for encrypted OpenAI API keys and trusted enterprise
  routes. GlassHive persists only opaque owner-bound references; grants are short lived, bound to
  tenant/user/worker/run/model/adapter, redacted, and revoked. Users cannot override upstream URLs or
  headers, and redirects are rejected.
- Fresh ephemeral workspaces, explicit Keep-to-named transition, human rename/search/tags/favorites,
  bounded catalog pagination, crash-safe idempotent paused duplication without starting compute,
  immutable versioned templates, and secret-safe artifact access.
- Curated non-secret Library manifests, inspect/confirm/activate/grant flow, browser-only human
  confirmation, and drift-aware removal that restores prior bootstrap state.
- One recurrence owner, daily/interval/cron/RFC 5545 definitions, start/end/overlap/misfire/jitter
  policy, immutable occurrence ledger, owner-scoped UI/API/MCP controls, and Viventium delegation to
  Scheduling Cortex with fresh occurrence-bound fire-time assertions and signed terminal callbacks.
- Managed connected-account policy in LibreChat/Viventium, capability grant propagation, and
  scheduler delegation while preserving the existing direct conversation provider.
- A versioned `connect-glasshive` companion skill and deployment-generated official Codex/Claude MCP
  commands.
- Worker bootstrap requirements updated through the existing mechanism to registry-current Codex
  `0.146.1` and Claude Code `2.1.222` on 2026-08-05.

Later correction (2026-08-05): the frozen candidate and repeat client inspection use Claude Code
`2.1.223`; `2.1.222` above records the earlier run and is not the supported candidate pin.

## Local Playwright Journey

| User action | Result | Supporting state |
| --- | --- | --- |
| Open Glass Drive and use the three-field launcher | PASS | Designed New view rendered; missing description focused that field, description without success criteria focused the second required field, optional context remained available, and advanced account/profile controls stayed secondary |
| Create fresh work | PASS | New workspace was stored as `ephemeral`; run completed in the synthetic worker runtime |
| Keep and rename workspace | PASS | Keep changed the kind to `named`; the human label persisted after refresh |
| Duplicate workspace | PASS | A new paused identity was created, files were copied, and no compute process started |
| Save and instantiate a workspace template | PASS | An immutable template created a fresh paused workspace identity; both persisted after refresh |
| Add a curated skill | PASS | Browser review/confirmation created an active grant and materialized the approved bootstrap file |
| Remove the skill | PASS | A second confirmation removed the grant and restored the prior bootstrap state |
| Create, run, and pause recurring work | PASS/PARTIAL | Daily definition and human next-run state rendered; Run now produced exactly one completed occurrence and stable scheduled run; pause confirmation and refresh persisted the paused state. This used the local synthetic worker, not an installed automatic clock fire |
| Inspect Activity | PASS | User-visible audit types appeared without raw instruction or message contents |
| Connect a personal Codex account | PASS/PARTIAL | Synthetic provider-native setup reached `ready`; account-specific home was private; no real provider was contacted |
| Connect a user OpenAI API-key reference | PASS/PARTIAL | Browser add/status/refresh passed and scoped database inspection found only the opaque LibreChat broker reference; no live paid inference ran |
| Disconnect the personal account | PASS | Account became disconnected, default cleared, active lease count stayed zero, and the managed credential home was removed |
| Use Connections/MCP setup guidance | PASS/PARTIAL | Copyable deployment-generated commands and accurate source-available wording rendered; no external client connected |
| Use narrow mobile viewport | PASS | All six navigation tabs remained visible in two rows and the Connections layout did not overlap |

The final browser console contained zero errors and zero warnings. The tested provider-created
credential file was normalized to `0600`; all managed credential directories were `0700`. Browser
results were correlated with scoped API responses, database status, grants, recurrence rows,
activity rows, workspace bootstrap state, and credential-home presence/removal.

## Automated and Build Evidence

| Surface | Result |
| --- | --- |
| Complete GlassHive runtime collection | PASS: 957 passed, 3 declared live-only skips, 960 collected. Every file passed in a fresh process; a monolithic run was interrupted after accumulated test-owned background threads stopped making useful progress |
| Complete Glass Drive auth and server suite | PASS: 153 tests |
| Parent config compiler suite | PASS: 209 tests |
| Scheduling Cortex complete suite | PASS: 130 tests plus 8 subtests |
| LibreChat direct GlassHive/provider/callback/discovery matrix | PASS: 74 tests |
| LibreChat affected API matrix | PASS: 94 tests |
| LibreChat connected-account broker and route | PASS: 20 typed broker tests and 4 HTTP route tests; the exact route rerun completed in 2.76 seconds |
| LibreChat OpenAI/Anthropic initialization plus inference broker | PASS: 55 tests |
| Connected-account client and data-provider suites | PASS: 8 and 2 tests |
| LibreChat data-schema, data-provider, API, and client builds | PASS; pre-existing unrelated TypeScript warnings remain |
| GlassHive public compatibility contract | PASS as part of the complete runtime suite |

Automated evidence includes positive and negative OIDC/assertion/MCP OAuth cases, cross-owner access,
provider support gates, service-secret non-inheritance, leases, durable duplicate idempotency and
crash recovery, duplication bounds and symlinks, template dependency/account revalidation, Library
confirmation/revocation drift, owner conflicts, recurrence DST/coalescing and complete form/policy
validation, broker route/redirect/redaction controls, API/MCP parity, direct-conversation
compatibility, and configuration validation.

## Happy and Unhappy Path Classification

| Path | Result | Reason or remaining gate |
| --- | --- | --- |
| Local single-user account/workspace/Library/schedule management | PASS/PARTIAL | Visible workflows and one exactly-once local run-now occurrence pass; real external accounts and installed automatic scheduled execution remain outside this synthetic run |
| Hosted OIDC login/logout/denied-domain/revocation | BLOCKED | No candidate was installed behind a configured HTTPS IdP/proxy |
| Email signup/signin/reset/MFA | BLOCKED | Correctly delegated to the configured IdP; no hosted IdP tenant was changed |
| Multi-user personal Codex/Claude subscription | BLOCKED by design | Runtime returns `isolated_substrate_required`; UID/shared-process homes are not a sufficient security boundary |
| Local supported Codex native-home lifecycle | PASS/PARTIAL | Native command/home contract passed with a synthetic CLI; real subscription and worker mission remain open |
| Host-native macOS Claude consumer account | BLOCKED by design | Correctly shown as unsupported; it would share the current OS user's native account |
| Hosted Claude consumer login | BLOCKED by design | Requires provider permission or a supported contract |
| Brokered collaboration/document connection | BLOCKED | Source integration is present, but no real consent/account/worker invocation ran |
| External Codex and Claude MCP clients | BLOCKED | No installed public HTTPS MCP/OAuth origin was available |
| Library invalid/tampered/cross-user/reused confirmation | PASS automated | Real remote package adapter and upgrade rollback remain open |
| Duplicate unsafe links/bounds/secret state | PASS automated | Installed browser-profile inspection remains open |
| Recurrence fire/renewal/lease/exactly-once callback | PASS local source / PARTIAL installed | Browser run-now completed exactly once; real scheduler-to-GlassHive dispatch uses a fresh 90-second occurrence-bound assertion, lost-response retry creates one run, and the signed terminal callback reconciles the authoritative source ledger. Installed automatic user/delegation/grant renewal, provider lease, restart, and external delivery remain open |
| Standalone cron/RFC 5545/start/end/overlap/misfire/jitter | PASS source / PARTIAL installed | Complete source contract and UI/API/MCP/runtime tests pass, including a visible native run-now occurrence; no installed automatic fire/restart/DST run |
| Versioned workspace templates | PASS/PARTIAL | Browser save/instantiate/refresh and source dependency/account/idempotency tests pass; installed worker restart and real-account proof remain open |
| Installed direct conversation and channel/voice preservation | BLOCKED | Source compatibility passes; no candidate was installed into those user surfaces |

## Findings Fixed During User QA

1. Fresh workspace kind and tags were missing from one Glass Drive flattening path. The DTO and exact
   UI tests now preserve them.
2. Narrow mobile tabs were clipped. The navigation now wraps into two complete rows.
3. Provider-created credential files could retain a permissive native mode. Successful verification
   now normalizes files to `0600` and directories to `0700` without following symlinks.
4. SQLite WAL/SHM permission hardening had an unlink-versus-chmod race during test shutdown. Missing
   transient files are now tolerated while other permission failures remain fatal.
5. Duplicate previously risked materializing compute to establish a destination. The runtime now
   prepares storage and copies files without starting the worker.
6. Library grants lacked a safe removal path. Removal is now owner-scoped, ordered, confirmation
   protected, drift detecting, audited, and restores the prior bootstrap snapshot.
7. MCP advertised connection/account capability confirmation even though those owners correctly
   refused generic activation. The prepare tool is now explicitly Library-only; direct API attempts
   return structured conflicts with the broker/execution-policy route before creating pending state.
8. Configurable MCP and browser issuers could produce different hashed owners. Compiler and runtime
   startup now require issuer parity whenever ownership is derived from issuer + subject.
9. Standalone OIDC could be misconfigured to trust raw inbound identity headers. Startup now rejects
   that combination, and trusted-proxy browser writes reject cross-origin requests.
10. Human-confirmation scope was inferred from a URL suffix. It is now added only by the explicit
    confirmation endpoint call site. Configured login aliases are also canonicalized before any
    owner-scoped catalog/query so existing durable owner IDs remain usable.
11. Duplicate retries could create multiple destination workspaces after a lost response. A required
    idempotency key, durable reservation and request hash now provide exact replay, conflict on
    payload drift, crash recovery, and a preallocated destination without starting compute.
12. A configured OIDC role map previously recovered the write-capable member default for an unknown
    or missing claim. Configured maps now fail closed to viewer; deployments without a map retain the
    intentional member default.
13. Provider login subprocesses used a denylist and could inherit newly introduced service secrets.
    Setup now starts from a narrow networking/locale/tooling allowlist, uses the account-specific
    home, and regression tests inject multiple service-secret sentinels and prove none arrive.
14. The trusted enterprise inference origin boundary was implicit. Product truth and tests now state
    that the fixed HTTPS origin is operator-reviewed infrastructure, caller origin/header overrides
    are impossible, automatic redirects are disabled, and every upstream `3xx` is rejected.
15. Delegated Viventium recurrence previously queued a GlassHive run without returning its terminal
    result to the authoritative occurrence ledger. Per-occurrence signed callback routing, fail-before-
    mutation configuration checks, and an atomic fast-completion-safe run link now close that loop.
16. Lost scheduler responses and repeated dispatch could race a completed callback or duplicate work.
    Stable occurrence identities and atomic create-or-get/link operations now preserve one run and its
    terminal state across retry.
17. Provider-account runtime homes, duplicate symlink exclusions, short mission-lease heartbeats,
    recurrence fencing/DST edges, and `personal_required` loading/unavailable UI states were hardened
    through adversarial review and focused regressions.
18. Inference routing now requires the explicit feature flag and separate issuer secret, binds every
    grant to tenant/user/worker/run/model/adapter, uses the fixed Responses adapter for Codex, honors
    only operator-owned enterprise origins, rejects redirects before reading their bodies, and applies
    bounded timeouts and revocation.
19. Delegated recurrence previously transmitted the static scheduler secret at fire time. Scheduling
    Cortex now mints a fresh 90-second HMAC assertion bound to occurrence, task, tenant, owner,
    workspace, worker, and instruction hash; GlassHive rejects raw-secret-only, altered, future, and
    expired requests before mutation, while same-occurrence retry remains exactly-once.

The first local launch also inherited an installed runtime authentication configuration that did not belong
to the isolated test harness. Relaunching with the supported default-runtime-environment disable flag
produced the intended local configuration. No generated installed state was edited or treated as a
product fix.

## Independent Opus Review

Claude Code Desktop visibly ran Claude Opus 5 with Effort Extra in the Viventium project as a
review-only second opinion after Codex's evidence-backed implementation. The first pass found source
issues in MCP confirmation scope, browser/MCP owner parity, OIDC/raw-header configuration, provider
home isolation, recurrence ownership/idempotency/callback ordering, provider child environments, and
inference routing. Codex independently validated each finding, added regressions, fixed the surviving
issues, and reran the affected suites.

The post-hardening review returned `source_candidate_complete = true`, no remaining P0/P1, source
gate **GO**, and release gate **NO-GO**. Its final delta review directly inspected the Scheduling
Cortex assertion minter, GlassHive verifier and request model, dispatch call site, negative and
cross-component tests, and updated requirement/QA truth. It concluded that the former static-secret
fire-time caveat is closed correctly and minimally: the assertion is fresh, bounded, request-bound,
checked before mutation, raw-secret fallback is absent, and exact-occurrence replay remains safe
through the atomic idempotency reservation.

Opus recorded four nonblocking maintenance notes: the fire-time assertion is symmetric HMAC rather
than the asymmetric gateway identity format; there is no JTI replay cache because exact-request replay
is currently made harmless by occurrence idempotency; the reverse user-initiated GlassHive-to-Cortex
CRUD route still uses its raw service secret over HTTPS or exact loopback; and the wire constants are
duplicated across the two nested component boundaries. It also carried forward the hosted
trusted-proxy CSRF defense-in-depth decision and the explicit local single-user confirmation bypass.
None was classified as a source blocker. It correctly marked all Codex-executed counts, browser
evidence, and scans `cannot_confirm`; Claude's review remains supporting evidence, not a substitute
for the recorded user path and test runs.

## Delivery and Public-Safety Review

- Protected downstream client directories were treated as read-only compatibility context and were
  not modified, staged, committed, or used for public fixtures.
- Public candidate artifacts use neutral synthetic examples and source-available/FSL wording.
- No credential value, provider home, runtime database, raw log, private screenshot, personal email,
  local absolute path, or customer-specific workflow is included in this report.
- No commit, component pin, push, deployment, cloud mutation, or installed-runtime activation was
  performed. Therefore the nested-pin, clean-install, upgrade, rollback, and installed-artifact gates
  remain open.

## Remaining Acceptance Work

1. Install the candidate behind a synthetic hosted OIDC tenant and run allowed/denied/two-user,
   logout/revocation, key rotation, and proxy-boundary browser tests.
2. Provide a dedicated per-worker OS/container credential isolation substrate, then run two real
   accounts concurrently through setup, refresh writeback, mission, failure, reconnect, and removal.
3. Connect a synthetic collaboration/document account through the broker and prove read, confirmed
   write, renewal, revocation, and a worker-produced result.
4. Connect fresh real Codex and Claude MCP clients to the installed HTTPS OAuth resource and compare
   their owner-scoped model with the browser.
5. Run installed automatic schedule fires, restart/catch-up, user/delegation/grant renewal/provider
   lease, and cross-surface callback/activity correlation. Run installed template creation/instantiation across a
   worker restart with real account and Library dependency revalidation.
6. Resolve nested commit/pin provenance and run clean clone/install, upgrade, restart/restore,
   rollback, installed direct-conversation/channel regression, final privacy/license scan, and the
   protected downstream owner-run compatibility suite before release acceptance.
