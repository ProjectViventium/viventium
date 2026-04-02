## Voice Latency + Memory RCA (cloud)

Date: 2026-01-22  
Scope: cloud voice calls (LiveKit voice gateway -> LibreChat agents)

### Executive Summary
- The 5s response delay is **not explained** by the VAD thresholds alone. VAD contributes ~0.5s of “end-of-speech” silence, but there are **two larger, config-driven waits** in the pipeline.
- **Background Cortex Phase A detection** is **awaited** before the main agent responds and has a default **2s time budget**. This is a real, synchronous wait.
- **“Use memory”** adds **synchronous work before the agent run**: it loads and formats *all* user memories and can initialize a memory agent. It also launches a **second LLM run** (memory agent) that can compete for the same provider key.

---

## Current cloud Config (Relevant)

### Voice Gateway (cloud env)
```736:749:devops/full_azure_deployment/full_deploy_v2/config.dev-codex-cloud.yaml
  voice_gateway:
    VIVENTIUM_TURN_DETECTION: vad
    VIVENTIUM_VOICE_STT_PROVIDER: assemblyai
    VIVENTIUM_STT_VAD_ACTIVATION: '0.4'
    VIVENTIUM_STT_VAD_MIN_SILENCE: '0.5'
    VIVENTIUM_STT_VAD_MIN_SPEECH: '0.1'
    VIVENTIUM_TTS_PROVIDER: cartesia
```

### LibreChat Memory Config (cloud deployed YAML)
```834:867:devops/full_azure_deployment/full_deploy_v2/librechat.yaml
memory:
  disabled: false
  validKeys: ["preferences", "work_info", "personal_info", "skills", "interests", "context"]
  tokenLimit: 10000
  personalize: true
  agent:
    provider: "xai"
    model: "grok-4-1-fast-reasoning"
```

---

## Voice Call Flow (Where Time Accrues)

### 1) Voice Gateway -> LibreChat (HTTP + SSE)
The voice gateway posts to `/api/viventium/voice/chat`, then subscribes to SSE stream. This adds normal network + server overhead.

```321:369:viventium_v0_4/voice-gateway/librechat_llm.py
chat_url = f"{self._origin}/api/viventium/voice/chat"
...
sse_url = f"{self._origin}/api/viventium/voice/stream/{stream_id}"
max_retries = ... default 2
retry_delay_s = ... default 0.5
```

### 2) Background Cortex Phase A (Default 2s)
This phase is **awaited** before the main response. If background cortices are configured for the agent, Phase A introduces a **time-budgeted detection wait**.

```187:193:viventium_v0_4/LibreChat/api/server/controllers/agents/client.js
function getCortexDetectTimeoutMs(voiceMode) {
  const base = parseIntEnv('VIVENTIUM_CORTEX_DETECT_TIMEOUT_MS', 2000);
  if (!voiceMode) return base;
  return parseIntEnv('VIVENTIUM_VOICE_CORTEX_DETECT_TIMEOUT_MS', base);
}
```

```1303:1313:viventium_v0_4/LibreChat/api/server/controllers/agents/client.js
// PHASE A: Detect activations (≤2s timeout)
const detectionResult = await detectActivations({
  ...,
  timeBudgetMs: cortexDetectTimeoutMs,
});
```

### 3) “Use Memory” (Synchronous Pre-Run Work)
When “Use memory” is enabled, the agent **waits for memory loading** before it starts the main run.

```678:681:viventium_v0_4/LibreChat/api/server/controllers/agents/client.js
const withoutKeys = await this.useMemory();
if (withoutKeys) {
  systemContent += `${memoryInstructions}\n\n# Existing memory about the user:\n${withoutKeys}`;
}
```

---

## “Use Memory” Feature Deep Dive

### UI Toggle -> Server Flag
The UI toggle “Reference saved memories” updates the user’s `personalization.memories` flag.

```37:46:viventium_v0_4/LibreChat/client/src/components/Nav/SettingsTabs/Personalization.tsx
if (user?.personalization?.memories !== undefined) {
  setReferenceSavedMemories(user.personalization.memories);
}
...
updateMemoryPreferencesMutation.mutate({ memories: checked });
```

```162:186:viventium_v0_4/LibreChat/api/server/routes/memories.js
router.patch('/preferences', ... async (req, res) => {
  const { memories } = req.body;
  const updatedUser = await toggleUserMemories(req.user.id, memories);
  res.json({ updated: true, preferences: { memories: updatedUser.personalization?.memories ?? true }});
});
```

### Decision Gate (Use Memory On/Off)
If the user opted out, the memory pipeline exits early.

```721:742:viventium_v0_4/LibreChat/api/server/controllers/agents/client.js
async useMemory() {
  const user = this.options.req.user;
  if (user.personalization?.memories === false) return;
  const memoryConfig = appConfig.memory;
  if (!memoryConfig || memoryConfig.disabled === true) return;
  ...
}
```

### Memory Loading (Synchronous)
`createMemoryProcessor` **fetches all memories** for the user from Mongo and formats them. This is awaited before the main run starts.

```436:441:viventium_v0_4/LibreChat/packages/api/src/agents/memory.ts
const { withKeys, withoutKeys, totalTokens } =
  await memoryMethods.getFormattedMemories({ userId });
```

```121:152:viventium_v0_4/LibreChat/packages/data-schemas/src/methods/memory.ts
const memories = await getAllUserMemories(userId);
const sortedMemories = memories.sort(...);
const withKeys = sortedMemories.map(...).join('\n\n');
const withoutKeys = sortedMemories.map(...).join('\n\n');
```

### Memory Agent Run (Concurrent LLM Call)
When enabled, memory processing launches a **separate LLM run** (default config uses `xai/grok-4-1-fast-reasoning`).

```333:349:viventium_v0_4/LibreChat/packages/api/src/agents/memory.ts
const defaultLLMConfig = {
  provider: Providers.OPENAI,
  model: 'gpt-4.1-mini',
  streaming: false,
  disableStreaming: true,
};
const finalLLMConfig = { ...defaultLLMConfig, ...llmConfig, streaming: false, disableStreaming: true };
```

```375:404:viventium_v0_4/LibreChat/packages/api/src/agents/memory.ts
const run = await Run.create({ ..., llmConfig: finalLLMConfig, tools: [memoryTool, deleteMemoryTool] });
const content = await run.processStream(inputs, config);
```

### Why “Use Memory” Can Add Seconds
1) **Pre-run DB fetch + formatting** is awaited. If memory entries are large or numerous, this can be slow.  
2) **Memory agent run** adds a **second LLM call** using your XAI key. Even if it doesn’t block the main run, it can still compete for quota/latency with your primary agent.  
3) **Prompt bloat**: `withoutKeys` is appended to system instructions, increasing token count and slowing the main model.

---

## Direct Answers to Your Questions

### 1) VAD settings alone are not a 5s cause
Correct. The VAD min silence (0.5s) is a fraction of the delay. The bigger synchronous wait is Phase A background cortex detection (2s budget) plus memory pre-processing.

### 2) Concurrency limits are not a 2s wait
Correct. The concurrency limiter **does not wait**; it rejects when over limit. Additionally, voice sessions **bypass** the limiter by default.

```17:81:viventium_v0_4/LibreChat/api/server/controllers/agents/request.js
function isVoiceConcurrencyBypassed(req) { ... default true ... }
if (!bypassConcurrency) { checkAndIncrementPendingRequest(...) } else {
  logger.debug('[concurrency] Bypassing concurrent request limit for voice session');
}
```

### 3) Main agent is fast, but memory agent is separate
Your main agent can be fast (`grok-4-1-fast`), but the **memory agent is configured separately** (xAI `grok-4-1-fast-reasoning`) and can still consume latency and provider quota.

---

## Likely Contributors to the ~5s Delay (Ranked)
1) **Background cortex Phase A detection** (up to ~2s, awaited).  
2) **Memory pre-processing** (DB read + formatting + agent init).  
3) **Memory agent LLM run** competing for XAI quota (especially if both use same key).  
4) **Prompt bloat** from memory injection increasing tokens.  
5) **SSE stream retries** if streaming doesn’t start cleanly (max 2 retries x 0.5s).

---

## What to Measure Next (No Changes Yet)
- Enable voice latency logging to measure:
  - `voice_chat_ready_ms` (time to streamId)
  - `ttft_ms` (time to first token)
  - `stream_done_ms` (time to completion)

These logs are already instrumented but disabled by default.

---

## Conclusion
The 5s delay is **most consistent** with:
- the **2s background cortex detection budget**, plus
- **memory pre-processing and/or memory agent concurrency**.

---

## Local Fast Profile Addendum (2026-03-05)
Local env was updated to align with the cloud Phase A/background values that reduce voice-call startup delay:

```env
VIVENTIUM_VOICE_BACKGROUND_AGENT_DETECTION_ASYNC=true
VIVENTIUM_VOICE_PHASE_A_AWAIT_MS=500
VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=false
```

Related Phase B controls currently used in code:
- `VIVENTIUM_PHASE_B_STREAM_WAIT_MS` (default `180000` ms in `api/server/controllers/agents/request.js`)
- `VIVENTIUM_DEBUG_PHASE_B` (debug logging flag in agent runtime/background services)

These Phase B vars are not currently exported in the cloud snapshot as explicit env values, so local tuning should be applied intentionally (only if follow-up delivery timing or debug visibility requires it).

Disabling “Use memory” bypasses the entire memory pipeline and is expected to reduce the delay, which matches your observation.
