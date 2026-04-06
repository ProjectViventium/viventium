# Remote Access QA Report

## Date

- 2026-04-04
- 2026-04-05
- 2026-04-06

## Build Under Test

- Repo branch: `codex/remote-modern-playground-access`
- Nested LibreChat branch: `codex/remote-modern-playground-access`
- Runtime profile: `isolated`
- Live config used for public-edge validation:
  - canonical App Support `config.yaml`
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
   - Result: `Origin: https://playground.<public-bootstrap-host>` returned
     `serverUrl=wss://livekit.<public-bootstrap-host>`
4. Live public-edge runtime validation.
   - Result: launcher reached `All Services Running`
   - Result: runtime state published:
     - `https://app.<public-bootstrap-host>`
     - `https://api.<public-bootstrap-host>`
     - `https://playground.<public-bootstrap-host>`
     - `wss://livekit.<public-bootstrap-host>`
   - Result: router mappings included `80/tcp`, `443/tcp`, `7889/tcp`, `7890/udp`, `5349/tcp`
5. LiveKit TURN/TLS runtime validation.
   - Result: generated `livekit.yaml` contained:
     - `turn.enabled: true`
     - `domain: livekit.<public-bootstrap-host>`
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
   - Result: independent external fetch reached `https://playground.<public-bootstrap-host>/`
     and returned HTML for the modern playground shell
8. Provider-prerequisite checks.
   - Result: Tailscale CLI is installed but not running/authenticated on this Mac
   - Result: NetBird CLI is not installed on this Mac
9. Directory-helper regression tests.
   - Command:
     `python3 -m pytest tests/release/test_directory_link.py tests/release/test_remote_call_tunnel.py -q`
   - Result: `19 passed`
10. Website directory layer static validation.
   - Commands:
     - `pnpm --dir <website-repo> --filter @workspace/database generate`
     - `pnpm --dir <website-repo> --filter marketing lint`
     - `pnpm --dir <website-repo> --filter marketing typecheck`
   - Result: passed
11. Local signed directory registration.
   - Setup:
     - synthetic HTTPS Viventium target on `https://localhost:44443`
     - local website dev server on `http://localhost:<directory-dev-port>`
     - isolated Postgres container for website directory state
   - Command:
     `NODE_TLS_REJECT_UNAUTHORIZED=0 python3 scripts/viventium/directory_link.py --state-file /tmp/viv-directory-qa/public-network.json --username qa-alice --directory-base-url http://localhost:<directory-dev-port>`
   - Result:
     - success JSON returned with the expected username, target origin, and vanity URL
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
14. Expanded release-suite validation.
   - Command:
     `python3 -m pytest tests/release/ -q`
   - Result: `192 passed, 7 failed`
   - Result: the 7 failures are outside the directory/remote-access slice and match current
     unrelated repo drift:
     - background-agent governance docs
     - detached LibreChat supervision contract
     - local Firecrawl compose defaults
     - native stack LiveKit helper contract
     - voice playground dispatch contract
15. Real wrapper UX validation.
   - Command:
     `VIVENTIUM_PUBLIC_NETWORK_STATE_FILE=/tmp/viv-directory-qa/public-network.json NODE_TLS_REJECT_UNAUTHORIZED=0 bin/viventium register-link qa-alice --directory-base-url http://localhost:<directory-dev-port>`
   - Result: positional CLI syntax worked and returned success JSON through the real shell wrapper
16. Shared-state rate-limit validation.
   - Result: the website now persists rate-limit buckets in Postgres instead of per-process memory
   - Result: repeated wrapper registrations returned:
     - attempts `1-8` => success
     - attempts `9-10` => wrapper exit `1` with `{"error":"Too many requests. Please try again in a minute."}`
   - Result: database evidence from `ViventiumDirectoryRateLimitBucket` showed persisted bucket rows
     and request counts, proving shared-state throttling
17. Real Caddy-served well-known validation.
   - Setup:
     - local upstream server on `http://127.0.0.1:39190`
     - live Caddy process using the helper-generated directory document in its Caddyfile
   - Result:
     - `curl --resolve app.qa.test:40443:127.0.0.1 https://app.qa.test:40443/.well-known/viventium-instance.json -k`
       returned the runtime-generated Viventium JSON document
     - `curl --resolve app.qa.test:40443:127.0.0.1 https://app.qa.test:40443/ -k`
       still returned upstream content `upstream-ok`
   - Finding:
     - the earlier claim that public-edge Caddy keying was broken was not reproduced; the helper
       emits the well-known route correctly for the public-edge host key it actually uses
18. Hosted-mode SSRF validation.
   - Setup:
     - marketing app built and started in production mode on a local test port
   - Command:
     `VIVENTIUM_PUBLIC_NETWORK_STATE_FILE=/tmp/viv-directory-qa/public-network.json NODE_TLS_REJECT_UNAUTHORIZED=0 bin/viventium register-link qa-prod-ssrf --directory-base-url http://localhost:<directory-prod-port>`
   - Result:
     - command failed with `{"error":"Target origin must resolve to a public internet address."}`
     - this proves the private-IP verification guard is active in hosted/production mode
19. Explicit local-override validation.
   - Setup:
     - marketing app started on a local test port with
       `VIVENTIUM_DIRECTORY_ALLOW_PRIVATE_TARGETS=true`
   - Command:
     `VIVENTIUM_PUBLIC_NETWORK_STATE_FILE=/tmp/viv-directory-qa/public-network.json NODE_TLS_REJECT_UNAUTHORIZED=0 bin/viventium register-link qa-alice --directory-base-url http://localhost:<directory-dev-override-port>`
   - Result:
     - registration succeeded
     - this proves private-target registration is now an explicit QA-only override rather than a
       default non-production bypass
20. Live custom-domain activation.
   - Setup:
     - operator-controlled DNS delegated for:
       - `app.<your-domain>`
       - `api.app.<your-domain>`
       - `playground.app.<your-domain>`
       - `livekit.app.<your-domain>`
     - canonical App Support config switched to:
       - `runtime.network.remote_call_mode: custom_domain`
       - explicit `public_*` origins on the chosen `app.<your-domain>` host family
   - Result:
     - runtime published `public-network.json` for the custom-domain edge
     - Caddy obtained real Let's Encrypt certificates for all four custom domains
     - direct internal host-routed checks through the live Caddy edge returned `200` for:
       - `app.<your-domain>`
       - `api.app.<your-domain>`
       - `playground.app.<your-domain>`
     - the runtime-generated `/.well-known/viventium-instance.json` returned valid JSON through the live custom-domain edge
21. Browser and external reachability checks on the custom-domain edge.
   - Result:
     - Playwright on `http://localhost:3190` loaded the Viventium login page with `0` console errors
     - Playwright on `http://localhost:3300` loaded the modern playground shell
     - same-machine Playwright and `curl` attempts to `https://playground.app.<your-domain>` timed out
     - an off-box fetch service successfully retrieved `https://playground.app.<your-domain>/` over HTTPS
   - Finding:
     - the current evidence is consistent with NAT hairpin failure on the local machine, not a dead public deployment

## Findings

- The branch now supports both private-mesh modes structurally:
  - `tailscale_tailnet_https`
  - `netbird_selfhosted_mesh`
- The real public-browser-capable mode in this repo is `public_https_edge`.
  - It is live on this Mac with Caddy-managed HTTPS, router mappings, and TURN/TLS-ready LiveKit
    state.
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
- The bootstrap `sslip.io` edge was externally reachable before custom-domain cutover.
  - non-local fetch succeeded for the public playground shell during bootstrap validation
- Stable custom-domain access is the remaining operator-facing finish step.
  - the public edge first worked through `sslip.io`
  - the operator-controlled custom-domain edge is now live on:
    - `app.<your-domain>`
    - `api.app.<your-domain>`
    - `playground.app.<your-domain>`
    - `livekit.app.<your-domain>`
  - the remaining acceptance gate is now a true off-home authenticated browser session and voice call
- The redirect-only website directory layer now exists and is functioning locally.
  - the self-hosted runtime publishes a signed verification document at
    `/.well-known/viventium-instance.json`
  - `bin/viventium register-link <username>` now works through the documented positional CLI syntax
    and signs the registration with the local instance key
  - the website verifies the signature and target before saving `username -> public_client_origin`
  - `viventium.ai/u/<username>` can therefore stay a phonebook rather than a relay
- The current safety posture for the directory layer is materially better than a naive open redirect.
  - unknown usernames return `404`
  - tampered signatures are rejected
  - registration and redirect endpoints are rate-limited
  - throttled responses carry `Retry-After: 60`
  - verification fetches refuse redirect chains and time out quickly
  - production verification now rejects target origins that resolve to non-public/private IP ranges
  - local private-target registration is now opt-in via `VIVENTIUM_DIRECTORY_ALLOW_PRIVATE_TARGETS=true`
  - the website username validation now matches the CLI contract for 1-32 character public names
  - the rate-limit state now lives in the shared website database rather than per-process memory
- This design keeps Vercel exposure low.
  - the website only handles redirect and registration requests
  - actual LibreChat, LiveKit signaling, media, and TURN traffic never flow through the website layer
- The runtime-to-directory integration path is now proven at the Caddy layer too.
  - a live Caddy instance served the runtime-generated well-known document
  - normal non-well-known requests still flowed to the upstream app
- The preferred stable custom-domain layout is:
  - `app.<your-domain>`
  - `api.app.<your-domain>`
  - `playground.app.<your-domain>`
  - `livekit.app.<your-domain>`
  - this keeps the primary public entrypoint on `app.<your-domain>` without consuming every
    top-level subdomain on the operator's domain

## Limitations

- The operator custom-domain DNS can be delegated and the custom-domain runtime can be active, but this report
  still does not include a true off-home authenticated browser session on `https://app.<your-domain>`.
- This Mac cannot hairpin cleanly to its own public custom-domain hosts with local `curl`/Playwright,
  so same-machine public URL timeouts are not treated as definitive production failures.
- Tailscale was not provider-native live-validated end to end on this Mac.
  - `tailscale` CLI is installed, but the local Tailscale service is not running/connected, so the
    tailnet-only URLs could not be exercised in a real tailnet session here.
- NetBird was not provider-native live-validated end to end on this Mac.
  - this machine does not currently have the NetBird client installed or joined to a self-hosted mesh
- TURN/TLS is now wired and listening on `5349`, but this report did not include a true external
  phone-on-cellular voice run over the public edge.
  - the strongest proof collected here is:
    - external HTTPS fetch proof for the public playground
    - local successful voice session after remote-edge enablement
    - live custom-domain certificates and host-routed Caddy responses
    - correct origin-based public-vs-local LiveKit routing
 - The directory-layer rate limits now use the shared website database, which materially improves
   hosted correctness over the earlier in-memory prototype.
  - this removes the per-process cold-start reset issue for normal hosted multi-instance execution
  - provider-level firewall/rate-limit controls are still recommended as defense in depth, but they
    are no longer the only thing preventing hosted rate-limit bypass
- Directory entries are still write-verified, not continuously revalidated.
  - `lastVerifiedAt` is stored and indexed
  - this branch does not yet include a cron/TTL cleanup pass for dead or lapsed target origins
- Username recovery/release remains an operator policy question.
  - if an operator loses the local private key and needs to reclaim the same vanity name, this
    branch does not yet include an automated release or transfer workflow
