<!-- === VIVENTIUM START ===
Document: Viventium Development Guide (Updated)
Updated: 2026-01-09
=== VIVENTIUM END === -->

# Viventium Development Guide

This guide documents development practices, environment setup, and repository rules for the Viventium integration.

## Docs Map
Start with:
1. `docs/VIVENTIUM_STATUS.md`
2. `docs/EXPECTED_BEHAVIOR.md`
3. `docs/ARCHITECTURE.md`
4. `docs/VOICE_CALLS.md`
5. `docs/IMPLEMENTATION_INDEX.md`

## Quick Start

### Prerequisites
- Node.js 20+ (use `nvm use 20`)
- MongoDB (local on 27017 or Atlas)
- Docker (for LiveKit server in dev)
- Python 3.10+ (voice gateway)

### Full Stack (Recommended)
```bash
./viventium-librechat-start.sh
```
Starts LibreChat, LiveKit, the Modern Viventium Playground, and the voice gateway with consistent
secrets.
The playground is Viventium's modern `agent-starter-react` UI by default.

The old `viventium-start-all.sh` command is a compatibility wrapper for this launcher. It does not
own a separate LiveKit or dependency-install path, and obsolete `--build`, `--clean`, and
`--install-deps` arguments fail closed instead of mutating the checkout.

### Stable Local Prod vs Side-by-Side Dev Env

For Viventium core development, prefer the public CLI runtime boundary instead of launching random
copies of the stack by hand.

- **Local prod** is the installed user-facing runtime started by the macOS helper. It uses the
  canonical App Support state and default local ports:
  - Web: `http://localhost:3190`
  - API: `http://localhost:3180/api`
  - Modern Playground: `http://localhost:3300`
- **Dev env** is an optional side-by-side runtime created by `bin/viventium dev-env`. It gets
  separate App Support state and offset app-facing ports. With the default `dev` env:
  - Web: `http://localhost:4190`
  - API: `http://localhost:4180/api`
  - Modern Playground: `http://localhost:4300`
- Heavy singleton services are shared by default and should not be duplicated for ordinary dev runs:
  recall/RAG, SearXNG, Firecrawl, Google Workspace MCP, and Microsoft 365 MCP.

Use local prod when validating the installed product, helper, Telegram, update, or user-facing
runtime behavior:

```bash
bin/viventium dev-runtime status
bin/viventium status
```

Use a dev env when testing local changes without disturbing the installed runtime:

```bash
bin/viventium dev-env create dev
bin/viventium dev-env status dev
bin/viventium dev-env run dev start
```

When the current checkout should become the installed local prod runtime, promote it through the
runtime-checkout path instead of copying source into install paths:

```bash
bin/viventium dev-runtime activate-current --validate --restart --allow-protected-folder
```

The canonical product contract for this is
`docs/requirements_and_learnings/50_Stable_Dev_Runtime.md`.

<!-- === VIVENTIUM START ===
Section: Launcher flags + modern playground
Added: 2026-01-11
=== VIVENTIUM END === -->
Common flags:
- `--restart` (clean + restart services; safe for LiveKit)
- `--modern-playground` (agent-starter-react UI from `agent-starter-react`; default)
- `--classic-playground` (old `agents-playground` UI; explicit opt-in only)
- `--skip-voice-gateway`, `--skip-ms365-mcp`, `--skip-google-mcp`, `--skip-code-interpreter`

### LibreChat Only (Text UI)
```bash
cd LibreChat
./scripts/viventium-start.sh
```

### Prompt Workbench (Prompt QA)
```bash
cd prompt-workbench
npm install
npm run build
npm run serve
```

Prompt Workbench is a standalone local developer/QA app for source/live/eval prompt reconciliation.
It reads source prompts from `LibreChat/viventium/source_of_truth`, uses the existing
`viventium-sync-agents.js` guarded sync path for live LibreChat agents, and stores drafts/ledger
state under private App Support user data.

## Development Principles

### 1. Minimize Upstream Conflicts
- Copy or extend rather than edit upstream files.
- Keep Viventium code in dedicated directories when possible.

### 2. VIVENTIUM Markers (Mandatory)
Any edit to upstream LibreChat files must be wrapped with:
```ts
// === VIVENTIUM START ===
// ... change description ...
// === VIVENTIUM END ===
```
Also add VIVENTIUM markers to new Viventium-owned files (header block) so future merges can isolate changes quickly.

### 3. UI Naming Conventions
User-facing labels must avoid internal neuroscience terms:
- Use "Background Agent" (not "Cortex")
- Use "Background Insight" (not "Subconscious")

## Key File Locations (Current)

### Background Agents (Server)
- `LibreChat/api/server/controllers/agents/client.js`
- `LibreChat/api/server/services/BackgroundCortexService.js`
- `LibreChat/api/server/services/viventium/BackgroundCortexFollowUpService.js`
- `LibreChat/api/server/services/ResponseController.js`

### Background Agents (Client)
- `LibreChat/client/src/hooks/SSE/useSSE.ts`
- `LibreChat/client/src/hooks/SSE/useResumableSSE.ts`
- `LibreChat/client/src/hooks/Viventium/useCortexFollowUpPoll.ts`
- `LibreChat/client/src/components/Chat/Messages/Content/CortexCall.tsx`
- `LibreChat/client/src/components/Chat/Messages/Content/CortexCallInfo.tsx`

### Voice Calls
- `LibreChat/client/src/components/Viventium/CallButton.tsx`
- `LibreChat/api/server/routes/viventium/calls.js`
- `LibreChat/api/server/routes/viventium/voice.js`
- `LibreChat/api/server/services/viventium/CallSessionService.js`
- `LibreChat/api/server/services/viventium/VoiceCortexInsightsService.js`
- `voice-gateway/worker.py`
- `voice-gateway/librechat_llm.py`

### Data Model
- `LibreChat/packages/data-schemas/src/schema/agent.ts`
- `LibreChat/packages/data-provider/src/types/assistants.ts`
- `LibreChat/packages/data-provider/src/types/runs.ts`

## Environment Configuration

### Core `.env`
Create `.env` in `LibreChat/` or rely on `viventium-librechat-start.sh` loading from `viventium_core/.env.local`.

Minimum variables:
```
MONGO_URI=mongodb://127.0.0.1:27017/LibreChat
OPENAI_API_KEY=your-key
CREDS_KEY=your-32-char-key
CREDS_IV=your-16-char-iv
JWT_SECRET=your-jwt-secret
JWT_REFRESH_SECRET=your-refresh-secret
ENDPOINTS=agents,openAI
```

### Voice Variables
```
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
LIVEKIT_URL=ws://localhost:7880
VIVENTIUM_PLAYGROUND_URL=http://localhost:3000
VIVENTIUM_CALL_SESSION_SECRET=your-shared-secret
```

<!-- === VIVENTIUM START ===
Section: STT + VAD parity with v1
Added: 2026-01-11
=== VIVENTIUM END === -->
### STT + VAD Variables (Voice Gateway)
```
VIVENTIUM_STT_PROVIDER=whisper_local
VIVENTIUM_VOICE_STT_PROVIDER=whisper_local
VIVENTIUM_STT_MODEL=large-v3-turbo
VIVENTIUM_STT_LANGUAGE=en
VIVENTIUM_STT_THREADS=8
VIVENTIUM_STT_VAD_ACTIVATION=0.4
VIVENTIUM_STT_VAD_MIN_SILENCE=0.5
VIVENTIUM_STT_VAD_MIN_SPEECH=0.1
ASSEMBLYAI_API_KEY=... (only if VIVENTIUM_STT_PROVIDER=assemblyai)
```

Notes:
- `STT_PROVIDER` (legacy v1) is honored if `VIVENTIUM_STT_PROVIDER` is unset.
- Local whisper.cpp preserves the selected model. The launcher checks the official whisper.cpp
  checksum, atomically re-downloads the exact selected artifact if it is missing or corrupt, and
  validates model load in a subprocess before the worker uses it. Do not recover by silently
  changing `large-v3-turbo` or any other selected local model into a different model.
- Silero VAD needs Python <= 3.12; the launcher rebuilds the voice-gateway venv if needed.

<!-- === VIVENTIUM START ===
Section: Voice concurrency bypass
Added: 2026-01-11
=== VIVENTIUM END === -->
### Voice Concurrency
```
VIVENTIUM_VOICE_BYPASS_CONCURRENCY=true
```
LibreChat’s concurrent limiter can block streaming voice responses; voice calls bypass it by default.

<!-- === VIVENTIUM START ===
Section: Code Interpreter
Added: 2026-01-11
=== VIVENTIUM END === -->
### Code Interpreter
```
LIBRECHAT_CODE_BASEURL=http://localhost:8001
LIBRECHAT_CODE_API_KEY=...
```
The launcher starts LibreCodeInterpreter (Docker) on port 8001 unless `--skip-code-interpreter` is set.

## Testing

### Backend
```bash
cd LibreChat/api
npm test
```

### Client
```bash
cd LibreChat/client
npm run test:ci
```

## Merge Conflict Resolution
1. Identify VIVENTIUM markers in conflicted files.
2. Keep upstream changes outside marked blocks.
3. Re-apply Viventium blocks if needed.
4. Update marker dates and run tests.

## Mongo / Agent Configuration
- Use the LibreChat Agent Builder UI for background agent config.
- For direct inspection:
```bash
mongosh --eval "db = db.getSiblingDB('LibreChat'); db.agents.find({'background_cortices.0': {$exists: true}}, {name: 1}).pretty()"
```
