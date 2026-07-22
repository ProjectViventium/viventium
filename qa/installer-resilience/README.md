# Installer Resilience QA

## Current Easy Install Audit Package

The current installer/new-user acceptance package is maintained through the case catalog and dated,
public-safe results below:

- [Native payload production integration QA](reports/2026-07-19-native-payload-production-integration.md);
- [Native Bootstrap Finder UX QA](reports/2026-07-20-native-bootstrap-finder-ux.md);
- [isolated Easy Install Docker core and failure/removal delta QA](reports/2026-07-20-isolated-easy-docker-delta-qa.md);
- [stable synthetic OpenAI API-key lifecycle QA](reports/2026-07-20-synthetic-openai-api-key-lifecycle-qa.md);
- [stable synthetic Anthropic API-key lifecycle QA](reports/2026-07-20-synthetic-anthropic-api-key-lifecycle-qa.md);
- [stable synthetic Groq and Grok API-key lifecycle QA](reports/2026-07-20-synthetic-groq-grok-api-key-lifecycle-qa.md);
- [provider-lifecycle compiler and browser-persistence gap audit](reports/2026-07-21-synthetic-provider-lifecycle-gap-audit.md);
- [experimental OpenAI compatibility-bridge QA](reports/2026-07-20-synthetic-openai-connected-account-lifecycle-qa.md);
- [locally available installer/delivery lifecycle inventory](installer-lifecycle-inventory-2026-07-18.md);
- [open-source installer and onboarding research](open-source-installer-research-2026-07-18.md);
- [phased remediation plan](express-installer-remediation-plan.md);
- [initial Fable 5 Extra review](fable-review-2026-07-18.md) and
  [final remediation reconciliation](fable-final-remediation-review-2026-07-18.md);
- [Claude Fable 5 Extra Easy Install review reconciliation](claude-final-express-review-2026-07-18.md);
- [physical MacBook Air Easy Install + Docker handoff](macbook-air-docker-qa-handoff.md);
- [storage-bounded disposable QA policy](storage-policy.json), enforced by `INST-032`;
- [umbrella reusable case catalog](cases.md), including discrete release gates through `INST-032` and links to
  narrower feature owners.

Current decision: **PARTIAL for the local Easy Install Native source candidate; not ready for a
public-release claim**. A disposable macOS VM now passes the stable browser-entered API-key lifecycle
for OpenAI, Anthropic, Groq, and Grok:
registration, encrypted local key save, two useful answers, refresh/restart persistence, invalid-key,
quota, outage and network repair, local Disconnect with no subsequent provider request, and key re-add.
The earlier source-candidate install/rerun/restart/reinstall and Feelings evidence remains supporting
lineage. The exact signed payload, truly vanilla no-developer-tools machine, public full-payload restore,
Developer ID/Keychain/Gatekeeper, wider fault/accessibility/network matrices, physical Docker
comparison, and delivery-pin/shipped-artifact alignment remain open.
The reconstructed parent candidate passed `python3 -m pytest tests/release/ -q` on 2026-07-22 with
1,539 passed, 11 skipped, and 0 failed in 275.92 seconds against temporary zero-copy links to all 11
clean reviewed component heads. A recorded corrected pin/payload/provenance slice passed 311/311;
the prior 174-pass run against rejected LibreChat `a2553962...` remains supporting history because
its exact argv was not retained. All 11 nested heads are hosted in open PRs. Corrected
LibreChat `44ac1f7a149e5a915e52f2f9f54fce5d38bab710` passes 59 stream and 216 Viventium route tests
locally, independent and Claude reviews pass, both parent manifests now match it, and all 15 exact
hosted checks pass, including actual Redis. No source suite can replace independent approval, committed delivery alignment, the
blocked signed artifact, or physical user paths.

The Finder-launched Native Bootstrap now has a source-built AppKit Easy Install window and compiled
headless-forwarding contracts. Its local synthetic headed run is still `BLOCKED` because the desktop
was locked; visible Cancel/Retry/success, VoiceOver, Reduce Motion, and the exact signed/notarized app
remain open under `INST-020` / `INST-023`.

The isolated Docker delta now passes core source-candidate install/start, Connected Accounts and
Feelings discovery, daemon-loss preflight/recovery, target-scoped failed-start cleanup, and
preserve-data uninstall. It does not close Docker Desktop GUI/Keychain/TCC, Recall/RAG, physical
power/resource, supported component-bootstrap, or exact shipped-artifact gates.
Historical scenarios below are supporting lineage, not substitutes for the current owning cases and
report.

Files dated before 2026-07-19 can retain “Express” in their filename or quoted historical result.
Current public product copy and all new evidence use **Easy Install** and **Custom Settings Install**;
the internal `express` / `custom` values remain compatibility identifiers.

## Storage guard for disposable-machine QA

Run source, unit, compiler, and browser-harness checks first. Freeze the candidate before acquiring
the storage lease. The guard state root must be an owner-only directory outside the public repo; it
contains machine-local Docker IDs and must never be copied into public QA evidence.

```bash
python3 scripts/viventium/qa_storage_guard.py prepare \
  --run-id arm64-pristine \
  --vm-name viventium-qa-arm64-pristine \
  --candidate /path/to/frozen-viventium-candidate \
  --state-root /path/to/private-evidence/qa-storage-guard \
  --policy qa/installer-resilience/storage-policy.json \
  --tart /path/to/tart \
  --docker /path/to/docker \
  --docker-disk "~/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw"

python3 scripts/viventium/qa_storage_guard.py clone \
  --run-id arm64-pristine \
  --state-root /path/to/private-evidence/qa-storage-guard \
  --source-vm macos-base

python3 scripts/viventium/qa_storage_guard.py run \
  --run-id arm64-pristine \
  --state-root /path/to/private-evidence/qa-storage-guard \
  -- /path/to/reviewed-qa-driver --synthetic

python3 scripts/viventium/qa_storage_guard.py cleanup \
  --run-id arm64-pristine \
  --confirm-run-id arm64-pristine \
  --state-root /path/to/private-evidence/qa-storage-guard
```

Do not start a second run when the guard says `CLEANUP_REQUIRED`. Review the persistent receipt,
remove only receipt-owned synthetic leftovers, and rerun the exact cleanup. Cleanup will not release
the lease while a post-baseline Docker container, volume, or image remains. Never use a global Tart or
Docker prune as recovery. The automated contract uses fake executables only; it does not count as the
final real disposable-Mac acceptance run. A guarded driver must also leave its exact process group
empty; a background grandchild is terminated and turns the run into `CLEANUP_REQUIRED` even when the
leader itself exited successfully.

## Disposable Easy Install Native browser QA

After creating a synthetic account in a disposable runtime, run the repeatable user-path harness:

```bash
VIVENTIUM_QA_CLIENT_BASE=http://127.0.0.1:13190 \
VIVENTIUM_QA_EMAIL='<synthetic-email>' \
VIVENTIUM_QA_PASSWORD='<synthetic-password>' \
node qa/installer-resilience/scripts/express-native-browser-qa.cjs
```

Add `--register` only on an empty disposable runtime. The harness requires a synthetic `.invalid`
identity, refuses non-loopback targets and production/CI use, verifies the stable API-key dialog
open/cancel/retry path without entering a credential, and stops before provider use. Screenshots
stay in its temporary private evidence directory.

### Full synthetic provider API-key lifecycle

The supported `INST-017` Easy Install path is
`qa/installer-resilience/scripts/openai-api-key-lifecycle-qa.cjs`. Point only the disposable runtime
at its loopback stub. OpenAI, Groq, and Grok use the OpenAI-compatible routes; Anthropic uses its
native Messages route and `x-api-key` authentication. Keep direct subscription authentication disabled.
The harness enters a synthetic key through the selected provider card, renders two useful answers, checks
refresh and runtime-restart persistence, and exercises invalid-key, quota, provider-outage, network,
local Disconnect, no-provider-call-after-Disconnect, and re-add recovery paths. It blocks every
non-loopback browser request. After valid/invalid entry, refresh, restart, Disconnect, and re-add it
also scans cookies, local/session storage, Cache Storage, and IndexedDB for the synthetic keys. It
writes screenshots plus a secret-free ledger outside the public repository; the ledger records only
the number of residue checks, never a key or storage dump.

```bash
VIVENTIUM_QA_CLIENT_BASE=http://127.0.0.1:3190 \
VIVENTIUM_QA_EMAIL='api-key-qa@example.invalid' \
VIVENTIUM_QA_PASSWORD='<synthetic-password>' \
VIVENTIUM_QA_PROVIDER=anthropic \
VIVENTIUM_QA_RESTART_ARGV_JSON='["/path/to/disposable-restart"]' \
VIVENTIUM_QA_PRIVATE_EVIDENCE_DIR='/path/outside/public-repo/api-key-lifecycle' \
node qa/installer-resilience/scripts/openai-api-key-lifecycle-qa.cjs --headed
```

Use `--register` only for an empty disposable database. `VIVENTIUM_QA_PROVIDER` accepts `openai`,
`anthropic`, `groq`, or `xai` and defaults to `openai`. A provider-stub self-test is supporting
evidence only: `VIVENTIUM_QA_PROVIDER=anthropic node
qa/installer-resilience/scripts/openai-api-key-lifecycle-qa.cjs --self-test`.
The fail-closed browser-persistence guard has a secret-free offline regression:
`node qa/installer-resilience/scripts/openai-api-key-lifecycle-qa.cjs --storage-self-test`.
That self-test proves the guard rejects synthetic local-storage and IndexedDB residue; it does not
replace the headed lifecycle on the exact candidate.

### Full synthetic OpenAI experimental account-bridge lifecycle

`INST-017` owns a second, stricter browser harness for the explicitly enabled legacy compatibility
bridge:
`qa/installer-resilience/scripts/openai-connected-account-lifecycle-qa.cjs`. It uses a synthetic
local user and a provider stub bound only to `127.0.0.1`. Playwright intercepts the one expected
`https://auth.openai.com/oauth/authorize` navigation and renders a local grant/deny page before any
provider request is sent; every other non-loopback browser request is blocked. The OAuth token,
refresh, and Codex Responses SSE endpoints are loopback stubs. No real provider, cloud account,
credential, or personal state is used.

This is not the Easy Install default or an official OpenAI integration. Easy Install uses the
browser-entered encrypted API-key path proven in the stable-path report above.
OpenAI provider-side revocation is unsupported by the experimental bridge: OpenAI's official
Codex CLI guidance says no public endpoint exists for automated key deletion. The product must label
its action **Disconnect**, explain that it deletes Viventium's locally stored credential, and direct
users who need provider-side invalidation to their OpenAI account controls. The harness proves that
Disconnect deletes local access and prevents another provider request; it does not invent a remote
revocation call.

Before starting the disposable runtime, point only the QA runtime at the stub port:

```bash
VIVENTIUM_OPENAI_OAUTH_TOKEN_URL=http://127.0.0.1:14660/oauth/token
VIVENTIUM_OPENAI_CODEX_BASE_URL=http://127.0.0.1:14660/backend-api/codex
VIVENTIUM_CONNECTED_ACCOUNTS_RETURN_ORIGIN=http://127.0.0.1:3190
VIVENTIUM_EXPERIMENTAL_DIRECT_SUBSCRIPTION_AUTH=true
```

The integrated runtime must carry those values itself; setting them only on the browser process is
not evidence. Then run the harness with synthetic `.invalid` credentials and a no-shell restart argv:

```bash
VIVENTIUM_QA_CLIENT_BASE=http://127.0.0.1:3190 \
VIVENTIUM_QA_EMAIL='connected-account-qa@example.invalid' \
VIVENTIUM_QA_PASSWORD='<synthetic-password>' \
VIVENTIUM_QA_PROVIDER_PORT=14660 \
VIVENTIUM_QA_RESTART_ARGV_JSON='["/path/to/viventium/bin/viventium","restart"]' \
node qa/installer-resilience/scripts/openai-connected-account-lifecycle-qa.cjs --register --headed
```

Run `node qa/installer-resilience/scripts/openai-connected-account-lifecycle-qa.cjs --self-test`
without a runtime to verify the local token/refresh/Responses stub. The full path covers deny, popup
cancel, grant, two useful answers, browser refresh, runtime restart, proactive expiry refresh,
early-401 refresh, failed-refresh repair guidance, reconnect, local Disconnect, post-disconnect
answer refusal without provider contact, and regrant. Raw screenshots and the sanitized run ledger
stay in a mode-restricted temporary directory outside the public repo; console output replaces that
path with `<private>`.

Current execution truth is recorded in
`reports/2026-07-20-synthetic-openai-connected-account-lifecycle-qa.md`. The harness and contracts
are ready, but the browser lifecycle remains `NOT RUN` until the integrated LibreChat candidate is
available in the stopped disposable VM.

This QA record also captures the April 7, 2026 installer hardening work for these clean-machine
failure classes:

1. optional public remote access must not abort local startup
2. the macOS helper must default to the shipped matching prebuilt binary on clean installs when
   local Swift toolchains are unreliable
3. Telegram bridge startup must survive long first-run LibreChat builds and self-recover once the
  API becomes healthy
4. clean-machine launcher/runtime startup must repair partial local stacks and reject stale
   local-search sidecars that only look healthy from an unauthenticated port probe
5. install/start wait logic must keep following a valid detached startup handoff instead of
   reporting a false early stop while the real stack is still warming
6. helper install from a checkout inside a macOS protected folder must bind the helper runtime to
   the supported safe checkout instead of retriggering Documents/Desktop/Downloads access prompts
7. native CLI prerequisite drift must be caught by executable probes instead of `PATH` presence
8. status-bar helper login startup must keep the helper alive long enough to submit and monitor
   local runtime auto-start

## Scenarios

### 1. Public edge router-port conflict

Repro surface:

- clean/local install configured with `runtime.network.remote_call_mode: public_https_edge`
- router already forwards `80/tcp` and `443/tcp` to another LAN host

Expected behavior:

- startup logs a warning instead of exiting
- local services continue booting
- `public-network.json` persists the exact blocker, even if the remote-access helper exits before it
  can write its own failure state
- `bin/viventium status` reports `Remote Access: Action Required`
- no background UPnP refresh worker starts for the failed edge state

### 2. Clean macOS helper install

Repro surface:

- clean x86_64 macOS machine using CommandLineTools where local SwiftPM manifest linking is not
  reliable for the helper package

Expected behavior:

- installer uses `apps/macos/ViventiumHelper/prebuilt/ViventiumHelper-universal` first when
  `source.sha256` matches
- `swift` / `xcrun` are not required for the default end-user path
- development can still force local builds with `VIVENTIUM_HELPER_FORCE_LOCAL_BUILD=1`

### 3. Telegram bridge on a clean first build

Repro surface:

- clean/native install with Telegram enabled
- LibreChat package rebuilds and client bundle build delay the API for several minutes

Expected behavior:

- startup reports `Telegram Bot: starting (waiting for LibreChat API)` during the build window
- `bin/viventium status` reports `Telegram Bridge: Starting` while the deferred watcher is pending
- once the API becomes healthy, the deferred watcher starts the bridge automatically without a
  manual restart
- the launched Telegram bot process survives detached launcher exit instead of depending on the
  parent shell staying alive

### 4. Partial-stack repair and Meilisearch key drift

Repro surface:

- clean/native install or restart on a Mac with:
  - a healthy LibreChat API already listening on `:3180` while the frontend is not listening on
    `:3190`
  - or a stale Viventium-owned Meilisearch listener on `:7700` using the wrong master key
  - or a local conversation-search sync failure during fallback startup

Expected behavior:

- startup detects partial LibreChat state and starts the missing service instead of treating the
  whole stack as already healthy
- Meilisearch readiness requires the configured key, not just unauthenticated `/health`
- Viventium-owned stale-key Meilisearch listeners are recycled automatically
- local conversation-search sync failures log a warning and do not block the frontend from coming
  up
- `bin/viventium status` reports `Configured` after a real stop instead of implying the stack is
  still starting forever

### 5. Detached launch handoff on a clean first build

Repro surface:

- clean/native install on a slower Mac
- detached launcher path where `bin/viventium start` exits after handing off to the real detached
  launch process group
- background LibreChat package/client builds continue for several more minutes before API/frontend
  listeners are healthy

Expected behavior:

- install/start wait continues while the detached launch process group recorded in
  `state/runtime/<profile>/detached-launch.pgid` is still alive
- install does not print `stopped during startup` just because the short-lived detached wrapper pid
  has exited
- a re-entrant `bin/viventium launch` returns `already starting` instead of tearing down the same
  warming stack
- detached LibreChat API watchdog keeps waiting through the clean-build window instead of giving up
  before the first healthy API response

### 6. Helper install from a protected-folder checkout

Repro surface:

- supported public checkout exists at `~/viventium`
- helper install or `bin/viventium status-bar on` is invoked from another checkout under a macOS
  protected folder such as `~/Documents/<repo>`

Expected behavior:

- helper-config.json stores `repoRoot` as the safe public checkout, not the protected-folder
  checkout
- generated helper launcher scripts point at the safe public checkout for `bin/viventium`
- helper install/status-bar output makes the rebinding explicit
- an already-installed helper self-heals stale protected-folder helper config on launch when a safe
  public checkout is available
- helper install fails closed when the only available runtime checkout is under Documents, Desktop,
  or Downloads
- detached helper start/stop uses the healed helper config directly instead of stale generated
  App Support wrapper content
- the installed helper app bundle is code signed with the `ai.viventium.helper` bundle identifier
  as packaging hygiene
- the helper app no longer needs ongoing Documents-folder access just to poll/start/stop the local
  stack

### 7. Explicit active developer checkout

Repro surface:

- a developer has both a supported installed checkout such as `~/viventium` and a working checkout
  elsewhere
- helper/start commands would otherwise choose the installed checkout and miss the code under active
  development

Expected behavior:

- `bin/viventium runtime-checkout use --this --allow-protected-folder` records an explicit
  machine-local active checkout under App Support state
- helper config and helper launcher scripts bind to that active checkout after helper refresh
- the helper does not self-heal that explicit developer checkout back to `~/viventium`
- helper refresh relaunches the status-bar helper instead of leaving the menu hidden until next login
- start/stop/helper commands invoked through a stale checkout re-exec through the active checkout
- re-execed commands use the active checkout's own component lock file
- inherited lock-file environment from the stale checkout is reset at the re-exec boundary
- the active-checkout setting outranks LaunchAgent helper runtime environment defaults
- no repo files, App Support config, snapshots, or database state are copied, deleted, reset, or
  migrated by changing the active checkout setting

### 8. Native CLI dependency drift

Repro surface:

- a Homebrew-installed CLI is still present on `PATH`
- one of its shared-library dependencies has changed underneath it, so the binary aborts or cannot
  execute

Expected behavior:

- preflight marks the affected prerequisite missing instead of healthy
- `bin/viventium install` / `bin/viventium upgrade` attempts install, then reinstall, and fails
  with a Homebrew drift hint if the binary still cannot execute
- `bin/viventium status` warns when the live stack owner checkout differs from the checkout running
  the status command
- daemon readiness remains feature-specific; binary probes do not pretend that Docker, Tailscale,
  Ollama models, router mappings, or service listeners are ready

### 9. Helper and MCP status health boundaries

Repro surface:

- the core browser/API/playground stack is reachable
- one optional sidecar is missing, still warming, or auth-protected
- an OAuth-backed MCP server has a stored refresh token but no current in-memory connection after
  restart

Expected behavior:

- the macOS helper menu shows `Running` and a `Stop` action when the core user-facing surfaces are
  healthy
- optional sidecar failures do not make the helper show `Start`
- `bin/viventium status` reports each optional sidecar independently
- Google/MS365 MCP `/mcp` responses with HTTP auth challenges count as live listeners
- a connection-refused MCP endpoint becomes `Starting` during an active start command and
  `Action Required` after startup has completed
- the MCP connection-status API warms OAuth-backed MCPs when the user already has a usable stored
  access or refresh token, so the UI can move from disconnected/needs-auth to connected without a
  manual reconnect click
- OAuth warmup is bounded by cooldown/in-flight guards and short token-presence caching so mounted
  UI polling does not turn into avoidable DB load
- mounted MCP UI controls refresh status periodically so recovery is reflected without a full browser
  reload

### 10. Status-bar helper survives login auto-start

Repro surface:

- macOS login item launches `~/Applications/Viventium.app` after a reboot or sign-in
- the local runtime is not yet listening on the core API/frontend/playground ports

Expected behavior:

- loginwindow/system logs show the helper launch without an immediate app-death exit
- the helper process remains alive as the status-bar app
- helper logs record an auto-start decision and either submit `bin/viventium launch` or explain the
  explicit blocker
- the helper disables AppKit automatic termination while it owns status-bar and login auto-start
  responsibility
- the shipped helper bundle declares `NSSupportsAutomaticTermination=false`
- the active runtime checkout remains the existing App Support `active-checkout.json`; no source is
  copied into install paths
