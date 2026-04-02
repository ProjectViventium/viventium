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
  - confirm `http://localhost:3180/health` and `http://localhost:3190` both return `200` before treating the install as healthy
- Cold-start note:
  - the installer now waits up to `1800s` for first-run health and prints periodic progress while LibreChat builds
  - if that budget still expires, it prints the recent `helper-start.log` tail plus the configured service summary so the user can tell whether the stack is still compiling or actually stuck
- Current status: `viventium_v0_4/viventium-librechat-start.sh` now prefers the direct-managed fallback for detached/helper launches and rebuild-required runs.

### Telegram says `Failed to reach Viventium. Please retry.`
- Root cause: the Telegram bridge was starting before a LibreChat-backed install had actually finished bringing up `3180`, so early Telegram requests were racing the cold-start LibreChat health check instead of waiting for it.
- Symptom: Telegram auth is fine, but the bot returns the generic connection fallback during cold start or first-run rebuilds.
- Fix:
  - start the LibreChat-backed Telegram bridge only after `http://localhost:3180/health` is healthy
  - if the stack is still warming, confirm LibreChat health first instead of rotating Telegram tokens
- Current status: the launcher now defers `VIVENTIUM_TELEGRAM_BACKEND=librechat` startup until LibreChat API health is up.

### Telegram replies include `stream_preview_task ... not associated with a value`
- Root cause: nested stream flush helper in `TelegramVivBot/bot.py` wrote to `stream_preview_task` without declaring it `nonlocal` under async flush paths.
- Symptom: partial bot reply appears, then bot appends a Python local-variable error string.
- Fix:
  - Pull latest `feature/viventium_alpha_18`.
  - Restart launcher: `./viventium_v0_4/viventium-librechat-start.sh --modern-playground --restart --skip-skyvern`
  - Ensure only one Telegram bot process is running (`pgrep -af 'TelegramVivBot.*bot.py'`).
- Current status: fixed with regression tests in `viventium_v0_4/telegram-viventium/tests/test_bot_stream_preview.py`.

### Modern LiveKit says `I'm having trouble reaching the service right now. Please try again.`
- Root cause: the voice call was reaching LibreChat, but a dedicated voice override could still rewrite the run onto a different provider with no server-side credential configured. That produced downstream `no_user_key` initialization failures even though the main agent model was healthy.
- Symptom: STT/TTS may work, but the voice reply falls back to the generic service-trouble message.
- Fix:
  - new installs should leave the main-agent voice override unset unless the installer explicitly configured a dedicated fast voice provider
  - when a dedicated voice provider is configured, runtime must choose a model for that provider instead of reusing a stale shipped model from another provider
  - if the alternate voice provider has no server credential, log the skip clearly and keep the main model/provider
- Current status: the shipped source-of-truth bundle now leaves the main voice override unset by default, runtime no longer reuses stale voice models across provider changes, and `voiceLlmOverride` now falls back cleanly to the main model when the alternate provider is not actually configured.

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
