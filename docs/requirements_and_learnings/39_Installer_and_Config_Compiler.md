# 39. Installer and Config Compiler

## Purpose

This document is the public installer source of truth for the `./install.sh` and `bin/viventium`
paths, plus the generated-runtime boundary enforced by the config compiler.

## Owning Flow

1. `./install.sh` clones or refreshes the repo checkout, then execs `bin/viventium install`.
2. `bin/viventium install` owns the public first-run flow:
   - wizard/config selection
   - preflight prerequisite detection and install
   - component bootstrap
   - config compilation
   - doctor validation
   - helper install
   - detached local startup plus health wait
3. Generated runtime files are written under `~/Library/Application Support/Viventium/runtime/` and
   are outputs, not authoring surfaces.
4. LibreChat startup then re-seeds the built-in Viventium agents from the git-tracked/source-of-truth
   agents bundle:
   - `viventium_v0_4/viventium-librechat-start.sh`
   - `viventium_v0_4/LibreChat/scripts/viventium-seed-agents.js`
   - `viventium_v0_4/LibreChat/viventium/source_of_truth/local.viventium-agents.yaml`

## Installer UX Requirements

- The primary startup wait UI must stay honest:
  - elapsed time
  - current startup step
  - which required surfaces are still pending
- Interactive TTY installs may render a second, playful tagline line below the truthful status line.
- The playful line must never replace the real health/status line or hide an actual failure.
- Headless and non-interactive installs stay on plain repeated progress logs only.
- Installer copy must remain public-safe and hardcoded from product code:
  - no secrets
  - no personal data
  - no machine-specific jokes or runtime-derived private state
- Animation contract for the playful line:
  - fast type-in effect
  - hold around five seconds once fully shown
  - rotate randomly
  - avoid immediately repeating the same line

## Config Compiler Boundary

- The config compiler still owns generated runtime artifacts such as:
  - `runtime.env`
  - `runtime.local.env`
  - `librechat.yaml`
- Human-facing browser auth posture must compile from canonical config too:
  - `runtime.auth.allow_registration` -> `ALLOW_REGISTRATION`
  - `runtime.auth.allow_password_reset` -> `ALLOW_PASSWORD_RESET`
- Generated runtime config must not silently preserve hidden provider defaults from the source
  template when the installer/compiler already knows the machine's real auth surface.
- `librechat.yaml` memory-writer provider/model must be compiled from the actually available
  foundation providers (`openai` / `anthropic`), including connected-account auth:
  - do not leave memory on a hardcoded xAI default when xAI was never configured
  - when both OpenAI and Anthropic are available, honor the configured foundation-provider order
    instead of silently preferring a different provider
- Endpoint helper config must not hide unavailable provider dependencies:
  - Anthropic conversation-title generation must stay on Anthropic instead of routing through xAI
- Built-in agent runtime truth must remain compatible with the selected install/runtime surface:
  - fresh installs and restarts rely on the seeded source-of-truth agent bundle
  - do not rely on Mongo hand-edits or App Support leftovers to make built-ins behave correctly
  - shipped Anthropic agents that intentionally use `temperature` must set `thinking: false`
    explicitly when Anthropic runtime defaults would otherwise enable thinking
- Installer UX affordances, including wait copy and inline animations, must not mutate or depend on
  generated App Support outputs to appear correct.

## Learnings

- First-run startup can honestly take minutes because local package builds and optional Docker sidecars
  are real work, especially on a clean machine.
- Playful wait copy is acceptable when the deterministic status path remains visible and reliable.
- Optional-sidecar readiness used by the launcher, install wait loop, and status must share the same
  contract. One path cannot hold the install open on a stricter probe than the runtime itself uses
  to declare the sidecar up.
- Interactive bootstrap paths can arrive with stdin still attached to a consumed pipe:
  - example: `curl .../install.sh | bash`
  - the CLI must reattach stdin from `/dev/tty` before wizard or preflight prompts
  - otherwise the first prompt sees EOF even though the user launched the install from a real terminal
- The right ownership layer for this feature is the public CLI wait loop in `bin/viventium`, not
  generated runtime files, LibreChat prompts, or machine-local App Support state.
- Remote access surfaced the same ownership rule again on April 7, 2026:
  - the wizard must own the human-facing remote-access choice in plain language
  - the config compiler must own the generated browser-auth/env posture
  - the runtime state file must own the exact live outside URL after startup
  - `bin/viventium status` / install summary must read that runtime state instead of making the
    operator reconstruct it manually
- Public remote access is optional and must never block local first run:
  - if router mappings or edge startup fail, local LibreChat/API/playground startup must continue
  - the remote access state file must persist the exact blocker so `bin/viventium status` can show
    an action-required message and the next `bin/viventium start` can retry cleanly
- Deferred Telegram startup must survive clean first-run build time:
  - LibreChat can spend several minutes rebuilding packages and the client bundle on a clean Mac
  - any Telegram startup path that waits inline against the API before those builds finish will
    produce a false skipped/stopped state for enabled installs
  - the launcher must retry Telegram in the background and expose that pending state through
    `bin/viventium status`
- The shipped macOS helper binary is the reliable clean-install path on April 7, 2026:
  - clean x86_64 CommandLineTools hosts can fail SwiftPM manifest linking before any app code builds
  - when `apps/macos/ViventiumHelper/prebuilt/source.sha256` matches current helper sources, the
    installer should use that shipped binary by default instead of surfacing brittle source-build
    failures to end users
- On April 5, 2026, a background-cortex failure showed why install/start ownership matters:
  built-in Anthropic agents are re-seeded from source-of-truth on startup, so fixing only live
  Mongo state or only a local runtime leftover would not align fresh installs or later restarts.
- On April 5, 2026, the memory-writer compile path exposed the same ownership rule from another
  angle: `local.librechat.yaml` still carried historical xAI defaults for `memory.agent` and the
  Anthropic endpoint `titleEndpoint/titleModel`, but the compiler never overlaid those fields. The
  correct fix was to compile those runtime surfaces from real configured provider availability, not
  to hand-edit App Support outputs or patch the memory runtime.
