# GlassHive User Control Plane Completion Ledger

## Purpose and authority

This is the living execution ledger for completing the GlassHive user-control-plane vision. It
exists to prevent scope drift, repeated rediscovery, and a source-tested feature being mistaken for
a completed user journey.

It does **not** create a second product specification:

- [Requirement 55](../../docs/requirements_and_learnings/55_GlassHive_User_Control_Plane_and_Persistent_Workspaces.md)
  is the product-truth owner.
- [cases.md](cases.md) is the durable happy/unhappy-path acceptance catalog.
- [coverage.md](coverage.md) is the requirement-to-evidence matrix.
- This ledger records the exact final outcome, current snapshot, smallest remaining work, execution
  order, blockers, and completion gates.

When implementation changes product truth, update Requirement 55 and the relevant case before or
with the code. When evidence changes status, update `coverage.md`, the applicable case, and a dated
report. This ledger then summarizes that evidence; it never upgrades a status on its own.

Snapshot date: **2026-08-21**

Provenance is recorded as separate facts so later documentation commits cannot be mistaken for the
exact artifact that was user-tested:

- installed Ultimate Phase 1 test baseline: parent `35c2c834ffb81c0db65d92d9d8df6332b185c3e4`
  and GlassHive `8153b6a3859877c54ce5895be4bd3e367e1797b8` on
  `codex/glasshive-user-flow-completion`
- accepted source follow-up baseline: parent `54d1fb9ffd431b6335b87cc0f553bb102ed8519b`
  and GlassHive `103c8bea4a9e1befe1d9063337123c866af7ae7d`
- current public GlassHive documentation/release-note tip pinned by the parent:
  `e3905534dd4716f315f24bffaa76270b08f254bb`
- source was reconciled from current public `origin/main` plus the reviewed renewable-auth and
  user-flow fixes; the original working tree was not used as an authoring surface

Overall status: **PARTIAL**. The installed release now passes the core organization login,
native Codex/Claude MCP, deployment-managed Codex, personal Codex, personal Claude, workspace
output/refresh/rename/duplicate, manual schedule occurrence, official native Outlook/SharePoint
read/reuse, native Gmail use inside a persistent Claude workspace, stale-account removal, and
same-workspace control from fresh Codex and Claude MCP clients. The current personal-Codex rerun is
blocked by the provider account's usage quota rather than GlassHive. Confirmed connected-service
write/revoke/renewal/two-user coverage, automatic schedule fire, Library worker use, and clean
install/restore remain open outside the Ultimate Phase 1 slice.

## Exact final goal

Any allowed individual user can:

1. sign in to GlassHive through a convenient, secure, configurable identity flow;
2. connect their own supported Codex or Claude worker subscription, or an optional user-scoped API
   key, without changing another user or the deployment-wide route;
3. create, find, rename, open, continue, duplicate, and schedule a private persistent workspace;
4. return later to the same approved files, browser profile, worker context, account references, and
   capabilities;
5. connect user-owned services such as SharePoint once, grant a bounded capability to a chosen
   workspace, and reuse it without copying tokens into that workspace;
6. add, update, disable, or remove approved skills/plugins/connectors through one generic Library
   lifecycle rather than bespoke provider UI;
7. perform the same owner-scoped operations from Glass Drive or a supported MCP client;
8. connect Codex or Claude through their native installation and OAuth flows with one obvious
   instruction, then make one goal-relevant tool call rather than inspect or enumerate the catalog;
9. see honest, actionable states for missing setup, expiry, denial, busy accounts, unsupported
   platforms, dependency failure, and recovery; and
10. retain existing GlassHive APIs, callbacks, worker/bootstrap behavior, Viventium's direct
    GlassHive conversation path, and protected downstream compatibility.

The complete flow must be secure for multiple users, simple enough for a first-time user, generic
enough for future skills/connectors, and proven through the installed product—not only source tests.

## The intended one-minute experiences

### Glass Drive

1. Sign in.
2. Open **Connections** only when an account or service needs setup.
3. Connect a supported personal worker account or user data service through its native/brokered
   flow.
4. Create or open a named workspace.
5. Ask the worker to do the work; grant an already connected capability or confirm a Library change
   only when needed.
6. Leave and return later; the workspace, output, and approved references are still there.

### Codex or Claude

1. Install the official GlassHive package for the current client.
2. Complete the client's native MCP OAuth sign-in once.
3. Start a new task and say, for example, “List my GlassHive workspaces” or “Create a workspace for
   this goal.”
4. The client makes one matching GlassHive call. Asynchronous completion uses callback delivery or
   a bounded wait owned by the integration; it does not make the user drive a polling loop.

No user should have to choose among overlapping `project_*`, `worker_*`, and `workspace_*` concepts,
read a tool inventory, construct OAuth URLs, manage callbacks, or understand internal worker IDs.

## Non-negotiable design decisions

1. **Less is more.** The worker is the intelligent planner. GlassHive transports the complete user
   goal, constraints, files, capabilities, and results; it does not invent a prompt-specific plan.
2. **Use native client machinery.** MCP is the authenticated control API, the skill is a short
   progressively loaded guide, and the plugin/package is installation and distribution. Do not
   create a second GlassHive protocol or custom OAuth client.
3. **One shared integration source.** Maintain one MCP contract and one concise shared skill source,
   then wrap them in thin client-native OpenAI and Claude packages. Manual commands remain a fallback.
4. **One goal-relevant action, measured before redesign.** Preserve the existing compatibility
   inventory and the proven Viventium eager/deferred contract. Extend native discovery/defer
   controls to external clients only where the client supports them; do not invent a second MCP
   profile, hardcode client identity, or preselect an arbitrary tool count. First capture the failing
   call trace and separate catalog selection, retries, and wait/poll calls.
5. **No skill theatrics.** The skill must not tell the client to list tools, narrate tool choice, or
   repeatedly mention itself. If GlassHive is callable, it should perform the user's requested action.
6. **One identity and authorization model.** UI and MCP resolve the same issuer+subject user and use
   the same owner-scoped service layer. Client convenience never weakens confirmation or scope.
7. **User credentials remain user scoped.** Provider homes and API-key references stay outside
   workspaces. Connection tokens stay with their owning broker/provider. Workspaces store references
   and grants only.
8. **Connections, Library, and Workspaces remain distinct.** Connections authenticate accounts;
   Library manages reusable non-secret capability packages; Workspaces consume approved references.
9. **No invented Claude consumer OAuth.** Enable only provider-supported native/headless routes on
   platforms where isolation, refresh writeback, terms, and policy are proven. Otherwise show
   `unsupported` truthfully.
10. **Renewable auth is product truth.** Requirement 55 `GH-UCP-004` owns expiry, refresh, client
    restart, ordinary reconnect, revocation, and recovery as installation acceptance gates.
11. **Provider-specific scopes remain provider-specific.** Entra needs `offline_access` for refresh,
    but generic OIDC configuration must derive or explicitly configure renewable scopes rather than
    universalize an Entra workaround.
12. **No private-client coupling.** Public code, tests, docs, examples, and evidence remain neutral.
    Protected downstream compatibility is read-only and separately validated.
13. **No status without evidence.** Source, mocks, logs, DB rows, and another model's review support
    acceptance; they never replace the required browser/client/provider/installed path.

## Current-state snapshot

### What has real user evidence

- Hosted organization-session recovery and an accepted sealed three-service canary.
- Real current Codex and Claude Code MCP OAuth/persistence with exactly one `workspace_list` call in
  a fresh process for each client.
- Two real personal-Codex missions, visible output, Watch, and browser refresh persistence.
- A real deployment-managed Codex mission with exact visible output, no personal lease, clean
  post-readiness logs, and no upstream `401`.
- Installed rename and duplicate with one fresh copy and no duplicate run.
- Installed browser Run now with Queued-to-Completed history and idle backend correlation.
- Human-readable workspace cards, modern navigation, view-only live state, and exact artifact actions.
- Local browser Library add/remove using the existing confirmation boundary.
- Local run-now schedule producing exactly one completed occurrence.
- Exact nested-source, parent-pin, and installed-artifact provenance for the accepted hosted release.

### What is implemented but still lacks required user-grade proof

- Full provider-hosted login/logout/denial/replay/profile matrix.
- Provider account rotation, full contention, and second-account/two-owner isolation. Real Claude
  reconnect and stale-account removal are already proven.
- Installed duplicate/template inspection and crash recovery.
- Confirmed harmless connected-service write plus revoke, renewal, reconnect/forget, outage, and
  two-user isolation paths; real native read/reuse is proven for personal Codex.
- Real Library package provenance, worker use, upgrade, rollback, and dependency-failure recovery.
- Automatic scheduled fire across expiry/renewal, restart, DST, overlap, misfire, and exactly-once
  delivery.
- Installed two-user denial, signer/runtime separation, key rotation, DB clone/restore, and clean
  install/upgrade/rollback.
- Candidate-specific Viventium direct-conversation web/channel/voice/scheduler regression.
- Large-catalog performance and full accessibility.

### Current delivered evidence and remaining product gaps

- Renewable MCP setup, the concise shared skill, and thin Codex/Claude packages are committed,
  pushed, installed in the exact canary, and proven by current native clients. A clean-machine public
  install/update/remove is still separate evidence.
- The escaped client task trace is now preserved. It shows that the ordinary workspace-list request
  lacked a native GlassHive tool in that task, fell back through a nested `codex exec`, guessed
  aliases/config, and repeated status checks while authentication was expired. The raw 60-tool
  inventory was not the cause, and removing compatible tools would be an overfit. The one-direct-call
  target now passes in both clients; one real asynchronous launch/result trace without a user-driven
  polling loop remains open.
- Thin native Codex and Claude plugin packages wrap the one canonical skill without embedding a
  second MCP server. Both official manifests validate; Codex marketplace/plugin and Claude package
  installs expose the same concise MCP-first guide.
- The repaired Library/template baseline now passes **10/10** on the reconciled candidate. The wider
  affected runtime/auth/MCP/provider/schedule/profile slices are also green; full cross-stack tests
  still run after the parent pin is updated.
- Current Claude Code authentication and a fresh single-call MCP run pass for the external control
  plane. Separately, the installed personal-Claude worker path now passes provider code handoff,
  Ready persistence, a real mission, same-workspace continuation, and Favorite retention.

### Current support truth

| User outcome | Current status | Plain truth |
| --- | --- | --- |
| Convenient individual GlassHive login | PARTIAL | Real organization and local-session paths passed; complete provider denial/logout/profile matrix is open |
| Personal Codex subscription | PARTIAL | Exact installed mission/output/lease isolation passed; current rerun is provider-quota blocked, while broader contention and second-account coverage remain open |
| Personal Claude subscription | PARTIAL | The installed Linux release completed real personal login and reconnect, hard-refresh persistence, native Gmail use, a normal same-workspace mission, output verification, Favorite retention, an honest setup-session contention fence, and reuse from fresh Codex and Claude MCP clients. A stale duplicate was removed with truthful provider-sign-out uncertainty; two-user proof remains open. |
| User-scoped API key | PARTIAL | Broker/reference boundaries exist; real rotate/disconnect/mission proof is open |
| Private persistent workspace | PARTIAL | Real Codex and Claude mission/file/Watch/output/refresh/reuse evidence exists; full installed service-restart/profile/grant continuity remains |
| Duplicate/template | PARTIAL | Automated/local evidence exists; installed and two-user reapproval proof remains |
| Codex/Claude MCP control | PARTIAL | Exact installed fresh-process traces passed for both with one workspace launch plus one bounded wait; clean public install/update/remove and two-owner parity remain |
| Connected-service use | PARTIAL | Official native Outlook/SharePoint authorization and reuse passed in personal Codex; native Gmail use/reuse passed in the persistent Claude workspace and from fresh Codex/Claude MCP controllers. Confirmed write, revoke/renewal, broker parity, and two-user coverage remain open |
| Library skill/plugin lifecycle | PARTIAL | Local add/remove and the repaired 10/10 Library/template baseline pass; real package/worker use, upgrade, and rollback remain open |
| Recurring schedules | PARTIAL | Exact installed Run now completed visibly with backend correlation; automatic fire/renewal/restart remains |
| Human naming/discovery | PARTIAL | Provider names are prefilled/editable and the real Claude workspace was rediscovered and favorited after refresh; scale and performance remain |
| Fresh install/upgrade/restore | PENDING | Accepted canary is not a clean public install/upgrade/restore proof |
| Installed two-user isolation | PARTIAL | Automated denial evidence exists; no complete two-user browser/MCP/provider/connection run |
| Viventium direct GlassHive conversation | PENDING | Architecture/tests are additive; installed candidate cross-surface regression remains |

## Completion workstreams

### `W01` — Make installation and MCP use obvious

**Final user outcome:** The user gives the current client one short official instruction; the client
installs/configures GlassHive through its native package and OAuth flow, then performs the requested
operation without catalog exploration.

**Current:** The exact escaped-task trace attributed the convoluted path to missing native tool
availability plus expired auth and subprocess fallback, not to the raw tool count. The installed
Connections UI now presents one concise Automatic instruction plus Manual fallback. The canonical
skill tells a client to act immediately when GlassHive tools are present. Fresh Codex and Claude Code
processes each completed one `workspace_list` call with no extra attempted/denied calls in the
transcripts. Claude's successful headless run preapproved only that tool, so broader-preapproval
behavior is not inferred. OAuth persisted. Clean public install/update/remove, two-owner parity, and
one real asynchronous launch/result trace remain open.

**Smallest plan:**

1. Capture one real failing task trace before changing the contract. Classify every call as initial
   action, catalog/discovery, invalid-input retry, status, wait/poll, or result retrieval.
2. Extend the existing eager/deferred contract (`tool_options.defer_loading` and its prompt-registry
   regression) to external clients only through their supported native discovery/defer mechanism.
   If a client has no such mechanism, keep the compatible server and use the concise skill as its
   goal-level guide; do not branch the MCP schema on a client name.
3. Reconcile `completion_polling_guidance` and `workspace_wait` with the one-action user experience.
   Prefer callback/result delivery or one host-owned bounded wait stream; repeated 45-second chunks
   must not require user prompts or inflate an ordinary task into dozens of visible model tool calls.
4. Keep universal one-call guidance once in server instructions. Reduce each tool description to
   when to use it, required inputs, result shape, and owned safety rule.
5. Maintain one shared skill/MCP definition and generate two thin packages:
   - OpenAI/Codex package using the official plugin manifest and skill conventions;
   - Claude package using the official Claude plugin manifest and `.mcp.json` conventions.
6. Make the skill self-select the current client in one sentence. Do not show the other client's
   steps, enumerate tools, or reconstruct OAuth.
7. Keep one exact manual add/login command per supported client under a collapsed fallback.
8. Before any visibility/discovery change, enumerate and regression-test every MCP consumer,
   including the Viventium main agent/direct conversation path and Telegram allowlists. Preserve the
   complete existing public tool/field contract.

**Acceptance gate:** From clean client state, install each package, complete native OAuth in the
intended already-open signed-in Edge profile, restart the client, list workspaces with one call,
launch one task without catalog calls, retrieve its result, restart again, and repeat one call.
Capture a before/after call trace proving which calls were eliminated and that async completion no
longer creates a model-visible wait loop. The Viventium direct-conversation and Telegram contracts
must pass in the same phase. Browser state must match. Unsupported clients are not advertised.

**Owners/cases:** `GH-UCP-001`, `GH-UCP-004`, `GH-UCP-012`; `GHUCP-001`, `005`, `006`, `020`,
`028`, `030`.

### `W02` — Finish renewable login and session recovery

**Final user outcome:** Initial sign-in, silent refresh, ordinary reconnect, restart, revocation, and
recovery behave predictably; the sticky expired-auth banner does not recur after a valid renewable
setup.

**Current:** The resource/scope/root-cause fix is deployed in the exact installed release and both
fresh Codex and Claude Code processes completed their owner-scoped MCP call. The installed evidence
is recorded in [the 2026-08-15 acceptance report](reports/2026-08-15-native-clients-provider-and-workspace-acceptance.md).
Full expiry/revocation/reconnect and clean-install recovery remain open.

**Smallest plan:**

1. Deploy the exact generated scope/config fix through the normal nested pin → parent pin → compiler
   → installed runtime chain.
2. Preserve canonical MCP resource, token audience, API scope, and refresh scope as separate fields.
3. Add provider-capability/config-driven renewable-scope handling for generic OIDC; keep the explicit
   Entra `offline_access` contract where required.
4. Test fresh setup and existing-config upgrade without manual client-file repair.
5. Force or wait for access-token expiry, verify silent refresh, restart the client, and call a tool.
6. Revoke authorization, verify concise action-required state, reconnect normally, and call again.
7. Cover wrong resource, scope, audience, client, tenant/issuer, callback, disabled user, and stale
   authorization without exposing tokens or callback details.

**Acceptance gate:** Real current Codex and Claude clients pass fresh login → expiry/refresh → process
restart → tool call → revocation → ordinary reconnect → tool call on the installed build. No custom
callback helper or manual token/config surgery is used.

**Owners/cases:** `GH-UCP-002`, `GH-UCP-004`, `GH-UCP-017`; `GHUCP-002`, `003`, `005`, `006`, `026`,
`027`, `030`.

### `W03` — Complete human login and enrollment policy

**Final user outcome:** Allowed users can sign in conveniently; unknown, disabled, denied, stale, or
throttled attempts fail safely with useful recovery. Deployment policy can enable supported identity
methods without creating a second principal namespace.

**Current:** OIDC gateway, signed sessions, optional preapproved local password, CSRF, and hosted
organization/local-session evidence exist. Full provider-hosted and policy matrix is incomplete.

**Smallest plan:**

1. Test configured OIDC organization and provider-hosted email/password entry as the same
   issuer+subject identity.
2. Exercise login, logout, provider switch when supported, cancellation, denial, replay, callback
   outage, session expiry, revocation, throttling, credential rotation, and deep-link recovery.
3. Test enrollment open/closed, exact preapproval, role mapping/demotion, assignment-required, and
   disabled principal.
4. Verify local password stays default-off, gateway-only, no-signup/no-reset, and revokes only its
   own sessions when disabled.

**Acceptance gate:** Real browser matrix on the installed HTTPS topology plus DB/log evidence of one
stable principal, no sensitive callback/error echo, and no worker/runtime exposure of gateway secrets.

**Owners/cases:** `GH-UCP-002`, `GH-UCP-003`; `GHUCP-002`, `003`, `004`, `030`, `031`.

### `W04` — Finish personal worker accounts and API-key routes

**Final user outcome:** Each user can connect/test/reconnect/rotate/disconnect/forget a supported
personal account, choose personal-only or preferred policy, and run without exposing or sharing the
credential.

**Current:** Personal Codex has real mission evidence. Account metadata, isolated homes, leases,
API-key references, route readiness, and deployment fallback exist. Complete lifecycle and supported
Claude proof are open.

**Smallest plan:**

1. Repair the exact account lifecycle in Connections before broadening provider types.
2. Run two distinct Codex accounts concurrently; prove correct home mount, exclusive lease, refresh
   writeback, cancellation/failure cleanup, stale lease recovery, and no cross-account secret.
3. Run user-scoped API-key add/test/rotate/disconnect and one real fixed-route Responses mission;
   scan DB, logs, argv, workspace, callbacks, and duplicate output.
4. Enable Claude only on a provider-approved substrate where native auth isolation and writeback pass.
   Otherwise retain an explicit unsupported state.
5. Verify `personal_required` never falls back; `personal_preferred` uses a ready personal account
   and only then an honestly configured deployment route.
6. Test busy/expired/disconnected accounts in dispatch, steer, resume, catalog, schedule, duplicate,
   and template paths before mutation.

**Acceptance gate:** Two users and two accounts complete and isolate real missions; lifecycle actions
survive restart; busy/revoked/missing states fail before run/interrupt; supported personal and
deployment routes remain separate; no credential crosses the owning boundary.

**Owners/cases:** `GH-UCP-005`, `GH-UCP-006`; `GHUCP-007`–`010`, `023`, `025`.

### `W05` — Complete the persistent workspace lifecycle

**Final user outcome:** Workspaces are human-named, discoverable, private, persistent, resumable, and
easy to reuse without accumulating confusing one-off history.

**Current:** Real create/run/output/Watch/refresh and local keep/rename/search evidence exist.
Installed restart, large-catalog, and cross-user continuity remain open.

**Smallest plan:**

1. Preserve fresh-by-default launches and explicit Keep/Open/Continue semantics.
2. Prove named, ephemeral, and migrated legacy behavior against a cloned existing database.
3. Reap compute, restart runtime/MCP/UI, reopen the named workspace, and verify filesystem, browser
   profile, context, account references, grants, output, and name.
4. Verify failed/interrupted/closed states offer only truthful recovery and cannot resurrect or start
   hidden compute.
5. Run server-side search, cursor pagination, tags, favorites, recent state, readiness, next run, and
   responsive rendering against a realistically large catalog.

**Acceptance gate:** A user can create, leave, restart services, find, reopen, continue, and inspect
the same workspace; another user cannot see/open its card, Watch, output, activity, or identifiers.

**Owners/cases:** `GH-UCP-007`, `GH-UCP-011`; `GHUCP-011`, `012`, `019`, `020`, `025`, `029`.

### `W06` — Finish duplicate and template safety

**Final user outcome:** Duplicate/template produces a useful fresh workspace while excluding every
credential, session, schedule, and unapproved grant; required reapproval is persistent and actionable.

**Current:** Automated and local browser copy/idempotency/review evidence exists. Installed crash,
secret-fixture, and two-user proof remain open.

**Smallest plan:**

1. Build a synthetic source containing ordinary files plus tokens/cookies/homes/schedules/pending
   changes/audit/grants/symlink hazards.
2. Duplicate through canonical and legacy routes; inject interruption at each creation/copy/report
   boundary; verify one destination and a durable execution-blocking review.
3. Confirm exact destination Library/provider decisions or continue-without where allowed; never
   treat a worker message as approval.
4. Instantiate templates with valid, missing, unready, wrong-owner, and changed dependencies.
5. Restart and paginate beyond the first catalog page; verify review restoration and owner isolation.

**Acceptance gate:** Installed destination has only allowed files/context and a fresh identity/browser;
secrets and excluded state are absent; crash retries remain idempotent; execution cannot occur before
required review; a second owner receives no source capability.

**Owners/cases:** `GH-UCP-008`; `GHUCP-013`, `014`, `020`, `025`, `032`.

### `W07` — Complete user connections, beginning with SharePoint

**Final user outcome:** A user connects SharePoint or another supported service once, grants a
bounded capability to a workspace, and the general worker chooses and uses it successfully.

**Current:** The optional broker/reference/grant/renewal boundaries have automated evidence. A real
official SharePoint/Outlook authorization → personal Codex worker read → visible result → compute
release → same-worker reuse path has passed. Confirmed write, brokered-provider parity,
revocation/renewal, brokered-provider parity, and the second-user matrix remain open. Native Gmail
use/reuse in personal Claude also passed without connector-specific GlassHive wiring. See the
[dated native-reuse report](reports/2026-08-16-native-microsoft-workspace-reuse.md) and
[Ultimate Phase 1 QA](reports/2026-08-18-ultimate-phase1-qa.md).

**Smallest plan:**

1. Reuse the existing generic connected-account broker; do not create provider-specific token storage
   or a second consent frontend in GlassHive.
2. Complete one user-scoped SharePoint/Microsoft 365 connection in Connections and show redacted
   readiness only.
3. Grant read scope to one workspace and pass compact factual capability context to the worker.
4. Ask a natural document task. Let the worker choose the tool; inspect the real call/result and
   visible artifact/output.
5. Run a harmless write through the existing explicit human confirmation policy.
6. Test revoked/expired consent, missing mapping, broker outage, rate limit, successful-empty,
   unsupported config, long-running renewal, schedule-time renewal, and cross-user denial.

**Acceptance gate:** Real connected-service read and confirmed write pass from browser and MCP-backed
workspace paths; tokens never enter GlassHive SQLite/workspace/logs; refresh/revocation and a second
user fail or recover truthfully.

**Owners/cases:** `GH-UCP-009`, `GH-UCP-014`; `GHUCP-015`, `016`, `023`, `025`.

### `W08` — Complete the generic Library lifecycle

**Final user outcome:** A user or AI can propose “add this skill/tool/connector,” understand the
source and permissions, confirm once in the browser, use it, upgrade it, disable it, or remove it.

**Current:** Manifest/storage/pending-change/confirmation/bootstrap activation exist; local add/remove
and the repaired 10/10 Library/template baseline pass. No real sourced package has been used by a
worker.

**Smallest plan:**

1. Keep the repaired migration fixtures and complete Library/template slices green before changing
   behavior.
2. Select one neutral, public-safe sourced skill/plugin package and record provenance/hash/profile,
   dependencies, requested scopes, health probe, upgrade, and remove contract.
3. Propose from UI and MCP, confirm only in the human browser, install through the existing profile
   adapter, and verify the workspace grant.
4. Use the capability in a real worker task and inspect the result.
5. Exercise tamper, provenance revoke, incompatible profile, dependency failure, interruption,
   partial rollback, upgrade narrowing/widening, disable, remove, and prior-state restoration.
6. Keep package metadata non-secret and connection/account credentials in their owning surfaces.

**Acceptance gate:** Green full Library suite plus real package install/use/upgrade/disable/remove in
the installed browser; worker self-confirm is denied; failure injection leaves no half-installed or
over-scoped capability.

**Owners/cases:** `GH-UCP-010`; `GHUCP-017`, `018`, `020`, `025`, `028`.

### `W09` — Finish recurring schedules and fire-time renewal

**Final user outcome:** A user schedules a persistent workspace once and receives exactly one
truthful result at the intended local time, including after restart or credential renewal.

**Current:** Native and delegated source paths, recurrence forms, ownership, run-now, and exactly-one
local occurrence have evidence. Installed automatic firing and integrated renewal do not.

**Smallest plan:**

1. Prove exactly one configured recurrence owner and preserve one-shot compatibility.
2. Run automatic one-shot, interval, cron, and RFC 5545 occurrences in the installed product with
   timezone/DST/start/end/overlap/misfire/jitter/catch-up cases.
3. Restart/sleep around claim and dispatch boundaries; prove stale recovery and no duplicate run.
4. At fire time revoke or expire user, delegation, provider account, Library grant, and SharePoint
   consent independently; verify action-required/terminal/retry policy and no silent fallback.
5. Renew the real broker grant, acquire the real provider lease, run the workspace, deliver callback,
   and correlate UI/MCP/activity/occurrence/run/output.
6. Cover pause/edit/delete/run-now and a one-shot missing-provider path without stranding `running`.

**Acceptance gate:** Installed clock-driven runs across restart and a DST boundary produce one
occurrence/run/result; permanent prerequisites pause actionably; transient failures retry the same
occurrence within budget; UI, MCP, activity, DB, and callbacks agree.

**Owners/cases:** `GH-UCP-013`, `GH-UCP-014`; `GHUCP-021`, `022`, `023`.

### `W10` — Preserve Viventium direct-conversation compatibility

**Final user outcome:** The new user control plane and mission-account features do not break
GlassHive as Viventium's direct conversation provider or its current channels/capabilities.

**Current:** Ownership remains additive and compatibility tests exist. No candidate-specific full
installed web/channel/voice/scheduler run is recorded.

**Smallest plan:**

1. Freeze current conversation-provider request/response/session/activity/cancel/reconnect contracts.
2. Run installed web conversation, continuation, reconnect, cancel, tool/capability projection, LIFE
   persistence, and callback.
3. Run applicable channel, voice, and scheduler paths through their existing QA owners.
4. Verify mission account selection never changes conversation account/session semantics.
5. Run protected downstream compatibility only through the approved read-only isolated suite.

**Acceptance gate:** All existing direct-conversation surfaces pass on the exact candidate with no
schema, session, tool, provider, model, callback, wording, or private-boundary regression.

**Owners/cases:** `GH-UCP-001`, `GH-UCP-015`; `GHUCP-001`, `024`, `025`, `026`.

### `W11` — Complete installed isolation and authorization

**Final user outcome:** Two users can safely share a deployment without seeing, controlling, or
using each other's workspaces, accounts, connections, grants, schedules, results, or credentials.

**Current:** Owner scoping, signed assertions, RBAC, replay defense, header scrubbing, and many
synthetic negative tests exist. Full installed two-user and signer/runtime separation are open.

**Smallest plan:**

1. Use two synthetic principals and roles across browser, MCP, API, Watch, desktop, artifacts,
   activity, account, connection, Library, duplicate/template, and schedules.
2. Test wrong owner/tenant, forged headers, wrong issuer/audience/client/scope/role, expired/replayed
   assertion/confirmation, disabled user, and direct runtime reachability.
3. Run gateway signer, runtime verifier, and workers under the intended separate service identities;
   verify private signing material is unreadable from runtime/worker.
4. Rotate signing keys through bounded overlap and remove the old public key after expiry.
5. Scan generated env, mounts, processes, DB, logs, workspaces, provider homes, callbacks, browser
   DOM/accessibility text, and artifacts for credentials/signed URLs/private identifiers.

**Acceptance gate:** Complete installed two-user happy/denial matrix, worker compromise probe cannot
mint assertions, rotation/replay/restart pass, and no secret/private state crosses a public or
wrong-owner boundary.

**Owners/cases:** `GH-UCP-002`, `003`, `005`, `006`, `008`, `009`, `010`, `012`, `016`, `017`;
`GHUCP-003`, `004`, `008`, `009`, `014`–`018`, `020`, `025`, `030`, `031`.

### `W12` — Prove the real delivery chain and continuity

**Final user outcome:** A fresh operator can install, upgrade, restart, restore, and, where supported,
roll back GlassHive without relying on owner-machine leftovers.

**Current:** One sealed canary and exact three-service cutover passed. Fresh public install,
database-inclusive restore, and preceding-version upgrade/rollback are open.

**Smallest plan:**

1. Reverify the existing nested commit and matching parent lock, then verify clean public origin
   reachability and public-safe identity/history after each later change.
2. Install from a fresh clone/new directory using supported public entrypoints only.
3. Inspect compiler outputs, generated client packages/config, permissions, unit definitions,
   runtime provenance, and browser/MCP assets.
4. Quiesce and take a WAL-consistent backup; clone-migrate with schema receipt, integrity/FK checks,
   invariant counts, and owner/tenant samples; restore-test it before cutover.
5. Upgrade from the preceding supported release; test crash recovery at stage/stop/config/state/start/
   acceptance boundaries.
6. Verify runtime/MCP/BFF atomic readiness, stable edge/out-of-scope invariants, explicit accept/reject,
   database-inclusive rollback, and post-restart user journeys.
7. Run final source/pin/shipped/installed provenance and public/private/license scans.

**Acceptance gate:** Clean install plus upgrade/restore/rollback on fresh state and cloned existing
state, with exact source→pin→compiler→installed provenance and all required real user paths on that
installed artifact.

**Owners/cases:** `GH-UCP-016`, `GH-UCP-017`, `GH-UCP-018`; `GHUCP-025`, `026`, `027`, `028`,
`032`, `033`.

### `W13` — Finish usability, accessibility, scale, and performance

**Final user outcome:** The complete flow stays clear, fast, keyboard/screen-reader usable, and
truthful for first-run, narrow screens, large catalogs, multiple workers, and degraded dependencies.

**Current:** Designed Glass Drive navigation, responsive local/hosted checks, keyboard coverage, and
bounded card polling exist. Full screen-reader, large-catalog, and performance acceptance remain.

**Smallest plan:**

1. Test first-run/empty, account setup, missing Work AI, no connections, no Library items, no
   workspaces, and blocked schedule states without dead controls or duplicate failed workspaces.
2. Test pointer, keyboard, screen reader, focus order, labels, live regions, reduced motion, zoom,
   narrow/mobile widths, and account/logout actions.
3. Load a realistic large catalog and activity/occurrence history; measure login, list/search,
   create, open, continue, duplicate, connect, MCP call, schedule fire, and result delivery.
4. Inspect visible and accessibility/copy text for internal IDs, raw URLs, tokens, tool dumps, or
   contradictory status.
5. Judge speed with the Core Outcome Metric; do not improve latency by reducing worker intelligence,
   correctness, capability, or useful feedback.

**Acceptance gate:** Real-browser accessibility and scale matrix on the installed build, recorded
before/after timings, no horizontal clipping or duplicate primary actions, no raw/internal text, and
all degraded paths remain actionable.

**Owners/cases:** `GH-UCP-011`, `GH-UCP-018`; `GHUCP-019`, `025`, `029`, `030`.

## Ordered execution plan

The order is deliberate. Do not start a later phase merely because its code is easier.

### Phase 0 — Restore a truthful green baseline

1. Keep the repaired Library/template baseline green and rerun the complete affected runtime/UI
   slices after the parent pin is updated.
2. Reconcile `coverage.md` with the red snapshot; record exact source, pin, client versions, tool
   count, current hosted artifact, and open gates.
3. Deploy the already committed renewable Codex generated-setup fix independently of packaging;
   prove a fresh native login, restart, and tool call in the intended signed-in browser profile.
4. Preserve the captured escaped-task trace and compare it with the post-install direct-call trace;
   classify action, discovery, invalid-input retry, status, wait/poll, and result-retrieval calls.
5. Record the approved package direction and call-trace/defer/polling acceptance in Requirement 55,
   `cases.md`, and `coverage.md` before changing a public client contract.

Exit gate: affected source baseline is green, the renewable hosted setup works from clean client
state, the problematic call pattern has a preserved trace, and all remaining gaps are classified.

### Phase 1 — Simplify installation and make auth renewable

Complete the packaging/discovery portion of `W01` and the remaining provider matrix in `W02`. Run the
`W10` Viventium direct-conversation and Telegram compatibility guard in this phase, not after the
external contract changes. Do not ship packages around an auth setup known to expire incorrectly.

Exit gate: clean current Codex and Claude package installs pass login, expiry/refresh, restart,
one-call list/launch, revocation, and reconnect against the installed candidate; the measured
call-trace target, direct Viventium conversation, and Telegram regression also pass.

### Phase 2 — Complete identity, accounts, and the core workspace loop

Complete `W03`, `W04`, and `W05`, then `W06`. Do not broaden connectors or schedules until the
identity, account lease, persistence, and duplicate boundaries they depend on are proven.

Exit gate: two-user installed login/account/workspace/duplicate matrix passes with real provider work.

### Phase 3 — Complete Connections and Library

Complete `W07` and `W08` using one neutral real connected-service path and one neutral sourced
Library package. Reuse the existing broker, confirmation, and profile adapter.

Exit gate: real connection and Library capability are installed/granted/used/revoked with no token
copy, self-confirmation, or half-installed state.

### Phase 4 — Complete recurrence and cross-surface parity

Complete `W09` and the remaining full-channel portions of `W10`. Fire-time auth must reuse the
already proven identity/account/connection/Library contracts instead of adding schedule-specific
credential logic.

Exit gate: automatic exactly-once scheduled delivery and the direct Viventium conversation matrix
pass on the same installed candidate.

### Phase 5 — Final isolation, continuity, and release acceptance

Complete `W11`, `W12`, and `W13`. Repeat every high-value real browser/MCP/provider/schedule journey
on the exact clean-installed/upgraded artifact after all changes are present.

Exit gate: every applicable `GHUCP-001`–`033` item is `PASS` for the claimed scope, or an explicitly
approved platform/legal item remains `BLOCKED` and is not advertised as supported.

## Full user-level acceptance matrix

Every surface must cover the applicable columns below. A row is not complete because one column
passed. Hosted browser work must use the intended already-open signed-in browser profile; evidence
from a different profile is inadmissible for that run.

| Surface | QA case(s) | Happy path | First-run/empty | Auth/config missing | Denial/isolation | Retry/interruption | Refresh/restart | Installed evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Login | `GHUCP-002`, `003` | sign in and land | no enrollment/account | provider unavailable | unassigned/disabled/wrong role | cancel/retry/throttle | session expiry/logout | edge, cookie, DB, logs |
| MCP install/use | `GHUCP-001`, `005`, `006`, `020` | install/login/one call | no registration | wrong scopes/resource | wrong client/user/tenant | cancel/reconnect/revoke | token expiry/client restart | native config + MCP logs |
| Provider account | `GHUCP-007`–`010` | connect/test/mission | no account | unsupported/missing key | wrong owner/busy | cancel/failure/reconnect | refresh writeback/runtime restart | mounts, lease, secret scan |
| Workspace | `GHUCP-011`, `012` | create/open/continue | no workspaces | Work AI unavailable | wrong owner | fail/interrupt/close | browser/runtime restart | files/profile/DB/output |
| Duplicate/template | `GHUCP-013`, `014` | create/review/use | empty source | missing dependency | wrong owner | crash/idempotent retry | review restore | source/destination scan |
| Connection | `GHUCP-015`, `016` | connect/read/write | no services | expired/revoked/outage | wrong owner/scope | renew/retry/confirm | long run/restart | broker/grant/tool/result |
| Library | `GHUCP-017`, `018`, `028` | inspect/confirm/use/remove | empty catalog | incompatible/tampered | self-confirm denied | partial install/rollback | upgrade/restart | files/hash/grant/audit |
| Schedule | `GHUCP-021`–`023` | create/fire/result | no schedules | missing account/grant | disabled principal | overlap/misfire/stale claim | sleep/restart/DST | occurrence/run/callback |
| Viventium direct | `GHUCP-001`, `024` | chat/tools/result | new conversation | provider unavailable | wrong identity | cancel/reconnect | session/runtime restart | web/channel/voice evidence |
| Release | `GHUCP-025`–`033` | fresh install/use | clean state | missing prerequisite | private/public boundary | crash/reject/rollback | upgrade/restore | source/pin/runtime hashes |

## Decisions and blockers requiring explicit closure

| Decision/blocker | Current rule | Closure evidence |
| --- | --- | --- |
| Personal Claude subscription | Advertise only the explicitly enabled isolated Linux native route; keep unsupported platforms and fixed API-key brokerage omitted | Installed native login/mission/reuse, contention, and real two-user isolation |
| Native package distribution | Shared source with thin OpenAI and Claude packages is implemented; both official manifests validate and isolated local installs work | Publish, clean remote install/update/remove, and installed hosted one-call proof |
| External call complexity | Do not infer cause from the 60-tool count; extend native defer/discovery only where supported and own async completion | Preserved before/after trace separating discovery, retry, polling, and result calls; compatibility regression |
| Generic OIDC refresh | Never universalize an Entra-only scope | Discovery/config contract and supported/unsupported provider tests |
| SharePoint enterprise consent | Use the existing user-scoped broker by default | Approved tenant app/consent, real user connect, worker read/write, revoke/renewal |
| Second user and second provider account | Required for isolation acceptance | Installed concurrent happy path and full cross-owner denial matrix |
| Clean install/upgrade environment | Owner checkout is not acceptance | New-directory public install and preceding-version upgrade/restore/rollback |
| Protected downstream compatibility | Read-only and private | Downstream owner-run isolated regression; no names/data/examples enter public artifacts |

## Anti-drift operating rules

1. Begin every implementation turn by reading this ledger, Requirement 55, the affected cases, and
   the latest report. Select one next incomplete workstream and name its exit gate.
2. Trace `user action → UI/MCP → gateway → service/store → worker/broker → visible result` before
   editing. Fix the owning boundary, not the complaint wording.
3. Prefer the smallest supported native mechanism. If a plan adds a protocol, auth flow, duplicate
   store, provider-specific frontend, or more user steps, stop and compare the existing native/broker
   path first.
4. Preserve the complete existing public MCP tool/field contract. Reduce what a client must reason
   over only through native discovery/defer mechanisms that client already supports; never remove or
   hide an existing public tool, and never branch the MCP schema on client identity.
5. Do not add tool-listing or workflow narration to prompts/skills to compensate for an oversized or
   ambiguous API. Fix the interface and descriptions.
6. Do not branch on prompt text, provider display names, people, customers, or machine state. Use
   structured identity, IDs, declared capabilities, profile metadata, and policy.
7. Update statuses only with a dated evidence link that states build, real surface, visible outcome,
   backend/state corroboration, and what was not run.
8. Never call a browser/client/provider flow `PASS` from unit tests, source inspection, DB/logs, or a
   model review alone.
9. Keep public evidence synthetic and path-free. Raw private evidence stays outside the public repo.
10. After any nested change, verify nested commit → parent lock → compiler/generated package →
    running artifact before claiming it shipped.
11. If a real user path fails after a prior fix, reopen the incident. Do not explain it away from old
    evidence.
12. Keep this ledger concise enough to operate: completed detail belongs in dated reports; enduring
    behavior belongs in Requirement 55/cases; this file retains only current status and next work.
13. Do not let rollout, backup, recovery, pruning, or release-helper work become the product task.
    Reuse the supported delivery path and change it only when a blocker prevents the exact user
    acceptance journey from running safely.

## Definition of complete

The full goal is complete only when:

- all advertised identity, provider, workspace, connection, Library, MCP, and schedule paths pass
  their real installed happy and unhappy journeys;
- a fresh Codex and Claude installation is obvious, renewable, and one-call for ordinary work;
- the same operations and owner boundaries agree across Glass Drive and MCP;
- two users and two provider accounts are proven isolated under concurrency and restart;
- a real SharePoint/connected-service capability and a real Library package are used by a worker;
- automatic recurring work survives expiry, renewal, restart, DST, overlap, and retry exactly once;
- Viventium's direct GlassHive conversation and protected downstream compatibility remain intact;
- clean install, upgrade, DB restore, rollback, signer isolation, accessibility, scale, and public
  safety pass on the exact shipped build; and
- every remaining unsupported platform/provider route is absent or clearly labeled, with no false
  success or silent fallback.

Until those gates pass, report the precise narrower scope that is accepted and keep the overall
status **PARTIAL**.

## Official design references

- [OpenAI plugins](https://learn.chatgpt.com/docs/plugins)
- [OpenAI skills](https://learn.chatgpt.com/docs/build-skills)
- [OpenAI MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [Claude Code plugins](https://code.claude.com/docs/en/plugins)
- [Claude Code MCP](https://code.claude.com/docs/en/mcp)
- [MCP authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
- [MCP OIDC refresh-token guidance](https://modelcontextprotocol.io/seps/2207-oidc-refresh-token-guidance)
- [Microsoft identity scopes and `offline_access`](https://learn.microsoft.com/en-us/entra/identity-platform/scopes-oidc)
