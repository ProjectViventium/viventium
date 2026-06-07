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

Historical note:
- This January 22, 2026 cloud snapshot used xAI for the memory writer.
- As of April 5, 2026, the public config compiler no longer treats that xAI value as the product
  default for generated local/runtime config. Memory provider/model must now be compiled from the
  actually configured foundation provider (`openai` / `anthropic`) instead of preserving a hidden
  xAI dependency.

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
When enabled, memory processing launches a **separate LLM run**. In the January 22, 2026 cloud
snapshot shown above, that memory writer used `xai/grok-4-1-fast-reasoning`.

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
Your main agent can be fast, but the **memory agent is configured separately** and can still
consume latency and provider quota. In the January 22, 2026 cloud snapshot above, that separate
memory writer was xAI `grok-4-1-fast-reasoning`.

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
Historical note: the values in this addendum were superseded by the May 30 two-mode contract in
`02_Background_Agents.md`. Current generated runtime defaults are voice async ON with
`VIVENTIUM_VOICE_PHASE_A_AWAIT_MS=690`,
`VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=true`, and text async OFF with
`VIVENTIUM_TEXT_PHASE_A_AWAIT_MS=1300`.

Older local env was updated to align with the Phase A/background values that reduce voice-call startup
delay without letting the main voice LLM start before Phase A knows whether background processing is
active:

```env
VIVENTIUM_CORTEX_PHASE_A_NOTICE_MODE=any_activated_on_voice
VIVENTIUM_VOICE_BACKGROUND_AGENT_DETECTION_ASYNC=false
VIVENTIUM_VOICE_PHASE_A_AWAIT_MS=500
VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=false
```

Related Phase B controls currently used in code:
- `VIVENTIUM_PHASE_B_STREAM_WAIT_MS` (default `180000` ms in `api/server/controllers/agents/request.js`)
- `VIVENTIUM_DEBUG_PHASE_B` (debug logging flag in agent runtime/background services)

These Phase B vars are not currently exported in the cloud snapshot as explicit env values, so local tuning should be applied intentionally (only if follow-up delivery timing or debug visibility requires it).

Disabling “Use memory” bypasses the entire memory pipeline and is expected to reduce the delay, which matches your observation.

---

## Local LiveKit RCA Addendum (2026-05-14)

Scope: local LiveKit modern-playground calls using the v0.4 LibreChat stack and a user-configured
main-agent Voice Call LLM route.

### What "Phase A instant" actually means

The product requirement is that the user hears a natural first response quickly after the end of
their utterance. In the current architecture, however, "Phase A" is not a separate cheap audible
acknowledgement. It is the first streamed answer from the same main-agent LLM path used by text chat.

For a simple call turn like "Hey, can you hear me?", the current first-audio path still includes:

1. LiveKit turn completion and STT final transcript.
2. Voice gateway `POST /api/viventium/voice/chat`.
3. Call-session auth, conversation/parent resolution, and voice route setup.
4. Agent initialization, model override validation, prompt/message assembly, and prompt-frame
   telemetry.
5. Phase A background-cortex activation policy. When async is enabled, this can defer after a short
   await window; when unsafe direct-action holds are unowned, it may still run synchronously.
6. Main Voice Call LLM request and provider first token.
7. LibreChat SSE stream delivery back to the voice gateway.
8. TTS first audio.

So "Phase A should feel instant" currently means "the main LLM path should reach first token
quickly." It does **not** mean the system already has a separate pre-LLM voice acknowledgement like
"Yeah, I hear you." If the desired UX requires sub-second "I heard you" feedback even when the main
LLM is still preparing, that should be implemented as a distinct acknowledgement layer with strict
rules so it does not replace or contradict the real Phase A answer.

### `{NTA}` and why silence can feel like a skipped Phase A

`{NTA}` means "no text/audio response." It is valid in passive modes and follow-up adjudication, but
it is not a spoken acknowledgement. If the main Phase A answer resolves to `{NTA}`, the voice
gateway intentionally suppresses speech. If a later Phase B follow-up also resolves to `{NTA}`, the
user hears nothing because both model decisions chose silence. That is correct for Wing or
listen-only-adjacent behavior, but it is wrong for a directly addressed ordinary call turn unless
the prompt/policy explicitly intended silence.

Debugging "Phase A was skipped" must therefore check which of these happened:

- no Phase A request was launched
- Phase A launched but waited on setup/detection/provider first token
- Phase A returned `{NTA}` and was intentionally silent
- Phase A produced text, but the gateway/SSE/TTS path failed before first audio

### What "direct-action tool-hold candidate" means

A direct-action tool-hold candidate is **not** generic background-agent activation and it is not
web search. It is a background-cortex activation scope that may require live productivity/tool work,
for example a Google Workspace or Microsoft 365 scheduling/action scope.

Example:

- User says: "Move my 3 PM meeting to tomorrow."
- A scheduling/productivity cortex is configured with a hold scope.
- If the main agent does not actually own the matching calendar tool surface, an immediate answer
  like "Sure, moving it now" would be unsafe.
- In that case runtime may hold the first answer until the direct-action ownership situation is
  known.

The previous policy treated "some configured hold scope exists" as enough to force synchronous Phase
A for voice. The low-risk refinement is more precise: if the current main agent already owns the
matching direct-action tools/surfaces, Phase A can stay async. Only unowned direct-action hold
scopes force synchronous Phase A.

### Prompt/runtime context map for the large voice prompt frames

The large prompt-frame telemetry observed on simple voice turns is not one single Markdown prompt.
It is the assembled runtime context created by several layers:

| Layer | Owner | Why it appears |
| --- | --- | --- |
| Main agent instructions | live agent config / prompt bundle | Viventium identity, truth, memory, tool, background-agent, and behavior policy |
| Surface prompt | `surfacePrompts.js` and voice provider capability contracts | voice style and provider-specific TTS/markup rules |
| Time/context cards | AgentClient runtime | current time and request metadata |
| Memory/context | memory and background-context services | user memory and relevant context when enabled |
| Conversation recall | recall layer | prior-chat summaries or retrieved context when available |
| MCP/server/tool instructions | MCP manager and tool schemas | capability advertisements and action contracts |
| Background-cortex runtime cards | background-cortex orchestration | which cortices exist, how activations/follow-ups relate to the main response |
| Recent messages/tool results | conversation persistence and run assembly | visible turns, tool calls, and returned evidence |

Observed local telemetry before this fix showed simple voice turns carrying about 90k characters in
`main_runtime` instructions plus additional memory/background context in some turns. That explains
why a "simple" utterance can still pay setup and model-ingestion cost: the request is preserving
full Viventium parity, not using a stripped-down voice bot prompt.

The parity-preserving fix is **not** a voice-only memory/prompt budget that silently removes context
from calls. The safer path is:

- keep prompt-frame logging on the decisive voice paths so every turn reports layer sizes and hashes
  without raw private text
- reduce duplicated instructions at the correct ownership layer, shared across text/voice/Telegram
- move capability manuals to MCP/tool instructions where they belong
- use provider/runtime prompt caching or client prewarming where supported
- keep exact-model evals and live QA before deleting behaviorally important prompt text

### Weather/web-search delay finding

The weather-style voice turn that took about 26 seconds to first audible text was dominated by tool
orchestration:

- background activation and setup consumed the early seconds before the main model run
- the first xAI call produced a `web_search` tool call instead of user-facing text
- the local web-search tool call completed much later
- a second xAI call then produced the final text

That means the 26-second TTFT was not explained by STT speed or by Grok 4.3's raw first-token speed.
It was the app path: tool choice, local tool execution, and second-hop synthesis before any audible
answer.

Direct provider probes on 2026-05-14 showed:

| Probe | First event | First text | Total | Notes |
| --- | ---: | ---: | ---: | --- |
| xAI Chat Completions, `grok-4.3`, `reasoning_effort: "none"` | ~0.8s | ~0.8s | ~0.8s | no reasoning events |
| xAI Responses API with built-in `web_search`, `reasoning.effort: "none"` | ~1.0s | ~3.2s | ~3.3s | server-side tool events observed |

Official xAI docs currently state that `grok-4.3` supports `reasoning_effort`, that `"none"`
disables reasoning, and that built-in `web_search` is available on the Responses API while legacy
Chat Completions live search is deprecated:

- https://docs.x.ai/developers/model-capabilities/text/reasoning
- https://docs.x.ai/developers/tools/web-search

Because Viventium's current xAI voice route is Chat Completions, the least-risk immediate fix is to
wire `reasoning_effort: "none"` correctly for the existing route. Replacing the voice route with
xAI Responses + built-in web search is a larger design change because it changes endpoint semantics,
tool event handling, citations, retry behavior, and fallback behavior. It is promising for weather
or current-web turns, but should be evaluated as a follow-up with parity tests rather than mixed
into the low-risk latency fix.

### Applied low-risk fixes

- The config compiler now emits the documented voice Phase A env:
  `VIVENTIUM_CORTEX_PHASE_A_NOTICE_MODE=any_activated_on_voice`,
  `VIVENTIUM_VOICE_BACKGROUND_AGENT_DETECTION_ASYNC=true`,
  `VIVENTIUM_VOICE_PHASE_A_AWAIT_MS=690`, and
  `VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=true`.
- Fully async voice background detection is now the shipped default; text async remains an explicit
  opt-in via its independent text flag.
- Fully async opt-in detection explicitly keeps `all_within_budget` detection semantics in the
  background so Phase B receives the complete activated set. The `any_activated_on_voice`
  early-notice behavior belongs to the shipped sync Phase A path.
- The config compiler also emits `VIVENTIUM_VOICE_LOG_LATENCY=1` so the real local runtime captures
  sub-second route, init, Phase A, provider, stream, and TTS timing without hand-editing generated
  App Support files.
- Phase A async policy now distinguishes owned vs unowned direct-action hold scopes.
- Voice Phase A async policy now rechecks canonical main-agent tools before treating direct-action
  hold scopes as unowned. This prevents voice turns from forcing synchronous Phase A merely because
  the request-scoped agent object was loaded before its tool list was hydrated.
- The xAI Voice Call LLM parameter path now preserves `reasoning_effort: "none"` for Chat
  Completions and strips provider-incompatible inherited thinking fields.
- Voice-mode reasoning deltas are now treated as provider internals, not transcript content. If the
  provider emits `on_reasoning_delta` despite the no-reasoning profile, LibreChat logs the first
  suppression event, does not stream that delta to the voice resumable stream, and filters
  `type: "think"` from persisted voice assistant content.
- When `VIVENTIUM_VOICE_LOG_LATENCY=1` is enabled, voice provider fetch telemetry records sanitized
  request knobs such as model,
  `reasoning_effort`, `reasoning.effort`, `include_reasoning`, stream flag, message count, and tool
  count. It intentionally does not log prompt text, message text, auth headers, or provider keys.
- The voice gateway now supplies a per-turn stream id to LibreChat, so sequential voice turns can be
  correlated and do not depend on conversation id as an implicit stream identifier.
- The current local source-of-truth main-agent voice route is `xai / grok-4.3` with
  `voice_llm_model_parameters.reasoning_effort: "none"`; live DB must be synced and verified through
  the agent sync path rather than by relying on hand-edited runtime state.

### Microtiming addendum (2026-05-19)

The `~0.35-0.40s` voice route ready delay was not basic byte transfer. A code trace found an
intentional live voice ingress coalescing wait: `VIVENTIUM_VOICE_TURN_COALESCE_WINDOW_MS` had a
350ms default. That wait was useful for merging fragmented same-parent ingress, but it sits before
the route returns the stream id, so it directly delays every normal spoken response.

Applied behavior:

- Normal live voice now defaults to `VIVENTIUM_VOICE_LIVE_TURN_COALESCE_WINDOW_MS=0`.
- The legacy `VIVENTIUM_VOICE_TURN_COALESCE_WINDOW_MS` still overrides the shared behavior when
  explicitly set.
- Listen-Only keeps a separate ambient transcript merge default:
  `VIVENTIUM_VOICE_LISTEN_ONLY_TURN_COALESCE_WINDOW_MS=350` when the shared value is unset.
- Route latency logs now include `coalesce_window_ms`, so a future trace can distinguish deliberate
  buffering from auth, conversation lookup, or job setup.

Auth/session and parent-resolution hot-path work was also tightened:

- Voice chat auth now performs the successful call-session existence check and worker lease claim in
  one atomic `findOneAndUpdate`. The extra session lookup is kept only on the error path to return
  the right 401/403 reason.
- Voice route logs split auth into `voice_auth_session_claim_done` and `voice_auth_user_done`.
- Parent resolution now projects only fields needed to validate the conversation and find the latest
  leaf (`conversationId`, `endpoint`, `agent_id`, ids, parent ids, timestamps, and listen-only
  metadata), instead of loading full message text/content before stream readiness.
- For voice requests whose server-side conversation resolution already proved the exact
  user-owned conversation, the later generic `validateConvoAccess` middleware is skipped and logged
  as `status=skipped_verified_voice`. If the earlier lookup failed, reset the conversation to
  `new`, or otherwise did not prove ownership, the generic validation still runs.

Local DB micro-benchmark against the current development MongoDB after the code changes:

| Hot-path operation | Median |
| --- | ---: |
| Combined session claim `findOneAndUpdate` | 0.309ms |
| User fetch projection | 0.255ms |
| Conversation validate projection | 0.210ms |
| Parent messages projected | 0.240ms |
| Voice ingress create+find with no sleep | 0.450ms |

For the sampled conversation, projected parent-message payload was 944 bytes versus 6572 bytes for
the old full-message shape. The important conclusion is practical: local DB/auth is not the
multi-hundred-millisecond wall in the measured route-ready delay; the default live coalescing sleep
was. The DB work should still stay measured and narrow because large conversations can make full
message reads expensive.

Phase A notice has an explicit latency mode now:

- Default is `VIVENTIUM_CORTEX_PHASE_A_NOTICE_MODE=any_activated_on_voice`: voice calls can
  release Phase A after the first true activation, while web, Telegram, scheduler, and other
  text surfaces continue to use `all_within_budget`.
- `any_activated` releases Phase A after the first true activation while final detection continues.
- `all_within_budget` remains available when a deployment needs every surface to wait for the full
  activation detection budget before Phase A.
- Early release injects a generic "background is brewing and full detection is still pending"
  instruction, not a first-agent result summary. Phase B waits for final detection and executes the
  final activated set.
- If any configured tool-hold cortex has an unowned direct-action scope on the current request, the
  effective notice mode falls back to `all_within_budget`.

The high-resolution latency log format now includes both rounded milliseconds and fractional
milliseconds (`*_ms_f`) for sub-0.01s analysis of route, controller, Phase A, tool/MCP, provider,
and stream stages.

### Remaining live validation

The local stack and browser surface were verified healthy after restart, but an old shared
call-session URL correctly returned `Unknown or expired call session`. A fresh authenticated
LiveKit call is still required to capture the post-fix end-to-end timing profile:

- STT final transcript time
- voice route ready/stream id time
- Phase A async/deferred/forced-off decision and reason
- model provider request headers and first text delta
- SSE subscribe time
- TTS first audio
- Phase B follow-up schedule/start/result

### Deep local timing profile addendum (2026-05-14)

After restarting the local stack with `VIVENTIUM_VOICE_LOG_LATENCY=1`, a warmed synthetic voice
turn through the canonical LibreChat voice route showed that xAI no-reasoning is wired correctly
but does not, by itself, make the call feel instant.

Simple prompt: `can you hear me`

| Stage | Elapsed from route entry | Stage cost | Meaning |
| --- | ---: | ---: | --- |
| Route entered | 0ms | 0ms | `/api/viventium/voice/chat` accepted the worker request |
| Parent/body normalized | 1ms | 1ms | call session resolved to the server-owned conversation state |
| Stream id returned | 415-416ms | ~415ms | voice gateway can subscribe to SSE |
| Client init started | 416ms | 0ms | async generation setup begins after the route has replied |
| Voice model override validated | 417ms | ~1ms | live agent voice route resolves to `xai / grok-4.3` |
| Primary agent/tool init done | 2540ms | 2123ms | 29 tool definitions loaded; Google Workspace OAuth-pending probe happened here |
| Client init done | 4570ms | 4154ms total | fallback/init work added another ~2030ms after primary init |
| Chat completion started | 4697ms | ~127ms | message/prompt assembly enters the Agent run |
| Phase A policy checked | 4698ms | 1ms | async was requested but forced off |
| Phase A activation detection done | 5200-5201ms | 502-503ms | 0/11 cortices activated; 10 timed out under the 500ms budget |
| Run created | 5352ms | 148ms | LangGraph/Agents run object ready |
| First chat model/provider request | 5476ms | 124ms | outbound xAI request starts |
| Provider headers | ~6216ms | 740ms | xAI returned HTTP 200 and opened the stream; this is not first text |
| First assistant message delta | 7096ms | 1620ms from provider start | first audible text candidate |
| Chat completion done | 7360ms | 2663ms from chat start | main answer generation finished |
| Send message done | 8048ms | 3478ms from send start | persistence/finalization completed |

Plain-language definitions:

- `provider_fetch_headers` means the HTTP request to xAI reached `api.x.ai`, xAI accepted it, and
  the response stream opened with status 200. It does **not** mean the model has produced text yet.
- `first_message_delta` is the first assistant text chunk that the voice gateway can turn into
  speech.
- `Phase A` here is background-cortex activation detection. It is not a separate cheap spoken
  acknowledgement.
- `unowned_tool_hold_candidate_configured` means at least one background cortex is configured with a
  direct-action hold scope, such as Google Workspace or Microsoft 365 productivity actions, but the
  current request's tool set does not own that scope. The safety policy therefore blocks async
  Phase A so the system does not speak ahead of a possible direct action. In this trace, that
  conservative block cost about 500ms even though no cortex activated.

The measured gap versus raw xAI is:

| Path | First text |
| --- | ---: |
| Raw xAI, tiny prompt, `grok-4.3`, `reasoning_effort: "none"` | ~0.69-0.79s |
| Raw xAI, ~46k synthetic system prompt | ~1.06-1.28s |
| Viventium voice route, warmed simple turn | ~7.10s |

So the post-fix provider/model segment is now roughly in the expected range for a large prompt
(about 1.6s from provider request to first text), but the full voice route still pays about 5.5s of
pre-provider orchestration before the provider can help.

Second-opinion review from Claude validated the broad RCA and corrected two details:

- The second Google Workspace OAuth-pending attempt is largely a fallback-agent initialization
  effect, not just a retry loop. Primary init cost about 2.1s; total client init cost about 4.15s.
  The fallback route currently repeats tool/MCP loading on the happy path.
- The existing hydrated-tool Phase A recheck does not help this scenario when request tools are
  already populated but do not own the configured Google Workspace / Microsoft 365 hold scopes.
  Owner decision 2026-05-30: accept the voice-mode async tradeoff and ship
  `VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=true`; first-answer speed wins, while late or
  side-effecting context must surface through Phase B/follow-up evidence.

Recommended least-risk order:

1. Add or surface explicit `fallback_initialize_ms` and OAuth-pending MCP probe timings so the
   existing 4.15s init block is split into primary tools, fallback tools, OAuth-pending probe, and
   memory/prompt work.
2. Reuse per-call or short-TTL OAuth-pending/tool-definition state across primary and fallback
   initialization. Do not probe the same unavailable Google Workspace server twice during a simple
   voice turn.
3. Move fallback-agent full initialization off the happy-path first-token route; validate fallback
   config cheaply and initialize it only when the primary route actually fails.
4. Do **not** implement broad speculative Phase A without a product decision. Activated background
   agents are supposed to be passed into the main agent's Phase A context before the main answer is
   authored. The lower-risk Phase A candidate is a narrow fast no-activation bypass: if detection
   proves that zero cortices activated, release the main response without spending the remaining
   detection budget; if any cortex activates, preserve the normal awareness/hold path.
5. Treat prompt size as a real but secondary provider-side lever. Preserve parity by using shared
   prompt ownership cleanup and provider prompt caching/prewarming, not voice-only truncation.

### Hot-path fix applied (2026-05-14)

The first shipped low-risk latency fix targets the measured `~4.15s` initialization block without
changing agent parity, tool availability, prompt content, or the live DB experiment surface.

Applied behavior:

- Primary agent initialization still loads the configured tools exactly as before.
- The configured fallback route is validated up front, but its full agent/tool/MCP initialization is
  lazy. It runs only when the primary route fails before producing assistant text. On a healthy
  simple voice turn, fallback initialization should no longer consume the extra `~2s` observed in
  the trace.
- OAuth-pending MCP server probes use a short in-process memo (`45s` default,
  `VIVENTIUM_MCP_OAUTH_PENDING_MEMO_TTL_MS` override, `0` disables). If Google Workspace or another
  OAuth MCP is already known to be pending during the current hot path, primary/fallback setup does
  not immediately re-probe it again just to discover the same pending state.
- MCP reinitialization now accepts a pre-resolved server config and request-scoped config-server map,
  following the upstream LibreChat pattern. This avoids duplicate registry/config lookup work where
  the local registry supports request-scoped config servers.
- Voice latency logs now include per-MCP tool-definition fetch outcomes:
  `cache_hit`, `reinit_success`, `oauth_pending`, `oauth_pending_memo_hit`,
  `disabled_by_env`, or `reinit_no_tools`.
- Init summary logs now report `fallback_mode=lazy` when a fallback route is configured. If the
  fallback is actually materialized, a separate `initialize_client_fallback_agent_done` stage logs
  its isolated cost.

Expected impact on the measured simple-turn trace:

| Segment | Before | After expected |
| --- | ---: | ---: |
| Primary tool/MCP init | ~2.12s | unchanged until Google OAuth/auth state is fixed or cached |
| Fallback tool/MCP init on healthy primary path | ~2.03s | removed from first-audio path |
| Repeat OAuth-pending probe inside the memo TTL | ~1-2s per repeat | near-zero memo lookup |
| Provider raw first text | ~0.7-1.6s depending prompt size | unchanged by this fix |

This fix intentionally does **not** add a separate pre-LLM spoken acknowledgement, does **not** turn
on unsafe async direct-action holds, and does **not** strip prompt/memory context for voice only.
Those remain separate product/design decisions.

### LiveKit browser follow-up (2026-05-15)

A fresh authenticated modern-playground call was run after the persistence and low-risk latency
fixes. The synthetic typed-transcript prompt `For QA latency logging after restart, reply exactly:
Kappa. Lambda.` returned `Kappa. Lambda.` in the LiveKit transcript, persisted into the linked
LibreChat conversation, survived reload, and Mongo stored the assistant row as visible text with no
`type: "think"` content part.

Measured simple-turn timing for that browser run:

| Segment | Time |
| --- | ---: |
| Voice gateway POST ready / stream subscribe | 565ms |
| Phase A detection window | ~502ms |
| Provider headers after outbound xAI request | ~770ms |
| First assistant app delta from route entry | ~5.2s |
| Stream done | ~5.4s |

Raw xAI `grok-4.3` with `reasoning_effort: "none"` produced first content in about `1.0s` for both
a tiny prompt and a synthetic prompt around the current main-instruction size. Therefore the
remaining simple-turn gap is mostly Viventium orchestration and framework/gateway timing, not
Grok reasoning being enabled.

Review-only Claude pass on 2026-05-15 agreed with the broad RCA but corrected the next-fix order:

1. First add raw-provider and gateway-audio timing: first raw SSE chunk, first raw content delta,
   first app delta, first post-buffer TTS chunk, and TTS first audio.
2. Split primary tool/MCP init and memory loading; the observed `~2.1s` primary init cost is still
   on the first-audio path.
3. Treat `Message.saveMessage` content-text mirroring as a parity-wide persistence repair, not a
   voice-only fix, and cover non-voice assistant content shapes in regression tests.
4. Only after that consider the narrow Phase A fast no-activation bypass described above.
