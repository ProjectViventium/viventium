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
