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
- GlassHive launch/watch defaults are part of that same generated-runtime contract:
  - `GLASSHIVE_DEFAULT_LAUNCH_SURFACE`
  - `GLASSHIVE_SHOW_LIVE_TERMINAL_IN_DESKTOP`
  - `WPR_IDLE_DESKTOP_PRIME_BROWSER`
  - do not rely on manual App Support edits or one laptop's shell exports to make GlassHive launch/watch UX correct
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
- Easy Install must keep Docker-backed features on a minimal first-run contract:
  - a stray `docker` CLI on `PATH` is not enough to treat Docker Desktop as available
  - shared Docker availability checks in wizard and preflight must require the real Docker Desktop
    app/cask install
  - Easy Install may offer local Web Search only when Docker Desktop is actually present
  - Easy Install keeps local Conversation Recall deferred by default instead of auto-enabling it
    from ambient Docker detection
- Built-in agent runtime truth must remain compatible with the selected install/runtime surface:
  - fresh installs and restarts rely on the seeded source-of-truth agent bundle
  - the authoritative background-agent provider/model matrix is documented in
    `docs/requirements_and_learnings/02_Background_Agents.md`; compiler assignments, source-of-truth
    bundle defaults, and runtime normalization must all agree with that matrix
  - for nested managed components, fresh installs follow the pinned component ref in
    `components.lock.json`; a newer local nested checkout does not change what end users receive
  - do not rely on Mongo hand-edits or App Support leftovers to make built-ins behave correctly
  - browser connected-account OAuth unlocks auth for the configured foundation-provider mix; it
    does not currently recompute the built-in background-agent roster by itself
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
  - startup reseed for existing installs must preserve live user-managed tool choices except for
    runtime-disabled tool gates:
    - if the compiler/runtime disabled Web Search, Code Interpreter, or an optional MCP surface,
      persisted built-in agents must prune only those dead tool IDs from live Mongo state
    - that repair path must not use the scaffold bundle to silently restore other live tool choices
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
- Voice turn-taking follows the same compiler/runtime ownership rule:
  - canonical runtime config owns the shared background follow-up window:
    - `runtime.background_followup_window_s`
    - compiles to:
      - `VIVENTIUM_CORTEX_FOLLOWUP_GRACE_S`
      - `VIVENTIUM_VOICE_FOLLOWUP_GRACE_S`
      - `VIVENTIUM_TELEGRAM_FOLLOWUP_GRACE_S`
    - note:
      - the umbrella product phrase is now `background follow-up window`
      - the env var names intentionally keep the older `FOLLOWUP_GRACE` suffix for backward compatibility
  - canonical voice config owns `VIVENTIUM_TURN_DETECTION`
  - canonical voice turn-handling config owns:
    - `VIVENTIUM_VOICE_MIN_INTERRUPTION_DURATION_S`
    - `VIVENTIUM_VOICE_MIN_INTERRUPTION_WORDS`
    - `VIVENTIUM_VOICE_MIN_ENDPOINTING_DELAY_S`
    - `VIVENTIUM_VOICE_MAX_ENDPOINTING_DELAY_S`
    - `VIVENTIUM_VOICE_FALSE_INTERRUPTION_TIMEOUT_S`
    - `VIVENTIUM_VOICE_RESUME_FALSE_INTERRUPTION`
    - `VIVENTIUM_VOICE_MIN_CONSECUTIVE_SPEECH_DELAY_S`
  - canonical voice STT config owns the surfaced AssemblyAI endpointing knobs:
    - `VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD`
    - `VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS`
    - `VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS`
    - `VIVENTIUM_ASSEMBLYAI_FORMAT_TURNS`
  - canonical `voice.worker` config owns the worker/runtime controls:
    - `VIVENTIUM_VOICE_INITIALIZE_PROCESS_TIMEOUT_S`
    - `VIVENTIUM_VOICE_IDLE_PROCESSES`
    - `VIVENTIUM_VOICE_WORKER_LOAD_THRESHOLD`
    - `VIVENTIUM_VOICE_JOB_MEMORY_WARN_MB`
    - `VIVENTIUM_VOICE_JOB_MEMORY_LIMIT_MB`
    - `VIVENTIUM_VOICE_PREWARM_LOCAL_TTS`
  - generated runtime must not rely on one machine's shell exports or App Support hand edits to
    change end-of-turn behavior
  - when the optional semantic turn-detector plugin is installed, launcher startup owns the model
    pre-download so a fresh boot does not die on a missing turn-detector ONNX cache

## Continuity-Aware Snapshot / Restore / Upgrade Boundary

- `bin/viventium snapshot` is the supported manual snapshot entrypoint for local installs.
- The public snapshot wrapper must always write a metadata-only `continuity-manifest.json` under
  the selected snapshot root, even when no private companion helper exists.
- That manifest is evidence, not authorship. It may include:
  - sanitized path labels
  - repo heads
  - runtime-profile and embeddings metadata
  - continuity-surface timestamps/counts
  - warnings/errors about what could not be inspected
- That manifest must not include:
  - secrets
  - raw message content
  - raw prompts
  - Mongo URIs
  - personal emails
  - absolute private home-directory paths
- App Support is the primary machine-local manifest destination. A private companion helper may add
  richer secret-bearing payload into the same machine-local snapshot flow or a private companion
  backup root, but the public wrapper must not require that helper to succeed.
- The product default is operator-triggered manual snapshots, not mandatory daily full backups.
  Bounded private automation may exist later, but the shipped public contract must stay explicit and
  storage-aware.
- `bin/viventium restore` must capture a live continuity audit, compare the selected snapshot
  manifest against live state, and refuse an older snapshot by default unless the operator passes
  `--allow-older-snapshot`.
- Restore must make a pre-apply safety copy of directly affected local state before overwriting it.
- If restore follow-through can leave recall-derived state older than live continuity, restore must
  write the recall rebuild-required marker and runtime must refuse vector-backed recall until the
  operator rebuilds and intentionally clears that marker.
- `bin/viventium continuity-audit` owns the operator review surface for current continuity metadata
  and the explicit `--clear-recall-marker` acknowledgement after rebuild.
- `bin/viventium upgrade` must capture pre/post continuity audits and treat their severity as part
  of the supported upgrade contract:
  - `error`: do not auto-restart
  - `warning`: finish upgrade but require operator review
  - `ok`: continue normally
- The macOS helper may expose a manual `Create Backup Snapshot` action, but it must call the same
  supported snapshot path as the CLI rather than inventing a second backup implementation.

## Learnings

- First-run startup can honestly take minutes because local package builds and optional Docker sidecars
  are real work, especially on a clean machine.
- Playful wait copy is acceptable when the deterministic status path remains visible and reliable.
- Optional-sidecar readiness used by the launcher, install wait loop, and status must share the same
  contract. One path cannot hold the install open on a stricter probe than the runtime itself uses
  to declare the sidecar up.
- On April 16, 2026, GlassHive surfaced the same compiler/runtime ownership rule:
  - desktop-first watch, visible live terminal-in-desktop, and idle desktop priming must come from generated runtime env defaults
  - the GlassHive launch UI and workstation runtime may still carry sane in-code fallbacks, but the shipped product contract belongs in compiled `runtime.env`
  - silent launch failures after worker creation must become explicit runtime state and events instead of relying on operators to infer what happened from an empty project page
- Interactive bootstrap paths can arrive with stdin still attached to a consumed pipe:
  - example: `curl .../install.sh | bash`
  - the CLI must reattach stdin from `/dev/tty` before wizard or preflight prompts
  - otherwise the first prompt sees EOF even though the user launched the install from a real terminal
- Reattached stdin is still not enough on every macOS terminal shape:
  - `questionary` / `prompt_toolkit` can still raise raw-mode attachment errors after the CLI hands
    prompts a real TTY
  - the shared installer UI must catch those runtime prompt failures and fall back to plain prompts
    instead of crashing the install
  - that fallback belongs in the shared prompt wrapper, not as one-off handling in only one wizard
    question
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
- Detached installer startup must track the detached launch ownership boundary, not only the
  short-lived wrapper pid:
  - `bin/viventium start` is allowed to hand control off to a detached process group and exit while
    background builds continue
  - install/start wait logic must therefore follow the recorded detached launch process group under
    `state/runtime/<profile>/detached-launch.pgid` before declaring early failure
  - otherwise clean first builds can be reported as `stopped during startup` during a valid warm-up
    handoff
- Re-entrant launch requests during detached startup must be treated as the same in-flight boot:
  - helper/login-item auto-start can legitimately invoke `bin/viventium launch` while the detached
    install-owned startup is still warming
  - if the recorded detached launch process group is still alive, `bin/viventium launch` must
    return `already starting` instead of tearing the stack down and restarting it mid-boot
- Detached LibreChat API watchdog budgeting must match real clean-machine build time:
  - first-run API readiness on slower Intel Macs can take well beyond the short historical
    watchdog budget
  - the watchdog's initial health wait must therefore survive the same clean-build envelope as the
    installer instead of exiting before the API ever has a chance to come up
- The shipped macOS helper binary is the reliable clean-install path on April 7, 2026:
  - clean x86_64 CommandLineTools hosts can fail SwiftPM manifest linking before any app code builds
  - when `apps/macos/ViventiumHelper/prebuilt/source.sha256` matches current helper sources, the
    installer should use that shipped binary by default instead of surfacing brittle source-build
    failures to end users
  - when helper install runs from a checkout under macOS protected user folders such as
    `~/Documents`, `~/Desktop`, or `~/Downloads`, the helper runtime binding must prefer the
    supported public checkout outside those folders (default `~/viventium`) when that checkout is
    available
  - helper/status-bar config writes must use that same resolver so toggling the helper does not
    silently rebind it back to a protected-folder checkout and retrigger macOS TCC folder prompts
- On April 19, 2026, macOS folder-access prompts exposed the same install/runtime boundary again:
  - the menu-bar helper itself is the macOS app that TCC evaluates, not the shell the user
    originally used to run install commands
  - binding the helper to a repo checkout inside `~/Documents` is enough to trigger repeated
    Documents-folder prompts even when the helper app bundle lives in `~/Applications`
  - the correct fix belongs in helper install/config binding, not in App Support hand edits and not
    by asking users to grant broader folder access than the supported install actually needs
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
- On April 13, 2026, a remote clean-machine audit showed the next nested-release boundary:
  - fresh installs followed the LibreChat ref pinned in `components.lock.json`, not a newer local
    nested checkout
  - a stale parent pin therefore shipped an older built-in main-agent prompt even though current
    nested source had already been updated
  - release readiness for built-in agent/prompt/runtime changes therefore includes updating and
    verifying the parent component pin, not only reviewing the nested repo
- The same April 13, 2026 audit also clarified the existing-install upgrade boundary:
  - the startup seed path already upserts built-in agents from the checked-out bundle on every run
  - existing installs therefore self-heal only after the supported upgrade path refreshes the
    checked-out nested component ref
  - the product gap is not “missing reseed logic”; it is failing to move stale installs onto the
    reviewed pinned checkout before that reseed/upsert runs
- On April 19, 2026, a live local rollback incident clarified the ownership boundary inside that
  reseed path:
  - startup reseed must not overwrite live user-managed built-in agent fields on existing installs
  - protected live fields include at least name/description, instructions, tools, model/provider,
    model bags, voice model/provider/bag, conversation starters, category, and background cortex
    wiring
  - the startup seed path may still create missing built-ins, fill missing fields, repair ACLs, and
    apply canonical runtime normalization to the effective live assignment
  - intentional changes to those live user-managed fields belong in reviewed sync flows such as
    `viventium-sync-agents.js compare` plus the narrowest safe push mode, not in automatic startup
    reseed
- The same April 13, 2026 audit clarified the recall-default ownership boundary:
  - if local conversation recall should default on when the machine already supports the local
    recall path, that default must be set consistently in shared config-building layers
  - fixing only one wizard branch is not enough when presets, base config generation, and advanced
    setup can still seed a different default
- The same April 13, 2026 remote connected-account QA clarified the continuity acceptance boundary:
  - a user can have a healthy connected foundation-model account and successful live chat while
    durable memory is still dead
  - an explicit `remember this` prompt that gets an in-thread success reply is not enough evidence;
    QA must also check the actual `Memories` surface and durable store
  - a visible recall toggle is only policy, not proof that the local recall runtime/index is live
  - when helper logs say the local RAG API is unavailable and recall sync is disabled, the product
    must present recall as unavailable even if the UI toggle still exists
- On April 14, 2026, the same remote memory follow-up clarified the local package-build boundary:
  - LibreChat `packages/*/dist` outputs are generated local runtime artifacts, not tracked public
    release sources
  - a source-only fix inside `packages/api/src/...` is therefore insufficient if the supported
    upgrade/start path leaves an older local `dist` bundle in place
  - launcher rebuild detection must compare package source trees against `dist` markers instead of
    watching only top-level manifest mtimes
  - public release coverage should verify that rebuild contract plus a built-bundle regression, not
    assume a checked-in `dist` artifact exists in clean public clones
- The same April 14, 2026 upgrade rerun clarified the nested-component refresh boundary:
  - existing installs can carry a dirty managed component checkout from earlier local hotfixes or
    debugging
  - `bootstrap_components.py` may correctly refuse to overwrite that dirty checkout, but upgrade
    must not continue as if the pinned component landed successfully
  - `bin/viventium upgrade` must therefore fail closed when selected components remain in
    `kept local dirty checkout` state after refresh
  - `doctor.sh` must report the real validation mode instead of always claiming "present at the
    pinned refs" when validation only passed because a dirty or vendored checkout was tolerated
  - the parent component pin itself must be the exact published full commit SHA from the nested
    component repo; a mistyped or locally copied hash is enough to break the supported fetch path
    even when the intended nested fix is already live on origin
- The same April 14, 2026 continuity hardening pass clarified the operator-state boundary:
  - chat history, saved memory, recall corpora, schedules, and runtime/provider state can drift
    independently
  - restore and upgrade must therefore compare continuity surfaces explicitly instead of assuming
    any snapshot or restart is safe because one service is healthy
  - recall after restore must fail closed until rebuild is intentionally acknowledged
  - manual backup UX belongs on the supported helper/CLI path, not in hidden private scripts
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
- The same April 13, 2026 installer/runtime hardening pass closed the next launcher/status gaps:
  - `bin/viventium status` must distinguish "configured but intentionally stopped" from "still
    starting" by reading the recorded stack-owner state instead of treating any failed live probe as
    startup in progress
  - local loopback health checks in install summary should prefer `curl` before Python urllib on
    macOS hosts where Python probing can misreport localhost reachability
  - local Meilisearch readiness must require the configured API key, not only unauthenticated
    `/health`, because stale listeners with the wrong key create a false green and then break local
    search sync
  - a healthy LibreChat API on `:3180` must not suppress starting a missing frontend on `:3190`;
    partial-stack startup must repair the missing surface
  - local conversation-search sync failures may degrade recall freshness, but they must not abort
    frontend availability during first-run startup
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
- On April 21, 2026, built-in agent continuity exposed the adjacent persisted-tool boundary:
  - existing-install startup reseed correctly preserved live tool arrays, but that alone was not
    enough when global runtime gates disabled a capability such as Web Search
  - the fix belongs in runtime-field repair: prune only the tools the current machine cannot back,
    while still preserving all other live user-managed tool choices
