# GlassHive Voice Call LLM — 2026-08-01

## Current result

- Result: `PARTIAL` while post-fix cancellation/reconnect and final merged-component gates run.
- Architecture: GlassHive is an optional author in the existing LiveKit STT -> LLM -> TTS pipeline;
  it does not claim native speech-to-speech support.
- Default: the existing lighter Voice Call LLM remains unchanged. GlassHive is an explicit Agent
  Builder choice with exact model, readiness, workspace/access, and effort controls.

## Evidence matrix

| Gate | Result | Evidence |
| --- | --- | --- |
| Capability contract | `PASS` | `voice_pipeline_llm: true`, `native_realtime_voice: false`, legacy alias retained. |
| Agent create/update validation | `PASS` | 13 focused package tests; exact model/effort, LIFE/full defaults, Responses-field pruning, and fail-closed fallback. |
| Agent Builder component | `PASS` | 17 focused client tests; GlassHive and friendly Codex label render, low effort persists, readiness and LIFE/full defaults appear. |
| Runtime voice override | `PASS` | 16 focused API tests; direct main -> explicit GlassHive and GlassHive primary routes resolve exactly. |
| GlassHive endpoint | `PASS` | 69 conversation-provider tests, including exact published voice capabilities. |
| Voice gateway | `PASS` | 109 streaming, turn, follow-up, and cancellation tests. No provider-specific gateway adapter was added. |
| Config compiler | `PASS` | 173 compiler tests and generated App Support config inspection. |
| Production client compilation | `PASS` | Vite transformed 8,354 modules and emitted the UI. The subsequent compliance collector correctly rejected a pnpm-realpath dependency tree against its npm package-lock allowlist; a clean npm install remains the release build gate. |
| Public safety | `PASS` | Exact staged diffs scanned with gitleaks plus identity/home-path patterns; zero findings. |
| Live Agent Builder save/reload | `PASS` | Synthetic agent saved GlassHive Codex with low voice effort; refresh and Mongo round trip retained exact provider/model/options. |
| Audible GlassHive call | `PASS` | Real Modern Playground turn produced the requested audible sentence once; LibreChat, voice-gateway, Mongo, and GlassHive request/session evidence agreed. |
| Explicit End Call | `PARTIAL` | The first live run stopped media but exposed a worker that continued. The fix now scopes by user/call metadata, propagates `user_cancelled` across Redis, suppresses duplicate transport abort, and passes 98 focused tests; post-fix live rerun remains. |
| Refresh in flight | `NOT RUN` | Passive disconnect does not request native cancellation, but reattachment/terminal delivery is not yet claimed. |
| Claude Opus 5 review | `BLOCKED` | Claude Desktop reports no remaining Opus usage until the displayed reset; no weaker model substituted. |
| Nested/public component identity | `PARTIAL` | LibreChat PR 90 and GlassHive PR 48 are open; parent manifests truthfully declare review-head pending merge. |

## Research-grounded decision

OpenAI distinguishes native speech-to-speech from chained voice pipelines, while LiveKit recommends
the chained STT-LLM-TTS architecture for most production agents when portability, observability,
and mature tool behavior matter. ChatGPT Voice uses a fast GPT-Live conversation lane and can launch
separate Codex tasks for longer work. Viventium therefore keeps its low-latency default and offers
GlassHive when workspace/tool intelligence is worth longer first-audio latency. GlassHive's current
profile exposes terminal authored text rather than fabricated token deltas; activity and reasoning
must never be spoken as the answer.

Primary sources are recorded in
`docs/requirements_and_learnings/34_Voice_Chat_LLM_Override.md`.

## Remaining user-grade gates

1. Activate the cancellation fix and rerun a long GlassHive turn followed by explicit End Call;
   verify one native cancel, no late speech/message, and no duplicate across logs and state.
2. Reload during a separate in-flight turn and prove whether terminal delivery reattaches; do not
   infer resumability from the absence of native cancellation.
3. Exercise stopped provider and invalid model/effort paths and verify visible, accurate failure.
4. Merge nested refs only after hosted checks, update parent pins to public-main commits, run the
   clean npm build and supported install/upgrade identity gates, then change this report to final.

## Public-safety boundary

No account identifier, local username, home path, private conversation, token, screenshot, runtime
log, or database row is published here. Private user-path evidence remains outside the public repo.
