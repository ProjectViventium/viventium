# Modern Playground Voice Cases

## Natural User Use Case Checklist

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `MPV-UC-001` | Start a call from an authenticated LibreChat conversation and send a simple typed or spoken prompt. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-001` | LibreChat browser plus Modern Playground | Voice gateway logs, LiveKit state, persisted chat message, generated voice config | Call connects, agent joins, transcript shows a real assistant answer. | See latest dated reports in `reports/` |
| `MPV-UC-002` | Interrupt or send a second turn while prior work or follow-up timing is still active. | `docs/requirements_and_learnings/06_Voice_Calls.md` / `MPV-003` | Modern Playground call | Transcript, stream ids, Mongo message chain, voice gateway timing logs | Turns stay distinct, no stale follow-up is spoken as current conversation state. | 2026-05-15 PARTIAL |
| `MPV-UC-003` | Ask the voice agent to look something up when Web Search appears enabled. | `docs/requirements_and_learnings/06_Voice_Calls.md`, `docs/requirements_and_learnings/10_Open_Source_Web_Search.md` / `MPV-006` | Modern Playground and linked LibreChat browser conversation | Visible transcript/chat, persisted `web_search` tool-call parts, local search backend health, hosted search backend status, request logs, Docker/container state for local providers, browser/local-delegation fallback when available | Voice/search either returns grounded evidence or says the exact degraded provider class without inventing facts; named-entity/current-fact failures use fallback before stopping. | FAIL (escaped 2026-05-18; fix run pending) |
| `MPV-UC-004` | Reload linked chat after a voice turn that used model/tooling. | `docs/requirements_and_learnings/34_Voice_Chat_LLM_Override.md` / `MPV-005` | LibreChat browser conversation | DB message content parts, logs, transcript, generated no-reasoning config | Visible chat persists audible answer only; no reasoning blocks or raw private transcript leak. | 2026-05-15 PASS for simple turn |

## MPV-001 Authenticated Call Launch

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`
- User Outcome: An authenticated chat can open a valid modern-playground call session and the voice
  agent joins instead of leaving unexpectedly.
- Surfaces: LibreChat Web UI, Modern Playground, LiveKit, Voice Gateway
- Preconditions: canonical local stack running; authenticated Viventium user; synthetic
  non-personal chat available.
- Steps:
  1. Open an authenticated LibreChat agent conversation.
  2. Click the phone button.
  3. Verify the modern playground opens with a call-session deep link.
  4. Click `Start chat`.
  5. Open transcript and send a synthetic typed prompt.
- Expected Result: LiveKit connects, the voice worker receives the job, and the assistant returns a
  real answer. Forbidden result: `Session ended / Agent left the room unexpectedly`.
- Evidence: `qa/modern-playground-voice/README.md`
- Last Run: see latest dated execution evidence in `README.md`.

## MPV-002 Local Whisper Exact-Model Self-Heal

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`
- User Outcome: Local Whisper voice calls preserve the user-selected Whisper.cpp model and repair
  missing or corrupt local model artifacts instead of silently changing models.
- Surfaces: Modern Playground, Voice Gateway capability API, Voice Gateway startup, Telegram local
  transcription helpers
- Preconditions: canonical local stack running with `VIVENTIUM_STT_PROVIDER=whisper_local` or
  equivalent local `pywhispercpp` route.
- Steps:
  1. Query the voice gateway capabilities endpoint.
  2. Open `http://localhost:3300` in a real browser.
  3. Inspect the Listening selector and its dropdown.
  4. Seed a stale generated runtime env with a different local STT model, then start through the
     supported launcher and verify canonical `config.yaml` wins.
  5. Corrupt or remove the cached selected model in a synthetic/temp cache and run the model
     self-heal check across voice gateway and Telegram local transcription helpers.
  6. Check the voice gateway startup log for the selected model preflight and prewarm.
- Expected Result: Current STT preserves the selected local model, including `large-v3-turbo` when
  selected. Missing or corrupt cache files are re-downloaded for that exact model and load-validated
  before worker use. Stale generated runtime env is regenerated from canonical config before launch.
  Forbidden result: runtime silently changes the selected model to `base.en`, `small`, OpenAI STT,
  or any other route to hide the local Whisper.cpp problem.
- Evidence: `qa/modern-playground-voice/README.md#2026-05-12-local-whisper-model-route-regression`
- Last Run: 2026-05-12, updated after exact-model self-heal fix.

## MPV-003 Sequential Voice Turns During Phase B

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`,
  `docs/requirements_and_learnings/02_Background_Agents.md`
- User Outcome: A second spoken turn can be sent while the prior turn's Phase B follow-up window is
  still open, without losing the second turn or speaking a stale follow-up as if the conversation had
  not moved on.
- Surfaces: Modern Playground, Voice Gateway, LibreChat voice route, Agents stream manager, Mongo
  conversation persistence.
- Preconditions: canonical local stack running; voice call route with at least one background cortex
  capable of producing a delayed Phase B follow-up; synthetic non-personal prompt text.
- Steps:
  1. Start an authenticated modern-playground voice call.
  2. Send a first synthetic prompt that activates a background cortex while still receiving an
     immediate Phase A answer.
  3. Before the background follow-up window closes, send a second synthetic prompt in the same call.
  4. Inspect the visible transcript, LibreChat conversation, backend logs, and Mongo messages.
- Expected Result: Both user turns and both assistant turn outcomes persist under the correct
  parent chain. The second stream does not return `Stream not found`. Any Phase B continuation from
  the first turn is adjudicated with the newer visible exchange and may resolve to silence. Distinct
  generated turns use distinct one-turn stream ids unless the requests were intentionally coalesced
  inside the same ingress window.
- Forbidden Result: the second user turn appears only in the playground transcript but not in Mongo;
  the voice gateway speaks a generic service error; a stale first-turn follow-up is generated with
  moved-on state missing; a later turn subscribes to or completes an older turn's stream.
- Evidence: `qa/modern-playground-voice/reports/2026-05-15-livekit-parity-latency-followup-qa.md`
- Last Run: 2026-05-15 partial browser/DB regression. Fresh multi-turn Phase B overlap timing is
  still needed for the full MPV-003 stress case.

## MPV-004 Voice Latency Timing Profile

- Requirement: `docs/requirements_and_learnings/14_Voice_Latency_and_Memory_RCA.md`,
  `docs/requirements_and_learnings/06_Voice_Calls.md`
- User Outcome: A simple directly addressed voice turn should start speaking quickly enough to feel
  natural, and logs must show where any remaining delay occurred.
- Surfaces: Modern Playground, LiveKit, Voice Gateway, LibreChat voice route, Voice Call LLM provider
  route, TTS.
- Preconditions: canonical local stack running; voice latency logging enabled; authenticated
  modern-playground call session; main agent Voice Call LLM route selected.
- Steps:
  1. Start an authenticated modern-playground voice call.
  2. Speak a simple non-tool prompt such as `Hey, can you hear me clearly?`.
  3. Capture STT final transcript timing, `/api/viventium/voice/chat` ready time, SSE subscribe time,
     Phase A async/forced-off decision, provider first-text timing, TTS first-audio timing, and Phase
     B follow-up timing.
  4. Repeat with a current-data prompt such as a weather/web question and record whether the route
     used local web-search tooling or a provider-native search path.
  5. Compare transcript, Mongo persistence, and logs to confirm the visible answer matches the
     recorded timing path.
- Expected Result: The simple turn avoids synchronous background detection when direct-action holds
  are either absent or owned, uses the voice provider's no-reasoning parameter shape, and produces a
  complete per-stage timing record. For xAI Chat Completions, provider-fetch telemetry shows
  `reasoning_effort="none"` on the actual outbound request, not only on the intermediate voice
  config. Current-data turns identify tool latency separately from model first-token latency.
  Healthy primary turns do not eagerly initialize the fallback agent before first audio; fallback
  initialization appears only when primary fails. OAuth-pending MCP servers either report an
  isolated `oauth_pending` probe or a later `oauth_pending_memo_hit`, not repeated opaque multi-second
  retries in the same hot path.
- Forbidden Result: generic "service unavailable" speech without a provider/tool error class;
  missing per-turn stream id; voice-only prompt/context truncation that breaks parity; hidden model
  remap; raw private transcript or call-session identifiers copied into public QA artifacts.
- Evidence: `qa/modern-playground-voice/reports/2026-05-15-livekit-parity-latency-followup-qa.md`
- Last Run: 2026-05-15 fresh authenticated LiveKit typed-transcript run completed for a simple
  non-tool turn. Current-data/tool-call timing and actual audio first-sound capture remain open.

## MPV-005 Voice Transcript Must Not Persist Reasoning Blocks

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`,
  `docs/requirements_and_learnings/34_Voice_Chat_LLM_Override.md`
- User Outcome: A live voice call transcript shows only the audible assistant response, not provider
  reasoning/thinking internals.
- Surfaces: Modern Playground, LibreChat conversation view, Agents stream manager, Mongo
  conversation persistence.
- Preconditions: canonical local stack running; voice call route with a Voice Call LLM configured
  for no reasoning, such as xAI Chat Completions `reasoning_effort: "none"`.
- Steps:
  1. Start an authenticated modern-playground voice call.
  2. Send a simple non-tool prompt.
  3. Inspect the modern-playground transcript during the turn.
  4. Open the linked LibreChat conversation after the turn completes.
  5. Inspect Mongo message content for the assistant message.
  6. Inspect voice latency logs for provider reasoning-delta suppression and sanitized provider
     request knobs.
- Expected Result: The spoken/transcript answer is present, but no visible `Thoughts` block appears
  in the conversation, no assistant message content part with `type: "think"` is persisted for the
  voice turn, provider-fetch telemetry confirms the no-reasoning request shape when the provider
  supports it, and logs show `voice_reasoning_delta_suppressed` if a provider emits reasoning
  anyway.
- Forbidden Result: Visible LibreChat `Thoughts` cards from a voice call; persisted voice assistant
  content containing `type: "think"`; raw prompt/message text copied into public QA evidence.
- Evidence: `qa/modern-playground-voice/reports/2026-05-15-livekit-parity-latency-followup-qa.md`
- Last Run: 2026-05-15 fresh authenticated LiveKit typed-transcript run, LibreChat reload, and Mongo
  inspection passed for a new simple voice turn.

## MPV-006 Voice Web-Search Request Must Not Escape The Checklist

- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`,
  `docs/requirements_and_learnings/10_Open_Source_Web_Search.md`, and
  `qa/feature-user-use-case-checklist.md`.
- User Outcome: When the user naturally asks the voice agent to look up current information, the
  transcript/chat result proves a real search path or gives honest degraded-provider wording.
- Surfaces: Modern Playground, linked LibreChat conversation, Web Search tool, SearXNG/Firecrawl or
  hosted provider, Mongo message persistence, API logs.
- Preconditions: local stack running; selected agent has Web Search capability enabled; synthetic
  public-safe current-data prompt; provider health state intentionally recorded before the run.
- Steps:
  1. Start an authenticated modern-playground call from LibreChat or use the linked conversation
     produced by that call.
  2. Ask a synthetic current-data prompt such as `Please look up the current public date and venue for
     Example Summit and answer only from search results.`
  3. Observe the modern-playground transcript and the linked LibreChat visible answer.
  4. Inspect persisted assistant content for `web_search` tool-call parts and web-search artifacts.
  5. Probe local/hosted search and scrape provider health. For local SearXNG/Firecrawl, explicitly
     record Docker daemon and container state before interpreting the failure.
  6. Inspect API/tool logs for returned sources or failure class.
  7. If the prompt is a named-entity/contact/date/current-fact lookup and search fails operationally,
     verify the assistant uses available browser/local-delegation fallback or states why fallback is
     unavailable.
  8. Compare the final spoken/text wording with actual provider health and persisted state.
- Expected Result: healthy provider state yields a grounded answer with fetched evidence. Degraded
  provider state yields explicit degraded-service wording and a retry/setup path, without pretending
  the event was not searchable or asking the user for data only because QA failed to verify search.
- Forbidden Result: the UI/voice answer says only that search is not pulling while QA has not proven
  provider health, Docker/local-service state where relevant, tool-call persistence, and logs; the
  Web Search checkbox is treated as proof of usable search; a non-browser/unit-only check is
  accepted for this browser/voice feature; an available browser/local-delegation fallback is skipped
  after an operational search failure on a current-fact lookup.
- Evidence: public-safe report with visible observation, DB/tool-call counts, search provider health,
  API log failure class or returned-source count, generated config state, and privacy review.
- Last Run: FAIL (escaped 2026-05-18 from live local browser evidence; regression case added, product
  fix and full rerun pending).

## Release Test Traceability

- `tests/release/test_voice_playground_dispatch_contract.py`
