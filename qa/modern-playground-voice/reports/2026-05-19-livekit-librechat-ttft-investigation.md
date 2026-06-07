<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# LiveKit -> LibreChat TTFT Investigation

Date: 2026-05-19

## Scope

Investigate the delay after a modern LiveKit playground final STT transcript appears and before the
first LibreChat LLM text appears. This report focuses on the boundary after STT finalization:

`final transcript -> voice gateway POST -> LibreChat voice route -> Phase A activation -> provider first text`

No secrets, private transcript text, call-session ids, personal paths, or user identifiers are included.

## Requirement Alignment

- Voice calls must reuse the standard Agents pipeline with text-chat parity.
- Phase A is the first main-agent answer path, not a separate cheap acknowledgement.
- Broad speculative Phase A is not aligned: activated background cortices must be known and passed
  into the main answer context when applicable.
- Direct-action tool-hold scopes must not be bypassed by starting the main answer before ownership
  and activation state are known.
- Voice model overrides must preserve voice-specific low-latency parameters and must not leak
  primary-model thinking fields into the voice request.

## Tests Run

| Test | Result |
| --- | ---: |
| Local API baseline, `GET /api/config` x10 | median 1ms, min 1ms, max 32ms |
| Direct xAI `grok-4.3`, `reasoning_effort: none`, small prompt, run 1 | first text 1201ms |
| Direct xAI `grok-4.3`, `reasoning_effort: none`, small prompt, run 2 | first text 672ms |
| Direct xAI `grok-4.3`, `reasoning_effort: none`, ~48k static prompt | first text 950ms |
| Direct Anthropic `claude-opus-4-7`, no `thinking` field, small prompt, run 1 | first text 794ms, no thinking block observed |
| Direct Anthropic `claude-opus-4-7`, no `thinking` field, small prompt, run 2 | first text 665ms, no thinking block observed |
| Direct Anthropic `claude-opus-4-7`, no `thinking` field, ~48k static prompt | first text 2506ms, no thinking block observed |
| Direct Groq, 11 parallel activation-like classifier requests | wall 904ms; 7/11 under 500ms; provider usage total_time about 90-100ms/request |
| LibreChat xAI full voice path, synthetic handoff | first text 2310ms in logs; route benchmark saw 2316ms |
| LibreChat xAI with diagnostic Phase A suppression | first text 1941ms in logs; route benchmark saw 1950ms |
| LibreChat Opus full voice path, synthetic handoff | first text 2986ms in logs; route benchmark saw 2989ms |
| LibreChat Opus with diagnostic Phase A suppression | first text 2955ms in logs; route benchmark saw 2960ms |
| Targeted voice route regression after live coalesce default change | 28/28 passed; normal voice logs `coalesce_window_ms=0` |
| Call session + voice route regression after atomic auth claim | 43/43 passed |
| Voice LLM override, fallback, Phase A notice regressions | 59/59 passed |
| Combined targeted regression suite after Claude fixes | 121/121 passed |
| Local Mongo hot-path microbenchmark after code changes | auth/session/user/conversation/message steps all sub-1.1ms max in sample |
| Modern playground Playwright shell check | `http://localhost:3300` loaded Viventium Voice Assistant and showed local STT/TTS selections |
| Fake-microphone LiveKit Listen-Only smoke test | PASS: 1 transcript message, expected text matched, active job present, synthetic DB cleanup deleted 1 user/session/ingress/message/conversation |
| Voice playground dispatch release contract | PASS: `uv run --with pytest pytest tests/release/test_voice_playground_dispatch_contract.py -q` -> 29 passed |

The synthetic handoff benchmark used the real LibreChat voice route and the real resumable voice SSE
stream. It did not use a mocked Agents controller. Temporary synthetic call-session rows were cleaned
up after the route tests.

## xAI Full Path Breakdown

Representative xAI voice route run:

| Stage | Elapsed |
| --- | ---: |
| `/api/viventium/voice/chat` ready | 355ms |
| client init done | 365ms |
| chat completion start | 385ms |
| Phase A activation done | 889ms total, 503ms stage |
| create run done | 990ms total, 98ms stage |
| first chat model start | 1004ms |
| xAI response headers | 673ms after provider fetch start |
| first message delta | 2310ms total |
| chat completion done | 2428ms total |
| message save/finalization done | 3736ms total |

Activation details: 5 of 11 classifier calls returned false by 228-463ms; 6 timed out at about 497ms.
Because the runtime waits for every per-cortex wrapper to resolve or time out, the slowest checks set
the Phase A wall time.

## Opus Full Path Breakdown

Representative Opus voice route run:

| Stage | Elapsed |
| --- | ---: |
| `/api/viventium/voice/chat` ready | 389ms |
| client init done | 698ms |
| chat completion start | 734ms |
| Phase A activation done | 1246ms total, 511ms stage |
| create run done | 1433ms total, 185ms stage |
| first chat model start | 1547ms |
| Anthropic response headers | 1406ms after provider fetch start |
| first message delta | 2986ms total |
| message save/finalization done | 6209ms total |

Diagnostic Phase A suppression still showed `thinking_enabled=true` in the Anthropic invoke path and
first text at 2955ms. This means the Opus voice route was not a clean "thinking=false" comparison,
despite the voice model parameter bag containing `thinking: false`.

## Updated Root Cause

The 2+ seconds is not caused by transferring a small transcript string from LiveKit/gateway to
LibreChat. The transfer and local HTTP layer are effectively negligible compared with the app gates.

The user-visible delay is mainly:

1. Voice route setup: previously about 0.35-0.40s, dominated by the old 350ms live ingress
   coalescing default, not by byte transfer.
2. Phase A background-cortex activation: about 0.50s under the current voice budget.
3. Run creation/orchestration: about 0.10-0.24s in these tests.
4. Provider first text: xAI about 1.3-1.5s through LibreChat; Opus about 1.4-2.3s through LibreChat,
   with evidence that Anthropic voice thinking may still be enabled.

## Fixes Applied In This Pass

| Area | Change | Evidence |
| --- | --- | --- |
| Live route readiness | Normal live voice coalescing default changed to `0ms`; Listen-Only keeps a separate 350ms ambient merge default | Route regression passed and verified `coalesce_window_ms=0` |
| Auth/session DB | Successful voice auth now combines call-session existence check and worker lease claim into one atomic DB update | `CallSessionService` + route regressions passed |
| Parent lookup DB | Conversation and messages are projected to the small fields needed for latest leaf resolution, including Listen-Only transcript type and mode; duplicate generic conversation validation is skipped only when the voice route already proved the exact user-owned conversation | Mongo microbenchmark: projected message payload 944 bytes vs old full shape 6572 bytes; Listen-Only projection regression passed |
| Anthropic voice thinking | Same-model Voice Call LLM params now apply; Anthropic `thinking:false` is consumed/deleted before graph config | Voice override regression proves final voice params are `{ model: "claude-opus-4-7" }` |
| xAI fallback | xAI keeps `reasoning_effort:"none"` through fallback sanitization | Fallback regression passed |
| Phase A notice | Added `all_within_budget`, `any_activated`, and `any_activated_on_voice`; early notice is generic, Phase B waits final detection, and unowned tool-hold scopes force fallback to `all_within_budget` | Phase A notice and tool-hold guard regressions passed |
| Timing evidence | Added high-resolution route/controller/client/Phase A/invoke logs with fractional milliseconds | Syntax checks passed on changed logging files |

## DB Microbenchmark After Fix

Local development MongoDB, seven samples per operation, public-safe synthetic call-session row
cleaned up after the run:

| Operation | Median | Max |
| --- | ---: | ---: |
| Combined session claim `findOneAndUpdate` | 0.309ms | 0.630ms |
| User fetch projection | 0.255ms | 0.307ms |
| Conversation validate projection | 0.210ms | 1.095ms |
| Parent messages projected | 0.240ms | 0.325ms |
| Voice ingress create+find with no sleep | 0.450ms | 0.785ms |

This means the measured 0.35-0.40s route-ready delay was not normal DB/auth cost. It lined up with
the old deliberate 350ms coalescing wait. DB/auth still needed cleanup because the prior session
auth did an avoidable extra round trip and parent resolution pulled more message data than needed.

## Aligned Options

1. Fix the Anthropic voice `thinking:false` leak first.
   - Evidence: DB voice params carry `thinking:false`, but the invoke path logs
     `thinking_enabled=true`.
   - Add a regression proving the constructed Anthropic client options do not include thinking for a
     voice route configured with `thinking:false`.

2. Add deeper Phase A classifier telemetry.
   - Needed fields: per-cortex prompt size, provider fetch start, headers/body/read/parse time,
     timeout reason, wall time, and provider usage timing where available.

3. Use the new Phase A notice mode only where the product accepts the tradeoff.
   - Default/current behavior is now `any_activated_on_voice`: voice releases Phase A on the first
     true activation, while web, Telegram, scheduler, and other text surfaces still use
     `all_within_budget`.
   - The shipped voice default keeps `VIVENTIUM_VOICE_BACKGROUND_AGENT_DETECTION_ASYNC=false` so this
     notice mode is the actual main-response path; fully async detection remains an explicit opt-in.
   - Fully async opt-in detection uses `all_within_budget` in the background so Phase B receives the
     complete activated set after the main voice LLM has already started.
   - `any_activated` and `any_activated_on_voice` release Phase A on the first true activation and
     continue full detection for Phase B.
   - Early notice must be generic: the main model knows background processing is brewing and the
     final activated scope is still pending; it does not receive a fake complete activation list.
   - If an unowned tool-hold/direct-action cortex is configured on the current request, early notice is
     disabled for that turn so the deterministic hold path can still protect the main answer.

4. Prewarm what is independent of final STT.
   - Useful: user/agent/model config, primary tool definitions, MCP definition caches, OAuth-pending
     state, and provider prompt-cache warmup.
   - Less useful: pre-creating a full per-turn generation job, because final conversation/user-message
     state is not known until the final transcript arrives.

5. Preserve parity when optimizing prompts.
   - Prompt cleanup and provider prompt caching are aligned.
   - Voice-only prompt truncation is not aligned unless separately specified and tested.

## Second Opinion

A review-only Claude pass agreed with the overall direction and flagged two blocking correctness
issues before completion:

- The parent-message projection originally included `metadata.viventium.type` but not
  `metadata.viventium.mode`, which would have broken Listen-Only transcript filtering. Fixed by
  projecting both fields and adding a regression assertion.
- The first-activation early notice path could have released the main response before a late
  unowned tool-hold activation set the deterministic hold flag. Fixed by guarding early notice
  whenever the current request has an unowned configured tool-hold scope.

## Gaps

- A full spoken browser call that continues into the main LLM response was not rerun after the code
  changes. The fresh browser/LiveKit pass used the repo's Listen-Only fake-microphone harness, which
  proves playground connection, voice gateway worker assignment, STT, LibreChat listen-only ingress,
  DB persistence, and cleanup, but intentionally stops before main-agent Phase A/LLM generation.
- The local launcher reported `EADDRINUSE` for the API port during restart because another API
  process already owned the port; the API still answered health/config probes and the launcher
  continued with the existing API process.
- Provider timings vary run to run; repeat benchmarks should capture request bytes, tool-schema bytes,
  cache hit status, and final token counts before estimating exact savings.
