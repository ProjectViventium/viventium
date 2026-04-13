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
