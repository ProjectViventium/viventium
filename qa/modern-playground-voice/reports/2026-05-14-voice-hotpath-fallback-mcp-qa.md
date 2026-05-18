<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
# Voice Hot-Path Fallback and MCP Init QA - 2026-05-14

## Scope

This pass covered the approved low-risk hot-path fixes for delayed voice responses:

- make fallback LLM initialization lazy instead of eagerly paying fallback tools/MCP cost on every healthy primary turn
- backport/follow upstream LibreChat's `configServers` / `serverConfig` MCP plumbing so config-source MCP resolution is done once per request and passed through reinitialize/connection paths
- memoize OAuth-pending MCP probes briefly so adjacent turns do not repeatedly pay the same failed auth initialization
- keep live user-level agent settings intact; no live DB sync or source-of-truth overwrite was performed

Out of scope for this pass: changing the voice Phase A tool-hold product policy. Runtime evidence below shows that policy still blocks first audio by about 500 ms on the tested turn.

## Evidence

Runtime ports after restart:

- LibreChat API: `3180`
- LibreChat frontend: `3190`
- Modern voice playground: `3300`
- Voice gateway health: `8301`

Endpoint checks:

- `GET /api/config` on API returned `200` in about `4 ms`
- voice gateway `/health` returned `200` in about `2 ms`

Live DB agent config inspection:

- Main text route remains `anthropic` / `claude-opus-4-7`
- Voice route is `xai` / `grok-4.3`
- Voice model parameters include `reasoning_effort: none`
- Voice fallback route remains `openAI` / `gpt-5.4`

Runtime env inspection:

- `VIVENTIUM_VOICE_BACKGROUND_AGENT_DETECTION_ASYNC=true`
- `VIVENTIUM_VOICE_PHASE_A_AWAIT_MS=500`
- `VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=false`

Upstream comparison:

- Upstream LibreChat `main` already has `resolveConfigServers`, request-scoped `configServers`, and `serverConfig` MCP plumbing in the same ownership path.
- The local change follows/backports that upstream pattern instead of inventing a separate Viventium-only MCP config path.
- The lazy fallback LLM path is Viventium-specific because upstream LibreChat does not have this agent fallback feature.

## Timing Profile

Synthetic authenticated voice route request:

- request body included `voiceMode=true`, `viventiumInputMode=voice_call`, `viventiumSurface=voice`
- route returned a stream id in about `436 ms`
- DB cleanup removed the synthetic call session, ingress row, messages, and conversation created by the test

Backend voice latency logs for that turn:

- voice model selected: `xai` / `grok-4.3`
- reasoning config: `reasoning_effort=none`, `thinking_enabled=false`
- Phase A async was still forced off: `unowned_tool_hold_candidate_configured`
- Phase A detection cost: about `501 ms`
- `create_run_done`: about `119 ms`
- provider HTTP headers from xAI: about `638 ms`
- first message delta from model phase start: about `2734 ms`
- first message delta from route entry: about `5973 ms`

Raw xAI benchmarks from the same machine/key:

- `grok-4.3` minimal prompt with `reasoning_effort=none`: first content about `860 ms`, done about `1020 ms`
- same minimal prompt without the reasoning parameter: first content about `3008 ms`
- DB agent instructions, no tools, `reasoning_effort=none`: first content about `1286 ms`
- DB agent instructions plus 29 simple tools, `reasoning_effort=none`: first content about `1026 ms`

Interpretation:

- The live voice LLM knob is wired; the tested voice path is not using Grok reasoning/thinking.
- The raw API test proves `reasoning_effort=none` materially improves first content for Grok 4.3.
- Remaining delay is now split between Viventium orchestration and provider/framework streaming behavior:
  - about `501 ms` from forced synchronous Phase A
  - about `638 ms` to xAI response headers
  - about `2.1 s` between xAI headers and the first application-level message delta
  - earlier route/init/prompt/run setup before model start still contributes to total route-entry timing

## Tests

Passed:

- `cd viventium_v0_4/LibreChat/api && npm run test:ci -- server/controllers/agents/client.test.js server/services/Tools/mcp.spec.js server/services/viventium/__tests__/voicePhaseAPolicy.spec.js --runInBand`
  - `115` tests passed
- `cd viventium_v0_4/LibreChat/packages/api && npx jest src/mcp/registry/__tests__/MCPServersRegistry.test.ts src/mcp/__tests__/MCPManager.test.ts --runInBand --coverage=false`
  - `51` tests passed
- `cd viventium_v0_4/LibreChat/packages/api && npm run build`
  - `dist` built successfully

Browser QA:

- Playwright loaded `http://127.0.0.1:3300`
- Page title: `Viventium Voice Assistant`
- Snapshot confirmed the modern playground rendered voice listening/speaking controls
- Screenshot saved locally under `output/playwright/voice-playground-2026-05-14.png`

Claude review:

- Claude auth check returned `CLAUDE_OK`
- Structured review-only Claude helper produced no output after about nine minutes and was terminated
- A smaller direct review-only Claude prompt also produced no output after about two minutes and was terminated
- Result: Claude second opinion was attempted but unavailable/hung; it is not counted as completed review evidence

## Findings

1. Fallback initialization was a real healthy-path waste.
   Before this change, the primary route could pay fallback `initializeAgent` and fallback MCP/tool loading even when the primary model succeeded. The fix validates fallback eligibility up front but only materializes fallback tools/client config when the primary fails before visible assistant text.

2. MCP config resolution now matches upstream ownership.
   The local fork now passes pre-resolved config-source MCP server config through the same layers upstream uses. This reduces repeated config resolution and lowers stale/global MCP config risk.

3. OAuth-pending MCP probes should no longer repeatedly tax adjacent turns.
   The memo is intentionally short TTL and same-user/same-server scoped. It does not authenticate or hide the need for OAuth; it avoids repeating the same known pending probe immediately.

4. The voice model knob is wired correctly.
   The corrected voice-mode synthetic request showed `xai/grok-4.3` with `reasoning_effort=none` and `thinking_enabled=false`.

5. The remaining "why is it still delayed?" root cause is not model reasoning.
   Current evidence points to synchronous Phase A policy plus application/provider streaming timing. The biggest unexplained post-header gap is between xAI headers and first application-level message delta.

6. Phase A is still not instant.
   The policy still forces synchronous Phase A whenever an unowned direct-action tool-hold scope exists in the configured background cortices. In this live config, the main agent owns Google Workspace tools but not MS365 tools, so the MS365 background cortex keeps voice Phase A on the hot path even for a simple "can you hear me" test.

## Proposed Next Fixes For Review

1. Do not silently loosen tool-hold safety in this patch.
   This remains a product-behavior decision because unowned Google/MS365 tool-cortex activation can require a visible hold/ack rather than a normal answer. The safest next design is to separate "configured unowned tool-hold scope exists" from "this turn actually activated an unowned tool-hold cortex."

2. Add a reviewed Phase A voice policy upgrade.
   Candidate design: allow Phase A async for normal voice turns, but if async Phase A later activates an unowned direct-action tool cortex, emit a deterministic voice-safe hold/follow-up state instead of letting the main model hallucinate tool results. This preserves parity better than disabling context or using keyword shortcuts.

3. Add exact provider streaming instrumentation.
   The current telemetry measures xAI headers and application-level first delta. Add per-provider first raw SSE data chunk / first raw content delta timing inside the xAI/OpenAI-compatible fetch patch, then compare that to LangChain/message delta emission. This will identify whether the remaining ~2 s is provider-side generation, framework buffering, or Viventium event handling.

4. Run a manual LiveKit playground call after this patch.
   The synthetic route validates the backend path and model selection. A user-level LiveKit test is still needed to record actual end-of-speech to first audible audio, including STT finalization and TTS start.
