# No Response Feature ({NTA})

**Document Version:** 2.1
**Date:** 2026-02-07
**Owner:** Viventium Core
**Status:** Implemented in `viventium_v0_4`

---

## Purpose

In passive/background modes (for example: cortex follow-ups) the assistant can legitimately have nothing meaningful to add.

Instead of emitting noisy messages like "Nothing new to add.", the system uses a strict internal marker: `{NTA}`.

When `{NTA}` is produced, it is treated as intentional silence:
- No Telegram message is sent
- No voice TTS is spoken
- No LibreChat UI bubble is rendered
- No LiveKit Agents Playground chat transcript is rendered (voice calls)

---

## Tag Definition

- **Token:** `{NTA}` (single braces)
- **Meaning:** "Nothing To Add" (intentional silence)
- **Rule:** Must be the *entire* assistant output (no surrounding text)

### Accepted Legacy Variants (Normalization / Filtering)

For backwards compatibility and LLM drift, we treat the *entire output* as no-response when it is:
- `{NTA}` (whitespace/case variants are accepted, normalized to `{NTA}`)
- `Nothing new to add.` / `Nothing to add.` (case-insensitive)
- Short equivalents like:
  - `Nothing new to add for now.`
  - `Nothing to add (yet).`
  - `Nothing to add, thanks!`

Important: we do **not** suppress if there is additional content, e.g. `Nothing new to add. What next?`

---

## Where It Is Generated (v0_4)

### Global Prompt Injection (LibreChat)

When enabled, LibreChat injects a single shared instruction block into the **system prompt** for user-facing LLM runs so the model can intentionally return `{NTA}` when it has nothing to add.

This is **env-gated** for safe rollout and **config-driven** for uniformity:
- **Env:** `VIVENTIUM_NO_RESPONSE_ENABLED=1`
- **Config (single source of truth):** `librechat.yaml` → `viventium.no_response.prompt`
- **Backend helper:** `viventium_v0_4/LibreChat/api/server/services/viventium/noResponsePrompt.js`

Injection sites:
- `viventium_v0_4/LibreChat/api/server/controllers/agents/client.js` (main agents + any handoff/parallel agents)
- `viventium_v0_4/LibreChat/api/server/services/BackgroundCortexService.js` (background cortices; `{NTA}` is treated as "no insight")
- `viventium_v0_4/LibreChat/api/server/services/viventium/BackgroundCortexFollowUpService.js` (follow-up generator)

### Background Cortex Follow-Up (LibreChat)

Background cortices produce individual insights; once complete we may generate a single merged follow-up message.
If the merged follow-up would be redundant, we output `{NTA}`.

Files:
- `viventium_v0_4/LibreChat/api/server/services/viventium/BackgroundCortexFollowUpService.js`
  - Uses the shared no-response injection (when enabled)
  - Normalizes final follow-up text via `normalizeNoResponseText(...)`
- `viventium_v0_4/LibreChat/api/server/services/viventium/noResponseTag.js`
  - Canonical definition + normalization helpers used by the backend
- `viventium_v0_4/LibreChat/api/server/services/viventium/noResponsePrompt.js`
  - Env-gated, YAML-configurable prompt block used across all injection sites

Design decision: `{NTA}` follow-up messages are still persisted as real messages (for signaling and auditability),
but surfaces suppress them so the user experiences "no message".

---

## Where It Is Suppressed (v0_4)

### Telegram

- `viventium_v0_4/telegram-viventium/TelegramVivBot/utils/librechat_bridge.py`
  - Suppresses follow-up delivery when `is_no_response_only(text)` is true
  - Ensures follow-up polling completes without sending a message
- `viventium_v0_4/telegram-viventium/TelegramVivBot/bot.py`
  - Suppresses the **main streamed reply** when it is no-response-only (`{NTA}` / legacy variants)
  - Guards during streaming so `{NTA}` does not flash as a visible Telegram message

### Voice Gateway (LiveKit)

- `viventium_v0_4/voice-gateway/worker.py`
  - Suppresses speaking follow-ups when `is_no_response_only(text)` is true
  - Prevents fallback speech from being used when `{NTA}` is explicitly returned
- `viventium_v0_4/voice-gateway/librechat_llm.py`
  - Suppresses the **main streamed voice-call reply** when it is no-response-only (`{NTA}` / strict variants)
  - Buffers early deltas so `{NTA}` never flashes in the LiveKit Playground UI during streaming

### Scheduling Cortex (Telegram dispatch)

- `viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex/scheduling_cortex/dispatch.py`
  - If the scheduled run's final response is `{NTA}`, nothing is sent (no "(No response generated.)" fallback)
  - If the follow-up is `{NTA}`, it is suppressed and no additional polling is performed

### LibreChat Web UI

- `viventium_v0_4/LibreChat/client/src/utils/noResponseTag.ts`
  - Filters `{NTA}` / legacy no-response-only messages from the message tree
- `viventium_v0_4/LibreChat/client/src/components/Chat/Messages/MessagesView.tsx`
- `viventium_v0_4/LibreChat/client/src/components/Share/MessagesView.tsx`

---

## Shared Helpers

To keep detection consistent across Python surfaces:
- `viventium_v0_4/shared/no_response.py`

If you add a new allowed variant, update these 3 places:
1. `viventium_v0_4/LibreChat/api/server/services/viventium/noResponseTag.js`
2. `viventium_v0_4/shared/no_response.py`
3. `viventium_v0_4/LibreChat/client/src/utils/noResponseTag.ts`

---

## Testing

Python:
- `pytest viventium_v0_4/shared/tests/test_no_response.py`

LibreChat (API):
- From `viventium_v0_4/LibreChat/api`: `npm run test:ci`
  - Includes `api/server/services/viventium/__tests__/noResponseTag.spec.js`
  - Includes `api/server/services/viventium/__tests__/noResponsePrompt.spec.js`

---

---

## NTA Auto-Hide Disable on LibreChat Web UI (2026-02-21)

### Context
The client-side `filterNoResponseMessagesTree()` was hiding ALL agent responses that contained `{NTA}` from the web UI. This made it impossible to see what the agent actually did during heartbeat/scheduled runs — tool calls, memory updates, and actual content were all invisible if the response ended with `{NTA}`.

### Investigation
The filter is in `client/src/utils/noResponseTag.ts` and was called from both:
- `client/src/components/Chat/Messages/MessagesView.tsx` (line 46)
- `client/src/components/Share/MessagesView.tsx` (line 36)

The filter operates on the entire message tree, removing any message node where the text content matches `isNoResponseOnly()`. However, because scheduled runs often produce tool calls + content + trailing `{NTA}`, the filter was overly aggressive for the web UI use case.

### Fix Applied
**Disabled** the client-side NTA filter by bypassing `filterNoResponseMessagesTree()` in both files. The filter function, import, and utility code are left intact for future re-enablement.

**File A**: `client/src/components/Chat/Messages/MessagesView.tsx`
```tsx
// BEFORE:
const messagesTree = filterNoResponseMessagesTree(_messagesTree, { brewNoResponsePlaceholder: '-' });

// AFTER:
const messagesTree = _messagesTree;
// VIVENTIUM DISABLED (2026-02-21): NTA auto-hide bypassed for full visibility
```

**File B**: `client/src/components/Share/MessagesView.tsx`
```tsx
// Same pattern — passthrough instead of filter
const messagesTree = _messagesTree;
```

### What Was NOT Changed
- `noResponseTag.ts` — utility functions preserved
- `noResponseTag.js` — server-side JS helpers preserved
- `noResponsePrompt.js` — server-side NTA injection preserved
- `dispatch.py` — server-side NTA suppression for Telegram/Voice stays active
- `bot.py` — Telegram NTA suppression stays active
- `worker.py` / `librechat_llm.py` — Voice NTA suppression stays active

### Impact
- **Web UI**: All agent responses now visible, including `{NTA}` text and tool calls
- **Telegram**: Unchanged — `{NTA}`-only responses still suppressed, trailing `{NTA}` still stripped
- **Voice**: Unchanged — `{NTA}` responses still silenced

### Deployment Status
- Code change applied locally in `viventium_v0_4/LibreChat/client/`
- Vite dev server compiled with zero errors (verified via `npm run dev`)
- NOT YET deployed to cloud — requires LibreChat container rebuild (`az acr build` + `az containerapp update`)

### Re-enablement
To re-enable NTA filtering on web UI:
1. Uncomment the `filterNoResponseMessagesTree()` call in both MessagesView.tsx files
2. Remove the `VIVENTIUM DISABLED` comment blocks
3. Rebuild and deploy LibreChat container

---

## Notes (v0_3)

The legacy v0_3 Python stack used `{{no-response}}`. v0_4 standardizes on `{NTA}`.
