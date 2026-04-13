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
  - service-specific env files such as `runtime/service-env/telegram.config.env`
- Web search ownership is part of that same compiler contract:
  - the live switch is `integrations.web_search` in canonical App Support config
  - if that input is off or absent, generated runtime must disable `interface.webSearch`, omit the
    top-level `webSearch` block, and launcher env must keep `START_SEARXNG` / `START_FIRECRAWL`
    false
  - do not treat the tracked `viventium/source_of_truth/local.librechat.yaml` snapshot as the
    machine's live enablement state
- The config compiler also owns the retrieval embeddings contract compiled from
  `runtime.retrieval.embeddings`:
  - `EMBEDDINGS_PROVIDER`
  - `EMBEDDINGS_MODEL`
  - `OLLAMA_BASE_URL` when the configured provider uses Ollama
  - `VIVENTIUM_RAG_EMBEDDINGS_PROVIDER`
  - `VIVENTIUM_RAG_EMBEDDINGS_MODEL`
  - `VIVENTIUM_RAG_EMBEDDINGS_PROFILE`
- Human-facing browser auth posture must compile from canonical config too:
  - `runtime.auth.allow_registration` -> `ALLOW_REGISTRATION`
  - `runtime.auth.allow_password_reset` -> `ALLOW_PASSWORD_RESET`
- Generated runtime config must not silently preserve hidden provider defaults from the source
  template when the installer/compiler already knows the machine's real auth surface.
- `librechat.yaml` memory-writer provider/model must be compiled from the actually available
  foundation providers (`openai` / `anthropic`), including connected-account auth:
  - do not leave memory on a hardcoded xAI default when xAI was never configured
  - current product policy prefers Anthropic for memory when Anthropic is available and otherwise
    falls back to OpenAI
  - docs, tests, and generated runtime outputs must all reflect that exact compiler rule
  - the generated provider token is part of the public product contract; downstream runtime
    initialization must accept the compiler-emitted canonical value instead of requiring a
    different alias such as `openAI`
- Endpoint helper config must not hide unavailable provider dependencies:
  - Anthropic conversation-title generation must stay on Anthropic instead of routing through xAI
- Retrieval-runtime prerequisites must stay honest across install/start surfaces:
  - if conversation recall is configured to use Ollama embeddings, preflight, install summary,
    doctor, and launcher readiness must all surface the same local-runtime dependency
  - Docker being healthy is not enough when the selected embeddings runtime is down
  - Ollama binary presence is not enough when the selected embeddings model artifact is still
    missing on the configured Ollama host
  - the launcher must ensure the configured embeddings model exists before starting the RAG sidecar
  - doctor should report whether the configured model is already ready or will be pulled on first
    start
- Built-in agent runtime truth must remain compatible with the selected install/runtime surface:
  - fresh installs and restarts rely on the seeded source-of-truth agent bundle
  - do not rely on Mongo hand-edits or App Support leftovers to make built-ins behave correctly
  - shipped Anthropic agents that intentionally use `temperature` must set `thinking: false`
    explicitly when Anthropic runtime defaults would otherwise enable thinking
  - install summary, browser reminders, and setup docs must distinguish foundation-model auth
    from per-user workspace OAuth; a healthy activation path does not mean Gmail/Drive or
    Outlook/MS365 execution is ready for that user yet
  - local duplicate QA accounts do not automatically inherit another user's Google Workspace,
    Microsoft 365, or connected-model OAuth state; realistic live QA must reconnect or reseed those
    user-scoped credentials explicitly
  - optional MCP/runtime surfaces such as GlassHive must compile out cleanly when they are not
    enabled for the install or not actually present in the checked-out component set
  - seeded built-in agents must not keep dead GlassHive tool IDs on installs where
    `START_GLASSHIVE=false`, or fresh-user chat can fail before any real task begins
  - public checkout bootstrap must accept vendored component source trees that were shipped inside
    the reviewed repo export; installer correctness must not depend on nested `.git` metadata being
    present on end-user machines
- Installer UX affordances, including wait copy and inline animations, must not mutate or depend on
  generated App Support outputs to appear correct.
- Telegram launcher parity follows the same rule: compiled Telegram service env must be the default
  startup source ahead of legacy repo-local or private overlay files.
- Managed Telegram large-media mode follows the same rule:
  - canonical `integrations.telegram.local_bot_api` config compiles to generated Telegram service env
  - the launcher reads that generated env to decide whether it owns a local `telegram-bot-api` process
  - Telegram max media size comes from canonical config (`integrations.telegram.max_file_size_bytes`),
    not a shell-only or repo-local default
  - preflight must surface missing `telegram-bot-api` / `api_id` / `api_hash` before runtime start

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
- On April 8, 2026, a follow-up incident showed the other half of the same contract:
  the compiler correctly emitted `memory.agent.provider = openai`, but runtime provider resolution
  still rejected that generated value in one path with `Provider openai not supported`. The fix
  belongs at the shared runtime normalization/initialization boundary, not in App Support hand
  edits and not by changing the compiler back to a different alias.
- On April 12, 2026, local live QA showed the next runtime boundary clearly:
  classifier-first activation and fallback wiring can be fully healthy while the user-visible
  Outlook or Gmail task still waits on user-scoped connected-account OAuth. Install/status/setup
  guidance must tell users to connect both:
  - one foundation model account so the shipped agents can reason
  - the matching Google Workspace or Microsoft 365 account when they want those tool surfaces
- On April 12, 2026, voice-call QA exposed the install/bootstrap side of the same contract:
  - the main agent's fast voice route can be visibly active in runtime logs while still relying on
    inherited primary-model parameters if the seeded source-of-truth omits the dedicated voice bag
  - shipped Anthropic voice overrides must therefore seed `voice_llm_model_parameters.thinking:
    false` explicitly
  - seed/sync tooling must preserve that bag so fresh installs, local rebuilds, and reviewed syncs
    all keep the same low-latency voice defaults
- On April 12-13, 2026, a real remote clean-machine install on Intel macOS clarified the next
  installer/runtime boundaries:
  - `bin/viventium status` and install summary must not claim "ready" while core web surfaces are
    still warming up; fresh users read that heading literally
  - headless macOS CLI paths must sanitize unsupported locale defaults such as `C.UTF-8` so clean
    SSH-driven installs do not emit noisy Perl locale warnings
  - a fresh browser user on connected-account auth must get an actionable "connect your account"
    message, not the raw `No key found` fallback intended for direct API-key mode
  - registration success redirects must not update router state during render; even a harmless
    warning there makes a clean install look unstable during first-user onboarding
- On April 13, 2026, remote clean-machine onboarding exposed the next optional-service rule:
  - GlassHive is not part of the minimum public first-run contract
  - generated `librechat.yaml`, seeded built-in agent tools, and runtime MCP/tool loading must all
    agree when GlassHive is off
  - otherwise a missing local GlassHive MCP can surface to fresh users as a generic `No key found`
    error even though foundation-model auth is healthy
- The same April 13, 2026 remote clean-machine pass exposed the public-clone bootstrap boundary:
  - a shipped public checkout can contain vendored component source without nested git history
  - `bootstrap_components.py` must therefore treat a bootable vendored component tree as valid
    installer input instead of aborting with `Existing path is not a git repo`
- The same April 13, 2026 uninstall/reinstall pass clarified the destructive-cleanup boundary:
  - uninstall and factory reset must synchronously drain managed native services before deleting App
    Support state
  - helper-detached cleanup is acceptable for normal stop flows, but destructive removal cannot
    race the deletion of pid/config state needed to identify managed native services such as LiveKit
- The same April 13, 2026 remote clean-machine reinstall clarified two more first-user boundaries:
  - non-interactive/headless setup must not spam macOS Keychain write failures when the supported
    fallback is to keep secrets in machine-local config state
  - first-message auth aborts on a brand-new conversation must not queue title generation against a
    transient stream id; otherwise clean installs surface a misleading `/api/convos/gen_title/...`
    404 after the real `connected_account_required` error
- On April 9, 2026, a local restart verified the memory-writer contract end to end:
  - before restart, the live generated runtime still pointed memory at `openai / gpt-5.4` and the
    running helper logs showed the unsupported-provider initialization failure
  - after the compiler/runtime fix and restart, the generated runtime pointed memory at
    `anthropic / claude-sonnet-4-6`
  - the saved-memory path then ran through product code without manual App Support or Mongo edits
- On April 9, 2026, the same ownership rule extended to local-first conversation recall:
  - the compiler must emit the selected retrieval embeddings provider/model explicitly
  - wizard defaults, preflight, doctor, install summary, and launcher readiness must consume the
    same retrieval-config helper
  - the startup path must fail closed when recall depends on Ollama embeddings but Ollama is not
    actually reachable
- A later April 9, 2026 follow-up clarified the next layer of the same contract:
  - fresh local installs can have Ollama installed and reachable while still missing the configured
    embedding model artifact
  - launcher ownership therefore includes verifying/pulling the configured model before RAG startup
  - doctor ownership includes reporting model readiness instead of only binary presence
  - Ollama host responses can normalize untagged model requests to `:latest`, so readiness checks
    must accept that canonicalization rather than treating it as a false missing-model error
- On April 9, 2026, conversation-recall prompt propagation exposed the compile/source boundary:
  - compile-time source-of-truth precedence must be private curated YAML when present, otherwise the
    tracked `local.librechat.yaml`
  - the compiler must not seed itself from a previously generated runtime `librechat.yaml` during
    compile, because that can silently drop newly added tracked fields until some manual cleanup or
    lucky regeneration path happens
  - generated runtime YAML is a deployment artifact for launch/runtime, not an authoring source for
    the next compile pass
- On April 10, 2026, MS365 MCP startup exposed the same runtime-ownership rule on a shipped local
  port:
  - restart must not trust an arbitrary healthy listener already occupying the shipped MS365 MCP
    port
  - the launcher must verify that the existing listener is Viventium-owned and reclaim the port
    when another workspace's MCP server is squatting there
  - otherwise the isolated runtime can silently inherit the wrong Azure app credentials even though
    the compiled Viventium config is correct
- On April 12, 2026, web search drift showed the same compiler boundary from another angle:
  - the runtime correctly disabled Web Search because canonical App Support config never enabled
    `integrations.web_search`
  - the tracked source-of-truth YAML still advertising `interface.webSearch: true` did not make the
    machine live
  - the right fix was to update canonical config and restart, not to patch generated
    `librechat.yaml`
