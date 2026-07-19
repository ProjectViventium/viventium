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
  - `GLASSHIVE_HOST_WORKERS_ENABLED`
  - `WPR_HOST_WORKSPACE_ROOT`
  - `WPR_DEFAULT_EXECUTION_MODE`
  - `WPR_HOST_DESTRUCTIVE_CONFIRMATION`
  - `WPR_HOST_ADVISORY_REVIEWER_ENABLED`
  - `WPR_HOST_PROMPT_VISIBILITY`
  - `WPR_LIBRECHAT_UPLOADS_ROOT`
  - `WPR_BOOTSTRAP_SOURCE_ROOTS`
  - `WPR_DB_PATH`
  - `WPR_CODEX_BIN`
  - `WPR_CLAUDE_CODE_BIN`
  - `WPR_OPENCLAW_BIN`
  - `VIVENTIUM_GLASSHIVE_CALLBACK_URL`
  - `VIVENTIUM_GLASSHIVE_CALLBACK_SECRET`
  - `VIVENTIUM_GLASSHIVE_CAPABILITY_BROKER_SECRET`
  - `GLASSHIVE_ENTERPRISE_MODE`
  - `GLASSHIVE_AUTH_MODE`
  - `GLASSHIVE_ENTERPRISE_TENANT_ID`
  - `GLASSHIVE_IDLE_TERMINATE_AFTER_S`
  - `GLASSHIVE_IDLE_REAPER_INTERVAL_S`
  - `GLASSHIVE_MAX_ACTIVE_WORKERS_PER_USER`
  - `GLASSHIVE_MAX_ACTIVE_WORKERS_PER_TENANT`
  - `GLASSHIVE_MAX_WORKSPACES_PER_USER`
  - `GLASSHIVE_MAX_WORKSPACES_PER_TENANT`
  - `GLASSHIVE_ARTIFACT_DOWNLOAD_MAX_BYTES`
  - `GLASSHIVE_WORKER_ENV_ALLOWLIST`
  - do not rely on manual App Support edits or one laptop's shell exports to make GlassHive launch/watch UX correct
- Stable developer runtimes are part of the compiler boundary:
  - `runtime.dev_env.enabled` marks a side-by-side developer runtime config
  - `runtime.dev_env.shared_singleton_services` declares heavy services that should be referenced
    rather than duplicated in that dev env
  - default shared singleton services are recall/RAG, SearXNG, Firecrawl, Google Workspace MCP, and
    Microsoft 365 MCP
  - Scheduling Cortex is not a shared singleton; dev-env config/compile must give it an offset
    `scheduling_mcp_port`/`VIVENTIUM_SCHEDULING_MCP_PORT` and per-env scheduler DB so a dev env
    cannot satisfy local-prod scheduler health
  - dev envs may offset app-facing ports, but shared singleton service ports must stay aligned with
    the installed runtime unless the operator explicitly chooses full isolation
  - generated env must expose the dev-env and shared-singleton state so launcher/helper surfaces can
    explain what is shared instead of guessing
- Local work workflows are also compiler/runtime-bound:
  - `bin/viventium workflows`, `bin/viventium heal`, and `bin/viventium feature-request` must run
    from the active runtime checkout just like helper/manual operator commands
  - GlassHive host-worker availability is read from compiled runtime env; workflow commands must not
    invent a second GlassHive enablement source
  - compiled runtime env must expose the host worker's executable and persistence inputs as the
    launched service sees them, including supported Codex app-bundled CLI paths and the active local
    GlassHive DB path; shell-only availability or repo-local fallback state is not a product
    readiness signal
  - when GlassHive host workers are unavailable, workflow commands fail loud unless the operator
    explicitly chooses documented degraded mode
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
  - `runtime.auth.connected_accounts_return_origin` ->
    `VIVENTIUM_CONNECTED_ACCOUNTS_RETURN_ORIGIN`; leave blank for the normal configured
    `DOMAIN_SERVER`/public API return path, and set it only for local/off-network connected-account
    OAuth QA when the completion page must return to a localhost browser
- Generated runtime config must not silently preserve hidden provider defaults from the source
  template when the installer/compiler already knows the machine's real auth surface.
- The local launcher owns the fallback OpenAI picker inventory written to LibreChat runtime env:
  - direct API-key inventories include `gpt-5.6`, `gpt-5.6-sol`, `gpt-5.6-terra`, and
    `gpt-5.6-luna`
  - the ChatGPT connected-account inventory includes only the provider-verified
    `gpt-5.6-sol` and `gpt-5.6-terra` slugs, with Sol first; do not silently remap unsupported IDs
  - `OPENAI_MODELS` and `ASSISTANTS_MODELS` remain the runtime delivery fields; explicit
    `VIVENTIUM_OPENAI_MODELS` / `VIVENTIUM_ASSISTANTS_MODELS` or canonical env overrides remain
    authoritative
  - supported restart/upgrade must refresh the generated LibreChat env before model-picker QA;
    editing that generated file by hand is not a product fix
- `librechat.yaml` memory-writer provider/model must be compiled from the actually available
  foundation providers (`openai` / `anthropic`), including connected-account auth:
  - do not leave memory on a hardcoded xAI default when xAI was never configured
  - current product policy prefers Anthropic for memory when Anthropic is available and otherwise
    falls back to OpenAI
  - docs, tests, and generated runtime outputs must all reflect that exact compiler rule
  - the generated provider token is part of the public product contract; downstream runtime
    initialization must accept the compiler-emitted canonical value instead of requiring a
    different alias such as `openAI`
- The supported local nightly-routines default is installed from canonical config, not from owner
  machine leftovers:
  - Express/Easy and Advanced installs enable GlassHive, Prompt Workbench, the built-in Workbench
    nightly reflection schedule, and memory hardening by default
  - upgrades reconcile the same defaults into existing canonical configs once, then compile the
    generated runtime from that config
  - `bin/viventium install`, `upgrade`, `configure`, `compile-config`, and `start` all run the same
    default-nightly reconciler before compiling runtime artifacts, so later CLI auth can be picked up
    without hand-editing App Support files
  - the reconciler must never write a real account email, local absolute user path, raw prompt,
    transcript, token, or owner-specific value into canonical config
  - the default GlassHive worker profile is filled from the currently signed-in local worker CLI
    only when no explicit profile is already configured: Codex when `codex login status` succeeds,
    otherwise Claude when `claude auth status` succeeds
  - the reconciler must not overwrite an explicit configured worker profile on later `start`,
    `compile-config`, `configure`, or `upgrade`; user choice beats auto-detection
  - GlassHive host-worker preflight requires at least one signed-in Codex or Claude CLI; if neither
    is usable, the installer must stop with one clear action to sign in to one of them, not ask the
    user product-design questions
  - OpenClaw may be reported as optional, but missing OpenClaw must not block the default nightly
    workflow when Codex or Claude is ready
  - worker CLI auth is not the same as model-provider API or connected-account auth for memory
    hardening. The worker gate proves GlassHive can run a host-native worker; `runtime.memory_hardening.provider`
    remains an explicit operator choice or is selected by the config compiler from the configured
    LLM auth surfaces.
  - the default built-in reflection schedule must target the first resolved local admin user after
    account creation and remain idempotent; it must not hardcode a public QA account, developer
    account, or private operator identity
  - if the user later signs into Codex or Claude and reruns a supported entrypoint, the generated
    runtime must fill a previously empty worker profile from the newly available CLI
  - if multiple local admins exist before any schedule owner can be resolved, the installer/runtime
    must not guess a personal account. The supported automatic path is the normal first-admin local
    install; multi-admin ambiguity is an operator-visible setup limitation until a deterministic
    owner is available.
- Express Rich Brain Readiness is a first-class installer contract, owned by the shared
  `scripts/viventium/brain_readiness.py` registry and reflected in wizard prompts, preflight,
  generated config, install/status output, doctor-style health, and QA rows:
  - Express installs the core spine automatically: core app/helper, Scheduler, GlassHive, Prompt
    Workbench, built-in nightly reflection, memory hardening with dry-run-first, and viable local
    voice on Apple Silicon
  - GlassHive is mandatory for Express moving forward; host-worker preflight must detect Codex CLI
    or Claude CLI sign-in and fail with one clear action when neither worker can run
  - the built-in nightly flow is documented and tested as: scheduled prompt -> filled placeholders
    -> GlassHive run -> callback -> scheduler ledger -> Workbench shows completed
  - the built-in nightly schedule must be active for the resolved first local admin and carry a
    bounded catch-up policy so a late local scheduler tick does not permanently drop the reflection
  - memory hardening and nightly reflection must resolve the installing user's first local admin
    path without asking for a developer email, hardcoding an owner account, or leaking private data
  - user-owned or resource-heavy surfaces are guided setup, not fake-ready defaults: primary AI
    provider account/API-key, optional fallback provider, transcript folder, Conversation
    Recall/RAG, web search provider, Telegram, Telegram Codex, Google Workspace MCP, Microsoft 365
    MCP, and hosted voice when local voice is not viable
  - foundation fallback credential presence means `Configured`, not `Ready`; only a successful live
    provider request can prove credential validity, and status must not manufacture that proof
  - Conversation Recall/RAG remains guided opt-in because it requires Docker/Ollama/vector-resource
    consent; Docker presence alone must not turn it on
  - Transcript ingest is pending until `runtime.memory_hardening.transcripts.source_dir` is set by
    the wizard, helper, or `bin/viventium transcripts source set <folder>`; an empty source is a
    setup-pending state, not a failure
  - Web Search is guided in Express: local Docker-backed SearXNG/Firecrawl or hosted Serper/
    Firecrawl keys are both valid, and status must identify the exact degraded local service when
    enabled health is incomplete
  - Code Interpreter, Skyvern, OpenClaw, and Remote Access remain off by default. They are
    Advanced/Lab or explicit guided opt-in surfaces and must not appear enabled in public examples
    unless that example is clearly lab-scoped
  - WhatsApp must not be advertised as installed or configured until an owning runtime integration,
    requirement doc, and QA surface exist
  - upgrades preserve explicit disables and never invent secrets, OAuth grants, transcript paths,
    user emails, local absolute paths, or private account state. They may add readiness/status cards
    and reconcile missing core-spine defaults idempotently.
- `runtime.memory_hardening` is the canonical source for the local saved-memory hardening operator
  job:
  - default local installs set `enabled: true`; explicit user disablement remains respected after
    the defaults marker has been applied
  - default schedule is `0 3 * * *`
  - schedules are local macOS wall-clock time; portable `timezone: local` resolves to the current
    system IANA timezone during compilation, and the exported effective timezone is operator/status
    evidence rather than a hardcoded owner-machine city
  - `operator_user_email` optionally scopes scheduled/helper hardening to one local account; empty
    means all local users are eligible
  - a successful scheduled run with `user_count=0` is healthy empty/skip evidence when user memory
    is intentionally disabled or no local users are eligible. Installer/runtime QA must not mark
    that as degraded merely because no memory writes occurred; it must mark it degraded only when
    eligibility is unknown, unexpectedly empty, or accompanied by provider/runtime/transcript/vector
    errors.
  - default lookback is 7 days
  - default idle gate is 60 minutes
  - default max semantic edits is 3 keys per user per run
  - default maximum prompt input is 500,000 estimated characters
  - full-lookback enforcement is on by default; runs fail closed instead of silently clipping the
    7-day corpus unless an operator explicitly allows partial lookback
  - install, configure, upgrade, compile-config, and start reconcile the macOS LaunchAgent from
    generated env. Enabled configs install one 03:00 calendar trigger; only explicit `false`
    removes it. Missing/invalid enablement preserves the existing agent and reports the ambiguity.
  - schedule reconciliation is idempotent and loader-only: identical loaded state is a no-op,
    matching-but-unloaded state is bootstrapped without bootout, and actual plist drift is replaced
    once with post-bootstrap verification. Lifecycle receipts contain only public-safe schedule,
    outcome, and generation-hash evidence. Install and uninstall also share a process lock so
    overlapping supported entrypoints cannot interleave loader state.
  - the installed macOS LaunchAgent command must invoke `scripts/viventium/memory_harden.py`
    directly with the generated runtime dir instead of routing scheduled hardening through
    `bin/viventium`; the user-facing launcher may be running when the 3am job fires
  - the installed macOS LaunchAgent command passes an explicit scheduled trigger marker to the
    wrapper. The wrapper writes a redacted trigger receipt before model work starts and finalizes it
    with exit status after the run. Runtime QA should use that receipt plus the hardener summary to
    prove scheduled delivery; it must not convert observed UTC differences from travel, DST,
    wake-coalesced launchd fires, or audit-time timezone context into a false `PARTIAL`.
  - the LaunchAgent working directory must be App Support, not the repo checkout, so unattended
    jobs do not inherit macOS protected-folder working-directory failures when a developer checkout
    is under Documents/Desktop/Downloads
  - the LaunchAgent command must start the wrapper with a minimal `env -i` environment; provider
    keys and runtime settings are loaded inside the wrapper from generated Viventium runtime files,
    not inherited from unrelated user-session launchd variables
  - the wrapper's generated env load order must match the public CLI: legacy repo/local env files
    are compatibility fallbacks, then `runtime.env`, `runtime.local.env`, and
    `service-env/librechat.env` load in that order so canonical generated runtime state wins
  - `bin/viventium memory-harden` participates in active-runtime-checkout re-exec, so helper/manual
    hardening and schedule installation use the same protected-folder-safe runtime checkout resolver
    as start/stop/helper commands
  - disabling the schedule clears the dry-run-first marker so a later re-enable gets the same
    first-run guard
  - when `dry_run_first` is enabled, the first scheduled apply with no marker performs a dry-run
    and writes the marker before future scheduled applies can mutate memory
  - model-backed memory hardening and transcript ingest are power-gated by the wrapper on macOS:
    they skip while the machine is on battery power or has recorded thermal/performance warnings
    unless an operator explicitly passes `--ignore-power-gate` with
    `VIVENTIUM_MEMORY_HARDENING_ALLOW_POWER_OVERRIDE=1`. `--ignore-idle-gate` only bypasses user-idle
    checks and must not bypass this power/thermal gate.
  - the power/thermal check is a shared local maintenance contract in
    `scripts/viventium/power_budget.py`; audit automations must report power-budget skips instead
    of forcing model-backed work with `--ignore-power-gate`.
  - when hardening is allowed to run, the wrapper starts the Node/model child at lower OS priority
    so scheduled work does not compete with foreground local-prod/dev work.
  - model-backed dry-run/apply hardening has a Node-owned efficiency gate in addition to the wrapper
    power gate: default `min_apply_interval_seconds` is 300, the public marker is stored in
    memory-hardening state without raw paths or content, and the only non-interactive bypass is
    `--ignore-efficiency-gate` paired with
    `VIVENTIUM_MEMORY_HARDENING_ALLOW_EFFICIENCY_OVERRIDE=1`. Power overrides are intentionally
    separate and must not bypass this cooldown.
  - `apply --run-id <run-id>` applies an already generated proposal and does not invoke model-backed
    proposal generation; it is intentionally outside the model-work cooldown.
  - `bin/viventium memory-harden status` is read-only operational inspection and must not wait on
    the global user-facing CLI lock or recompile config; it reports existing generated/runtime
    state while a hardening run may be in progress.
  - non-macOS operators must wire an equivalent cron/systemd timer; the public CLI currently
    auto-installs schedules only through macOS LaunchAgents
  - `provider_profile` must stay `launch_ready_only`
  - default Anthropic hardening tuple is `anthropic / claude-opus-4-8 / xhigh`; the root wrapper
    passes it to the Claude Code CLI path as the explicit provider/model plus
    `VIVENTIUM_MEMORY_HARDENING_ANTHROPIC_EFFORT=xhigh`
  - default OpenAI hardening tuple is `openai / gpt-5.6-sol / xhigh`; the compiler emits
    `VIVENTIUM_MEMORY_HARDENING_OPENAI_REASONING_EFFORT=xhigh` alongside the explicit
    provider/model tuple for the Codex CLI path
  - optional meeting transcript ingestion is configured under
    `runtime.memory_hardening.transcripts`
  - `transcripts.source_dir` compiles to `VIVENTIUM_MEMORY_TRANSCRIPTS_DIR`; empty disables the
    transcript lane
  - `transcripts.ignore_globs` compiles to `VIVENTIUM_MEMORY_TRANSCRIPTS_IGNORE_GLOBS`; this is the
    canonical way to exclude downloader manifests, temp files, and other source-folder sidecars
    without adding semantic transcript parsing
  - ignore globs are serialized into env as a comma-separated list; glob literals should not contain
    commas
  - transcript caps are deterministic cost controls, not content judgment:
    `max_files_per_run` default 20, `min_files_per_run` default 5 for apply-mode Node batches,
    `max_batches_per_invocation` default 1 in the wrapper, `max_chars_per_file` default 500,000,
    `summary_max_chars` default 32,000, reference saved-memory context default 24,000 chars,
    reference recent-conversation context default 36,000 chars, and stable-evidence decay default
    90 days
  - transcript files deferred by a per-run cap are not terminal; the next scheduled/helper run must
    retry them even when mtime, size, and content hash are unchanged
  - transcript RAG mode defaults to `detailed_summary_only`, which means raw transcripts are first
    summarized as complete per-transcript units and detailed summary artifacts are stored/attached
    for normal file_search recall; `raw_and_summary` and `raw_only` are explicit operator/QA modes
  - a configured but unhealthy RAG/vector runtime must not block chat-only memory hardening:
    transcript vector lifecycle and transcript-derived memory writes are deferred, while chat-only
    accepted operations may still apply
  - when a transcript source directory is configured, generated runtime must start the RAG sidecar
    even if default conversation recall is off, because transcript summary artifacts are
    vector-backed file_search resources
  - the macOS helper's manual `Advanced > Ingest Meeting Transcripts` action uses the same wrapper
    path, shows the active operator scope before and after the run, bypasses the idle gate because
    it is user-triggered, marks the run as interactive maintenance so the cooldown can be bypassed
    for that click, keeps the power/thermal gate in force, runs one bounded batch of at least 5
    transcript files, defaults to zero durable saved-memory changes, and writes only
    status/scope/count helper logs. Durable memory reflection remains the normal scheduled hardener
    responsibility unless the operator explicitly overrides the change cap.
  - introducing a future newer model family requires updating model governance and release contract
    tests first
- Endpoint helper config must not hide unavailable provider dependencies:
  - Anthropic conversation-title generation must stay on Anthropic instead of routing through xAI
  - xAI custom endpoint inventory is an explicit compiler/source-template contract:
    `grok-4.3` is the default and title/summary model, current 4.20 stable IDs use the dated
    `0309` forms documented by xAI, and model IDs scheduled for xAI's May 15, 2026 retirement must
    not be used as generated defaults
  - Keep the compiler fallback and `local.librechat.yaml` source-template xAI endpoint aligned;
    the source template currently wins same-name custom endpoint merges in generated
    `librechat.yaml`
  - Direct LibreChat dev starts must refresh the ignored local `LibreChat/librechat.yaml` from the
    tracked `viventium/source_of_truth/local.librechat.yaml` before the API loads startup config;
    otherwise the browser model picker can serve stale model specs even when the source template and
    generated App Support runtime are correct
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
  - Easy Install may offer local Web Search as a guided choice; when Docker Desktop is absent the
    prompt must say that local SearXNG/Firecrawl requires automatic Docker Desktop installation,
    while hosted Serper/Firecrawl requires user-owned keys
  - Easy Install keeps local Conversation Recall deferred by default instead of auto-enabling it
    from ambient Docker detection
- Homebrew-installed CLI prerequisites must be validated as runnable tools, not just files on
  `PATH`:
  - preflight and post-install formula validation must share the same bounded runtime probe
  - broken dynamic-link state after a Homebrew dependency upgrade must surface as a missing
    prerequisite so `bin/viventium install` and `bin/viventium upgrade` can repair or fail clearly
  - domain-specific tools may need stronger probes than `--version`; for example Telegram media
    support validates `ffmpeg` with a tiny decode/filter run
  - daemon, account, model, router, and service readiness remain separate feature checks; a binary
    probe only proves the local CLI can execute
- Built-in agent runtime truth must remain compatible with the selected install/runtime surface:
  - fresh installs and restarts rely on the seeded source-of-truth agent bundle
  - the authoritative background-agent provider/model matrix is documented in
    `docs/requirements_and_learnings/02_Background_Agents.md`; compiler assignments, source-of-truth
    bundle defaults, and runtime normalization must all agree with that matrix
  - for nested managed components, fresh installs follow the pinned component ref in
    `components.lock.json`; a newer local nested checkout does not change what end users receive
  - component selection defaults to the modern LiveKit playground (`agent-starter-react`) for
    voice-capable installs and must not include the old `agents-playground` unless
    `runtime.playground_variant: classic` is explicitly selected with voice enabled
  - running component bootstrap without `--config` uses the same public modern-playground default;
    an existing classic checkout may remain on disk, but it is not refreshed or selected unless the
    install explicitly opts into the classic playground
  - do not rely on Mongo hand-edits or App Support leftovers to make built-ins behave correctly
  - browser connected-account OAuth unlocks auth for the configured foundation-provider mix; it
    does not currently recompute the built-in background-agent roster by itself
  - when the compiler policy changes a model family, the source-of-truth bundle and live built-in
    agent sync must be updated together; otherwise existing installs can keep failing on stale
    model config even though generated runtime config is healthy
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
  - GlassHive host-native workers compile from `integrations.glasshive.host_worker`; when GlassHive
    is enabled, host workers default on, the default execution mode is `host`, the default workspace
    root is user-scoped (`~/viventium`), and `/viventium` is valid only when doctor proves it is
    writable by the current user
  - the default host Codex automation tuple is `gpt-5.6-sol / xhigh`. The compiler emits the same
    tuple for host and general Codex worker env so Prompt Workbench, Scheduling Cortex, GlassHive
    bootstrap, and model-route evidence cannot silently diverge. The Viventium compiler also emits
    the now-proven xHigh route flag by default; otherwise GlassHive's standalone safety clamp could
    turn a requested xHigh run into medium on a clean install
  - that host-worker setting is shared by unattended Workbench automation and direct host Codex
    delegation. This is the intentional current quality-first baseline, not a change to the main
    conscious agent, voice, activation classifiers, or `viventium_agent` reminder delivery
  - `integrations.glasshive.host_worker` also owns first-class optional native-capability controls
    for host worker runtime requirements, Codex native MCP allowlist/plugin cache, Codex lockdown
    flags, and Claude Chrome/effort launch flags. These compile into canonical runtime env so
    operators do not need undocumented `runtime.extra_env` escape hatches for the capability
    contract.
  - when `integrations.glasshive.host_worker.enabled=false`, the compiler must emit
    `GLASSHIVE_HOST_WORKERS_ENABLED=false`, force the generated default execution mode to `docker`,
    and generate MCP instructions that do not tell agents to create host-native workers
  - when `integrations.glasshive.deployment_mode=azure_enterprise_vm_docker`, the compiler must:
    - reject localhost GlassHive MCP/operator URLs
    - force `GLASSHIVE_HOST_WORKERS_ENABLED=false` and `WPR_DEFAULT_EXECUTION_MODE=docker`
    - emit `GLASSHIVE_ENTERPRISE_MODE=true`, the configured auth mode, tenant id, idle reaper
      policy, quota caps, artifact cap, upload root, bootstrap source roots, and provider env
      allowlist
    - emit optional `GLASSHIVE_OWNER_IDENTITY_CLAIMS`,
      `GLASSHIVE_OWNER_IDENTITY_ALIASES_JSON`, or `GLASSHIVE_OWNER_IDENTITY_ALIASES_FILE` only from
      `integrations.glasshive.enterprise.owner_identity`; defaults stay strict `user_id` matching
      with no aliases so SSO deployments do not silently widen owner scope
    - emit `GLASSHIVE_SIGNED_LINK_SECRET` for enterprise mode. If no dedicated
      `integrations.glasshive.enterprise.signed_link_secret` is configured, compile a tenant-scoped
      derivative from the call-session secret; explicitly reject values that equal the service token
    - when local enterprise simulation URLs include explicit ports, emit matching
      `GLASSHIVE_MCP_PORT` and `GLASSHIVE_UI_PORT` so the launcher binds the same ports that
      LibreChat is configured to call
    - default service-token delivery to a trusted reverse proxy and therefore omit `X-WPR-Token`
      from LibreChat YAML unless `service_token_delivery=client_header` is explicitly configured
    - add `X-Viventium-Tenant-Id` and LibreChat user/request/upload headers to the generated
      GlassHive MCP server
    - support server-side `api_key` provider auth for enterprise mode, including explicit
      `OPENAI_BASE_URL`, `ANTHROPIC_BASE_URL`, and `PORTKEY_*` env projection through
      `runtime.extra_env` or the canonical env import list; connected-account auth remains
      supported for local/personal modes but is not the default enterprise path
    - compile optional MCP OAuth only when explicitly enabled; OAuth is a separate MCP consent path
      and must not be documented as silent reuse of LibreChat's login token. The runtime remains
      `first_party_assertion` unless a real external token validator is installed; OAuth/OIDC auth
      modes fail closed by default.
    - keep enterprise worker bootstrap clean-room with respect to the VM account's local Codex,
      Claude, and git auth/identity files; provider access must come from explicit allowlisted env
      vars or a broker
    - emit the env needed for short-lived opaque artifact/watch links, and keep local/personal
      callback URLs compatible when no enterprise signing secret is configured
  - host worker doctor/preflight must report local `codex`, `claude`, and `openclaw` CLI
    availability separately; missing OpenClaw degrades only the `@openclaw` host worker, not Codex
    or Claude workers
  - host worker CLI availability must match the launched service environment, not only the
    interactive shell. On macOS, a valid app-bundled Codex CLI path is a supported Codex host-worker
    runtime and the compiler must emit it as `WPR_CODEX_BIN` when `codex` is not on the service
    `PATH`; discovery checks `/Applications`, `~/Applications`, and `VIVENTIUM_CODEX_APP_DIRS`.
  - generated GlassHive MCP headers must include user, agent, conversation, parent message, and
    current message context so `worker_find_or_resume` can seed same-chat callback metadata without
    a controller-level mention parser
  - those generated GlassHive MCP headers also carry request-scoped upload metadata (`files`,
    `attachments`, `tool_resources`, `file_ids`) as encoded JSON so GlassHive workers reuse the
    current upload path rather than adding a duplicate one
  - generated GlassHive env must expose the existing LibreChat uploads root to GlassHive through
    `WPR_LIBRECHAT_UPLOADS_ROOT` and allow bootstrap file materialization from that same root
    through `WPR_BOOTSTRAP_SOURCE_ROOTS`; this is how browser/API/voice uploads become workspace
    files without adding a second upload service
  - GlassHive callbacks must be validated with per-worker/run HMAC binding, fresh callback
    timestamps, replay detection, and same-user conversation ownership before the callback receiver
    writes status or completion messages back into chat; the compiled GlassHive callback secret is a
    scoped derivative, not the raw call-session or scheduler secret
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
- Telegram voice-note STT is a bridge reliability boundary:
  - canonical `integrations.telegram.stt_provider` may override transcription just for Telegram
  - when omitted, Telegram inherits the configured global voice STT provider, including local
    Whisper/whisper.cpp
  - the compiler must not silently remap inherited local Whisper to OpenAI, AssemblyAI, or any
    hosted provider; hosted Telegram STT must be an explicit operator choice
  - local Telegram STT must use the serialized local-STT path and media-decoder preflight instead
    of avoiding local STT by changing providers behind the user's back
  - release tests must assert the inherited local-Whisper default so future "reliability" changes
    cannot drift Telegram onto hosted STT without an explicit config field
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
  - canonical runtime config separately owns the GlassHive worker callback wait window:
    - `runtime.glasshive_followup_timeout_s`
    - compiles to:
      - `VIVENTIUM_WEB_GLASSHIVE_TIMEOUT_S`
      - `VIVENTIUM_VOICE_GLASSHIVE_TIMEOUT_S`
      - `VIVENTIUM_TELEGRAM_GLASSHIVE_TIMEOUT_S`
    - default:
      - 600 seconds, because host-native browser/desktop work can legitimately take several minutes
  - GlassHive callback delivery health is runtime state, not generated config. Generated config owns
    callback URL/secret/wait-window inputs, but runtime health and nightly QA must prove callback
    outbox delivery, active backlog, active retry attempts, stale delivering reclaim, and dead-letter
    delta from the live store.
      - this timeout must not inherit the shorter background follow-up grace window
    - valid range:
      - 30-86400 seconds; compiler and preflight should reject values outside that range
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
  - canonical Cartesia TTS config owns the Sonic-3 request knobs:
    - `VIVENTIUM_CARTESIA_API_VERSION`
    - `VIVENTIUM_CARTESIA_MODEL_ID`
    - `VIVENTIUM_CARTESIA_VOICE_ID`
    - `VIVENTIUM_CARTESIA_SAMPLE_RATE`
    - `VIVENTIUM_CARTESIA_SPEED`
    - `VIVENTIUM_CARTESIA_VOLUME`
    - `VIVENTIUM_CARTESIA_EMOTION`
    - `VIVENTIUM_CARTESIA_LANGUAGE`
    - `VIVENTIUM_CARTESIA_MAX_BUFFER_DELAY_MS`
    - `VIVENTIUM_CARTESIA_SEGMENT_SILENCE_MS`
  - canonical `voice.worker` config owns the worker/runtime controls:
    - `VIVENTIUM_VOICE_INITIALIZE_PROCESS_TIMEOUT_S`
    - `VIVENTIUM_VOICE_IDLE_PROCESSES`
    - `VIVENTIUM_VOICE_WORKER_LOAD_THRESHOLD`
    - `VIVENTIUM_VOICE_JOB_MEMORY_WARN_MB`
    - `VIVENTIUM_VOICE_JOB_MEMORY_LIMIT_MB`
    - `VIVENTIUM_VOICE_PREWARM_LOCAL_TTS`
  - the compiler owns the default Phase A background notice mode:
    - `VIVENTIUM_CORTEX_PHASE_A_NOTICE_MODE=any_activated_on_voice`
    - this value, plus the voice Phase A knobs below, must be emitted into both `runtime.env` and
      `service-env/librechat.env` so the installed LibreChat service uses the same default as source
    - background detection budgets/flags are owner-canonical in
      `docs/requirements_and_learnings/02_Background_Agents.md` ("2026-05-30 … Two Independent Modes").
      The compiler emits, for the two independent modes (neither flag affects the other mode):
    - `VIVENTIUM_VOICE_BACKGROUND_AGENT_DETECTION_ASYNC=true` (voice async "nevermind+redo" default
      ON)
    - `VIVENTIUM_TEXT_BACKGROUND_AGENT_DETECTION_ASYNC=false` (text async opt-in; default OFF)
    - `VIVENTIUM_VOICE_PHASE_A_AWAIT_MS=690` (voice detection budget)
    - `VIVENTIUM_TEXT_PHASE_A_AWAIT_MS=1300` (text detection budget)
    - `VIVENTIUM_CORTEX_DETECT_TIMEOUT_MS=2000` (shared fallback budget)
    - `VIVENTIUM_CORTEX_LATE_DETECT_TIMEOUT_MS=4000` (non-blocking recovery budget after a zero-activation fast-pass timeout; reuses canonical classifier/fallback/Phase B paths and does not delay the main answer)
    - `VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=true` (voice stays async even when a
      configured tool-hold cortex exists; Phase B/follow-up owns late or side-effecting evidence)
    - `VIVENTIUM_VOICE_LOG_LATENCY=1`
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

## Feelings compiler contract

`runtime.feelings` is the canonical operator surface for the Feelings feature. The compiler owns:

- operator availability and the per-user default-enabled seed;
- agent scope (`all_agents` by default or `conscious_agent`);
- all nine default Nature/half-life/enabled values, whose band semantics and product requirements
  are owned by `54_Emotional_Cortex_And_Feeling_State.md`;
- reaction activation mode (`always`, `classified`, or `disabled`);
- reaction provider, model, Responses API, reasoning effort, Fast/Priority tier, and timeout;
- classified-activation provider/model/confidence/timeout.

The compiler validates closed enums, supported provider names, finite band ranges, positive
half-lives/timeouts, known band IDs, and a bounded confidence threshold. It emits explicit
`VIVENTIUM_FEELINGS_*` values plus `VIVENTIUM_FEELINGS_BANDS_JSON`. Defaults and examples live in
`config.schema.yaml`, `config.full.example.yaml`, and `config.minimal.example.yaml`; the executable
contract is `tests/release/test_feelings_contract.py`.

The default reaction route is `openai / gpt-5.6-terra`, Responses API, reasoning `none`,
`fast: true`, and `service_tier: priority`. Generated env is runtime output. Operators edit canonical
config and recompile/restart; they do not patch generated App Support env files.

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
- The CLI operation lock protects startup preparation, not the lifetime of the foreground stack:
  - `bin/viventium start` must release `state/cli-operation.lock` after config compilation,
    schedule sync, and runtime handoff setup, before entering the long-running stack supervisor
  - otherwise status-bar actions such as Stop/Quit, prompt workbench launch, manual memory
    hardening, and meeting-transcript ingest are blocked while the app is already healthy
  - long-running runtime ownership belongs in stack/process state, not in the short operator
    command lock
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
- On May 2, 2026, a recurrence exposed two additional helper delivery requirements:
  - already-installed helper state must self-heal stale protected-folder `repoRoot` values on
    helper launch, because source fixes in the installer do not automatically rewrite App Support
    config for users who already have the helper installed
  - detached helper start/stop must derive the command from the healed helper config instead of
    trusting a generated App Support wrapper that may still contain an old protected checkout path
  - when no safe checkout exists, helper install must fail closed and the running helper must block
    start/stop/backup actions with clear user guidance instead of silently launching from the
    protected checkout
  - Swift and shell protected-folder checks must both resolve symlinks so aliases or symlinked
    checkout paths do not bypass the macOS TCC boundary
  - the assembled helper app bundle must be locally code signed with the `ai.viventium.helper`
    bundle identifier after packaging so the installed app identity matches the product bundle;
    Developer ID signing is still required for update-stable TCC identity, so signing is not a
    substitute for keeping runtime roots out of protected folders
- The same incident clarified the developer-checkout escape hatch:
  - default public installs still prefer a safe checkout outside `~/Documents`, `~/Desktop`, and
    `~/Downloads` to avoid repeated macOS folder-access prompts
  - developers need an explicit machine-local setting when they want helper/start commands to run
    the checkout they are actively editing, even when a separate installed checkout also exists
  - `bin/viventium runtime-checkout use --this --allow-protected-folder` records that choice under
    App Support state and refreshes the helper binding without copying, deleting, resetting,
    pulling, or migrating code, runtime config, snapshots, or database state
  - helper refresh from this command should relaunch the status-bar helper so applying the setting
    does not make the menu disappear until the next login
  - helper config carries the same explicit protected-folder acknowledgement so the helper does not
    silently self-heal the developer checkout back to `~/viventium`
  - global or stale checkout invocations of start, stop, and helper-binding commands should re-exec
    through the active runtime checkout instead of starting or stopping a different repo by accident
  - re-execed commands must use the active checkout's own component lock file instead of carrying
    the caller checkout's `components.lock.json`
  - the re-exec boundary must reset both argv and inherited environment, including
    `VIVENTIUM_COMPONENTS_LOCK_FILE`; otherwise the right code can still read the wrong component
    lock
  - an explicit active-checkout setting must outrank LaunchAgent environment hints such as
    `VIVENTIUM_HELPER_RUNTIME_REPO_ROOT`; install-time helper defaults should not outvote a later
    developer selection
  - clearing the setting restores automatic checkout resolution; it must not remove App Support
    state or repo files
- The same pass exposed an optional-cleanup rule:
  - disabled optional maintenance features must not block start/upgrade when their cleanup helper is
    absent from a temporary or partial checkout
  - if memory hardening is explicitly enabled and its helper script is missing, fail closed; if the
    feature is disabled and an old LaunchAgent cleanup cannot run, warn and continue
- The same May 2, 2026 incident clarified two health-reporting boundaries:
  - the macOS helper's Running/Stopped state is a core surface check only: LibreChat API, LibreChat
    frontend, and the modern playground. Optional sidecars such as MCP servers, local search,
    recall, voice, or scraper services must not make the helper show `Start` while the app is
    usable.
  - optional sidecars still matter for stop convergence and for `bin/viventium status`, where each
    sidecar must report its own live/configured/action-required state.
  - OAuth-backed MCP servers that already have a usable stored access or refresh token should be
    warmed by the connection-status endpoint. The UI should not stay in a needs-auth/disconnected
    state merely because the last refresh happened while the local MCP listener was down.
  - status-route warmup must be bounded: cooldown/in-flight guards still apply, OAuth token
    presence should be short-cacheable, and setup data should be re-read only after a warmup
    attempt that could have changed connection state
  - the browser MCP status query should refresh periodically while MCP controls are mounted so a
    recovered local listener or refreshed token becomes visible without requiring a full page reload.
  - MCP endpoint readiness must treat an HTTP auth challenge from `/mcp` as a live server signal;
    connection-refused is the failure state.
- On May 15, 2026, restart QA exposed a status-bar helper lifecycle boundary:
  - loginwindow can launch the Viventium helper successfully and still report an early app death
    before the delayed helper auto-start callback submits `bin/viventium launch`
  - the helper must explicitly disable AppKit automatic termination while it owns the status-bar
    menu and login auto-start responsibility, because a menu-bar app with no normal windows must
    remain alive long enough to start and monitor the local runtime
  - the helper bundle must also declare `NSSupportsAutomaticTermination=false` so the lifecycle
    contract is visible in the shipped app, not only in Swift runtime code
  - helper startup QA must inspect loginwindow/system logs, the helper process, helper logs, and the
    live runtime surfaces; the presence of a macOS login item alone is not proof that Viventium will
    start after reboot
- The helper's `Advanced > Prompt Workbench` submenu is a separate lifecycle surface:
  - `Open` must start the workbench if needed and then open the browser
  - `Start` and `Stop` must call `bin/viventium prompt-workbench ...`, not the main stack start/stop
    commands
  - `Stop` must terminate only the managed Prompt Workbench process recorded under App Support
    prompt-workbench state, leaving LibreChat, native services, and Viventium's current runtime state
    untouched
  - clean installs and upgrades must refresh the shipped helper fallback when the helper source
    changes, or new users will not see the same Advanced submenu
- The config compiler owns the Workbench sidecar flag:
  - `runtime.prompt_workbench.enabled: true` compiles to `VIVENTIUM_PROMPT_WORKBENCH_ENABLED=true`
    and `START_PROMPT_WORKBENCH=true`
  - supported local installs and upgrades set this flag true by default because Prompt Workbench is
    part of the nightly reflection contract
  - `runtime.prompt_workbench.seed_nightly.enabled/active/executor` compiles to
    `VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_*` env keys; default local behavior is an active
    `glasshive_host` Workbench schedule
  - the main launcher may start and watchdog Prompt Workbench only when that compiled/env flag is
    enabled, or when an equivalent explicit env override is provided
  - stack-managed starts must suppress stdout from `bin/viventium prompt-workbench start` so the
    launch token/authenticated URL is not copied into helper or stack logs
  - helper/CLI `prompt-workbench stop` must leave a local user-stopped marker that the sidecar
    watchdog respects, so the Workbench does not immediately reopen after the user stops it
  - `bin/viventium prompt-workbench stop` remains scoped to Workbench and must not stop the main
    runtime
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
  - shipped voice overrides must therefore seed provider-specific voice parameters explicitly
    (`voice_llm_model_parameters.reasoning_effort: none` for the current xAI/Grok voice route, or
    `voice_llm_model_parameters.thinking: false` for Anthropic voice routes)
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
  - local Meilisearch readiness must also inspect recent failed tasks and fail closed on
    index-version or incompatible-engine failures; otherwise `/health` can stay green while
    settings/document tasks churn forever
  - Viventium-owned local Meilisearch must run with source-owned resource/log caps and a pinned
    stable image; derived indexes may be archived and rebuilt from Mongo, but Mongo conversation,
    user, and config collections are protected state
  - a healthy LibreChat API on `:3180` must not suppress starting a missing frontend on `:3190`;
    partial-stack startup must repair the missing surface
  - local conversation-search sync failures may degrade recall freshness, but they must not abort
    frontend availability during first-run startup
- On April 13, 2026, remote clean-machine onboarding exposed the optional-service consistency rule
  that still applies when a user explicitly disables GlassHive:
  - generated `librechat.yaml`, seeded built-in agent tools, and runtime MCP/tool loading must all
    agree when GlassHive is off
  - otherwise a missing local GlassHive MCP can surface to fresh users as a generic `No key found`
    error even though foundation-model auth is healthy
- On May 31, 2026, the nightly-routines QA follow-up superseded the old local default: GlassHive is
  part of the supported local install and upgrade path because the built-in nightly reflection uses
  scheduled Workbench prompts delivered through GlassHive.
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
    `xai / grok-4.3` with `voice_llm_model_parameters.reasoning_effort: none`
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
- On May 7, 2026, xAI standalone TTS added a provider-id and secret-routing rule:
  - canonical voice TTS provider id is `xai`
  - legacy aliases `x_ai`, `grok`, and `xai_grok_voice` are accepted at config/compiler/runtime
    boundaries but compile to `xai`
  - hosted voice setup must be able to collect a TTS-only xAI API key and store it under
    `voice.provider_keys.xai` / `keychain://viventium/x_ai_api_key`
  - xAI TTS secret precedence is voice provider key, selected `voice.tts`, keychain fallback, then
    `llm.extra_provider_keys.x_ai` only as a fallback
  - generated Telegram service env must include xAI voice settings and
    `VIVENTIUM_XAI_TTS_API_KEY` so Telegram voice replies can follow the same saved Speaking route
    and dedicated TTS key as LiveKit calls
  - the hosted wizard must not silently default new installs to xAI before the user has explicitly
    configured and QA'd that provider
