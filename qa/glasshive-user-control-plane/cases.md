# GlassHive User Control Plane QA Cases

## Case ID Convention

Use stable `GHUCP-NNN` identifiers. These cases are the cross-feature acceptance gate; link to the
most specific existing QA owner when a scenario already has a detailed provider or runtime case.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `GHUCP-001` | `GH-UCP-001` | Existing public routes, MCP tools, bootstrap, callbacks, and direct conversations still work | API, MCP, Viventium | Compatibility tests + user regression | 2026-08-05 PARTIAL: focused source tests exist; installed user regression pending |
| `GHUCP-002` | `GH-UCP-002` | Allowed user signs in and returns to a secure session | Browser, IdP | Gateway tests + Playwright | 2026-08-09 PARTIAL: hosted local-factor login/refresh/restart/logout passed; real organization/IdP path remains open |
| `GHUCP-003` | `GH-UCP-002` | Denied, replayed, expired, or malformed login fails safely with recovery guidance | Browser, IdP | Gateway tests + Playwright | 2026-08-09 PARTIAL: hosted local failure/CSRF/closed-signup/flag-off rollback passed; broader IdP matrix remains open |
| `GHUCP-004` | `GH-UCP-003` | Runtime sees the correct user/tenant/role/scope and rejects cross-user or unsigned writes | Gateway, API | Assertion/API tests | 2026-08-05 PARTIAL: focused tests only |
| `GHUCP-005` | `GH-UCP-004` | User copies an official command and connects Codex and Claude to the hosted MCP | Browser, Codex, Claude | MCP OAuth tests + real clients | 2026-08-05 PARTIAL: metadata/command tests only |
| `GHUCP-006` | `GH-UCP-004` | Wrong audience, tenant, scope, expired token, or missing OAuth config fails loud | MCP clients, API | MCP OAuth tests | 2026-08-05 PARTIAL: focused tests only |
| `GHUCP-007` | `GH-UCP-005` | User connects, tests, selects, reconnects, disconnects, and forgets a personal provider account | Browser, MCP, native harness | Control-plane tests + real provider | 2026-08-06 PARTIAL: UI/MCP lifecycle plus native/broker observed-run, outcome, duration, and worker-reported-token tests pass; refreshed local browser and real provider pending |
| `GHUCP-008` | `GH-UCP-005` | Provider metadata and homes remain owner scoped and secrets never enter the runtime database | API, filesystem, DB | Control-plane tests + secret scan | 2026-08-05 PARTIAL: owner-scope tests plus local private-mode and credential-removal checks passed |
| `GHUCP-009` | `GH-UCP-006` | A mission uses only its selected compatible account and releases its lease | Worker, provider home | Mission tests + live worker | 2026-08-06 PARTIAL: focused source tests prove exact Docker config-home projection, rootless-worker ACL/access verification, stale-mount cleanup, short heartbeat recovery, and container/permission cleanup before lease release; real provider mission pending |
| `GHUCP-010` | `GH-UCP-006` | Required/busy/unsupported account states fail closed; preferred policy preserves legacy compatibility | Browser, worker | Mission/policy tests | 2026-08-06 PARTIAL: focused source tests prove the multi-user per-worker-container gate and unchanged preferred/legacy fallbacks; installed supported/unsupported platform matrix pending |
| `GHUCP-011` | `GH-UCP-007` | User creates and finds a private, human-named workspace | Browser, API, DB | Catalog tests + Playwright | 2026-08-09 PARTIAL: hosted local principal created and rediscovered one retained workspace; provider execution failed upstream and two-user path remains open |
| `GHUCP-012` | `GH-UCP-007` | Rename, favorite, resume, refresh, and restart preserve workspace identity and state | Browser, workspace desktop | Catalog/UI tests + restart QA | 2026-08-09 PARTIAL: hosted session/workspace catalog survived UI restart and local-auth rollback; compute/profile continuity remains open |
| `GHUCP-013` | `GH-UCP-008` | Duplicate creates a fresh identity and copies only approved files/context | Browser, filesystem | Duplicate tests + Playwright | 2026-08-05 PARTIAL: local browser duplicate-without-compute and automated file checks passed |
| `GHUCP-014` | `GH-UCP-008` | Unsafe links, oversized trees, secrets, cookies, leases, grants, and schedules are not copied | API, filesystem, DB | Duplicate security tests | 2026-08-05 PARTIAL: synthetic tests only |
| `GHUCP-015` | `GH-UCP-009` | User connects a service once and the selected worker uses it through the broker | Browser, broker MCP, worker | Broker cases + live worker | PENDING for this candidate |
| `GHUCP-016` | `GH-UCP-009` | Revoked, expired, missing, unavailable, rate-limited, empty, and unconfirmed-write states stay distinct | Browser, broker, worker | Broker failure tests + live probes | PENDING for this candidate |
| `GHUCP-017` | `GH-UCP-010` | User asks to add a Library item, reviews permissions, confirms once, and sees healthy status | Browser, Library, worker | Control-plane tests + Playwright | 2026-08-05 PARTIAL: local browser bootstrap activation and confirmed removal passed; live worker use pending |
| `GHUCP-018` | `GH-UCP-010` | Worker cannot self-authorize; hash/profile/dependency/expiry/rollback failures are actionable | Browser, Library, API | Control-plane tests + failure injection | 2026-08-05 PARTIAL: synthetic tests only |
| `GHUCP-019` | `GH-UCP-011` | Designed UI remains clear, accessible, responsive, and limited to the intended primary actions | Browser | Static tests + Playwright/accessibility | 2026-08-05 PARTIAL: desktop/mobile Playwright visual and interaction pass; keyboard/screen-reader matrix pending |
| `GHUCP-020` | `GH-UCP-012` | UI and MCP observe the same scoped resources, pagination, conflicts, and idempotent outcomes | Browser, API, MCP | API/MCP tests + parity run | PENDING |
| `GHUCP-021` | `GH-UCP-013` | User creates, lists, inspects, and disables recurring work with one explicit owner | Browser, MCP, scheduler | Recurrence tests + real fire | 2026-08-05 PARTIAL: local browser create/list/disable and recurrence suites pass; real fire pending |
| `GHUCP-022` | `GH-UCP-013` | Invalid timezone/DST/owner/overlap/misfire/catch-up input never produces duplicate or runaway work | Scheduler, DB | Recurrence tests + clock/restart QA | 2026-08-05 PARTIAL: synthetic tests only |
| `GHUCP-023` | `GH-UCP-014` | Fire time renews identity/grants, rechecks state, acquires account lease, and runs exactly once | Scheduler, broker, worker | Integration + real scheduled delivery | PENDING |
| `GHUCP-024` | `GH-UCP-015` | Viventium direct GlassHive conversations keep session, tools, activity, cancellation, and channels | Web, channel, voice, scheduler | Core-provider QA | PENDING for this candidate |
| `GHUCP-025` | `GH-UCP-016` | Cross-user access and public-data leakage fail closed across every surface | Browser, API, MCP, repo | Security tests + public scan | 2026-08-05 PARTIAL: synthetic scope tests only |
| `GHUCP-026` | `GH-UCP-017` | Nested source, parent pin, bootstrap, compiler, launcher, and installed process all identify one build | Installer, helper, runtime | Release/installer cases | 2026-08-09 PARTIAL: exact merged parent/nested provenance reached the installed canary and browser; clean public bootstrap remains open |
| `GHUCP-027` | `GH-UCP-017` | Fresh install, upgrade, restart, restore, and rollback preserve user state and compatibility | Installer, browser, runtime | Clean-room and continuity QA | 2026-08-09 PARTIAL: canary restart plus local-auth flag-off/session-revocation/re-enable passed; full clean install/upgrade/restore remains open |
| `GHUCP-028` | `GH-UCP-018` | Supported worker update preserves native skills/plugins/browser/project instructions and quality | Worker, browser, MCP | Preflight + wildcard QA | PENDING |
| `GHUCP-029` | `GH-UCP-018` | Catalog, setup, resume, duplicate, schedule, and delivery remain useful and responsive at scale | Browser, API, worker | Timing/load + quality scoring | PENDING |
| `GHUCP-030` | `GH-UCP-002`–`004`, `017` | Hosted browser, MCP, JWKS, and private runtime routes reach only their owning security contexts | Browser, edge, MCP, API | Route/header probes + real clients | 2026-08-09 PARTIAL: real hosted local login/CSRF-negative/stable-listener isolation passed; spoof and real MCP-client matrix remains open |
| `GHUCP-031` | `GH-UCP-003`, `017` | Runtime and workers can verify identity but cannot read the private signer key or mint assertions | Services, worker, filesystem | Security probes + key rotation | PENDING |
| `GHUCP-032` | `GH-UCP-007`, `017` | Existing state migrates from a rehearsed clone and a failed upgrade restores the verified database | Installer, DB, browser, MCP | Migration/restore harness + user QA | PARTIAL |
| `GHUCP-033` | `GH-UCP-017`–`018` | Runtime, MCP, and BFF cut over as one healthy release or not at all | Installer, edge, browser, MCP | Failure injection + full readiness | PARTIAL |

## `GHUCP-001` — Additive Compatibility Baseline

- Requirement: `GH-UCP-001`, `GH-UCP-015`.
- Risk covered: the control plane replaces or subtly changes an existing public or Viventium path.
- Preconditions: candidate nested source, parent checkout, and synthetic compatibility fixtures.
- Steps:
  1. Run the public compatibility suite and existing API/MCP/provider suites.
  2. Compare route schemas, MCP tool schemas, bootstrap materialization, callbacks, and lifecycle
     responses with the preceding supported release.
  3. Run a direct Viventium GlassHive conversation and a delegated workspace turn.
- Expected result: additive resources are available and every pre-existing contract still behaves as
  before. A valid worker-view signed link may still send only its narrow message/steer request when
  OIDC session CSRF protection is enabled. An authenticated watch session sends its current CSRF
  cookie value in `X-GlassHive-CSRF` for message, steer, lifecycle, and desktop mutations.
- Forbidden result: a renamed/removed field or tool, private fixture dependency, duplicate provider
  run, changed callback, direct conversation rerouted through MCP delegation, a valid signed link
  blocked by session CSRF, or a signed link bypassing CSRF for any other mutation.
- Evidence to capture: test summaries, schema diff, sanitized request/result shapes, visible direct
  conversation, worker audit, component/build provenance.
- Full-view evidence minimum: source + API + MCP + browser + direct conversation + installed artifact.
- Automation: `runtime_phase1/tests/test_public_compatibility_contract.py` plus owning suites.
- Last run: PARTIAL 2026-08-09; source compatibility, hosted-mode signed-link/CSRF regression, and
  authenticated-watch CSRF forwarding tests passed, while installed browser/channel regression
  remains open.

## `GHUCP-002` — OIDC Login Happy Path

- Requirement: `GH-UCP-002`.
- Risk covered: a valid user cannot enter the product securely or loses session continuity.
- Preconditions: hosted HTTPS deployment, configured OIDC client, IdP-assigned synthetic SSO user,
  provider-managed email/password user when that capability is advertised, and exact registered
  login/post-logout redirect URIs.
- Steps: open login, verify no public-signup action, start authorization, inspect PKCE/state/nonce,
  complete both the applicable organization SSO and provider-hosted email/password paths, land in
  Glass Drive, verify the visible current-user control, refresh, open a workspace, exercise local
  logout and provider account switching, and verify the session is revoked.
- Expected result: one stable principal is created from issuer+subject; secure session survives refresh;
  mutable profile values update without changing ownership; mapped browser roles synchronize both
  promotion and demotion; logout ends access and provider switching is truthful about IdP support.
- Forbidden result: identity keyed by email, token in URL/storage/log, missing PKCE/nonce/state, session
  fixation, or silent fallback to a local owner.
- Evidence to capture: browser network/DOM, sanitized cookie flags/claims, gateway logs, scoped DB rows.
- Full-view evidence minimum: real IdP browser path, refresh, logout, and backend principal match.
- Automation: `frontends/glass-drive-ui/tests/test_auth_gateway.py`, `test_auth_admin.py`, login UI
  tests, plus Playwright.
- Last run: PARTIAL 2026-08-09; the real hosted local factor passed visible login, refresh, canary
  service restart, logout, flag-off session revocation, re-enable, and reauthentication with no
  signup/reset surface. Organization/IdP login and its provider-hosted password path were not
  repeated in this isolated run and remain open for the complete case.

## `GHUCP-003` — Login Policy and Failure Paths

- Requirement: `GH-UCP-002`.
- Risk covered: enrollment or login policy fails open or leaves a user stranded.
- Preconditions: allowed and IdP-denied synthetic users; combined and split Entra app fixtures;
  closed principal enrollment; administrator-preapproved immutable subjects; controllable
  expired/replayed callback fixtures; and an optional local-password candidate initially staged
  disabled with a synthetic preapproved subject.
- Steps: try compile with an empty/invalid role map; verify combined and split app configurations;
  present missing, unmapped, and mapped roles through both browser OIDC and MCP OAuth; verify a
  shared combined app with assignment disabled still denies an unassigned principal through the
  mapped-role gate; then try IdP tenant/app-role denial, disabled enrollment, unknown subject,
  same email with two different subjects, public signup, missing config, wrong issuer/audience,
  nonce/state mismatch, reused callback, expired session, safe deep-link recovery, IdP outage, and
  rotated signing key. Run the installed preapproval wrapper twice from the sealed active release
  using an operator-only input, switch releases, and repeat against the preserved gateway database.
  With the optional local factor enabled only on the additive candidate, verify no signup/reset
  route, exact-subject provisioning over stdin, right/wrong/unknown/disabled/locked login parity,
  same-origin plus login-CSRF enforcement through the real edge, source/account throttling across
  restart, concurrent rotation, session refresh/logout, OIDC-session independence, and identical
  browser/MCP owner. Revoke local sessions, disable the flag, and prove old-binary rollback rejects
  the local cookie while OIDC remains healthy.
- Expected result: each case fails safely with useful retry/operator guidance; no runtime resources are
  created and no principal row is enrolled for a missing/unmapped role; a mapped role is accepted on
  both surfaces; the designed login page shows bounded retry/admin guidance without
  claims/codes/state; the administrator CLI is idempotent and returns only an opaque user ID; the
  same subject retains ownership across mutable-email changes while different subjects remain
  isolated; the installed wrapper runs under the gateway identity with both reviewed
  EnvironmentFiles and creates exactly one durable row; a disabled principal is reported as
  disabled rather than silently re-enabled; concurrent rollout/preapproval fails with retry guidance
  in both directions; a newly valid signing key works after bounded JWKS refresh. Local password
  state is Argon2id-only and gateway-private; generic failures do not enumerate accounts; successful
  login cannot reset a different account's source-throttle history; busy KDF capacity does not create
  a false lockout; and flag-off/rollback revokes only local sessions.
- Forbidden result: generic success, an unassigned tenant user admitted because registration is open,
  leaked claims, redirect loop, raw exception, user creation before validation, public signup/reset,
  plaintext/SHA password storage, email-based identity linking, password/session projection outside
  the gateway tier, an MCP password grant, or local-auth projection to runtime, workers, or
  LibreChat; generic/source-checkout Python touching the hosted auth database; or a
  successful preapproval message for a disabled account; or successful mutation of a rehearsal
  clone/state that rollback can overwrite.
- Evidence to capture: visible error/recovery copy, request status, one-shot unit properties and exit,
  sealed release revision, gateway logs, and presence/absence/count of scoped rows.
- Full-view evidence minimum: real browser failure state plus backend no-side-effect proof.
- Automation: compiler topology tests, gateway negative tests, MCP OAuth role-admission tests, plus
  Playwright failure injection plus `tests/release/test_glasshive_auth_admin.py`. Verify the
  compiler's canonical provider-email/enrollment settings override their legacy fallbacks, default
  closed when both are absent, and never project a password or mutable-email admission rule. Verify
  local-password config defaults off, has no LibreChat fallback, emits only gateway values, and the
  rollout preserves the three additive local-auth tables.
- Last run: PARTIAL 2026-08-09; the hosted local factor returned generic visible failure for an
  unknown synthetic account, rejected a missing login-CSRF pair at the real edge with `403`, kept
  signup/reset routes at `404`, and revoked the active local session when the feature was disabled.
  Compiler tests support combined/split topology and require a non-empty
  validated role map; browser and MCP tests reject missing/unmapped roles before enrollment; backend/DOM
  tests cover cancel, IdP denial, expired/replayed and invalid
  state, provider outage, wrong issuer/audience class, safe retry, disabled enrollment, deep-link
  recovery, signed-link exclusion, callback URL/log redaction, optional local Argon2id credentials,
  durable throttling, issuer/rotation concurrency, separate rollback sessions, malformed input, and
  absent signup/reset routes. The broader real hosted IdP denial/replay/expiry matrix remains pending.

## `GHUCP-004` — Signed Runtime Assertion, RBAC, and Delegation

- Requirement: `GH-UCP-003`.
- Risk covered: trusted gateway identity is widened, replayed, or replaced by caller headers.
- Preconditions: multi-user mode, dedicated signing key, member/viewer/admin/service fixtures.
- Steps: exercise read/write routes by role/scope; verify browser role promotion/demotion reaches an
  existing session while MCP cannot overwrite it; alter tenant/audience/subject/jti/expiry; omit
  JWKS; replay the same signed runtime assertion in one process and a second process sharing the
  state database; reuse a confirmation; disable the user/delegation; attempt cross-user access.
- Expected result: only authorized operations succeed; all altered, unsigned, expired, replayed, or
  cross-user operations fail closed without resource disclosure.
- Forbidden result: plain identity headers accepted in multi-user mode, symmetric shared user token,
  viewer write, cross-user `403` revealing existence, or browser token reused by scheduler.
- Evidence to capture: public JWKS, sanitized assertion claims, API status classes, audit rows.
- Full-view evidence minimum: gateway mint + runtime validation + DB/audit correlation.
- Automation: `test_internal_assertions.py`, gateway assertion tests, and delegated recurrence
  assertion/integration tests. The runtime-client regression also proves a fresh assertion header is
  generated for every upstream runtime request made by one browser BFF request.
- Last run: PARTIAL 2026-08-05; gateway/runtime assertions, bounded old/new public JWKS overlap and
  expiry, fresh occurrence-bound scheduler mint, tamper, expiry, raw-secret rejection, and
  idempotent retry pass; installed revoke/rotation paths remain.

## `GHUCP-005` — Connect Codex and Claude through MCP

- Requirement: `GH-UCP-004`.
- Risk covered: setup is confusing, client-specific, or works only with hidden local configuration.
- Preconditions: public HTTPS MCP origin, configured OAuth issuer, explicit token audience(s), the
  authorization server's full delegated scope value, explicit pre-registered Codex/Claude public-client
  IDs in the verifier allowlist, canonical public MCP resource, and fixed Codex/Claude callback ports
  plus the exact displayed callback URIs registered at the identity provider.
- Steps: open Connect AI, copy each official command or the versioned companion-skill instruction,
  add the server in a fresh Codex and Claude client profile, authenticate, list tools, create/list a
  synthetic workspace, inspect account/connection/Library operations, disconnect, and reconnect.
- Expected result: only fully configured/allowlisted client commands are shown; Codex includes its
  OAuth client/public-resource flags, fixed callback login override, and exact derived redirect URI;
  Claude includes its client/fixed-callback flags and localhost redirect URI; OAuth completes; both
  clients see the same user-scoped capabilities and actionable reconnect flow.
- Forbidden result: localhost command, static bearer token, cross-user list, hidden manual config,
  false “connected” state, or license claim inconsistent with repository metadata.
- Evidence to capture: visible command UI, redacted client config, OAuth metadata/challenge, tool list,
  scoped runtime rows.
- Full-view evidence minimum: browser command + two real clients + runtime authorization evidence.
- Automation: `test_mcp_oauth.py`, Connect AI UI tests, and real client runs.
- Last run: PARTIAL 2026-08-06; source tests prove exact pre-registered client flags, separate public
  resource/token-audience projection, both fixed callbacks, allowlist alignment, and hidden/action-required
  commands when verifier policy or registration is missing. Real clients pending.

## `GHUCP-006` — MCP OAuth Failure and Scope Paths

- Requirement: `GH-UCP-004`.
- Risk covered: token validation accepts a different resource/user/tenant or fails ambiguously.
- Preconditions: canonical public resource plus independent GlassHive ownership namespace, optional
  upstream token-tenant policy, and valid token/wrong audience, tenant, client, scope, expiry, key,
  and revoked-user fixtures.
- Steps: initialize MCP with each token; test missing/all-or-nothing OAuth config and non-HTTPS hosted
  origin; rotate keys; reconnect after expiration.
- Expected result: valid scoped token succeeds; invalid tokens receive a standards-based challenge and
  no tools/data; retry after valid reauthentication succeeds.
- Forbidden result: public URL implicitly reused as the Entra token audience, token passthrough from
  another application, weak resource comparison, owner from email, public HTTP hosted OAuth, or
  partial config silently disabling auth.
- Evidence to capture: protected-resource metadata, challenge header, sanitized verifier decision/log.
- Full-view evidence minimum: real MCP client failure/recovery plus verifier evidence.
- Automation: `runtime_phase1/tests/test_mcp_oauth.py`.
- Last run: PARTIAL 2026-08-05; synthetic verifier/metadata tests only.

## `GHUCP-007` — Personal Provider Account Lifecycle

- Requirement: `GH-UCP-005`.
- Risk covered: user-specific subscription setup is global, opaque, or irreversible.
- Preconditions: supported provider/platform, signed-in user, no existing personal account.
- Steps: create a labeled account through UI and MCP, complete either supported native subscription
  login or secure per-user API-key entry, test readiness, make default, inspect verified/last-used and
  truthfully observed usage metadata, reconnect or rotate after expiry, disconnect, confirm affected
  workspaces show action required, forget the disconnected metadata, and create a replacement at the
  active-account quota boundary. Disable account setup, then prove personal-only mode can be reversed
  when already active but cannot be newly enabled without a saved personal credential.
- Expected result: lifecycle is owner scoped, native, understandable, resumable, and never exposes a
  token; default selection affects only that user.
- Forbidden result: deployment-global credential changed, provider token/API key returned, logged, or
  stored in SQLite, setup attached to another account, disconnect leaves active authorization,
  disconnected metadata permanently exhausts quota, an active/in-use account can be forgotten, or
  policy-only recovery creates an unreachable personal-required state.
- Evidence to capture: browser setup/status, PTY/device transition, secret-free API/DB metadata,
  provider-home permissions, audit events.
- Full-view evidence minimum: real provider setup through visible UI and a subsequent worker mission.
- Automation: control-plane/provider setup tests plus real provider QA.
- Last run: PARTIAL 2026-08-06; focused UI/API/MCP tests prove connect/setup/test/reconnect/disconnect/
  forget parity, active-quota recovery, verification timestamps, and secret-free observed-use API/UI
  fields. Native and brokered dispatch tests prove run/outcome/duration accounting occurs after real
  worker dispatch rather than lease acquisition, token totals remain absent unless reported, and a
  v2 database migrates additively. Permission tests prove `0700` directories, normalized `0600`
  credential files, strict rootless-worker ACL verification, and credential-home removal. A refreshed
  local browser path, real approved provider, and subsequent mission remain open.

## `GHUCP-008` — Provider Isolation and Secret Boundary

- Requirement: `GH-UCP-005`, `GH-UCP-016`.
- Risk covered: one user's subscription or provider home is visible or usable by another.
- Preconditions: two synthetic principals and separate provider accounts/homes.
- Steps: list/get/setup/test/disconnect across users; inspect API, DB, workspace, logs, callback, and
  duplicate/export output; change home permissions; tamper opaque locator.
- Expected result: owner sees only their metadata; other user sees not found; homes are owner-only and
  external to workspaces; no raw credential appears anywhere inspected.
- Forbidden result: cross-user status difference reveals existence, locator traversal, token in DB/log,
  provider home copied to workspace, or permissive filesystem mode.
- Evidence to capture: scoped results, sanitized row counts/hashes, file mode, negative secret scan.
- Full-view evidence minimum: two-user browser/API attempt plus filesystem/DB/log scan.
- Automation: `test_control_plane.py` and provider setup tests.
- Last run: PARTIAL 2026-08-05; automated two-owner isolation plus local DB/filesystem secret-boundary
  checks passed. Hosted two-user browser and deployment-volume encryption remain open.

## `GHUCP-009` — Mission Account Binding and Exclusive Lease

- Requirement: `GH-UCP-006`.
- Risk covered: worker uses global/wrong credentials or concurrent refresh corrupts account state.
- Preconditions: ready personal account matching worker profile and a mission that lasts through a
  lease renewal interval.
- Steps: launch with selected account; inspect runtime environment/home; start a concurrent mission;
  allow token refresh; complete/fail/cancel the first run; start again; simulate stale lease.
- Expected result: only selected native home is projected; concurrent run gets actionable busy state;
  refresh writes back safely; lease releases on every terminal path; stale lease recovers.
- Forbidden result: global auth copied, wrong provider accepted, lease ends before mission, stuck lease,
  or second user obtains the account.
- Evidence to capture: worker command/env sans secrets, lease timeline, provider-home hash/metadata,
  run outcomes.
- Full-view evidence minimum: real native worker mission and concurrency/recovery proof.
- Automation: `test_mission_provider_accounts.py`.
- Last run: PARTIAL 2026-08-05; synthetic mission tests only.

## `GHUCP-010` — Account Policy and Platform Gates

- Requirement: `GH-UCP-006`.
- Risk covered: unsupported consumer auth is advertised or required personal auth silently falls back.
- Preconditions: required/preferred policy fixtures; missing, unready, incompatible, busy, and
  unsupported-platform accounts.
- Steps: launch each combination on supported and unsupported host/container modes.
- For an existing paused workspace, prepare an account switch from UI and MCP, review it in the
  browser, approve it, refresh, and repeat while a run, lease, incompatible account, disconnected
  account, cross-owner account, or changed review snapshot is present.
- Expected result: `personal_required` fails closed; `personal_preferred` uses ready personal auth and
  otherwise preserves the approved deployment path; unsupported/legal-gated paths show honest status.
- Forbidden result: silent provider substitution, optional policy drift, macOS multi-user Claude
  isolation claim without proof, copied owner-machine credential, self-confirmation by an AI, or a
  queued/running mission changing credentials underneath the run.
- Evidence to capture: policy resolution, visible failure/recovery copy, zero-run/no-side-effect proof.
- Full-view evidence minimum: browser selection + worker result on each supported platform class.
- Automation: mission/provider-platform tests plus `test_workspace_account_switch.py`.
- Last run: PARTIAL 2026-08-05; synthetic policy tests only.

## `GHUCP-011` — Create and Discover a Private Workspace

- Requirement: `GH-UCP-007`, `GH-UCP-011`.
- Risk covered: user cannot tell where work lives or accidentally reuses another/private workspace.
- Preconditions: signed-in user with empty catalog, then enough synthetic workspaces for pagination.
- Steps: create from the three-field launcher with a cold worker image; verify the request returns
  promptly to a starting watch surface and exactly one project/workspace/run exists; force
  a second cold-image preparation after the reviewed build input has become read-only and verify
  atomic replacement succeeds without partial input or temporary residue; build the digest-pinned
  base against the reviewed immutable Ubuntu snapshot, verify the package set is compatible, and
  require the exact snapshot provenance label before reuse; have the rootless worker fill its
  precreated private exit marker, verify the runtime identity can read it while the gateway identity
  cannot, and verify an empty marker remains unfinished across recovery; force
  auxiliary watch/link state unavailable, malformed, and writer-locked beyond the edge budget, then
  verify a bounded authenticated fallback without duplicate work; fail/cancel/interrupt the first
  run and verify the UI asks for a corrected follow-up without offering an ineffective Resume action;
  explicitly close a workspace and verify `terminating`, teardown-failed, and `terminated` states
  stay closed across stale runtime writers, pause/interrupt/resume, account switching, cached
  desktop/terminal access, already-open terminal/noVNC streams, recurring re-enable/run-now, API,
  browser, and MCP actions; race Close against the last external start boundary and prove no new
  compute starts afterward, while an accepted long stream has already persisted its runtime PID and
  Close remains prompt; race a delegated recurring create/enable against Close and prove either its
  definition is deactivated or failed compensation remains visibly retryable;
  restart the runtime while that first run is still queued and verify the same run is processed;
  verify fresh-by-default; rename; tag/favorite; search by human name; paginate; filter
  recent/readiness/state; try a second user.
- Expected result: human name is clear and editable; alias/id remain stable; catalog is scoped,
  searchable, cursor stable, and shows readiness/next run; empty state is useful.
- Forbidden result: raw internal ids as primary labels, cold image preparation blocking the browser
  request, a read-only staged build input making a safe retry fail, partial build input or staging
  residue, a mixed-snapshot package set or stale managed image satisfying provenance, watch/link
  storage corruption or contention consuming the edge deadline or returning a
  retry-inducing 500 after commit, a terminal run presented as resumable compute, a terminated
  workspace accepting work its queue cannot run, teardown failure or a stale writer reopening a
  workspace, group/world permission widening on worker workspace, home, browser, or provider state,
  an empty exit marker reported as success, cached or already-open desktop/terminal access after
  close intent, unknown orphan compute, a truncated provider stream reported complete, a closed recurring definition being
  re-enabled or left active in the delegated owner, duplicate project/workspace/run, a queued first run
  stranded after restart, automatic stale reuse, duplicate pagination, cross-user tile, or basic
  runtime UI replacing Glass Drive.
- Evidence to capture: browser screenshots/DOM, API cursors, DB ownership, launch/run audit.
- Full-view evidence minimum: real browser empty/create/search/rename plus scoped backend state.
- Automation: `test_workspace_catalog.py`, UI server tests, Playwright.
- Last run: PARTIAL 2026-08-09; local Playwright proved fresh ephemeral create, explicit Keep to
  named, human rename, refresh, and scoped backend state. A hosted authenticated watch action reached
  exactly one durable run, and a real rootless cold build of the corrected digest/snapshot package
  pairing completed with package, CLI, Python, Chromium, and driver checks. Post-restage worker
  execution reached the provider but exposed a rootless ownership mismatch on the worker-created
  exit marker. The corrected source precreates a private runtime-owned marker and passed the full
  runtime suite; a live rootless identity smoke proved worker write, runtime read, retained runtime
  ownership, and gateway denial. The strict multi-user ACL path also applied private access and
  default ACLs to a synthetic worker directory, let a newly created worker file remain readable by
  the runtime identity, and denied the gateway identity; missing ACL support now fails closed.
  The 2026-08-09 hosted local-factor run created exactly one synthetic workspace, rediscovered the
  same retained record after UI restart and a flag-off/on drill, and preserved its owner-scoped
  catalog entry. Its deployment-managed Codex run reached the provider boundary but failed
  truthfully with upstream `401 Unauthorized`; no personal account was substituted. Exact-commit
  successful worker completion, hosted two-user, and scale paths remain open.

## `GHUCP-012` — Resume, Refresh, and Restart Continuity

- Requirement: `GH-UCP-007`.
- Risk covered: a “persistent” workspace loses files, browser state, context, grants, or identity.
- Preconditions: named workspace with synthetic file, browser preference/session, context, approved
  grant, and paused compute.
- Steps: open (auto-resume), inspect state, edit file, pause, refresh UI, restart worker/runtime, reopen,
  expire an external session, and retry after reconnect.
- Expected result: same alias and approved state return; compute lifecycle does not delete persistence;
  expired external auth is explicit and recoverable.
- Forbidden result: new workspace silently created, files/browser/context lost, old tab keeps compute
  forever, or expired auth reported as successful empty data.
- Evidence to capture: visible desktop/files before/after, hashes, worker/home paths sanitized to logical
  ids, DB/grant state, lifecycle logs.
- Full-view evidence minimum: browser + refresh + process restart + backend/state correlation.
- Automation: specialized workspace/runtime cases plus Playwright.
- Last run: PARTIAL 2026-08-09; the real hosted local session survived a UI-service restart, and its
  retained workspace catalog record survived both that restart and the local-auth flag-off/on drill.
  Compute reaping, full runtime restart, browser-profile continuity, favorite, and external-auth
  recovery remain open.

## `GHUCP-013` — Safe Duplicate Happy Path

- Requirement: `GH-UCP-008`.
- Risk covered: duplicate aliases the source or copies too much/too little without telling the user.
- Preconditions: source workspace with regular files, nested directories, approved context, capability
  references, and an empty-source control.
- Steps: duplicate with an idempotency key, replay the exact request, conflict on key reuse with a
  different request, inject failure/retry, inspect new name/id/alias/profile/audit, compare regular
  files, inspect copy report; instantiate/replay a template; duplicate empty source.
- Expected result: fresh identity and browser profile; approved files/context copied; non-secret refs
  revalidated; explicit copied/skipped/zero counts; exact retries return one destination and never a
  second hidden project/workspace.
- Forbidden result: shared routing identity, source mutation, silent empty result, or inherited schedule.
- Evidence to capture: browser result, source/destination hashes, copy report, DB rows, grant decisions.
- Full-view evidence minimum: browser action plus filesystem/DB comparison.
- Automation: workspace duplicate/idempotency tests and UI duplicate path.
- Last run: PARTIAL 2026-08-05; local Playwright duplicated a named workspace into a fresh paused
  identity without starting compute, and automated filesystem/report checks passed. Template
  instantiation and installed browser-profile inspection remain open.

## `GHUCP-014` — Duplicate Security and Bounds

- Requirement: `GH-UCP-008`, `GH-UCP-016`.
- Risk covered: duplicate exfiltrates host files, provider auth, cookies, grants, or unbounded data.
- Preconditions: synthetic absolute/out-of-root/looping symlinks, special files, oversize/deep trees,
  browser profile, provider home, lease, grant, pending change, schedule, and audit entries.
- Steps: attempt duplicate for each unsafe input and inspect destination/transaction rollback.
- Expected result: unsafe trees fail before copy or roll back atomically; excluded secrets/state never
  appear; user receives bounded actionable failure.
- Forbidden result: partial unsafe copy, host-path disclosure, copied cookies/tokens/account home,
  inherited grant/schedule/audit, or source corruption.
- Evidence to capture: API failure class, destination absence/clean rollback, negative scans, audit.
- Full-view evidence minimum: filesystem attack fixtures + visible failure + DB transaction state.
- Automation: `test_workspace_catalog.py` security/bounds cases.
- Last run: PARTIAL 2026-08-05; synthetic filesystem tests only.

## `GHUCP-015` — Brokered Connection Happy Path

- Requirement: `GH-UCP-009`.
- Risk covered: GlassHive duplicates provider OAuth or host predicts the worker's plan.
- Preconditions: user-owned ready synthetic connection, workspace, and approved read capability.
- Steps: connect through existing broker UI; launch worker with factual capability context; let worker
  list/describe/invoke suitable tools; return result; revoke after completion.
- Expected result: broker owns tokens; workspace gets only compact context and narrow grant; worker
  chooses tool path; result and audit identify exact tool evidence without exposing secrets.
- Forbidden result: provider token copied to workspace, hardcoded provider plan, invented success
  criteria, worker bypasses broker, or host claims unsupported completion.
- Evidence to capture: browser connection/status, launch args, workspace MCP config, broker calls,
  worker output, host answer, DB/log audit.
- Full-view evidence minimum: real connected service + real worker + visible result.
- Automation: [capability broker cases](../glasshive-mcp-capability-broker/cases.md).
- Last run: PARTIAL 2026-08-06; source tests prove shared-OIDC opaque-principal create/re-login
  backfill without email fallback, operator-mapping fallback, two-user isolation, fresh direct
  UI/MCP grants, redacted readiness, in-memory-only projection, and terminal revoke. A real hosted
  two-user OIDC and connected-service worker run remains pending.

## `GHUCP-016` — Connection Failure, Renewal, and Write Confirmation

- Requirement: `GH-UCP-009`, `GH-UCP-014`.
- Risk covered: connection failure is laundered into empty data or a write occurs without confirmation.
- Preconditions: fixtures for expired/revoked/missing auth, provider down, timeout, rate limit, request
  rejection, unsupported config, successful-empty, and a write-capable tool.
- Steps: invoke each state; let a grant expire during a bounded run; attempt read-content without scope;
  attempt write before and after explicit human confirmation; retry after reconnect.
- Expected result: exact states remain distinct; bounded renewal succeeds only inside policy; reads and
  writes fail closed without scope/confirmation; reconnect succeeds without token exposure.
- Forbidden result: “nothing found” for an outage, worker self-authorization, stale unbounded grant,
  mutation before confirmation, or duplicated provider token store.
- Evidence to capture: visible copy, structured broker results, confirmation record, provider audit,
  absence/presence of mutation.
- Full-view evidence minimum: real user confirmation and real provider failure/recovery.
- Automation: broker policy/renewal tests and live provider probes.
- Last run: PARTIAL 2026-08-06; source tests prove action-required/broker-unavailable/unmapped
  separation, assertion tamper/expiry rejection, shared-cache nonce consumption/replay rejection,
  bounded grant scope, and revoke. Real provider
  outage/reconnect/write-confirmation QA remains pending.

## `GHUCP-017` — Add a Curated Library Item

- Requirement: `GH-UCP-010`.
- Risk covered: adding a skill/connector is manual, secret-bearing, or silently over-privileged.
- Preconditions: valid signed/hash-pinned synthetic manifest compatible with selected profile.
- Steps: ask worker/UI to add item; inspect manifest/provenance/scopes/dependencies; create pending
  change; confirm in browser; install through adapter; probe; grant workspace; use item; refresh.
- Expected result: one obvious flow explains permissions, requires one human confirmation, installs
  non-secret content, records version/hash, and shows healthy reusable status.
- Forbidden result: raw credentials in manifest, worker self-confirms, hidden shell instructions,
  global install, grant wider than reviewed, or success before health probe.
- Evidence to capture: manifest/hash, visible review/confirmation, adapter log, probe result, grant and
  audit rows, workspace usage.
- Full-view evidence minimum: browser confirmation + installed worker use + persisted Library state.
- Automation: control-plane pending-change tests plus profile-adapter and Playwright QA.
- Last run: PARTIAL 2026-08-05; local Playwright prepared and confirmed a bootstrap Library item,
  observed its workspace file and active grant, then confirmed removal and prior-state restoration.
  A real sourced adapter and worker invocation remain open.

## `GHUCP-018` — Library Failure, Upgrade, Disable, and Remove

- Requirement: `GH-UCP-010`.
- Risk covered: stale/tampered/incompatible Library state remains trusted or rollback loses workspace.
- Preconditions: hash mismatch, expired confirmation, wrong user, incompatible profile, missing
  dependency, failing probe, upgrade failure, removed provenance, and active grant fixtures.
- Steps: attempt add/confirm for each failure; retry; upgrade; disable; remove; inspect affected
  workspace; roll back partial adapter changes.
- Expected result: failures are typed and actionable; confirmation remains single-use/user-bound;
  rollback is safe; disabled/removed item cannot be invoked; workspace files remain intact.
- Forbidden result: tampered install, reused token, cross-user grant, partial global mutation, orphaned
  credential, or worker continuing with revoked capability.
- Evidence to capture: UI status, API decision, adapter transaction, filesystem diff, grant/audit state.
- Full-view evidence minimum: visible failure/recovery plus worker denial after revoke/remove.
- Automation: control-plane tests plus failure-injection adapter tests.
- Last run: PARTIAL 2026-08-05; synthetic pending-change tests only.

## `GHUCP-019` — Designed, Accessible Control-Plane UI

- Requirement: `GH-UCP-011`.
- Risk covered: functionality lands in an obsolete/basic UI or becomes dense/inaccessible.
- Preconditions: empty, populated, loading, degraded, narrow viewport, keyboard-only, and
  reduced-motion states.
- Steps: navigate Workspaces/Connections/Library/Schedules/Activity; create using the three primary
  fields; use secondary account/profile controls; search/rename/favorite; complete confirmation;
  inspect focus, labels, contrast, scroll, responsive layout, and refresh.
- Expected result: designed Glass Drive UI is coherent, human named, keyboard accessible, responsive,
  honest about readiness, and avoids unnecessary control clutter.
- Forbidden result: basic runtime UI as product, unlabeled controls, overlapping panels, trapped focus,
  inaccessible status, hidden blockers, or made-up provider readiness.
- Evidence to capture: full-page and narrow screenshots, accessibility tree, keyboard trace, network
  calls, persisted state.
- Full-view evidence minimum: real browser visual/interaction QA plus API/log/DB confirmation.
- Automation: UI static tests, accessibility checks, Playwright.
- Last run: PARTIAL 2026-08-05; complete Glass Drive auth/UI tests and real desktop/mobile Playwright
  navigation/interaction passed with no console errors. Hosted auth, keyboard, and screen-reader
  matrices remain open.

## `GHUCP-020` — UI, API, and MCP Parity

- Requirement: `GH-UCP-012`.
- Risk covered: each surface creates a separate model, store, or authorization rule.
- Preconditions: same synthetic user and resource set available to browser and MCP clients.
- Steps: create/list/update workspace/account/connection/Library pending change/schedule through one
  surface; inspect through the others; repeat idempotent mutation; test pagination/conflict/capacity.
- Expected result: all surfaces show the same owner-scoped resources, human names, structured states,
  and activity; retries do not duplicate work.
- Forbidden result: MCP bypasses confirmation, UI-only object, unbounded list, different owner scope,
  duplicate mutation, or raw internal error.
- Evidence to capture: correlated request/activity ids, response shapes, DB rows, visible UI/MCP output.
- Full-view evidence minimum: real browser and both MCP clients against one runtime.
- Automation: API/MCP/BFF tests plus parity script.
- Last run: PARTIAL 2026-08-05; a real in-process Cortex-to-GlassHive fire proves a fresh
  occurrence-bound assertion, lost-response retry produces one GlassHive run, and the signed terminal
  callback reconciles the authoritative occurrence. Integrated user/delegation/account/grant revocation,
  provider lease, installed clock fire, restart, and external delivery remain pending.

## `GHUCP-021` — Create and Manage Recurring Work

- Requirement: `GH-UCP-013`.
- Risk covered: schedule is acknowledged without durable creation or conflicting schedulers both fire.
- Preconditions: deployment explicitly configured for one recurrence owner and a named workspace.
- Steps: create daily and interval work from UI and MCP; list/detail/occurrences; inspect next run and
  timezone/DST policy; deactivate; verify one-shot compatibility and owner conflict.
- Expected result: one durable definition appears identically across UI/MCP/API; disabled definition
  stops future occurrences; other recurrence owner refuses creation.
- Forbidden result: natural-language-only acknowledgement, two owners, hidden timezone, schedule
  created against wrong workspace/user, or one-shot regression.
- Evidence to capture: visible UI/MCP result, definition/occurrence rows, owner config, scheduler logs.
- Full-view evidence minimum: real create + at least one fire + visible result + persisted ledger.
- Automation: recurrence store/API/MCP/UI tests plus a compiler-to-pinned-runtime contract probe:
  standalone enterprise deployments without a Viventium callback select `glasshive_native`, while
  callback-bearing Viventium deployments and explicit Scheduling Cortex integrations select
  `viventium_cortex`.
- Last run: PASS-AUTOMATED/PARTIAL 2026-08-08; recurrence/API/UI suites and the cross-layer
  native/delegated owner regression pass, and disabling a
  synthetic principal atomically deactivates its native definition and pre-fire work while
  transactional create/enable/manual-run/run-link guards close concurrent-disable races and leave
  other schedule classes untouched. Hosted admin-browser disable and a real clock fire are still
  required.

## `GHUCP-022` — Recurrence Time, Overlap, and Recovery Safety

- Requirement: `GH-UCP-013`.
- Risk covered: DST/misfire/restart causes skipped, duplicate, overlapping, or unbounded work.
- Preconditions: controlled clock around spring/fall DST, missed intervals, stale claim, slow run,
  invalid persisted definition, and restart.
- Steps: test invalid timezone/spec; advance through DST; miss multiple periods; restart after claim;
  attempt overlap; apply bounded catch-up/jitter; inspect immutable occurrences.
- Expected result: documented DST and coalescing policy is deterministic; occurrence key is unique;
  stale work recovers; invalid definition cannot block legacy one-shot work; catch-up is bounded.
- Forbidden result: duplicate occurrence, runaway herd, mutable history, permanent stuck claim, silently
  guessed timezone, or invalid recurrence stopping unrelated schedules.
- Evidence to capture: clock inputs, occurrence ids/states, claim leases, run mapping, scheduler logs.
- Full-view evidence minimum: deterministic tests plus at least one restarted real scheduler run.
- Automation: `test_recurring_schedules.py` and scheduling integration cases.
- Last run: PASS-AUTOMATED/PARTIAL 2026-08-06; direct latest-due regressions cover a 15-year-stale
  minutely RFC rule without linear walking and a month-end rule without changing `DTSTART` phase,
  RFC cadence/complexity is bounded, and existing DST/overlap/misfire/restart/exactly-once suites
  pass. Installed delayed-clock evidence remains.

## `GHUCP-023` — Fire-Time Authorization, Renewal, and Exactly-Once Run

- Requirement: `GH-UCP-014`.
- Risk covered: a future job reuses stale human credentials or silently falls back when access changes.
- Preconditions: recurring definition with delegated user, personal account, broker connection, Library
  grant, and controllable revoke/disable/busy/capacity states.
- Steps: let a valid occurrence fire; inspect new assertion/grant/lease; retry delivery; then revoke one
  prerequisite before each subsequent fire; restore and retry where policy allows.
- Expected result: valid fire runs once in correct workspace/account; each invalid prerequisite yields
  correct action-required/retryable/terminal outcome; no browser token or stale grant is replayed.
- Forbidden result: duplicate run, global credential fallback, disabled user execution, unbounded
  renewal, silently skipped occurrence, or success before worker result.
- Evidence to capture: assertion/grant metadata, occurrence/attempt/run ids, lease, broker calls,
  callback/activity, visible result.
- Full-view evidence minimum: real clock-triggered worker/provider/broker execution and retry controls.
- Automation: scheduler-runtime-broker integration plus live schedule QA.
- Last run: PASS-AUTOMATED/PARTIAL 2026-08-06; a disabled principal is rejected before any delegated
  run/schedule mutation, delegated definitions are owner/tenant-targeted, structured non-retryable
  action-required failures dispatch once, and retryable failures—including private-detail failure
  before network dispatch—stop at the bounded deterministic-attempt budget while lost-response retry
  still maps to exactly one GlassHive run. Native action-required fire validation likewise pauses its
  definition after one immutable occurrence. Real hosted identity/provider/grant renewal and visible
  installed delivery remain pending.

## `GHUCP-024` — Preserve Viventium Direct GlassHive Conversation

- Requirement: `GH-UCP-015`.
- Risk covered: user-control changes break the primary conversational agent or channel parity.
- Preconditions: installed Viventium with direct GlassHive provider, synthetic conversation, tools,
  schedule, channel, and voice prerequisites where available.
- Steps: converse across multiple turns; use broker-selected tool; cancel/reconnect; refresh; run a long
  channel turn; create schedule; run applicable voice control; compare provider/session/run audit.
- Expected result: one authored conversation session persists; LIFE and capability bootstrap remain
  authoritative; activity/cancel/reconnect/callback/channel behavior is unchanged.
- Forbidden result: conversation becomes delegated mission, duplicate harness run, lost session,
  missing tool projection, channel timeout regression, or control-plane account selection leaking in.
- Evidence to capture: visible conversations, provider session/run ids sanitized, activity/callback,
  channel/voice delivery, logs/DB, installed build.
- Full-view evidence minimum: installed web plus applicable channel/voice/scheduler paths.
- Automation: [core-provider cases](../glasshive-core-provider/cases.md) plus runtime provider tests.
- Last run: PENDING for this candidate.

## `GHUCP-025` — Multi-User and Public-Safety Boundary

- Requirement: `GH-UCP-016`.
- Risk covered: a second user sees resources or public artifacts reveal private/local information.
- Preconditions: two synthetic users/tenants and populated resources across every control-plane type.
- Steps: cross-user list/get/update/resume/duplicate/download/grant/confirm/schedule/activity/MCP calls;
  tamper ids/refs; scan diffs/docs/tests/reports/build output; inspect logs and signed-link handling.
- Expected result: no cross-user object disclosure or mutation; public artifacts contain only synthetic
  neutral values; sensitive URLs/credentials are absent/redacted.
- Forbidden result: owner id accepted from client, resource existence leak, raw signed URL/token,
  personal email, customer name, local path, machine id, raw DB/log, or private screenshot.
- Evidence to capture: two-user browser/API/MCP results, audit decisions, public scan, staged/build scan.
- Full-view evidence minimum: real two-user sessions plus repo/artifact/log scan.
- Automation: scope/security tests and public-boundary release tests.
- Last run: PARTIAL 2026-08-05; synthetic owner-scope tests exist, full two-browser/public-artifact scan
  remains open.

## `GHUCP-026` — Exact Source-to-Installed Build Chain

- Requirement: `GH-UCP-017`.
- Risk covered: source works but the parent pin, compiled output, launcher, or installed service is stale.
- Preconditions: nested component commit candidate and parent release candidate.
- Steps: verify nested clean commit/origin; update and inspect parent lock; bootstrap into a new path;
  compile; inspect generated config; start via supported launcher/helper; compare running provenance;
  run a focused browser/API smoke.
- Expected result: every layer identifies the same nested commit/config and visible feature exists in
  the installed process.
- Forbidden result: uncommitted nested source claimed shipped, stale parent pin, owner-machine leftover,
  generated file edited as source, or source-only test accepted as installed proof.
- Evidence to capture: commit/pin/provenance hashes, bootstrap/compiler/doctor summaries, process origin,
  installed browser/API result.
- Full-view evidence minimum: clean bootstrap through supported entrypoint and installed user smoke.
- Automation: release/bootstrap/compiler/installer suites plus provenance checks.
- Last run: PARTIAL 2026-08-09; merged parent `4d021f0258f92bdbc350c41655651de9b6c1b1ef`
  pins merged GlassHive `35c82be4275f72ec3019e19580003d8947cd73d5`, and the sealed canary `/health`
  plus the real browser surface reported that exact pair. A fresh public bootstrap/install in a new
  directory remains open.

## `GHUCP-027` — Clean Install, Upgrade, Continuity, and Rollback

- Requirement: `GH-UCP-017`.
- Risk covered: feature only works in a developed checkout or upgrade loses personal state.
- Preconditions: fresh public clone and prior supported installed version with synthetic user state.
- Steps: fresh install; create user/workspace/account metadata/connection/Library grant/schedule;
  upgrade; restart; resume; inspect all state; inject failed upgrade; roll back/recover; uninstall or
  cleanup via supported workflow.
- Expected result: clean install works without private dependency; upgrade preserves supported state;
  failure is transactional/recoverable; secrets remain outside git/install artifacts.
- Forbidden result: protected/private repo dependency, owner home credential required, state loss,
  duplicate scheduler, stale artifact, or destructive rollback.
- Evidence to capture: installer/doctor/browser results, before/after state hashes/counts, process/build
  provenance, recovery report, public scan.
- Full-view evidence minimum: fresh directory plus real installed browser and restart/upgrade path.
- Automation: installer, continuity, stable-runtime, and release-readiness suites.
- Last run: PARTIAL 2026-08-09; a real canary UI restart preserved the local session, and the reviewed
  flag-off rollback revoked that session and hid the form while keeping organization sign-in and
  stable-listener behavior intact. Re-enabling restored login and the existing workspace record.
  Fresh install, full upgrade, database restore, and preceding-binary rollback remain open.

## `GHUCP-028` — Worker/Bootstrap Upgrade without Capability Loss

- Requirement: `GH-UCP-018`.
- Risk covered: “latest” worker removes native tools, authentication, browser support, instructions, or
  produces a lower-quality result.
- Preconditions: current pinned and candidate supported CLI/bootstrap versions and official docs.
- Steps: compare versions/capabilities; upgrade through existing requirement mechanism; run native
  skills/plugins, project instructions, effort, browser/computer, MCP broker, file/artifact, pause/resume,
  and wildcard work; compare outcome quality/performance; roll back.
- Expected result: candidate is source-backed, capability-equal or better, compatible, reversible, and
  meets the universal self-check/final-report contract.
- Forbidden result: ad hoc global upgrade, unsupported flag, native capability hidden by generic MCP
  inventory, prompt-specific workaround, or speed win with lower quality.
- Evidence to capture: official source links, version/preflight, capability matrix, wildcard results,
  artifacts, browser/network, logs, timing/quality score.
- Full-view evidence minimum: real candidate worker in clean installed runtime with rollback proof.
- Automation: runtime requirement/preflight tests and GlassHive Standard QA wildcard cases.
- Last run: PENDING.

## `GHUCP-029` — Enterprise Scale and Core Outcome Metric

- Requirement: `GH-UCP-018`.
- Risk covered: control plane is correct for one user but slow, confusing, or unreliable under normal
  enterprise catalogs and concurrent use.
- Preconditions: synthetic multi-user dataset with paginated workspaces/accounts/connections/Library
  items/schedules and bounded concurrent runs.
- Steps: measure login, catalog/search, create, resume, duplicate, provider setup transitions, MCP
  connection, schedule claim/fire, result delivery, conflict/capacity, retry, and recovery; score result
  quality and UI clarity.
- Expected result: bounded responsive lists, no cross-user leakage, stable ordering/cursors, useful
  blockers, no thundering herd, and Quality + Performance parity across UI/MCP paths.
- Forbidden result: unbounded query/render, relaunch loop, quota advice that suggests profile switching,
  duplicate occurrence, stale UI, or faster but less truthful/useful result.
- Evidence to capture: sanitized timings/percentiles, query/run counts, resource use, visible UX,
  quality rubric, failure/recovery outcomes.
- Full-view evidence minimum: browser + MCP load on installed candidate with logs/DB/metrics.
- Automation: bounded load harness plus real-user QA.
- Last run: PENDING.

## `GHUCP-030` — Hosted Edge Route and Trusted-Header Boundary

- Requirement: `GH-UCP-002`, `GH-UCP-003`, `GH-UCP-004`, `GH-UCP-017`.
- Risk covered: browser authentication intercepts MCP/JWKS, untrusted identity reaches an upstream,
  or the runtime API is publicly exposed.
- Preconditions: candidate hosted behind its intended HTTPS identity proxy and path-aware edge.
- Steps: exercise `/`, `/mcp`, protected-resource metadata, public JWKS, and direct runtime paths with
  no session, an allowed session, an MCP token, and spoofed identity headers. Through the public
  browser edge, perform an authenticated state-preserving mutation with the real CSRF cookie/header
  pair and a spoofed identity header on the same request; inspect owning service logs and the
  canonical subject that actually authorized the mutation. From the authenticated watch surface,
  submit a steer, a queued message, and one reversible lifecycle action; replay a mutation with the
  header absent and with a mismatched value.
- Expected result: browser routes reach BFF through login; MCP metadata/challenges reach MCP directly;
  JWKS is public; runtime has no public route; the edge removes client identity headers, preserves
  only the declared browser `X-GlassHive-CSRF` double-submit token across its prefix scrub, and injects
  only verified stable-subject identity. The three authenticated watch actions each mutate once;
  absent or mismatched CSRF pairs return `403` without runtime mutation.
- Forbidden result: MCP/JWKS receives an HTML login redirect, one catch-all BFF upstream, raw client
  identity accepted, the CSRF header is scrubbed or bypassed, any other prefixed client header
  survives, email is used as durable owner id, or the runtime port/path is public.
- Evidence to capture: sanitized edge config, response/status/content types, challenge headers,
  upstream logs, spoof probes, and negative external reachability.
- Full-view evidence minimum: real hosted browser plus real MCP client and edge/runtime correlation.
- Automation: deterministic route/header contract probes plus Playwright and external MCP smoke.
- Last run: PARTIAL 2026-08-09; the real public canary accepted the browser's login-CSRF pair and
  rejected a same-origin login POST without it at `403`; organization sign-in remained available
  while local auth was disabled, and the stable listener retained its existing `302` behavior.
  Identity-header spoof probes, runtime reachability, and real Codex/Claude MCP clients remain open.

## `GHUCP-031` — Signer/Runtime Key Isolation

- Requirement: `GH-UCP-003`, `GH-UCP-017`.
- Risk covered: compromising a runtime or worker permits assertion minting.
- Preconditions: separately isolated BFF/MCP signer contexts and runtime/worker verifier contexts.
- Steps: inspect service users, mounts, descriptors, and sanitized environments; from runtime and a
  worker attempt to stat/read the private key and mint an accepted assertion; verify JWKS validation;
  rotate keys with bounded public overlap and refresh.
- Expected result: signer contexts alone can read the private key; runtime/worker cannot discover or
  read it or mint an accepted assertion; verification and rotation remain available.
- Forbidden result: shared readable key volume/user, key path or value in runtime/worker env/log/build,
  mode `0600` treated as isolation under a shared Unix account, or rotation outage caused by copying
  private material into a verifier.
- Evidence to capture: sanitized user/mount/permission/env inventories, denial results, JWKS ids,
  rotation timeline, accepted/rejected assertion audits.
- Full-view evidence minimum: installed service and real worker proof, not source configuration alone.
- Automation: runtime key-refusal and launcher verifier-only tests plus installed isolation probes.
- Last run: PENDING; focused source guards pass, installed OS/container isolation is unproven.

## `GHUCP-032` — Existing-Database Migration Rehearsal and Restore

- Requirement: `GH-UCP-007`, `GH-UCP-017`.
- Risk covered: the first migration occurs on live state, WAL data is lost, concurrent versions write
  one database, or rollback reuses an incompatible mutated database.
- Preconditions: preceding supported runtime with synthetic users, workspaces, accounts, grants,
  schedules, occurrences, and WAL-backed state.
- Steps: quiesce writers; create and restore-test a consistent backup; clone and rehearse migration;
  compare schema ledger/receipt, `quick_check`/`integrity_check`, `foreign_key_check`, invariant row
  counts, and owner/tenant samples; seed a pending callback, queued run, and due schedule, emit a new
  callback during candidate acceptance, and prove the rehearsal clone keeps both callback records
  pending and otherwise stays passive; cut over; verify browser/MCP persistence and that live resumes
  each eligible item once; inject failure and restore both preceding artifact and pre-upgrade database/state.
- Expected result: rehearsal passes before live open, exactly one version writes at a time, all checks
  and user-visible state survive, and failed upgrade recovery reopens the preceding healthy state.
- Forbidden result: first rehearsal on live DB, file copy that omits committed WAL, concurrent old/new
  writers, callback/schedule/queue side effects from cloned rehearsal state, binary-only rollback
  with a mutated incompatible DB, or unexplained row/owner drift.
- Evidence to capture: quiesce proof, backup/restore ids, integrity/FK/schema/count summaries,
  sanitized before/after samples, process provenance, and reopened browser/MCP state.
- Full-view evidence minimum: clone rehearsal plus installed cutover and injected restore path.
- Automation: schema-ledger tests and `tests/release/test_glasshive_systemd_rollout.py`.
- Last run: PARTIAL; the portable WAL backup, clone rehearsal, invariant, failure-injection, and
  database-restore harness passes on macOS and clean Debian. Installed migration/browser/MCP restore
  evidence is unrun.

## `GHUCP-033` — Atomic Three-Service Cutover and Readiness

- Requirement: `GH-UCP-017`, `GH-UCP-018`.
- Risk covered: ingress points to a mixed or partially healthy runtime/MCP/BFF group, or a sealed
  release retains absolute editable-package paths into the temporary staging directory and cannot
  import its runtime/BFF modules after the atomic rename.
- Preconditions: preceding healthy release, immutable staged candidate, controllable failure points.
- Steps: fail dependency staging and each service start/readiness in turn; verify ingress and preceding
  group; inspect both staged environments after the atomic rename and import their owning packages
  from the final release path; then start the complete candidate and run runtime health, nested BFF health, MCP metadata and
  unauthenticated/authenticated initialize, browser login/designed-root, public JWKS, spoof-header,
  and negative runtime-exposure probes.
- Expected result: no ingress switch or orphaned/mixed-version service occurs on any failure; all probes
  pass before successful cutover; rollback restores the complete preceding release.
- Forbidden result: editable `.pth` files that reference a vanished staging path, generated bytecode
  that embeds a temporary probe path, PID-only success, warning followed by zero exit, MCP omitted
  from readiness, new
  runtime with stale UI/MCP, ingress switched before readiness, or candidate residue after failure.
- Evidence to capture: staged artifact/env hashes, service provenance, readiness responses, ingress
  target, failure cleanup, authenticated browser/MCP smoke, and rollback result.
- Full-view evidence minimum: real installed failure injection and successful atomic cutover.
- Automation: launcher hard-readiness tests plus `tests/release/test_glasshive_systemd_rollout.py`.
- Last run: PARTIAL; a real hosted side-by-side start on 2026-08-08 caught absolute editable package
  paths surviving the staging rename before ingress. The helper now relativizes the generated source
  path and proves both packages import after physically relocating the staging tree; the focused
  41-case rollout suite passes. Post-fix hosted start, browser identity, authenticated MCP,
  process-loss recovery, and rollback remain unrun.

## Natural User Use Case Checklist

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `GHUCP-UC-001` | Sign in with organization SSO, provider-hosted email/password, or the optional admin-provisioned local factor; refresh and log out; confirm public signup/reset is absent | `GH-UCP-002` / `GHUCP-002`–`003` | Real browser + IdP/local candidate | Gateway logs, principal/session state | Secure entry, one immutable owner, and clear closed-enrollment policy/recovery | PARTIAL: hosted local-factor login/refresh/restart/logout/rollback passed; organization/IdP path remains open |
| `GHUCP-UC-002` | Connect personal Codex/Claude and choose it for one mission | `GH-UCP-005`–`006` / `GHUCP-007`–`010` | Browser + native worker | Provider home, lease, worker audit, DB | Only that user's selected account is used | PARTIAL: local browser synthetic-native lifecycle passed; real worker mission pending |
| `GHUCP-UC-003` | Create, find, rename, favorite, resume, and duplicate a workspace | `GH-UCP-007`–`008` / `GHUCP-011`–`014` | Glass Drive + desktop | API/DB/files/browser state | Human-named persistent workspace and safe copy | PARTIAL: local browser create/Keep/rename/duplicate passed; restart/favorite pending |
| `GHUCP-UC-004` | Connect a service and let a worker use it | `GH-UCP-009` / `GHUCP-015`–`016` | Browser + broker + worker | Grant, tool calls, output, logs | Worker chooses a real scoped tool path | PENDING |
| `GHUCP-UC-005` | Ask to add, update, disable, and remove a Library item | `GH-UCP-010` / `GHUCP-017`–`018` | Browser + worker | Manifest/hash, pending change, adapter, grant | Human-confirmed reusable capability | PARTIAL: local browser add/remove passed; update/worker use pending |
| `GHUCP-UC-006` | Copy MCP command into Codex and Claude and manage the same workspace | `GH-UCP-004`, `012` / `GHUCP-005`–`006`, `020` | Browser + both clients | OAuth metadata, tools, API/DB | One scoped model across clients | PARTIAL: source tests only |
| `GHUCP-UC-007` | Create recurring work, wait for fire, inspect result, then disable | `GH-UCP-013`–`014` / `GHUCP-021`–`023` | Browser + MCP + scheduler | Definition/occurrence/run/grant/lease/callback | Exactly one authorized visible result | PARTIAL: local browser create/disable passed; real fire pending |
| `GHUCP-UC-008` | Continue an ordinary Viventium direct GlassHive conversation | `GH-UCP-015` / `GHUCP-024` | Installed web/channel/voice | Provider session, activity, callback, logs/DB | Existing conversation behavior is intact | PENDING |
| `GHUCP-UC-009` | Try missing auth, denied domain, cross-user ids, busy account, revoked connection, dependency outage, retry, cancel, and capacity | All / matching unhappy-path cases | Every real surface | Structured failures, no-side-effect state, audit | Honest actionable failure with no leak/fake success | PENDING as a complete matrix |
| `GHUCP-UC-010` | Install fresh, upgrade, restart, reopen, and roll back | `GH-UCP-017` / `GHUCP-026`–`027` | Public installer + installed browser | Pin/build/process/state provenance | Same feature and user state on installed artifact | PENDING |
| `GHUCP-UC-011` | Stage, migrate, cut over all three services, verify every route, and roll back without state loss | `GH-UCP-017` / `GHUCP-030`–`033` | Hosted edge + installed services | Route/key/DB/readiness/provenance evidence | One secure complete release or the preceding healthy release | PENDING |

## Incident Promotion Checklist

- [ ] Reproduce with neutral synthetic data.
- [ ] Add the escaped failure as a stable `GHUCP-` case or link a narrower existing owner.
- [ ] Record expected and forbidden results, including the exact structured failure class.
- [ ] Add deterministic automated coverage where possible.
- [ ] Run the real browser/MCP/provider/scheduler/installed path affected by the incident.
- [ ] Save only public-safe evidence and link the dated report.
