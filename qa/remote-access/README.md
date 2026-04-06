# Remote Access QA

## Purpose

Verify that Viventium's remote-access modes work without breaking the existing localhost path, with
honest separation between:

- private-mesh access for an operator's own enrolled devices
- public-browser access through the public HTTPS edge
- what this machine could validate live versus what still depends on provider runtime state or
  operator-controlled DNS

## Acceptance Contract

- Localhost app/API/playground behavior remains healthy after enabling remote-access support in the
  product code.
- Public-origin call launch stays gated to configured public origins only; localhost callers keep
  localhost playground links.
- `api/connection-details` must preserve the localhost LiveKit URL for localhost callers while
  returning the public LiveKit WSS URL for configured public playground origins.
- `netbird_selfhosted_mesh` can publish secure app/API/playground/LiveKit signaling origins through
  the local Caddy edge and serve those pages successfully over HTTPS.
- `public_https_edge` can publish secure app/API/playground/LiveKit signaling origins through the
  local Caddy edge, expose the required router mappings, and generate TURN/TLS-ready LiveKit state.
- Secure-origin browser access does not break the local Vite dev proxy path when `DOMAIN_SERVER`
  becomes a public API origin.
- A fresh local voice session still connects, opens transcript mode, and returns a typed assistant
  reply after remote access is enabled.
- When `public_https_edge` is active, an external fetch path can retrieve at least the public app or
  public playground surface over HTTPS.
- Preflight clearly explains missing provider prerequisites instead of failing silently:
  - NetBird client not installed/joined
  - Tailscale daemon/tailnet not connected
  - Caddy or router-mapping tools missing for `public_https_edge`
- QA must distinguish provider-compatible validation from provider-native end-to-end validation.
- Stable bookmarkable public access is not considered fully accepted until the operator-controlled
  custom-domain path has been validated or explicitly called out as the remaining external blocker.

## Public-Safe Evidence

- Root remote-access regression tests:
  - `tests/release/test_preflight.py`
  - `tests/release/test_config_compiler.py`
  - `tests/release/test_remote_call_tunnel.py`
- LibreChat regression tests:
  - `viventium_v0_4/LibreChat/api/server/routes/viventium/__tests__/calls.spec.js`
  - `viventium_v0_4/LibreChat/client/src/utils/devProxy.spec.ts`
- Runtime helper state:
  - `~/Library/Application Support/Viventium/state/runtime/isolated/public-network.json`
- Remote Caddy log:
  - `~/Library/Application Support/Viventium/state/runtime/isolated/logs/remote-call-netbird-caddy.log`
  - `~/Library/Application Support/Viventium/state/runtime/isolated/logs/remote-call-public-caddy.log`
- Generated LiveKit runtime config:
  - `~/Library/Application Support/Viventium/state/runtime/isolated/livekit/livekit.yaml`
- Local Playwright artifacts:
  - `output/playwright/remote-access/`
  - `.playwright-cli/`
  - Keep browser artifacts local-only because they can include authenticated or machine-local state.

## Verification Steps

1. Start the isolated stack on the feature branch with the remote-access config under test.
2. Confirm listeners exist for local services and secure mesh-facing ports.
3. Verify localhost app/API/playground health.
4. Verify the localhost-vs-public call-launch and `connection-details` origin split.
5. Verify secure-origin app/API/playground health through the remote edge under test.
6. Run browser QA against the local chat and modern-playground voice flow after remote access is enabled.
7. Run targeted automated regression tests for helper/preflight/call-launch/proxy behavior.
8. Run preflight for Tailscale, NetBird, and public-edge configs and record any required manual attention.
9. If `public_https_edge` is active, capture at least one non-local fetch proof of the public app or
   playground surface.
10. If stable custom-domain DNS is not yet delegated, record that as the remaining external operator action
    instead of overstating acceptance.
