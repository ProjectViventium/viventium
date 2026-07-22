# 39. Installer and Config Compiler

## Purpose

This document is the public installer source of truth for the `./install.sh` and `bin/viventium`
paths, plus the generated-runtime boundary enforced by the config compiler.

## Owning Flow

1. `./install.sh` clones or refreshes the repo checkout, then execs `bin/viventium install`.
2. `bin/viventium install` owns the public first-run flow:
   - wizard/config selection
   - preflight prerequisite detection and install
   - component bootstrap
   - config compilation
   - doctor validation
   - helper install
   - detached local startup plus health wait
3. Generated runtime files are written under `~/Library/Application Support/Viventium/runtime/` and
   are outputs, not authoring surfaces.
4. LibreChat startup then re-seeds the built-in Viventium agents from the git-tracked/source-of-truth
   agents bundle:
   - `viventium_v0_4/viventium-librechat-start.sh`
   - `viventium_v0_4/LibreChat/scripts/viventium-seed-agents.js`
   - `viventium_v0_4/LibreChat/viventium/source_of_truth/local.viventium-agents.yaml`

## Installer UX Requirements

- The primary startup wait UI must stay honest:
  - elapsed time
  - current startup step
  - which required surfaces are still pending
- Interactive TTY installs may render a second, playful tagline line below the truthful status line.
- The playful line must never replace the real health/status line or hide an actual failure.
- Headless and non-interactive installs stay on plain repeated progress logs only.
- Installer copy must remain public-safe and hardcoded from product code:
  - no secrets
  - no personal data
  - no machine-specific jokes or runtime-derived private state
- Animation contract for the playful line:
  - fast type-in effect
  - hold around five seconds once fully shown
  - rotate randomly
  - avoid immediately repeating the same line

## Easy Install Native And Docker Target Product Contract

### Objective

The supported Easy Install journey is for a nontechnical person on a clean Mac. One public command must
install an exact Viventium release, open browser setup, connect one preferred model provider, prove
that provider with a real request, and land in a useful persistent chat. Optional capabilities must
never block the first useful answer.

`Easy Install Native` and `Easy Install Docker` are the approved capability-profile target over one
installer transaction, canonical config compiler, service supervisor, setup UI, connection-state
model, upgrade/rollback path, and QA contract. They must not become separate installers or
duplicate onboarding flows. The current immutable candidate packages Native only; Docker remains a
source-candidate/physical-QA lane and must not be advertised as a shipped artifact yet.

- `Easy Install Native` is the first clean-machine acceptance lane. Its required core is local account,
  provider connection, text chat, chat history, saved memory, built-in agents, Prompt Templates,
  Agent Builder, Feelings, restart persistence, repair, upgrade/rollback, and preserve-data
  uninstall/restore.
- The planned `Easy Install Docker` profile uses the same state machine and adds Docker Desktop plus
  the capabilities whose current owning runtimes require containers. A Docker failure must degrade
  only those capabilities and must not falsify the native core's readiness.
- “80% covered in the VM” means installer, onboarding, continuity, recovery, and core-product
  reliability—not a claim that 80% of all optional features run without Docker.

### First-Use Sequence

The normative Easy Install sequence is:

`verified bootstrap -> read-only preflight -> recovery checkpoint -> journaled install -> live core health -> browser first-user setup -> OpenAI key save -> live provider probe -> first rendered optimized Viventium answer -> Ready`

- The terminal asks no provider secret and no optional-integration question before browser setup.
- Browser setup asks only what is necessary for the first useful answer. It preserves a drafted
  first prompt across authentication, failure, retry, and reload.
- Services outside the immutable core require Custom Settings Install today. Easy Install must not
  suggest that an omitted service can be added in place until a signed optional-component
  transaction exists.
- Supported OAuth-capable providers use the external system browser with state and PKCE. OpenAI and
  Anthropic currently document subscription login for their own Codex and Claude Code clients, not
  a general Viventium OAuth entitlement. Easy Install therefore defaults to a browser-entered API
  key stored through the encrypted user-key path. The legacy direct subscription bridges remain an
  explicit experimental Custom Settings option for compatible existing installs; they must not be
  presented as official or stable, and the supported migration target is the vendor-owned client
  integration surface (for OpenAI, `codex app-server`).
- Provider evidence for this boundary:
  - [OpenAI `codex app-server` auth endpoints](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#auth-endpoints)
    expose vendor-managed ChatGPT login for rich clients.
  - [OpenAI Codex CLI sign-in guidance](https://help.openai.com/en/articles/11381614-api-codex-cli-and-sign-in-with-chatgpt)
    says disconnect does not revoke generated API keys and no public automated key-deletion endpoint
    exists.
  - [Anthropic account/API separation guidance](https://support.anthropic.com/en/articles/9876003-i-subscribe-to-a-paid-claude-ai-plan-why-do-i-have-to-pay-separately-for-api-usage-on-console)
    distinguishes Claude subscriptions from general API access.
- Consumer subscriptions and API entitlements are distinct. In particular, Groq API access and
  xAI API access must not be inferred from a Groq or Grok consumer account.
- Easy Install exposes stable browser-entered API-key cards for OpenAI, Anthropic, Groq, and Grok
  (xAI) in one Connected Accounts surface. Groq and Grok compile as `user_provided` custom
  endpoints so the encrypted per-user key is required; removing it must prevent another provider
  request rather than falling back to a machine-level credential or the literal sentinel.
- The stable headed-browser lifecycle is proven for all four cards with synthetic loopback
  providers: native Anthropic Messages protocol for Anthropic and OpenAI-compatible protocols for
  OpenAI, Groq, and Grok. Each proof includes two answers, refresh and runtime-restart persistence,
  invalid/quota/outage/network repair, local Disconnect with no new provider request, and key re-add.
- That four-card proof covers credential transport, raw model selection, persistence, and failure
  handling. It does not prove optimized Viventium main-agent, cortex, Feelings, memory, or quality
  parity. OpenAI is the intended optimized Easy Install path today, but readiness is not claimed
  until a live request and visible first answer succeed; other cards add
  explicitly selected models without replacing the Viventium brain.
- Provider selection remains explicit. Saving a Groq or Grok key does not silently change an
  existing conversation's provider/model, and no provider is remapped to another provider.
- `Configured` is never rendered as `Ready`. Readiness requires a current live self-test, records
  when it was tested, and classifies authentication, authorization/scope, quota/rate limit,
  network, unhealthy dependency, unsupported configuration, and update-required failures.

Provider credentials have two distinct owners and must not drift between them:

- Easy Install browser-entered keys are encrypted per-user LibreChat state. They are not canonical
  config, macOS Keychain entries, generated runtime values, or reusable machine credentials. The
  compiler exposes OpenAI, Anthropic, Groq, and Grok through the literal `user_provided` capability
  sentinel; it never replaces that sentinel with another provider's machine key.
- Custom Settings Install may reference machine-level provider keys from canonical config through
  `keychain://` references. The compiler resolves OpenAI, Anthropic, Groq, and xAI through one
  provider-to-runtime mapping, writes resolved source-runtime and service env files mode `0600`,
  and keeps the immutable Native behavior contract secret-free with `user_provided` sentinels.
- Restart preserves encrypted per-user keys in the selected runtime database. Source upgrade
  recompiles from canonical config inside its transaction and checkpoints database state; a
  missing Keychain reference fails before generated runtime replacement. Portable snapshot/restore
  intentionally excludes provider credentials and records reauthentication as required. Source
  uninstall moves the complete App Support tree to its recoverable local removal backup; Native
  uninstall removes runtime/payload material while preserving user data. Neither uninstall mode nor
  restore may describe a local delete as provider-side revocation.
- The headed lifecycle must inspect persistent browser state after valid-key entry, refresh,
  runtime restart, invalid-key entry, Disconnect, and re-add. Cookies, local/session storage,
  Cache Storage, and IndexedDB must not contain the synthetic credential. This check supports the
  encrypted-server-state claim but does not prove a real provider account or final signed payload.

### Public Install Names And Compatibility Values

The installer uses plain user-facing names while preserving the existing machine-readable contract:

| Public installer choice | Canonical config value | Intended use |
| --- | --- | --- |
| **Easy Install** | `install.experience: express` | Recommended guided native-first setup with optional capabilities deferred until after the first working answer. |
| **Custom Settings Install** | `install.experience: custom` | Deliberate selection of runtime mode, providers, integrations, and optional capabilities during installation. |

The public labels must never leak the internal `express` name into installer, startup, status, or
recovery copy. The schema/API/runtime values remain `express`, `custom`, and the existing `legacy`
compatibility state so current configs, upgrades, browser onboarding, and generated artifacts do not
break. Missing `install.experience` continues to resolve through the documented legacy-existing-user
path; it must not be silently rewritten merely to change a label.

### Native Core And Deferred Capabilities

The product-grade Native core must use prebuilt, versioned artifacts and a pinned runtime. A fresh
user must not need Docker, Homebrew, Git, Xcode Command Line Tools, pnpm, uv, Python, or a system
Node installation to reach the first answer.

Required before Native core readiness:

- a pinned production Node runtime plus prebuilt LibreChat/Viventium server and client;
- the smallest current persistence runtime required by LibreChat, bound to loopback and limited by
  an explicit memory budget;
- local first-user creation, one working provider, text chat, persistence, built-in product
  surfaces, helper/supervisor health, and recovery metadata.

Deferred until the core is ready unless a later accepted requirement proves otherwise:

- Groq or xAI activation credentials beyond the user's selected first provider;
- GlassHive worker authentication, Prompt Workbench schedules, and nightly automation;
- voice, LiveKit, local speech models, and the modern voice playground;
- conversation Recall/RAG, local SearXNG/Firecrawl, Code Interpreter, Microsoft 365 MCP, Skyvern,
  and GlassHive Docker workstation execution;
- Telegram, Google Workspace, Slack, WhatsApp, remote access, transcript ingestion, and additional
  providers.

Deferral is not permission to deliver a stale optional runtime. When Voice is enabled after core
readiness or selected through **Custom Settings Install**, the supported browser surface is the
modern Viventium playground. Its `/api/health` response must identify the exact surface, variant,
and 40-character component source ref. A generic HTTP success or an old classic listener on the
configured port is not healthy. An installed start or upgrade replaces a safely identified stale
Viventium-managed listener; an unrelated process is never killed merely to reclaim its port.

The Docker LiveKit server is an optional runtime artifact, not the nested placeholder checkout. Its
release identity is owned by `release/optional-runtime-components.json` and must be invoked using the
exact patch tag plus multi-architecture OCI index digest. A managed container is reusable only when
its configured image and Viventium image/source labels match the lock. Custom external/native
LiveKit remains allowed only when deliberately configured and reachable. Viventium does not discover
or execute `livekit` or `livekit-server` from `PATH`: the upstream v1.13.4 release does not provide a
Viventium-verified macOS server artifact, so an arbitrary local executable cannot satisfy release
identity. Until a signed, version-verified native artifact is added, Voice uses the exact Docker
runtime or a user-configured external endpoint; Custom Settings Install without either fails closed
and explains how to enable Docker, configure `LIVEKIT_API_HOST`, or start without Voice. An explicit
endpoint override that is unhealthy also fails closed without silently starting Docker, and an
unconfigured listener occupying the default port is preserved but never adopted as LiveKit. The
early Native dependency stack is not an alternate server owner: supported `bin/viventium start`
skips LiveKit there and delegates Voice to the provenance-aware launcher. A direct attempt to enable
Native-stack LiveKit fails before MongoDB/Meilisearch startup and never installs or executes a
`PATH` binary. The v1.13 upgrade lane must explicitly test or migrate TURN credentials that omit
TTL; port reachability alone does not prove TURN media.

### Storage-Bounded Release QA

Clean-machine proof must not consume unbounded owner-machine storage. Source, unit, compiler, and
browser checks run before any disposable machine is created. After the candidate is frozen, QA may
create one disposable VM at a time, capture public-safe evidence outside the VM, and delete that VM
immediately after the case. Docker QA uses explicitly named Viventium test resources and measured
before/after disk usage. It must never use global prune, delete unrelated volumes, or multiply
machine clones to parallelize acceptance. Logical sparse-disk size and physical disk usage are
reported separately.

`scripts/viventium/qa_storage_guard.py` is the executable gate for that policy, and
`qa/installer-resilience/storage-policy.json` owns its reviewed budgets. Before clone it requires an
empty `viventium-qa-*` inventory, enough free space, a read-only Docker resource baseline, the exact
Docker sparse-disk identity, and an exclusive persistent run lease. Clone always exports
`TART_NO_AUTO_PRUNE=1`; Tart must never make storage available by automatically deleting another
machine. Guarded work is an argument vector, not a shell string. Known shells, direct deletion tools,
prune operations, and wildcard arguments are refused.

The lease and receipt are intentionally not self-expiring. An interruption, child failure, missing
pre-existing Docker resource, context/disk replacement, low free-space floor, or growth-budget breach
stops only the guarded child process group and leaves `CLEANUP_REQUIRED`. A leader exit is not command
completion: the guard probes the exact process group, terminates lingering descendants, escalates to
`SIGKILL` even after the leader has exited, and refuses success unless that owned group is proven
empty. Cleanup requires the run ID twice, refuses any unowned QA VM, and can delete only the exact
receipt-owned VM. It never deletes a Docker container, image, volume, cache, or sparse disk. Cleanup
also refuses to finish while any post-baseline Docker container, volume, or image remains; the
reviewed QA driver must remove its own exact synthetic objects first. A persistent clean Docker-disk
baseline blocks cumulative physical/logical growth across guarded runs; it is never silently reset.
Raw resource IDs and machine-local receipts remain outside the public repository in private QA
evidence.

The default policy requires 100 GiB free before a run, aborts below 60 GiB, bounds total host growth
at 32 GiB, Docker physical growth during a run at 16 GiB, Docker physical residue at 4 GiB, and
Docker sparse logical growth from the persistent baseline at 64 GiB. These are safety ceilings, not
resource requirements for Viventium. Changing them requires code review and the same fake-tool
regressions; raising a limit to make a failing run pass is not remediation.

Meilisearch is not assumed to be a core prerequisite merely because the current source launcher
starts it. The implementation must prove whether current chat startup requires it. If conversation
search can be disabled safely, Easy Install Native defers Meilisearch and exposes it as an optional
capability; otherwise the acceptance evidence must record why it remains in the core.

### Isolated Browser Artifact Runtime

LibreChat Artifacts execute browser code and therefore must never share the authenticated app
origin. Every supported runtime owns a second loopback-only origin with one coherent identity:

- Native uses the release-owned proxy on `127.0.0.1:3191`; the API listener is disabled and the
  assembled `index.html` digest is bound into release metadata. Candidate builds require the exact
  audited digest, while synthetic local-QA builds carry and verify their own recorded digest.
- source local prod uses an API-owned listener on `127.0.0.1:3191`; the default `dev` environment
  offsets it to `4191`; compatibility mode uses `3091`.
- Docker must build or pin the exact Viventium LibreChat image that contains the listener and the
  prepared runtime. Merely mapping a port on an unrelated upstream image is not support.

`SANDPACK_BUNDLER_URL` and `SANDPACK_STATIC_BUNDLER_URL` are canonical absolute origin-root URLs
for the same listener and must match its port. Runtime readiness requires the API and isolated
artifact listeners to belong to the same process on source/Docker, or to the same guarded Native
proxy release. Installer, status, helper, watchdog, stop/restart, upgrade, and collision recovery
must include the isolated origin. A missing, stale, foreign, same-origin, traversal-capable, or
non-on-prem runtime fails closed without being reported healthy.

The isolated server permits only the required loopback/browser origins, validates `Host`, constrains
framing to the app origin, exposes only regular files under the prepared root, and serves `GET` or
`HEAD`. Unhashed runtime filenames must revalidate across upgrades; only demonstrably
content-addressed assets may be immutable-cached. A cold artifact can still download declared npm
dependencies from their package CDN; local bundler ownership means no CodeSandbox bundler or
analytics transport, not zero dependency-network traffic.

### Packaging, Install, And Upgrade Boundary

- The public command is a thin bootstrap. It detects supported OS/architecture, downloads an
  immutable versioned manifest and payload, verifies integrity and publisher identity, stages into
  a new release directory, starts it, waits on real readiness, and rolls back automatically on
  failure.
- Source clone, package-manager dependency resolution, arbitrary `postinstall` execution, and
  compilation on the user's Mac are developer flows, not the final Easy Install product path.
- Release directories are immutable. Upgrade stages and validates the next version before an atomic
  active-version switch. Failed readiness returns to the last known-good compatible release.
- Data/schema migration and binary activation are separate gates. A pre-migration recovery point is
  mandatory, and automatic binary rollback must not pretend an incompatible data migration was
  reversed.
- Public distribution requires the applicable Developer ID signature, hardened runtime,
  notarization, stapled ticket, manifest digests, exact component pins, and independent installed-
  artifact verification. Local unsigned QA artifacts must say they are local QA artifacts and are
  not public-release evidence.
- MongoDB or any other third-party runtime may be bundled only after its redistribution/license
  boundary is accepted and recorded in the public/private/license matrix. Until then, an exact
  publisher-hosted, digest-verified download is the safer implementation boundary.

The historical source runtime's Node 20 requirement was not a shippable Native artifact decision;
Node 20 is end-of-life. A July 18, 2026 source-candidate production client/data-provider build
passes on Node `24.16.0`. Post-review remediation now aligns preflight, shared PATH setup, doctor,
dependency repair, the LibreChat launcher, the optional Skyvern launcher, and the macOS helper CLI
PATH on Node 24, with a six-surface regression contract; 90 focused preflight/launcher tests and a
fresh helper build pass. That is source-candidate evidence, not exact-artifact
acceptance. The first packaged candidate must ship one pinned official supported runtime and repeat
build/start/restart/process-path proof on the exact installed artifact. Node single-executable
applications remain active-development and are not the first packaging boundary; ship a pinned
official runtime plus immutable production code first.

Pull-request automation must use explicit architecture labels rather than `macos-latest`. The
source-level compiler lane runs on both `macos-15` (`arm64`) and `macos-15-intel` (`x86_64`) and
asserts the observed architecture before testing. All third-party GitHub Actions are pinned to full
commit SHAs, workflow permissions default to read-only, Node automation uses major 24, and the
secret-scan container is pinned by image digest. These hosted images contain developer tools, so
their two-architecture source checks support but never replace the pristine no-tools payload gate.

### Finder-Launched Native Bootstrap Experience

Opening `ViventiumBootstrap.app` from Finder with no arguments is a native **Easy Install** surface,
not a terminal-only wrapper. It must present one accessible AppKit window with a truthful current
stage, progress, bounded public-safe detail, safe Cancel, visible success/failure, Retry, Quit, and
Open Viventium. The window must never render child stdout/stderr, raw commands, paths, token-bearing
URLs, secrets, or unbounded logs. Open Viventium uses the fixed local client origin; it never derives
a destination from installer output.

Cancellation begins cooperatively. The bootstrap sends an interrupt to the bundled installer,
disables repeat cancellation, and says **Cancel requested — finishing a safe checkpoint…** while
the installer's journaled recovery/activation boundary finishes. If the installer does not exit,
the bootstrap escalates after bounded grace periods to termination and then kill so Cancel cannot
leave an indefinitely running install. The Python installer owns every spawned release command in a
separate process group, drains that group when interrupted, removes an unpublished staging attempt,
restores the prior pointer before a durable health result, and preserves a health-passed activation.
Abrupt termination may still require the durable journal to finish recovery on Retry. The window
must never infer rollback merely from a signal; success or recovery remains owned by installer
exit/health and journal evidence, not optimistic copy.

Any command-line invocation, including `--self-check`, remains headless and forwards the exact
arguments, stdout, stderr, and exit status while still executing only the signed bundled Python at
`Contents/Resources/runtime/python/bin/python3`. The Finder window discards child streams rather than
capturing or displaying them, which bounds memory and prevents secret/path disclosure.

Standard AppKit controls carry explicit accessibility labels/help, Return activates the current
primary action, Escape requests Cancel while work is active, and visual state is not communicated by
color alone. Normal installs use indeterminate progress; when macOS Reduce Motion is enabled, the
bootstrap shows a static progress state plus the same textual stage. This follows Apple's
[AppKit accessibility guidance](https://developer.apple.com/documentation/appkit/accessibility-for-appkit),
[accessibility label contract](https://developer.apple.com/documentation/appkit/nsaccessibilityprotocol/setaccessibilitylabel(_:)),
and [Reduce Motion signal](https://developer.apple.com/documentation/appkit/nsworkspace/accessibilitydisplayshouldreducemotion).

### Current Local Implementation Status — 2026-07-20

The local source candidate implements public **Easy Install** through the shared internal
`install.experience: express` profile with Native
mode, API/web-only core readiness, deferred heavy services, browser Connected Accounts handoff,
truthful Easy Install startup copy, and current-attempt build-failure detection. Easy Install
preflight fetches
the exact MongoDB `8.0.23` publisher archive, verifies its pinned digest, bounded extraction,
Developer ID team, and reported version, and installs the allowed runtime files under app-owned
state rather than requiring the Homebrew tap. Easy Install preflight and startup fail closed unless that
exact app-owned binary and its loopback listener/process arguments match; arbitrary `PATH` or
Homebrew Mongo remains a legacy/custom-path option only. API, web, status output, and the startup
banner use loopback truth in local mode.

The browser handoff persists `setup=accounts` across registration/login, requires a configured
trusted server origin for OAuth instead of trusting the request `Host`, and scopes popup/poll/manual
completion work to one attempt identity so stale async results cannot corrupt a newer connection.
The disposable browser lane proves the stable browser-entered API-key lifecycle for OpenAI,
Anthropic, Groq, and Grok/xAI with synthetic loopback providers: two useful answers, refresh and
runtime-restart persistence, invalid/quota/outage/network repair, local disconnect with zero later
provider contact, and key re-add. This proves the integrated disposable source-runtime path only.
The same lifecycle must still pass from the final immutable installed artifact before release.

`scripts/viventium/native_payload.py` and its tests implement the signed-manifest, hostile-archive,
immutable-activation, journal/lock, interruption recovery, idempotent re-activation, and health-
gated rollback boundary. `scripts/viventium/build_native_payload.py` now produces deterministic,
deflated per-architecture ZIPs and canonical manifests, with a visibly unsigned `local-qa` channel
and a fail-closed signed `stable` channel. Determinism is guaranteed for the pinned build
interpreter/toolchain; it is not a cross-interpreter compression claim.
`assemble_native_payload.py`, the Native supervisor/process guard, and the bundled-Python bootstrap
source own relocatable target execution. Runtime secrets are generated atomically under
machine-local App Support state with mode `0600`, PID records bind signals to a release-owned
guard/start token, and helper replacement requires an ownership marker with retained rollback. The
public shell bootstrap has an opt-in Native hand-off with embedded release/digest/Developer ID trust
slots, but those slots are intentionally empty; it refuses source fallback until approved public
trust and signed bootstrap bytes are provisioned. The current default remains the source installer.
The protected release lane is globally serialized and must advance the complete signed Native
GitHub release history by exactly one sequence (the first release is sequence `1`). Every prior
Native bootstrap index, including a retained draft, is downloaded, signature-verified with the
pinned Ed25519 public key, structurally validated, and checked for duplicate tags/sequences and any
gap in the complete `1..N` history before signing starts. The tagged `install.sh` carries a reviewed
minimum-sequence floor equal to the candidate;
it validates the outer signed sequence and requires the Developer-ID-signed app's embedded
`release.json` to match the outer release tag, release id, origin, and sequence. The embedded policy
then requires the separately signed payload manifest to match that same release id and sequence,
while activation retains the owner-only highest-sequence state for established installs.

This closes accidental sequence reuse, workflow races, mixed bootstrap/payload releases, and
rollback on an established install. A truly pristine Mac has no prior high-water state, however,
and cannot cryptographically distinguish an older valid signed bootstrap plus an older copy of the
public shell from the current release without an independently authenticated freshness source.
The reviewed sequence floor protects a current authentic shell; it is not a transparency log or
timestamp authority. Public Native release acceptance therefore still requires an authenticated
current bootstrap distribution boundary (or equivalent external append-only freshness authority)
in addition to provisioning the intentionally absent signer and Apple trust values. No local test
or source fallback may claim to satisfy that external authority.

Native assembly is also a public/private boundary. Compiled prompt metadata uses identifiers and
paths relative to the prompt-registry root; it must never serialize the compiler checkout path.
Assembly removes runtime logs, audit JSON, Python bytecode, caches, and package-manager/development
surfaces that the Native runtime does not execute. Node is staged as its exact executable plus
license, MongoDB as `mongod` plus required notices, and Python as the interpreter, non-GUI standard
library/native extensions, CPython license, and the exact hash-pinned python-build-standalone
dependency-license set. The payload and Bootstrap receive byte-identical staged Python trees. Each
copy is bound to the architecture archive digest, Python version, license-source commit/digest, and
every staged path/mode/size/hash through the same deterministic component manifest; candidate and
post-sign archive verification must validate both copies independently. The candidate producer
strips producer-local Swift debug metadata and immediately ad-hoc re-signs both candidate
executables so the linker signature remains valid. The bootstrap always invokes its bundled Python
with `-B`, so self-check and install cannot write producer-local bytecode into the signed app.
After the complete apps and helper ownership marker exist, the candidate workflow runs self-check,
ad-hoc seals both outer app bundles, and strict-verifies them before scanning; the protected workflow
later replaces those candidate signatures with Developer ID signatures. The producer then
runs `verify_native_public_safety.py` over the exact assembled candidate. That gate rejects
forbidden artifact shapes, scans every byte—including binaries—for the exact producer workspace and
temporary prefixes, and scans Viventium-owned/generated surfaces for private home/temp paths and
high-confidence credential material. The protected release workflow repeats the gate after download
and again after signing/compliance generation, before packaging or release assets are created.

The secret-free candidate workflow declares exact arm64/x86_64 lanes, verifies pinned Node
`24.16.0`, Python `3.12.13`, MongoDB `8.0.23`, and the LibreChat component commit, builds the full
LibreChat packages/static client, then installs only the backend workspace production dependency
tree beside those build outputs. Frontend packages omitted from physical `node_modules` are not
omitted from compliance: the exact Rollup input closure and package-owned notices must be normalized,
copied, hash-bound, and verified before the backend-only tree is accepted. A missing compiled-client
notice or unresolved build input is a release blocker. The workflow then compiles canonical
defaults, builds both macOS apps, assembles the
relocatable payload, and declares a real install/start/registration/Connected Accounts/health smoke.
The assembled `release-metadata/build.json` must carry the exact sanitized projection of that
component policy: the LibreChat full commit plus each shipped runtime version and architecture
archive digest. Assembly rejects missing or malformed commit/digest values, and extracted artifact
metadata is compared directly with the policy; producer paths, URLs, credentials, and local state
are not part of the embedded projection.
Native first-admin reconciliation runs against that pruned production tree. Its maintenance helper
uses the driver already exposed by the retained Mongoose production dependency. The built
`@librechat/api` package has a separate direct runtime import of `mongodb`, however, and Rollup keeps
that import external. The package therefore declares `mongodb` as a peer dependency while the
consuming backend declares it as a production dependency; keeping it only as a package build/test
dependency is forbidden. After every production prune, the candidate workflow must execute the
built `@librechat/api` entrypoint. Resolving the file without loading it is not sufficient, because
that would miss an externalized direct import.
The protected Native release workflow pins all actions, accepts only a successful same-repository and
same-commit architecture candidate, signs nested code and both apps with Developer ID and hardened
runtime, notarizes and staples supported containers, builds and verifies the signed manifest,
independently installs/health-checks both architecture payloads and bootstrap archives, attests an
exact public-asset allowlist, explicitly confirms GitHub immutable releases, and creates a complete
draft. It does not publish. Both workflows fail closed until the release owner records approved
manifest/Apple trust, MongoDB redistribution approval, protected Apple/manifest authorities, and
repository environment controls. A provisional exact local-QA payload was installed in a disposable
vanilla guest, but startup failed before registration because its pruned runtime omitted the direct
`mongodb` dependency required by built `@librechat/api`. That candidate was rejected. The structural
package-boundary fix and a clean install/build/prune/load regression now pass, but the replacement
payload has not been rebuilt or rerun through the pristine lifecycle. No candidate Actions or
Developer ID/notary run has occurred, so this remains `PARTIAL`, not production acceptance. The
current evidence is recorded in
`qa/installer-resilience/reports/2026-07-19-native-payload-production-integration.md`.

Native canonical defaults have a separate compiler-owned `native-runtime.env` contract. It contains
only relocatable behavior/model settings, fixed Native profile/ports, and disabled `START_*` flags;
provider credential values, arbitrary secret-shaped keys, unresolved `${...}` values, build paths,
and compiler-owned URL/path settings are forbidden. The exact `OPENAI_API_KEY=user_provided` and
`ANTHROPIC_API_KEY=user_provided`, `GROQ_API_KEY=user_provided`, and
`XAI_API_KEY=user_provided` entries are permitted fixed capability sentinels, not credentials; any
other value or secret-shaped key fails validation. Assembly requires and copies that exact file,
install validates it before writing the mode-`0600` App Support runtime environment, and child
services start from a fixed system environment plus this contract, generated machine secrets, and
explicit release-owned local paths/ports. Host provider values are never inherited; the four fixed
sentinels replace them regardless of the invoking shell.
The same contract carries `VIVENTIUM_CONNECTED_ACCOUNTS_ENABLED=true` as a capability declaration,
not a credential. LibreChat projects that flag into startup configuration so Native Easy Install can
show the stable OpenAI, Anthropic, Groq, and Grok API-key setup surface without inheriting a provider
secret or enabling the separate experimental subscription bridge. A visible panel is not sufficient
acceptance: the exact payload must save, use, repair, disconnect, re-add, and persist each supported
synthetic provider lifecycle through the installed browser surface.
An explicit `VIVENTIUM_CONNECTED_ACCOUNTS_ENABLED=false` is authoritative over legacy discovery
signals. The capability flag never enables `/api/connected-accounts/*` subscription OAuth routes;
those remain separately fail-closed behind `VIVENTIUM_EXPERIMENTAL_DIRECT_SUBSCRIPTION_AUTH`.
The candidate compiler disables MCP servers whose runtimes are not bundled. First-admin success is
not returned until the release-owned close hook has restarted the backend with direct registration
closed. The one-time URL must exchange its query token for a bounded HttpOnly SameSite cookie and
redirect to a token-free URL before rendering. Its CSP must allow only the required same-origin setup
request; password confirmation, progress, service failure, mismatch, retry, replay, and ordinary
`/register` navigation must all have explicit outcomes. The browser must never embed the token in
page JavaScript or leave ordinary registration as a silent `403`. The compiler also emits a
Native-specific agent bundle that removes tools, tool options,
direct-action ownership, and handoffs backed only by unavailable MCP servers. Initial boot must not
seed the agent system owner before the real admin exists, because that synthetic user would close
first-user registration; the post-registration restart reconciles the new user's installer-owned
defaults, seeds the exact compiled agent bundle, and verifies the default agent in MongoDB. Candidate
acceptance must probe direct port
`3180` before setup, after setup, and after restart, then prove login and default-agent health. Those
exact-candidate checks are declared but have not run, so this boundary remains `PARTIAL`.

### Native Build And Release Contract

- Local QA uses `build_native_payload.py --channel local-qa`; the unsigned manifest is accepted only
  through the explicit verifier override and can prove deterministic packaging, hostile extraction,
  activation, health, interruption, retry, and rollback behavior. It cannot prove publisher identity,
  Gatekeeper acceptance, notarization, or public installation.
- Production uses `build_native_payload.py --channel stable` only inside the protected workflow.
  Stable output requires the private SSH manifest key, a committed allowed-signers policy, an approved
  Apple team policy, Developer ID Application signing, hardened runtime, trusted timestamp,
  notarization success, stapling where Apple supports it, and installed-artifact verification.
- The manifest signer public key and Apple team identifier are public pinned policy. Private keys,
  certificate material, passwords, and notary credentials are protected environment secrets and must
  not transit candidate artifacts or public bootstrap environment variables.
- The release workflow consumes architecture-specific payload/bootstrap roots from the implemented
  successful same-commit producer. The producer assembles the pinned runtime without secrets,
  declares complete inside-out Apple code-signing/staple targets, and runs target-like smoke checks.
  Its actual dual-architecture execution and exact artifacts remain acceptance blockers, and its
  distributable mode fails closed until the license matrix records MongoDB redistribution approval.
- Native release workflows are globally serialized. Before any protected signing work, the workflow
  verifies every GitHub release carrying a Native bootstrap index and signature, rejects incomplete,
  malformed, unsigned, duplicate-tag, or duplicate-sequence history, requires sequence `1` for the
  first release and exactly `highest + 1` thereafter, and requires the tagged public bootstrap's
  embedded minimum sequence to equal that candidate. A release may not skip or reuse a sequence.
- The public bootstrap downloads only an exact release-named bootstrap archive over HTTPS, verifies
  its embedded SHA-256 and exact Developer ID team, validates the stapled ticket and Gatekeeper
  assessment, binds the outer signed release identity/sequence to the app's embedded release policy,
  and then hands off. The embedded policy binds the payload's signed release id and sequence, and
  activation rejects anything below the established local high-water mark. Trust values are
  compile/review inputs, not environment overrides.
  Until real approved values and reviewed signed bootstrap digests exist, Native mode must fail
  before network or source execution; source mode remains an explicitly separate developer/local-QA
  path.

Apple's current guidance requires Developer ID authority and hardened runtime for outside-App-Store
distribution, `notarytool` submission, inspection of the accepted result, and stapling to supported
containers. GitHub's current guidance supports protected environments, full action-SHA pinning,
artifact attestations, and immutable releases built as a complete draft before publication. See the
[Apple certificate guidance](https://developer.apple.com/help/account/certificates/create-developer-id-certificates/),
[Apple notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow),
[GitHub environment controls](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments),
[GitHub secure-use guidance](https://docs.github.com/en/actions/reference/security/secure-use), and
[GitHub immutable-release guidance](https://docs.github.com/en/enterprise-cloud@latest/code-security/concepts/supply-chain-security/immutable-releases).

### Easy Install Threat Model

Assets: provider credentials and refresh tokens, local user/session data, canonical config,
conversation/memory databases, recovery payloads, code-signing/update trust, and the last-known-good
runtime.

| Trust boundary | Abuse case | Required control and evidence |
| --- | --- | --- |
| Network bootstrap -> local machine | DNS/TLS compromise, mutable branch, replayed or downgraded manifest | Minimal bootstrap, embedded trust root, signed monotonic manifest, exact digest, supported-version policy, replay/downgrade tests |
| Download -> staging/extraction | Corrupt archive, path traversal, symlink escape, decompression bomb, executable substitution | Size limits, allowlisted archive paths/types, private attempt directory, no-follow extraction, per-file manifest, signature/notarization verification, hostile-archive tests |
| Existing install -> candidate | Partial overwrite, concurrent installers, cancellation or power loss | Exclusive lock, append-only stage journal, immutable releases, recovery checkpoint, atomic pointer, kill/reboot-at-each-stage tests |
| Candidate -> active data | Incompatible or malicious migration, rollback with newer data | Declared schema compatibility, pre-migration backup, migration journal, independent restore proof, no binary rollback claim without data rollback |
| Local browser -> setup API | LAN attacker creates first admin, CSRF, origin confusion, session theft | Explicit loopback bind, one-time setup nonce, strict Origin/Host validation, CSRF/session controls, registration closes by policy, loopback/LAN and replay tests |
| System browser -> OAuth callback | Redirect interception, code injection, state replay, wrong account/scope | External browser, PKCE-S256, unpredictable state, exact loopback callback, single use/expiry, least scopes, live identity/capability display, denial/replay/wrong-account tests |
| App -> Keychain/helper | Plaintext secret fallback, logs/process args leak, over-privileged persistent service | Keychain references, no secret CLI args/env/logs, user-level least-privilege service, redacted diagnostics, secret/process-list/filesystem tests |
| Optional capability -> core | Docker/worker/voice outage blocks chat or reports false Ready | Declared capability graph, independent health states, timeouts, circuit/degraded behavior, core-first readiness and dependency-failure matrix |
| VM guest -> personal host | Writable mount, clipboard/audio leakage, host credential reuse | No host/home mounts, clipboard/audio off by default, dedicated synthetic accounts/SSH key, pinned guest host key, immutable stopped baseline and disposable clones |

The bootstrap script, manifest/archive contents, browser inputs, OAuth responses, provider results,
and migration metadata are all untrusted inputs. Installer/runtime code must validate them at their
owning boundary; prompts and model output are never security controls.

### Commands And Owning Structure

- Public entrypoint: `./install.sh` and the future verified one-line bootstrap that invokes the same
  installer contract.
- Public lifecycle: `bin/viventium install`, `bin/viventium configure`, `bin/viventium status`,
  `bin/viventium doctor`, `bin/viventium upgrade --restart`, snapshot/restore, and uninstall.
- Installer/config/compiler/runtime ownership remains under `scripts/viventium/` and
  `bin/viventium`; browser onboarding remains in the LibreChat nested repository and must follow
  the nested commit -> parent pin -> built artifact -> installed artifact delivery chain.
- Requirements stay in this document. Reusable cases and dated public-safe evidence stay under
  `qa/installer-resilience/` and linked feature-owner QA folders.

Implementation style follows the existing structural boundaries: canonical schema fields and
declared capabilities instead of prompt, provider-label, machine, or user-name heuristics; one
shared state transition model instead of per-surface booleans; additive, rollback-friendly slices;
and no edits to generated App Support outputs as a product fix.

### Testing And Acceptance

- Every behavior change starts with a failing synthetic test and a linked installer QA case.
- Disposable Apple Silicon macOS VM acceptance covers exact bootstrap/payload, no-developer-tools
  install, account-first browser setup, first real model answer, persistence, idempotence,
  interruption, offline/corrupt payload, low resources, port collisions, auth failure classes,
  restart, repair, upgrade rollback, uninstall-preserve, and restore.
- A physical disposable Mac remains mandatory for Docker Desktop first-launch/permissions,
  Docker-only services, microphone/audio, sleep/wake, LAN/device behavior, and final full-Easy-Install
  resource acceptance.
- Required browser evidence is visible action -> visible result/detail -> refresh/restart ->
  supporting log/DB/state/config/artifact evidence. Source, mocks, unit tests, or model review do not
  replace the user path.
- Initial measurable budgets are setup page within five minutes on a normal broadband connection,
  warm startup under twenty seconds, idle core memory under 1.5 GB, normal text chat under 3 GB,
  loopback-only default listeners, and no undeclared system prerequisite. These are acceptance
  targets until a dated clean-machine run proves or revises them.

### Boundaries

- Always: protect existing-user continuity; use attempt-scoped state; redact diagnostics; verify
  exact artifacts; keep optional capabilities deferrable; fail with one specific recovery action.
- Ask before: adding dependencies, changing persistence schema, accepting a redistribution license,
  requesting privileged macOS permissions, destructive clean-machine reset, or any cloud action.
- Never: use personal state as a clean-install prerequisite; store provider secrets in tracked or
  generated plaintext config; call configured-only state ready; silently install Docker-only
  capabilities in Easy Install Native; publish or push without explicit approval.

### Success Criteria

Easy Install Native is accepted only when the exact candidate artifact completes the first-use sequence
in a disposable clean macOS VM, every applicable happy/unhappy/recovery case has evidence, restart
and restore preserve the promised state, and the measured resource budgets are recorded. Easy Install
Docker is accepted only after the same artifact/state machine passes the Docker and physical-device
delta on the disposable MacBook Air. Until those gates pass, release wording remains `PARTIAL` or
`BLOCKED`; source implementation alone is not “done.”

## Config Compiler Boundary

- The config compiler still owns generated runtime artifacts such as:
  - `runtime.env`
  - `runtime.local.env`
  - `librechat.yaml`
  - service-specific env files such as `runtime/service-env/telegram.config.env`
- GlassHive launch/watch defaults are part of that same generated-runtime contract:
  - `GLASSHIVE_DEFAULT_LAUNCH_SURFACE`
  - `GLASSHIVE_SHOW_LIVE_TERMINAL_IN_DESKTOP`
  - `WPR_IDLE_DESKTOP_PRIME_BROWSER`
  - `GLASSHIVE_HOST_WORKERS_ENABLED`
  - `WPR_HOST_WORKSPACE_ROOT`
  - `WPR_DEFAULT_EXECUTION_MODE`
  - `WPR_HOST_DESTRUCTIVE_CONFIRMATION`
  - `WPR_HOST_ADVISORY_REVIEWER_ENABLED`
  - `WPR_HOST_PROMPT_VISIBILITY`
  - `WPR_LIBRECHAT_UPLOADS_ROOT`
  - `WPR_BOOTSTRAP_SOURCE_ROOTS`
  - `WPR_DB_PATH`
  - `WPR_CODEX_BIN`
  - `WPR_CLAUDE_CODE_BIN`
  - `WPR_OPENCLAW_BIN`
  - `VIVENTIUM_GLASSHIVE_CALLBACK_URL`
  - `VIVENTIUM_GLASSHIVE_CALLBACK_SECRET`
  - `VIVENTIUM_GLASSHIVE_CAPABILITY_BROKER_SECRET`
  - `GLASSHIVE_ENTERPRISE_MODE`
  - `GLASSHIVE_AUTH_MODE`
  - `GLASSHIVE_ENTERPRISE_TENANT_ID`
  - `GLASSHIVE_IDLE_TERMINATE_AFTER_S`
  - `GLASSHIVE_IDLE_REAPER_INTERVAL_S`
  - `GLASSHIVE_MAX_ACTIVE_WORKERS_PER_USER`
  - `GLASSHIVE_MAX_ACTIVE_WORKERS_PER_TENANT`
  - `GLASSHIVE_MAX_WORKSPACES_PER_USER`
  - `GLASSHIVE_MAX_WORKSPACES_PER_TENANT`
  - `GLASSHIVE_ARTIFACT_DOWNLOAD_MAX_BYTES`
  - `GLASSHIVE_WORKER_ENV_ALLOWLIST`
  - do not rely on manual App Support edits or one laptop's shell exports to make GlassHive launch/watch UX correct
- Stable developer runtimes are part of the compiler boundary:
  - `runtime.dev_env.enabled` marks a side-by-side developer runtime config
  - `runtime.dev_env.shared_singleton_services` declares heavy services that should be referenced
    rather than duplicated in that dev env
  - default shared singleton services are recall/RAG, SearXNG, Firecrawl, Google Workspace MCP, and
    Microsoft 365 MCP
  - Scheduling Cortex is not a shared singleton; dev-env config/compile must give it an offset
    `scheduling_mcp_port`/`VIVENTIUM_SCHEDULING_MCP_PORT` and per-env scheduler DB so a dev env
    cannot satisfy local-prod scheduler health
  - dev envs may offset app-facing ports, but shared singleton service ports must stay aligned with
    the installed runtime unless the operator explicitly chooses full isolation
  - generated env must expose the dev-env and shared-singleton state so launcher/helper surfaces can
    explain what is shared instead of guessing
- Local work workflows are also compiler/runtime-bound:
  - `bin/viventium workflows`, `bin/viventium heal`, and `bin/viventium feature-request` must run
    from the active runtime checkout just like helper/manual operator commands
  - GlassHive host-worker availability is read from compiled runtime env; workflow commands must not
    invent a second GlassHive enablement source
  - compiled runtime env must expose the host worker's executable and persistence inputs as the
    launched service sees them, including supported Codex app-bundled CLI paths and the active local
    GlassHive DB path; shell-only availability or repo-local fallback state is not a product
    readiness signal
  - when GlassHive host workers are unavailable, workflow commands fail loud unless the operator
    explicitly chooses documented degraded mode
- Web search ownership is part of that same compiler contract:
  - the live switch is `integrations.web_search` in canonical App Support config
  - if that input is off or absent, generated runtime must disable `interface.webSearch`, omit the
    top-level `webSearch` block, and launcher env must keep `START_SEARXNG` / `START_FIRECRAWL`
    false
  - do not treat the tracked `viventium/source_of_truth/local.librechat.yaml` snapshot as the
    machine's live enablement state
- The config compiler also owns the retrieval embeddings contract compiled from
  `runtime.retrieval.embeddings`:
  - `EMBEDDINGS_PROVIDER`
  - `EMBEDDINGS_MODEL`
  - `OLLAMA_BASE_URL` when the configured provider uses Ollama
  - `VIVENTIUM_RAG_EMBEDDINGS_PROVIDER`
  - `VIVENTIUM_RAG_EMBEDDINGS_MODEL`
  - `VIVENTIUM_RAG_EMBEDDINGS_PROFILE`
- Human-facing browser auth posture must compile from canonical config too:
  - `runtime.auth.allow_registration` -> `ALLOW_REGISTRATION`
  - `runtime.auth.allow_password_reset` -> `ALLOW_PASSWORD_RESET`
  - `runtime.auth.connected_accounts_return_origin` ->
    `VIVENTIUM_CONNECTED_ACCOUNTS_RETURN_ORIGIN`; leave blank for the normal configured
    `DOMAIN_SERVER`/public API return path, and set it only for local/off-network connected-account
    OAuth QA when the completion page must return to a localhost browser
  - `llm.primary.auth_mode: user_provided` -> the vendor endpoint's `user_provided` sentinel so the
    encrypted browser API-key dialog owns the secret instead of terminal config
  - an explicit legacy `auth_mode: connected_account` ->
    `VIVENTIUM_EXPERIMENTAL_DIRECT_SUBSCRIPTION_AUTH=true`; absence of that explicit config compiles
    the flag to `false`, while the Connected Accounts setup page and stable API-key path remain
    available
- Scheduled agent automation is a separate compiler-owned policy under
  `runtime.scheduled_agent`; supported installs currently emit the atomic
  `openai` / `gpt-5.6-sol` / `xhigh` tuple as:
  - `VIVENTIUM_SCHEDULED_AGENT_PROVIDER`
  - `VIVENTIUM_SCHEDULED_AGENT_MODEL`
  - `VIVENTIUM_SCHEDULED_AGENT_REASONING_EFFORT`
  This override is scoped to the scheduler-secret-authenticated generation route. It must not alter
  the conscious agent's ordinary interactive model/effort settings or be inferred from prompt text,
  schedule names, agent names, or user identity.
- Generated runtime config must not silently preserve hidden provider defaults from the source
  template when the installer/compiler already knows the machine's real auth surface.
- The local launcher owns the fallback OpenAI picker inventory written to LibreChat runtime env:
  - direct API-key inventories include `gpt-5.6`, `gpt-5.6-sol`, `gpt-5.6-terra`, and
    `gpt-5.6-luna`
  - the ChatGPT connected-account inventory includes only the provider-verified
    `gpt-5.6-sol` and `gpt-5.6-terra` slugs, with Sol first; do not silently remap unsupported IDs
  - `OPENAI_MODELS` and `ASSISTANTS_MODELS` remain the runtime delivery fields; explicit
    `VIVENTIUM_OPENAI_MODELS` / `VIVENTIUM_ASSISTANTS_MODELS` or canonical env overrides remain
    authoritative
  - supported restart/upgrade must refresh the generated LibreChat env before model-picker QA;
    editing that generated file by hand is not a product fix
- `librechat.yaml` memory-writer provider/model must be compiled from the actually available
  foundation providers (`openai` / `anthropic`), including connected-account auth:
  - do not leave memory on a hardcoded xAI default when xAI was never configured
  - current product policy prefers Anthropic for memory when Anthropic is available and otherwise
    falls back to OpenAI
  - docs, tests, and generated runtime outputs must all reflect that exact compiler rule
  - the generated provider token is part of the public product contract; downstream runtime
    initialization must accept the compiler-emitted canonical value instead of requiring a
    different alias such as `openAI`
- The supported local nightly-routines policy is installed from canonical config, not from owner
  machine leftovers:
  - the immutable Easy Install payload does not package Scheduler, GlassHive, Prompt Workbench,
    nightly reflection, or scheduled memory hardening today; it must describe them as Custom
    Settings Install features rather than installed or ready capabilities
  - Custom Settings Install may activate the workflow during setup; upgrades of that runtime preserve an existing
    explicit active or disabled posture instead of forcing the new-user default over it
  - the canonical `install.experience` plus declared feature enablement owns this distinction;
    missing `install.experience` is legacy existing-user state and must not be silently reclassified
  - `bin/viventium install`, `upgrade`, `configure`, `compile-config`, and `start` all run the same
    default-nightly reconciler before compiling runtime artifacts, so later CLI auth can be picked up
    without hand-editing App Support files
  - the reconciler must never write a real account email, local absolute user path, raw prompt,
    transcript, token, or owner-specific value into canonical config
  - the default GlassHive worker profile is filled from the currently signed-in local worker CLI
    only when no explicit profile is already configured: Codex when `codex login status` succeeds,
    otherwise Claude when `claude auth status` succeeds
  - the reconciler must not overwrite an explicit configured worker profile on later `start`,
    `compile-config`, `configure`, or `upgrade`; user choice beats auto-detection
  - when GlassHive host-worker activation is explicitly enabled in Custom Settings Install, preflight requires at least one
    signed-in Codex or Claude CLI and gives one clear sign-in action if neither is usable; a disabled
    or setup-pending worker must not block Easy Install Native core readiness
  - OpenClaw may be reported as optional, but missing OpenClaw must not block the default nightly
    workflow when Codex or Claude is ready
  - worker CLI auth is not the same as model-provider API or connected-account auth for memory
    hardening. The worker gate proves GlassHive can run a host-native worker; `runtime.memory_hardening.provider`
    remains an explicit operator choice or is selected by the config compiler from the configured
    LLM auth surfaces.
  - the default built-in reflection schedule must target the first resolved local admin user after
    account creation and remain idempotent; it must not hardcode a public QA account, developer
    account, or private operator identity
  - if the user later signs into Codex or Claude and reruns a supported entrypoint, the generated
    runtime must fill a previously empty worker profile from the newly available CLI
  - if multiple local admins exist before any schedule owner can be resolved, the installer/runtime
    must not guess a personal account. The supported automatic path is the normal first-admin local
    install; multi-admin ambiguity is an operator-visible setup limitation until a deterministic
    owner is available.
- Easy Install Brain Readiness is a first-class installer contract, owned by the shared
  `scripts/viventium/brain_readiness.py` registry and reflected in wizard prompts, preflight,
  generated config, install/status output, doctor-style health, and QA rows:
  - Easy Install Native installs the useful first-answer spine automatically: core app/helper, local
    account, OpenAI provider connection, text chat/persistence, built-in agents, Prompt
    Templates, Agent Builder, Feelings, and the setup/status shell
  - Scheduler, GlassHive, Prompt Workbench, nightly reflection, scheduled memory hardening, local
    voice, Telegram, transcript ingest, Recall/RAG, web search, and productivity MCP services remain
    supported through Custom Settings Install, but are not packaged in immutable Easy Install today
  - the built-in nightly flow is documented and tested as: scheduled prompt -> filled placeholders
    -> GlassHive run -> callback -> scheduler ledger -> Workbench shows completed
  - in Custom Settings installs that enable the nightly workflow, the built-in schedule must be
    active for the resolved first local admin and carry a bounded catch-up policy so a late local
    scheduler tick does not permanently drop the reflection
  - memory hardening and nightly reflection must resolve the installing user's first local admin
    path without asking for a developer email, hardcoding an owner account, or leaking private data
  - provider API-key entry and an optional fallback provider are the only guided Easy Install
    surfaces today; user-owned or resource-heavy services stay behind Custom Settings Install until
    a signed optional-component transaction exists
  - foundation fallback credential presence means `Configured`, not `Ready`; only a successful live
    provider request can prove credential validity, and status must not manufacture that proof
  - Conversation Recall/RAG remains Custom Settings-only because it requires
    Docker/Ollama/vector-resource consent; Docker presence alone must not turn it on
  - Transcript ingest is pending until `runtime.memory_hardening.transcripts.source_dir` is set by
    the wizard, helper, or `bin/viventium transcripts source set <folder>`; an empty source is a
    setup-pending state, not a failure
  - Web Search is Custom Settings-only today. Its setup may use local Docker-backed
    SearXNG/Firecrawl or hosted Serper/Firecrawl keys, and status
    must identify the exact degraded local service when enabled health is incomplete
  - Code Interpreter, Skyvern, OpenClaw, and Remote Access remain off by default. They are
    Custom Settings Install or later guided opt-in surfaces and must not appear enabled in public examples
    unless that example is clearly lab-scoped
  - OpenClaw remains internal lab-only and absent from both public installer choices until
    authenticated client wiring and lifecycle QA ship. If it is later enabled, its bridge defaults
    to the reviewed E2B sandbox and requires
    bridge authentication even on loopback. Direct host execution is never an implicit fallback:
    it requires both `OPENCLAW_RUNTIME=direct` and the explicit
    `OPENCLAW_ALLOW_DIRECT_HOST_EXEC=true` risk acknowledgement
  - WhatsApp must not be advertised as installed or configured until an owning runtime integration,
    requirement doc, and QA surface exist
  - upgrades preserve explicit disables and never invent secrets, OAuth grants, transcript paths,
    user emails, local absolute paths, or private account state. They may add readiness/status cards
    and reconcile missing core-spine defaults idempotently.
- `runtime.memory_hardening` is the canonical source for the local saved-memory hardening operator
  job:
  - default local installs set `enabled: true`; explicit user disablement remains respected after
    the defaults marker has been applied
  - default schedule is `0 3 * * *`
  - schedules are local macOS wall-clock time; portable `timezone: local` resolves to the current
    system IANA timezone during compilation, and the exported effective timezone is operator/status
    evidence rather than a hardcoded owner-machine city
  - `operator_user_email` optionally scopes scheduled/helper hardening to one local account; empty
    means all local users are eligible
  - a successful scheduled run with `user_count=0` is healthy empty/skip evidence when user memory
    is intentionally disabled or no local users are eligible. Installer/runtime QA must not mark
    that as degraded merely because no memory writes occurred; it must mark it degraded only when
    eligibility is unknown, unexpectedly empty, or accompanied by provider/runtime/transcript/vector
    errors.
  - default lookback is 7 days
  - default idle gate is 60 minutes
  - default max semantic edits is 3 keys per user per run
  - default maximum prompt input is 500,000 estimated characters
  - full-lookback enforcement is on by default; runs fail closed instead of silently clipping the
    7-day corpus unless an operator explicitly allows partial lookback
  - install, configure, upgrade, compile-config, and start reconcile the macOS LaunchAgent from
    generated env. Enabled configs install one 03:00 calendar trigger; only explicit `false`
    removes it. Missing/invalid enablement preserves the existing agent and reports the ambiguity.
  - schedule reconciliation is idempotent and loader-only: identical loaded state is a no-op,
    matching-but-unloaded state is bootstrapped without bootout, and actual plist drift is replaced
    once with post-bootstrap verification. Lifecycle receipts contain only public-safe schedule,
    outcome, and generation-hash evidence. Install and uninstall also share a process lock so
    overlapping supported entrypoints cannot interleave loader state.
  - the installed macOS LaunchAgent command must invoke `scripts/viventium/memory_harden.py`
    directly with the generated runtime dir instead of routing scheduled hardening through
    `bin/viventium`; the user-facing launcher may be running when the 3am job fires
  - the installed macOS LaunchAgent command passes an explicit scheduled trigger marker to the
    wrapper. The wrapper writes a redacted trigger receipt before model work starts and finalizes it
    with exit status after the run. Runtime QA should use that receipt plus the hardener summary to
    prove scheduled delivery; it must not convert observed UTC differences from travel, DST,
    wake-coalesced launchd fires, or audit-time timezone context into a false `PARTIAL`.
  - the LaunchAgent working directory must be App Support, not the repo checkout, so unattended
    jobs do not inherit macOS protected-folder working-directory failures when a developer checkout
    is under Documents/Desktop/Downloads
  - the LaunchAgent command must start the wrapper with a minimal `env -i` environment; provider
    keys and runtime settings are loaded inside the wrapper from generated Viventium runtime files,
    not inherited from unrelated user-session launchd variables
  - the wrapper's generated env load order must match the public CLI: legacy repo/local env files
    are compatibility fallbacks, then `runtime.env`, `runtime.local.env`, and
    `service-env/librechat.env` load in that order so canonical generated runtime state wins
  - `bin/viventium memory-harden` participates in active-runtime-checkout re-exec, so helper/manual
    hardening and schedule installation use the same protected-folder-safe runtime checkout resolver
    as start/stop/helper commands
  - disabling the schedule clears the dry-run-first marker so a later re-enable gets the same
    first-run guard
  - when `dry_run_first` is enabled, the first scheduled apply with no marker performs a dry-run
    and writes the marker before future scheduled applies can mutate memory
  - model-backed memory hardening and transcript ingest are power-gated by the wrapper on macOS:
    they skip while the machine is on battery power or has recorded thermal/performance warnings
    unless an operator explicitly passes `--ignore-power-gate` with
    `VIVENTIUM_MEMORY_HARDENING_ALLOW_POWER_OVERRIDE=1`. `--ignore-idle-gate` only bypasses user-idle
    checks and must not bypass this power/thermal gate.
  - the power/thermal check is a shared local maintenance contract in
    `scripts/viventium/power_budget.py`; audit automations must report power-budget skips instead
    of forcing model-backed work with `--ignore-power-gate`.
  - when hardening is allowed to run, the wrapper starts the Node/model child at lower OS priority
    so scheduled work does not compete with foreground local-prod/dev work.
  - model-backed dry-run/apply hardening has a Node-owned efficiency gate in addition to the wrapper
    power gate: default `min_apply_interval_seconds` is 300, the public marker is stored in
    memory-hardening state without raw paths or content, and the only non-interactive bypass is
    `--ignore-efficiency-gate` paired with
    `VIVENTIUM_MEMORY_HARDENING_ALLOW_EFFICIENCY_OVERRIDE=1`. Power overrides are intentionally
    separate and must not bypass this cooldown.
  - `apply --run-id <run-id>` applies an already generated proposal and does not invoke model-backed
    proposal generation; it is intentionally outside the model-work cooldown.
  - `bin/viventium memory-harden status` is read-only operational inspection and must not wait on
    the global user-facing CLI lock or recompile config; it reports existing generated/runtime
    state while a hardening run may be in progress.
  - non-macOS operators must wire an equivalent cron/systemd timer; the public CLI currently
    auto-installs schedules only through macOS LaunchAgents
  - `provider_profile` must stay `launch_ready_only`
  - default Anthropic hardening tuple is `anthropic / claude-opus-4-8 / xhigh`; the root wrapper
    passes it to the Claude Code CLI path as the explicit provider/model plus
    `VIVENTIUM_MEMORY_HARDENING_ANTHROPIC_EFFORT=xhigh`
  - default OpenAI hardening tuple is `openai / gpt-5.6-sol / xhigh`; the compiler emits
    `VIVENTIUM_MEMORY_HARDENING_OPENAI_REASONING_EFFORT=xhigh` alongside the explicit
    provider/model tuple for the Codex CLI path
  - optional meeting transcript ingestion is configured under
    `runtime.memory_hardening.transcripts`
  - `transcripts.source_dir` compiles to `VIVENTIUM_MEMORY_TRANSCRIPTS_DIR`; empty disables the
    transcript lane
  - `transcripts.ignore_globs` compiles to `VIVENTIUM_MEMORY_TRANSCRIPTS_IGNORE_GLOBS`; this is the
    canonical way to exclude downloader manifests, temp files, and other source-folder sidecars
    without adding semantic transcript parsing
  - ignore globs are serialized into env as a comma-separated list; glob literals should not contain
    commas
  - transcript caps are deterministic cost controls, not content judgment:
    `max_files_per_run` default 20, `min_files_per_run` default 5 for apply-mode Node batches,
    `max_batches_per_invocation` default 1 in the wrapper, `max_chars_per_file` default 500,000,
    `summary_max_chars` default 32,000, reference saved-memory context default 24,000 chars,
    reference recent-conversation context default 36,000 chars, and stable-evidence decay default
    90 days
  - transcript files deferred by a per-run cap are not terminal; the next scheduled/helper run must
    retry them even when mtime, size, and content hash are unchanged
  - transcript RAG mode defaults to `detailed_summary_only`, which means raw transcripts are first
    summarized as complete per-transcript units and detailed summary artifacts are stored/attached
    for normal file_search recall; `raw_and_summary` and `raw_only` are explicit operator/QA modes
  - a configured but unhealthy RAG/vector runtime must not block chat-only memory hardening:
    transcript vector lifecycle and transcript-derived memory writes are deferred, while chat-only
    accepted operations may still apply
  - when a transcript source directory is configured, generated runtime must start the RAG sidecar
    even if default conversation recall is off, because transcript summary artifacts are
    vector-backed file_search resources
  - the macOS helper's manual `Advanced > Ingest Meeting Transcripts` action uses the same wrapper
    path, shows the active operator scope before and after the run, bypasses the idle gate because
    it is user-triggered, marks the run as interactive maintenance so the cooldown can be bypassed
    for that click, keeps the power/thermal gate in force, runs one bounded batch of at least 5
    transcript files, defaults to zero durable saved-memory changes, and writes only
    status/scope/count helper logs. Durable memory reflection remains the normal scheduled hardener
    responsibility unless the operator explicitly overrides the change cap.
  - introducing a future newer model family requires updating model governance and release contract
    tests first
- Endpoint helper config must not hide unavailable provider dependencies:
  - Anthropic conversation-title generation must stay on Anthropic instead of routing through xAI
  - xAI custom endpoint inventory is an explicit compiler/source-template contract:
    `grok-4.3` is the default and title/summary model, current 4.20 stable IDs use the dated
    `0309` forms documented by xAI, and model IDs scheduled for xAI's May 15, 2026 retirement must
    not be used as generated defaults
  - Keep the compiler fallback and `local.librechat.yaml` source-template xAI endpoint aligned;
    the source template currently wins same-name custom endpoint merges in generated
    `librechat.yaml`
  - Direct LibreChat dev starts must refresh the ignored local `LibreChat/librechat.yaml` from the
    tracked `viventium/source_of_truth/local.librechat.yaml` before the API loads startup config;
    otherwise the browser model picker can serve stale model specs even when the source template and
    generated App Support runtime are correct
- Retrieval-runtime prerequisites must stay honest across install/start surfaces:
  - if conversation recall is configured to use Ollama embeddings, preflight, install summary,
    doctor, and launcher readiness must all surface the same local-runtime dependency
  - Docker being healthy is not enough when the selected embeddings runtime is down
  - Ollama binary presence is not enough when the selected embeddings model artifact is still
    missing on the configured Ollama host
  - the launcher must ensure the configured embeddings model exists before starting the RAG sidecar
  - doctor should report whether the configured model is already ready or will be pulled on first
    start
- Easy Install must keep Docker-backed features on a minimal first-run contract:
  - a stray `docker` CLI on `PATH` is not enough to treat Docker Desktop as available
  - shared Docker availability checks in wizard and preflight must require the real Docker Desktop
    app/cask install
  - Web Search is deferred until after Easy Install reaches a working first answer. The user may
    then rerun `bin/viventium configure` and choose Custom Settings Install to add local Web Search.
    When Docker
    Desktop is absent, the prompt must say that local SearXNG/Firecrawl requires automatic Docker
    Desktop installation, while hosted Serper/Firecrawl requires user-owned keys
  - Easy Install keeps local Conversation Recall deferred by default instead of auto-enabling it
    from ambient Docker detection
- Homebrew-installed CLI prerequisites must be validated as runnable tools, not just files on
  `PATH`:
  - preflight and post-install formula validation must share the same bounded runtime probe
  - broken dynamic-link state after a Homebrew dependency upgrade must surface as a missing
    prerequisite so `bin/viventium install` and `bin/viventium upgrade` can repair or fail clearly
  - domain-specific tools may need stronger probes than `--version`; for example Telegram media
    support validates `ffmpeg` with a tiny decode/filter run
  - daemon, account, model, router, and service readiness remain separate feature checks; a binary
    probe only proves the local CLI can execute
- Built-in agent runtime truth must remain compatible with the selected install/runtime surface:
  - fresh installs and restarts rely on the seeded source-of-truth agent bundle
  - the authoritative background-agent provider/model matrix is documented in
    `docs/requirements_and_learnings/02_Background_Agents.md`; compiler assignments, source-of-truth
    bundle defaults, and runtime normalization must all agree with that matrix
  - for nested managed components, fresh installs follow the pinned component ref in
    `components.lock.json`; a newer local nested checkout does not change what end users receive
  - component selection defaults to the modern LiveKit playground (`agent-starter-react`) for
    voice-capable installs and must not include the old `agents-playground` unless
    `runtime.playground_variant: classic` is explicitly selected with voice enabled
  - running component bootstrap without `--config` uses the same public modern-playground default;
    an existing classic checkout may remain on disk, but it is not refreshed or selected unless the
    install explicitly opts into the classic playground
  - do not rely on Mongo hand-edits or App Support leftovers to make built-ins behave correctly
  - browser connected-account OAuth unlocks auth for the configured foundation-provider mix; it
    does not currently recompute the built-in background-agent roster by itself
  - when the compiler policy changes a model family, the source-of-truth bundle and live built-in
    agent sync must be updated together; otherwise existing installs can keep failing on stale
    model config even though generated runtime config is healthy
  - shipped Anthropic agents that intentionally use `temperature` must set `thinking: false`
    explicitly when Anthropic runtime defaults would otherwise enable thinking
  - install summary, browser reminders, and setup docs must distinguish foundation-model auth
    from per-user workspace OAuth; a healthy activation path does not mean Gmail/Drive or
    Outlook/MS365 execution is ready for that user yet
  - local duplicate QA accounts do not automatically inherit another user's Google Workspace,
    Microsoft 365, or connected-model OAuth state; realistic live QA must reconnect or reseed those
    user-scoped credentials explicitly
  - optional MCP/runtime surfaces such as GlassHive must compile out cleanly when they are not
    enabled for the install or not actually present in the checked-out component set
  - GlassHive host-native workers compile from `integrations.glasshive.host_worker`; when GlassHive
    is enabled, host workers default on, the default execution mode is `host`, the default workspace
    root is user-scoped (`~/viventium`), and `/viventium` is valid only when doctor proves it is
    writable by the current user
  - the default host Codex automation tuple is `gpt-5.6-sol / xhigh`. The compiler emits the same
    tuple for host and general Codex worker env so Prompt Workbench, Scheduling Cortex, GlassHive
    bootstrap, and model-route evidence cannot silently diverge. The Viventium compiler also emits
    the now-proven xHigh route flag by default; otherwise GlassHive's standalone safety clamp could
    turn a requested xHigh run into medium on a clean install
  - that host-worker setting is shared by unattended Workbench automation and direct host Codex
    delegation. This is the intentional current quality-first baseline, not a change to the main
    conscious agent, voice, activation classifiers, or `viventium_agent` reminder delivery
  - `integrations.glasshive.host_worker` also owns first-class optional native-capability controls
    for host worker runtime requirements, Codex native MCP allowlist/plugin cache, Codex lockdown
    flags, and Claude Chrome/effort launch flags. These compile into canonical runtime env so
    operators do not need undocumented `runtime.extra_env` escape hatches for the capability
    contract.
  - when `integrations.glasshive.host_worker.enabled=false`, the compiler must emit
    `GLASSHIVE_HOST_WORKERS_ENABLED=false`, force the generated default execution mode to `docker`,
    and generate MCP instructions that do not tell agents to create host-native workers
  - when `integrations.glasshive.deployment_mode=azure_enterprise_vm_docker`, the compiler must:
    - reject localhost GlassHive MCP/operator URLs
    - force `GLASSHIVE_HOST_WORKERS_ENABLED=false` and `WPR_DEFAULT_EXECUTION_MODE=docker`
    - emit `GLASSHIVE_ENTERPRISE_MODE=true`, the configured auth mode, tenant id, idle reaper
      policy, quota caps, artifact cap, upload root, bootstrap source roots, and provider env
      allowlist
    - emit optional `GLASSHIVE_OWNER_IDENTITY_CLAIMS`,
      `GLASSHIVE_OWNER_IDENTITY_ALIASES_JSON`, or `GLASSHIVE_OWNER_IDENTITY_ALIASES_FILE` only from
      `integrations.glasshive.enterprise.owner_identity`; defaults stay strict `user_id` matching
      with no aliases so SSO deployments do not silently widen owner scope
    - emit `GLASSHIVE_SIGNED_LINK_SECRET` for enterprise mode. If no dedicated
      `integrations.glasshive.enterprise.signed_link_secret` is configured, compile a tenant-scoped
      derivative from the call-session secret; explicitly reject values that equal the service token
    - when local enterprise simulation URLs include explicit ports, emit matching
      `GLASSHIVE_MCP_PORT` and `GLASSHIVE_UI_PORT` so the launcher binds the same ports that
      LibreChat is configured to call
    - default service-token delivery to a trusted reverse proxy and therefore omit `X-WPR-Token`
      from LibreChat YAML unless `service_token_delivery=client_header` is explicitly configured
    - add `X-Viventium-Tenant-Id` and LibreChat user/request/upload headers to the generated
      GlassHive MCP server
    - support server-side `api_key` provider auth for enterprise mode, including explicit
      `OPENAI_BASE_URL`, `ANTHROPIC_BASE_URL`, and `PORTKEY_*` env projection through
      `runtime.extra_env` or the canonical env import list; connected-account auth remains
      supported for local/personal modes but is not the default enterprise path
    - compile optional MCP OAuth only when explicitly enabled; OAuth is a separate MCP consent path
      and must not be documented as silent reuse of LibreChat's login token. The runtime remains
      `first_party_assertion` unless a real external token validator is installed; OAuth/OIDC auth
      modes fail closed by default.
    - keep enterprise worker bootstrap clean-room with respect to the VM account's local Codex,
      Claude, and git auth/identity files; provider access must come from explicit allowlisted env
      vars or a broker
    - emit the env needed for short-lived opaque artifact/watch links, and keep local/personal
      callback URLs compatible when no enterprise signing secret is configured
  - host worker doctor/preflight must report local `codex`, `claude`, and `openclaw` CLI
    availability separately; missing OpenClaw degrades only the `@openclaw` host worker, not Codex
    or Claude workers
  - host worker CLI availability must match the launched service environment, not only the
    interactive shell. On macOS, a valid app-bundled Codex CLI path is a supported Codex host-worker
    runtime and the compiler must emit it as `WPR_CODEX_BIN` when `codex` is not on the service
    `PATH`; discovery checks `/Applications`, `~/Applications`, and `VIVENTIUM_CODEX_APP_DIRS`.
  - generated GlassHive MCP headers must include user, agent, conversation, parent message, and
    current message context so `worker_find_or_resume` can seed same-chat callback metadata without
    a controller-level mention parser
  - those generated GlassHive MCP headers also carry request-scoped upload metadata (`files`,
    `attachments`, `tool_resources`, `file_ids`) as encoded JSON so GlassHive workers reuse the
    current upload path rather than adding a duplicate one
  - generated GlassHive env must expose the existing LibreChat uploads root to GlassHive through
    `WPR_LIBRECHAT_UPLOADS_ROOT` and allow bootstrap file materialization from that same root
    through `WPR_BOOTSTRAP_SOURCE_ROOTS`; this is how browser/API/voice uploads become workspace
    files without adding a second upload service
  - GlassHive callbacks must be validated with per-worker/run HMAC binding, fresh callback
    timestamps, replay detection, and same-user conversation ownership before the callback receiver
    writes status or completion messages back into chat; the compiled GlassHive callback secret is a
    scoped derivative, not the raw call-session or scheduler secret
  - seeded built-in agents must not keep dead GlassHive tool IDs on installs where
    `START_GLASSHIVE=false`, or fresh-user chat can fail before any real task begins
  - startup reseed for existing installs must preserve live user-managed tool choices except for
    runtime-disabled tool gates:
    - if the compiler/runtime disabled Web Search, Code Interpreter, or an optional MCP surface,
      persisted built-in agents must prune only those dead tool IDs from live Mongo state
    - that repair path must not use the scaffold bundle to silently restore other live tool choices
  - public checkout bootstrap must accept vendored component source trees that were shipped inside
    the reviewed repo export; installer correctness must not depend on nested `.git` metadata being
    present on end-user machines
- Installer UX affordances, including wait copy and inline animations, must not mutate or depend on
  generated App Support outputs to appear correct.
- Telegram launcher parity follows the same rule: compiled Telegram service env must be the default
  startup source ahead of legacy repo-local or private overlay files.
- Telegram voice-note STT is a bridge reliability boundary:
  - canonical `integrations.telegram.stt_provider` may override transcription just for Telegram
  - when omitted, Telegram inherits the configured global voice STT provider, including local
    Whisper/whisper.cpp
  - the compiler must not silently remap inherited local Whisper to OpenAI, AssemblyAI, or any
    hosted provider; hosted Telegram STT must be an explicit operator choice
  - local Telegram STT must use the serialized local-STT path and media-decoder preflight instead
    of avoiding local STT by changing providers behind the user's back
  - release tests must assert the inherited local-Whisper default so future "reliability" changes
    cannot drift Telegram onto hosted STT without an explicit config field
- Managed Telegram large-media mode follows the same rule:
  - canonical `integrations.telegram.local_bot_api` config compiles to generated Telegram service env
  - the launcher reads that generated env to decide whether it owns a local `telegram-bot-api` process
  - Telegram max media size comes from canonical config (`integrations.telegram.max_file_size_bytes`),
    not a shell-only or repo-local default
  - preflight must surface missing `telegram-bot-api` / `api_id` / `api_hash` before runtime start
- Voice turn-taking follows the same compiler/runtime ownership rule:
  - canonical runtime config owns the shared background follow-up window:
    - `runtime.background_followup_window_s`
    - compiles to:
      - `VIVENTIUM_CORTEX_FOLLOWUP_GRACE_S`
      - `VIVENTIUM_VOICE_FOLLOWUP_GRACE_S`
      - `VIVENTIUM_TELEGRAM_FOLLOWUP_GRACE_S`
    - note:
      - the umbrella product phrase is now `background follow-up window`
      - the env var names intentionally keep the older `FOLLOWUP_GRACE` suffix for backward compatibility
  - canonical runtime config separately owns the GlassHive worker callback wait window:
    - `runtime.glasshive_followup_timeout_s`
    - compiles to:
      - `VIVENTIUM_WEB_GLASSHIVE_TIMEOUT_S`
      - `VIVENTIUM_VOICE_GLASSHIVE_TIMEOUT_S`
      - `VIVENTIUM_TELEGRAM_GLASSHIVE_TIMEOUT_S`
    - default:
      - 600 seconds, because host-native browser/desktop work can legitimately take several minutes
  - GlassHive callback delivery health is runtime state, not generated config. Generated config owns
    callback URL/secret/wait-window inputs, but runtime health and nightly QA must prove callback
    outbox delivery, active backlog, active retry attempts, stale delivering reclaim, and dead-letter
    delta from the live store.
      - this timeout must not inherit the shorter background follow-up grace window
    - valid range:
      - 30-86400 seconds; compiler and preflight should reject values outside that range
  - canonical voice config owns `VIVENTIUM_TURN_DETECTION`
  - canonical voice turn-handling config owns:
    - `VIVENTIUM_VOICE_MIN_INTERRUPTION_DURATION_S`
    - `VIVENTIUM_VOICE_MIN_INTERRUPTION_WORDS`
    - `VIVENTIUM_VOICE_MIN_ENDPOINTING_DELAY_S`
    - `VIVENTIUM_VOICE_MAX_ENDPOINTING_DELAY_S`
    - `VIVENTIUM_VOICE_FALSE_INTERRUPTION_TIMEOUT_S`
    - `VIVENTIUM_VOICE_RESUME_FALSE_INTERRUPTION`
    - `VIVENTIUM_VOICE_MIN_CONSECUTIVE_SPEECH_DELAY_S`
  - canonical voice STT config owns the surfaced AssemblyAI endpointing knobs:
    - `VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD`
    - `VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS`
    - `VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS`
    - `VIVENTIUM_ASSEMBLYAI_FORMAT_TURNS`
  - canonical Cartesia TTS config owns the Sonic-3 request knobs:
    - `VIVENTIUM_CARTESIA_API_VERSION`
    - `VIVENTIUM_CARTESIA_MODEL_ID`
    - `VIVENTIUM_CARTESIA_VOICE_ID`
    - `VIVENTIUM_CARTESIA_SAMPLE_RATE`
    - `VIVENTIUM_CARTESIA_SPEED`
    - `VIVENTIUM_CARTESIA_VOLUME`
    - `VIVENTIUM_CARTESIA_EMOTION`
    - `VIVENTIUM_CARTESIA_LANGUAGE`
    - `VIVENTIUM_CARTESIA_MAX_BUFFER_DELAY_MS`
    - `VIVENTIUM_CARTESIA_SEGMENT_SILENCE_MS`
  - canonical `voice.worker` config owns the worker/runtime controls:
    - `VIVENTIUM_VOICE_INITIALIZE_PROCESS_TIMEOUT_S`
    - `VIVENTIUM_VOICE_IDLE_PROCESSES`
    - `VIVENTIUM_VOICE_WORKER_LOAD_THRESHOLD`
    - `VIVENTIUM_VOICE_JOB_MEMORY_WARN_MB`
    - `VIVENTIUM_VOICE_JOB_MEMORY_LIMIT_MB`
    - `VIVENTIUM_VOICE_PREWARM_LOCAL_TTS`
  - the compiler owns the default Phase A background notice mode:
    - `VIVENTIUM_CORTEX_PHASE_A_NOTICE_MODE=any_activated_on_voice`
    - this value, plus the voice Phase A knobs below, must be emitted into both `runtime.env` and
      `service-env/librechat.env` so the installed LibreChat service uses the same default as source
    - background detection budgets/flags are owner-canonical in
      `docs/requirements_and_learnings/02_Background_Agents.md` ("2026-05-30 … Two Independent Modes").
      The compiler emits, for the two independent modes (neither flag affects the other mode):
    - `VIVENTIUM_VOICE_BACKGROUND_AGENT_DETECTION_ASYNC=true` (voice async "nevermind+redo" default
      ON)
    - `VIVENTIUM_TEXT_BACKGROUND_AGENT_DETECTION_ASYNC=false` (text async opt-in; default OFF)
    - `VIVENTIUM_VOICE_PHASE_A_AWAIT_MS=690` (voice detection budget)
    - `VIVENTIUM_TEXT_PHASE_A_AWAIT_MS=1300` (text detection budget)
    - `VIVENTIUM_CORTEX_DETECT_TIMEOUT_MS=2000` (shared fallback budget)
    - `VIVENTIUM_CORTEX_LATE_DETECT_TIMEOUT_MS=6000` (non-blocking recovery budget after a zero-activation fast-pass timeout; reuses canonical classifier/fallback/Phase B paths and does not delay the main answer)
    - `VIVENTIUM_ACTIVATION_PRIMARY_ATTEMPT_TIMEOUT_MS=1600`
    - `VIVENTIUM_ACTIVATION_FALLBACK_ATTEMPT_TIMEOUT_MS=2500`
    - `VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=true` (voice stays async even when a
      configured tool-hold cortex exists; Phase B/follow-up owns late or side-effecting evidence)
    - `VIVENTIUM_VOICE_LOG_LATENCY=1`
  - generated runtime must not rely on one machine's shell exports or App Support hand edits to
    change end-of-turn behavior
  - when the optional semantic turn-detector plugin is installed, launcher startup owns the model
    pre-download so a fresh boot does not die on a missing turn-detector ONNX cache

## Transactional Configuration Boundary

- Headless `install` and `configure` inputs are patches over the existing canonical config, not
  replacement documents. Unknown forward-compatible fields and explicit user choices must survive.
- The CLI prepares each headless change in a private, attempt-scoped candidate directory under App
  Support, runs the wizard normalizer and default reconciler against that candidate, then runs a
  compiler dry-run before canonical state changes.
- Applying a validated candidate first writes a mode-`0600` backup under a mode-`0700` App Support
  backup directory and then replaces canonical config atomically. A later compile or schedule-sync
  failure restores the prior canonical config.
- Failed input parsing or candidate validation leaves canonical config byte-for-byte unchanged and
  removes attempt-scoped candidate files.
- Interactive configure, helper-driven configure, redacted preview/diff, post-reload health proof,
  and crash/power-loss journaling still need to converge on this same transaction before the whole
  `INST-006` contract can be called complete.
- The current interactive wizard remains outside this boundary: it writes canonical YAML directly
  and can update Keychain items while prompts are still in progress. Completing the transaction
  requires staging secret references and values, validating first, then committing Keychain,
  canonical config, generated outputs, schedules, helper state, and process/reload effects with a
  local compensation journal. Canonical config rollback alone is not sufficient.

## Bootstrap Destination Identity Boundary

- Before `install.sh` fetches, checks out, or pulls an existing destination, it must read that
  checkout's `origin` and compare its canonical repository identity with the requested repository.
- The supported ProjectViventium HTTPS, GitHub SCP-style SSH, and `ssh://git@github.com/` spellings
  are equivalent identities. An explicit `VIVENTIUM_REPO_URL` remains the requested identity for
  controlled local/private bootstrap testing.
- A missing or unrelated origin fails closed with guidance to choose an empty install directory or
  explicitly repair the checkout. The bootstrap must not run a mutating Git command first.
- An existing checkout with tracked changes also fails before fetch/checkout/pull. After the
  fast-forward update, the tracked tree must still be clean and local `HEAD` must exactly equal the
  fetched `origin/<branch>` revision before its CLI can execute; a clean local-ahead commit is not a
  verified public artifact.
- Origin identity is the immediate destination-safety gate. Immutable release selection,
  signature/digest verification, interruption recovery, and exact installed-artifact proof remain
  required before the complete `INST-007` provenance contract passes.
- This immediate gate covers accidental wrong destinations only. Running `git -C` inside an
  existing repository can execute repository-controlled hooks or filesystem-monitor configuration;
  same-origin spoofing, the local-checkout fast path, and surviving untracked files also remain
  outside the protection. The secure public boundary requires hook-disabled clean staging and an
  immutable verified release before any destination-controlled Git operation is trusted.

## Continuity-Aware Snapshot / Restore / Upgrade Boundary

- `bin/viventium snapshot` is the supported manual snapshot entrypoint for local installs.
- The public snapshot wrapper must always write a metadata-only `continuity-manifest.json` under a
  newly allocated snapshot-attempt directory, even when no private companion helper exists.
- A metadata-only attempt is a continuity audit, not a recoverable backup. CLI/helper wording must
  say that no recoverable payload was created, and the attempt must carry an explicit machine-local
  metadata-only marker.
- The wrapper must never discover the latest prior snapshot and write into it as fallback. Repeated
  metadata-only attempts allocate distinct directories and leave every prior manifest/payload
  byte-for-byte unchanged.
- `LATEST_PATH` is a commit pointer: publish it atomically only after the new continuity manifest
  succeeds. Capture failure or interruption must preserve the prior last-good pointer; an
  incomplete attempt directory is not promoted.
- `LATEST_PATH` may therefore name the newest completed metadata audit. Restore must inspect the
  explicit metadata-only marker and refuse that directory before capturing live state or applying
  any restore-side mutation; a continuity audit is never a restore source merely because it is
  latest.
- That manifest is evidence, not authorship. It may include:
  - sanitized path labels
  - repo heads
  - runtime-profile and embeddings metadata
  - continuity-surface timestamps/counts
  - warnings/errors about what could not be inspected
- That manifest must not include:
  - secrets
  - raw message content
  - raw prompts
  - Mongo URIs
  - personal emails
  - absolute private home-directory paths
- App Support is the primary machine-local manifest destination. A private companion helper may add
  richer secret-bearing payload into the same machine-local snapshot flow or a private companion
  backup root. The helper must record a new snapshot path for the current attempt and that path must
  pass the public complete-bundle validator before publication; otherwise the public wrapper preserves
  all prior snapshots and creates a separate metadata-only audit.
- The product default is operator-triggered manual snapshots, not mandatory daily full backups.
  Bounded private automation may exist later, but the shipped public contract must stay explicit and
  storage-aware.
- Complete logical capture must reserve 10 GiB after a conservative estimate of the sanitized config,
  schedules, uploads archive, transaction overhead, and the larger of locally visible Mongo storage
  or allowlisted logical-collection statistics before it creates an attempt directory. It rechecks
  that reserve between capture phases; a capacity failure removes the incomplete attempt and never
  promotes it. Capture also refuses an archive source with more than 100,000 files, a relative path
  longer than 1,024 UTF-8 bytes, or a relative path deeper than 32 components.
- `bin/viventium restore` must first refuse any default or explicitly selected metadata-only
  attempt and any source/target overlap. Marker-less, partial, corrupt, or resource-abusive inputs
  fail before target creation. The validator must run from a stock standard-library Python without
  bootstrapping App Support, and must reject boolean schema versions, oversized artifacts, and
  excessive declared or observed archive expansion. Archive headers are streamed through validation
  before extraction: each archive is limited to 100,000 regular-file members, all bundle archives
  together are limited to 200,000 members, and the same 1,024-byte/32-component path bounds apply.
  The exact cap is valid; the next header fails closed. The declared upload-file count is bounded and
  must equal the observed archive count, and extraction independently rechecks these rules to close
  validation-to-use replacement.
- Transactional independent restore must group its manifest-declared compressed plus uncompressed
  working footprint plus 4 KiB of conservative filesystem metadata overhead per extracted archive
  member by destination filesystem, and retain a 10 GiB reserve on each affected volume. This check
  runs before target Mongo inspection, claim, journal, or target creation; filesystem and Mongo
  phases recheck the reserve and enter the existing transaction-owned rollback path on failure.
- A producer's positive marker, complete domain ledger, typed artifacts, size/hash checks, and
  format checks establish only a structurally valid candidate. A restore-ready public bundle also
  requires the versioned logical-Mongo collection ledger, per-collection document counts/hashes,
  bounded canonical Extended JSON validation, runtime/helper selection policy, and the exact
  secret-exclusion contract. Legacy complete candidates remain valid for inspection but return
  `recoverable: false`, `semanticValidation: not_performed`, and cannot enter apply.
- The public logical-Mongo adapter exports an allowlist containing chats, messages, saved memory,
  agents/assistants, projects, files metadata, feelings, prompts/presets, shares, authorization
  structure, and sanitized users. It excludes token/session/provider-key/action/MCP/plugin-auth
  credential collections, raw tool-call rows, and argument/result payloads embedded in message tool
  parts, and exports only an allowlist of non-secret user fields. Any nonempty password, credential,
  API-key, or auth-token field found in an otherwise allowed document fails the whole complete
  capture. No partial bundle is promoted. Source installs use LibreChat's pinned Node MongoDB/BSON
  packages, not separately installed host Mongo command-line tools.
- Canonical config is restored as the authoring source, but inline secret values are replaced with
  explicit null/reauth-required entries; safe `keychain://` references may remain. Generated env,
  helper binding, and runtime YAML are never copied as authority and must be regenerated for the
  target checkout/profile.
- The bundle is mode-`0700` with mode-`0600` payload files and is not self-encrypted. Its manifest
  states `not_self_encrypted_owner_only`; users must keep the machine-local bundle on an encrypted
  host volume or encrypted external destination. Provider/channel/browser credentials are excluded
  even on encrypted hosts and must be reauthenticated. Product wording must not imply portable
  cryptographic encryption when only owner permissions and host-volume protection exist.
- Uploaded files are a bounded, no-follow regular-file tar; schedules/background tasks use SQLite's
  online backup API plus integrity checking. Recall/RAG indexes remain derived and are not copied as
  canonical truth; restore writes the rebuild-required marker so vector-backed recall stays blocked
  until rebuilt and explicitly acknowledged.
- Apply accepts only an absent independent App Support target, a separate fresh checkout with no
  existing uploads target, and an empty credential-free loopback Mongo database with a different
  database name from the source. The selected bundle must still be current-user owner-only at apply
  time. Source/target/checkout overlap, symlinks, hardlinks, foreign-owned entries, existing/personal
  state, nonempty databases, and legacy bundles fail before mutation.
- The restore transaction stages config, schedules, files, Recall and reauthentication ledgers;
  acquires a transaction-ID claim in the proven-empty isolated database, imports logical Mongo, then
  activates target filesystem roots. Failure or `SIGINT`/`SIGTERM` removes transaction-owned
  filesystem state and drops only a database carrying that transaction's claim. Pending activation
  flags cover faults immediately after a directory rename. If rollback itself fails, the private
  local journal remains with `rollback_incomplete` and the command fails closed.
- Apply records the independent runtime selection in an owner-only, non-symlink ledger. The config
  compiler accepts only a matching schema/profile/canonical-config/generated-output binding. The
  restartable `v2` ledger additionally pins the credential-free loopback Mongo port and a distinct,
  owner-only Mongo data path, so a full stop/start cannot silently fall back to source persistence.
  Restore generates a fresh target-local internal call-session secret with mode `0600`; it does not
  migrate the source internal secret or any provider, channel, browser, session, or OAuth secret.
- `--allow-older-snapshot` and `--apply-telegram` remain refused compatibility flags. `--mark-recall-stale`
  is accepted only as redundant compatibility wording because every supported restore marks Recall
  stale. Restore success still means reconnect provider/channel accounts, reset browser-user
  passwords through the supported recovery path, regenerate runtime/helper binding, rebuild Recall,
  start, and prove the recovered visible user path; it never means credentials migrated.
- `bin/viventium continuity-audit` owns the operator review surface for current continuity metadata
  and the explicit `--clear-recall-marker` acknowledgement after rebuild.
- `bin/viventium upgrade` must capture pre/post continuity audits and treat their severity as part
  of the supported upgrade contract:
  - `error`: do not auto-restart
  - `unknown`, malformed, or capture failure: do not auto-restart
  - `warning`: finish upgrade but require operator review
  - `ok`: continue normally
- A mutating source-install upgrade is a machine-local transaction, distinct from the public
  snapshot/restore product:
  - register the transaction and arm interruption recovery before stopping a running stack
  - after stop, create and hash a private pre-mutation checkpoint of canonical config, generated
    runtime, runtime state, bootstrap Python state, legacy Mongo state, native data, and any
    App-Support-contained explicit Mongo path
  - inventory the active Mongo storage backend from the installed runtime; `compat` named-volume
    installs must checkpoint and content-verify the exact Docker volume before source mutation,
    while isolated/native App Support paths are covered by the stopped filesystem checkpoint
  - fetch may observe the target before shutdown, but parent/source activation, component refresh,
    candidate config compilation, and candidate doctor validation happen only after the checkpoint
  - copy and hash the pre-pull transaction runner into the private transaction; every later
    checkpoint/activate/rollback/commit command uses that immutable runner rather than candidate source
  - candidate config/runtime remain private and separate until validation succeeds; prerequisite
    discovery during upgrade is check-only because Homebrew/system installation is not a reversible
    transaction (the operator applies missing prerequisites separately and retries)
  - failure or interruption restores recognized parent/component revisions without discarding
    unknown local work, restores the exact stopped file and named-volume checkpoint, quarantines a
    component first cloned by the failed attempt, and returns the prior running/stopped state
  - rollback must fail closed before overwriting state if a checkout has moved to an unrecognized
    commit, gained tracked work, a state path crosses a symlink/ownership boundary, or a Docker
    checkpoint cannot be verified
  - exact stopped bytes are rollback evidence; they do not prove semantic reversal of an arbitrary
    forward-only data migration. The ledger must record semantic migration reversal as not proven.
- When `--restart` is used, stop must succeed before source pull. Helper refresh uses `--no-launch`;
  only an accepted post-audit followed by a successful runtime restart may relaunch the helper, so
  its login auto-start loop cannot race the continuity gate.
- The macOS helper may expose a manual `Create Backup Snapshot` action, but it must call the same
  supported snapshot path as the CLI rather than inventing a second backup implementation. It may
  show backup success only for positive marker+manifest proof and must show a warning for metadata-only
  or invalid/missing proof.

## Feelings compiler contract

`runtime.feelings` is the canonical operator surface for the Feelings feature. The compiler owns:

- operator availability and the per-user default-enabled seed;
- agent scope (`all_agents` by default or `conscious_agent`);
- all nine default Nature/half-life/enabled values, whose band semantics and product requirements
  are owned by `54_Emotional_Cortex_And_Feeling_State.md`;
- reaction activation mode (`always`, `classified`, or `disabled`);
- reaction provider, model, Responses API, reasoning effort, Fast/Priority tier, and timeout;
- classified-activation provider/model/confidence/timeout.

The compiler validates closed enums, supported provider names, finite band ranges, positive
half-lives/timeouts, known band IDs, and a bounded confidence threshold. It emits explicit
`VIVENTIUM_FEELINGS_*` values plus `VIVENTIUM_FEELINGS_BANDS_JSON`. Defaults and examples live in
`config.schema.yaml`, `config.full.example.yaml`, and `config.minimal.example.yaml`; the executable
contract is `tests/release/test_feelings_contract.py`.

The default reaction route is `openai / gpt-5.6-terra`, Responses API, reasoning `none`,
`fast: true`, and `service_tier: priority`. Generated env is runtime output. Operators edit canonical
config and recompile/restart; they do not patch generated App Support env files.

## Learnings

- First-run startup can honestly take minutes because local package builds and optional Docker sidecars
  are real work, especially on a clean machine.
- Playful wait copy is acceptable when the deterministic status path remains visible and reliable.
- Optional-sidecar readiness used by the launcher, install wait loop, and status must share the same
  contract. One path cannot hold the install open on a stricter probe than the runtime itself uses
  to declare the sidecar up.
- On April 16, 2026, GlassHive surfaced the same compiler/runtime ownership rule:
  - desktop-first watch, visible live terminal-in-desktop, and idle desktop priming must come from generated runtime env defaults
  - the GlassHive launch UI and workstation runtime may still carry sane in-code fallbacks, but the shipped product contract belongs in compiled `runtime.env`
  - silent launch failures after worker creation must become explicit runtime state and events instead of relying on operators to infer what happened from an empty project page
- Interactive bootstrap paths can arrive with stdin still attached to a consumed pipe:
  - example: `curl .../install.sh | bash`
  - the CLI must reattach stdin from `/dev/tty` before wizard or preflight prompts
  - otherwise the first prompt sees EOF even though the user launched the install from a real terminal
- Reattached stdin is still not enough on every macOS terminal shape:
  - `questionary` / `prompt_toolkit` can still raise raw-mode attachment errors after the CLI hands
    prompts a real TTY
  - the shared installer UI must catch those runtime prompt failures and fall back to plain prompts
    instead of crashing the install
  - that fallback belongs in the shared prompt wrapper, not as one-off handling in only one wizard
    question
- The right ownership layer for this feature is the public CLI wait loop in `bin/viventium`, not
  generated runtime files, LibreChat prompts, or machine-local App Support state.
- Remote access surfaced the same ownership rule again on April 7, 2026:
  - the wizard must own the human-facing remote-access choice in plain language
  - the config compiler must own the generated browser-auth/env posture
  - the runtime state file must own the exact live outside URL after startup
  - `bin/viventium status` / install summary must read that runtime state instead of making the
    operator reconstruct it manually
- Public remote access is optional and must never block local first run:
  - if router mappings or edge startup fail, local LibreChat/API/playground startup must continue
  - the remote access state file must persist the exact blocker so `bin/viventium status` can show
    an action-required message and the next `bin/viventium start` can retry cleanly
- Public LiveKit media keeps the same canonical-config ownership rule:
  - blank `runtime.network.livekit_node_ip` preserves the local-first LAN-address default
  - a deployed direct-public edge must set an explicit public node address until the compiler
    exposes dual internal/external candidate fields
  - the compiler must carry that value through generated runtime env and `livekit.yaml`; the active
    process and `public-network.json` must agree after restart
  - App Support generated files remain outputs and must never become the manual authoring surface
  - an external page or signaling check is not compiler/runtime acceptance; `REMOTE-004` and
    `MPV-023` require selected off-LAN media and a delivered synthetic turn
- Deferred Telegram startup must survive clean first-run build time:
  - LibreChat can spend several minutes rebuilding packages and the client bundle on a clean Mac
  - any Telegram startup path that waits inline against the API before those builds finish will
    produce a false skipped/stopped state for enabled installs
  - the launcher must retry Telegram in the background and expose that pending state through
    `bin/viventium status`
- Detached installer startup must track the detached launch ownership boundary, not only the
  short-lived wrapper pid:
  - `bin/viventium start` is allowed to hand control off to a detached process group and exit while
    background builds continue
  - install/start wait logic must therefore follow the recorded detached launch process group under
    `state/runtime/<profile>/detached-launch.pgid` before declaring early failure
  - otherwise clean first builds can be reported as `stopped during startup` during a valid warm-up
    handoff
- Re-entrant launch requests during detached startup must be treated as the same in-flight boot:
  - helper/login-item auto-start can legitimately invoke `bin/viventium launch` while the detached
    install-owned startup is still warming
  - if the recorded detached launch process group is still alive, `bin/viventium launch` must
    return `already starting` instead of tearing the stack down and restarting it mid-boot
- The CLI operation lock protects startup preparation, not the lifetime of the foreground stack:
  - `bin/viventium start` must release `state/cli-operation.lock` after config compilation,
    schedule sync, and runtime handoff setup, before entering the long-running stack supervisor
  - otherwise status-bar actions such as Stop/Quit, prompt workbench launch, manual memory
    hardening, and meeting-transcript ingest are blocked while the app is already healthy
  - long-running runtime ownership belongs in stack/process state, not in the short operator
    command lock
- Detached LibreChat API watchdog budgeting must match real clean-machine build time:
  - first-run API readiness on slower Intel Macs can take well beyond the short historical
    watchdog budget
  - the watchdog's initial health wait must therefore survive the same clean-build envelope as the
    installer instead of exiting before the API ever has a chance to come up
- The shipped macOS helper binary is the reliable clean-install path on April 7, 2026:
  - clean x86_64 CommandLineTools hosts can fail SwiftPM manifest linking before any app code builds
  - when `apps/macos/ViventiumHelper/prebuilt/source.sha256` matches current helper sources, the
    installer may use that shipped binary only when `prebuilt/binary.sha256` also matches the exact
    executable and the executable contains both supported macOS architectures; source hash alone is
    not binary integrity or publisher provenance
  - the binary sidecar detects accidental replacement/corruption but does not replace Developer ID
    signing, notarization, or an immutable signed release manifest
  - source-mode helper install and uninstall must validate `~/Applications` without following a
    symlink and must refuse any `Viventium.app` or legacy helper bundle that is not owned by the
    current user and identified by the exact Viventium bundle ID/executable shape
  - validation is not a lease: creation of a missing `~/Applications` must be relative to an
    owner-validated parent descriptor, and every later stage, rename, rollback, commit, and
    uninstall must reopen the exact captured directory identity without following a replacement
  - the capture binds a recursive content fingerprint for every recognized existing helper and the
    staged candidate; changed same-inode contents stop deletion, commit, or rollback and retain the
    identity-bound backup instead of treating a familiar filename as continuing authorization
  - helper replacement is assembled and verified in a same-filesystem staging directory; an
    existing recognized helper and the one supported marker-free legacy bundle are moved to
    same-filesystem backups and restored on install failure before those backups are retired; the
    activation result is persisted owner-only inside the private stage before the child returns so
    a shell interruption cannot lose the information required for descriptor-safe recovery
  - newly installed helper bundles carry a structured Viventium owner marker; uninstall never
    removes an unrelated application merely because its filename resembles Viventium
  - when helper install runs from a checkout under macOS protected user folders such as
    `~/Documents`, `~/Desktop`, or `~/Downloads`, the helper runtime binding must prefer the
    supported public checkout outside those folders (default `~/viventium`) when that checkout is
    available
  - helper/status-bar config writes must use that same resolver so toggling the helper does not
    silently rebind it back to a protected-folder checkout and retrigger macOS TCC folder prompts
- On April 19, 2026, macOS folder-access prompts exposed the same install/runtime boundary again:
  - the menu-bar helper itself is the macOS app that TCC evaluates, not the shell the user
    originally used to run install commands
  - binding the helper to a repo checkout inside `~/Documents` is enough to trigger repeated
    Documents-folder prompts even when the helper app bundle lives in `~/Applications`
  - the correct fix belongs in helper install/config binding, not in App Support hand edits and not
    by asking users to grant broader folder access than the supported install actually needs
- On May 2, 2026, a recurrence exposed two additional helper delivery requirements:
  - already-installed helper state must self-heal stale protected-folder `repoRoot` values on
    helper launch, because source fixes in the installer do not automatically rewrite App Support
    config for users who already have the helper installed
  - detached helper start/stop must derive the command from the healed helper config instead of
    trusting a generated App Support wrapper that may still contain an old protected checkout path
  - when no safe checkout exists, helper install must fail closed and the running helper must block
    start/stop/backup actions with clear user guidance instead of silently launching from the
    protected checkout
  - Swift and shell protected-folder checks must both resolve symlinks so aliases or symlinked
    checkout paths do not bypass the macOS TCC boundary
  - the assembled helper app bundle must be locally code signed with the `ai.viventium.helper`
    bundle identifier after packaging so the installed app identity matches the product bundle;
    Developer ID signing is still required for update-stable TCC identity, so signing is not a
    substitute for keeping runtime roots out of protected folders
- The same incident clarified the developer-checkout escape hatch:
  - default public installs still prefer a safe checkout outside `~/Documents`, `~/Desktop`, and
    `~/Downloads` to avoid repeated macOS folder-access prompts
  - developers need an explicit machine-local setting when they want helper/start commands to run
    the checkout they are actively editing, even when a separate installed checkout also exists
  - `bin/viventium runtime-checkout use --this --allow-protected-folder` records that choice under
    App Support state and refreshes the helper binding without copying, deleting, resetting,
    pulling, or migrating code, runtime config, snapshots, or database state
  - helper refresh from this command should relaunch the status-bar helper so applying the setting
    does not make the menu disappear until the next login
  - helper config carries the same explicit protected-folder acknowledgement so the helper does not
    silently self-heal the developer checkout back to `~/viventium`
  - global or stale checkout invocations of start, stop, and helper-binding commands should re-exec
    through the active runtime checkout instead of starting or stopping a different repo by accident
  - re-execed commands must use the active checkout's own component lock file instead of carrying
    the caller checkout's `components.lock.json`
  - the re-exec boundary must reset both argv and inherited environment, including
    `VIVENTIUM_COMPONENTS_LOCK_FILE`; otherwise the right code can still read the wrong component
    lock
  - an explicit active-checkout setting must outrank LaunchAgent environment hints such as
    `VIVENTIUM_HELPER_RUNTIME_REPO_ROOT`; install-time helper defaults should not outvote a later
    developer selection
  - clearing the setting restores automatic checkout resolution; it must not remove App Support
    state or repo files
- The same pass exposed an optional-cleanup rule:
  - disabled optional maintenance features must not block start/upgrade when their cleanup helper is
    absent from a temporary or partial checkout
  - if memory hardening is explicitly enabled and its helper script is missing, fail closed; if the
    feature is disabled and an old LaunchAgent cleanup cannot run, warn and continue
- The same May 2, 2026 incident clarified two health-reporting boundaries:
  - the macOS helper's Running/Stopped state is a core surface check only: LibreChat API, LibreChat
    frontend, and the modern playground. Optional sidecars such as MCP servers, local search,
    recall, voice, or scraper services must not make the helper show `Start` while the app is
    usable.
  - optional sidecars still matter for stop convergence and for `bin/viventium status`, where each
    sidecar must report its own live/configured/action-required state.
  - OAuth-backed MCP servers that already have a usable stored access or refresh token should be
    warmed by the connection-status endpoint. The UI should not stay in a needs-auth/disconnected
    state merely because the last refresh happened while the local MCP listener was down.
  - status-route warmup must be bounded: cooldown/in-flight guards still apply, OAuth token
    presence should be short-cacheable, and setup data should be re-read only after a warmup
    attempt that could have changed connection state
  - the browser MCP status query should refresh periodically while MCP controls are mounted so a
    recovered local listener or refreshed token becomes visible without requiring a full page reload.
  - MCP endpoint readiness must treat an HTTP auth challenge from `/mcp` as a live server signal;
    connection-refused is the failure state.
- On May 15, 2026, restart QA exposed a status-bar helper lifecycle boundary:
  - loginwindow can launch the Viventium helper successfully and still report an early app death
    before the delayed helper auto-start callback submits `bin/viventium launch`
  - the helper must explicitly disable AppKit automatic termination while it owns the status-bar
    menu and login auto-start responsibility, because a menu-bar app with no normal windows must
    remain alive long enough to start and monitor the local runtime
  - the helper bundle must also declare `NSSupportsAutomaticTermination=false` so the lifecycle
    contract is visible in the shipped app, not only in Swift runtime code
  - helper startup QA must inspect loginwindow/system logs, the helper process, helper logs, and the
    live runtime surfaces; the presence of a macOS login item alone is not proof that Viventium will
    start after reboot
- The helper's `Advanced > Prompt Workbench` submenu is a separate lifecycle surface:
  - `Open` must start the workbench if needed and then open the browser
  - `Start` and `Stop` must call `bin/viventium prompt-workbench ...`, not the main stack start/stop
    commands
  - `Stop` must terminate only the managed Prompt Workbench process recorded under App Support
    prompt-workbench state, leaving LibreChat, native services, and Viventium's current runtime state
    untouched
  - clean installs and upgrades must refresh the shipped helper fallback when the helper source
    changes, or new users will not see the same Advanced submenu
- The config compiler owns the Workbench sidecar flag:
  - `runtime.prompt_workbench.enabled: true` compiles to `VIVENTIUM_PROMPT_WORKBENCH_ENABLED=true`
    and `START_PROMPT_WORKBENCH=true`
  - supported local installs and upgrades set this flag true by default because Prompt Workbench is
    part of the nightly reflection contract
  - `runtime.prompt_workbench.seed_nightly.enabled/active/executor` compiles to
    `VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_*` env keys; default local behavior is an active
    `glasshive_host` Workbench schedule
  - the main launcher may start and watchdog Prompt Workbench only when that compiled/env flag is
    enabled, or when an equivalent explicit env override is provided
  - stack-managed starts must suppress stdout from `bin/viventium prompt-workbench start` so the
    launch token/authenticated URL is not copied into helper or stack logs
  - helper/CLI `prompt-workbench stop` must leave a local user-stopped marker that the sidecar
    watchdog respects, so the Workbench does not immediately reopen after the user stops it
  - `bin/viventium prompt-workbench stop` remains scoped to Workbench and must not stop the main
    runtime
- On April 5, 2026, a background-cortex failure showed why install/start ownership matters:
  built-in Anthropic agents are re-seeded from source-of-truth on startup, so fixing only live
  Mongo state or only a local runtime leftover would not align fresh installs or later restarts.
- On April 5, 2026, the memory-writer compile path exposed the same ownership rule from another
  angle: `local.librechat.yaml` still carried historical xAI defaults for `memory.agent` and the
  Anthropic endpoint `titleEndpoint/titleModel`, but the compiler never overlaid those fields. The
  correct fix was to compile those runtime surfaces from real configured provider availability, not
  to hand-edit App Support outputs or patch the memory runtime.
- On April 8, 2026, a follow-up incident showed the other half of the same contract:
  the compiler correctly emitted `memory.agent.provider = openai`, but runtime provider resolution
  still rejected that generated value in one path with `Provider openai not supported`. The fix
  belongs at the shared runtime normalization/initialization boundary, not in App Support hand
  edits and not by changing the compiler back to a different alias.
- On April 12, 2026, local live QA showed the next runtime boundary clearly:
  classifier-first activation and fallback wiring can be fully healthy while the user-visible
  Outlook or Gmail task still waits on user-scoped connected-account OAuth. Install/status/setup
  guidance must tell users to connect both:
  - one foundation model account so the shipped agents can reason
  - the matching Google Workspace or Microsoft 365 account when they want those tool surfaces
- On April 12, 2026, voice-call QA exposed the install/bootstrap side of the same contract:
  - the main agent's fast voice route can be visibly active in runtime logs while still relying on
    inherited primary-model parameters if the seeded source-of-truth omits the dedicated voice bag
  - shipped voice overrides must therefore seed provider-specific voice parameters explicitly
    (`voice_llm_model_parameters.reasoning_effort: none` for the current xAI/Grok voice route, or
    `voice_llm_model_parameters.thinking: false` for Anthropic voice routes)
  - seed/sync tooling must preserve that bag so fresh installs, local rebuilds, and reviewed syncs
    all keep the same low-latency voice defaults
- On April 13, 2026, a remote clean-machine audit showed the next nested-release boundary:
  - fresh installs followed the LibreChat ref pinned in `components.lock.json`, not a newer local
    nested checkout
  - a stale parent pin therefore shipped an older built-in main-agent prompt even though current
    nested source had already been updated
  - release readiness for built-in agent/prompt/runtime changes therefore includes updating and
    verifying the parent component pin, not only reviewing the nested repo
- The same April 13, 2026 audit also clarified the existing-install upgrade boundary:
  - the startup seed path already upserts built-in agents from the checked-out bundle on every run
  - existing installs therefore self-heal only after the supported upgrade path refreshes the
    checked-out nested component ref
  - the product gap is not “missing reseed logic”; it is failing to move stale installs onto the
    reviewed pinned checkout before that reseed/upsert runs
- On April 19, 2026, a live local rollback incident clarified the ownership boundary inside that
  reseed path:
  - startup reseed must not overwrite live user-managed built-in agent fields on existing installs
  - protected live fields include at least name/description, instructions, tools, model/provider,
    model bags, voice model/provider/bag, conversation starters, category, and background cortex
    wiring
  - the startup seed path may still create missing built-ins, fill missing fields, repair ACLs, and
    apply canonical runtime normalization to the effective live assignment
  - intentional changes to those live user-managed fields belong in reviewed sync flows such as
    `viventium-sync-agents.js compare` plus the narrowest safe push mode, not in automatic startup
    reseed
- The same April 13, 2026 audit clarified the recall-default ownership boundary:
  - if local conversation recall should default on when the machine already supports the local
    recall path, that default must be set consistently in shared config-building layers
  - fixing only one wizard branch is not enough when presets, base config generation, and advanced
    setup can still seed a different default
- The same April 13, 2026 remote connected-account QA clarified the continuity acceptance boundary:
  - a user can have a healthy connected foundation-model account and successful live chat while
    durable memory is still dead
  - an explicit `remember this` prompt that gets an in-thread success reply is not enough evidence;
    QA must also check the actual `Memories` surface and durable store
  - a visible recall toggle is only policy, not proof that the local recall runtime/index is live
  - when helper logs say the local RAG API is unavailable and recall sync is disabled, the product
    must present recall as unavailable even if the UI toggle still exists
- On April 14, 2026, the same remote memory follow-up clarified the local package-build boundary:
  - LibreChat `packages/*/dist` outputs are generated local runtime artifacts, not tracked public
    release sources
  - a source-only fix inside `packages/api/src/...` is therefore insufficient if the supported
    upgrade/start path leaves an older local `dist` bundle in place
  - launcher rebuild detection must compare package source trees against `dist` markers instead of
    watching only top-level manifest mtimes
  - public release coverage should verify that rebuild contract plus a built-bundle regression, not
    assume a checked-in `dist` artifact exists in clean public clones
- The same April 14, 2026 upgrade rerun clarified the nested-component refresh boundary:
  - existing installs can carry a dirty managed component checkout from earlier local hotfixes or
    debugging
  - `bootstrap_components.py` may correctly refuse to overwrite that dirty checkout, but upgrade
    must not continue as if the pinned component landed successfully
  - `bin/viventium upgrade` must therefore fail closed when selected components remain in
    `kept local dirty checkout` state after refresh
  - `doctor.sh` must report the real validation mode instead of always claiming "present at the
    pinned refs" when validation only passed because a dirty or vendored checkout was tolerated
  - the parent component pin itself must be the exact published full commit SHA from the nested
    component repo; a mistyped or locally copied hash is enough to break the supported fetch path
    even when the intended nested fix is already live on origin
  - review-head pins must be marked `review-head-pending-merge` in both the parent component lock
    and the Native component policy. The Native candidate producer fails closed until both records
    are deliberately changed to `merged` after the nested changes land, and it independently checks
    that the Native LibreChat commit equals the parent pin
  - a later July 19, 2026 audit separated clean refresh work from protected local work: a clean
    selected checkout at a different HEAD is `refresh_required` and may move to the exact pin, while
    dirty, unreadable, orphan-risk, unrelated, or unverifiable component state blocks before parent
    pull, stack stop, or any component mutation
  - update inspection is a real read-only operation: remote observation must not run `git fetch`,
    create App Support layout, compile config, install the helper, or touch the running stack
  - a policy blocker returns a nonzero machine status while preserving structured JSON for the
    helper; clean refresh-required state remains safe to attempt
  - mutating upgrade must refuse a running stack without `--restart` before pulling, gate the
    pre-upgrade continuity baseline while services are still available, fail when stop fails, and
    never describe an availability restart from partially changed disk state as a rollback
  - post-upgrade continuity `error` means do not auto-restart; `--allow-dirty` never authorizes a
    fetch/pull and therefore requires `--skip-pull`
- The same April 14, 2026 continuity hardening pass clarified the operator-state boundary:
  - chat history, saved memory, recall corpora, schedules, and runtime/provider state can drift
    independently
  - restore and upgrade must therefore compare continuity surfaces explicitly instead of assuming
    any snapshot or restart is safe because one service is healthy
  - recall after restore must fail closed until rebuild is intentionally acknowledged
  - manual backup UX belongs on the supported helper/CLI path, not in hidden private scripts
- On April 12-13, 2026, a real remote clean-machine install on Intel macOS clarified the next
  installer/runtime boundaries:
  - `bin/viventium status` and install summary must not claim "ready" while core web surfaces are
    still warming up; fresh users read that heading literally
  - headless macOS CLI paths must sanitize unsupported locale defaults such as `C.UTF-8` so clean
    SSH-driven installs do not emit noisy Perl locale warnings
  - a fresh browser user on connected-account auth must get an actionable "connect your account"
    message, not the raw `No key found` fallback intended for direct API-key mode
  - registration success redirects must not update router state during render; even a harmless
    warning there makes a clean install look unstable during first-user onboarding
- The same April 13, 2026 installer/runtime hardening pass closed the next launcher/status gaps:
  - `bin/viventium status` must distinguish "configured but intentionally stopped" from "still
    starting" by reading the recorded stack-owner state instead of treating any failed live probe as
    startup in progress
  - local loopback health checks in install summary should prefer `curl` before Python urllib on
    macOS hosts where Python probing can misreport localhost reachability
  - local Meilisearch readiness must require the configured API key, not only unauthenticated
    `/health`, because stale listeners with the wrong key create a false green and then break local
    search sync
  - local Meilisearch readiness must also inspect recent failed tasks and fail closed on
    index-version or incompatible-engine failures; otherwise `/health` can stay green while
    settings/document tasks churn forever
  - Viventium-owned local Meilisearch must run with source-owned resource/log caps and a pinned
    stable image; derived indexes may be archived and rebuilt from Mongo, but Mongo conversation,
    user, and config collections are protected state
  - a healthy LibreChat API on `:3180` must not suppress starting a missing frontend on `:3190`;
    partial-stack startup must repair the missing surface
  - local conversation-search sync failures may degrade recall freshness, but they must not abort
    frontend availability during first-run startup
- On April 13, 2026, remote clean-machine onboarding exposed the optional-service consistency rule
  that still applies when a user explicitly disables GlassHive:
  - generated `librechat.yaml`, seeded built-in agent tools, and runtime MCP/tool loading must all
    agree when GlassHive is off
  - otherwise a missing local GlassHive MCP can surface to fresh users as a generic `No key found`
    error even though foundation-model auth is healthy
- On May 31, 2026, the nightly-routines QA follow-up made GlassHive part of the supported local
  install and upgrade path because the built-in nightly reflection uses scheduled Workbench prompts
  delivered through GlassHive. The approved July 18, 2026 Easy Install Native contract narrows when it
  activates: the capability remains supported, existing explicit state is preserved, and new
  Easy Install Native installs defer worker auth and schedules until after the first useful answer.
- The same April 13, 2026 remote clean-machine pass exposed the public-clone bootstrap boundary:
  - a shipped public checkout can contain vendored component source without nested git history
  - `bootstrap_components.py` must therefore treat a bootable vendored component tree as valid
    installer input instead of aborting with `Existing path is not a git repo`
- The same April 13, 2026 uninstall/reinstall pass clarified the destructive-cleanup boundary:
  - uninstall and factory reset must synchronously drain managed native services before deleting App
    Support state
  - helper-detached cleanup is acceptable for normal stop flows, but destructive removal cannot
    race the deletion of pid/config state needed to identify managed native services such as LiveKit
- The same April 13, 2026 remote clean-machine reinstall clarified two more first-user boundaries:
  - non-interactive/headless setup must not spam macOS Keychain write failures when the supported
    fallback is to keep secrets in machine-local config state
  - first-message auth aborts on a brand-new conversation must not queue title generation against a
    transient stream id; otherwise clean installs surface a misleading `/api/convos/gen_title/...`
    404 after the real `connected_account_required` error
- On July 13, 2026, scheduled-provider QA exposed two connected-account truthfulness boundaries:
  - a stored key row is not proof of connectivity; status must first prove the active runtime can
    decrypt the value, otherwise Settings reports disconnected and guides a supported reconnect
  - an OAuth provider may reject an access token before its stored expiry; the Codex route refreshes
    and replays exactly once on the first provider 401, deduplicates concurrent refreshes per user,
    and preserves the original authenticated fallback/error path if refresh fails
- On April 9, 2026, a local restart verified the memory-writer contract end to end:
  - before restart, the live generated runtime still pointed memory at `openai / gpt-5.4` and the
    running helper logs showed the unsupported-provider initialization failure
  - after the compiler/runtime fix and restart, the generated runtime pointed memory at
    `xai / grok-4.3` with `voice_llm_model_parameters.reasoning_effort: none`
  - the saved-memory path then ran through product code without manual App Support or Mongo edits
- On April 9, 2026, the same ownership rule extended to local-first conversation recall:
  - the compiler must emit the selected retrieval embeddings provider/model explicitly
  - wizard defaults, preflight, doctor, install summary, and launcher readiness must consume the
    same retrieval-config helper
  - the startup path must fail closed when recall depends on Ollama embeddings but Ollama is not
    actually reachable
- A later April 9, 2026 follow-up clarified the next layer of the same contract:
  - fresh local installs can have Ollama installed and reachable while still missing the configured
    embedding model artifact
  - launcher ownership therefore includes verifying/pulling the configured model before RAG startup
  - doctor ownership includes reporting model readiness instead of only binary presence
  - Ollama host responses can normalize untagged model requests to `:latest`, so readiness checks
    must accept that canonicalization rather than treating it as a false missing-model error
- On April 9, 2026, conversation-recall prompt propagation exposed the compile/source boundary:
  - compile-time source-of-truth precedence must be private curated YAML when present, otherwise the
    tracked `local.librechat.yaml`
  - the compiler must not seed itself from a previously generated runtime `librechat.yaml` during
    compile, because that can silently drop newly added tracked fields until some manual cleanup or
    lucky regeneration path happens
  - generated runtime YAML is a deployment artifact for launch/runtime, not an authoring source for
    the next compile pass
- On April 10, 2026, MS365 MCP startup exposed the same runtime-ownership rule on a shipped local
  port:
  - restart must not trust an arbitrary healthy listener already occupying the shipped MS365 MCP
    port
  - the launcher must verify that the existing listener is Viventium-owned and reclaim the port
    when another workspace's MCP server is squatting there
  - otherwise the isolated runtime can silently inherit the wrong Azure app credentials even though
    the compiled Viventium config is correct
- On April 12, 2026, web search drift showed the same compiler boundary from another angle:
  - the runtime correctly disabled Web Search because canonical App Support config never enabled
    `integrations.web_search`
  - the tracked source-of-truth YAML still advertising `interface.webSearch: true` did not make the
    machine live
  - the right fix was to update canonical config and restart, not to patch generated
    `librechat.yaml`
- On April 21, 2026, built-in agent continuity exposed the adjacent persisted-tool boundary:
  - existing-install startup reseed correctly preserved live tool arrays, but that alone was not
    enough when global runtime gates disabled a capability such as Web Search
  - the fix belongs in runtime-field repair: prune only the tools the current machine cannot back,
    while still preserving all other live user-managed tool choices
- On May 7, 2026, xAI standalone TTS added a provider-id and secret-routing rule:
  - canonical voice TTS provider id is `xai`
  - legacy aliases `x_ai`, `grok`, and `xai_grok_voice` are accepted at config/compiler/runtime
    boundaries but compile to the standalone `xai` TTS provider; they do not select the retired
    Grok Voice Agent model
  - `voice.tts.xai.tts_api: voice_agent` is retired and must fail closed with guidance to use
    `tts`; it is never silently remapped
  - hosted voice setup must be able to collect a TTS-only xAI API key and store it under
    `voice.provider_keys.xai` / `keychain://viventium/x_ai_api_key`
  - xAI TTS secret precedence is voice provider key, selected `voice.tts`, keychain fallback, then
    `llm.extra_provider_keys.x_ai` only as a fallback
  - generated Telegram service env must include xAI voice settings and
    `VIVENTIUM_XAI_TTS_API_KEY` so Telegram voice replies can follow the same saved Speaking route
    and dedicated TTS key as LiveKit calls
  - the hosted wizard must not silently default new installs to xAI before the user has explicitly
    configured and QA'd that provider

### July 20, 2026 Ownership-Safe Failure And Removal Boundary

Isolated Easy Install Docker QA exposed three destructive-boundary rules that apply to every
installation profile:

- Helper ownership must survive across CLI processes. Install writes an atomic owner-only receipt
  under canonical App Support state after an explicit helper skip or a successful helper install.
  Uninstall reads and validates that receipt before moving App Support into the recoverable removal
  backup. It removes the helper only when the receipt says this target owns it. A receipt-less legacy
  install may migrate only after its helper config and bundle marker both prove the same canonical
  target; unknown ownership fails closed without touching the helper.
- A failed install must drain the exact detached process group that the attempt recorded before
  rolling back config. The recorded group is signalable only when it is not the current CLI group and
  its live command lines are scoped to this repo or App Support target. Cleanup sends bounded TERM,
  then KILL only if required, and clears the matching group/native-Mongo pid records. It must never
  use a broad name-based kill.
- A disabled Telegram integration does not own the fixed LaunchAgent label merely because the label
  exists. LaunchAgent submission writes a mode-`0600`, target-bound receipt; stop/restart may query or
  boot out that label only with a valid receipt. Legacy migration additionally requires the recorded
  Telegram PID, the live launchctl PID, and process scope to agree.
- Local password recovery must follow the selected runtime, not a hard-coded parent/nested checkout
  assumption. `password-reset-link` validates and resolves the selected LibreChat directory before
  executing its helper. An explicit `DOMAIN_CLIENT` wins, followed by `CLIENT_URL`, then the compiled
  `VIVENTIUM_PUBLIC_CLIENT_URL`; only when none is configured may the CLI synthesize the configured
  loopback frontend origin. A missing or invalid selected source fails closed without issuing a
  token. This keeps non-loopback deployments intact while making the default local Easy Install
  recovery path work without extra origin configuration.
- The immutable Native payload must expose the same local recovery capability. Its public CLI ships
  `password-reset-link <email>`, starts the installed Native runtime when necessary, and invokes only
  the payload's pinned Node executable and bundled LibreChat helper against the private Native
  MongoDB Unix socket. It must
  construct the child environment from the compiler-owned Native allowlist and machine-owned runtime
  secrets rather than inheriting provider credentials from the calling shell. A missing helper,
  mismatched release pointer, invalid email, or failed issuance is a hard failure; public browser
  password reset remains disabled when no email delivery service is configured.
- Immutable Native LibreChat must not expose its backend on the shared loopback API port. The
  backend listens on one owner-checked Unix socket under the mode-`0700` Native runtime directory;
  the browser-facing `3190` proxy validates the exact socket path, owner and mode before launch and
  uses that socket for ordinary HTTP, first-admin registration, and WebSocket upgrades. Startup,
  health, status, stop, and rollback bind the socket listener to the recorded LibreChat process
  group, remove only a proven stale owned socket, and reject a symlink, non-socket, foreign owner, or
  foreign listener. A process that acquires the historical TCP `3180` port must receive zero Native
  traffic. Source and Docker profiles retain their documented TCP API contracts; this isolation is
  specific to the immutable Native Easy Install runtime.
- Immutable Native MongoDB must not expose an unauthenticated TCP listener, including loopback.
  `mongod` binds only the exact support-owned Unix socket under the mode-`0700` runtime directory,
  with socket mode `0600`; its automatic `/tmp` socket is disabled. Startup and maintenance bind
  that socket to the recorded MongoDB process group, reject foreign/stale-unsafe paths, and fail if
  any process in that group owns a TCP listener. Source and Docker profiles retain their separate
  configured MongoDB TCP contracts.
- The Native release is an **Easy Install** surface. Its public CLI and helper expose complete
  snapshot and in-profile restore now that both use the shared public logical-bundle validator and
  the Native transaction below. They must not advertise Custom Settings Install, in-place source
  upgrade, or cross-profile migration while those implementations are absent. Ordinary users see
  only actions that work.
  Custom Settings Install remains a supported source-installer choice; moving an established Native
  data directory to or from the source/Docker profile requires a separately reviewed migration and
  must never be implied by a menu item. Native updates arrive through a newly verified signed
  Bootstrap, not an in-place Git or package-manager command.
- Native snapshot uses the installed immutable payload's pinned Python, Node, LibreChat Mongo/BSON
  dependencies, and the exact owner-checked Mongo Unix socket. It captures only the allowlisted
  logical Mongo collections, sanitized canonical config, bounded App-Support uploads, and an online
  schedule backup. Provider/channel/browser credentials and derived Recall state remain excluded.
  The frontend proxy and LibreChat writer stop before capture, no foreign Mongo client may retain the
  private socket, and the exact prior stopped/Mongo-only/full service state returns afterward. A
  successful semantic validation is required before the owner-only `LATEST_PATH` pointer is
  atomically replaced; a failed capture preserves the prior pointer. Native manifests bind the
  captured data schema and source release identity; restore accepts only the current release's
  declared compatibility range and requires a reviewed migration for any schema transition.
- Raw tool-call result and argument payloads are not portable continuity data. Tool-call collection
  rows are excluded, and tool-call parts embedded in otherwise preserved message history have their
  argument/result payload removed structurally. This intentionally trades tool-transcript fidelity
  for the credential boundary: arbitrary plaintext returned by tools cannot be proven secret-free
  from key names alone. Ordinary user and assistant message text remains canonical chat history and
  therefore stays inside the owner-only, not-self-encrypted backup boundary.
- Native restore accepts only a complete owner-only bundle whose recorded profile and database are
  exactly `native` and `LibreChat`. Source/Docker bundles fail as unsupported migrations. Before any
  live mutation or service stop, it bounds disk/time/file use, copies the source through no-follow
  source descriptors into a private App-Support stage, proves source/copy hashes and inode stability,
  validates only that private copy, stages files and a separate socket-only Mongo data directory,
  imports through a transaction claim, and stops that isolated staging process. Its strict activation
  and rollback journal covers the exact mutable roots: canonical config, Mongo data, uploads, Native
  schedules, and Native continuity ledgers. Every rename has a durable pending/completed transition;
  rollback first validates the complete remaining checkpoint and durably advances each reversed root
  so a second process can resume after loss at any rollback rename. A missing/stale pid record cannot
  authorize activation: fixed listeners, private sockets, process guards, and open handles below all
  mutable roots must prove complete quiescence.
- Native restore never replaces `native-runtime.json`, `runtime.env`, Native machine secrets, helper
  binding, or the immutable release tree. The journal binds the exact prior stopped/Mongo-only/full
  service intent. If the prior runtime was running, the restored runtime must start and pass installed
  health before commit; activation/start/health failure or next-command recovery rolls back the
  mutable roots and returns that exact prior service state before the journal is retired. Read-only
  lifecycle commands fail closed while recovery is pending; mutating commands recover under the
  installed release identity. A newly signed Bootstrap refuses to download or cross the release
  identity boundary until the currently installed release has cleared its journal. Restore success
  still requires local browser-password reset, account and channel reconnection, and Recall rebuild.
  The retained pre-restore checkpoint is machine-local, owner-only, and not a portable encrypted
  backup. Helper logs use owner-only directories and no-follow regular-file descriptors; an unsafe
  log target disables that action instead of following or replacing another file.
- Native compliance must bind both the declared license expression and the actual notice bytes
  shipped for every physical package. A recognized SPDX token without a package-owned LICENSE,
  LICENCE, COPYING, or NOTICE file is not a pass: the generator records `notice_present: false`,
  marks the package for review, and the independent verifier rejects empty or tampered inventories.
  Compiler/assembler component metadata is hash-bound objects, so generator and verifier must read
  the nested `version` field rather than stringifying the whole record. Legal approval is never
  inferred from a package name, a dependency being popular, or a permissive-looking declaration.

Docker-mode preflight must test the selected Docker endpoint, not merely the presence of a `docker`
binary. QA harnesses that use a non-default isolated context must pin that endpoint for both healthy
and daemon-down cases; otherwise a removed test context can fall back to an unrelated local Docker
daemon and create false-green evidence.
