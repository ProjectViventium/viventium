# Remote Access QA Report

## Date

- 2026-04-04
- 2026-04-05
- 2026-04-06
- 2026-04-07

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
   - Result: the 7 failures are mostly outside the direct directory/remote-access slice, but a
     subset still touches adjacent launcher and voice-surrounding surfaces:
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
     - local upstream server on `http://127.0.0.1:<ephemeral-port>`
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
22. Same-host full-tunnel VPN routing check.
   - Result:
     - with Windscribe enabled on the same Mac, the route to the host's own public IP resolved to a
       VPN `utun` interface instead of the normal LAN gateway
     - Caddy still showed genuine external requests from other public IPs reaching the custom-domain edge
   - Finding:
     - a full-tunnel VPN on the serving host is not a valid substitute for a separate off-network
       client when validating `public_https_edge`
23. Investigated real off-network failure after the custom-domain edge had previously passed local
    and external fetch checks.
   - Result:
     - the runtime state still advertised the expected public-edge mappings, but the live router
       table no longer contained them
     - manually re-adding `80/tcp`, `443/tcp`, `7889/tcp`, `7890/udp`, and `5349/tcp` immediately
       restored phone access to `app.<your-domain>`
     - the router granted those renewed mappings with finite lease times of roughly four hours
   - Finding:
     - the remaining public-edge reliability gap was leased UPnP mappings expiring after startup,
       not a broken app, broken DNS record, or broken Caddy config
24. Added renewable mapping support to the runtime helper and launcher.
   - Result:
     - `remote_call_tunnel.py refresh-mappings --state-file ...` now re-applies the saved public
       edge mappings and updates `router.last_refreshed_at`
     - the launcher now starts a background mapping-refresh worker for
       `public_https_edge` / `custom_domain`
     - targeted regression slice passed after the change:
       `python3 -m pytest tests/release/test_directory_link.py tests/release/test_remote_call_tunnel.py tests/release/test_config_compiler.py tests/release/test_preflight.py -q`
       => `88 passed`
   - Finding:
     - the public-edge implementation now matches real home-router behavior more closely because it
       treats UPnP mappings as leased state that may need renewal during a long-running session
25. Installer and status UX follow-up validation.
   - Result:
     - the wizard now lets a user choose remote access in plain language and, when remote access is
       enabled, explicitly choose whether browser sign-up and browser password reset should stay
       enabled
     - the updated release slice passed:
       `python3 -m pytest tests/release/test_wizard.py tests/release/test_install_summary.py tests/release/test_config_compiler.py tests/release/test_preflight.py tests/release/test_directory_link.py tests/release/test_remote_call_tunnel.py -q`
       => `117 passed`
     - `bin/viventium status` now showed:
       - `Remote Access: Running`
       - `Account Sign-up: Closed`
       - `Password Reset: Disabled`
26. Local operator auth-hardening validation on the live custom-domain install.
   - Result:
     - canonical App Support config now sets:
       - `runtime.auth.allow_registration: false`
       - `runtime.auth.allow_password_reset: false`
     - Playwright on `http://localhost:3190/login` showed the login page without the browser
       `Sign up` link after restart
     - `bin/viventium password-reset-link <email>` generated a one-time local operator link while
       leaving the public browser reset path disabled by default
     - `GET /api/viventium/auth/password-reset?...` returned `200` locally for the issued link
       without requiring public password-reset enablement
27. Public custom-domain reachability sanity check after the auth-hardening restart.
   - Result:
     - localhost checks returned `200` for:
       - `http://localhost:3190`
       - `http://localhost:3300`
     - an independent web fetch reached `https://playground.app.<your-domain>/` over HTTPS after
       the restart
   - Finding:
     - the auth-hardening restart preserved the public browser edge while closing public sign-up on
       the running install
25. Added canonical auth controls, a clearer remote-access setup path, and live status reporting.
   - Result:
     - `runtime.auth.allow_registration` and `runtime.auth.allow_password_reset` now compile from
       canonical `config.yaml` into the generated runtime env
     - the installer/configure flow now asks remote-access questions in plain language instead of
       requiring manual YAML edits just to discover the supported modes
     - if an operator enters `app.example.com`, the wizard derives:
       - `https://app.example.com`
       - `https://api.app.example.com`
       - `https://playground.app.example.com`
       - `wss://livekit.app.example.com`
     - `bin/viventium status` now reports:
       - the actual live outside URL from `public-network.json` when remote access is active
       - whether browser sign-up is open or closed
       - whether browser password reset is enabled or intentionally disabled
     - targeted regression slice passed after these changes:
       `python3 -m pytest tests/release/test_wizard.py tests/release/test_install_summary.py tests/release/test_config_compiler.py tests/release/test_preflight.py tests/release/test_directory_link.py tests/release/test_remote_call_tunnel.py -q`
       => `116 passed`
   - Finding:
     - remote access and browser-auth posture are now owned by canonical config plus a single
       operator-facing status surface, which reduces ambiguity for new installs and new machines
26. Added and live-validated an operator-only local password-reset-link flow for public installs.
   - Result:
     - the live personal config compiled to:
       - `ALLOW_REGISTRATION=false`
       - `ALLOW_PASSWORD_RESET=false`
     - `bin/viventium password-reset-link <email>` now:
       - recompiles runtime files
       - loads the generated LibreChat runtime env
       - connects to the live local MongoDB
       - returns a short-lived password reset URL without opening the public browser reset flow
     - local GET validation against
       `http://localhost:3180/api/viventium/auth/password-reset?...`
       returned `200 text/html`
     - targeted LibreChat regression slice passed:
       `npx jest --config jest.config.js --runInBand server/routes/viventium/__tests__/auth.spec.js server/services/viventium/__tests__/localPasswordResetService.spec.js`
       => `2 passed suites`, `7 passed tests`
   - Finding:
     - public installs can now keep browser sign-up closed and browser password reset disabled
       without losing a safe operator recovery path

## Findings

- The branch now supports both private-mesh modes structurally:
  - `tailscale_tailnet_https`
  - `netbird_selfhosted_mesh`
- The real public-browser-capable mode in this repo is `public_https_edge`.
  - It is live on this Mac with Caddy-managed HTTPS, router mappings, and TURN/TLS-ready LiveKit
    state.
- The key reliability fix in the latest pass was UPnP lease renewal.
  - some home routers expire the mapped public ports after a few hours even though the runtime
    itself is still healthy
  - manually restoring those mappings immediately restored real phone access
  - the runtime now includes a mapping refresh path and launcher worker so leased mappings do not
    silently expire during normal operation
- The localhost path is preserved even after enabling the remote edge.
  - chat still works on `localhost`
  - a fresh voice launch still works on `localhost`
  - the modern playground transcript path still returns a real model reply
- A full-tunnel VPN on the same Mac is not a clean external QA method for `public_https_edge`.
  - it can route the host's own public IP back through the VPN tunnel instead of the normal home
    gateway
  - separate-device or VPN-off testing is required before drawing conclusions from failures there
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
  - a real off-home phone browser load was restored after renewing the router mappings
  - the remaining acceptance gate is now a true off-home authenticated chat and voice round-trip
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
- New installs no longer need to discover remote access by reading raw YAML first.
  - the wizard now offers:
    - local only
    - my own phone/laptop
    - any browser anywhere
  - if the operator chooses a custom public hostname, the host family is derived automatically
- Public browser exposure and browser auth posture are now easier to reason about.
  - `bin/viventium status` is the single operator-facing place to read:
    - the live outside URL
    - whether sign-up is open or closed
    - whether password reset is enabled or intentionally disabled
  - the documented safe public posture is:
    - `allow_registration: false` after onboarding
    - `allow_password_reset: false`
    - `bin/viventium password-reset-link <email>` when a one-time reset is needed

## Limitations

- This report now includes proof that an off-home phone browser could load `https://app.<your-domain>`
  after the router mappings were renewed, but it still does not include a full authenticated chat and
  voice round-trip on that off-home device.
- This Mac cannot hairpin cleanly to its own public custom-domain hosts with local `curl`/Playwright,
  so same-machine public URL timeouts are not treated as definitive production failures.
- Tailscale was not provider-native live-validated end to end on this Mac.
  - `tailscale` CLI is installed, but the local Tailscale service is not running/connected, so the
    tailnet-only URLs could not be exercised in a real tailnet session here.
- NetBird was not provider-native live-validated end to end on this Mac.
  - this machine does not currently have the NetBird client installed or joined to a self-hosted mesh
- The final public-browser acceptance gate still requires a real off-home authenticated chat plus a
  real voice round-trip on a separate device.
  - this report now includes stronger supporting proof for the public edge itself:
    - external fetch success on the public app/playground hosts
    - real off-home phone browser load restored after renewing the router mappings
    - local Caddy host-routed `200` checks for app, playground, and well-known identity
  - but it still does not replace a true remote voice conversation from a separate device
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
