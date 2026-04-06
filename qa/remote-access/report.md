# Remote Access QA Report

## Date

- 2026-04-04
- 2026-04-05

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
9. Directory-helper regression tests.
   - Command:
     `python3 -m pytest tests/release/test_directory_link.py tests/release/test_remote_call_tunnel.py -q`
   - Result: `17 passed`
10. Website directory layer static validation.
   - Commands:
     - `pnpm --dir /Users/adri/Documents/Viventium/website --filter @workspace/database generate`
     - `pnpm --dir /Users/adri/Documents/Viventium/website --filter marketing lint`
     - `pnpm --dir /Users/adri/Documents/Viventium/website --filter marketing typecheck`
   - Result: passed
11. Local signed directory registration.
   - Setup:
     - synthetic HTTPS Viventium target on `https://localhost:44443`
     - local website dev server on `http://localhost:3001`
     - isolated Postgres container for website directory state
   - Command:
     `NODE_TLS_REJECT_UNAUTHORIZED=0 python3 scripts/viventium/directory_link.py --state-file /tmp/viv-directory-qa/public-network.json --username qa-alice --directory-base-url http://localhost:3001`
   - Result:
     - `{"success":true,"username":"qa-alice","targetOrigin":"https://localhost:44443","vanityUrl":"http://localhost:3001/u/qa-alice"}`
12. Directory redirect behavior.
   - Result: `GET /u/qa-alice` returned `307` to `https://localhost:44443/`
   - Result: query-string preservation confirmed:
     - `GET /u/qa-alice?foo=bar` redirected to `https://localhost:44443/?foo=bar`
   - Result: `GET /u/does-not-exist` returned `404`
13. Directory abuse-guard validation.
   - Result: tampering the signed username after signing returned `400 {"error":"Signature verification failed."}`
   - Result: repeated valid registration attempts from one client IP produced throttling with an
     explicit retry contract:
     - attempts `1-8` returned `200`
     - attempts `9-10` returned `429` with `Retry-After: 60`
   - Result: browser-level check through Playwright hit the redirect route and stopped on the
     synthetic target's self-signed certificate, proving the redirect left the website and reached
     the target origin

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
- The redirect-only website directory layer now exists and is functioning locally.
  - the self-hosted runtime publishes a signed verification document at
    `/.well-known/viventium-instance.json`
  - `bin/viventium register-link <username>` signs the registration with the local instance key
  - the website verifies the signature and target before saving `username -> public_client_origin`
  - `viventium.ai/u/<username>` can therefore stay a phonebook rather than a relay
- The current safety posture for the directory layer is materially better than a naive open redirect.
  - unknown usernames return `404`
  - tampered signatures are rejected
  - registration and redirect endpoints are rate-limited
  - throttled responses carry `Retry-After: 60`
  - verification fetches refuse redirect chains and time out quickly
  - production verification now rejects target origins that resolve to non-public/private IP ranges
  - the website username validation now matches the CLI contract for 1-32 character public names
- This design keeps Vercel exposure low.
  - the website only handles redirect and registration requests
  - actual LibreChat, LiveKit signaling, media, and TURN traffic never flow through the website layer
- For the owner deployment, the preferred stable custom-domain layout is now:
  - `app.viventium.ai`
  - `api.app.viventium.ai`
  - `playground.app.viventium.ai`
  - `livekit.app.viventium.ai`
  - this keeps the primary public entrypoint on `app.viventium.ai` without consuming every
    top-level subdomain on `viventium.ai`

## Limitations

- The stable public-domain finish step was not live-validated yet because the required DNS records
  do not exist today.
  - `app.viventium.ai`
  - `api.app.viventium.ai`
  - `playground.app.viventium.ai`
  - `livekit.app.viventium.ai`
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
- The directory-layer rate limits are implemented in-process in the website app.
  - they are effective for the single-instance local validation performed here
  - they are not a full replacement for provider-level firewall/rate-limit controls when the website
    is publicly deployed on hosted infrastructure such as Vercel
- Directory entries are still write-verified, not continuously revalidated.
  - `lastVerifiedAt` is stored and indexed
  - this branch does not yet include a cron/TTL cleanup pass for dead or lapsed target origins
