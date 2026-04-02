# Architecture Overview

This is the high-level map of both stacks. Deep dives live in the version-specific docs.

## v0.4 (LibreChat Stack)

Flow summary:
```
User -> LibreChat UI -> AgentClient -> BackgroundCortexService
                     -> SSE updates -> UI cards
                     -> Follow-up service -> extra assistant message
                     -> Voice Gateway (LiveKit) for calls
```

Core components:
- Orchestration: `viventium_v0_4/LibreChat/api/server/controllers/agents/client.js`
- Background activation: `viventium_v0_4/LibreChat/api/server/services/BackgroundCortexService.js`
- Follow-ups: `viventium_v0_4/LibreChat/api/server/services/viventium/BackgroundCortexFollowUpService.js`
- Voice worker: `viventium_v0_4/voice-gateway/`

Reference: `viventium_v0_4/docs/ARCHITECTURE.md`

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
| Voice | Voice Gateway worker | LiveKit agent directly |
