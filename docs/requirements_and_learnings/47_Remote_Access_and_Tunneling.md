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

## Product Position

The default public-safe local-install story remains:

- `remote_call_mode: disabled`
- localhost browser access for the web UI and modern playground
- no implied support for raw LAN-IP voice access from another device

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
- `LIVEKIT_NODE_IP` resolves to the discovered public IPv4 for direct TCP/UDP media paths.
- When the public edge is active, the launcher also exports LiveKit TURN/TLS settings so the
  generated `livekit.yaml` can advertise a TURN domain and certificate pair.
- `api/connection-details` must return the public LiveKit URL only for requests that originated
  from the configured public playground origin. Localhost callers must keep `ws://localhost:7888`.

Config contract:

- `runtime.network.remote_call_mode: public_https_edge`
- `runtime.network.remote_call_mode: custom_domain`
- blank `public_*` origins are allowed for the bootstrap `sslip.io` fallback
- stable bookmarkable access requires explicit values for:
  - `runtime.network.public_client_origin`
  - `runtime.network.public_api_origin`
  - `runtime.network.public_playground_origin`
  - `runtime.network.public_livekit_url`

Operational requirements:

- `caddy` installed
- router support for either:
  - UPnP / NAT-PMP auto-mapping, or
  - manual forwarding of `80/tcp`, `443/tcp`, LiveKit TCP media, LiveKit UDP media, and TURN/TLS
- a public IPv4 path to this machine, or an operator-managed edge that forwards those ports
- for the durable public answer:
  - operator-owned DNS pointing the app/API/playground/LiveKit subdomains at the current public IP

Hostname guidance:

- The recommended stable layout is unique subdomains per surface, for example:
  - `https://app.example.com`
  - `https://api.example.com`
  - `https://playground.example.com`
  - `wss://livekit.example.com`
- The helper intentionally rejects reusing one hostname for different surface ports because that
  would blur routing ownership and create brittle mixed-surface assumptions.

Durability note:

- The auto-generated `sslip.io` hostnames are valid for bootstrap QA and emergency use.
- They are not the stable operator-facing story because the hostname changes when the public IP
  changes.
- If the operator already owns a domain, explicit subdomains on that domain are the sovereignty-
  first, zero-added-cost answer.

Operator recipe for a stable public link:

1. Create four DNS records that point at the current public IPv4 of the home network:
   - `app.<your-domain>`
   - `api.<your-domain>`
   - `playground.<your-domain>`
   - `livekit.<your-domain>`
2. Set explicit origins in `~/Library/Application Support/Viventium/config.yaml`:
   ```yaml
   runtime:
     network:
       remote_call_mode: custom_domain
       public_client_origin: "https://app.<your-domain>"
       public_api_origin: "https://api.<your-domain>"
       public_playground_origin: "https://playground.<your-domain>"
       public_livekit_url: "wss://livekit.<your-domain>"
   ```
3. Ensure the router forwards `80/tcp`, `443/tcp`, `7889/tcp`, `7890/udp`, and `5349/tcp` to this
   Mac, or allow the helper to manage those mappings through UPnP/NAT-PMP.
4. Restart Viventium. The local Caddy edge will request real certificates for the configured
   hostnames and the launcher will republish those URLs back into the runtime.
5. Validate from another device on a different network:
   - `https://app.<your-domain>` loads LibreChat
   - voice launch opens `https://playground.<your-domain>`
   - the call completes a real round-trip

For the current owner deployment, the preferred stable records are:

- `app.viventium.ai`
- `api.app.viventium.ai`
- `playground.app.viventium.ai`
- `livekit.app.viventium.ai`

That keeps the user-facing primary URL on `app.viventium.ai` while avoiding collisions with other
top-level properties that may already live on `viventium.ai`.

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
- registration must be rate-limited and return a short `Retry-After` contract when throttled
- redirect targets must come only from the verified registry table; no arbitrary redirect passthrough
- the redirect route itself may be cached briefly and separately rate-limited, but it must remain a
  plain redirect rather than a fetch/proxy layer
- verification fetches should stay direct, refuse redirect chains, and use a short timeout so the
  directory cannot be turned into an expensive generic fetcher
- the hosted directory verifier must reject target origins that resolve to private, loopback,
  link-local, or otherwise non-public IP ranges
- if the website is deployed on Vercel or another hosted edge, platform firewall/rate-limit
  controls are recommended as defense in depth, but the product-level safety contract must still
  hold without proxying user traffic

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
- the private mesh or public network path must still allow the LiveKit TCP/UDP media ports to reach
  this Mac
- `public_https_edge` also advertises TURN/TLS so remote browsers have a standards-based TCP/TLS
  fallback when direct UDP is not available
- a single-IP zero-cost home deployment is still bounded by the operator's router, ISP, and egress
  policy; the strongest reliability comes from explicit custom domains plus forwarded LiveKit media
  and TURN ports

That is why the product does not frame plain HTTP tunnels as sufficient for the whole voice stack.
Private mesh access remains the easiest operator-owned answer for the operator's own devices, while
`public_https_edge` is the public-browser answer for a self-hosted machine.

## QA Contract

Remote-access acceptance lives in:

- `qa/remote-access/README.md`
- `qa/remote-access/report.md`

Minimum acceptance expectations:

- automated coverage for config compilation, preflight, and helper behavior
- localhost path remains intact
- public-origin call launch only activates for configured public origins
- at least one real secure-origin browser validation for the public-edge path
- at least one real voice-session QA proving the localhost path still works after remote access is
  enabled
- external public fetch proof for the public app or playground surface when `public_https_edge` is
  active
- stable custom-domain validation when operator-controlled DNS is available
- directory registration only accepts verified HTTPS origins with valid signatures
- the directory redirect remains redirect-only, preserves query strings, and rejects unknown users
- rate-limit and throttling behavior for the directory layer are validated with real requests
- private-mesh validation must state clearly whether it is provider-compatible or provider-native
- Tailscale live validation when a real tailnet is available on the test machine

## Non-Goals

This document does not make `viventium.ai` a shared public relay for every user's local instance.

That is a separate architecture involving public DNS, public certificates, routing, identity, and
operator-controlled relay infrastructure. A redirect-only discovery layer can be designed
separately, but it must stay outside the transport/runtime modes defined here.
