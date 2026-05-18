<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
# 2026-05-15 LiveKit Voice Parity and Latency Follow-Up QA

## Scope

This pass followed up the modern-playground voice incident after the low-risk hot-path and
persistence fixes were applied. It specifically checked:

- checked-out worktrees were not ignored or left behind
- documented voice fast-profile env reached the generated runtime
- new LiveKit typed-transcript voice turns persist into the linked LibreChat conversation
- new voice turns no longer persist visible reasoning/thought blocks
- per-turn latency logging is present enough to break down the remaining delay
- xAI `grok-4.3` no-reasoning behavior was compared against raw provider timing
- upstream and official docs were checked before proposing the next fix

The pass used synthetic non-personal prompts only. Public QA notes intentionally omit raw
conversation ids, message ids, call-session ids, request ids, private account values, and local
absolute user paths.

## Worktree Preservation Check

Checked-out worktrees were inventoried before concluding:

- parent release/Claude worktree heads are already ancestors of the active parent branch
- nested LibreChat release worktree head is already an ancestor of the active LibreChat branch
- the active parent and active nested LibreChat trees contain the current voice fixes as dirty work
- no checked-out worktree commit needed to be merged because none was ahead of the active line

Historical unmerged non-worktree branches still exist, including old archive/Telegram/MLX lines.
They were not merged blindly into this voice patch because they are broad historical branches rather
than current checked-out worktrees carrying missing voice fixes.

## Runtime Env

Generated runtime env was inspected after restart and contains:

- `VIVENTIUM_VOICE_BACKGROUND_AGENT_DETECTION_ASYNC=true`
- `VIVENTIUM_VOICE_PHASE_A_AWAIT_MS=500`
- `VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=false`
- `VIVENTIUM_VOICE_LOG_LATENCY=1`

The `VIVENTIUM_VOICE_LOG_LATENCY=1` value is now compiler-owned, so the deep timing logs do not
depend on a manual App Support edit.

## Browser QA

Real user-level browser flow:

1. Opened an authenticated LibreChat agent conversation on `http://localhost:3190`.
2. Clicked `Start voice call`, which opened the modern playground on `http://localhost:3300`.
3. Verified the call UI loaded with AssemblyAI listening and xAI Eve speaking.
4. Clicked `Start chat`.
5. Opened the transcript panel.
6. Muted microphone input to avoid ambient STT during the typed-transcript test.
7. Sent the synthetic typed prompt:
   - `For QA latency logging after restart, reply exactly: Kappa. Lambda.`
8. Observed the modern playground assistant transcript:
   - `Kappa. Lambda.`
9. Ended the call.
10. Reloaded the linked LibreChat conversation.

Observed LibreChat result:

- the synthetic user turn persisted
- the assistant turn persisted as `Kappa. Lambda.`
- the reloaded conversation did not show a visible `Thoughts` block for that new voice turn

This is the first post-fix visible browser confirmation that the LiveKit modern-playground answer
and the linked LibreChat conversation agree for a new simple voice turn.

## DB QA

Mongo inspection for the two latest synthetic voice turns showed:

- assistant `text` is populated, not blank
- assistant `content` contains one text part matching the visible assistant response
- assistant `content` contains no `type: "think"` part
- a previous synthetic turn also persisted correctly as text-only content

Latest synthetic assistant rows:

| Prompt Purpose | Assistant Text | Content Shape | Reasoning Persisted |
| --- | --- | --- | --- |
| latency logging after restart | `Kappa. Lambda.` | one text part | no |
| text mirror patch | `Sigma. Tau.` | one text part | no |

There is a residual timestamp nuance: the assistant placeholder row can have a slightly earlier
`createdAt` than the finalized user row because the route creates the assistant placeholder before
the user row is fully finalized. The message parent chain and visible UI order were correct in the
tested conversation.

## Timing Evidence

For the fresh simple `Kappa. Lambda.` turn, the voice gateway saw:

| Stage | Time |
| --- | ---: |
| POST to LibreChat voice route ready | 565 ms |
| stream subscribe attempt | 565 ms |
| first text/token event to gateway | 5,209 ms |
| stream complete | 5,421 ms |
| follow-up scheduling | 5,421 ms |

Backend deep timing for the same simple turn:

| Ordered Step | Time From Route Entry | Step Cost / Notes |
| --- | ---: | --- |
| route body normalized and stream setup | ~0-565 ms | gateway had a stream id by 565 ms |
| Phase A detection completed | 1,875 ms | 502 ms in the Phase A detection window; `0` activated |
| run created | 1,971 ms | 92 ms after Phase A |
| process stream start | 1,971 ms | model run begins |
| first chain start | 2,121 ms | 150 ms after stream start |
| provider fetch start | ~2,121 ms | outbound xAI request starts |
| provider headers | +770 ms | HTTP stream opened, not content yet |
| first assistant message delta | 5,187 ms | first application-level content |
| chat completion done | 5,302 ms | full simple answer complete |
| persisted/send done | 5,387 ms | message saved and stream finalized |
| Phase B wait skipped | 5,400 ms | no cortex follow-up expected |

The provider request telemetry for that simple turn showed:

- provider/model: `xai` / `grok-4.3`
- `reasoning_effort=none`
- `reasoning.effort=unset`
- `include_reasoning=unset`
- streaming enabled
- `29` tools available to the full agent route
- no activated background cortex

This means the latest simple-turn delay was not caused by the voice model "thinking" being enabled.

## Raw Provider Benchmark

Using the same configured local xAI credential without printing it:

| Raw xAI Request | First Content | Done |
| --- | ---: | ---: |
| tiny prompt, `grok-4.3`, `reasoning_effort: "none"` | 977 ms | 1,019 ms |
| synthetic 46,874-char system prompt, `grok-4.3`, `reasoning_effort: "none"` | 1,000 ms | 1,002 ms |

Comparison:

- raw xAI no-reasoning first content: about 1.0 s
- Viventium modern-playground simple turn first gateway text: about 5.2 s
- remaining gap after the fixes: about 4.2 s over the raw provider baseline

## Current Root Cause

The current bottleneck is no longer a single broken knob. It is the accumulated voice hot path:

1. Voice gateway posts to LibreChat and subscribes to the generated stream.
2. LibreChat initializes the agent path and full tool surface.
3. Phase A activation detection still runs on the hot path for about 500 ms on the tested simple
   turn, even though no cortex activates.
4. The full LibreChat/LangGraph provider path starts the xAI streaming request.
5. The provider returns headers in under 1 s, then the app receives the first message delta around
   5.2 s from route entry.
6. The answer is persisted and Phase B is skipped.

The "Phase A instant" issue is therefore not that Phase A became `{NTA}` or that it silently spoke
nothing. The product currently has no separate cheap audible acknowledgement before the main model.
What users hear is still the first content from the main LLM path, so it waits for route setup,
prompt/runtime context assembly, Phase A detection, model run setup, provider streaming, and TTS.

## Direct-Action Tool-Hold Meaning

In this context, "direct-action tool-hold candidate" means a configured background cortex is tied to
external action or live-data tools where speaking too soon can be unsafe.

Example:

- "Please check my calendar and schedule a follow-up" can touch scheduling or workspace tools. If a
  background/direct-action path owns that step, the main agent should not confidently speak as if it
  has already done the work.
- "Reply exactly: Kappa. Lambda." is not a direct-action turn. The latest logs show no background
  cortex activated, but the current policy still spent the Phase A budget before first audio.

The safer next policy is not to blindly allow all direct-action tool holds asynchronously. A broad
"start the main answer while Phase A runs" design would weaken the documented background-agent
contract because activated cortices are supposed to be visible to the main agent's Phase A context
before it authors the answer. The lower-risk candidate is narrower: if activation detection proves
there are zero activations, release the main response without paying any remaining detection budget;
if a cortex activates, keep the awareness/hold path intact.

## Prompt and Context Size

The simple voice turn still carried a large shared agent frame:

- main instructions: about 46.9k chars, about 11.7k estimated tokens
- background context: about 2.3k chars, about 573 estimated tokens
- tools exposed on the full route: 29

This is not a recommendation to make a voice-only reduced context path. A voice-only budget would
violate the parity requirement. The aligned fix is shared prompt architecture cleanup and caching
that benefits text and voice together while preserving the same agent behavior contract.

## Tool Call Delay Learning

The earlier current-data/weather-style turn showed why long tool calls are a separate UX problem:

- first model hop identified a `web_search` tool call instead of producing audible text
- local web-search tool work completed much later
- a second model hop synthesized the answer
- first visible answer arrived around 26 s in that run

xAI official docs now state Web Search is available on the Responses API and that Live Search on
Chat Completions is deprecated. A direct xAI Responses web-search probe was faster for the first
server-side tool event than the local tool path, but changing the voice route from Chat Completions
tooling to Responses-native search is a product/runtime design change. It should be reviewed as a
separate current-data voice design, not folded into this low-risk patch.

## Official Docs Checked

- xAI `grok-4.3` docs: `grok-4.3` supports configurable reasoning including `none`.
- xAI reasoning docs: for `grok-4.3`, `reasoning_effort` / `reasoning.effort` can disable reasoning
  and the default is not `none`.
- xAI May 15, 2026 migration docs: older fast non-reasoning slugs redirect to `grok-4.3` with
  `none` effort after retirement; explicit `grok-4.3` plus no-reasoning remains the controlled path.
- xAI Web Search docs: web search is Responses API-only; Chat Completions live search is deprecated.
- LiveKit text/transcription docs: synchronized transcriptions are audio-paced by default, and
  disabling synchronization sends text to the client as it becomes available.
- LiveKit voice reference docs: endpointing delay can add after STT end-of-speech in STT mode.

## Tests

Passed:

- `uv run --with pytest --with PyYAML python -m pytest tests/release/test_config_compiler.py -q`
  - `92 passed`
- `cd viventium_v0_4/LibreChat/api && npm run test:ci -- api/models/Message.spec.js server/controllers/agents/__tests__/requestPersistence.spec.js server/services/viventium/__tests__/voiceDeltaAggregation.spec.js server/controllers/agents/client.test.js server/services/viventium/__tests__/BackgroundCortexFollowUpService.spec.js server/services/viventium/__tests__/voicePhaseAPolicy.spec.js --runInBand`
  - `6` suites passed, `204` tests passed
- `cd viventium_v0_4/voice-gateway && .venv/bin/python -m unittest tests.test_librechat_llm -v`
  - `30` tests passed
- `cd viventium_v0_4/voice-gateway && .venv/bin/python -m py_compile librechat_llm.py sse.py xai_grok_voice_tts.py worker.py`
  - passed
- targeted syntax checks for edited LibreChat voice/controller/model files
  - passed
- follow-up `Message.saveMessage` regression after Claude review:
  - `cd viventium_v0_4/LibreChat/api && npm run test:ci -- api/models/Message.spec.js --runInBand`
  - `40` tests passed, including the non-voice assistant content mirror guard

## Acceptance Status

Now covered:

- fresh LiveKit modern-playground typed-transcript turn returns a real assistant answer
- the same answer persists into LibreChat and survives reload
- new voice turns do not show/persist provider reasoning blocks
- the compiler emits the documented fast voice env plus latency logging
- the voice model is `grok-4.3` with no reasoning on the actual outbound provider path
- checked-out worktrees were inventoried and not skipped

Still not acceptable for "natural-feeling" voice latency:

- simple turn first text is still about 5.2 s after route entry versus about 1.0 s raw xAI
- Phase A is still on the first-audio path
- the provider/framework segment after headers still needs raw SSE versus app-delta instrumentation
- no actual audio waveform capture was recorded in this pass; transcript text and TTS text
  sanitization were verified by browser/DB/tests, but not by audio capture

## Claude Review

Claude review-only pass completed after this report draft. It agreed with the broad RCA and with raw
provider streaming instrumentation as the lowest-risk next move, but challenged the previous broad
speculative-Phase-A proposal.

Evidence-backed corrections from the review:

- the measured `5.2s` is gateway route entry to first app delta, not end-of-speech to first audible
  sound; STT endpointing, gateway delta buffers, and TTS first audio still need timing
- broad speculative Phase A would skip the current activation-awareness injection that
  `02_Background_Agents.md` requires for activated background agents
- primary tool/MCP init around `2.1s` is still on the first-audio path and needs its own breakdown
- memory loading may still be synchronous on the hot path and should be measured explicitly
- `Message.saveMessage` text mirroring is not voice-only; it should be documented/tested as a
  parity-wide persistence repair, not just a voice patch

The proposed fix order below incorporates those corrections.

## Proposed Next Fix For Review

1. Add raw provider and gateway audio timing instrumentation:
   - outbound request start
   - headers
   - first raw SSE chunk
   - first raw content delta
   - first LangChain/App message delta
   - first gateway post-buffer chunk sent to TTS
   - TTS first audio
   This identifies whether the remaining gap is xAI generation, framework buffering, local event
   handling, gateway buffering, or TTS startup.
2. Split and reduce primary hot-path init:
   - MCP pending probe time
   - canonical tool-definition load time
   - memory load/useMemory time
   - prompt-frame assembly time
   - short per-call/per-user reuse for stable tool definitions and known OAuth-pending states
3. Replace broad speculative Phase A with a narrow fast no-activation bypass:
   - do not weaken activation-awareness injection when a cortex actually activates
   - when activation detection returns zero activations, release the main response immediately
     instead of spending the remaining detection budget
   - keep current direct-action safety for real tool/action turns
4. Keep prompt cleanup parity-safe:
   - no voice-only truncation
   - reduce duplicated shared prompt/runtime material for all surfaces
   - cache stable system/tool context where provider/runtime support makes that safe
5. Treat current-data/tool-call voice UX as a separate product design:
   - decide whether voice should speak an inline status line while tools run
   - evaluate xAI Responses-native Web Search separately from current Chat Completions tooling
