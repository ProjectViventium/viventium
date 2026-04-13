# MCPs (Model Context Protocol)

**Purpose**: Define requirements and learnings for MCP integration across v0.3 and v0.4.

---

## Requirements

1. **Non-blocking tool access**
   - MCP calls must never block the main agent response.
   - Failures must degrade gracefully.

2. **Multi-user auth support**
   - MS365 must support OAuth flows with per-user tokens.
   - Google Workspace must support OAuth with user-specific credentials.

3. **Transport flexibility**
   - Support HTTP/streamable HTTP for server mode.
   - Support STDIO for local subprocess mode.

4. **Configuration by environment**
   - All secrets and endpoints must be configurable via `.env`.
   - No hardcoded credentials in code or docs.

---

## Specifications

### MS365 MCP

- Server config: `viventium_v0_3_py/viventium_v1/backend/brain/tools/mcp/servers/ms365.yaml`
- Default transport: `streamable-http`
- Required env vars:
  - `MS365_MCP_CLIENT_ID`
  - `MS365_MCP_CLIENT_SECRET`
  - `MS365_MCP_TENANT_ID`
- URLs (overridable):
  - `MS365_MCP_SERVER_URL`
  - `MS365_MCP_AUTH_URL`
  - `MS365_MCP_TOKEN_URL`
- OAuth callback:
  - `MS365_MCP_CALLBACK_PORT` (default 3002)
  - `MS365_MCP_REDIRECT_URI`

### Google Workspace MCP

- Server code: `viventium_v0_4/MCPs/google_workspace_mcp/`
- Default URL: `http://localhost:8000/mcp`
- **Required env vars**:
  - `GOOGLE_OAUTH_CLIENT_ID` - Google Cloud Console OAuth 2.0 Client ID
  - `GOOGLE_OAUTH_CLIENT_SECRET` - Google Cloud Console OAuth 2.0 Client Secret
  - `MCP_ENABLE_OAUTH21` - Set to `true` for OAuth 2.1 mode (required for LibreChat integration)
- Optional env vars:
  - `GOOGLE_WORKSPACE_MCP_URL`
  - `GOOGLE_WORKSPACE_MCP_AUTH_URL`
  - `GOOGLE_WORKSPACE_MCP_TOKEN_URL`
  - `GOOGLE_WORKSPACE_MCP_SCOPE`
  - `GOOGLE_CLIENT_SECRET_PATH` (service account JSON path for local auth flows)

### YouTube Transcript MCP (Utility)

- Reference docs: `viventium_v0_4/MCPs/yt_transcript/`
- Upstream server: `jkawamoto/mcp-youtube-transcript` (see README for `uvx` usage)

### v0.3 Integration (Legacy)

- Launcher: `viventium_v0_3_py/start_all.sh`
- HTTP mode uses Docker compose: `viventium_v0_3_py/docker/ms365-mcp/docker-compose.yml`

### v0.4 Integration

- Launcher: `viventium_v0_4/viventium-librechat-start.sh`
- Local MS365 compose: `viventium_v0_4/docker/ms365-mcp/docker-compose.yml`
- MCP server code:
  - `viventium_v0_4/MCPs/ms-365-mcp-server`
  - `viventium_v0_4/MCPs/google_workspace_mcp`
- LibreChat MCP configs live in the v0.4 stack (see `viventium_v0_4/docs/`).

---

## Use Cases

- Read and send emails.
- Manage calendar events.
- Access files and folders in OneDrive or Google Drive.
- Query enterprise search across mail and docs.

---

## Google Workspace MCP OAuth 2.1 Deep Dive (Jan 2026, Updated Feb 2026)

**Update (February 2026)**: We upgraded Google Workspace MCP to upstream `workspace-mcp` `v1.10.7` and removed our older "pre-seed + token-middleware" workaround. Upstream now relies on FastMCP's native `GoogleProvider` OAuth proxy (DCR + CORS + `.well-known` metadata). To stay authenticated across MCP restarts/deployments, the OAuth proxy client registry must be persisted; in the managed cloud environment we do this with the **disk** backend + a persistent volume mount (no Redis/Valkey dependency).

### Root Cause Analysis: "Client ID not found" Error

**Problem**: When users clicked "Google Workspace MCP authenticate" in LibreChat, they got redirected to the MCP server which returned:
```json
{"error":"invalid_request","error_description":"Client ID 'xxx.apps.googleusercontent.com' not found"}
```

**Initial Misdiagnosis**: The error message suggested the Google OAuth Client ID was not configured correctly in Google Cloud Console.

**Actual Root Cause**: The error came from the **MCP server**, not Google. The MCP SDK's OAuth 2.1 implementation uses **Dynamic Client Registration (DCR)**, which requires clients to be registered before they can use the `/authorize` endpoint.

### OAuth 2.1 vs OAuth 2.0 Architecture

```
OAuth 2.0 (Legacy Mode):
User → LibreChat → MCP Server → Google OAuth
                   ↓
            Token stored in MCP
            
OAuth 2.1 (DCR/Proxy Mode):
User → LibreChat → MCP Server (OAuth Proxy) → Google OAuth
                   ↓                ↓
            DCR Client Registry    PKCE Generation
                   ↓
            MCP generates its own authorization codes
```

**Key Insight**: In OAuth 2.1 mode:
1. The MCP server acts as an **OAuth proxy** between LibreChat and Google
2. LibreChat performs **Dynamic Client Registration** against the MCP server (`POST /register`) and receives a DCR `client_id`/`client_secret`
3. The MCP server must persist the **DCR client registry** (otherwise refresh breaks after restarts)
4. The MCP server generates its OWN authorization codes for LibreChat (PKCE)
5. LibreChat exchanges these codes with the MCP server's `/token` endpoint and stores tokens for refresh

### Current Fix (February 2026): DCR + Persistent OAuth Proxy Storage

1. **LibreChat** (`librechat.yaml`):
   - Do **NOT** set `oauth.client_id` / `oauth.client_secret` for `mcpServers.google_workspace`.
   - Keep `authorization_url`, `token_url`, `redirect_uri`, and `scope`.
   - This forces LibreChat to use DCR (`POST /register`) against the MCP server.

2. **Google Workspace MCP** (Azure Container App):
   - Enable OAuth 2.1: `MCP_ENABLE_OAUTH21=true`
   - Persist OAuth proxy registry:
     - `WORKSPACE_MCP_OAUTH_PROXY_STORAGE_BACKEND=disk`
     - `WORKSPACE_MCP_OAUTH_PROXY_DISK_DIRECTORY=/app/store_creds/oauth-proxy`
   - Mount a persistent volume at `/app/store_creds` (Azure Files, ReadWrite).

**Result**: LibreChat authenticates once, stores tokens + the DCR `client_id`/`client_secret`, and token refresh continues working across MCP restarts/deployments unless the user revokes access.

### Legacy Fix (January 2026, deprecated)

In January 2026 we temporarily worked around DCR issues by pre-seeding FastMCP OAuth proxy client storage and injecting missing token parameters. This is no longer needed (and should not be reintroduced) after the upstream `workspace-mcp` v1.10.x upgrade.

### Key Learnings (February 2026)

1. OAuth 2.1 relies on DCR; ensure `/register` works and LibreChat is configured to use it.
2. OAuth proxy client registry must persist across MCP restarts; use `disk` (single-server) or `valkey` (distributed) backends.
3. If users are forced to re-auth frequently, suspect missing persistence or failed refresh before blaming Google OAuth.
4. If Valkey/Redis is used in ACA, DNS/network must be reachable from the managed environment (private endpoints require private DNS).

### RCA: OAuth Re-auth Loop After LibreChat Config Drift (2026-02-19)

#### Symptoms
- User completes Google OAuth but MCP remains unavailable in LibreChat.
- Clicking Google Workspace immediately re-initiates OAuth instead of staying connected.
- OAuth callback intermittently returns `invalid_state` when the approval page sits open too long.
- Consent screen shows FastMCP's default "F" logo page.

#### Root Cause
1. The live cloud `librechat.yaml` in the managed config store drifted to loopback OAuth endpoints for MCP servers (for example `http://localhost:8000/oauth2/token`), while runtime was remote.
2. In LibreChat refresh flow, `MCPOAuthHandler.refreshOAuthTokens(...)` prioritized `oauth.token_url` from config when stored client info existed.
3. Because the configured `token_url` was loopback, refresh requests from the LibreChat container failed (`fetch failed`) and the server repeatedly fell back to re-auth.
4. A secondary issue: flow-state TTL is 10 minutes; delayed user approval can produce `Flow state not found`/`invalid_state`.

#### Why This Regressed
- Config was updated in running environment without preserving the non-loopback OAuth URLs.
- Deployment validation did not block `localhost` OAuth URLs for non-local environments.

#### Permanent Fix Applied
1. Corrected live cloud OAuth URLs to public MCP endpoints (Google + MS365) in:
   - the managed runtime config
   - the environment-specific git source-of-truth mirror
2. Added a code guard in `viventium_v0_4/LibreChat/packages/api/src/mcp/oauth/handler.ts`:
   - Ignore configured loopback `token_url` when `serverUrl` is non-loopback.
   - Fall back to discovered OAuth token endpoint.
3. Added regression test in `viventium_v0_4/LibreChat/packages/api/src/mcp/__tests__/handler.test.ts` covering loopback-token-url fallback behavior.
4. Restarted LibreChat after config/image update so runtime picked up corrected endpoints.

#### Preventatives (Must Keep)
1. Before any deploy, pull live config from Azure Files and diff against git-tracked source of truth.
2. Add/keep a pre-deploy guard: fail deployment if cloud/prod `oauth.authorization_url` or `oauth.token_url` contains `localhost`, `127.0.0.1`, `0.0.0.0`, or `::1`.
3. Keep OAuth refresh regression tests in CI (loopback configured URL must not be used when server is remote).
4. Keep OAuth proxy persistence enabled for Google MCP (`WORKSPACE_MCP_OAUTH_PROXY_STORAGE_BACKEND=disk` + Azure Files mount).
5. Preserve the FastMCP consent page behavior as expected upstream; branding customizations, if desired, must be done in the MCP OAuth proxy layer, not LibreChat callback handling.

#### Per-User Separation Validation (2026-02-19)
1. OAuth flow IDs are namespaced by user: `generateFlowId(userId, serverName) => "${userId}:${serverName}"`.
2. OAuth initiate rejects user mismatch (`userId` query must equal authenticated `req.user.id`).
3. Callback persists tokens with `flowState.userId` and reconnects for that same user only.
4. Stored token records are keyed by `userId` + `identifier` (`mcp:<serverName>`, `mcp:<serverName>:refresh`, `mcp:<serverName>:client`).
5. OAuth token retrieval endpoint denies access when `flowId` is not prefixed by the authenticated `user.id`.
6. Caveat: this guarantees separation per LibreChat user. For Telegram, per-person isolation additionally depends on `TelegramUserMapping` (see `03_Telegram_Bridge.md` section "Telegram OAuth Tokens Shared Across Users (2026-01-15)").

### RCA: Google MCP "Auth Completes but Re-Prompts / Not Available" (2026-02-19, cloud)

#### Symptoms
- User completes Google consent flow, then MCP still appears unavailable in LibreChat.
- Clicking Google Workspace starts auth again.
- Intermittent `invalid_state` style callback failures around rollout/restart windows.

#### Root Causes (Confirmed)
1. **Flow-state storage fragility during rollout windows**  
   OAuth flow records (`CacheKeys.FLOWS`) were process-local/in-memory in non-Redis mode. During rolling transitions (or temporary multi-replica windows), initiate and callback could land on different replicas and miss flow state.
2. **Per-user token isolation (working as designed) exposed account mismatch**  
   Live checks showed tokens existed for one LibreChat user ID while another logged-in user ID had none. In that case reinitialize correctly returns `oauthRequired: true` for the user without tokens.

#### Permanent Fixes Applied
1. **Shared flow-state cache** (LibreChat):  
   `viventium_v0_4/LibreChat/api/cache/getLogStores.js` now stores `CacheKeys.FLOWS` in Mongo-backed Keyv instead of in-process cache.
2. **Google OAuth proxy persistence** (already in place, retained):  
   - `WORKSPACE_MCP_OAUTH_PROXY_STORAGE_BACKEND=disk`  
   - `WORKSPACE_MCP_OAUTH_PROXY_DISK_DIRECTORY=/app/store_creds/oauth-proxy`  
   - Azure Files mounted at `/app/store_creds`

#### Live Validation Snapshot (2026-02-19)
- Example user `user-1`: `google_workspace/reinitialize` returns `oauthRequired: true` (no stored tokens for this user).

## Local MCP Placeholder Validation Drift (2026-03-26)

### Symptom
- Running `npm run backend:dev` directly from `LibreChat/` caused OAuth MCPs like `ms-365` and `google_workspace` to disappear from the loaded config.
- Validation failed on `oauth.authorization_url` / `oauth.token_url` even though `.env` already contained real values.
- The same stack still worked when started through `viventium-librechat-start.sh`.

### Root Cause
1. The config compiler intentionally emits `${ENV_VAR}` placeholders into `librechat.yaml` for MCP OAuth URLs.
2. The normal launcher renders a resolved `librechat.generated.yaml` and exports `CONFIG_PATH` to that generated file before starting LibreChat.
3. A plain backend dev start bypassed that render step and loaded `librechat.yaml` directly.
4. `loadCustomConfig()` validated the raw placeholder strings before env interpolation, so Zod rejected them as invalid URLs and silently dropped those MCP servers from the usable config.

### Fix
1. Keep the launcher render step for full-stack startup.
2. Also make `loadCustomConfig()` interpolate `${ENV_VAR}` placeholders recursively before schema validation.
3. Add regression coverage proving placeholderized MCP OAuth URLs validate correctly when `.env` supplies the concrete values.

### Rule

### MCP OAuth Wait Policy Must Stay Structural (2026-04-12)

- MCP OAuth wait behavior must not infer user intent from message keywords, provider labels, or
  hand-written text heuristics.
- Runtime wait/strip decisions may use only structural signals available at tool-loading time:
  - current surface (`web`, `voice`, `telegram`, `gateway`)
  - which MCP servers are actually pending OAuth
  - which tool definitions for the current turn are owned by those pending servers
  - whether any non-pending specialized tools remain available after stripping pending MCP tools
- Current product rule:
  - `telegram` / `gateway` never wait in-turn
  - `always` waits on web/voice for all pending OAuth servers
  - `never` never waits
  - `intent` is still the default env mode name, but its runtime meaning is structural:
    wait only when exactly one pending OAuth server owns the current specialist tool surface and
    only generic built-ins remain otherwise
- Reason:
  - keyword-based OAuth wait logic is runtime NLU by another name
  - it drifts with phrasing and conflicts with the no-hardcoded-NLU rule in
    `01_Key_Principles.md`
- Placeholderized `librechat.yaml` is valid source-of-truth input.
- Direct backend dev starts must not lose MCP servers just because the generated `CONFIG_PATH` step was skipped.

## Local OAuth Drift Repair (2026-03-12)

### Symptom
- Local `google_workspace` looked configured but intermittently fell back into OAuth re-init loops.
- Error logs showed repeated refresh failures against `404 Not Found` and stale `Flow state not found` follow-on errors.
- The MCP itself was healthy on `http://localhost:8111`, but LibreChat local config still carried older loopback `/oauth2/*` endpoints in some generated/tracked paths.

### Root Cause
1. The canonical local Google MCP advertises loopback OAuth endpoints at:
   - `http://localhost:8111/authorize`
   - `http://localhost:8111/token`
2. Local LibreChat config drifted to older FastMCP-style paths:
   - `http://localhost:8111/oauth2/authorize`
   - `http://localhost:8111/oauth2/token`
3. During token refresh, LibreChat could still honor the stale configured `token_url` unless discovery metadata won decisively.
4. Once refresh hit the stale `/oauth2/token` path, LibreChat fell into the expected follow-on failure chain:
   - refresh `404`
   - transport `invalid_token`
   - OAuth re-init
   - callback `Flow state not found` if the pending flow no longer existed

### Fix (Local, Minimal)
1. Corrected the local source of truth and runtime mirror to use the actual MCP endpoints:
   - `viventium_v0_4/LibreChat/viventium/source_of_truth/local.librechat.yaml`
   - `viventium_v0_4/LibreChat/librechat.yaml`
   - `viventium_v0_4/LibreChat/.env`
   - `viventium_v0_4/LibreChat/.env.example`
2. Hardened the local launcher:
   - `viventium_v0_4/viventium-librechat-start.sh`
   - isolated/local legacy `/oauth2/*` loopback values are treated as default-like drift and normalized back to `/authorize` and `/token`
3. Added a narrow runtime self-heal in:
   - `viventium_v0_4/LibreChat/packages/api/src/mcp/oauth/handler.ts`
   - when both URLs are loopback and config disagrees with discovered metadata, refresh now prefers the discovered token endpoint
4. Added regression coverage in:
   - `viventium_v0_4/LibreChat/packages/api/src/mcp/__tests__/handler.test.ts`

### Why We Did Not Update The Google MCP Upstream Here
- This incident was not caused by a broken Google MCP server.
- The local MCP already exposed the correct metadata and served real Gmail requests once LibreChat stopped refreshing against the stale URL.
- Updating the Google MCP upstream would have increased scope and churn without addressing the actual failure mode.

## Local MCP Status + Tool Inventory Reliability (2026-03-13)

### Symptom
- MCP Settings could show `Needs Auth` for `google_workspace` and `ms-365` after local restarts even though saved tokens still existed.
- `GET /api/mcp/tools` could return an empty tool map for an OAuth MCP even when that server was actually reconnectable.
- Real tool runs could succeed later, but the local UI state looked stale and misleading.

### Root Cause
1. Local warmup only eagerly reconnected servers in `MCP_PERSISTENT_CONNECTION_SERVERS`, which effectively guaranteed `scheduling-cortex` but not OAuth MCPs.
2. OAuth MCPs with valid saved tokens were therefore left cold until some later runtime path forced a reconnect.
3. The tools endpoint treated an empty cached object as a valid cache hit instead of a stale/empty inventory that needed discovery.

### Fix
1. Warm user MCP connections for:
   - explicitly persistent servers
   - plus OAuth MCP servers that already have stored token records for that user
2. In the tools controller, treat only non-empty cached tool maps as authoritative.
3. When cached/connected tools are missing, fall back to explicit discovery for that server instead of reporting an empty inventory.

### Files
- `viventium_v0_4/LibreChat/api/server/routes/mcp.js`
- `viventium_v0_4/LibreChat/api/server/controllers/mcp.js`

### Validation
- Fresh local browser session showed:
  - `ms-365` connected
  - `google_workspace` connected
  - `scheduling-cortex` connected
  - `sequential-thinking` connected
- Direct local MCP tool runs succeeded:
  - Gmail unread/Joey checks
  - Outlook unread/Joey checks
  - scheduling tool execution
- Regression suite passed:
  - `server/routes/__tests__/mcp.spec.js`
  - `test/services/viventium/mcpOAuthPolicy.test.js`
  - `packages/api/src/mcp/__tests__/UserConnectionManager.test.ts`

### Operational Rule
- Local MCP truth must be judged by:
  - connection status
  - non-empty discovered tool inventory
  - real user-scoped tool execution
- A saved OAuth token without reconnection/discovery is not enough to call the local surface healthy.

### Validation
1. Canonical local restart path:
   - `viventium_v0_4/viventium-librechat-start.sh --restart --skip-skyvern --skip-firecrawl --skip-code-interpreter`
2. Rebuilt package used by the API process:
   - `viventium_v0_4/LibreChat/packages/api/dist/index.js` timestamp precedes the restarted API process and includes the new loopback drift guard
3. Post-restart log scan (`2026-03-12T14:15:57Z` onward):
   - no new `Token refresh failed`
   - no new `Flow state not found`
   - no new `invalid_token`
4. Real browser validation on local LibreChat (`http://localhost:3190`):
   - prompt: `Check whether you can access my Gmail inbox right now...`
   - response: `GOOGLE_OK`

### Backup / Rollback Safety
- Pre-fix local snapshots were stored at:
  - `.viventium/artifacts/manual-repairs/runs/20260312T100845-google-oauth-cortex-repair/`
- Included:
  - pre-fix YAML/env files
  - exported local agent docs
  - exported local MCP key docs
- Example user `user-2`: `google_workspace/reinitialize` returns `oauthRequired: false` and reconnects directly.
- This confirms per-user isolation is functioning and explains why one user can reconnect silently while another still needs first-time auth.

#### Preventatives
1. Keep `CacheKeys.FLOWS` in shared backing store (Mongo/Redis), never process-local for multi-replica-safe OAuth.
2. During incidents, always confirm active LibreChat user ID and token ownership before concluding "refresh is broken".
3. Keep cloud runbook checks:
   - `/api/mcp/<server>/reinitialize` response (`oauthRequired`, `oauthUrl`)
   - `/api/mcp/connection/status/<server>`
   - token presence by user ID (`mcp:<server>`, `mcp:<server>:refresh`, `mcp:<server>:client`)
4. Continue to persist Google MCP OAuth proxy storage on disk + Azure Files.

### RCA: Local Google OAuth Drift In Isolated Runtime (2026-03-05)

#### Symptoms
- Local Google auth opened Google with blocked legacy app `764086051850-6qr4p6gpi6hn506pt8ejuq83di341hur.apps.googleusercontent.com`.
- Redirect URI in that blocked flow was `http://localhost:8000/oauth2callback`.
- The isolated runtime was expected to use Google MCP on `http://localhost:8111` with app `1006762232621-it2lm2r4b8af4qjcujqvo1gpl78cqneh.apps.googleusercontent.com`.

#### Root Cause
1. Repo-root fallback env files (`.env`, `.env.local`) still contained stale legacy `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` values.
2. Google MCP startup inherited both the correct `GOOGLE_OAUTH_*` vars and the stale legacy `GOOGLE_CLIENT_*` vars, so legacy auth code paths could drift back to the wrong app.
3. A stale Google MCP process on port `8000` survived from an older local run and kept serving the old OAuth flow.
4. The restored `mcp:google_workspace:client` and `mcp:google_workspace:refresh` token docs were cloud-issued for the managed deployment's Google MCP OAuth proxy. They were not portable to isolated local, so local refresh attempts against `http://localhost:8111/token` failed with `400`.

#### Fix Applied
1. Canonicalized `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` to the active `GOOGLE_OAUTH_*` values during Google MCP startup.
2. Updated local Google MCP OAuth defaults to `/authorize` and `/token` so launcher output matches live FastMCP metadata.
3. Forced `FASTMCP_HOME` and `GOOGLE_MCP_CREDENTIALS_DIR` under `VIVENTIUM_STATE_ROOT` for isolated local runs.
4. Refreshed stale pre-seeded FastMCP OAuth client files when redirect URIs drift.
5. Backed up and removed the non-portable local `mcp:google_workspace:*` token docs so the next Google connection uses a clean local OAuth flow instead of dead cloud credentials.

#### Preventatives
1. Do not treat cloud `mcp:google_workspace:*` token docs as portable local restore state.
2. When debugging local Google auth, inspect the actual Google `client_id` and `redirect_uri` in the browser URL before assuming consent-screen or account issues.
3. Kill orphaned port-`8000` Google MCP listeners during isolated local startup so old auth links cannot survive across runs.
4. For the isolated local profile, the Google OAuth client must allow `http://localhost:8111/oauth2callback`. The older `8000` and `3000` redirects are not sufficient for the current local runtime.
5. Seeing `http://localhost:8111/oauth2callback` in the Google Cloud Console editor is not enough by itself. The OAuth client must be saved explicitly; otherwise Google can still reject the redirect with `redirect_uri_mismatch`.
6. The fastest proof for redirect registration is a direct Google auth request using the real client ID and target redirect URI. If Google reaches account chooser or consent, the redirect registration is active. If Google returns `redirect_uri_mismatch`, the cloud-side client is still wrong regardless of local logs.

### RCA: Local Google Workspace MCP Reinitialize Hung Instead Of Surfacing OAuth (2026-03-05)

#### Symptoms
- Local Google-backed conversations could stall with the Google cortex left in `brewing` and the assistant message left `unfinished`.
- The concrete failing local thread was conversation `ee8c815e-2355-41d9-8edb-b1a71a51308f`, where the last user request referenced `Viventium_Master_GTM_Handbook` on Google Docs and the follow-up assistant message `62b31d7a-9734-45e2-98d7-f3268b4b9000` never completed.
- MCP Settings showed `google_workspace - Connecting` or `Unknown`, but no Google auth window opened.
- Local launcher/API logs showed:
  - `Failed to establish connection Connection timeout after 120000ms`
  - `OAuth state - oauthRequired: false, oauthUrl: null`
- Google MCP itself was healthy and correctly advertising OAuth discovery metadata, but LibreChat never surfaced the auth URL.

#### Root Cause
1. On isolated local runs with no usable stored Google tokens, LibreChat's `reinitMCPServer()` path relied on the MCP connection layer to emit `oauthRequired`.
2. In this failure mode, the Google Streamable HTTP connection path hit the server, received repeated unauthenticated `POST /mcp` responses, but still timed out before the OAuth requirement was surfaced back to the reinitialize caller.
3. Because `oauthRequired` stayed `false`, the UI remained in a generic `Connecting` state instead of opening Google consent.
4. Separately, successful Google auth needed stronger local persistence:
   - Mongo token docs alone were not enough for isolated-local durability.
   - The Google MCP local refresh-token file had to be rebuilt so restart reconciliation would stop treating local state as unauthenticated.

#### Fixes Applied
1. **Backend OAuth timeout fallback**  
   `viventium_v0_4/LibreChat/api/server/services/Tools/mcp.js`
   - When an OAuth MCP server times out during `reinitialize` before surfacing `oauthRequired`,
   - and there are no usable stored OAuth tokens,
   - LibreChat now proactively initiates the OAuth flow and returns `oauthRequired: true` plus the real `oauthUrl` instead of hanging.
2. **Durable local Google token persistence**  
   `viventium_v0_4/MCPs/google_workspace_mcp/auth/auth_info_middleware.py`  
   `viventium_v0_4/MCPs/google_workspace_mcp/auth/persistent_google_provider.py`
   - Verified bearer-token requests now persist refresh-token state locally.
   - Access-token to refresh-token mappings are flushed into `google_refresh_tokens.json`.
3. **Launcher reconciliation kept aligned with durable local auth state**  
   `viventium_v0_4/viventium-librechat-start.sh`
   - Local startup now treats either Mongo token docs or the Google MCP durable credential state as evidence of valid local auth, instead of assuming auth is gone whenever one representation is temporarily missing.

#### Validation
1. Before the fix:
   - `google_workspace_mcp.log` showed repeated `POST /mcp 401 Unauthorized`.
   - Local Mongo had no `mcp:google_workspace`, `mcp:google_workspace:refresh`, or `mcp:google_workspace:client` docs.
   - Reinitialize timed out without an auth URL.
2. After the fix:
   - Authenticated `POST /api/mcp/google_workspace/reinitialize` returned:
     - `success: true`
     - `oauthRequired: true`
     - real `oauthUrl` on `http://localhost:8111/authorize?...`
   - Google consent completed successfully and returned to:
     - `http://localhost:3180/oauth/success?serverName=google_workspace`
   - `google_workspace_mcp.log` then showed:
     - `GET /authorize ... 302`
     - Google token exchange `POST https://oauth2.googleapis.com/token ... 200`
     - `GET /oauth2callback ... 302`
     - local `POST /token ... 200`
     - authenticated `POST /mcp ... 200`
   - Local Mongo contained fresh token docs again:
     - `mcp:google_workspace`
     - `mcp:google_workspace:refresh`
     - `mcp:google_workspace:client`
   - Local disk contained:
     - `.viventium/runtime/isolated/google_workspace_mcp/fastmcp/oauth-proxy-tokens/google_refresh_tokens.json`
   - `GET /api/mcp/connection/status` reported:
     - `google_workspace.connectionState = connected`

#### Preventatives
1. Treat `OAuth server + no stored tokens + connection timeout` as a deterministic OAuth bootstrap case, not a generic transport failure.
2. Always validate all three layers when debugging local Google MCP:
   - MCP server discovery/401 behavior
   - LibreChat reinitialize response (`oauthRequired`, `oauthUrl`)
   - durable auth state on both Mongo and local disk
3. Keep the focused regression test:
   - `viventium_v0_4/LibreChat/api/server/services/Tools/mcp.spec.js`
4. When a Google-backed conversation stalls locally, inspect the last unfinished assistant message and corresponding MCP logs before changing prompts or agent logic. In this incident the deterministic break was runtime auth bootstrap, not the agent instructions.

### RCA: OAuth Flow Timeout Mismatch (2026-02-19, cloud)

#### Symptoms
- User waits on Google account chooser/consent, then callback ends in failure and LibreChat keeps showing reauth/error states.
- MCP row can oscillate between `Connecting` and `Error`, then prompt auth again.

#### Root Cause
1. OAuth flow-status evaluation in `api/server/services/MCP.js` used a hardcoded 3-minute timeout fallback (`180000ms`).
2. Real flow TTL is configured via `FLOW_STATE_TTL_MINUTES` (default 10 minutes) in `api/config/index.js`.
3. Result: status checker could mark a still-valid in-progress flow as failed too early.
4. `CacheKeys.FLOWS` namespace default TTL was also set to 3 minutes in `api/cache/getLogStores.js`, creating additional drift risk versus configured flow TTL.

#### Fix Applied
1. `checkOAuthFlowStatus(...)` now computes timeout from `FLOW_STATE_TTL_MINUTES` (default 10) instead of hardcoded 3 minutes.
2. `CacheKeys.FLOWS` Keyv namespace TTL now follows the same `FLOW_STATE_TTL_MINUTES` value.
3. Timed-out pending OAuth flows are treated as **stale/disconnected** instead of hard `error` state to avoid sticky red UI after slow user-consent journeys.
4. Regression tests updated in `api/server/services/MCP.spec.js` to verify:
   - default 10-minute behavior,
   - env override behavior (`FLOW_STATE_TTL_MINUTES`).

#### Preventatives
1. Keep OAuth flow TTL sourced from a single env value everywhere (`FLOW_STATE_TTL_MINUTES`).
2. Add CI checks/tests whenever flow timeout logic is changed.
3. During incident triage, compare user dwell time on consent pages against current `FLOW_STATE_TTL_MINUTES`.

### Configuration Checklist for New Environments

When deploying Google Workspace MCP to a new environment:

1. **Google Cloud Console**:
   - Create OAuth 2.0 Client ID (Web application type)
   - Add authorized redirect URIs:
     - `https://<your-domain>/api/mcp/google_workspace/oauth/callback`
     - `https://<mcp-container-url>/oauth2callback`
     - Local isolated Viventium example: `http://localhost:8111/oauth2callback`
   - Add test users if app is in "Testing" mode
   - Note: "External" user type with "Testing" status limits to 100 test users

2. **Secret store**:
   - `google-oauth-client-id` - The full Client ID
   - `google-oauth-client-secret` - The Client Secret

3. **Container Environment Variables**:
   ```yaml
   MCP_ENABLE_OAUTH21: "true"
   GOOGLE_OAUTH_CLIENT_ID: <from secret store>
   GOOGLE_OAUTH_CLIENT_SECRET: <from secret store>
   WORKSPACE_MCP_OAUTH_PROXY_STORAGE_BACKEND: "disk"
   WORKSPACE_MCP_OAUTH_PROXY_DISK_DIRECTORY: "/app/store_creds/oauth-proxy"
   ```
   - Also mount persistent storage at the configured credentials volume.

4. **LibreChat Configuration** (`librechat.yaml`):
   ```yaml
   mcpServers:
     google_workspace:
       type: streamable-http
       url: https://<mcp-url>/mcp
       requiresOAuth: true
       oauth:
         authorization_url: https://<mcp-url>/authorize
         token_url: https://<mcp-url>/token
         redirect_uri: https://<librechat-url>/api/mcp/google_workspace/oauth/callback
         # DCR: do not set client_id/client_secret; LibreChat will register via /register
         scope: ${GOOGLE_WORKSPACE_MCP_SCOPE}
   ```

---

## Learnings (General)

- HTTP transport is better for multi-user OAuth because tokens are stored server-side.
- STDIO is simpler for local dev but requires local npm install or `npx` availability.
- OAuth callback ports must be consistent with Azure app registration.
- Keychain/keytar can cause token persistence issues; fallback storage in `~/.ms365-mcp-server/` is often required.
- **OAuth 2.1 requires DCR** - ensure LibreChat can call `/register` and that DCR state persists
- **Persist the MCP OAuth proxy registry** - use `disk` or `valkey` to avoid re-auth loops after MCP restarts
- **Non-chatMenu persistent MCPs need explicit warm-up** - if an MCP (like `scheduling-cortex`) is hidden from chat selection (`chatMenu: false`), it will not be part of selected-server reconnect logic unless specifically added as always-on.
- **Test OAuth flows locally before deploying** - Azure deployment cycles are slow

---

## Edge Cases

- Port conflicts on 3002/6274 or 8000 (callback and server ports).
- Missing OAuth credentials causes silent MCP failures; warn early in startup.
- Network access restrictions can block MCP calls in local testing.
- **HEAD requests to `/authorize` return 400** - only GET requests work
- **Token exchange fails silently if client_id missing** - LibreChat shows generic "Authentication failed"
- **Google "Testing" mode limits to 100 users** - publish app for production use
- **MCP connections in background cortices are event-driven**: In the background cortex path (`BackgroundCortexService.executeCortex`), MCP connections are NOT established at init time. They are created on demand when the `ON_TOOL_EXECUTE` handler fires and calls `loadToolsForExecution` → `createMCPTools` → `reconnectServer`. If the `ON_TOOL_EXECUTE` handler is missing (e.g., `toolExecuteOptions` not passed to `getDefaultHandlers`), no MCP connections are ever established and no MCP-related logs appear — a key diagnostic signal. See `02_Background_Agents.md` § "Event-Driven Tool Execution Architecture" and `11_Scheduling_Cortex.md` § "Issue: Background cortex tool calls silently dropped" for the full incident (2026-02-12).

---

## RCA: Gemini 400 Errors — `$defs` and `const` in MCP Tool Schemas (2026-02-14)

### Symptoms
When using Google/Gemini models with agents that have MCP tools, the API returns 400 Bad Request errors:
- `Unknown name "$defs" at 'tools[0].function_declarations[N].parameters'` — on multiple tool declarations
- `Unknown name "const" at 'tools[0].function_declarations[116].parameters.properties[4].value.any_of[0]'`

### Root Cause
Google's `function_declarations` API does not support `$defs`, `definitions`, or `const` JSON Schema keywords in tool parameter schemas. These are standard JSON Schema features but are not part of Google's subset.

The `resolveJsonSchemaRefs()` function in `packages/api/src/mcp/zod.ts` was correctly resolving `$ref` references and stripping `$defs` — but only at the **root level** (the `!visited.size` condition on line 214 limited it). Nested `$defs` blocks and `const` fields passed through to the API untouched.

### Causal Chain
```
MCP tool schemas (from tool servers) contain $defs at nested levels + const keyword
  → resolveJsonSchemaRefs() resolves $ref but only strips root $defs
  → Resolved schema still contains nested $defs + const
  → LangChain passes schema to Google API as function_declarations.parameters
  → Google API rejects unknown fields → 400 Bad Request
```

### Fix (2026-02-14)
Modified the VIVENTIUM block in `resolveJsonSchemaRefs()` to strip `$defs`, `definitions`, and `const` at **every recursion depth**, not just root:

```typescript
if (key === '$defs' || key === 'definitions' || key === 'const') {
  continue;
}
```

This is safe because:
- After ref resolution, `$defs`/`definitions` blocks are dead data at every level
- `const` is not consumed by any downstream component in our pipeline
- Anthropic, OpenAI, and xAI silently ignore unknown fields, so removal has no cross-provider impact

### Files Updated
- `viventium_v0_4/LibreChat/packages/api/src/mcp/zod.ts` — `resolveJsonSchemaRefs` recursive stripping
- `viventium_v0_4/LibreChat/packages/api/src/mcp/__tests__/zod.spec.ts` — 7 new tests for nested `$defs` and `const` removal

### Validation
- All 71 tests in `zod.spec.ts` pass (64 existing + 7 new)
- Existing `$ref` resolution behavior preserved
- Other JSON Schema keywords (`minLength`, `maxLength`, `pattern`, `required`, `enum`, etc.) unaffected

---

## RCA: Local Google Workspace "Authentication Failed" After Redirect Fix (2026-03-05)

### Symptoms
- Google Workspace auth in isolated local still failed even after the correct client id and redirect URI were in use.
- LibreChat surfaced generic auth failures while local logs showed:
  - `Creating streamable-http transport: http://localhost:8111/mcp`
  - `Transport error ... fetch failed`
  - `OAuth state - oauthRequired: false, oauthUrl: null`
- Browser auth would only succeed after the Google MCP process was started cleanly and the Google OAuth client had `http://localhost:8111/oauth2callback` saved in Google Cloud Console.

### Causal Chain
1. User clicked Google Workspace connect in LibreChat.
2. LibreChat reinitialize/status paths attempted to talk to the local MCP server at `http://localhost:8111/mcp`.
3. The launcher-started Google MCP child was not reliably staying bound on `:8111`, so the HTTP transport fetch failed before LibreChat could receive an OAuth challenge.
4. LibreChat therefore reported `oauthRequired: false` / `oauthUrl: null`, which surfaced to the UI as generic authentication failure instead of an actionable OAuth redirect.

### Root Causes
1. **Launcher child-process drift**
   - The Google MCP wrapper respected `WORKSPACE_MCP_PORT`, but the actual Python runtime also reads ambient `PORT`.
   - Launcher startup did not explicitly force `PORT=$GOOGLE_MCP_PORT` through the background handoff, so the child could bind incorrectly or die under inherited shell state.
2. **Legacy local drift paths**
   - Old `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` values and stale port-`8000` processes could still revive older local Google flows unless startup normalized them.
3. **Cloud-side redirect prerequisite**
   - Google Cloud OAuth client `1006762232621-it2lm2r4b8af4qjcujqvo1gpl78cqneh.apps.googleusercontent.com` must explicitly save `http://localhost:8111/oauth2callback`.
   - When that redirect is missing or unsaved, Google returns `Error 400: redirect_uri_mismatch` regardless of local logs.

### Fixes Applied
1. **Deterministic Google MCP port ownership**
   - `viventium_v0_4/MCPs/google_workspace_mcp/start_server.sh`
   - Export `PORT="${WORKSPACE_MCP_PORT}"` so the Python server and wrapper agree on the same bind port.
2. **Launcher handoff hardening**
   - `viventium_v0_4/viventium-librechat-start.sh`
   - Start Google MCP with `env PORT="$GOOGLE_MCP_PORT" nohup ...` so the child binds to the isolated port and survives launcher-shell detachment.
3. **Legacy local drift cleanup**
   - `viventium_v0_4/viventium-librechat-start.sh`
   - Kill stale port-`8000` Google MCP listeners in isolated profile.
   - Canonicalize legacy `GOOGLE_CLIENT_*` vars to the active `GOOGLE_OAUTH_*` app before startup.
4. **Fresh-machine preflight**
   - `viventium_v0_4/viventium-librechat-start.sh`
   - Added a Google redirect preflight that hits the real Google OAuth endpoint using the active client id + `GOOGLE_OAUTH_REDIRECT_URI` and logs an explicit error if Google returns `redirect_uri_mismatch`.

### Validation
- Local health after launcher restart:
  - `http://localhost:8111/health` -> `200 OK`
  - `http://localhost:3180/api/health` -> `OK`
  - `http://localhost:3190/login` -> `200 OK`
- Real browser flow reached:
  - `http://localhost:3180/oauth/success?serverName=google_workspace`
- Local Mongo token docs existed after success:
  - `mcp:google_workspace`
  - `mcp:google_workspace:refresh`
  - `mcp:google_workspace:client`
- LibreChat UI showed `google_workspace - Connected`.

### Fresh-Machine Rules
1. Local isolated Google MCP owns port `8111`; old `8000` URLs are legacy and must not be reused.
2. The launcher is the source of truth for local Google env canonicalization; do not rely on stale repo-root `GOOGLE_CLIENT_*` values.
3. Google OAuth app registration is still a shared cloud prerequisite, but launcher preflight now catches drift before the user reaches a broken auth page.
4. If local Google auth fails, inspect the launcher log first. If it says redirect preflight failed, the issue is cloud-side redirect registration, not local LibreChat wiring.

---

## Integration Points

- v0.3 MCP server wiring: `viventium_v0_3_py/viventium_v1/backend/brain/tools/`
- v0.3 launcher: `viventium_v0_3_py/start_all.sh`
- v0.4 LibreChat pipeline: see `viventium_v0_4/docs/ARCHITECTURE.md`
- Google Workspace MCP core: `viventium_v0_4/MCPs/google_workspace_mcp/core/server.py`
- **Background cortex tool execution**: `viventium_v0_4/LibreChat/api/server/services/BackgroundCortexService.js` — creates MCP connections on demand via `ON_TOOL_EXECUTE` → `loadToolsForExecution` → `createMCPTools`. See `02_Background_Agents.md` for the event-driven architecture.

---

## Related Files

| File | Purpose |
|------|---------|
| `core/server.py` | Main MCP server with OAuth 2.1 fixes |
| `auth/oauth_config.py` | OAuth configuration loading |
| `auth/scopes.py` | Scope management for Google APIs |
| `Dockerfile` | Container build for Azure deployment |
| `azure_configs/librechat-cloud.yaml` | Example cloud LibreChat MCP server configuration |
