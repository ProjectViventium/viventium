# Architecture Overview

This is the high-level map of both stacks. Deep dives live in the version-specific docs.

## v0.4 (LibreChat Stack)

Flow summary:
```
User -> LibreChat UI -> AgentClient -> BackgroundCortexService
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
- GlassHive user control plane: Glass Drive owns the browser session, OIDC/PKCE login, CSRF, and
  human confirmation boundary; the GlassHive runtime owns owner-scoped workspaces, templates,
  provider-account references, Library grants, activity, and worker execution. It receives only
  short-lived signed identity assertions from the gateway.
- Connected-account inference ownership: LibreChat keeps each user's encrypted API credential and
  issues a short-lived grant bound to user, tenant, worker, run, model, route, and adapter. A worker
  receives the grant and fixed adapter URL, never the upstream credential.
- Recurring workspace ownership: Scheduling Cortex is the sole durable recurring-definition and
  occurrence-ledger owner for Viventium. It dispatches owner-authenticated work to GlassHive; the
  GlassHive schedule API is a delegated facade and does not persist a second shadow definition.
- Agent provider capability/validation ownership:
  `viventium_v0_4/LibreChat/packages/api/src/agents/validation.ts` and
  `viventium_v0_4/LibreChat/packages/api/src/agents/initialize.ts`
- Canonical LIFE bootstrap: `scripts/viventium/life_bootstrap.py`
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
