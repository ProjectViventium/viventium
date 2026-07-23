# 47. Remote Access and Tunneling

## Purpose

Define the supported ways a local Viventium install can be accessed securely from outside the home
network without breaking the default localhost development/runtime path.

This document is the source of truth for:

- `runtime.network.remote_call_mode`
- the browser-facing remote origins for local installs
- the launcher/runtime contract for private-mesh access
- the launcher/runtime contract for stable public-browser access from a self-hosted machine
- the supported and unsupported remote-access topologies

## User Setup Entry Points

Users configuring remote access should start here:

- `config.minimal.example.yaml`
- `config.full.example.yaml`
- `docs/05_ENVIRONMENT.md`
- this document for choosing the correct remote-access mode

Operator guidance:

- If you do not need remote access, leave `runtime.network.remote_call_mode: disabled`.
- If you only need your own enrolled devices to reach Viventium privately, choose
  `tailscale_tailnet_https`.
- If you need a stable public browser URL for arbitrary devices, choose `custom_domain`
  / `public_https_edge`.
- The easiest way to change modes later is `bin/viventium configure`. The wizard now asks where you
  need to use Viventium and, for remote installs, whether browser sign-up and browser password reset
  should stay enabled.
- After startup, run `bin/viventium status` to see the exact live outside URL that Viventium
  published for this machine.

## Product Position

The default public-safe local-install story remains:

- `remote_call_mode: disabled`
- localhost browser access for the web UI and modern playground
- explicit loopback listeners for app-facing services; a localhost URL alone is not proof of the
  bind address
- no implied support for raw LAN-IP voice access from another device

The modern Playground's Next process binds to `127.0.0.1` explicitly in every mode. Supported
remote modes publish it through their authenticated/trusted HTTPS ingress; they do not change the
underlying Next listener to `0.0.0.0` or `[::]`.

Remote access is a deliberate operator opt-in because browsers require trusted HTTPS/WSS origins,
and LiveKit media still needs a real network path for TCP/UDP beyond just an HTTP reverse proxy.

Viventium now supports three distinct shapes:

- local-only access
  - `disabled`
- private-device access for mesh-enrolled operator devices
  - `tailscale_tailnet_https`
  - `netbird_selfhosted_mesh`
- public-browser access for arbitrary internet devices
  - `public_https_edge`
  - `custom_domain` is a clearer alias for the same mode

Product position:

- Private mesh modes are not the final answer to "any browser anywhere."
- The stable bookmarkable public answer is `public_https_edge` with explicit custom domains.
- The automatic `sslip.io` hostnames are a zero-cost bootstrap fallback only. They are useful for
  proof and QA, but they are tied to the current public IP and therefore are not the durable
  operator-facing answer.
- `viventium.ai/u/<user>` or a similar discovery layer is allowed only as an optional
  redirect-only convenience. It must not become a shared relay for user traffic.
- Discovery and transport are separate concerns:
  - transport stays in the self-hosted runtime
  - discovery can live on the website
  - the website must never proxy chat, voice, or LiveKit media for self-hosted installs

Quick operator choice:

- leave remote access `disabled` if you only use Viventium locally
- use `tailscale_tailnet_https` if you want your own phone/laptop/tablet to reach Viventium and
  you are willing to install Tailscale on those devices
- use `custom_domain` when you want the app and modern playground reachable from any browser
  anywhere without installing a mesh client

Public-account safety:

- `runtime.auth.allow_registration` defaults to `true` so a brand-new local install can create its
  first real account
- when the wizard is configuring a remote install, it now asks explicitly whether browser sign-up
  and browser password reset should stay enabled
- once the install is reachable from outside your network, close registration unless you
  intentionally want public self-signup
- keep `runtime.auth.allow_password_reset: false` unless you have real email delivery configured
- for a one-time operator-issued reset link without opening the public browser reset endpoint, use:
  - `bin/viventium password-reset-link <email>`

## Supported Modes

### 1. `disabled`

Use this by default.

- Local browser sessions continue to use `localhost`
- Voice and modern playground behavior stay local-only
- No extra reverse proxy or mesh assumptions are introduced

### 2. `cloudflare_quick_tunnel`

Still supported as an explicit experiment only.

- Voice-surface only
- Publishes the modern playground and LiveKit signaling over Cloudflare quick tunnels
- Does not become the recommended general-purpose remote-access story for Viventium

Why it stays experimental:

- it only handles the browser-facing HTTP/WSS surfaces
- LiveKit media quality and reliability are weaker than real private-mesh or direct-network setups
- it is not the canonical path for the full Viventium browser surface

### 3. `tailscale_tailnet_https`

Recommended when the same operator just wants their own devices to reach Viventium privately.

Runtime contract:

- Viventium publishes tailnet-only HTTPS origins through `tailscale serve`
- the launcher exports:
  - `VIVENTIUM_PUBLIC_CLIENT_URL`
  - `VIVENTIUM_PUBLIC_SERVER_URL`
  - `VIVENTIUM_PUBLIC_PLAYGROUND_URL`
  - `VIVENTIUM_PUBLIC_LIVEKIT_URL`
  - `VIVENTIUM_PUBLIC_GLASSHIVE_URL` when GlassHive is enabled and a dedicated public origin is configured
- `LIVEKIT_NODE_IP` is derived automatically from the local node's Tailscale IPv4
- browser origins stay on the node's `*.ts.net` hostname rather than raw mesh IPs

Config contract:

- `runtime.network.remote_call_mode: tailscale_tailnet_https`
- `public_*` origins may be left blank for the automatic `*.ts.net` defaults
- if provided explicitly, the host must still match this node's Tailscale DNS name

Operational requirements:

- `tailscale` installed
- Tailscale daemon running on the Mac
- the Mac already signed in to the target tailnet before startup

User expectation:

- yes, this mode lets you use Viventium from your phone outside the local network
- the phone or tablet must also be enrolled in the same tailnet
- this is the easiest remote-access path when the operator only needs their own devices

Validation status:

- Config/compiler/preflight coverage exists.
- This branch has not yet performed a provider-native end-to-end validation on a real tailnet from
  this Mac.

### 4. `netbird_selfhosted_mesh`

Supported as the OSS self-hosted private-mesh path, with a deliberately narrower contract than a
full NetBird control-plane installer.

What this mode does:

- assumes the operator already has a NetBird mesh/client setup
- terminates browser-trusted HTTPS/WSS locally with Caddy
- publishes explicit mesh-private app/API/playground/LiveKit signaling origins
- preserves `localhost` behavior for localhost callers

What this mode does not do:

- it does not install or operate the NetBird management/control plane
- it does not enroll devices into the mesh for you
- it is not the final answer to public-browser access from arbitrary devices
- it is not a public-internet multi-user relay on `viventium.ai`

Config contract:

- `runtime.network.remote_call_mode: netbird_selfhosted_mesh`
- always required:
  - `runtime.network.public_client_origin`
  - `runtime.network.public_api_origin`
- also required when voice is enabled:
  - `runtime.network.public_playground_origin`
  - `runtime.network.public_livekit_url`
- optional but recommended when mesh DNS is not already resolving to this Mac correctly:
  - `runtime.network.livekit_node_ip`

Operational requirements:

- NetBird client/CLI installed and this Mac joined to the intended mesh
- `caddy` installed
- mesh hostnames or trusted host mappings already decided by the operator

TLS note:

- the current NetBird mode uses Caddy `tls internal`
- Viventium does not auto-elevate system trust by default because that can block startup on macOS
- operators can run `caddy trust --config <generated Caddyfile>` manually on the local Mac
- `VIVENTIUM_REMOTE_CALL_CADDY_AUTO_TRUST=true` is an explicit opt-in if the operator wants startup
  to attempt that trust step automatically
- other client devices must trust the same issuing CA, or the operator must adopt a certificate
  strategy compatible with their mesh/browser fleet

Validation status:

- The secure-origin Caddy/browser contract was validated locally.
- This branch has not yet performed a provider-native end-to-end validation on a real NetBird mesh
  from this Mac.

### 5. `public_https_edge` / `custom_domain`

Recommended when the operator wants a real public HTTPS/WSS entrypoint that arbitrary browsers can
reach without installing a mesh client.

Runtime contract:

- Viventium terminates browser-facing HTTPS with Caddy on the local machine.
- The launcher exports:
  - `VIVENTIUM_PUBLIC_CLIENT_URL`
  - `VIVENTIUM_PUBLIC_SERVER_URL`
  - `VIVENTIUM_PUBLIC_PLAYGROUND_URL`
  - `VIVENTIUM_PUBLIC_LIVEKIT_URL`
- `LIVEKIT_NODE_IP` defaults to the discovered LAN IPv4 for local-first installs. A direct public
  edge is not accepted for off-LAN calling while that private-only candidate remains active.
- Operators can set `runtime.network.livekit_node_ip` explicitly when they want LiveKit to
  advertise a public/mesh media address for direct TCP/UDP paths and have already validated that
  the local browser path still works in their network.
- When the public edge is active, the launcher also exports LiveKit TURN/TLS settings so the
  generated `livekit.yaml` can advertise a TURN domain and certificate pair.
- `api/connection-details` must return the public LiveKit URL only for requests that originated
  from the configured public playground origin. Localhost callers must keep `ws://localhost:7888`.

Config contract:

- `runtime.network.remote_call_mode: public_https_edge`
- `runtime.network.remote_call_mode: custom_domain`
- `runtime.network.remote_call_mode: custom_domain_public_edge`
- `runtime.network.remote_call_mode: public_custom_domain`
- blank `public_*` origins are allowed for the bootstrap `sslip.io` fallback
- stable bookmarkable access requires explicit values for:
  - `runtime.network.public_client_origin`
  - `runtime.network.public_api_origin`
  - `runtime.network.public_playground_origin`
  - `runtime.network.public_livekit_url`
- Official WhatsApp Business Cloud callbacks may reuse `runtime.network.public_api_origin`. An Easy
  Install administrator who operates an equivalent stable public edge may instead enter that API
  origin under **Settings > Channels > WhatsApp > Public Viventium HTTPS address**. Viventium
  validates a public HTTPS origin and generates the connection-specific callback path; the setting
  does not provision DNS, TLS, a tunnel, a Meta app, or provider approval.
- externally usable GlassHive workspace/artifact links additionally require:
  - `runtime.network.public_glasshive_origin`
  - the compiler-owned signed-link-only mode; the local GlassHive operator port must never be
    published without this boundary

Operational requirements:

- `caddy` installed
- router support for either:
  - UPnP / NAT-PMP auto-mapping, or
  - manual forwarding of `80/tcp`, `443/tcp`, LiveKit TCP media, LiveKit UDP media, and TURN/TLS
- if embedded TURN is relied on for acceptance, a bounded `turn.relay_range_start` /
  `turn.relay_range_end` and the matching forwarded UDP range; forwarding only the TURN/TLS
  listener does not expose the allocated relay candidates
- a public IPv4 path to this machine, or an operator-managed edge that forwards those ports
- for the durable public answer:
  - operator-owned DNS pointing the app/API/playground/LiveKit and optional GlassHive subdomains at
    the current public IP
- do not run a full-tunnel VPN on the same Mac that is serving the public edge unless the VPN is
  explicitly split-routed to keep the local LAN and the host's own public IP off the tunnel

Router lease note:

- some consumer routers grant UPnP port mappings with finite leases instead of permanent mappings
- Viventium now treats those mappings as renewable runtime state, not one-time setup
- the launcher keeps a lightweight background refresh worker alive for `public_https_edge` /
  `custom_domain` so leased mappings are renewed before they expire
- startup may reclaim stale UPnP mappings that already point back to this same Mac but no longer
  have a reachable local target; active conflicting mappings still remain a fatal operator-visible
  error instead of being silently hijacked
- if the router refuses a required mapping, or those public ports already belong to another LAN host,
  Viventium must keep the local install running and record the exact blocker in
  `public-network.json` for `bin/viventium status`
- the launcher must also persist a fallback `last_error` itself when the helper exits before writing
  failure state, so stale healthy mappings cannot survive into status or the refresh worker gate
- a failed remote-access attempt must clear only the public-edge exports. Local startup must restore
  a LAN-reachable `LIVEKIT_NODE_IP` before the local LiveKit path runs, so a blocked router mapping
  cannot take down localhost startup
- if the router does not support UPnP/NAT-PMP at all, or refuses renewal, manual forwarding is still
  the fallback

Hostname guidance:

- The recommended stable layout is unique subdomains per surface, for example:
  - `https://app.example.com`
  - `https://api.example.com`
  - `https://playground.example.com`
  - `wss://livekit.example.com`
  - `https://glasshive.example.com` when externally usable GlassHive links are enabled
- If you prefer to keep one visible namespace in front, choose an app hostname such as
  `app.example.com` and then derive:
  - `https://app.example.com`
  - `https://api.app.example.com`
  - `https://playground.app.example.com`
  - `wss://livekit.app.example.com`
  - `https://glasshive.app.example.com`

Same-network note:

- Public custom domains resolve to the router's public address. A phone on the same Wi-Fi can use
  those URLs only when the router supports NAT loopback/hairpinning (or split-horizon DNS sends the
  names back through an equivalent trusted HTTPS edge).
- A public link working over cellular while timing out on the same Wi-Fi is evidence of missing NAT
  loopback, not evidence that Caddy, public DNS, or the public edge is down.
- The immediate user test is to turn Wi-Fi off and use cellular. The durable LAN fix is router NAT
  loopback/split DNS, or a supported private-mesh mode such as Tailscale. Plain LAN HTTP is not a
  substitute for browser microphone, LiveKit WSS, or signed public-link security.
- The helper intentionally rejects reusing one hostname for different surface ports because that
  would blur routing ownership and create brittle mixed-surface assumptions.

Durability note:

- The auto-generated `sslip.io` hostnames are valid for bootstrap QA and emergency use.
- They are not the stable operator-facing story because the hostname changes when the public IP
  changes.
- If the operator already owns a domain, explicit subdomains on that domain are the sovereignty-
  first, zero-added-cost answer.

Operator recipe for a stable public link:

1. Create four voice/app DNS records that point at the current public IPv4 of the home network:
   - `app.<your-domain>`
   - `api.<your-domain>`
   - `playground.<your-domain>`
   - `livekit.<your-domain>`
   If GlassHive is enabled and its returned links must work externally, also create
   `glasshive.<your-domain>`.
2. Set explicit origins in `~/Library/Application Support/Viventium/config.yaml`:
   ```yaml
   runtime:
     network:
       remote_call_mode: custom_domain
       public_client_origin: "https://app.<your-domain>"
       public_api_origin: "https://api.<your-domain>"
       public_playground_origin: "https://playground.<your-domain>"
       public_livekit_url: "wss://livekit.<your-domain>"
       livekit_node_ip: "<public IPv4>" # direct-public media until dual-candidate config is exposed
       public_glasshive_origin: "https://glasshive.<your-domain>" # optional; GlassHive only
   ```
3. Ensure the router forwards `80/tcp`, `443/tcp`, `7889/tcp`, `7890/udp`, and `5349/tcp` to this
   Mac, or allow the helper to manage those mappings through UPnP/NAT-PMP. If TURN is part of the
   promised fallback, configure a bounded relay UDP range and forward that range too; `5349/tcp`
   alone is not a complete TURN media path.
4. Restart Viventium. The local Caddy edge will request real certificates for the configured
   hostnames, the launcher will republish those URLs back into the runtime, and leased UPnP
   mappings will be refreshed automatically while the runtime stays up.
5. Run `bin/viventium status` and copy the exact outside URL Viventium reports.
6. Validate from another device on a different network:
   - `https://app.<your-domain>` loads LibreChat
   - voice launch opens `https://playground.<your-domain>`
   - the call completes a real round-trip
   - do not treat a full-tunnel VPN running on the same host Mac as equivalent proof; use a
     separate device or disable the VPN on the serving host first

Temporary disable / re-enable recipe:

- If the Mac is away from the network/IP that the public domains route to, disable remote access
  instead of leaving stale public origins active:
  ```yaml
  runtime:
    network:
      remote_call_mode: disabled
      public_client_origin: ""
      public_api_origin: ""
      public_playground_origin: ""
      public_livekit_url: ""
  ```
- Keep the intended custom-domain values in operator notes or YAML comments, not as active
  `public_*` fields, while remote access is disabled.
- Re-enable when the Mac is back on the routed network:
  1. Set `runtime.network.remote_call_mode: custom_domain`.
  2. Restore the saved `public_client_origin`, `public_api_origin`,
     `public_playground_origin`, and `public_livekit_url`.
  3. Restart with `bin/viventium restart` or `bin/viventium stop && bin/viventium start`.
  4. Run `bin/viventium status`.
  5. Validate from a separate off-home network before treating public voice as ready.

User expectation:

- yes, this mode is the one that lets you use Viventium and the modern playground from a phone
  outside the local network without installing a mesh client
- because the browser is public and unmodified, this is also the right mode for sharing your
  self-hosted Viventium with other people

Recommended stable record pattern:

- `app.<your-domain>`
- `api.app.<your-domain>`
- `playground.app.<your-domain>`
- `livekit.app.<your-domain>`

That keeps the user-facing primary URL on `app.<your-domain>` while avoiding collisions with other
top-level properties that may already exist on the same domain.

Learnings from public-edge validation:

- Some consumer routers issue finite UPnP/NAT-PMP leases instead of permanent mappings.
- Viventium now treats those mappings as renewable runtime state and keeps a refresh worker alive
  while the public edge is running.
- If the router drops or refuses renewal, the operator fallback is still manual forwarding of the
  required ports.
- A full-tunnel VPN running on the serving Mac can invalidate same-machine "outside network" tests
  even while real outside devices still work.
- A full-tunnel VPN can also break outbound AI-provider traffic from the local runtime. Groq may
  reject some VPN egress IPs with `403 Access denied`; if activation checks fail only while the VPN
  is enabled, split-tunnel Groq/API-provider traffic or disable the VPN before treating the issue as
  a model, prompt, or runtime bug.
- The runtime-owned `public-network.json` file is the source of truth for the live outside URL, the
  current public IP, and the current mapping lease state after startup.
- That state file must fail closed: any startup-time helper failure must leave an explicit `last_error`
  instead of reusing a stale healthy mapping snapshot from an earlier run.

## Public-Media Decision And Synthetic Lab Contract

The April and May network behaviors describe different supported cases rather than a single rule
that should overwrite the other:

- The LAN-address default remains correct for local-first installs, localhost callers, and private
  networks where clients can reach the host directly.
- An arbitrary off-LAN browser using `public_https_edge` is a separate case. It needs a reachable
  public LiveKit media candidate or a proven relay path; a private-only candidate cannot satisfy
  that product promise.
- The config-only recovery for an already deployed direct-public edge is an explicit public
  `runtime.network.livekit_node_ip`, followed by compile and restart. Generated runtime files are
  evidence, not the authoring surface.
- The prior assumption that advertised TURN/TLS was sufficient fallback was documentation and QA
  drift. A TLS listener and relay-candidate allocation do not prove media unless the allocated relay
  range is reachable and the browser selects a relay pair.
- A public hostname that works off-LAN but times out on the serving Wi-Fi is a separate router
  hairpin/split-DNS topology issue. It must not be misreported as either a dead public edge or a
  completed same-Wi-Fi fix.

Product, development, and operations consequences:

- The public-call promise covers usable media and a delivered voice turn, not merely a public page,
  certificate, signaling session, or listening port.
- A direct-public recovery may stay config-only and preserve the self-hosted deployment shape, but
  it is not accepted until an isolated lab browser selects the intended media path and the worker
  receives the synthetic fixture.
- An explicit public node address creates an operator maintenance obligation when the public IP
  changes. DNS and canonical config must be updated, recompiled, restarted, and revalidated.
- Any future change to the compiler, launcher, LiveKit generation, public origins, router mappings,
  Telegram call links, modern playground, or voice gateway is inside this regression's blast radius
  and must rerun `REMOTE-004` and `MPV-023`.

Prioritized hardening, separate from the config-only incident recovery:

1. Expose the official dual internal/external LiveKit candidate fields through canonical config and
   the compiler so local and public routes do not depend on a single advertised address.
2. If TURN remains a product fallback, expose a bounded relay UDP range, map it through the router,
   and require a selected relay pair in acceptance.
3. Provide or document a trusted same-Wi-Fi route through router NAT loopback, split-horizon DNS plus
   HTTPS, or a supported private mesh. Do not weaken the browser security boundary with plain LAN
   HTTP.

## Directory Discovery Layer

The optional website discovery layer exists to make public self-hosted installs easier to find
without sacrificing sovereignty.

Supported shape:

- `https://viventium.ai/u/<username>` returns an HTTP redirect to the user's own public
  `public_client_origin`
- once the redirect happens, all chat, voice, API, LiveKit, and TURN traffic go directly to the
  user's self-hosted machine
- `viventium.ai` is therefore a phonebook, not a relay

Security and abuse constraints:

- only verified `https://` Viventium client origins may be registered
- the target origin must expose `/.well-known/viventium-instance.json`
- registration is accepted only when the local instance signs the registration payload with the
  instance private key and the website verifies that signature against the public key in the
  well-known document
- registration must be rate-limited with shared hosted state and return a short `Retry-After`
  contract when throttled
- redirect targets must come only from the verified registry table; no arbitrary redirect passthrough
- the redirect route itself may be cached briefly and separately rate-limited, but it must remain a
  plain redirect rather than a fetch/proxy layer
- verification fetches should stay direct, refuse redirect chains, and use a short timeout so the
  directory cannot be turned into an expensive generic fetcher
- the hosted directory verifier must reject target origins that resolve to private, loopback,
  link-local, or otherwise non-public IP ranges
- local/private target registration is allowed only as an explicit QA/development override via
  `VIVENTIUM_DIRECTORY_ALLOW_PRIVATE_TARGETS=true`; it must not be the default behavior
- if the website is deployed on Vercel or another hosted edge, platform firewall/rate-limit
  controls are recommended as defense in depth, but the product-level safety contract must still
  hold without proxying user traffic
- the public runtime-to-directory handoff must be verifiable through the actual Caddy-served
  `/.well-known/viventium-instance.json` path, not only through synthetic side servers

Operator contract:

1. Start Viventium with a public remote-access mode so the client origin and well-known verification
   document are live.
2. Run:
   ```bash
   bin/viventium register-link <username>
   ```
3. The website verifies the instance and stores `username -> public_client_origin`.
4. `https://viventium.ai/u/<username>` becomes a stable discovery URL that redirects to the real
   self-hosted app.

Where users should look for configuration help:

- `config.minimal.example.yaml`
- `config.full.example.yaml`
- `docs/05_ENVIRONMENT.md`
- this document for the full remote-access topology and acceptance contract

Recommended operator verification checklist:

1. Open the configured app URL from another network.
2. Log in and confirm LibreChat loads.
3. Start a voice call.
4. Confirm the browser opens the configured modern playground URL.
5. Toggle transcript and send a typed test message.
6. Confirm a real assistant reply appears.
7. Complete a short spoken round-trip and confirm audio works both ways.
8. Only after the public client origin is working, optionally run `bin/viventium register-link <username>`.

Non-goals:

- no shared `viventium.ai/app/<username>` reverse proxy
- no shared relay of LiveKit signaling or media
- no attempt to make path-based single-host self-hosting look like a trivial tweak to the current
  transport runtime

## Owning Runtime Path

The supported flow is:

1. canonical config
   - `~/Library/Application Support/Viventium/config.yaml`
2. config compiler
   - exports remote-mode env and browser-facing origins
3. launcher
   - prepares the remote access topology before services start
   - exports the resolved public origins back into the runtime
   - keeps the local frontend dev proxy pointed at the local LibreChat backend instead of feeding
     the public browser-facing API origin back into Vite
4. remote access helper
   - provisions/reuses the selected remote-access provider
   - saves machine-local state in the runtime state directory
   - for `public_https_edge`, also manages router mappings and Caddy certificate state
5. LibreChat call launch
   - returns public playground links only for requests that actually came from configured public
     browser origins
6. modern playground / LiveKit
   - use the secure browser origin for signaling
   - use the mesh-reachable or public `LIVEKIT_NODE_IP` for media
   - advertise TURN/TLS details when remote public access is enabled

## Browser-Origin Safety Contract

Localhost must remain safe and unchanged.

The runtime must not blindly trust arbitrary request hosts and turn them into public playground
links.

Current contract:

- only requests whose browser origin matches the configured public client/API origins receive the
  public playground URL
- only requests whose browser origin matches the configured public playground origin receive the
  public LiveKit WSS URL from `api/connection-details`
- localhost callers still receive the localhost playground URL
- the browser-facing public API origin must stay separate from the local frontend dev proxy target,
  so secure-origin launches do not proxy back into their own public HTTPS edge
- this avoids turning `Host` header spoofing into an open redirect or accidental public-link switch

## LiveKit Network Truth

The remote helper solves the browser-facing app/API/playground/LiveKit signaling surfaces, but the
media path still matters separately.

LiveKit media is still separate:

- signaling uses `VIVENTIUM_PUBLIC_LIVEKIT_URL`
- media uses the node address advertised by `LIVEKIT_NODE_IP`
- the local-first default advertises the LAN address; explicit operator overrides can advertise a
  mesh/public address when the target browser network can reach it
- the private mesh or public network path must still allow the LiveKit TCP/UDP media ports, or the
  TURN/TLS fallback, to reach this Mac
- `public_https_edge` also advertises TURN/TLS, but a listening TLS port alone does not prove the
  fallback works: LiveKit's configured TURN relay UDP range must also be reachable through the
  router/firewall. Until that range is explicitly configured, forwarded, and tested, direct public
  LiveKit TCP/UDP is the required path rather than an assumed fallback.
- Off-LAN acceptance must prove a selected external ICE pair and delivered media/transcript. A
  public call page returning `200`, a successful signaling WebSocket, or a TURN/TLS certificate
  check is supporting evidence only.
- The preferred dual-network LiveKit shape is `rtc.use_external_ip: true` with
  `rtc.advertise_internal_ip: true`; behind a router without public-IP self-ping, also use
  `rtc.skip_external_ip_validation: true`. The runtime generator does not yet expose those fields,
  so the current config-only direct-public recovery uses an explicit public
  `runtime.network.livekit_node_ip` and records same-Wi-Fi NAT-loopback limitations separately.
- a single-IP zero-cost home deployment is still bounded by the operator's router, ISP, and egress
  policy; the strongest reliability comes from explicit custom domains plus forwarded LiveKit media
  and TURN ports

That is why the product does not frame plain HTTP tunnels as sufficient for the whole voice stack.
Private mesh access remains the easiest operator-owned answer for the operator's own devices, while
`public_https_edge` is the public-browser answer for a self-hosted machine.

## QA Contract

Remote-access acceptance lives in:

- `qa/remote-access/README.md`
- `qa/remote-access/cases.md`
- `qa/remote-access/report.md`
- `qa/modern-playground-voice/cases.md`

Minimum acceptance expectations:

- automated coverage for config compilation, preflight, and helper behavior
- localhost path remains intact
- public-origin call launch only activates for configured public origins
- at least one real secure-origin browser validation for the public-edge path
- at least one real voice-session QA proving the localhost path still works after remote access is
  enabled
- external public fetch proof for the public app or playground surface when `public_https_edge` is
  active, plus a selected off-LAN ICE pair, real worker join, delivered synthetic media/transcript,
  and targeted state cleanup under `REMOTE-004` / `MPV-023`
- a forced TURN mode that passes only when a relay pair is selected whenever TURN is claimed as a
  fallback
- same-Wi-Fi public-host access recorded independently from off-LAN acceptance so router hairpin or
  split-DNS gaps cannot be hidden by either result
- stable custom-domain validation when operator-controlled DNS is available
- directory registration only accepts verified HTTPS origins with valid signatures
- the directory redirect remains redirect-only, preserves query strings, and rejects unknown users
- rate-limit and throttling behavior for the directory layer are validated with real requests
- hosted-mode SSRF rejection for private/non-public targets is validated under production settings
- private-mesh validation must state clearly whether it is provider-compatible or provider-native
- Tailscale live validation when a real tailnet is available on the test machine

## Non-Goals

This document does not make `viventium.ai` a shared public relay for every user's local instance.

That is a separate architecture involving public DNS, public certificates, routing, identity, and
operator-controlled relay infrastructure. A redirect-only discovery layer can be designed
separately, but it must stay outside the transport/runtime modes defined here.
