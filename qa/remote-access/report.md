# Remote Access QA Report

## Date

- 2026-04-04

## Build Under Test

- Repo branch: `codex/remote-modern-playground-access`
- Nested LibreChat branch: `codex/remote-modern-playground-access`
- Runtime profile: `isolated`
- Live config used for secure-origin validation: `/tmp/viventium-remote-access-netbird.yaml`

## Checks Executed

1. Targeted root regression suite.
   - Command:
     `python3 -m pytest tests/release/test_preflight.py tests/release/test_config_compiler.py tests/release/test_remote_call_tunnel.py -q`
   - Result: `69 passed`
2. Launcher/script syntax validation.
   - Command:
     `bash -n viventium_v0_4/viventium-librechat-start.sh`
   - Result: passed
3. Python module syntax validation.
   - Command:
     `python3 -m py_compile scripts/viventium/preflight.py scripts/viventium/config_compiler.py scripts/viventium/remote_call_tunnel.py`
   - Result: passed
4. LibreChat public-origin call-launch regression tests.
   - Command:
     `npm run test:api -- --runInBand server/routes/viventium/__tests__/calls.spec.js`
   - Result: `8/8` tests passed
5. LibreChat frontend proxy-target regression tests.
   - Command:
     `npx jest --config client/jest.config.cjs --runInBand src/utils/devProxy.spec.ts`
   - Result: `8/8` tests passed
6. Live secure-origin NetBird-compatible browser/API validation.
   - Result: secure app login rendered over `https://app.10.88.111.46.sslip.io:4443/login`
   - Result: secure modern playground rendered over `https://playground.10.88.111.46.sslip.io:3443/`
   - Result: secure app API and banner endpoints returned `200`
7. Localhost regression validation.
   - Result: `http://127.0.0.1:3190/api/config` returned `200`
   - Result: `http://localhost:3300/` returned `200`
8. Provider-prerequisite preflight checks.
   - Result: Tailscale config reports manual attention because this Mac is not connected to a
     tailnet.
   - Result: NetBird config reports manual attention because this Mac does not have the NetBird
     client joined to a mesh.

## Findings

- The branch now supports both private-mesh modes structurally:
  - `tailscale_tailnet_https`
  - `netbird_selfhosted_mesh`
- The secure-origin NetBird-compatible path is working live on this Mac.
  - Caddy is listening on `4443`, `8443`, `3443`, and `7443`
  - `public-network.json` exposes the expected secure URLs plus `livekit_node_ip`
- The localhost path is preserved.
  - After enabling remote-access support, the local frontend proxy still serves `/api/config`
    successfully instead of regressing to `500`
- The key regression fixed in this pass was the frontend proxy boundary.
  - `DOMAIN_SERVER` must remain the browser-facing public API origin
  - the local Vite dev proxy must keep using a local backend target
  - the launcher now writes `VIVENTIUM_FRONTEND_PROXY_TARGET=http://localhost:3180`
  - the frontend resolver now prefers that explicit local proxy target instead of feeding the
    public HTTPS API origin back into Vite
- Browser QA evidence after the fix:
  - secure app page loaded with `0` browser errors and only one non-fatal React Router warning
  - secure playground loaded with `0` browser errors

## Limitations

- Tailscale was not provider-native live-validated end to end on this Mac.
  - `tailscale` CLI is installed, but the local Tailscale service is not running/connected, so the
    tailnet-only URLs could not be exercised in a real tailnet session here.
- NetBird was not provider-native live-validated end to end on this Mac.
  - this machine does not have the NetBird client joined to a self-hosted mesh
  - the live validation in this report proves the Viventium NetBird-mode contract through its
    secure-origin/Caddy/private-hostname behavior, not a real NetBird control-plane enrollment
- Caddy local trust remains manual by default.
  - the helper intentionally does not auto-elevate trust unless explicitly opted in
  - the generated `trust_note` must be followed on client devices that need browser trust without
    certificate prompts
