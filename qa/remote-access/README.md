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
- the optional `viventium.ai/u/<username>` directory layer only issues redirects to verified
  self-hosted origins; it must never proxy user app, API, or media traffic
- directory registration only succeeds for verified HTTPS targets with a matching signed payload and
  `/.well-known/viventium-instance.json`
- hosted directory verification rejects target origins that resolve to private or otherwise
  non-public network ranges
- local/private target registration for QA is only allowed when the website is started with
  `VIVENTIUM_DIRECTORY_ALLOW_PRIVATE_TARGETS=true`
- the directory redirect preserves query strings, returns `404` for unknown usernames, and returns
  `429` with throttling under burst traffic
- the directory throttling path must use shared state that survives hosted multi-instance execution;
  per-process-only limits are not sufficient for Vercel-style serverless deployment
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
- Directory registration CLI:
  - `scripts/viventium/directory_link.py`
- Website discovery layer in the sibling website repo:
  - `website/apps/marketing/app/api/viventium/directory/register/route.ts`
  - `website/apps/marketing/app/u/[username]/route.ts`
  - `website/apps/marketing/lib/viventium-directory.ts`
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
11. Start a safe local directory-test target that exposes `/.well-known/viventium-instance.json`.
12. Register that target through the real directory CLI and verify the website stores and redirects
    to the resolved origin.
13. Probe negative cases for the directory layer:
    - tampered signature
    - unknown username
    - burst traffic that must produce throttling
14. Fetch the runtime-generated `/.well-known/viventium-instance.json` through a live Caddy process,
    not only through a synthetic side server.
15. Validate the hosted-mode SSRF guard under `NODE_ENV=production` by attempting to register a
    private/loopback target and confirming rejection.
16. Record the full `tests/release/` result and clearly separate pre-existing unrelated failures
    from this feature slice.
