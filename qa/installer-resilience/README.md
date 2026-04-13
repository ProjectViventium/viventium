# Installer Resilience QA

This QA record captures the April 7, 2026 installer hardening work for two clean-machine failure
classes:

1. optional public remote access must not abort local startup
2. the macOS helper must default to the shipped matching prebuilt binary on clean installs when
   local Swift toolchains are unreliable
3. Telegram bridge startup must survive long first-run LibreChat builds and self-recover once the
   API becomes healthy
4. clean-machine launcher/runtime startup must repair partial local stacks and reject stale
   local-search sidecars that only look healthy from an unauthenticated port probe

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
