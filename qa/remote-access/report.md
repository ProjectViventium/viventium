# Remote Access QA Report

## Date

- 2026-04-04

## Build Under Test

- Repo branch: `codex/remote-modern-playground-access`
- Nested LibreChat branch: `codex/remote-modern-playground-access`
- Runtime profile: `isolated`
- Live config used for public-edge validation:
  - `~/Library/Application Support/Viventium/config.yaml`
  - `runtime.network.remote_call_mode: public_https_edge`

## Checks Executed

1. Targeted root regression suite.
   - Command:
     `python3 -m pytest tests/release/test_preflight.py tests/release/test_config_compiler.py tests/release/test_remote_call_tunnel.py -q`
   - Result: `73 passed`
2. Launcher/script syntax validation.
   - Command:
     `bash -n bin/viventium scripts/viventium/native_stack.sh viventium_v0_4/viventium-librechat-start.sh`
   - Result: passed
3. Public-origin routing contract validation.
   - Result: `Origin: http://localhost:3300` returned `serverUrl=ws://localhost:7888`
   - Result: `Origin: https://playground.199.7.147.132.sslip.io` returned `serverUrl=wss://livekit.199.7.147.132.sslip.io`
4. Live public-edge runtime validation.
   - Result: launcher reached `All Services Running`
   - Result: runtime state published:
     - `https://app.199.7.147.132.sslip.io`
     - `https://api.199.7.147.132.sslip.io`
     - `https://playground.199.7.147.132.sslip.io`
     - `wss://livekit.199.7.147.132.sslip.io`
   - Result: router mappings included `80/tcp`, `443/tcp`, `7889/tcp`, `7890/udp`, `5349/tcp`
5. LiveKit TURN/TLS runtime validation.
   - Result: generated `livekit.yaml` contained:
     - `turn.enabled: true`
     - `domain: livekit.199.7.147.132.sslip.io`
     - `tls_port: 5349`
   - Result: listeners existed on:
     - `7888/tcp`
     - `7889/tcp`
     - `7890/udp`
     - `5349/tcp`
6. Localhost regression validation.
   - Result: authenticated LibreChat chat on `http://localhost:3190` returned exact reply `QA_OK`
   - Result: a fresh modern-playground voice session connected successfully on `http://localhost:3300`
   - Result: transcript toggle worked
   - Result: typed transcript prompt `Reply with exactly REMOTE_QA_OK and nothing else.` returned exact reply `REMOTE_QA_OK`
   - Result: successful voice run had `0` browser console errors
7. External public fetch sanity check.
   - Result: independent external fetch reached `https://playground.199.7.147.132.sslip.io/` and returned HTML for the modern playground shell
8. Provider-prerequisite checks.
   - Result: Tailscale CLI is installed but not running/authenticated on this Mac
   - Result: NetBird CLI is not installed on this Mac

## Findings

- The branch now supports both private-mesh modes structurally:
  - `tailscale_tailnet_https`
  - `netbird_selfhosted_mesh`
- The real public-browser-capable mode in this repo is `public_https_edge`.
  - It is live on this Mac with Caddy-managed HTTPS, public-IP-derived `sslip.io` hostnames, router
    mappings, and TURN/TLS-ready LiveKit state.
- The localhost path is preserved even after enabling the remote edge.
  - chat still works on `localhost`
  - a fresh voice launch still works on `localhost`
  - the modern playground transcript path still returns a real model reply
- The key regression fixed in this pass was the localhost/public LiveKit boundary.
  - earlier, localhost modern-playground sessions inherited the public LiveKit WSS URL and timed
    out on signal
  - now `api/connection-details` returns public LiveKit only for requests that originated from the
    configured public playground origin
  - localhost callers keep `ws://localhost:7888`
- The public `sslip.io` edge is externally reachable.
  - non-local fetch succeeded for the public playground shell
- Stable custom-domain access is the remaining operator-facing finish step.
  - the public edge works now through `sslip.io`
  - the durable bookmarkable production answer still requires explicit operator-controlled DNS
    instead of IP-derived fallback hosts

## Limitations

- The stable public-domain finish step was not live-validated yet because the required DNS records
  do not exist today.
  - `app.viventium.ai`
  - `api.viventium.ai`
  - `playground.viventium.ai`
  - `livekit.viventium.ai`
- This Mac cannot hairpin cleanly to its own public `sslip.io` hosts with local `curl`/Playwright,
  so public-surface reachability was validated through an external fetch path instead of a same-host
  authenticated browser run.
- Tailscale was not provider-native live-validated end to end on this Mac.
  - `tailscale` CLI is installed, but the local Tailscale service is not running/connected, so the
    tailnet-only URLs could not be exercised in a real tailnet session here.
- NetBird was not provider-native live-validated end to end on this Mac.
  - this machine does not currently have the NetBird client installed or joined to a self-hosted mesh
- TURN/TLS is now wired and listening on `5349`, but this report did not include a true external
  phone-on-cellular voice run over the public edge.
  - the strongest proof collected here is:
    - external public playground reachability
    - local successful voice session after remote-edge enablement
    - correct origin-based public-vs-local LiveKit routing
