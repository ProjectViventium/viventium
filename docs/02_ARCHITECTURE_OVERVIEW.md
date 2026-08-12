# Architecture Overview

This is the high-level map of both stacks. Deep dives live in the version-specific docs.

## v0.4 (LibreChat Stack)

Flow summary:
```
User -> LibreChat UI -> AgentClient -> BackgroundCortexService
                     -> selected Agent Provider -> direct LLM or GlassHive harness session
                        -> per-user model OAuth (LibreChat identity)
                        -> signed capability grant -> brokered recall/tools
                        -> /host worker auth (machine/operator identity; separate plane)
                     -> Feelings snapshot + active range cause/addition
                        -> final behavioral instruction boundary
                     -> voice-capable surface -> feeling-expression + provider prompt
                        -> raw provider controls -> clean display + provider TTS
                     -> SSE updates -> UI cards
                     -> Follow-up service -> extra assistant message
                     -> detached Emotional Reaction Cortex -> versioned FeelingState
                     -> Call session + browser/Telegram capability + canonical Agent ACL
                        -> Voice Gateway / LiveKit real-time conversation plane
                        -> LibreChat durable task/tool/search/memory work plane
                        -> task/source/speaker events -> modern call UI + linked chat
```

Core components:
- Orchestration: `viventium_v0_4/LibreChat/api/server/controllers/agents/client.js`
- GlassHive provider API/session ownership:
  `viventium_v0_4/GlassHive/runtime_phase1/src/workers_projects_runtime/conversation_provider.py`
- Agent provider capability/validation ownership:
  `viventium_v0_4/LibreChat/packages/api/src/agents/validation.ts` and
  `viventium_v0_4/LibreChat/packages/api/src/agents/initialize.ts`
- Canonical LIFE bootstrap: `scripts/viventium/life_bootstrap.py`
- Saved-memory control plane: nested LibreChat memory agent/policy, revision-safe data-schema
  methods, collision-free `/api/memories/entries/:key`, and per-user privacy-safe health receipts
- Recall control plane: nested LibreChat `fileSearch.js`, recall health/freshness checks, and the
  signed GlassHive broker capability; recall is not implicit filesystem access
- Wearable evidence control plane: pinned `viventium_v0_4/Viventium-Health/` acquisition/archive
  component, its owner-only installed runtime, read-only MCP, and the bounded Prompt Workbench
  `health_context` snapshot; the MCP carries a structural `local_owner` audience enforced at the
  shared tool loader, and acquisition, interpretation, memory, and surfacing remain separate
- WHOOP owner setup surface: admin-only LibreChat Settings card plus the macOS `viventium://oauth/whoop`
  helper callback; it brokers official OAuth, automatic history/scheduling, exact official ZIPs, and
  bounded PNG/JPEG manual evidence to the installed health runtime through stdin-only commands
- Connected-model-account truth: nested LibreChat OpenAI/Anthropic OAuth refresh plus encrypted
  `oauthReconnectRequired` state; `/api/keys` and Settings reflect terminal provider rejection while
  transient provider failures remain retryable
- Background activation: `viventium_v0_4/LibreChat/api/server/services/BackgroundCortexService.js`
- Follow-ups: `viventium_v0_4/LibreChat/api/server/services/viventium/BackgroundCortexFollowUpService.js`
- Feelings kernel/state/config: `viventium_v0_4/LibreChat/packages/api/src/feelings/` (five stable
  ranges per band, sparse per-user additions, active-only capsule serialization)
- Detached feeling appraisal: `viventium_v0_4/LibreChat/api/server/services/viventium/EmotionalReactionService.js`
- Feelings control surface: `viventium_v0_4/LibreChat/client/src/components/Feelings/` (main live
  evidence plus selected-band range editor)
- Spoken-surface prompt composition: `viventium_v0_4/LibreChat/api/server/services/viventium/surfacePrompts.js`
- Voice real-time plane: `viventium_v0_4/voice-gateway/` plus the pinned LiveKit server and modern
  playground. It owns media, endpointing, TTS, interruption, speaker-segment production, and relay
  of authoritative task events; it does not own tool/task truth.
- Voice work plane: nested LibreChat `VoiceTaskService`, `VoiceTaskManagementTool`,
  `SpeakerSegmentService`, durable task/suppression/speaker models, GenerationJobManager/GlassHive
  owner adapters, and post-call memory hardening.
- Voice authority plane: nested LibreChat call routes, `CallSessionService`, `callLaunch`, and
  `VoiceAgentAuthorizationService`; browser BFF routes require exact-session capability and Telegram
  launch links exchange a one-time fragment bearer.

Reference: `viventium_v0_4/docs/ARCHITECTURE.md`

The joined continuity integrity command is `bin/viventium cognitive-integrity --json`. It reports
each control plane independently and fails closed when a natural scheduled run is unobserved or the
latest receipt does not match the currently configured provider/model/effort. A healthy `/host`,
memory row, prompt bundle, or manual kickstart cannot certify a different plane.

## v0.3 (Python Cortex Stack)

Flow summary:
```
User -> LiveKit -> Frontal Cortex -> ResponseController
                     -> ConversationTap -> SubconsciousRuntime -> Cortices
                     -> Insights persisted in markdown -> surfaced by ResponseController
```

Core components:
- Frontal cortex agent: `viventium_v0_3_py/viventium_v1/backend/brain/frontal-cortex/`
- ResponseController: `viventium_v0_3_py/viventium_v1/backend/brain/frontal-cortex/frontal_cortex/response_controller.py`
- Subconscious runtime: `viventium_v0_3_py/viventium_v1/backend/brain/infrastructure/runtime.py`
- Cortices: `viventium_v0_3_py/viventium_v1/backend/brain/cortices/`

Reference: `viventium_v0_3_py/docs/02_ARCHITECTURE.md`

## Comparison

| Area | v0.4 (LibreChat) | v0.3 (Python) |
| --- | --- | --- |
| UI | LibreChat web app + LiveKit calls | LiveKit + playgrounds |
| Background processing | Background agents inside LibreChat | Cortices in Python runtime |
| Response serialization | LibreChat pipeline + follow-up messages | ResponseController single queue |
| Memory | LibreChat DB + metadata | Markdown + vector store |
| Wearable evidence | Private append-only provider archive + bounded Workbench correlation | None |
| Voice | Voice Gateway worker | LiveKit agent directly |
