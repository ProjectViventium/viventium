# Systems Map

## v0.4 (Active Stack)

Location: `viventium_v0_4/`

Entrypoints:
- Full stack: `viventium_v0_4/viventium-librechat-start.sh`
- LibreChat only: `viventium_v0_4/LibreChat/scripts/viventium-start.sh`

Key directories:
- `viventium_v0_4/LibreChat/` (Node API + client + packages)
- `viventium_v0_4/voice-gateway/` (Python voice worker)
- `viventium_v0_4/telegram-viventium/` (Telegram bridge)
- `viventium_v0_4/GlassHive/` (standalone workspace/worker runtime)
- `viventium_v0_4/agents-playground/` (legacy playground)
- `viventium_v0_4/agent-starter-react/` (modern playground)
- `viventium_v0_4/livekit/` (LiveKit server repo)

GlassHive core provider ownership:

- compiler registration/capabilities: `scripts/viventium/config_compiler.py`
- Agent document and Builder fields: nested LibreChat `packages/data-schemas`, `packages/data-provider`,
  `packages/api`, and `client/src/components/SidePanel/Agents/`
- exact provider/session/activity/cancellation API: nested GlassHive
  `runtime_phase1/src/workers_projects_runtime/conversation_provider.py`
- conversation-mode harness execution: nested GlassHive
  `runtime_phase1/src/workers_projects_runtime/profile_runtime.py`
- canonical LIFE template/bootstrap: `templates/life-v0.01/` and
  `scripts/viventium/life_bootstrap.py`; private bootstrap version state remains in App Support
- UI activity part: nested LibreChat `client/src/components/Chat/Messages/Content/HarnessActivity.tsx`
- Telegram long-turn transport: the compiler owns a 120-second `/chat` setup budget and a
  720-second SSE read budget; reconnect remains idempotent and never authorizes a second harness run

Feelings ownership inside LibreChat:

- compiler/env contract: root `config.schema.yaml`, examples, and `scripts/viventium/config_compiler.py`
- persisted state and methods: `packages/data-schemas/src/*/feelingState.ts`, including sparse
  per-band/per-range prompt additions
- decay/capsule/runtime config: `packages/api/src/feelings/`, including the canonical five-level
  definitions and active-only default-plus-addition serializer
- authenticated API and telemetry: `api/server/routes/viventium/feelings.js` and
  `api/server/services/viventium/`
- final behavioral placement: `api/server/services/viventium/feelingPromptTail.js`, used by the
  main/Phase-B prompt assembly and by every GlassHive worker instruction artifact after broker text
- product UI: `client/src/components/Feelings/` at `/feelings`; live capsule/trail stay in the main
  workspace while the selected-band sidebar owns its range editor
- feeling-aware spoken prompt source: `viventium/source_of_truth/prompts/surface/voice_feeling_expression.md`
  included by registered voice-call and Telegram-audio provider prompts
- Telegram audio delivery/telemetry: `viventium_v0_4/telegram-viventium/TelegramVivBot/`, consuming
  the same shared voice capability JSON as LibreChat prompt composition

Smart messaging delivery ownership:

- semantic choice and registered prompt sources: nested LibreChat
  `viventium/source_of_truth/prompts/surface/messaging_*.md`
- JavaScript persistence boundary: nested LibreChat
  `api/server/services/viventium/deliveryControls.js` and `voiceArtifactText.js`
- Python transport boundary: `viventium_v0_4/shared/delivery_controls.py`, consumed by
  `viventium_v0_4/telegram-viventium/TelegramVivBot/`
- parity guard: `tests/release/test_delivery_controls_contract.py`
- owning behavior and QA: `docs/requirements_and_learnings/03_Telegram_Bridge.md` and
  `qa/telegram-voice-replies/`

Cognitive continuity ownership:

- saved-memory policy and whole-entry read profile: nested LibreChat
  `packages/api/src/agents/memory.ts` plus compiled `memory.readProfile`
- revision-safe saved-memory persistence and collision-free entry API: nested LibreChat
  `packages/data-schemas/src/methods/memory.ts`, `api/server/routes/memories.js`, and
  `packages/data-provider/src/api-endpoints.ts`; `/preferences` is a control route while
  `/entries/:key` owns arbitrary saved-memory keys
- conversation recall attachment and degraded-state semantics: nested LibreChat agent
  initialization and `fileSearch.js`
- provider-parity host-tool transport: nested LibreChat
  `GlassHiveConversationProviderService.js`, signed broker auth/service, and the authenticated broker
  MCP route
- conversation-provider execution and native evidence: nested GlassHive
  `conversation_provider.py`, `profile_runtime.py`, provider/run/worker SQLite rows, and per-run
  native JSONL
- integrity convergence command: `bin/viventium cognitive-integrity --json`, backed by Prompt
  Workbench's read-only integrity module; schedule inspection opens SQLite in read-only mode and
  honors the selected `VIVENTIUM_APP_SUPPORT_DIR`
- per-turn availability evidence: privacy-safe saved-memory read/writer receipts under App Support;
  the integrity command reports missing receipts as not observed and degraded receipts as blocking
- recurring lanes remain distinct: direct LaunchAgent memory hardening, Workbench
  scheduler/GlassHive nightly work, and observer-only Codex automation

Wearable health-evidence ownership:

- acquisition, OAuth, exact append-only archive, provider correction overlap, and the 06:00 local
  LaunchAgent: pinned `viventium_v0_4/Viventium-Health/`
- owner-only installed executable: `~/Library/Application Support/Viventium/health/runtime/`, built
  from the reviewed parent lock pin by `scripts/viventium/viventium_health_runtime.py`
- correlation: one inactive-by-default 06:15 Scheduling Cortex definition in Prompt Workbench;
  bounded health bodies appear only in its private model snapshot
- optional Life surface: metadata-only connector status; raw provider evidence remains in the
  private archive and is read through the bounded CLI/MCP
- conscious-agent access: the generated read-only health MCP exposes inventory/read tools only;
  it does not authorize acquisition, memory writes, diagnosis, or automatic chat injection, and
  its `local_owner` audience blocks ordinary shared-agent viewers before the MCP process starts
- owner onboarding/import: the admin-only LibreChat WHOOP card invokes the installed runtime through
  fixed stdin-only commands; the macOS helper owns the custom-scheme callback; API, official ZIP,
  and verified manual PNG/JPEG evidence remain separately labeled in the one private archive

Authentication-plane ownership:

- signed-in user model OAuth and terminal reconnect state: nested LibreChat
  `packages/api/src/endpoints/{openai,anthropic}/`, `packages/data-schemas/src/methods/key.ts`, and
  Connected Accounts settings
- host worker login: local Codex/Claude `/host` session inside GlassHive; this is machine/operator
  authorization and never certifies a LibreChat user credential
- request-bound tool authorization: nested LibreChat signed broker grant/service plus GlassHive
  conversation-provider developer instruction; normal turns receive a ten-minute grant and
  scheduled work receives a delay-aware initial lifetime capped at 24 hours. Expired grants are
  rejected; there is no bearer-token pseudo-renewal path
- provider status truth: successful refresh clears reconnect state; terminal `invalid_grant`, 401,
  or 403 marks disconnected; transient provider failure remains retryable and does not become a
  false reconnect instruction

World-class call ownership:

- launch/session/auth: nested LibreChat `routes/viventium/calls.js`, `CallSessionService.js`,
  `callLaunch.js`, and `VoiceAgentAuthorizationService.js`; web browser authority is exact-session,
  Telegram launch authority is single-use, and canonical Agent `USE`/`VIEW` is rechecked on every
  Call/Wing turn
- task/work plane: nested LibreChat `VoiceTaskService.js`, `VoiceTaskManagementTool.js`, durable
  task/suppression models, GenerationJobManager and GlassHive owner adapters; paged durable replay
  and cross-process tail feed `viventium.task.v1`
- speaker plane: `voice-gateway/speaker_segments.py` and `multi_track_ingress.py` produce
  call-scoped segments/session-trust changes; nested LibreChat `SpeakerSegmentService.js` and the
  speaker model own persistence/revisions; `viventium.speaker.v1` feeds the browser
- browser surface: `agent-starter-react` call bootstrap/BFF routes, call mode/status/activity,
  task-event/action hooks, and speaker captions; Call/Wing/Listen-Only switch within one RTC room
- memory boundary: nested LibreChat message metadata and memory hardener defer durable voice writes
  until terminal post-call speaker/suppression truth is available
- raw audio retention remains zero; derived transcripts follow conversation retention, deletion,
  and export controls

Nested git repos inside v0.4:
- `viventium_v0_4/GlassHive/`
- `viventium_v0_4/Viventium-Health/`
- `viventium_v0_4/LibreChat/`
- `viventium_v0_4/agents-playground/`
- `viventium_v0_4/agent-starter-react/`
- `viventium_v0_4/cartesia-voice-agent/`
- `viventium_v0_4/livekit/`
- `viventium_v0_4/MCPs/ms-365-mcp-server/`
- `viventium_v0_4/MCPs/google_workspace_mcp/`
- `viventium_v0_4/MCPs/yt_transcript/`
- `viventium_v0_4/openclaw/`
- `viventium_v0_4/skyvern-source/`

## v0.3 (Legacy Stack)

Location: `viventium_v0_3_py/`

Entrypoints:
- Full stack: `viventium_v0_3_py/start_all.sh`
- Root wrapper: `start_all.sh`

Key directories:
- `viventium_v0_3_py/viventium_v1/` (Python cortex system)
- `viventium_v0_3_py/interfaces/` (legacy Telegram, playgrounds, MCP servers)
- `viventium_v0_3_py/scripts/` (legacy scripts)
- `viventium_v0_3_py/docker/` (legacy docker stacks)
- `viventium_v0_3_py/mcps/` (MS365 MCP server + configs)

## Shared Resources

- `.env` / `.env.local`: shared secrets and overrides
- `.viventium/`: runtime logs and artifacts
- `docs/requirements_and_learnings/`: single source of truth per feature
