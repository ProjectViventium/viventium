# Remote Access QA

## Purpose

Verify that Viventium's private-mesh remote-access modes work without breaking the existing
localhost path, with honest separation between what this machine could validate live and what still
depends on provider runtime state.

## Acceptance Contract

- Localhost app/API/playground behavior remains healthy after enabling remote-access support in the
  product code.
- Public-origin call launch stays gated to configured public origins only; localhost callers keep
  localhost playground links.
- `netbird_selfhosted_mesh` can publish secure app/API/playground/LiveKit signaling origins through
  the local Caddy edge and serve those pages successfully over HTTPS.
- Secure-origin browser access does not break the local Vite dev proxy path when `DOMAIN_SERVER`
  becomes a public API origin.
- Preflight clearly explains missing provider prerequisites instead of failing silently:
  - NetBird client not installed/joined
  - Tailscale daemon/tailnet not connected
- QA must distinguish provider-compatible validation from provider-native end-to-end validation.

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
- Local Playwright artifacts:
  - `output/playwright/remote-access/`
  - `.playwright-cli/`
  - Keep browser artifacts local-only because they can include authenticated or machine-local state.

## Verification Steps

1. Start the isolated stack on the feature branch with the remote-access config under test.
2. Confirm listeners exist for local services and secure mesh-facing ports.
3. Verify localhost app/API/playground health.
4. Verify secure-origin app/API/playground health through the remote edge.
5. Run browser QA against the secure app and secure playground.
6. Run targeted automated regression tests for helper/preflight/call-launch/proxy behavior.
7. Run preflight for both Tailscale and NetBird configs and record any required manual attention.
