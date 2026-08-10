# 55. GlassHive User Control Plane and Persistent Workspaces

## Status

The source is **merged and locally validated, with hosted acceptance still pending**. The additive
control plane, designed Glass Drive UX, local user journeys, and affected automated suites are present.
Hosted identity, real external provider/connector consent, multi-user personal-subscription isolation,
real external MCP clients, full standalone recurrence/template scope, installed-runtime provenance,
clean install, and upgrade continuity remain explicit gates. This document is therefore the product
truth and traceability source, not a claim that those hosted or external gates passed.

## Target Outcome

An authenticated enterprise user can use the designed GlassHive UI or a standards-based MCP client to:

- create, find, rename, resume, duplicate, and schedule private persistent workspaces;
- choose a personal Codex or Claude subscription for that user's missions without changing another
  user or the deployment-wide default;
- connect user-owned data accounts through supported worker-native setup or, when configured, the
  optional existing capability broker;
- inspect and add reusable skills, plugins, and connectors through a curated Library with explicit
  human approval;
- return to the same files, browser profile, worker context, account references, and approved
  capabilities later; and
- keep existing GlassHive HTTP/MCP/bootstrap contracts and Viventium's direct GlassHive conversation
  provider intact.

The Core Outcome Metric from [01_Key_Principles.md](01_Key_Principles.md) applies to every path:
Quality (Intelligence, Relevance, Usefulness, Alignment) + Performance (Fast, Smooth, Reliable).

## Owning Boundaries

This document is the cross-feature control-plane index. It does not replace the detailed owners:

- workstation, worker, workspace, browser, provider, and deployment behavior:
  [48_GlassHive_Workstation_Sandbox_Runtime.md](48_GlassHive_Workstation_Sandbox_Runtime.md);
- MCP and OAuth provider behavior: [07_MCPs.md](07_MCPs.md);
- schedule delivery behavior: [11_Scheduling_Cortex.md](11_Scheduling_Cortex.md);
- workflow approval and isolated-worktree behavior:
  [51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md](51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md);
- installer, component pin, generated artifact, and runtime activation:
  [39_Installer_and_Config_Compiler.md](39_Installer_and_Config_Compiler.md) and
  [50_Stable_Dev_Runtime.md](50_Stable_Dev_Runtime.md);
- public/private and licensing boundaries:
  [40_Public_Private_Boundaries_and_License_Matrix.md](40_Public_Private_Boundaries_and_License_Matrix.md).

GlassHive remains the generic worker/workspace runtime. Viventium may broker identity, capability,
conversation context, and schedule ownership without teaching the worker a prompt-specific plan. The
worker harness remains responsible for choosing and executing the work. The host remains a faithful
courier of the user's goal, explicit constraints, factual context, and verified capabilities.

## Product Vocabulary

- **User**: the authenticated human principal, stable by identity-provider issuer and subject.
- **Workspace**: the user-visible persistent environment. Internally it may reference a project,
  worker, sandbox, filesystem, browser profile, and provider-account bindings.
- **Worker**: the Codex, Claude, or other supported intelligent agent runtime inside a workspace.
- **Provider account**: a user's Codex or Claude subscription/runtime home. It is not a data
  connection.
- **Connection**: a user-owned data or service account exposed through the existing capability
  broker, such as a document or collaboration service.
- **Library item**: versioned, non-secret skill/plugin/connector metadata and installation material.
- **Grant**: a user-approved relationship allowing one workspace to use a provider account,
  connection, or Library item.
- **Pending change**: a time-bounded, single-use request awaiting human confirmation.
- **Recurring definition**: an editable schedule intent. An **occurrence** is an immutable fire-time
  execution record.

## Architecture and Trust Boundaries

```text
browser / MCP client
        |
        v
identity provider -- Auth Code + PKCE / OAuth resource token
        |
        v
Glass Drive gateway / MCP verifier -- session, CSRF, domain, tenant, resource, scopes
        |
        v
short-lived signed internal assertion
        |
        v
GlassHive runtime -- user-scoped workspaces, accounts, templates, Library, activity
        |                    |
        |                    +-- provider-home lease -> native Codex/Claude harness
        |
        +-- optional narrow grant -> user-scoped capability broker -> connected service
        |
        +-- optional inference grant -> LibreChat credential owner -> fixed upstream adapter

recurrence owner -- glasshive_native, or optional Scheduling Cortex integration
        |
        +-- idempotent dispatch -> GlassHive workspace/run
```

The browser gateway, runtime, and provider homes are distinct trust domains. The capability,
inference, and Scheduling Cortex bridges add separate trust domains only when configured. Identity
data and authorization assertions may cross these boundaries; raw provider tokens, browser cookies,
and deployment credentials may not.

### Hosted public edge and process topology

Hosted multi-user GlassHive uses one HTTPS origin with explicit path ownership:

- browser routes, including `/`, pass through the verified browser identity proxy and terminate at
  the Glass Drive BFF (current loopback port `8780`);
- `/mcp` and `/.well-known/oauth-protected-resource/mcp` bypass browser-session middleware and
  terminate at the MCP service (current loopback port `8767`), whose OAuth resource verifier returns
  standards-based metadata and `401` challenges rather than an HTML login redirect;
- `/.well-known/jwks.json` terminates at the BFF without a browser session because it publishes
  public verification keys; and
- the runtime API (current loopback port `8766`) has no public ingress route and is reachable only
  over loopback, a private service network, or mutually authenticated transport.

The edge removes every client-supplied privileged `X-Viventium-*`, `X-GlassHive-*`, and
`X-LibreChat-*` header before injecting identity derived from the verified proxy session. The
browser route captures and restores only the BFF's `X-GlassHive-CSRF` double-submit token across
that scrub; it never restores an identity or service header. The authenticated watch client reads
the current session CSRF cookie for each state-changing request and sends the matching header for
message, steer, lifecycle, and desktop actions; missing or stale pairs remain fail-closed. The stable IdP
subject/`oid`, not email, is the canonical user id. A single catch-all upstream to the BFF is not a
compliant hosted topology.

## Requirements

### `GH-UCP-001` — Additive compatibility baseline

- Existing public HTTP routes, request/response fields, MCP tools, tool fields, bootstrap bundle
  shapes, callbacks, direct-conversation routes, and lifecycle semantics remain compatible.
- New control-plane APIs and UI are additive. No prompt, person, provider label, customer, or local
  machine path becomes a runtime branching key.
- Protected or private downstream work is used only as read-only compatibility input. Public tests,
  docs, fixtures, and screenshots use neutral synthetic data.
- A worker/toolchain upgrade is accepted only after the compatibility, native-capability,
  clean-bootstrap, browser, and installed-artifact gates pass.

### `GH-UCP-002` — Human login and enrollment policy

- Hosted multi-user deployments use an external OIDC identity provider with Authorization Code,
  PKCE S256, `state`, `nonce`, replay protection, issuer/audience validation, JWKS refresh, secure
  cookies, CSRF protection, logout/revocation handling, and bounded login/callback rate limits.
- When LibreChat reuses OpenID bearer tokens for protected APIs, it pins the exact configured issuer,
  explicit API audience, and `RS256` before its callback runs, then reapplies the current allowed-domain
  and required-role admission gates on every authentication. A valid signature from the same JWKS is
  insufficient when issuer, audience, algorithm, role, or domain policy differs.
- The durable principal is derived from issuer + subject. Email and display name are mutable profile
  attributes, never authorization keys.
- Public email/password signup, reset, MFA, invitation, and account recovery are delegated to the
  configured identity provider. GlassHive may additionally enable a default-off, gateway-owned local
  password credential for an administrator-preapproved exact OIDC issuer + subject. Email is only a
  normalized credential locator and never discovers, merges, or owns a principal. The verifier is a
  versioned Argon2id PHC in the gateway-only auth database; raw passwords never enter config, argv,
  logs, runtime state, worker homes, or MCP. Provisioning/rotation/unlock/disable use the locked
  gateway one-shot over bounded stdin. The deployment secret manager generates the credential; the
  gateway enforces at least 24 characters and 12 distinct characters without claiming a tiny literal
  list is a comprehensive compromised-password corpus. Public signup and reset routes remain absent.
- Local-password browser sessions use a separate session table understood only by releases that
  support the feature. Disabling the feature rejects and revokes those sessions without affecting
  OIDC sessions; rollback to an older OIDC-only release requires the supported revoke-local-sessions
  one-shot before activation. The local factor bypasses IdP MFA/Conditional Access for this GlassHive
  browser entry only, so it is an explicit deployment policy—not a claim of IdP-managed assurance.
  MCP remains OIDC OAuth and resolves the same issuer + subject principal.
- Provider-hosted organization SSO and provider-hosted email/password are two entry methods into the
  same OIDC issuer + subject identity. `provider_email_login` controls only truthful login-page
  capability copy; it never enables a GlassHive credential form or changes authorization.
- Operators can enable or disable GlassHive principal enrollment. `runtime.auth.allowed_domains`
  applies to LibreChat/local email signup and login; GlassHive OIDC admission is enforced by the
  IdP's tenant and app-role/group assignment policy, never by mutable `email` or
  `preferred_username` claims. Multi-user compilation requires a non-empty role map. Entra may use
  one app registration for both confidential web sign-in and the exposed API resource, or separate
  web and API registrations. Every enterprise application actually used must require assignment,
  or an equivalently reviewed and tested deny-by-default gate. In combined mode roles and
  assignments are defined once; in split mode the same role values and assignment policy apply to
  both. `allow_principal_enrollment` never admits an otherwise unassigned tenant user and never
  enables public signup. With enrollment closed, an administrator may idempotently preapprove an
  exact provider subject through the gateway-only CLI. The subject must come from the configured
  issuer; email is display metadata and is never used to find, merge, or authorize the principal.
  Both GlassHive-specific controls default false when neither their canonical key nor an explicitly
  configured one-release legacy fallback is present.
- `local_password_login` is a separate GlassHive-specific, default-false capability and never falls
  back from LibreChat auth settings. `local_password_allowed_domains` constrains credential locators
  only. The compiler emits a stable gateway-only HMAC key for source throttling and never projects
  the PHC or local session material outside the existing gateway tier. The UI and public MCP service
  already share that gateway OS identity/environment boundary; the MCP protocol exposes no password
  grant and MCP clients receive none of these values. LibreChat, runtime, and workers receive none of
  the local-auth flag, locator allowlist, HMAC key, PHC, or session material. Unknown, wrong,
  disabled, and locked credentials return the same public failure; durable
  account/source throttles survive restart, bounded Argon2 capacity returns retry guidance without
  charging a valid credential, and credential rotation cannot lock the replacement verifier.
- Cancelled, stale/replayed, invalid-token, provider-outage, and unapproved-account callbacks return
  to the designed login page with bounded non-sensitive error codes, retry guidance, and no echoed
  authorization code, state, claims, or provider description. Fresh and expired sessions preserve
  safe deep links; signed-link credentials are never copied into login return URLs.
- The main UI identifies the signed-in account and exposes CSRF-protected local sign-out plus
  provider account switching. Provider switching is available only when OIDC discovery advertises
  an end-session endpoint and the exact public post-logout URI is registered; local logout remains
  truthful when it is unavailable.
- Local single-user compatibility mode remains explicit and cannot silently satisfy a multi-user
  deployment.

### `GH-UCP-003` — Internal authorization, roles, and delegation

- Gateway-to-runtime identity uses an asymmetric, short-lived assertion with issuer, audience,
  tenant, subject, role, scopes, issued/expiry time, unique token id, and a published public JWKS.
- The private assertion-signing key is mounted read-only only into signer-capable BFF/MCP security
  contexts. Runtime and worker processes run under a separate OS user or container boundary and
  receive only public JWKS material. File mode `0600` under one Unix account shared with the runtime
  or workers is not key separation; compromising a runtime or worker must not permit assertion
  minting. Key rotation permits bounded public-key overlap/refresh without copying private material
  into verifier processes. The gateway supports a public-only previous JWKS with an absolute
  180-900 second expiry; it signs only with the new key, publishes both ids during the overlap, and
  removes the prior key dynamically after expiry. Split service environments keep both the current
  private key and previous-public-key source out of runtime/worker contexts.
- Supported initial roles are `member`, `viewer`, `tenant_admin`, and `service`; every write route
  enforces both role and scope.
- Fully verified browser OIDC is the durable role authority and synchronizes mapped promotions and
  demotions on every login; active sessions read the current durable role. MCP may establish a first
  role only during permitted enrollment and never overwrites an existing durable role.
- A human-created delegation record may authorize a future occurrence. At fire time the scheduler
  mints a new short-lived assertion; it never stores or replays a browser session token.
- Each browser-gateway or MCP hop mints a fresh assertion for each runtime request. The runtime
  atomically consumes its hashed `jti` in the shared durable state store through expiry, so replay
  fails closed across processes and restarts without persisting the bearer assertion itself.
- Disabled users, disabled schedules, revoked delegation, wrong tenant, wrong audience, expired or
  replayed assertions, replayed confirmation tokens, and cross-user identifiers fail closed.
- Plain client-asserted owner or identity headers are permitted only in an explicitly configured
  legacy/local mode and never become the hosted multi-user default.

### `GH-UCP-004` — Standards-based MCP connection

- The GlassHive MCP endpoint publishes OAuth 2.1 protected-resource metadata and challenges clients
  with the correct resource metadata URL.
- The canonical public MCP URL is the RFC 8707 resource and is kept separate from explicit accepted
  JWT `aud` values. Access tokens are bound to one configured token audience, stable subject,
  authorized client, request scope, and emitted token scope. Optional upstream token-tenant policy
  is separately configured as `mcp_oauth.token_tenant_id`; it never reuses or changes the independent
  GlassHive ownership namespace in `enterprise.tenant_id`. Another audience, resource, configured
  token tenant, client, or partial verifier policy is rejected.
- Official Codex and Claude connection commands are generated from configured public HTTPS endpoints;
  the UI never invents a localhost or unconfigured command for a hosted user.
- Hosted Entra deployments do not assume MCP dynamic client registration. Codex and Claude Code
  commands appear only for explicitly pre-registered public clients whose IDs are also in the MCP
  verifier allowlist. Codex uses the canonical public MCP URL as its OAuth resource and requires a
  fixed callback port plus the exact derived callback URI; Claude Code requires its fixed callback
  port and localhost callback URI. Missing token audiences/scopes, client allowlist drift, resource
  drift, or partial registration is an action-required deployment state, not a copyable false command.
- “Use from Codex/Claude” presents copyable setup and login commands, truthful prerequisites, and a
  link to source-available documentation. It does not claim an OSI-approved license where the
  component's license is source-available.
- A versioned, non-secret companion skill/connector may point to the canonical live repository and
  official MCP setup docs so a user can paste one instruction into a supported AI client. The skill
  explains and invokes the official client configuration/login path; it does not embed credentials,
  bypass client consent, or fork a second GlassHive protocol.
- MCP exposes the same owner-scoped workspace, worker, schedule, account, connection, Library, and
  confirmation model as the UI. Client convenience must not weaken human confirmation or scope.

### `GH-UCP-005` — Personal provider accounts

- Provider-account rows store only owner, provider, label, status, policy, capability metadata, an
  opaque provider-home locator, and timestamps. Raw subscription tokens are not stored in runtime
  SQLite or returned by APIs.
- Per-user API keys are an optional alternative where the provider supports them. The secret value
  lives in the deployment's user-scoped Keychain/vault/secret store; GlassHive stores and returns
  only an opaque reference and redacted readiness metadata.
- The current fixed user-key inference adapter is OpenAI Responses-only. Although LibreChat can own
  a user-scoped Anthropic key, GlassHive must report Claude API-key execution unavailable until a
  fixed Anthropic Messages-compatible broker adapter proves the same user/run binding, revocation,
  redirect/origin restrictions, and no-secret-copy boundary. The experimental Claude consumer OAuth
  path is not an accepted hosted subscription path and is not advertised as supported.
- Codex uses an account-specific `CODEX_HOME`; Claude uses its supported native authentication home
  or provider-supported headless token flow. GlassHive does not invent or extract Claude OAuth.
- Setup uses an isolated PTY/device/browser flow for native subscriptions or a no-echo secure secret
  input for API keys, shows pending/ready/action-required/unsupported status, and supports connect,
  test, reconnect, rotate, disconnect, usage/readiness inspection, and default selection.
- Native setup output is translated at the runtime boundary into provider-specific, allowlisted
  guidance: the reviewed sign-in destination, a bounded one-time code where supported, and an
  optional reviewed recovery destination. The main Connections surface exposes those values as one
  primary sign-in action and one copy action. Raw PTY output remains available only in collapsed
  technical details and is never promoted into a clickable arbitrary URL.
- While a provider sign-in attempt is active, Connections hides stale recovery text, account-creation
  controls, and external-client setup so the current sign-in link, one-time code, copy action, and
  cancel action remain the only primary task. Those controls return when the attempt ends.
- Account creation controls are generated from the server's supported provider methods. An
  unavailable worker-account route is omitted instead of rendered as a dead button or an internal
  policy warning. External Codex/Claude MCP client setup remains a separate collapsed surface and is
  never presented as a worker subscription.
- The first account for an owner/provider becomes that provider's default. On launch, a sole Ready
  compatible account is selected even when its row predates that defaulting rule, and new personal
  work defaults to `personal_required`. Temporarily choosing a worker profile without personal
  account support must not silently change that saved personal policy to deployment credentials.
- The UI and MCP expose the same generic account lifecycle: connect metadata, start native setup,
  test current readiness, disconnect credentials, and forget already-disconnected metadata. A
  disconnected row does not consume the active-account quota, and forgetting it is rejected until
  active leases are gone and disconnect has completed.
- `last_verified_at`, `last_used_at`, and GlassHive-observed usage counters are non-secret operational
  metadata. Lease acquisition alone is not usage. After an account-bound native or brokered worker
  dispatch returns or raises, GlassHive atomically records the run, failure outcome, and measured
  dispatch duration. Input/output token totals remain absent unless the worker harness reports them
  truthfully. These fields are local operational telemetry, never provider balance, billing, or quota.
- Provider homes live outside workspace files on encrypted deployment storage with owner-only
  permissions. Duplicate/export/template operations never copy them. Hosted active environments
  declare one canonical phase-local provider-home root. Upgrade resolves the predecessor from the
  effective systemd EnvironmentFile order (base file, then active-slot overrides), using the
  explicit provider-home value when present and the legacy runtime-database parent otherwise. It
  reads only those non-secret path selectors from the base file, snapshots both predecessor and
  canonical paths before mutation, and then atomically materializes canonical live state before
  rehearsal. Clone, seal, restore, and recovery preserve exact content, numeric uid/gid, modes,
  extended attributes, POSIX ACLs, and prior absence; an account row without its matching home is a
  failed rollout.
- Provider accounts and setup sessions are owner scoped. Cross-user access is indistinguishable from
  not found.
- A user may enable personal-only credential policy only when a personal setup path is available or
  a personal credential already exists. If setup is later disabled, an existing policy remains
  visible and reversible; the UI cannot create a new unreachable personal-only state.
- A user may change an existing idle or paused workspace's credential policy through the same
  single-use browser confirmation boundary used for other sensitive workspace changes. Selection is
  revalidated against owner, profile, readiness, queued/running work, and active leases at approval
  time and applies only to future runs; an AI/MCP caller may prepare but never self-confirm it.

### `GH-UCP-006` — Mission binding and provider leases

- The selected personal provider home is mounted or projected only into the selected user's mission.
  Process-global authentication is never copied into that worker as a fallback.
- A durable exclusive lease covers the complete mission, including refresh writeback. Concurrent use
  of one account fails with an actionable busy state. Mission leases are heartbeated against a short
  crash-detection window rather than inheriting the worker's potentially day-long timeout, so an API
  crash cannot strand the account for 24 hours; loss quarantines the account with a reconnect action.
- In the reviewed Linux `per_worker_container` route, the exact account home is mounted only into the
  selected worker container. The rootless container grants and verifies access for its non-root worker
  user through POSIX ACLs, with no world-writable fallback; the container is removed, credential-tree
  modes are tightened again, and only then is the exclusive lease released. Provider CLIs may leave
  private executable-wrapper symlinks in their own caches. Sealing unlinks those directory entries
  without following their targets before it changes ownership, modes, or ACLs on real directories and
  files; hardlinks, special files, escaped paths, and any unlink failure remain fail-closed. The repair
  one-shot uses Docker's writable-by-default bind-mount grammar; an unsupported bare `rw` mount field
  must never prevent the sealed repair container from starting.
- A hosted rollout does not infer provider-tree quiescence from currently open files alone. With the
  runtime, MCP, and UI stopped, it recursively checks descendant descriptors and separately inspects
  every recognized rootless `wpr-*` container. A running, paused, or restarting container whose bind
  mount is at or below the predecessor, canonical, rehearsal, or rollback provider tree blocks state
  mutation even when it has no open credential descriptor. Exited containers' historical mount
  metadata does not block rollout.
- `personal_required` fails closed when no ready compatible account is selected. The default
  `personal_preferred` policy uses a ready personal account first and otherwise preserves the
  deployment-managed legacy path. A differently named optional policy must not silently replace this
  canonical behavior.
- Platform support is explicit. Multi-user Claude subscription isolation on a macOS host is
  unsupported unless separately proven; Linux/container and hosted consumer-subscription flows are
  gated by technical, provider-policy, and legal approval.

### `GH-UCP-007` — Private persistent workspace catalog

- Every workspace has an immutable id and routing alias plus a user-editable display name. Rename
  never breaks callbacks, schedules, or resume routing.
- Workspace kinds are `named`, `ephemeral`, and `legacy`. Existing workers migrate to `legacy`
  without changing their behavior.
- New work starts fresh by default. Reuse is an explicit `Open`/`Resume` action or a parent decision
  backed by a known stable alias.
- Browser launch durably prepares the workspace and queues its first run before returning the watch
  surface. Cold image/container preparation continues through the worker queue, so an edge request
  deadline cannot invite a duplicate retry; the watch surface truthfully shows starting, running,
  or failed. Busy, unavailable, or malformed auxiliary watch/link state falls back to the
  authenticated owner-scoped watch URL after a bounded, sub-request-budget storage attempt and after
  the one project, workspace, and run are durable. A failed/cancelled/interrupted run asks for a corrected
  follow-up; it must not offer a Resume control that only restarts compute while leaving the same
  terminal run as the visible result. An explicit close is permanent from `terminating` through
  `terminated`; if compute teardown fails, `termination_failed` remains visibly closed and
  retryable by Close/startup reconciliation without reopening the workspace. All three states
  disable follow-up, pause/interrupt/resume, account switching, desktop/terminal attachment, and
  schedule creation/re-enablement/run-now, and stale runtime writers cannot resurrect them. The
  real external runtime start is serialized with Close; newly started runtime identity is durable
  before request acceptance, while already-accepted long responses do not hold the Close lock.
  Close revokes already-open terminal/desktop streams and deactivates both native and delegated
  recurring definitions. A late delegated definition whose compensating deactivation fails makes
  cleanup visibly `termination_failed` and retryable instead of claiming a clean close.
- The supported single-runtime hosted service reconciles on startup. It recreates the process-local
  queue processor for a durable queued run without creating a second run; an intentionally paused
  workspace remains paused.
- A migration rehearsal against cloned state is passive: startup reconciliation, immediate and
  replay/retry callback delivery, lifecycle reapers, and schedule dispatch are all disabled. New
  callback records remain pending for live. The live phase enables the consumers together so copied
  work cannot produce rehearsal side effects and then run again after cutover.
- The catalog is owner scoped, cursor paginated, searchable, and discoverable by human name, tags,
  favorite/recent state, provider readiness, current state, and next scheduled occurrence.
- Opening a paused named workspace resumes it and restores its persisted filesystem, browser profile,
  worker context, and capability references. Expired external sessions produce an actionable
  reconnect state rather than false success.

### `GH-UCP-008` — Safe duplicate and templates

- Duplicate creates a new workspace id, routing alias, browser profile, audit trail, and ownership
  record. It copies only approved regular workspace files/context and non-secret capability
  references that are revalidated for the destination owner.
- Duplicate does not copy provider homes, access/refresh tokens, browser cookies, active leases,
  schedules, pending confirmations, audit history, or grants that require fresh approval.
- Duplicate is durably idempotent per owner and tenant. A retry with the same key and request returns
  the original destination; key reuse for a different request conflicts, and interrupted attempts do
  not create a second hidden workspace.
- Absolute, out-of-root, looping, device, socket, and unsafe symlink inputs fail closed. File count,
  byte, and depth limits are enforced. An empty source produces an explicit zero-item report.
- Templates contain versioned non-secret bootstrap, exact Library references, and—when present—only
  an opaque same-owner provider-account reference and policy. Instantiation creates a fresh paused
  workspace, revalidates the referenced account/profile/readiness, reruns dependency probes, and
  creates fresh capability approvals; credential homes, grants, and tokens are never templated.

### `GH-UCP-009` — Brokered user connections

- Brokered LibreChat/Viventium connections are optional. When the compatible capability-broker
  adapter is enabled, GlassHive reuses its user-scoped OAuth lifecycle and stores metadata and broker
  references, not duplicate provider refresh tokens. Without that adapter, GlassHive remains
  standalone: persisted workers use their supported provider-native login, connectors, and skills
  without a LibreChat account binding, replay cache, grant API, connected-accounts UI, or LibreChat
  source change.
- A worker receives compact factual capability context and a short-lived, narrow broker grant. It
  chooses the tool path itself; the host does not predict provider/account routing or manufacture a
  plan.
- When the optional broker adapter is enabled, direct Glass Drive launches, workspace continuations,
  scheduled missions, and authenticated MCP assignments resolve the same verified GlassHive-owner
  to LibreChat-user binding immediately before each run. The scalable default uses the exact shared
  OIDC issuer and principal claim:
  LibreChat derives and uniquely indexes the same opaque issuer-plus-subject principal at
  authenticated sign-in, including existing-user re-login backfill. It never falls back to email.
  Deployments without a shared issuer may use an explicit operator-reviewed mapping. LibreChat
  returns redacted readiness plus a fresh
  tenant/user/worker/run-bound grant; the runtime keeps it in memory, projects it through an
  environment-variable indirection, and revokes it on completion, interruption, pause, or
  termination. The grant is not persisted in GlassHive SQLite, reusable worker metadata, templates,
  public API responses, logs, or literal workspace MCP configuration.
- When the optional broker adapter is enabled, unmapped owners, broker outage, no reviewed
  connections, and connection action-required are distinct states. The Connections surface reuses
  LibreChat's generic connected-accounts UI and redacted readiness instead of adding
  provider-specific consent or token storage to GlassHive.
- When the optional broker adapter is enabled, every 60-second direct issuer assertion carries a
  signed random nonce that LibreChat consumes in the existing shared replay cache before resolving a
  user or issuing/revoking a grant. Replay or production replay-cache outage fails closed; a retry
  uses a freshly signed nonce.
- Read-content and write scopes remain separate. Writes and destructive actions require the existing
  explicit confirmation policy. Revoke, expiry, provider outage, missing auth, unsupported
  configuration, rate limit, and successful-empty remain distinct states.
- Provider-native connectors may be supported as optional adapters only when they preserve the same
  owner, scope, audit, and revocation guarantees.
- User-scoped OpenAI API-key or enterprise-route execution uses a fixed, allowlisted inference
  adapter with a short-lived grant bound to the canonical user, tenant, worker, run, model, route,
  and adapter. Codex custom providers use the supported Responses wire protocol; GlassHive must not
  claim that a Chat Completions-only route is a working Codex connection. Grant issue/revoke and
  credential lookup remain in the connected-account owner, not GlassHive SQLite or workspace files.
- Direct capability issuance and inference issuance use independent derived secrets so compromise of
  either protocol cannot mint assertions accepted by the other.
- The enterprise upstream is fixed, HTTPS, and operator-trusted; an approved private gateway is a
  valid deployment boundary. Users and workers cannot override its origin, path suffix, adapter,
  authorization header, or extra headers. The adapter does not follow redirects and rejects every
  upstream `3xx`; personal API-key execution always uses the fixed OpenAI API origin.

### `GH-UCP-010` — Curated Library and human confirmation

- A Library manifest has a stable id, version, content hash, provenance, supported profiles,
  requested scopes, non-secret configuration schema, dependencies, health probe, and upgrade/remove
  behavior. It contains no credentials.
- “Add this skill/tool/connector” resolves to a universal sequence: inspect manifest, explain
  permissions and dependencies, create a pending change, obtain explicit browser confirmation,
  install through the profile adapter, probe health, and create the workspace grant.
- A worker may propose a Library item or pending change, but cannot self-confirm it or grant itself a
  new connection/account scope. Confirmations are user bound, time bounded, and single use.
- Install, upgrade, disable, remove, dependency failure, incompatible profile, revoked provenance,
  hash mismatch, and partial rollback are auditable and have actionable states.

### `GH-UCP-011` — Designed UI and least-resistance entry

- The control plane extends the designed Glass Drive UI. It does not expose the basic runtime API UI
  as the user product.
- Primary navigation is clear and bounded: Run Project, Workspaces, Connections, Library, Schedules,
  and Activity.
- Connections defaults to the account name, status, and the single action needed now. Account
  creation, destructive/diagnostic account actions, external MCP client commands and callbacks, raw
  provider output, empty connected-tool state, and operational provenance use progressive disclosure
  or remain hidden until they are relevant. The same essential-first hierarchy applies on narrow
  screens.
- The create-workspace entry preserves the approved three primary inputs: project description,
  success criteria, and optional context. Account/profile/type controls are secondary and
  use progressive disclosure.
- Human names, rename, favorites, recent items, search, tags, readiness, next run, empty states,
  blockers, retry, and recovery are visible and keyboard accessible. Layout remains usable on narrow
  screens, with reduced-motion support.
- The current user, local sign-out, provider-level account switch, and actionable login recovery are
  visible product surfaces rather than hidden API-only operations.
- An authenticated browser launch may return an opaque `/r/{ref}` handoff. That handoff reuses the
  validated browser session, rechecks tenant and immutable owner before opening the watch surface,
  returns an expired session through safe sign-in recovery, and retains not-found behavior for a
  different owner. It never requires a second trusted-proxy assertion from the same browser.
- Primary tabs and account controls wrap at narrow-desktop and mobile widths; no destination or
  sign-out/account-switch action may be clipped behind a hidden horizontal scrollbar.
- Account setup and connector authentication happen inside the selected private workspace only where
  the provider requires an interactive worker/browser session; deployment-wide credentials remain
  an operator concern.

### `GH-UCP-012` — Additive public API

- Additive owner-scoped resources may include `/v1/me`, `/v1/workspaces`,
  `/v1/provider-accounts`, `/v1/connections`, `/v1/library`, `/v1/pending-changes`,
  `/v1/recurring-schedules`, and `/v1/activity`.
- List endpoints are bounded and paginated. Mutations are idempotent or accept an idempotency key
  where retries can duplicate work. Conflict, capacity, auth, policy, action-required, retryable,
  and terminal failures use stable structured classes.
- UI and MCP use the same owning runtime model through a scoped gateway/BFF; neither creates a
  parallel store or different authorization semantics.

### `GH-UCP-013` — One recurrence owner and immutable occurrences

- A deployment selects exactly one recurrence owner: `viventium_cortex` or `glasshive_native`.
  Conflicting ownership fails closed. Existing one-shot schedules remain compatible.
- Standalone GlassHive selects `glasshive_native`; `viventium_cortex` is enabled only with the
  separately pinned Scheduling Cortex bridge and is not a standalone deployment prerequisite.
- The acceptance target supports one-shot, interval, cron, and RFC 5545-compatible definitions.
  Timezone, DST policy, start/end, enabled state, overlap, misfire, bounded catch-up, and jitter are
  explicit data, not prompt parsing. A narrower first increment must report unsupported forms
  honestly and is not full recurrence acceptance.
- Definitions are mutable and owner scoped. Occurrences are immutable, uniquely keyed, claimable,
  and record scheduled time, claim/lease, attempt, run, outcome, and failure class.
- Scheduler recovery is deterministic: stale claims are recoverable, overlapping fires obey policy,
  missed periods do not create an unbounded herd, and a retry cannot create a second occurrence.
- Recurrence evaluation never walks every stale occurrence to reach the present. Interval, cron,
  daily, and RFC 5545-compatible rules calculate the latest eligible occurrence directly. RFC rules
  enforce a one-minute minimum cadence and bounded length, part/list complexity, and `COUNT` so a
  user-supplied rule cannot create unbounded scheduler CPU work. Bounded RFC reconstruction preserves
  the original `DTSTART` phase, including month-end rules that intentionally skip shorter months.
- In `viventium_cortex` mode, the normalized workspace schedule is persisted as an internal-only
  structural rule while public Scheduling Cortex tools retain their existing schedule schema. A
  deterministic nominal occurrence id, durable bounded claim expiry, and monotonically increasing
  attempt count fence dispatch across process restart. Jitter materializes and pins the nominal
  occurrence before delaying dispatch; it never stores credentials and cannot continually replace a
  waiting occurrence on a cadence shorter than the jitter bound.

### `GH-UCP-014` — Fire-time renewal and execution safety

- Each occurrence revalidates the user, delegation, schedule, workspace, selected provider account,
  Library/grants, and connections at fire time.
- Fire time mints a new internal assertion, renews or reissues bounded broker grants, acquires the
  provider-account lease, and starts or resumes the correct workspace exactly once.
- Revoked users, disabled workspaces, unavailable accounts, expired connection auth, removed Library
  items, and capacity limits produce structured `action_required`, `retryable`, or `terminal`
  outcomes. Native and delegated definitions pause after terminal/action-required fire validation so
  the same permanent prerequisite does not create an unbounded occurrence ledger. They do not
  silently fall back to another user's or global credential.
- A hosted principal has a narrow schedule-authority record in the GlassHive runtime store. Tenant
  administration disables that authority and deactivates native/delegated definitions before the
  browser-auth principal is disabled. The record contains no browser session or provider credential.
  Every native or delegated fire checks the current authority before creating a schedule/run; native
  create, enable, manual-run, run-link, and queue-claim mutations repeat that check inside the same
  database transaction. A missing or disabled hosted authority fails closed as non-retryable
  `principal_disabled`. Disablement cancels work that has not fired, while already-running work remains
  truthfully represented as already fired rather than being silently relabeled in the database.
- Scheduling Cortex treats structured `failure_retryable=false` as terminal and preserves an
  explicit `action_required` outcome when provided. Transient/unknown transport failures retry the
  same deterministic occurrence only up to the configured bounded attempt budget, then become
  terminal `retry_budget_exhausted`; the deterministic attempt is claimed before private-detail or
  network side effects so pre-dispatch failures count toward the same budget. Other Viventium schedules
  are unaffected.
- UI, MCP, activity, callbacks, and occurrence history show next run, last run, current outcome, and
  the exact user action required.

### `GH-UCP-015` — Preserve Viventium direct conversations

- GlassHive's OpenAI-compatible conversation provider remains a first-class Viventium direct
  conversation agent. Control-plane and mission-account additions do not route ordinary authored
  conversation turns through the delegated-workspace MCP path.
- Conversation session continuity, LIFE/bootstrap authority, capability-broker projection,
  activity, cancellation, reconnect, callbacks, Telegram, scheduling, feelings, and voice control
  retain their owning contracts.
- Conversation and mission account selection remain distinct even if they share the same provider
  profile implementation.

### `GH-UCP-016` — Public/private safety and auditability

- Public source, docs, tests, screenshots, examples, and commit history contain only neutral
  synthetic identities, tenants, domains, workspaces, and artifacts.
- Secrets, provider homes, browser profiles, runtime databases, logs, private prompts/data, customer
  names, local paths, and machine identifiers remain outside the public repository.
- Audit events record actor, tenant, action, target, decision, failure class, and timestamps without
  raw credentials or signed URLs. Owner and tenant checks apply to list, inspect, resume, duplicate,
  download, activity, and MCP result routes.

### `GH-UCP-017` — Delivery and installed-artifact chain

- A nested GlassHive source change is not shipped until its own commit exists, the parent component
  lock points to that commit, bootstrap resolves it, the compiler emits the intended config, the
  launcher starts it, and the installed runtime proves the same artifact.
- Acceptance includes a fresh public clone/install in a new directory, upgrade from the preceding
  supported version, restart/restore continuity, and rollback/recovery where applicable.
- Before a candidate opens an existing SQLite runtime database, the preceding runtime is quiesced, a
  consistent backup including committed WAL state is created and restore-tested, and migration is
  rehearsed against a clone. Acceptance requires an explicit schema version/receipt,
  `quick_check`/`integrity_check`, `foreign_key_check`, invariant row counts, owner/tenant sampling,
  and user-visible persistence checks. Old and new runtimes never write the same database
  concurrently. Binary rollback alone is insufficient after an incompatible migration; rollback
  restores the verified pre-upgrade database and associated state.
- Dependencies and immutable environments are staged before cutover. Runtime, MCP, and BFF form one
  release unit: ingress changes only after every readiness probe passes, and any start/readiness
  failure stops the complete candidate group and leaves or restores the preceding healthy group.
  PID existence and warning-only checks are not readiness.
- Runtime, MCP, and BFF are the standalone GlassHive release unit. Optional LibreChat/Viventium
  bridges are separately pinned, deployed, and validated only when enabled; they are not a
  prerequisite or required source change for an existing standalone LibreChat deployment.
- Minimum readiness is: internal runtime `/health` returns `200` JSON with `status=ok`; BFF `/health`
  returns `200` JSON with `status=ok` and nested `runtime.status=ok`; public MCP metadata returns the
  exact resource/issuer/scopes and unauthenticated initialize returns `401` with a
  `WWW-Authenticate` resource-metadata challenge; authenticated initialize succeeds; unauthenticated
  browser access enters the identity flow and an allowed user lands in the designed Glass Drive;
  an authenticated state-preserving mutation proves the browser CSRF header survives the public
  edge while spoofed identity headers are overwritten; public JWKS is reachable without a browser
  cookie; and
  the runtime remains externally unreachable.
- Source correctness, unit tests, mocks, or an already-running owner checkout cannot substitute for
  built and installed artifact evidence.

### `GH-UCP-018` — Observability, QA, and worker updates

- Every release candidate traces requirement -> user case -> expected/forbidden result -> browser or
  MCP evidence -> API/log/DB/state evidence -> installed artifact -> remaining gap.
- Happy, first-run, empty, missing-auth, denied-domain, expired-session, cross-user, dependency-down,
  retry, cancel, interruption, persistence, restart, duplicate, schedule, provider-busy, revoke, and
  capacity paths are exercised.
- Worker CLI/bootstrap versions are upgraded only through existing component/runtime requirement
  mechanisms and official supported interfaces. Upgrades must preserve native skills/plugins,
  browser/computer integration, project instruction loading, effort controls, and the universal
  self-check/final-report contract.
- Reviewed worker-image inputs are staged through same-directory atomic replacement so a sealed
  read-only prior copy remains retryable without partial build context or temporary residue.
- The digest-pinned worker base image is paired with a reviewed immutable Ubuntu snapshot whose
  package builds are compatible with that base. The managed image tag changes when this pairing
  changes, and image provenance must attest the exact snapshot before an existing image is reused.
- Performance measurement includes login, catalog load, create/resume/duplicate, setup, MCP
  connection, schedule fire, and result delivery, and is judged with the Core Outcome Metric rather
  than latency alone.

## Current Implementation Evidence and Gaps

This table describes the working tree at the time of this requirements update. Detailed run truth
lives in [`qa/glasshive-user-control-plane/`](../../qa/glasshive-user-control-plane/).

| Area | Source-level evidence present | Acceptance gap |
| --- | --- | --- |
| Login and assertions | OIDC gateway, stable issuer+immutable-claim principal derivation, PKCE/nonce callback, local enrollment policy, IdP-owned tenant/app-role admission contract, bounded callback recovery/redaction, current-user/local/provider logout UI, browser-authoritative durable role sync, signed internal assertions, role/scope checks, public JWKS, raw-header/issuer parity guards, canonical compiler projection, and automated failure coverage | Real IdP login/logout/account-switch/denial/revocation in a hosted HTTPS proxy topology; live key rotation and session-revocation browser evidence |
| MCP OAuth/connect | OAuth JWT verifier, resource metadata, separate public-resource/token-audience/request-scope/token-scope/upstream-token-tenant policy, independent GlassHive ownership namespace, pre-registered fixed client callbacks, enforced UI/MCP issuer parity for hashed ownership, UI-generated client commands, additive owner-scoped workspace/account/connection/Library/activity tools, explicit Library-only confirmation preparation, and versioned `connect-glasshive` companion skill | Run fresh real Codex and Claude clients against hosted HTTPS OAuth; prove consent, reconnect, revocation, and installed config. Connected services remain broker-owned and account selection remains execution-policy-owned |
| Personal accounts | Owner-scoped metadata, isolated native homes/setup, status/default/disconnect, credential-tree permission normalization, short heartbeated exclusive mission leases, allowlisted provider-setup environments with no service-secret inheritance, user-scoped API-key/enterprise inference references, fail-closed multi-user `per_worker_container` projection, exact Codex/Claude config-home bind mounts, strict rootless-worker ACL/access verification, mount removal before lease release, and real-browser synthetic native/API-key lifecycle evidence | Real approved subscription/API-key mission, reconnect/rotate/usage, rootless-container credential refresh/writeback inspection, and provider/legal approval remain open; deployments without the reviewed per-worker container mode still return `isolated_substrate_required` |
| Workspaces | Kind migration, fresh launches as ephemeral, explicit Keep transition, owner-scoped catalog/search/tags/favorites, crash-safe idempotent duplicate-without-compute, immutable versioned templates with dependency/account revalidation, UI controls, and local browser create/keep/rename/duplicate/template evidence | Browser/profile/context continuity across runtime restart, large catalogs, and installed source/destination/template inspection |
| Connections/Library | Owner-scoped connection and Library models, pending change, single-use human confirmation, real bootstrap activation, drift-aware LIFO removal, grant audits, and local browser add/remove evidence | Real brokered connected service, provider-native adapter where supported, upgrade/rollback failure paths, and live worker tool use |
| Recurrence | Native daily/interval/cron/RFC 5545 definitions, explicit start/end/overlap/misfire/jitter policy, immutable occurrences, one owner, timezone/DST/coalescing logic, API/MCP/UI surfaces, plus local browser create/run-now/exactly-one-completed-occurrence/pause evidence. In Viventium mode, authenticated CRUD and polling are authoritative in Scheduling Cortex, GlassHive stores no shadow definition, owner outage fails before local mutation, every dispatch carries a fresh 90-second assertion bound to its occurrence/user/workspace/task/instruction, raw scheduler secrets are not transmitted, lost-response retry reserves exactly one GlassHive run, and the signed terminal callback reconciles the authoritative occurrence without a fast-completion overwrite | Integrated user/delegation/grant renewal/provider lease and real installed scheduled delivery/restart/catch-up across DST/overlap/misfire paths |
| Viventium preservation | Direct-conversation ownership remains intact; connected-account policy, capability grants, scheduler delegation, compatibility suites, and affected LibreChat/Scheduling Cortex tests pass | Full installed web/channel/voice/scheduler regression and real connected-service use |
| Worker toolchain | Existing host-native compatibility floors remain Codex `0.144.1` and Claude Code `2.1.178` so current Viventium conversations stay intact; fresh isolated workstation images are separately pinned to Codex `0.146.1` and Claude Code `2.1.223`, with capability preflight on both paths | Clean-bootstrap/install capability proof on approved platforms and future version refresh through the same mechanism |
| Delivery/public safety | Isolated source checkout, public-safe synthetic test data, read-only protected downstream boundary, source/install separation, per-component SQLite schema ledger with newer-database refusal, runtime startup refusal for a readable signer key, verifier-only integrated runtime launch, and hard runtime/MCP/BFF local readiness | Hosted path split/header scrubbing, separate signer/runtime OS identities, consistent existing-DB backup/clone rehearsal/restore, atomic installed cutover, final public diff/history/build scan, nested commit and parent pin, clean clone/install, and protected downstream owner-run compatibility |

## Acceptance Owner

The cross-feature case catalog and status matrix are in
[`qa/glasshive-user-control-plane/`](../../qa/glasshive-user-control-plane/). Specialized evidence
continues to live in its existing QA owners; the control-plane coverage matrix links those owners
instead of copying their reports.
