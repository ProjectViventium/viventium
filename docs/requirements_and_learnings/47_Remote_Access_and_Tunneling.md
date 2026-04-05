# 47. Remote Access and Tunneling

## Purpose

Define the supported ways a local Viventium install can be accessed securely from outside the home
network without breaking the default localhost development/runtime path.

This document is the source of truth for:

- `runtime.network.remote_call_mode`
- the browser-facing remote origins for local installs
- the launcher/runtime contract for private-mesh access
- the supported and unsupported remote-access topologies

## Product Position

The default public-safe local-install story remains:

- `remote_call_mode: disabled`
- localhost browser access for the web UI and modern playground
- no implied support for raw LAN-IP voice access from another device

Remote access is a deliberate operator opt-in because browsers require trusted HTTPS/WSS origins,
and LiveKit media still needs a real network path for TCP/UDP beyond just an HTTP reverse proxy.

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
5. LibreChat call launch
   - returns public playground links only for requests that actually came from configured public
     browser origins
6. modern playground / LiveKit
   - use the secure browser origin for signaling
   - use the mesh-reachable `LIVEKIT_NODE_IP` for media

## Browser-Origin Safety Contract

Localhost must remain safe and unchanged.

The runtime must not blindly trust arbitrary request hosts and turn them into public playground
links.

Current contract:

- only requests whose browser origin matches the configured public client/API origins receive the
  public playground URL
- localhost callers still receive the localhost playground URL
- the browser-facing public API origin must stay separate from the local frontend dev proxy target,
  so secure-origin launches do not proxy back into their own public HTTPS edge
- this avoids turning `Host` header spoofing into an open redirect or accidental public-link switch

## LiveKit Network Truth

The remote helper only solves the browser-facing app/API/playground/LiveKit signaling surfaces.

LiveKit media is still separate:

- signaling uses `VIVENTIUM_PUBLIC_LIVEKIT_URL`
- media uses the node address advertised by `LIVEKIT_NODE_IP`
- the private mesh must still allow the LiveKit TCP/UDP media ports to reach this Mac

That is why the product treats private mesh VPN access as the reliable local-install answer and does
not frame plain HTTP tunnels as sufficient for the whole voice stack.

## QA Contract

Remote-access acceptance lives in:

- `qa/remote-access/README.md`
- `qa/remote-access/report.md`

Minimum acceptance expectations:

- automated coverage for config compilation, preflight, and helper behavior
- localhost path remains intact
- public-origin call launch only activates for configured public origins
- at least one real secure-origin browser validation for the NetBird-compatible path
- Tailscale live validation when a real tailnet is available on the test machine

## Non-Goals

This document does not make `viventium.ai` a shared public relay for every user's local instance.

That is a separate architecture involving public DNS, public certificates, routing, identity, and
operator-controlled relay infrastructure. It should be designed as its own feature rather than
blended into the private-mesh local-install modes.
