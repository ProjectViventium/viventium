<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
# 2026-05-14 Voice Latency Fast-Profile QA

## Scope

Partial local QA for the LiveKit voice latency incident. This run validates low-risk wiring,
provider behavior, runtime health, and browser reachability. It does not claim full end-to-end
post-fix voice latency because the available deep-link call session had expired; a fresh
authenticated LiveKit call is still required for MPV-004 completion.

## Public-Safe Evidence

- Runtime compiler output now includes the documented voice fast-profile env:
  - `VIVENTIUM_VOICE_BACKGROUND_AGENT_DETECTION_ASYNC=true`
  - `VIVENTIUM_VOICE_PHASE_A_AWAIT_MS=500`
  - `VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=false`
- Live experimental main-agent DB config was verified with public-safe fields only:
  - primary route remains `anthropic / claude-opus-4-7`
  - voice route is `xai / grok-4.3`
  - voice params include `reasoning_effort: "none"`
- Targeted regression coverage now verifies that voice-mode reasoning deltas are suppressed before
  stream emission/aggregation and that persisted voice assistant content drops `type: "think"`
  parts while retaining audible text.
- Direct provider probe, using the configured local xAI credential without printing it:
  - Chat Completions `grok-4.3` with `reasoning_effort: "none"`: first text about `0.8s`, no
    reasoning events observed
  - Responses API `grok-4.3` with built-in `web_search` and no reasoning: first tool event about
    `1.0s`, first text about `3.2s`
- Local stack health after restart:
  - LibreChat frontend running
  - LibreChat API running
  - Modern Playground running
  - LiveKit configured
  - voice route configured
- Real-browser Playwright pass:
  - `http://localhost:3300` loaded with title `Viventium Voice Assistant`
  - visible route selectors showed local Whisper listening and local Chatterbox speaking
  - replaying the old shared call URL displayed `Unknown or expired call session` and 401s for
    call-session voice settings, which is expected for an expired call session
  - a public-safe screenshot of the modern-playground home surface was captured under
    `output/playwright/`
- Post-restart voice transcript persistence probe:
  - the current runtime was restarted through the supported modern-playground launcher
  - a synthetic voice-mode request through the canonical LibreChat voice route returned the supplied
    one-turn stream id and used the live DB voice route `xai / grok-4.3`
  - runtime logs showed the normalized voice params included `reasoning_effort=none`
  - Mongo persisted the synthetic assistant message as text-only content parts with no `type:
    "think"` or reasoning part
  - the user-reported screenshot conversation was confirmed as an earlier persisted row containing
    `type: "think"` plus text; reopening that historical conversation can still show a `Thoughts`
    card even after the runtime guard is fixed for new voice turns
- Second fresh synthetic visibility probe:
  - `/api/viventium/voice/chat` returned `200` in about `435ms`
  - the response preserved the caller-supplied per-turn stream id
  - the SSE stream completed successfully in about `10.3s`
  - no reasoning event or `type: "think"` marker was observed in the SSE stream
  - Mongo again persisted one assistant message with text-only content parts and no reasoning block
  - runtime logs showed the model swap and normalized no-reasoning voice params, plus prompt-frame
    layer sizes and the Phase A policy decision
- Post-policy-fix synthetic probe:
  - after the running LibreChat backend restarted from the Phase A policy edit, the same voice route
    returned `200` in about `426ms`
  - the route again preserved the caller-supplied per-turn stream id
  - the SSE stream completed successfully, with no reasoning event or `type: "think"` marker
  - Mongo again persisted one assistant message with text-only content parts and no reasoning block
- Step-1 xAI request-shape verification:
  - upstream LibreChat was checked before patching; it has provider-specific `modelKwargs` handling
    for OpenRouter reasoning and Responses API reasoning handling, but no current xAI/Grok Chat
    Completions no-reasoning bridge
  - current xAI docs identify `grok-4.3` as the model with configurable reasoning, including
    `none`; live provider probes rejected `grok-4.3-non-reasoning` as an unknown model
  - the local xAI Chat Completions shim now passes `reasoning_effort` through LangChain
    `modelKwargs` for `grok-4.3` and current aliases, which is the path that reaches the outbound
    Chat Completions request for this custom endpoint
  - live provider probes showed older xAI non-reasoning slugs reject `reasoning_effort` on Chat
    Completions, so the shim is intentionally scoped to the `grok-4.3` family instead of all xAI
    model names
  - a post-build synthetic voice-mode route run showed provider-fetch telemetry with
    `model=grok-4.3`, `reasoning_effort=none`, `reasoning.effort=unset`, and streaming enabled
  - that corrected run emitted no reasoning delta, persisted no `type: "think"` assistant content,
    and left the remaining multi-second delay attributable to orchestration/provider timing rather
    than the no-reasoning knob being unwired
- Deep warmed synthetic timing profile after restarting with `VIVENTIUM_VOICE_LOG_LATENCY=1`:
  - simple prompt `/api/viventium/voice/chat` route returned a stream id in about `415ms`
  - SSE subscribed in about `480ms`
  - client initialization completed in about `4.15s`
  - primary agent/tool initialization accounted for about `2.12s` of that init time
  - Phase A was configured for `500ms`, async was requested, but it was forced synchronous because
    unowned Google Workspace / Microsoft 365 direct-action hold scopes were configured
  - Phase A consumed about `503ms`, activated `0/11` cortices, and timed out most checks
  - outbound xAI provider request started at about `5.48s`
  - xAI returned HTTP headers in about `740ms`; this means the stream opened, not that text existed
  - first assistant text delta arrived at about `7.10s`
  - no provider reasoning delta was observed in the corrected run
- Raw xAI comparison using the same configured credential:
  - tiny prompts with `grok-4.3` and `reasoning_effort: "none"` produced first text in about
    `0.69s` to `0.79s`
  - a synthetic large prompt around the voice prompt-frame size produced first text in about `1.06s`
    to `1.28s`
  - the remaining gap is therefore mostly pre-provider orchestration, not raw Grok latency
- Claude review status for the deep RCA follow-up:
  - Claude CLI auth check passed
  - structured review completed after waiting for it to finish
  - Claude validated that the xAI no-reasoning request shape is correct and challenged the RCA in two
    useful ways: the second Google Workspace OAuth-pending probe is largely fallback-agent
    initialization repeating tool/MCP loading, and the current hydrated-tool Phase A recheck does not
    help when request tools are populated but do not own the configured direct-action hold scopes

## Automated Checks

- LibreChat API targeted voice suites:
  - `voicePhaseAPolicy.spec.js`
  - `voiceLlmOverride.spec.js`
  - `voice.spec.js`
  - Result: passed
- LibreChat API transcript/stream regressions:
  - `callbacks.spec.js`
  - `requestPersistence.spec.js`
  - Result: passed
- Voice gateway LLM bridge tests:
  - `tests/test_librechat_llm.py`
  - Result: passed
- Config compiler fast-profile env regression:
  - `test_config_compiler_emits_background_followup_window_override`
  - Result: passed
- LibreChat packages API xAI reasoning request-shape regression:
  - `packages/api/src/endpoints/openai/llm.spec.ts`
  - Result: passed
- LibreChat packages API build:
  - `npm run build`
  - Result: passed

## Findings

- The xAI no-reasoning knob is real and fast on the direct provider path. Remaining multi-second
  voice delay must be measured in the Viventium orchestration path, not guessed as raw Grok latency.
- In reality, the xAI no-reasoning fix changed the shape of the delay but did not make the voice
  turn naturally instant: fresh corrected simple turns no longer emit reasoning deltas, and the
  provider segment is about `1.6s` to first text, but the full route still takes about `7.1s` to
  first assistant text because client initialization, tool/MCP loading, fallback initialization, and
  forced synchronous Phase A happen first.
- The first xAI request-shape implementation could look correct inside Viventium because the voice
  config normalized to `reasoning_effort: "none"`, but the custom endpoint path did not guarantee
  that field reached LangChain's final outbound request. The regression now asserts the
  `ChatOpenAI.invocationParams()` shape and live provider-fetch telemetry.
- A visible LibreChat `Thoughts` block after a voice turn means a provider reasoning delta reached
  stream aggregation or persistence. Voice mode must defensively suppress those deltas even when the
  provider request says no reasoning.
- The prior weather-style delay is consistent with local tool orchestration and second-hop answer
  synthesis before any audible text. Provider-native xAI web search is promising but uses the
  Responses API, so it is a follow-up design change rather than a safe flag flip on the current Chat
  Completions voice route.
- A voice-only prompt/context budget was rejected for this incident because it would violate
  parity. The safer path is shared prompt ownership cleanup, prompt-frame telemetry, and provider
  caching/prewarm where supported.
- The prompt is still materially expensive: the warmed simple voice run assembled about `90k`
  `main_runtime` characters and `29` tools. Raw large-prompt xAI probes show this likely contributes
  hundreds of milliseconds inside the provider segment, but it is not the dominant `7s` root cause.
- The least-risk runtime fix is not `VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=true` by itself.
  The aligned fix is speculative Phase A parallelism with an output gate, plus removing duplicated
  fallback/tool/OAuth init from the hot path.
- The expired-call browser result confirms the UI path is reachable and correctly rejects stale
  sessions, but it cannot supply post-fix LiveKit STT/LLM/TTS timings.
- The transcript `Thoughts` failure has a concrete persistence cause: provider reasoning deltas were
  allowed to aggregate into voice assistant content before the guard was added. The post-restart
  synthetic route now proves the persistence guard on the canonical backend route; a fresh user-level
  LiveKit run is still needed to complete the visible call transcript portion of MPV-005.
- The deep provider-fetch timing logs added for this incident are gated by
  `VIVENTIUM_VOICE_LOG_LATENCY=1`; the currently running generated runtime did not have that flag
  set. The always-on logs still prove voice model routing/no-reasoning normalization and prompt
  frame sizes, but the full MPV-004 timing profile should be collected after restarting the local
  stack with latency logging enabled.

## Required Follow-Up

- Start a fresh authenticated modern-playground LiveKit call and run MPV-004 against the already
  instrumented route so the remaining STT-final and TTS-first-audio timing can be added to the
  synthetic backend timing profile.
- Include MPV-005 in that run: verify no visible `Thoughts` block, no persisted `type: "think"` in
  the voice assistant message, and sanitized logs showing either no reasoning deltas or
  `voice_reasoning_delta_suppressed`.
- Capture one simple non-tool turn and one current-data turn.
- Record per-stage timings: STT final transcript, voice route ready, SSE subscribe, Phase A policy
  decision, provider first text, TTS first audio, stream done, and Phase B follow-up result.
- Add the next regression for the confirmed backend bottlenecks: explicit fallback initialization
  timing, one OAuth-pending MCP probe per request/call session, and first-message budget once
  fallback/tool-state reuse is implemented.
- Confirm no `Stream not found`, stale Phase B speech, generic service-failure speech, or raw
  private identifiers in public QA artifacts.
