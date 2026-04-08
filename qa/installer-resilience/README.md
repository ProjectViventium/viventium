# Installer Resilience QA

This QA record captures the April 7, 2026 installer hardening work for two clean-machine failure
classes:

1. optional public remote access must not abort local startup
2. the macOS helper must default to the shipped matching prebuilt binary on clean installs when
   local Swift toolchains are unreliable
3. Telegram bridge startup must survive long first-run LibreChat builds and self-recover once the
   API becomes healthy

## Scenarios

### 1. Public edge router-port conflict

Repro surface:

- clean/local install configured with `runtime.network.remote_call_mode: public_https_edge`
- router already forwards `80/tcp` and `443/tcp` to another LAN host

Expected behavior:

- startup logs a warning instead of exiting
- local services continue booting
- `public-network.json` persists the exact blocker
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
