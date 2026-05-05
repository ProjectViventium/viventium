# Report

Date: 2026-04-07

## Automated verification

Ran:

```bash
bash -n viventium_v0_4/viventium-librechat-start.sh
bash -n scripts/viventium/install_macos_helper.sh
python3 -m pytest tests/release/test_remote_call_tunnel.py tests/release/test_install_summary.py tests/release/test_macos_helper_install.py tests/release/test_cli_upgrade.py tests/release/test_detached_librechat_supervision.py -q
```

Result:

- `65 passed in 22.07s`

Coverage added:

- remote tunnel persists a structured error state on bootstrap failure
- launcher keeps local startup going when remote access setup fails
- launcher suppresses the UPnP refresh worker when the saved public-edge state contains `last_error`
- install summary/status renders `Action Required` and recovery next steps from the saved error
- helper install prefers the shipped matching prebuilt binary and does not touch `swift`/`xcrun`
- Telegram bridge defers cleanly during long LibreChat builds, surfaces `Starting`, and self-starts
  after API health without a manual restart

## Native CLI dependency-drift follow-up

Date: 2026-04-26

Incident driver:

- Telegram voice transcription failed even though `ffmpeg` was present on `PATH`
- the binary aborted at runtime after Homebrew dependency drift left it linked to an older x265
  dylib than the one installed on the host

Fix contract:

- preflight validates runnable Homebrew CLI prerequisites with bounded executable probes
- formula install handling retries with `brew reinstall` when install succeeds but the runtime
  probe still fails
- if install plus reinstall cannot make the binary execute, the installer reports likely Homebrew
  dependency drift and points the operator at `brew upgrade`, `brew reinstall <formula>`, and
  `brew doctor`
- `bin/viventium status` surfaces a `Runtime Checkout` warning when the live stack owner checkout
  differs from the checkout running the status command
- Telegram bot startup now uses `nohup` plus `disown`, and detached launcher cleanup skips child
  termination, so narrow launcher runs do not report a successful Telegram start and then lose the
  bot when the launcher shell exits

Verification:

```bash
uv run --with pytest --with PyYAML python -m pytest tests/release/test_preflight.py tests/release/test_install_summary.py tests/release/test_telegram_media_prereqs.py tests/release/test_telegram_transcription_error_contract.py -q
uv run --with pytest --with PyYAML python -m pytest tests/release/test_detached_librechat_supervision.py -q
cd viventium_v0_4/telegram-viventium/TelegramVivBot && uv run --with pytest python -m pytest ../tests/test_voice_preferences.py ../tests/test_stt_telegram_assemblyai.py ../tests/test_stt_env.py -q
python3 -m py_compile scripts/viventium/preflight.py scripts/viventium/install_summary.py
bash -n bin/viventium
git diff --check
```

Result:

- combined release preflight/install-summary/Telegram/detached-supervision slice: `99 passed, 1 skipped`
- repeated preflight/install-summary slice: `80 passed`
- Telegram bot STT slice: `31 passed`
- syntax and whitespace checks passed
- broader `tests/release/test_cli_upgrade.py` was also sampled; its isolated temp-repo cases fail
  before this change is exercised because those fixtures omit `scripts/viventium/memory_harden.py`

## Public-review follow-up

Date: 2026-04-08

Reran the focused launcher/runtime slice after closing the helper-early-exit stale-state gap and
sanitizing the public QA artifact placeholders.

Ran:

```bash
bash -n viventium_v0_4/viventium-librechat-start.sh
python3 -m pytest tests/release/test_cli_upgrade.py tests/release/test_install_summary.py tests/release/test_remote_call_tunnel.py -q
```

Result:

- `57 passed in 14.86s`

Additional coverage now proves:

- the launcher writes a fallback `last_error` when the remote-access helper exits before persisting
  failure state
- stale healthy `public-network.json` content is replaced before refresh-worker gating runs

## Live-machine verification

Machine:

- local macOS clean-install test host
- required public ports already forwarded to another LAN host:
  - `80/tcp`
  - `443/tcp`

Ran:

```bash
cd /path/to/viventium
./bin/viventium start
./bin/viventium status
```

Observed:

- startup logged:
  - `Remote access setup failed; local startup will continue without it: Router already forwards TCP 80 ...`
- startup continued into normal local service boot instead of stopping
- `~/Library/Application Support/Viventium/state/runtime/isolated/public-network.json`
  persisted:
  - `provider: public_https_edge`
  - `last_error: Router already forwards TCP 80 ...`
- `bin/viventium status` reported:
  - `Remote Access | Action Required`
  - exact router conflict in the detail row
  - recovery next step telling the operator to fix the blocker and rerun `bin/viventium start`

## Isolated clean-install verification

Machine:

- local macOS clean-install test host
- isolated temp root:
  - `<temp>`

Ran:

```bash
./install.sh --headless --config-input <temp>/preset.yaml --app-support-dir <temp>/app-support
<temp>/repo/bin/viventium --app-support-dir <temp>/app-support status
```

Observed:

- helper selected the shipped prebuilt helper binary
- helper logged:
  - `Remote access setup failed; local startup will continue without it: Router already forwards TCP 80 ...`
  - `Queued deferred Telegram bot startup watcher`
  - `Telegram Bot: starting (waiting for LibreChat API)`
  - `LibreChat API before Telegram bot start ready`
  - `Telegram bot started`
- steady-state status reported:
  - `LibreChat Frontend | Running`
  - `LibreChat API | Running`
  - `Modern Playground | Running`
  - `Remote Access | Action Required`
  - `Telegram Bridge | Running`
- runtime state persisted:
  - `<temp>/app-support/state/runtime/isolated/public-network.json`
  - `<temp>/app-support/state/runtime/isolated/telegram_bot.pid`

## Remote clean-machine verification

Date: 2026-04-12 to 2026-04-13

Machine:

- private remote Intel macOS test host
- verified through a fresh public clone in a new directory after supported uninstall

Ran:

```bash
~/viventium/bin/viventium uninstall --yes
git clone <public-main-repo> <fresh-clone>
cd <fresh-clone>
./install.sh --headless --config-input <temp>/preset.yaml
bin/viventium status
```

Observed before fixes:

- uninstall completed successfully and preserved a backup under App Support Removed
- first-run clean-machine startup was materially slower than a warm owner machine, but it did
  complete and eventually brought up the API, frontend, and playground
- during warm-up, install/status copy could still read as "ready" before the core surfaces were
  actually healthy
- headless macOS shell sessions emitted unsupported-locale noise (`C.UTF-8`) that made the install
  look dirtier than it was
- a newly registered browser user could log in and land in `/c/new`, but the first real message
  surfaced a raw `No key found. Please provide a key and try again.` error even though the install
  was configured for connected-account auth
- browser registration emitted a React warning caused by redirecting during render after success

Fixes applied:

- install summary / status now distinguish `still starting` from `ready` based on live core-surface
  health
- the public CLI sanitizes unsupported macOS locale defaults before Python-backed steps run
- non-interactive setup now keeps secrets in machine-local config state without spamming macOS
  Keychain write failures during supported headless installs
- uninstall and factory reset now synchronously drain managed native services before removing App
  Support state, so a stale LiveKit process from an older checkout does not survive into the next
  clean install
- OpenAI and Anthropic connected-account initialization now return a dedicated
  `connected_account_required` error so the UI tells the user exactly where to connect their model
  account
- registration success countdown now redirects from an effect instead of mutating router state
  during render
- aborted first-message auth failures no longer trigger stray title-generation requests against a
  transient stream id, so clean installs do not log a misleading `/api/convos/gen_title/...` 404

Follow-up verification:

- targeted release slice passed:
  - `test_install_summary.py`
  - `test_cli_upgrade.py` affected scenarios
- targeted LibreChat regression slice passed:
  - OpenAI connected-account initialize
  - Anthropic connected-account initialize
  - registration success/error flow
  - resumable SSE title-queue flow
- remote browser retest showed:
  - sign-up works
  - login works
  - `/c/new` loads
  - missing connected-model auth now produces actionable guidance instead of a raw key error
  - aborted first-message auth no longer triggers a stray title-generation 404

Scope note:

- a separate-device voice deep-link that opens `http://localhost:3300/...` is still not a public
  remote-access claim in `remote_call_mode: disabled`; that path remains out of scope unless the
  supported remote voice mode is enabled

## Installer/runtime hardening follow-up

Date: 2026-04-13

Validated against the current parent `main` after a remote clean-machine review showed the earlier
publish only covered prompt-entry resilience, not the deeper launcher/runtime boundaries.

Ran:

```bash
bash -n viventium_v0_4/viventium-librechat-start.sh
python3 -m py_compile scripts/viventium/wizard.py scripts/viventium/preflight.py scripts/viventium/install_summary.py
uv run --with pytest --with pyyaml pytest tests/release/test_wizard.py tests/release/test_preflight.py tests/release/test_install_summary.py tests/release/test_detached_librechat_supervision.py -q
```

Result:

- syntax checks passed
- focused release slice passed after the missing runtime hardening was merged

Confirmed fixes:

- Easy Install now treats Docker Desktop conservatively:
  - a stray `docker` CLI on `PATH` is no longer enough to enable Docker-backed defaults
  - if Docker Desktop is absent, Easy Install keeps local Web Search and local Conversation Recall
    off and defers them to later configuration
- `bin/viventium status` now distinguishes a stopped stack from a warming stack:
  - missing local web surfaces show `Configured` after a recorded stop instead of `Starting`
- install summary loopback health now prefers `curl` before Python urllib
- local Meilisearch readiness now requires an authenticated probe using the configured key
- stale Viventium-owned Meilisearch listeners with the wrong key are recycled automatically
- partial LibreChat startup now repairs the missing surface instead of treating a lone healthy API
  as proof that the frontend is already healthy
- local conversation-search sync failures now log a warning and continue instead of aborting the
  frontend path

Why this matters:

- the earlier piped-bootstrap fix only proved the installer could reach a prompt
- the remote review showed a fresh user could still land in a broken runtime shape later because
  launcher ownership and status honesty were incomplete
- this follow-up closes that gap in the owning startup/status layers instead of relying on owner
  machine leftovers or private repair steps

## Detached-launch follow-up

Date: 2026-04-13

Observed on the private remote macOS clean-install test path:

- install wait reached the timeout/failure branch even though the detached launch had already handed
  off correctly and background LibreChat build output was still progressing
- the detached launch wrapper pid had exited, but the recorded detached launch process group was
  still alive under `state/runtime/<profile>/detached-launch.pgid`
- a re-entrant launch during that same warm-up window could restart the stack instead of honoring
  the in-flight detached startup
- detached LibreChat API watchdog initial wait was still shorter than real first-run Intel clean
  build time

Root cause:

- `bin/viventium` install/start wait logic treated the short-lived detached wrapper pid as the main
  ownership signal
- once that wrapper exited, the handoff gap before healthy listeners appeared could be misread as
  `startup stopped`, even though the detached launch process group was still alive
- the detached LibreChat API watchdog initial health wait budget was shorter than real clean-machine
  build time on the remote Intel Mac

Fixes applied:

- `bin/viventium` now reads the recorded detached launch process group and keeps waiting while that
  group is still alive
- `bin/viventium launch` now returns `Viventium is already starting.` instead of restarting the
  stack when the detached launch process group is still warming
- detached LibreChat API watchdog initial wait now defaults to the longer clean-build budget
  (`1800` retries)

Focused verification:

- `python3 -m pytest tests/release/test_cli_upgrade.py tests/release/test_detached_librechat_api_watchdog.py -q`
- targeted assertions prove:
  - detached launch process-group detection in `bin/viventium`
  - `detached_start_failed_early()` continues waiting while the detached process group is alive
  - re-entrant detached launch requests return `already starting`
  - the longer detached LibreChat API watchdog initial wait budget is wired into the launcher

## Remote current-main audit

Date: 2026-04-13

Machine:

- private remote macOS test laptop
- validated against:
  - the pre-existing canonical local install on default ports
  - a fresh isolated public clone in a new directory on alternate ports

### Existing-install findings

Verified through real browser QA plus Mongo/runtime inspection:

- synthetic browser user login worked and reached `/c/new`
- browser `Settings > Account > Connected Accounts` showed:
  - `OpenAI | Connected`
  - `Using your connected account.`
- live chat on the shipped `Viventium` agent worked once that browser-visible connection existed
- the installed main agent was still stale on that machine:
  - Mongo `agents.instructions` began with the legacy `You're Eve (or Viv for Viventium)...`
  - this did not match the current tracked/source-of-truth main agent prompt
- the user-facing continuity controls were still split on that install:
  - `Reference saved memories` was on
  - `Recall all conversations` was off
- durable memory was still broken on that stale install:
  - an explicit memory-worthy prompt got an in-thread success reply:
    - user: `Remember this as a personal preference: my favorite color is teal. Reply with exactly SAVED.`
    - assistant: `SAVED`
  - but the durable-memory surfaces remained empty immediately afterward:
    - Mongo `memoryentries` remained `0`
    - the browser `Memories` panel still showed `0% used` and `No memories yet`
  - a brand-new conversation then failed the recovery check:
    - user: `What is my favorite color? Reply in one word.`
    - assistant: `Unknown`
- historical error logs on that install still contained:
  - `Error initializing memory writer Provider openai not supported`
- launcher/runtime logs on that install also still contained:
  - `Local RAG API not detected on port 8110; disabling conversation recall sync for this run`
- the straightforward Mongo probe for that account did not surface a matching visible user-scoped
  `keys` row in the expected collection, even though the UI showed `Connected` and chat execution
  worked

Interpretation:

- foundation-model connected-account chat execution was healthy
- conversation/message persistence was healthy
- durable memory and cross-conversation recall were not healthy on the stale install
- the browser showing `Connected` is not enough to claim durable memory is healthy
- a visible recall toggle is not enough to claim recall runtime/indexing is healthy
- the stale prompt and stale memory behavior came from the installed runtime/bundle state, not from
  the current tracked source alone

### Fresh isolated current-main findings

Used a fresh public clone in a new directory plus an isolated App Support root.

Verified:

- the parent-side component pin fix changed clean bootstrap behavior:
  - before the fix, fresh bootstrap pulled LibreChat ref `07c1960c...`
  - after the fix, fresh bootstrap pulled LibreChat ref `ba450451...`
- seeded main-agent truth in Mongo matched the current source:
  - prompt now begins with `You're Viv (Viventium). A cognitive brain...`
- seeded voice override truth in Mongo matched the current source:
  - `voice_llm_provider: anthropic`
  - `voice_llm_model: claude-haiku-4-5`
  - `voice_llm_model_parameters.thinking: false`
- `bin/viventium status` on the fresh isolated install now reports honest foundation-auth posture:
  - `Primary AI | Action Required | Connect OpenAI in Settings > Account > Connected Accounts`
  - it no longer falsely implies that a missing connected account is already configured

Observed remaining gaps on that fresh isolated run:

- cold first boot on the remote laptop was still materially long:
  - the modern playground reached `Running`
  - LibreChat API/frontend remained in `Starting` while the client build/finalization path was still
    running beyond the initial warm-up window
- durable memory on a fresh current-ref install is still not production-proven:
  - the clean browser pass proved registration/login and actionable connected-account guidance
  - but a real connected-account memory write + recovery pass has still not been completed on the
    fresh current-ref install
- conversation recall was still not live on that machine:
  - launcher/status reported local recall prerequisites were not satisfied
  - the machine did not have a local `ollama` binary available, so the local recall sidecar could
    not come up there

Interpretation:

- prompt freshness and voice-LLM seeding now follow current main on clean bootstrap
- status honesty for connected-account installs is fixed
- clean-machine first-boot latency is still a real product-quality concern
- local conversation recall still depends on shipping or provisioning its actual local embeddings
  runtime on that machine

### Root causes confirmed by this audit

1. Parent component pin drift was shipping stale nested product truth.
   - Fresh installs follow `components.lock.json`, not whatever newer nested checkout may exist on
     an owner machine.
   - A stale LibreChat ref therefore shipped the stale main-agent prompt and older runtime behavior
     even when the nested repo had already moved on locally.

2. Existing installs do not auto-heal just because tracked source changed.
   - The startup seed/upsert path can only heal from the bundle currently checked out on disk.
   - The old remote install kept the stale main-agent prompt and stale memory behavior until an
     explicit upgrade/reinstall refreshed the checked-out component ref.

3. Connected-account readiness and durable memory readiness are separate surfaces.
   - The remote synthetic user could chat successfully through a connected OpenAI account while
     still having zero durable memories and no cross-conversation recovery.

4. Local conversation recall availability still depends on local embeddings prerequisites.
   - A machine without the required local embeddings runtime cannot actually provide local recall,
     even if the broader install succeeds.

5. Clean-machine cold-start time is still a friction source on slower Macs.
   - Fresh users can wait through a long staged build before the API/frontend are actually ready.

## Helper protected-folder binding follow-up

Date: 2026-04-19

Automated verification:

Ran:

```bash
bash -n scripts/viventium/common.sh
bash -n scripts/viventium/install_macos_helper.sh
bash -n bin/viventium
uv run --with pytest pytest tests/release/test_macos_helper_install.py -q
uv run --with pytest pytest tests/release/test_cli_upgrade.py -k 'test_maybe_install_macos_helper_accepts_explicit_no_launch_override or test_cli_usage_documents_status_bar_and_shell_init_commands' -q
```

Result:

- syntax checks passed
- `test_macos_helper_install.py`: `8 passed`
- targeted CLI helper/status-bar slice: `2 passed`

Coverage added:

- helper install now prefers the supported safe public checkout when invoked from a checkout under
  `~/Documents`
- generated helper-config and helper launcher scripts no longer rebind the helper back to a
  protected-folder checkout in that scenario
- the `status-bar` config-writing path uses the same resolver as helper install

Live-machine verification:

Machine:

- local macOS install with:
  - current working checkout under `~/Documents/<repo>`
  - supported public checkout present at `~/viventium`

Ran:

```bash
bin/viventium install-helper --no-launch
bin/viventium status-bar on
```

Observed:

- helper install logged:
  - `Using public-safe helper runtime checkout: ~/viventium`
- `~/Library/Application Support/Viventium/helper-config.json` now stores:
  - `repoRoot: ~/viventium`
- `~/Library/Application Support/Viventium/helper-scripts/viventium-stack.sh` now launches:
  - `~/viventium/bin/viventium`
- the helper binding no longer points at the checkout under `~/Documents/<repo>`

## Helper protected-folder recurrence follow-up

Date: 2026-05-02

Runtime evidence:

- The installed helper config can remain stale after the source-level installer fix:
  - `helper-config.json` may still store `repoRoot: ~/Documents/<repo>`
  - `helper-scripts/viventium-stack.sh` may still launch `~/Documents/<repo>/bin/viventium`
- The installed app bundle must be verified independently from source:
  - an unsigned assembled helper bundle does not provide the stable `ai.viventium.helper` app
    identity that the source `Info.plist` declares

Root cause:

- The April fix only repaired helper install/status-bar config writes.
- Already-installed helper state still needed a runtime self-heal path.
- Detached helper start/stop still trusted the generated App Support wrapper, so a stale wrapper
  could preserve the protected checkout path even after config repair.

Product fix:

- `ViventiumHelper` now self-heals a protected-folder `repoRoot` on launch when a supported safe
  public checkout is available.
- If no safe checkout is available, helper install fails closed and the helper blocks
  start/stop/backup actions with guidance instead of launching from the protected checkout.
- Swift helper protected-folder checks now resolve symlinks for parity with the shell resolver and
  macOS TCC's real-path behavior.
- Detached helper start/stop now executes the healed `repoRoot/bin/viventium` directly with the
  helper environment that the wrapper used to provide.
- Helper install still writes the wrapper for compatibility, but stale wrapper contents no longer
  own detached start/stop.
- The assembled helper app bundle is locally code signed with `ai.viventium.helper` after
  packaging so the installed bundle identity matches the product `Info.plist`; this is packaging
  hygiene, while avoiding protected-folder runtime roots remains the actual TCC prompt prevention.

Automated verification:

Ran:

```bash
swiftc -parse-as-library -sdk "$(xcrun --show-sdk-path)" -target "$(uname -m)-apple-macosx13.0" apps/macos/ViventiumHelper/Sources/ViventiumHelper/ViventiumHelperApp.swift -o /tmp/ViventiumHelper-check
bash -n scripts/viventium/common.sh
bash -n scripts/viventium/install_macos_helper.sh
bash -n bin/viventium
./scripts/viventium/build_macos_helper_fallback.sh
uv run --with pytest pytest tests/release/test_macos_helper_install.py -q
uv run --with pytest pytest tests/release/test_cli_upgrade.py -k 'test_maybe_install_macos_helper_accepts_explicit_no_launch_override or test_cli_usage_documents_status_bar_and_shell_init_commands' -q
```

Result:

- Swift compile passed with the existing Swift 6 sendable-capture warning elsewhere in the helper
  source.
- shell syntax checks passed.
- helper prebuilt artifact and `source.sha256` were regenerated from current helper sources.
- `test_macos_helper_install.py`: `9 passed`
- targeted CLI helper/status-bar slice: `2 passed`
- a temporary real helper install verified that `codesign -dv` reports
  `Identifier=ai.viventium.helper` and no longer reports an unsigned app bundle.

Live-machine verification:

Ran:

```bash
bin/viventium install-helper --no-launch
bin/viventium status-bar on
open -g ~/Applications/Viventium.app
bin/viventium stop
bin/viventium status
```

Observed:

- helper install logged:
  - `Using public-safe helper runtime checkout: ~/viventium`
- live `helper-config.json` stores:
  - `repoRoot: ~/viventium`
- live `helper-scripts/viventium-stack.sh` contains the compatibility-wrapper header and launches:
  - `~/viventium/bin/viventium`
- `codesign -dv ~/Applications/Viventium.app` reports:
  - `Identifier=ai.viventium.helper`
  - sealed resources and bound `Info.plist` entries
- launching the helper did not start the old protected checkout; it logged:
  - `Auto-start blocked; split-workspace state detected`
- the old Documents-owned runtime was stopped through the CLI, leaving only the signed helper app
  process active and no runtime child processes under `~/Documents/<repo>`.

## Active developer checkout follow-up

Date: 2026-05-02

Runtime evidence:

- A live stack can be healthy while being owned by a different checkout than the one under active
  development.
- The prior protected-folder fix intentionally preferred `~/viventium` for helper binding, which
  avoided repeated macOS folder prompts but made local source fixes invisible to helper-launched
  runtime processes.

Product fix:

- Added `bin/viventium runtime-checkout`:
  - `status` shows the active setting, helper binding, live stack owner, and command checkout
  - `use --this --allow-protected-folder` explicitly selects a developer checkout under a macOS
    protected folder
  - `clear` restores automatic checkout resolution
- The setting is machine-local App Support state and does not touch repo history, repo files,
  generated runtime config, snapshots, or database state.
- Helper install/status-bar config writes now honor the active checkout setting.
- The helper config records the explicit protected-folder acknowledgement so the helper does not
  silently rebind an intentional developer checkout back to `~/viventium`.
- Helper refresh relaunches the status-bar helper after updating the binding.
- Start/stop/helper commands invoked through a stale checkout re-exec through the active checkout.
- Re-execed commands use the active checkout's own component lock file.
- Re-execed commands reset inherited lock-file environment so the active checkout cannot
  accidentally read the caller checkout's component lock.
- The explicit active-checkout setting outranks LaunchAgent helper runtime environment defaults.
- Disabled optional memory-hardening cleanup warns and continues when a partial checkout lacks the
  cleanup helper; explicitly enabled memory hardening still fails closed if its helper is missing.

Verification plan:

```bash
bash -n scripts/viventium/common.sh
bash -n scripts/viventium/install_macos_helper.sh
bash -n bin/viventium
swiftc -parse-as-library -sdk "$(xcrun --show-sdk-path)" -target "$(uname -m)-apple-macosx13.0" apps/macos/ViventiumHelper/Sources/ViventiumHelper/ViventiumHelperApp.swift -o <temp>/ViventiumHelper-check
./scripts/viventium/build_macos_helper_fallback.sh
uv run --with pytest pytest tests/release/test_macos_helper_install.py -q
uv run --with pytest pytest tests/release/test_cli_upgrade.py -q
```

Verification result:

- shell syntax checks passed
- Swift helper compile passed with the existing Swift 6 sendable-capture warning elsewhere in the
  helper source
- helper prebuilt artifact and `source.sha256` were regenerated from current helper sources
- `test_macos_helper_install.py`: `10 passed`
- `test_cli_upgrade.py` plus helper install tests after the hardening follow-up: `45 passed`

Second-opinion review:

- ClaudeViv confirmed the RCA and the non-destructive active-checkout design.
- Initial review findings addressed before applying the live setting:
  - helper refresh now relaunches the status-bar helper after rebinding
  - active-checkout re-exec no longer forwards the caller checkout's component lock file
  - re-exec coverage now includes stop and uninstall-helper in addition to start/launch/helper
    binding commands
  - helper refresh uses the active checkout's installer when the selected checkout differs from the
    caller checkout
  - hand-edited protected active-checkout settings without explicit acknowledgement are ignored with
    a helper log line instead of silently healing to another checkout
- Follow-up review findings addressed before final validation:
  - re-exec now resets inherited `VIVENTIUM_COMPONENTS_LOCK_FILE` and passes the active checkout's
    lock file explicitly
  - helper checkout resolution now lets the explicit active-checkout setting outrank LaunchAgent
    `VIVENTIUM_HELPER_RUNTIME_REPO_ROOT`
  - MCP OAuth warmup now has token-presence caching, negative-path coverage, and skips the second
    setup-data read when no warmup was attempted
  - a CLI integration test proves re-exec reaches the active checkout with the active checkout's
    lock file in argv and environment

Live-machine setting verification:

Ran:

```bash
bin/viventium runtime-checkout use --this --allow-protected-folder
bin/viventium runtime-checkout status
viventium runtime-checkout status
codesign -dv ~/Applications/Viventium.app
```

Observed:

- active runtime checkout points at the current developer checkout under `~/Documents/<repo>`
- helper config points at the same developer checkout and records `allowProtectedRepoRoot: true`
- helper log records an intentionally protected developer checkout and split-workspace auto-start
  block
- installed helper bundle remains signed with `Identifier=ai.viventium.helper`
- live stack owner still points at the prior installed checkout until an intentional stop/start

## Helper and MS365 MCP status follow-up

Date: 2026-05-02

Runtime evidence:

- The live stack was owned by the installed checkout while the active fixes were in another working
  checkout, so helper-launched runtime processes did not include current local source changes.
- With Docker down or warming, the MS365 MCP listener was absent and LibreChat logged repeated
  `fetch failed` connection attempts for `ms-365`.
- After starting from the active checkout with Docker running, core endpoints returned healthy
  responses and the MS365 `/mcp` endpoint returned an HTTP auth challenge, proving the listener was
  alive.
- The helper menu could still report `Start`/`Stopped` because helper core health required every
  managed optional service URL to respond.
- The MCP connection-status API returned `disconnected` for a user with stored MS365 refresh-token
  records because OAuth MCPs were not warmed from stored tokens during status polling.

Product fix:

- Helper Running/Stopped state now depends on core surfaces only: LibreChat API, LibreChat
  frontend, and the modern playground.
- Managed optional sidecars remain part of stop convergence, but no longer decide whether the app is
  running.
- `bin/viventium status` now probes Google/MS365 MCP endpoints separately and treats an HTTP auth
  challenge as a live listener.
- Local MCP endpoints that are expected to start now show `Starting` while a CLI start command is
  active and `Action Required` after startup has completed with no listener.
- The MCP status route now warms OAuth-backed MCP servers when the user already has a usable stored
  access or refresh token.
- OAuth warmup is bounded with cooldown/in-flight checks and short token-presence caching so
  mounted status polling does not repeatedly hit token storage.
- The browser MCP status query refreshes periodically while mounted so recovered local MCP listeners
  and warmed OAuth connections are reflected without a full page reload.

Verification result:

```bash
uv run --with pytest --with PyYAML pytest tests/release/test_install_summary.py -q
uv run --with pytest pytest tests/release/test_macos_helper_install.py -q
npm run test -- server/routes/__tests__/mcp.spec.js --runInBand
npm run test -- server/services/MCP.spec.js --runInBand
swift build -c release --package-path apps/macos/ViventiumHelper
./scripts/viventium/build_macos_helper_fallback.sh
git diff --check
```

Observed:

- install-summary tests: `31 passed`
- CLI/helper release tests: `45 passed`
- MCP route tests: `82 passed`
- MCP service tests: `35 passed`
- frontend typecheck was attempted after the MCP query refresh change; it still fails on existing
  repo-wide TypeScript drift outside this change area
- Swift helper build passed with the pre-existing Swift 6 sendable-capture warning
- helper prebuilt artifact and `source.sha256` were regenerated after the helper health fix
- `bin/viventium status` reports Google Workspace MCP and Microsoft 365 MCP as `Running`
- direct local probes returned `200` for frontend/API/playground and `401` auth challenges for
  Google Workspace MCP and Microsoft 365 MCP `/mcp`, which is the expected live-listener signal
- `bin/viventium runtime-checkout status` reports the active checkout, helper checkout, live stack
  owner, and command checkout all aligned to the developer checkout
- the QA account's live `GET /api/mcp/connection/status/ms-365` response reports
  `connectionStatus: connected` and `requiresOAuth: true`
- live helper menu reports `Running` with a `Stop` action while the stack is up
