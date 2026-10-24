<!-- === VIVENTIUM START ===
Document: Viventium Development Guide (Updated)
Updated: 2026-01-09
=== VIVENTIUM END === -->

# Viventium Development Guide

This guide documents development practices, environment setup, and repository rules for the Viventium integration.

## Docs Map
Start with:
1. [Shared project rules](../../AGENTS.md)
2. [Feature owner and QA map](../../docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md)
3. [Expected behavior](EXPECTED_BEHAVIOR.md)
4. [Architecture](ARCHITECTURE.md)
5. [Voice calls](VOICE_CALLS.md)
6. [Implementation index](IMPLEMENTATION_INDEX.md)

## Quick Start

### Prerequisites
- Node.js 24 LTS (use the exact supported patch from the current release manifest; do not use Node 20)
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

`dev-env run` is also the required host-safety boundary for local candidate work. It replaces
unbounded native Python worker-pool settings and supervises the candidate's Python thread budget.
If the guard stops the candidate, investigate the workload; do not raise or bypass the limit.
Broad Python, voice, audio, dependency-build, and soak workloads belong on disposable
infrastructure after any host thread-exhaustion incident.

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


## xPerfect scheduled Main

Viventium is the cognitive application. xPerfect owns the generic clock, native AI work and
orchestration. The [capability contract](../../docs/requirements_and_learnings/capabilities/main-scheduling-continuity.md)
owns behavior and acceptance; xPerfect's own application-boundary document owns its standalone
webhook and scheduling API. This setup adds no second scheduler or work manager.

### Source settings and setup

`integrations.glasshive.scheduled_wakes.enabled` is opt-in and defaults to `false`. An existing
installation can enable it through the canonical settings helper, then use its supported compile
and runtime activation path:

```sh
python3 scripts/viventium/config_settings.py \
  --config-file "$VIVENTIUM_CONFIG_FILE" \
  --backup-dir "$VIVENTIUM_STATE_DIR/config-backups" \
  scheduled-wakes-set --enabled true --json
bin/viventium compile
```

Use the runtime owner's restart or activation command for the installation. Do not copy generated
environment files into place or patch database state. Native payloads regenerate the signer and
local due URL from the existing protected machine secret; secret-free payload configuration retains
the opt-in flag. Source installations derive a distinct Standard Webhooks key from the existing
Keychain-backed runtime secret. No provider/model key is needed for clock setup.

Optional settings under `scheduled_wakes`:

| Setting | Meaning |
| --- | --- |
| `destination_id` | Protected owner-scoped `whd_…` returned by xPerfect setup. Omit for automatic idempotent setup; the settings helper accepts `--destination-id auto` to return to that mode. |
| `receiver_url` | Exact operator-owned `/api/viventium/scheduler/due` endpoint. Defaults to the current local profile. Remote endpoints require HTTPS. |
| `allowed_receiver_networks` | Explicit operator CIDRs for private HTTPS receivers. Public HTTPS and the scoped local loopback profile need no entry. |

The trusted native worker launch registers or reuses the owner's protected destination through the
ordinary authenticated xPerfect API, then supplies labeled opaque targets. A fast Direct Queen
reply does no scheduling setup; its existing handoff prepares these grants only when native work
starts. A full native Main receives the same authority during its normal bootstrap. Setup
reads the native request's trusted original source segments; it must not require a duplicate
top-level `text` field that the native request does not carry. Acceptance must inspect the
actual worker's protected grant and scheduling MCP, then a saved clock and its due return.
When that scheduled turn creates another schedule, Core resolves its server-authored due admission
back to the authorized original request binding. Its original text, event identity and source
conversation remain the source; the internal scheduler prompt is never recast as the user's request.
The current accepted stream, owner, tenant and source permissions must still match. The saved
schedule's own instruction remains the specific work to perform, independently of the original title
source and fallback. Delivery choices store ordered original-message references and a text digest,
not copied request text. Core verifies those references against the current owner's source history
before use. Repeated grants for the same originals reuse that reference identity. Existing text-only
bindings remain readable; missing, changed or foreign original messages settle the occurrence as
`failed` with `schedule_task_source_unavailable`. This permanent source failure is not reclaimed or
restored on the next recovery pass. Transient storage failures remain retryable. Conversation deletion
removes its source/destination bindings through the existing deletion
path. Sleeping inside a worker and printing a reminder is not a saved schedule.
Setup uses a stable owner/integration identity; secret changes update that protected destination. A URL
change creates a replacement and moves only matching future schedule targets through the normal
version-checked API. Existing occurrence snapshots, admitted work and receipts are not replayed.
Owner-scoped URL hashes let explicit destination IDs be checked without exposing the URL. Startup
reuses the existing recovery path to refresh known owners; due requests return retryable 503 until
that setup is ready, so a key change cannot turn the first wake into a permanent signature failure.
URLs and signer keys stay protected; workers receive only a destination ID and request reference. A configured
fixed destination must belong to the current owner. The authenticated existing scheduler gateway
also exposes `POST /api/viventium/scheduler/targets` for setup/diagnostics, using the same
`x-viventium-scheduler-secret` and owner lookup as its other operations. Supply a real owned
conversation, a source message identity and the original task; the response contains authorized
targets, never credentials. Do not expose that service secret to a model or browser.

### Normal execution and useful evidence

The fast Queen keeps `hand_off_to` / `list_workers`. Native workers use xPerfect's existing scoped
schedule tools. `schedule_list` exposes labeled authorized targets before creation: web chat,
Telegram when linked, or both; same conversation, a new conversation when due, or an explicitly
selected owned conversation. Structured `viventiumScheduleConversationIds` values are checked
against the current owner before a target is supplied. The normal native request courier preserves
that structured selection; it does not infer another conversation from prompt text. Unselected channels and other owners'
conversations never become destinations. Linked Telegram private-chat targets reuse the existing
account mapping: the stored Telegram user ID is also the private-chat ID when no separate chat ID
is present. Creation and later permission checks use that same rule.
Existing-worker queue, message, steer, retry and resume
actions refresh the current original-source grant through the existing continuation bundle. A
failed refresh cannot silently retain a prior task's create reference. Worker-supplied explicit
timing remains intact; omitted one-time timing uses the existing catch-up window (12 hours by
default, capped at 24 hours), and repeating timing uses the existing strict grace (15 minutes by
default). The protected destination rejects a body over the receiver's 64 KiB limit at schedule
creation instead of accepting a schedule that cannot be delivered.

A Telegram request defaults to Telegram delivery, with the result retained in its bound
conversation. Web/call requests default to web chat. An eligible, already open call in that same
selected chat may speak the result; this path never starts a call. New-conversation targets create
no empty conversations during setup. Actual new IDs are bound by normal Main admission when due.
The original source conversation is recorded separately from the selected destination. For a new
or different destination, Core checks both owners, reads the source's current authorized branch,
and passes its exact raw inherited context and owner-resolved files through the normal Main
formatter. It does not ask a model to rewrite the request. Same-conversation execution uses its
ordinary current history without a second history load. Source permission is rechecked at delivery.

When due, xPerfect sends its immutable signed occurrence and saved task instruction. Viventium
verifies the exact bytes and current binding, commits one intent in the existing scheduler dispatch
collection, and releases acknowledgement and ordinary Main independently. The original task and
conversation remain Viventium-owned. Distinct scheduled tasks from one source request retain
their own signed instructions, so an A-at-nine / B-at-ten request does not execute both at each
wake. Existing Workbench scheduler envelope prompts, current memory/Feelings/tools/context and
parallel subconscious paths are reused. Native workers never receive an invented Queen brief.

The normal generation receipt is retained before its HTTP response. Duplicate/lost replies recover
that stream; an already accepted but unavailable result stays unknown instead of repeating tool
work. A stored canonical result message can finish presentation after a restart without requiring
the former in-memory generation job or running Main again. A prior unknown state caused only by
that missing stream is eligible for this check when it has a saved result ID; a missing canonical
message stays unknown. The canonical Main result uses the
existing Core channel outbox and per-channel receipts.
Main presentation authority is its accepted due admission, persisted canonical response, and
current owner/conversation/binding/channel permissions. Telegram and an eligible live call use the
existing outbox claim and dispatch permit lifecycle; no synthetic worker receipt or new queue is
created. Voice also checks the exact canonical response hash before speech and never marks
interrupted or unconfirmed audio as heard. Intent states such as `delivery_queued` prove enqueue,
not delivery. `{NTA}` remains silent; file-only output keeps its files and adds no empty speech.

Private structured `schedule_due_stage` records split native target preparation (owner permission,
destination setup, channel lookup, binding writes and total), signature verification, durable
admission, ordinary Main admission and presenter enqueue. A wake that arrives too early returns
retryable 425; the same occurrence can be admitted when the clock reaches its due time. Independent destination/channel reads
and selected-conversation permission reads run in parallel. Bindings retain each exact source;
setup does not overwrite an earlier request or expire a reference that an active schedule may use. Correlate the admission identity with xPerfect's
occurrence/delivery trace and the Core channel receipt. These durations exclude downstream
provider, harness and network work unless that stage actually measures them.

### Compatibility and acceptance

Existing Cortex definitions, effective lateness/windows, receipts and in-flight effects retain
Cortex ownership. When this new path is on, the existing compiled capability policy disables only
legacy `schedule_create`; list/update/delete and old clock execution remain available. The broker
omits tools explicitly marked `access: none`, so new work has one creation clock. Enabling the new adapter does not copy those definitions or silently activate a
replacement. Before any migration, inspect and fence old dispatch and delivery, retain identity
mapping and uncertainty, and accept the replacement behavior. An empty native store is evidence
for that candidate only, not a universal migration rule.

The [scheduling journey](../../qa/main-scheduling-continuity/cases.yaml) owns actual clock-to-Main
and selected-surface acceptance, including lost ACK/restart, changed-body conflict, revoked
bindings, late/expired wakes, current call ownership, files, silence and cross-turn schedule
management. Deterministic tests and a saved definition do not prove natural user/channel delivery.
