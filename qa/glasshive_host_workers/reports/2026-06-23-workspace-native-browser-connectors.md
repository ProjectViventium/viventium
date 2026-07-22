# GlassHive Workspace Native Browser Connectors QA - 2026-06-23

<!-- qa-evidence-exempt: Historical implementation investigation retained as supporting evidence; it predates the complete user-path report format. -->

## Scope

This pass covers the GlassHive Docker workstation bootstrap for AI-worker browser connector
readiness. It is local-only and does not change LibreChat code, LibreChat images, cloud resources, or
user-facing warning UX.

Rules under test:

- `GH-WNBC-001` Less-Is-More Worker Delegation
- `GH-WNBC-002` Faithful Courier Capability Context
- `GH-WNBC-003` Additive Native Capability Projection
- `GH-WNBC-004` Browser/Computer Is Native Worker Surface
- `GH-WNBC-005` Isolated Workspace Bootstrap
- `GH-WNBC-006` No Residual Warning UX
- `GH-WNBC-007` User-Grade Native Capability QA

## Expected Result

A fresh workstation worker should install the Claude and Codex Chrome Web Store extensions, run the
native-host bootstrap before Chromium opens, and expose the selected worker CLI's real browser
connector without fake prompts or overfit task routing. If a vendor native-host bundle is not present,
the runtime should record that provisioning blocker truthfully instead of faking a connected state.

## Implementation Evidence

- Workstation default image moved to `workers-projects-runtime-workstation:phase1-node22-docs7`.
- Default worker CLIs moved to Codex CLI `0.142.0` and Claude Code `2.1.186`.
- `glasshive-browser-native-host-bootstrap` now runs before worker Chromium launch.
- Claude native messaging host is created in the worker home and executes `claude --chrome-native-host`.
- Codex native messaging host is created only when a real first-party Linux
  `extension-host/linux/<arch>/extension-host` bundle and reachable node-repl executable are
  provisioned through the documented worker-local paths. The bootstrap does not masquerade
  `codex app-server proxy` as a native messaging host.

## Automated Checks

- `runtime_phase1/tests/test_docker_sandbox.py -q`: PASS, 36 passed.
- `runtime_phase1/tests/test_profile_runtime.py -q`: PASS.
- `runtime_phase1/tests/test_mcp_server.py -q`: PASS.
- Docker image smoke: PASS for Codex CLI `0.142.0`, Claude Code `2.1.186`, Claude native host
  installed, browser extension policy installed.
- Bootstrap fixture tests: PASS for Claude manifest creation and Codex manifest/config creation when a
  fake first-party Linux bundle is present.

## User-Grade Browser QA

Fresh managed worker under the local Docker manager:

- noVNC health: PASS.
- Browser opened through GlassHive `desktop_action(browser)`: PASS.
- Playwright opened noVNC, captured snapshot/screenshot, and reported no console errors: PASS.
- Extension menu in remote Chromium showed both installed extensions: PASS.
- Profile install check after Chromium launch:
  - Claude extension: `profile-installed`.
  - Codex extension: `profile-installed`.
- Native host check:
  - Claude: `native-host-installed`; process list showed Chromium spawned `claude --chrome-native-host`.
  - Codex: `native-host-pending`; no first-party Linux native-host bundle was present.
- Visible popup check:
  - Codex popup reproduced `Disconnected`.
  - Claude popup opened its login/auth panel; the native host process evidence proved the extension
    reached the CLI bridge in the clean unauthenticated sandbox.

Temporary Playwright screenshots were inspected locally and not committed to the public QA report.

## Verdict

`GHHOST-006`: PASS/PARTIAL.

The local substrate fix is valid for Claude Code and for Codex when the real Codex Chrome native-host
bundle is provisioned. It also truthfully reproduces why Codex still shows `Disconnected` in a clean
Linux workstation today: the Chrome extension and CLI are installed, but the Codex Chrome plugin's
native-host binary is not present in the workstation image.

## Remaining Gap

Codex workstation browser connector requires explicit first-party provisioning before it can be
called connected in Linux workstation mode:

- a real Codex Chrome plugin native-host bundle for Linux,
- a reachable worker-local node-repl executable, and
- an agreed worker-local bundle location, either through documented environment keys or an image/home
  path.

The code now has a narrow config path for those inputs and regression coverage proving the
manifest/config materializes correctly when the prerequisites are visible to the worker launch
environment. Do not add warning banners, prompt routing, or fake bridge behavior as a workaround.
