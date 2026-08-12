# Installer Resilience QA

## Current Easy Install Audit Package

The current installer/new-user acceptance baseline is the 2026-07-19 audit package:

- [latest Easy Install lifecycle and safety QA](reports/2026-07-19-easy-install-lifecycle-and-safety-qa.md);
- [evidence report](reports/2026-07-18-express-installer-and-onboarding-audit.md);
- [locally available installer/delivery lifecycle inventory](installer-lifecycle-inventory-2026-07-18.md);
- [open-source installer and onboarding research](open-source-installer-research-2026-07-18.md);
- [phased remediation plan](express-installer-remediation-plan.md);
- [initial Fable 5 Extra review](fable-review-2026-07-18.md) and
  [final remediation reconciliation](fable-final-remediation-review-2026-07-18.md);
- [Claude Fable 5 Extra final Easy Install review reconciliation](claude-final-express-review-2026-07-18.md);
- [corrected visible Fable 5 Extra review and remediation reconciliation](claude-fable5-extra-review-2026-07-19.md);
- [physical MacBook Air Easy Install + Docker handoff](macbook-air-docker-qa-handoff.md);
- [umbrella reusable case catalog](cases.md), including discrete release gates through `INST-024` and links to
  narrower feature owners.

Current decision: **PARTIAL for the local Easy Install Native source candidate; not ready for a
public-release claim**. The disposable macOS VM passes install/rerun/restart/reinstall, real browser
registration and account handoff, provider authorization start/cancel/retry, disconnected-provider
guidance, Feelings discovery and persistence, core loopback listeners, failed-upgrade recovery,
Custom Settings Install rollback, preserve-data uninstall, and manual recovery of the tested synthetic state. The full
parent release suite passes with 1,032 passed and 7 skipped. The exact signed payload, truly vanilla
no-developer-tools machine, completed provider answer, public full-payload restore,
Developer ID/Keychain/Gatekeeper, wider fault/accessibility/network matrices, physical Docker
comparison, and delivery-pin/shipped-artifact alignment remain open.
The corrected visible second opinion accepted the audit closeout after its findings were reconciled
and retained the product's PARTIAL/not-ready verdict.
Historical scenarios below are supporting lineage, not substitutes for the current owning cases and
report.

Files dated before 2026-07-19 can retain “Express” in their filename or quoted historical result.
Current public product copy and all new evidence use **Easy Install** and **Custom Settings Install**;
the internal `express` / `custom` values remain compatibility identifiers.

## Disposable Easy Install Native browser QA

After creating a synthetic account in a disposable runtime, run the repeatable user-path harness:

```bash
VIVENTIUM_QA_CLIENT_BASE=http://127.0.0.1:13190 \
VIVENTIUM_QA_EMAIL='<synthetic-email>' \
VIVENTIUM_QA_PASSWORD='<synthetic-password>' \
node qa/installer-resilience/scripts/express-native-browser-qa.cjs
```

Add `--register` only on an empty disposable runtime. The harness refuses non-loopback targets and
production/CI use, never prints credentials or OAuth state, and intentionally stops before provider
authorization completes. Screenshots stay in its temporary private evidence directory.

This QA record captures the April 7, 2026 installer hardening work for two clean-machine failure
classes:

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
