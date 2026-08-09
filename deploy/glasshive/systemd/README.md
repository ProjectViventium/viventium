# GlassHive hosted split services and atomic rollout

Hosted `multi_user` mode runs one three-service release under two operating-system identities:

- `glasshive-gateway` runs Glass Drive and the public MCP security boundary. Only this identity may
  read the internal assertion signing key.
- `glasshive-runtime` runs the verifier-only worker runtime and receives only public verification
  material.
- `glasshive-runtime` uses its own rootless Docker daemon. It never joins the host's rootful Docker
  group; access to the rootful socket is effectively host-root and defeats the signer/runtime split.
- both identities join `glasshive-state` for shared state using group mode `0660`/`0770`.
- only `glasshive-gateway` joins `glasshive-gateway-secrets`.

The three units are one release group. Each is `PartOf=glasshive.target`, but rollout still stops and
starts all three explicit unit names and proves that every process stopped. PID existence is never a
readiness result. UI starts after runtime. Its `ExecStartPost` proves nested runtime health and reads
the initialized auth-registry schema through the gateway identity; MCP has `Requires`/`After` on UI,
so an MCP-first OAuth enrollment cannot race first-start auth schema creation. This dependency is
one-way and introduces no UI-to-MCP cycle.

Administrator-preapproved OIDC access uses the same sealed interpreter, gateway identity, groups,
EnvironmentFiles, and writable state root as Glass Drive. Do not run a source-checkout or generic
host Python against the gateway database. With a secret manager supplying a temporary `0600` JSON
file or ephemeral descriptor, run:

```bash
sudo /opt/viventium/current/deploy/glasshive/systemd/glasshive_auth_admin.py \
  preapprove-oidc --stdin-json < /run/private/glasshive-principal.json
```

The one-shot wrapper never accepts subject/email metadata on argv. It invokes the gateway module
through `systemd-run --pipe`, and the module returns only an opaque user ID. Delete only that exact
temporary input after the command returns. Repeating the same issuer + subject is idempotent;
preapproval never silently re-enables a disabled principal. The wrapper holds the same root-owned
`/run/lock/glasshive-rollout.lock` mutation lock as production deploy/recovery for the complete
one-shot. If a rollout is active it exits with retry guidance rather than writing a rehearsal clone
or state that rollback could overwrite. Production rollout configs must use that exact lock path.

The same wrapper owns optional local-password administration for that exact preapproved principal:

```bash
sudo /opt/viventium/current/deploy/glasshive/systemd/glasshive_auth_admin.py \
  set-local-password --stdin-json < /run/private/glasshive-local-credential.json
sudo /opt/viventium/current/deploy/glasshive/systemd/glasshive_auth_admin.py \
  unlock-local-password --stdin-json < /run/private/glasshive-principal.json
sudo /opt/viventium/current/deploy/glasshive/systemd/glasshive_auth_admin.py \
  disable-local-password --stdin-json < /run/private/glasshive-principal.json
```

Passwords and identity metadata remain on stdin and must never appear in argv, environment values,
shell history, or logs. `set-local-password` attaches only by exact configured OIDC subject; it never
searches by email. Before disabling the feature or activating an older OIDC-only release, run
`glasshive_auth_admin.py revoke-local-sessions`, prove local sessions are rejected, then activate the
predecessor. OIDC sessions remain independent.

## Immutable release layout

The active pointer is `/opt/viventium/current`, but it may point only to a sealed release below
`/opt/viventium/releases`. A release contains a `glasshive-release.json` manifest binding the parent
commit, exact nested GlassHive commit, every staged file, and both frozen virtual environments.

Create it only from a clean committed parent whose `components.lock.json` GlassHive pin equals the
nested commit:

```bash
sudo python3 /path/to/viventium/deploy/glasshive/systemd/glasshive_rollout.py stage \
  --source /path/to/viventium \
  --releases-root /opt/viventium/releases \
  --release-id release-YYYYMMDD-N \
  --uv /opt/viventium/toolchain/bin/uv \
  --python /opt/viventium/toolchain/python/bin/python3
```

Staging uses committed `git archive` input, never a working-tree copy. For the runtime and Glass
Drive it first creates a supported `uv venv --relocatable`, then runs `uv sync --frozen --no-dev
--link-mode copy` against that environment. The helper keeps each project editable so source-layout
assets remain available, but rewrites the generated absolute source `.pth` entry to a relative path.
It then physically relocates the complete staging tree and imports both owning packages with
bytecode writes disabled before the artifact can be sealed. This proves the source paths survive the
atomic parent-directory rename without embedding the temporary probe path in generated files. It
also verifies required executables and symlink containment, includes resolved external-interpreter
content in the manifest hash, and removes write permission from the release. An unresolved, mutable,
or changed interpreter target fails closed. A dirty checkout, stale component pin, unexpected
symlink, missing lock, dependency failure, relocation/import failure, or existing destination is
terminal. Services invoke the frozen `.venv` executables directly; no unit resolves dependencies at
startup.

## Service identities and rootless Docker

Example host preparation (adapt package installation to the supported Linux distribution):

```bash
sudo install -d -m 0755 /etc/viventium/glasshive /opt/viventium/releases
sudo groupadd --system glasshive-state
sudo groupadd --system glasshive-gateway-secrets
sudo useradd --system --create-home --home /var/lib/glasshive --shell /bin/bash \
  --gid glasshive-state glasshive-runtime
sudo useradd --system --home /var/lib/glasshive --gid glasshive-state \
  --groups glasshive-gateway-secrets glasshive-gateway
sudo install -d -o root -g glasshive-state -m 0770 /var/lib/glasshive
sudo install -d -o root -g glasshive-state -m 0770 /var/lib/glasshive/.rollout-candidates
sudo install -d -o root -g root -m 0700 /var/lib/glasshive-rollouts
sudo install -d -o glasshive-gateway -g glasshive-gateway-secrets -m 0700 \
  /var/lib/glasshive/gateway
```

Install Docker's supported rootless prerequisites and assign the runtime user unique subordinate UID
and GID ranges of at least 65,536 entries. Then install its user daemon and enable lingering:

```bash
sudo machinectl shell glasshive-runtime@ /bin/bash -lc 'dockerd-rootless-setuptool.sh install'
sudo loginctl enable-linger glasshive-runtime
```

The host must load `br_netfilter` and enable bridge IPv4/IPv6 netfilter before the rootless daemon
creates GlassHive's internal-only worker network. Its systemd user manager must also expose the
`cpu`, `memory`, and `pids` controllers; worker limits fail closed if any requested controller is
missing. Verify both prerequisites on the target host before staging:

```bash
sudo modprobe br_netfilter
sudo sysctl -w net.bridge.bridge-nf-call-iptables=1
sudo sysctl -w net.bridge.bridge-nf-call-ip6tables=1
runtime_uid="$(id -u glasshive-runtime)"
test -r "/sys/fs/cgroup/user.slice/user-${runtime_uid}.slice/user@${runtime_uid}.service/cgroup.controllers"
grep -qw cpu "/sys/fs/cgroup/user.slice/user-${runtime_uid}.slice/user@${runtime_uid}.service/cgroup.controllers"
grep -qw memory "/sys/fs/cgroup/user.slice/user-${runtime_uid}.slice/user@${runtime_uid}.service/cgroup.controllers"
grep -qw pids "/sys/fs/cgroup/user.slice/user-${runtime_uid}.slice/user@${runtime_uid}.service/cgroup.controllers"
sudo -u glasshive-runtime env XDG_RUNTIME_DIR="/run/user/${runtime_uid}" \
  DOCKER_HOST="unix:///run/user/${runtime_uid}/docker.sock" \
  docker info --format '{{.CgroupDriver}}' | grep -qx systemd
```

Persist the module, sysctls, and systemd controller delegation with the host distribution's normal
configuration mechanism; an interactive one-time setting is not an accepted deployment state.

`runtime-active.env` supplies `DOCKER_HOST=unix:///run/user/<uid>/docker.sock`. Before every runtime
start, `glasshive_rootless_docker_probe.py` calls Docker through that socket and requires the daemon's
JSON `SecurityOptions` to advertise `rootless`. Socket reachability alone is insufficient. Rootful,
unavailable, malformed, or ambiguous socket results fail startup.

## Static and active environments

The config compiler writes the secret-capable static files:

- `/etc/viventium/glasshive/runtime.env`
- `/etc/viventium/glasshive/gateway.env`

Install the runtime file as `root:glasshive-state 0640` and the gateway file as
`root:glasshive-gateway-secrets 0640`. The runtime file contains no auth database, signing-key, or
OIDC secret. The private assertion key remains readable only by the gateway identity.

### Bounded internal-assertion key rotation

Rotate without exposing the old private key to runtime or workers:

1. Generate a new owner-only gateway private key and a new unique `key_id`.
2. Export only the prior key's public JWK into a public-only JWKS file.
3. For the rotation rollout, set `internal_assertion.private_key_file` and `key_id` to the new
   signer, plus `previous_public_jwks_file` and an absolute `previous_keys_expire_at` 180-900
   seconds in the future. Six hundred seconds is the normal overlap.
4. Compile and inspect split service environments: the gateway receives the private signer and
   previous public JWKS; runtime receives only the public JWKS URL and neither file path.
5. Start the candidate, verify the public JWKS contains both key ids, exercise an assertion signed
   by each key, and confirm new assertions use only the new key id.
6. After the absolute expiry, verify the old key disappears from the public JWKS. Remove both
   previous-key fields and the old public file in the next controlled rollout.

Startup fails closed for private JWK material, duplicate ids, invalid RSA keys, partial rotation
configuration, and overlap windows outside 180-900 seconds. The old private key is never required.

Use the real unit paths and preserve those ownership boundaries when installing compiler output:

```bash
sudo install -o root -g glasshive-state -m 0640 \
  /path/to/generated/runtime.env /etc/viventium/glasshive/runtime.env
sudo install -o root -g glasshive-gateway-secrets -m 0640 \
  /path/to/generated/gateway.env /etc/viventium/glasshive/gateway.env
```

The rollout helper owns two non-secret slot files, both `0640`:

- `runtime-active.env`: runtime port, state/database paths, rootless socket, phase-specific
  background-consumer/reconciliation policy, and immutable release provenance;
- `gateway-active.env`: MCP/UI ports, runtime loopback URLs, auth database path, watch-session
  state beside that database under the writable state root, and the same immutable release
  provenance.

The explicit watch-session path prevents the hardened gateway unit from falling back to its
read-only service home. Runtime worker-image staging is retry-safe even though sealed release lock
inputs and prior staged copies are read-only.

The public-safe provenance keys are `GLASSHIVE_RELEASE_ID`, `GLASSHIVE_PARENT_REVISION`, and
`GLASSHIVE_COMPONENT_REVISION`. They come from the verified staged manifest; they are not a guessed
or artificially bumped package version. Runtime, UI, and MCP must expose the exact release id,
parent revision, and GlassHive revision through readiness before the candidate may cut over.

The helper writes them atomically while the complete service group is stopped. They must never
contain secrets. The first managed deployment must stage the existing healthy release as an
immutable predecessor, point `/opt/viventium/current` to it, and create slot files for its ports
before an upgrade can run. Install reviewed predecessor slot files at their exact unit paths so the
helper can preserve their owner and group across atomic rewrites:

```bash
sudo install -o root -g glasshive-state -m 0640 \
  /path/to/reviewed/runtime-active.env /etc/viventium/glasshive/runtime-active.env
sudo install -o root -g glasshive-gateway-secrets -m 0640 \
  /path/to/reviewed/gateway-active.env /etc/viventium/glasshive/gateway-active.env
```

An unmanaged checkout or ad-hoc process is not a rollback target. Validate the staged predecessor,
its two slot files, and all three services before treating the first managed rollout as atomic.

Install the units after a release exists:

```bash
sudo install -m 0644 /opt/viventium/current/deploy/glasshive/systemd/*.service \
  /etc/systemd/system/
sudo install -m 0644 /opt/viventium/current/deploy/glasshive/systemd/glasshive.target \
  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable glasshive.target
```

## Microsoft Entra registration contract

Hosted Entra supports either one existing tenant-specific confidential registration that serves both
Glass Drive web sign-in and the exposed API resource, or separate confidential web and API resource
registrations. Use separate public-client registrations for Claude Code and Codex. Do not use
`common`, email as the principal, dynamic client registration, a shared public-client secret, or a v1
access token. Reuse a suitable existing registration and preserve its callbacks, permissions, roles,
and consumers instead of creating a duplicate application.

The application exposing the API resource must keep its exact client-id GUID as the access-token
`aud`, issue v2 tokens, expose one delegated scope, and preauthorize only the reviewed public clients.
In combined mode this is the same registration used by Glass Drive web sign-in; in split mode it is
the dedicated API registration:

```json
{
  "signInAudience": "AzureADMyOrg",
  "groupMembershipClaims": null,
  "appRoles": [
    {
      "id": "<stable-api-member-role-uuid>",
      "allowedMemberTypes": ["User"],
      "displayName": "GlassHive Member",
      "description": "Use owner-scoped GlassHive MCP tools.",
      "isEnabled": true,
      "value": "GlassHive.Member"
    },
    {
      "id": "<stable-api-viewer-role-uuid>",
      "allowedMemberTypes": ["User"],
      "displayName": "GlassHive Viewer",
      "description": "View owner-scoped GlassHive resources.",
      "isEnabled": true,
      "value": "GlassHive.Viewer"
    },
    {
      "id": "<stable-api-admin-role-uuid>",
      "allowedMemberTypes": ["User"],
      "displayName": "GlassHive Tenant Administrator",
      "description": "Administer this GlassHive deployment.",
      "isEnabled": true,
      "value": "GlassHive.TenantAdmin"
    }
  ],
  "api": {
    "requestedAccessTokenVersion": 2,
    "oauth2PermissionScopes": [
      {
        "id": "<stable-scope-uuid>",
        "value": "user_impersonation",
        "type": "User",
        "isEnabled": true,
        "adminConsentDisplayName": "Use GlassHive as the signed-in user",
        "adminConsentDescription": "Allow this client to use owner-scoped GlassHive MCP tools.",
        "userConsentDisplayName": "Use your GlassHive account",
        "userConsentDescription": "Allow this client to use your owner-scoped GlassHive MCP tools."
      }
    ],
    "preAuthorizedApplications": [
      {
        "appId": "<registered-claude-public-client-id>",
        "delegatedPermissionIds": ["<stable-scope-uuid>"]
      },
      {
        "appId": "<registered-codex-public-client-id>",
        "delegatedPermissionIds": ["<stable-scope-uuid>"]
      }
    ]
  }
}
```

Both public clients are single-tenant, have `isFallbackPublicClient: true`, no credential, delegated
`requiredResourceAccess` to `<stable-scope-uuid>`, and only their exact registered loopback redirect:

- Claude Code: `http://localhost:<fixed-registered-claude-loopback-port>/callback`.
- Codex: `http://127.0.0.1:<fixed-registered-codex-loopback-port>/callback/<server-hash>`.

The Codex hash is derived by the supported client from the canonical MCP URL. Copy the complete URI
shown by Glass Drive Connect AI; never calculate, wildcard, or shorten it. The confidential
registration used by Glass Drive stores its credential through the deployment secret reference and
registers both exact public reply URIs:

- login callback: `https://glasshive.example.com/auth/oidc/callback`; and
- logout/account-switch return: `https://glasshive.example.com/login` (the exact configured
  `human_auth.oidc.post_logout_redirect_uri`).

In combined mode, web redirects, the exposed API scope, role values, and assignment policy live on
one registration and service principal. In split mode, the web registration must define the same
app-role **values** as the API registration—`GlassHive.Member`, `GlassHive.Viewer`, and
`GlassHive.TenantAdmin`—with its own stable role UUIDs. In **Enterprise applications → Properties**,
set **Assignment required? = Yes** on every enterprise application used: once in combined mode, or
on both web and API applications in split mode. Assign each approved user/security group to a mapped
app role on every application used. An organization that replaces this with a Conditional
Access/application-assignment gate must document, review, and test that equivalent deny-by-default
control before enabling GlassHive; an open tenant-wide application is not supported. Browser ID
tokens carry roles from the web client; MCP access tokens carry roles from the exposed API resource.
In split mode, defining or assigning a role on only one app produces cross-surface authorization
drift.

When reusing an existing registration that already serves another application, do not flip its
service principal to assignment-required until every current consumer is inventoried and assigned;
that change can cause an unrelated login outage. A required mapped-role check that rejects missing or
unmapped roles may instead be the reviewed deny-by-default GlassHive admission gate. Preserve the
shared app's existing callbacks, permissions, roles, secrets, and consumers, then add only the exact
GlassHive callbacks and assignments needed by the deployment.

Bind all registrations to one exact tenant id and issuer
`https://login.microsoftonline.com/<tenant-id>/v2.0`. Configure GlassHive with:

- principal claim `oid`; independent GlassHive ownership namespace `enterprise.tenant_id`; and
  optional upstream token tenant policy
  `GLASSHIVE_MCP_OAUTH_TOKEN_TENANT_ID=<entra-directory-tenant-guid>`;
- token audience `<glasshive-api-app-client-id-guid>`, using the combined app client id in combined
  mode or the API app client id in split mode;
- authorization/request scope
  `GLASSHIVE_MCP_OAUTH_REQUIRED_SCOPES=api://<glasshive-api-app-client-id-guid>/user_impersonation`,
  with the same combined-or-split resource client id;
- access-token claim scope `GLASSHIVE_MCP_OAUTH_TOKEN_SCOPES=user_impersonation`;
- allowed client ids equal to the two preauthorized public-client app ids; and
- role claim `roles` with the same explicit map for browser and MCP values, for example
  `{"GlassHive.Member":"member","GlassHive.Viewer":"viewer","GlassHive.TenantAdmin":"tenant_admin"}`.

The compiler rejects multi-user OIDC configuration without a non-empty role map. The deployment
still fails admission unless every enterprise application uses assignment or the reviewed
deny-by-default mapped-role gate above: canonical GlassHive
`integrations.glasshive.enterprise.human_auth.allow_principal_enrollment` controls creation of an
already admitted principal and is not an IdP access policy. The runtime `allow_registration` value
is only a one-release upgrade fallback. Assign users or security groups to matching app
roles on the combined app, or on both web and API apps in split mode, so both token types carry
bounded `roles`. Keep
raw group claims disabled unless the deployment has separately implemented and tested group-overage
resolution; truncation or a `_claim_names` overage response must never recover to a write-capable
role. Before cutover, obtain a token through each real client and verify v2 issuer, API `aud`, `tid`,
stable `oid`, requested full resource scope, access-token `scp` claim must equal `user_impersonation`,
allowed client id, mapped role, and exact redirect. The authorization scope and token claim value are
intentionally different Entra representations; accepting the full URI in `scp` or using the short
claim as the authorization request is a configuration failure. Wrong tenant, audience, scope,
client, redirect, missing role, or raw-group overage fails closed.

## Adapter boundary

Public code cannot safely infer a deployment's filesystem snapshotter, HTTPS edge, identity proxy,
or synthetic authentication client. The rollout therefore requires three root-owned, non-writable,
absolute executable adapters. Each reads one schema-1 JSON object from stdin, writes one JSON object
of at most 64 KiB to stdout, and exits nonzero on uncertainty. Outputs contain opaque receipt IDs
and named check results only—never credentials, cookies, user data, database rows, or signed URLs.

### State adapter

Actions are `snapshot`, `clone`, `seal_clone`, `restore`, `commit`, and `cleanup_clone`.

- `snapshot` runs only after all writers are proven stopped. It snapshots associated non-database
  state and returns `{"ok":true,"snapshot_id":"..."}`. Declared SQLite paths are excluded because
  the rollout helper backs them up with SQLite's backup API.
- `clone` materializes the snapshot into the supplied empty candidate state directory without
  signing keys or secret gateway configuration, creates every declared candidate database parent
  with the requested runtime-shared or gateway-only access boundary, and returns `clone_id`.
- `seal_clone` runs after the helper has copied the SQLite backups. It applies and verifies the
  declared `0660` runtime-shared and `0600` gateway-only ownership/modes, proves the runtime identity
  cannot traverse/read the auth database, and returns `seal_clone_id`.
- `restore` transactionally restores associated state and returns `restore_id`. It must not open or
  overwrite the declared SQLite paths.
- `commit` records retention of the pre-upgrade snapshot and returns `commit_id`; it must not destroy
  rollback evidence before the rollout journal is terminal.
- `cleanup_clone` safely removes only the adapter-owned candidate clone and returns
  `cleanup_clone_id`. It must also tolerate cleanup after a partially failed `clone`.

An adapter action that exits nonzero must be atomic: it may not report failure after changing live
state. All state receipts are local, owner-only deployment artifacts.

### Ingress adapter

Actions are `inspect`, `switch`, `restore`, and `status`.

- `inspect` proves the complete predecessor release and returns `snapshot_id` plus
  `active_release_id`.
- `switch` applies the complete supplied route contract atomically. Glass Drive owns exact `/`,
  `/auth`, `/login`, `/confirm-change`, `/favicon.ico`, `/health`, `/static`, `/ui`, and `/v1`, plus
  `/auth/`, `/static/`, `/api/`, `/r/`, `/watch/`, `/desktop/`, `/novnc/`, `/ui/`, and `/v1/` path
  families; `/novnc/` preserves websocket
  upgrade. Exact `/mcp` and
  `/.well-known/oauth-protected-resource/mcp` routes directly to MCP without an `oauth2-proxy` HTML
  redirect; and exact `/.well-known/jwks.json` to the BFF. It strips every client-supplied identity
  header whose name begins `X-Viventium-`, `X-GlassHive-`, or `X-LibreChat-`, except that the
  browser route captures and restores the BFF's `X-GlassHive-CSRF` double-submit token exactly as
  declared by `browser.preserve_client_headers`. The adapter must capture the token before the
  prefix scrub and must not restore any other prefixed header. It never exposes the
  runtime upstream. It returns the exact `active_release_id` and SHA-256 of the canonical route
  contract only after the edge has converged. Canonical JSON is UTF-8 with recursively sorted object
  keys and compact `,`/`:` separators.
- `restore` atomically restores the inspected route set.
- `status` independently proves the expected complete release after cutover or rollback. Candidate
  status must attest the same canonical route-contract SHA-256; a generic healthy edge is not enough.

The UI unit disables Uvicorn access logs because the OIDC callback query contains one-time `code`
and `state` values. The ingress adapter must likewise disable query-string logging or redact the
complete query for `/auth/oidc/callback` before persistence or export. Candidate and live acceptance
capture sanitized service/edge logs and fail unless neither raw value appears; query-bearing access
logs are never public QA evidence.

The helper marks a switch attempted before invoking the adapter. A lost response therefore restores
the inspected ingress snapshot instead of assuming the switch did nothing.

### Acceptance adapter

Actions `preflight`, `candidate`, `live`, and `rollback` return `checks` with boolean `true` for every
required check. Candidate validation requires authenticated MCP initialize, browser identity flow,
and the designed Glass Drive root on the alternate-port group. Candidate and live validation also
prove that runtime, UI, and MCP report the exact staged manifest provenance. Live validation proves
every named browser route family, including noVNC websocket upgrade, reaches the same Glass Drive
release; both MCP routes reach MCP; MCP does not receive an `oauth2-proxy` HTML redirect; JWKS reaches
the BFF; every named identity-header family is scrubbed; and
`browser_csrf_header_preserved` performs an authenticated, harmless state-changing request through
the public edge with the real session cookie and double-submit header while a spoofed identity
header is present. It passes only when the mutation succeeds for the authenticated subject, the
spoof is absent upstream, and no other prefixed client header survives. The runtime is not public.
Preflight and rollback validate the preceding release under its
existing supported route contract, allowing a fail-closed migration away from a legacy catch-all
without pretending that the predecessor already has the candidate routes. Missing checks, mocked
success, or a generic HTTP 200 fail closed.

## Database rehearsal, cutover, and rollback

Copy `rollout.example.json` outside git, replace only deployment paths/origins/adapter locations, and
review every invariant table. Invariant evidence records counts and SHA-256 digests of ordered
owner/tenant identity samples; it never records raw identities.

Run the rollout:

```bash
sudo python3 /opt/viventium/current/deploy/glasshive/systemd/glasshive_rollout.py deploy \
  --config /etc/viventium/glasshive/rollout.json
```

The transaction is:

1. verify both immutable manifests, distinct port slots, rootless Docker, predecessor local
   readiness, ingress identity, and full hosted acceptance;
2. explicitly stop UI, MCP, and runtime; prove all units inactive and scan `/proc/*/fd` for every
   live database and committed WAL/SHM inode;
3. snapshot associated state; use SQLite's backup API for each database; restore-test it; run
   `quick_check`, `integrity_check`, `foreign_key_check`, table counts, and hashed owner/tenant
   invariants;
4. clone the snapshot and databases; point the sealed candidate at alternate loopback ports and
   clone-only paths; disable all autonomous queue, schedule, callback, and lifecycle consumers;
   start all three services; run local runtime/BFF/MCP/JWKS readiness plus the
   authenticated candidate adapter; stop the group and compare post-migration invariants;
5. point the same candidate at the live databases while the predecessor remains stopped; enable
   the single-runtime autonomous consumers and startup reconciliation; rerun all
   local checks and invariants; atomically switch ingress only after success; run full hosted
   acceptance and independently inspect ingress;
6. commit the journal and retain the verified pre-upgrade snapshot/backups under the deployment's
   retention policy.

Any ordinary failure stops the complete candidate, restores ingress if a switch was attempted,
restores associated state and every verified SQLite backup, restores the predecessor symlink and
slot files, restarts all three predecessor services, and reruns local plus hosted acceptance. An
incomplete rollback exits nonzero and remains journaled; it never degrades to binary-only rollback
against a candidate-mutated database.

After host or process loss, a second deploy is refused until the exact journal is recovered:

```bash
sudo python3 /opt/viventium/current/deploy/glasshive/systemd/glasshive_rollout.py recover \
  --config /etc/viventium/glasshive/rollout.json \
  --transaction-id rollout-<timestamp>-<id>
```

Only one deploy/recovery process can hold the rollout lock. Terminal journals and verified backups
remain local deployment evidence; they are not public QA artifacts.

## Readiness and remaining acceptance

Local hard readiness requires runtime `/health` JSON `status=ok`; BFF `/health` JSON `status=ok`
with nested runtime `status=ok`; exact MCP resource/issuer/scopes; unauthenticated initialize `401`
with the configured protected-resource challenge; and a non-empty public JWKS. During candidate
rehearsal and live preparation, runtime `/health` must include `release`, UI `/health` must include
the same top-level `release` and `runtime.release`, and MCP `/health` must include the same `release`.
The object must exactly equal
`{release_id,parent_revision,glasshive_revision}` from the staged manifest. The acceptance adapter
supplies the required real authenticated MCP/browser/edge and provenance checks.

The helper and failure-injection tests are source-level deployment evidence. Release acceptance
still requires a clean staged artifact on the intended Linux host, installed unit verification,
real adapter implementations, real identity/MCP/browser runs, injected service/edge/state failures,
successful rollback, log/state correlation, and an operator-approved monitoring window. Do not mark
`GHUCP-032` or `GHUCP-033` passed from unit tests alone.
