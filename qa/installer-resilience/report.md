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
