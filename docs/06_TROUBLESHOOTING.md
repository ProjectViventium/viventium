# Troubleshooting

This is the shared troubleshooting index. For stack-specific detail, see:
- v0.3: `viventium_v0_3_py/docs/06_TROUBLESHOOTING.md`
- v0.4: `viventium_v0_4/docs/` (see `VIVENTIUM_STATUS.md` and `EXPECTED_BEHAVIOR.md`)

## Common Issues

### LiveKit ports already in use
- Default ports: 7880 (WS/HTTP), 7881, 7882/udp
- Fix: stop existing containers or set different ports.

### Docker not running
- Start Docker Desktop before running any start scripts.

### MS365 MCP auth fails
- Ensure `MS365_MCP_CLIENT_ID`, `MS365_MCP_CLIENT_SECRET`, `MS365_MCP_TENANT_ID` are set.
- v0.3 HTTP mode uses Docker + callback server on port 3002.

### Voice calls not connecting (browser)
- If LiveKit runs in Docker, set `LIVEKIT_NODE_IP=127.0.0.1` in `.env`.

### Python dependencies missing
- Install uv and run `uv sync --all-extras --dev` in the target stack.

### Launcher shows `Unknown arg:` with blank-looking spaces
- Root cause: invisible Unicode whitespace (commonly non-breaking spaces from copy/paste) was passed as a real CLI argument.
- Quick fix: retype the command manually, or run `./viventium_v0_4/viventium-librechat-start.sh --help` first to validate parsing.
- Note: `viventium_v0_4/viventium-librechat-start.sh` now normalizes common Unicode space variants before option parsing.

### Launcher fails with `START_*: unbound variable`
- Root cause: launcher runs with `set -u` and hit a stale/removed feature variable reference.
- Fix: sync help/options/preflight checks and remove stale references (or default-gate with `${VAR:-...}`).
- Current status: stale `START_VM_RUNTIME` reference was removed from `viventium_v0_4/viventium-librechat-start.sh`.

### Launcher fails with `...[@]: unbound variable`
- Root cause: `set -u` + empty bash array expanded as `"${arr[@]}"`.
- Fix: guard with a length check before expansion and branch the command call for empty/non-empty args.
- Current status: bootstrap arg-array expansion in `viventium_v0_4/viventium-librechat-start.sh` was fixed.

### Launcher says scheduling MCP path missing and loops bootstrap
- Root cause: some branches do not include `LibreChat/viventium/MCPs/scheduling-cortex`.
- Fix: auto-disable scheduling MCP for that run instead of blocking full stack startup.
- Current status: launcher now warns and disables scheduling MCP if that directory is absent.

### Scheduling Cortex seems "up" but MCP calls fail
- Symptom: HTTP `406 Not Acceptable` when calling `http://localhost:7010/mcp`.
- Root cause: Scheduling Cortex MCP in streamable-http mode requires `Accept: application/json, text/event-stream`.
- Verify:
  - `curl -s http://localhost:7010/health` should return `{\"status\":\"ok\"}`.
  - Use MCP initialize with both accept types:
    `curl -H 'Accept: application/json, text/event-stream' -H 'Content-Type: application/json' -d '{...initialize...}' http://localhost:7010/mcp`

### LibreChat crashes with `JwtStrategy requires a secret or key`
- Root cause: `viventium_v0_4/LibreChat/.env` existed but missed required JWT secrets.
- Fix: launcher now auto-generates and persists local dev values for `JWT_SECRET`, `JWT_REFRESH_SECRET`, `CREDS_KEY`, and `CREDS_IV` when missing.
- Current status: one-click local start no longer requires manual secret generation.

### LibreChat wrapper fails because `mongosh` is missing
- Root cause: `LibreChat/viventium-start.sh` path expects `mongosh`.
- Fix: launcher detects missing `mongosh` and automatically switches to a direct startup fallback.
- Current status: local stack can start without `mongosh` installed.

### Launcher starts but MongoDB is unreachable
- Root cause: local `MONGO_URI` points to `localhost` but no MongoDB is running.
- Fix: launcher auto-starts Docker container `viventium-mongodb` and waits for readiness.
- Current status: MongoDB bootstrap is automatic for local dev URIs.

### Firecrawl `/health` returns 404
- Root cause: local Firecrawl image may expose health via `/` banner instead of `/health`.
- Fix: launcher now validates Firecrawl with multiple signals (`/health`, `/` banner, and expected Docker container).
- Current status: health checks no longer fail on `/health`-only assumptions.

### SearXNG looks unready on first boot even though web search was enabled
- Root cause: a cold SearXNG container can answer its local root page before the first live
  `/search?...` request returns quickly, so installer/startup checks that probe a real search query
  can create false negatives on clean Macs.
- Fix: installer/startup readiness now probes the local SearXNG root page with a longer timeout and
  retry window.
- Current status: if web search is enabled, first-run readiness should no longer fail just because
  upstream search engines are still warming.

### Skyvern starts with unhealthy postgres and keeps restarting
- Root cause: local Skyvern dependency instability on some machines/platform combinations.
- Fix: launcher now cleans up Skyvern containers immediately on failed startup instead of leaving restart loops.
- Current status: stack continues cleanly; use `--skip-skyvern` when Skyvern is not required.

### Voice worker prints `Health endpoint unavailable on 0.0.0.0:8000`
- Root cause: the LiveKit worker health endpoint defaults to port `8000`, which is already used by Google Workspace MCP in this stack.
- Impact: warning-only in current local setup; worker can still register and handle jobs.
- Current status: treat as non-blocking unless voice calls fail.

### `3090` loads blank/white after pull
- Root cause: LibreChat backend crashes during startup, commonly from dependency drift (`Cannot find module '@google/genai'`) or stale `packages/*/dist` artifacts after branch updates.
- Symptom: frontend dev server is up, but the app page is blank or API health fails.
- Fix: run a clean restart:
  - `./viventium_v0_4/viventium-librechat-start.sh --stop`
  - `./viventium_v0_4/viventium-librechat-start.sh --modern-playground --restart`
- Current status: launcher now auto-heals Node dependencies and rebuilds LibreChat workspace packages before startup.

### Fresh install auto-start launches `3300` but not `3180` / `3190`
- Root cause: the helper/install path launches the stack in detached mode. On first run, that path can require LibreChat package rebuilds, and backgrounding the extra `LibreChat/viventium-start.sh` wrapper could leave LibreChat stuck behind its internal build stage even though the helper had already returned.
- Symptom: the modern playground on `3300` responds, but the LibreChat API/frontend on `3180` / `3190` never bind.
- Fix:
  - use the launcher-managed direct LibreChat startup path for detached launches and first-run package rebuilds
  - in that direct fallback, keep backend and frontend supervised by the same shell instead of
    `exec`-ing the frontend dev server
  - confirm `http://localhost:3180/health` and `http://localhost:3190` both return `200` before treating the install as healthy
- Cold-start note:
  - the installer now waits up to `1800s` for first-run health and prints periodic progress while LibreChat builds
  - if that budget still expires, it prints the recent `helper-start.log` tail plus the configured service summary so the user can tell whether the stack is still compiling or actually stuck
- Current status: `viventium_v0_4/viventium-librechat-start.sh` now prefers the direct-managed fallback for detached/helper launches and rebuild-required runs, and that fallback now backgrounds both backend and frontend so the shell continues supervising LibreChat after startup.

### Telegram says `Failed to reach Viventium. Please retry.`
- Root cause:
  - early-start case: the Telegram bridge was starting before a LibreChat-backed install had actually finished bringing up `3180`, so early Telegram requests were racing the cold-start LibreChat health check instead of waiting for it
  - detached-runtime case: a detached direct LibreChat launch could later lose the real API child while a parent `npm`/`nodemon` process stayed alive, leaving Telegram healthy but `localhost:3180` unreachable
- Symptom: Telegram auth is fine, but the bot returns the generic connection fallback during cold start, first-run rebuilds, or after the local LibreChat API silently drops out of a detached run.
- Fix:
  - start the LibreChat-backed Telegram bridge only after `http://localhost:3180/health` is healthy
  - keep the detached direct LibreChat fallback supervising both backend and frontend processes instead of turning the launcher shell into the frontend process
  - run a detached LibreChat API watchdog that restarts the backend when API health drops even though parent dev processes are still present
  - if the stack is still warming, confirm LibreChat health first instead of rotating Telegram tokens
- Current status: the launcher now defers `VIVENTIUM_TELEGRAM_BACKEND=librechat` startup until LibreChat API health is up, detached direct LibreChat launches no longer `exec` the frontend in a way that can strand Telegram behind a dead `3180` listener, and detached runs now include an API watchdog for the dead-child/live-parent failure mode.
 - Current status on clean installs: if LibreChat is still building, the launcher keeps retrying the Telegram bridge in the background and `bin/viventium status` reports `Telegram Bridge | Starting` until that handoff completes.

### Telegram says `Temporarily unable to download this video from Telegram. Please retry.`
- Root cause:
  - Telegram itself rejected the bot's `getFile` request before download because the file exceeded the hosted Bot API download limit
  - older bridge code collapsed Telegram's specific `File is too big` error into a generic download failure
- Fix:
  - map Telegram's oversize exception to an explicit oversize media error instead of a generic retry-only message
  - for large Telegram videos that truly need to work, either point the bot at an external local Telegram Bot API server with `integrations.telegram.bot_api_origin` / base URLs, or enable the Viventium-managed same-Mac server under `integrations.telegram.local_bot_api`
  - managed local Bot API mode also needs `api_id` / `api_hash` plus the `telegram-bot-api` binary available on the Mac
  - if local Bot API mode is enabled, Telegram media size policy now comes from `integrations.telegram.max_file_size_bytes` instead of a hidden bot default

### Telegram shows `🎤 Transcription: error: ...`
- Root cause: Telegram media ingestion treated raw transcription exceptions as if they were successful transcript text, then forwarded that raw `error:` string into LibreChat as the user's message.
- Symptom:
  - Telegram visibly prints `🎤 Transcription:` followed by an `error:` string
  - the next bot reply may be the generic LibreChat connection fallback because the garbage transcript text was submitted as chat input
- Fix:
  - use structured transcription results for voice notes and video notes instead of raw `error:` strings
  - if transcription fails, send one clean Telegram media error and stop before chat submission
  - keep the shared Telegram downloader responsible for file-size gating so oversized media fails honestly before transcription
- Current status: failed Telegram voice/video transcription no longer renders as transcript text and no longer gets forwarded into LibreChat as user input.

### Telegram replies include `stream_preview_task ... not associated with a value`
- Root cause: nested stream flush helper in `TelegramVivBot/bot.py` wrote to `stream_preview_task` without declaring it `nonlocal` under async flush paths.
- Symptom: partial bot reply appears, then bot appends a Python local-variable error string.
- Fix:
  - Pull latest `feature/viventium_alpha_18`.
  - Restart launcher: `./viventium_v0_4/viventium-librechat-start.sh --modern-playground --restart --skip-skyvern`
- Ensure only one Telegram bot process is running (`pgrep -af 'TelegramVivBot.*bot.py'`).
- Current status: fixed with regression tests in `viventium_v0_4/telegram-viventium/tests/test_bot_stream_preview.py`.

### Telegram voice note says `FFMPEG is not installed or not in PATH`
- Root cause: Telegram voice notes arrive as non-WAV media, and the local `pywhispercpp` STT path
  uses `ffmpeg` to decode them before transcription. Telegram video-note extraction also requires
  `ffmpeg`.
- Symptom: Telegram returns `error: Error processing audio file: FFMPEG is not installed or not in PATH...`
- Fix:
  - Run `bin/viventium install` or `bin/viventium upgrade` so preflight can install Telegram media prerequisites.
  - If you are starting directly from an older install, restart through `bin/viventium start` or
    `./viventium_v0_4/viventium-librechat-start.sh` so the Telegram launcher can self-heal the missing
    `ffmpeg` dependency.
- Current status: when Telegram is enabled, preflight now installs `ffmpeg` automatically and the
  Telegram launcher refuses to start a partially broken bridge without it.

### Modern LiveKit says `I'm having trouble reaching the service right now. Please try again.`
- Root cause: the voice call was reaching LibreChat, but a hidden machine-level fast-voice LLM route
  could still rewrite the run onto a different provider than the agent-visible selection. That
  produced downstream provider credential failures even though the main agent model was healthy.
- Symptom: STT/TTS may work, but the voice reply falls back to the generic service-trouble message.
- Fix:
  - the agent primary model/provider and optional explicit Voice Call LLM are the only LLM selectors
    that may affect live calls
  - when the Voice Call LLM is unset, runtime must inherit the agent primary model/provider
  - legacy machine-level `voice.fast_llm_provider` / `VIVENTIUM_VOICE_FAST_LLM_PROVIDER` values
    must not rewrite call LLM selection
  - if an explicit Voice Call LLM lacks a required server credential, log the skip clearly and keep
    the agent primary model/provider
- Current status: live call LLM selection now ignores the legacy machine fast-voice route, so old
  config values no longer override the agent-visible Voice Call LLM behavior.
- Migration note: if an older install intentionally used `voice.fast_llm_provider`, move that choice
  into the agent `Voice Chat Model` / `voice_llm_provider` + `voice_llm_model` fields instead.

### Local modern playground times out on signal after remote access is enabled
- Root cause: localhost modern-playground sessions were incorrectly inheriting the public LiveKit
  WSS URL after remote-access state was prepared.
- Symptom:
  - the local voice tab loads, but `Start chat` times out
  - browser console shows signal-connection or `/rtc/validate` timeouts against the public
    `wss://livekit...` hostname
- Fix:
  - keep localhost callers on `ws://localhost:7888`
  - return the public LiveKit URL only when `api/connection-details` sees the configured public
    playground origin
  - do not globally overwrite localhost-facing `NEXT_PUBLIC_LIVEKIT_URL` when preparing the remote
    edge
- Current status: fixed on `codex/remote-modern-playground-access`; fresh localhost voice launches
  now connect and transcript replies work again.

### Public remote link still uses `sslip.io`
- Root cause: `public_https_edge` can auto-bootstrap a zero-cost public hostname from the current
  public IP, but `sslip.io` hostnames change when the home public IP changes.
- Symptom:
  - the public app/playground links work, but they are not the durable bookmarkable production
    answer
- Fix:
  - keep `runtime.network.remote_call_mode: public_https_edge` (or `custom_domain`)
  - set explicit custom-domain origins:
    - `public_client_origin`
    - `public_api_origin`
    - `public_playground_origin`
    - `public_livekit_url`
  - point those DNS records at the current public IP and restart Viventium so Caddy can provision
    real certificates for the stable hostnames
- Current status: `sslip.io` remains the bootstrap fallback; stable custom-domain access is the
  remaining operator step.

### Public remote access worked, then stopped a few hours later
- Root cause: some routers grant UPnP/NAT-PMP mappings with finite leases instead of permanent
  mappings.
- Symptom:
  - the public domain still resolves
  - outside devices stop loading the app or playground
- Fix:
  - keep Viventium running so the mapping refresh worker can renew those leases automatically
  - run `bin/viventium start` again if the router dropped the mappings after a restart or sleep
  - if the router refuses renewal entirely, use manual forwarding for `80/tcp`, `443/tcp`,
    `7889/tcp`, `7890/udp`, and `5349/tcp`

### Public startup aborts saying the router already forwards `80` or `443`
- Root cause:
  - the router still has a stale UPnP mapping from an earlier Viventium run, but that mapping now
    points to a dead local target port on this same Mac
- Symptom:
  - startup fails during `Preparing secure remote access topology`
  - the launcher logs a message like:
    - `Router already forwards TCP 80 to <lan-ip>:<old-port>; cannot reuse it for Viventium ...`
- Fix:
  - current Viventium startup now reclaims dead same-machine mappings automatically
  - if the conflicting mapping points to a live service or a different machine, treat that as a
    real conflict and clear the router rule or switch to manual forwarding intentionally
### Public remote access fails because ports `80` / `443` already belong to another LAN device
- Root cause: router port-forward ownership conflict. Viventium cannot safely steal those public
  ports from another machine already using them.
- Symptom:
  - startup or install logs `Router already forwards TCP 80 ...`
  - local Viventium keeps running
  - `bin/viventium status` shows `Remote Access: Action Required`
- Fix:
  - move the existing router forwards off that other LAN host, or disable them there
  - or choose a different remote-access mode such as `tailscale_tailnet_https`
  - rerun `bin/viventium start` after the router conflict is resolved
- Current status: remote-access setup failure is now non-fatal to the local install; the exact
  blocker is persisted in `public-network.json` and surfaced by `bin/viventium status`.

### Clean macOS helper install prints Swift build errors before continuing
- Root cause: some clean macOS CommandLineTools environments can fail SwiftPM manifest linking for
  the menu-bar helper even when the shipped helper binary is already valid.
- Symptom:
  - first-run helper install prints Swift or `Package.swift` build/linker errors
  - helper still succeeds only after a fallback path
- Fix:
  - current public installer behavior now prefers the shipped matching
    `apps/macos/ViventiumHelper/prebuilt/ViventiumHelper-universal` binary by default
  - only force local helper builds if you are actively developing the helper and intentionally set
    `VIVENTIUM_HELPER_FORCE_LOCAL_BUILD=1`
- Current status: clean end-user installs should no longer depend on opportunistic local helper
  source builds.

### Public remote test fails only when a VPN is running on the host Mac
- Root cause: a full-tunnel VPN on the same Mac that is serving the public edge can rewrite the
  route to the host's own public IP and break same-machine "pretend I am remote" tests.
- Symptom:
  - outside devices may still work
  - the serving Mac itself times out or shows odd SSL/proxy errors when it opens the public domain
- Fix:
  - turn the VPN off on the serving Mac while Viventium is acting as the public edge
  - do the real acceptance test from a separate device on cellular or another external network

### Public app loads but voice does not connect from outside the house
- Root cause: browser HTTPS is up, but LiveKit media/TURN ports are not reachable.
- Fix:
  - confirm the public edge still owns `7889/tcp`, `7890/udp`, and `5349/tcp`
  - if UPnP/NAT-PMP renewal is not stable on the router, forward those ports manually
  - keep localhost callers on `ws://localhost:7888`; only remote callers should use the public
    LiveKit URL

### Capacity: how many simultaneous users?
- There is no hard-coded user cap in this local dev launcher.
- Voice gateway worker runs with LiveKit `WorkerOptions` defaults (`job_executor_type=process`, dev `load_threshold=inf`, `job_memory_limit_mb=0`), so practical limits are machine/latency/rate-limit bound.
- On this local Mac setup (64 GB RAM), use this as a safe starting point:
  - Interactive voice sessions: start with `2-4` concurrent users, then scale while watching latency and memory.
  - Text-only/chat-heavy usage: start with `10-20` concurrent users, then validate with load tests.
- For distribution: treat local dev mode as functional testing, not production capacity. Run dedicated load tests before publishing user limits.

## Quick Checks

- v0.4: `viventium_v0_4/viventium-librechat-start.sh --help`
- v0.3: `viventium_v0_3_py/start_all.sh --help`
- v0.4 proof endpoints:
  - Isolated profile:
    - `curl -s -o /dev/null -w "%{http_code}" http://localhost:3180/health`
    - `curl -s -o /dev/null -w "%{http_code}" http://localhost:3190`
    - `curl -s -o /dev/null -w "%{http_code}" http://localhost:3300`
    - Real call-flow proof:
      - open LibreChat on `3190`
      - start a call from an agent conversation
      - confirm the returned `playgroundUrl` opens on `3300`, not `3000`
      - if browser automation shows `NotAllowedError`, treat that as a microphone-permission issue, not a runtime failure
  - Compat profile:
    - `curl -s -o /dev/null -w "%{http_code}" http://localhost:3080/health`
    - `curl -s -o /dev/null -w "%{http_code}" http://localhost:3090`
    - `curl -s -o /dev/null -w "%{http_code}" http://localhost:3000`
