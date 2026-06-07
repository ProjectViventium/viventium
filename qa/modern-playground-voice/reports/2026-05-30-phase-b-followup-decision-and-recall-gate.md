<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-30 Phase B Follow-Up Decision And Recall Gate QA

## Scope

This pass covered the approved fix for missing Phase B follow-up observability across LibreChat web,
voice, and Telegram pollers, plus a related recall-off leakage found during QA.

Public-safe synthetic prompts only are recorded here. Private user call/session IDs, transcripts,
account identifiers, and local absolute paths are omitted.

## Changes Verified

- Phase B follow-up generation now emits and persists a structured `CortexFollowupDecision`.
- Phase B early exits now emit and persist the same decision shape when the result is terminal-silent
  before follow-up synthesis is called, including newer-input suppression, empty output, and
  error-only non-deferred output.
- Web, voice, and Telegram poll paths can distinguish terminal silent outcomes from "still waiting".
- Voice and Telegram pollers stop early when the shared decision is terminal-silent.
- Voice and Telegram pollers do not stop merely because a non-terminal persisted decision carries a
  `suppressionReason`; the structured `result` must be terminal.
- Completed cortex parts can be recovered into merged follow-up context when the normal merged result
  is unavailable.
- Meeting transcript RAG attachment now requires resolved all-conversation recall scope; a configured
  transcript folder alone, or agent-only recall, is not permission.
- Non-blocking RAG verification no longer serves cached vector ids while a recall rebuild marker is
  present, preventing stale recall after restore/rebuild handoffs.
- Telegram canonical answer recovery now wins before terminal-silent follow-up decisions, so a
  placeholder cannot strand the real final answer.

## Existing Call Classification

I inspected the user-referenced live call/conversation in logs and Mongo, but did not copy its private
transcript here.

Finding: the missing separate follow-up was not always a Phase B execution failure. The old logs show
multiple Phase B adjudications resolving to `{NTA}` with `suppressionReason=no_response_tag`, so silence
was often the intended outcome. The bug was that this terminal decision existed only in transient logs:
voice/Telegram/web QA could not tell "the correct answer is no follow-up" from "Phase B never ran."

## Browser QA

### Recall-Off Regression

Synthetic prompt:

```text
Synthetic recall-off QA. Ignore prior context and answer exactly: NO_CONTEXT.
```

Result:

- Visible LibreChat response: `NO_CONTEXT`.
- User personalization in Mongo: `memories=false`, `conversation_recall=false`.
- API timing log for the same turn: `recall_scope=none transcript=0`.
- API log also recorded that meeting transcript recall was configured but user recall was disabled.
- Unit coverage now also verifies agent-only recall does not attach all-user meeting transcript
  resources.

Verdict: PASS. Conversation recall off now prevents transcript recall attachment.

### Phase B Decision Persistence

Synthetic prompt:

```text
Synthetic cortex QA. Give the fastest useful answer first, then let background agents add follow-up only if they have a distinct useful critique. Scenario: fictional vendor Alpha Labs is fast but has shaky QA; fictional vendor Beta Forge is slower but reliable. Which is the stronger choice? Keep the first answer to two sentences.
```

Result:

- Browser showed named completed cortex rows for `Background Analysis` and `Strategic Planning`.
- Mongo assistant message stored `metadata.viventium.cortexFollowUpDecision`.
- Decision summary: `result=persisted`, `surface=web`, `llmResult=generated`,
  `selectedStrategy=llm_generated`, `hasInsights=true`, `finalLength=767`.
- Timing logs for the same turn showed `recall_scope=none transcript=0` on the main and cortex agents.

Verdict: PASS for persisted generated decision metadata and recall isolation.

Residual: on this run the primary model emitted no visible text before Phase B completed, so the forced
Phase B synthesis was promoted onto the canonical parent. That avoids a blank assistant message, but it
does not satisfy the ideal "fast answer first" behavior and should remain tracked separately.

### Post-Restart Browser Harness

After the final early-exit decision patch and runtime restart, I ran the latest-user browser QA
harness with a synthetic local user.

First finding: the setup card timeout was a real source-of-truth drift. The standalone Red Team
activation prompt already said explicit red-team/pressure-test requests should activate, but the live
local agent bundle still had the older shorter Red Team activation prompt. I patched the source bundle
and applied a narrow activation-config-only live sync for the Red Team cortex prompt.

Second finding: after Red Team setup cards appeared, the second exact-answer turn exposed stale-history
activation. Background cortices activated from the setup prompt even though the latest user turn only
asked for an exact marker. I tightened the source-owned activation-subject prompt and restored its
`promptRef` ownership in both local source-of-truth YAML files. The active generated `librechat.yaml`
was verified to contain the stricter latest-message/output-only rule after restart.

Third finding: the harness itself had a false-negative bug. It accepted `--test-expected-text` but
still checked literal `TEST_OK` in the browser body, and it treated equivalent DB `text` plus
`content[]` text as duplicated answer text. I fixed both harness issues and added regression checks.

Final result:

- Harness result: PASS.
- Setup cards visible: true.
- Setup follow-up ready: true.
- Latest parent exactly expected text: true.
- Expected text visible before reload: true.
- Expected text visible after reload: true.
- Latest direct assistant count: 1.
- Latest Phase B visible child count: 0.
- Latest scoped cortex part count: 0.
- Latest scoped cortex names: none.

Verdict: PASS. The browser-visible card setup path works, and the latest simple exact-answer turn no
longer inherits background activation from older history.

Post final-cleanup runtime restart rerun:

- Harness result: PASS.
- Setup cards visible: true.
- Setup follow-up ready: true.
- Latest parent exactly expected text: true.
- Expected text visible before reload: true.
- Expected text visible after reload: true.
- Latest direct assistant count: 1.
- Latest Phase B visible child count: 0.
- Latest scoped cortex part count: 0.

Verdict: PASS against the restarted live runtime.

Final runtime rerun after the Telegram ordering and RAG restore-marker fixes:

- Harness result: PASS.
- Setup cards visible: true.
- Setup follow-up ready: true.
- Latest parent exactly expected text: true.
- Expected text visible before reload: true.
- Expected text visible after reload: true.
- Latest direct assistant count: 1.
- Latest Phase B visible child count: 0.
- Latest scoped cortex part count: 0.

Verdict: PASS against the final restarted runtime.

Post async tool-hold default rerun:

- Harness result: PASS.
- Setup cards visible: true.
- Setup follow-up ready: true.
- Latest parent exactly expected text: true.
- Expected text visible before reload: true.
- Expected text visible after reload: true.
- Latest direct assistant count: 1.
- Latest Phase B visible child count: 0.
- Latest scoped cortex part count: 0.

Verdict: PASS after regenerating/restarting with
`VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=true`. Text async remained off by default; this rerun
checks the browser/latest-user regression surface stayed clean.

## Modern LiveKit QA

Run:

```text
node qa/modern-playground-voice/scripts/livekit_synthetic_audio_qa.js --case-id 2026-05-30-phaseb-short
```

Result:

- Real Chromium playground run with fake microphone WAV.
- Call-session proxy preflight passed.
- LiveKit/voice worker path accepted the synthetic call.
- Transcript matched expected text: `Short Synthetic Voice QA. Alpha Bravo.`
- One listen-only transcript row persisted.
- Synthetic user, call session, ingress event, conversation, and message records were cleaned up.
- Browser page errors: none.

Verdict: PASS for the real modern playground/worker/STT surface. This did not exercise a spoken
multi-turn Phase B overlap; MPV-003 remains PARTIAL for that stress case.

Post-restart rerun:

- Real Chromium playground run passed after the final runtime restart.
- Transcript persisted one listen-only row and matched the synthetic phrase by token ratio.
- Exact first word was imperfect (`Short` was recognized as a similar word), so this is a worker/STT
  persistence pass, not an exact-transcription-quality pass.
- Cleanup removed the synthetic records.

Post activation-rule rerun:

- Real Chromium playground run passed after the activation-subject prompt/fallback change and runtime
  restart.
- The selected voice route was local Whisper.cpp `large-v3-turbo` for STT and local Chatterbox for
  TTS.
- Transcript persisted one listen-only row and matched the expected synthetic utterance by token
  ratio, again with the known `Short`/similar-word first-token drift.
- Cleanup removed the synthetic records.

Post final-cleanup runtime restart rerun:

- Real Chromium playground run passed after the terminal-decision and recall-scope cleanup.
- The selected route remained local Whisper.cpp `large-v3-turbo` for STT and local Chatterbox for
  TTS.
- Transcript persisted one listen-only row and matched the expected synthetic utterance by token
  ratio.
- Cleanup removed the synthetic records.

Final runtime rerun after the Telegram ordering and RAG restore-marker fixes:

- Real Chromium playground run passed.
- The selected route remained local Whisper.cpp `large-v3-turbo` for STT and local Chatterbox for
  TTS.
- Transcript persisted one listen-only row and exactly matched the synthetic phrase.
- Worker logs showed `pywhispercpp_recognize` around `761ms`, `stream_adapter_final` around `761ms`,
  and `listen_only_saved_ms=377`.
- Cleanup removed the synthetic records.

Post async tool-hold default rerun:

- Real Chromium playground run passed with the same fake-microphone WAV after regenerating/restarting
  the runtime with `VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=true`.
- The selected route remained local Whisper.cpp `large-v3-turbo` for STT and local Chatterbox for
  TTS.
- Transcript persisted one listen-only row and matched the expected synthetic phrase by token ratio.
- Cleanup removed the synthetic user, call session, ingress event, conversation, and message.
- Browser page errors: none. Two benign local-storage warnings were recorded.

## Telegram QA

Automated Telegram bridge regression:

```text
cd viventium_v0_4/telegram-viventium/TelegramVivBot && uv run --with pytest pytest ../tests/test_librechat_bridge.py -q
```

Result:

- Focused bridge suite: 95 tests passed.
- Full Telegram suite through the project dependency environment: 287 tests passed.
- Covered terminal `followUpDecision` handling in `_poll_for_followup`.
- Covered the regression where `result=persisted` plus a `suppressionReason` must keep polling for a
  real follow-up instead of marking the stream terminal.
- Covered the regression where canonical text must be delivered before a terminal-silent decision is
  allowed to end polling.
- Live synthetic bridge route run passed with a temporary Telegram mapping:
  - the running Telegram bridge called the local `/api/viventium/telegram/chat` path
  - the streamed response contained the expected synthetic marker
  - cleanup removed the temporary mapping, conversation, messages, ingress event, and transactions
- Post final-cleanup restart synthetic bridge route run passed again:
  - the bridge returned the expected synthetic marker from `/api/viventium/telegram/chat`
  - cleanup removed two temporary mappings, one ingress event, two messages, one conversation, and
    two transactions
- Final runtime synthetic bridge route run passed after the Telegram ordering and RAG
  restore-marker fixes:
  - the bridge returned the expected synthetic marker from `/api/viventium/telegram/chat`
  - bridge timing showed chat HTTP around `412ms`, first stream event around `3535ms`, and final
    stream around `3971ms`
  - API timing showed `recall_scope=none transcript=0`, memory read around `1.4ms`, and cortex
    detection activated `0`
  - cleanup removed one temporary mapping, one ingress event, two messages, one conversation, and
    two transactions; follow-up DB checks found zero remaining synthetic mapping/ingress/message rows
- Live bot log after restart shows the Telegram application running.
- Real Telegram Desktop QA was run with Computer Use after explicit user approval to send harmless
  synthetic prompts from the live account. No private chat content is copied into this report.
- First real send after restart reached the bot and Mongo, but the visible Telegram reply rendered
  identifier underscores incorrectly. Mongo stored the exact synthetic marker; the visible client
  displayed the marker with underscores removed.
- Root cause was Telegram Markdown underscore emphasis parsing treating identifier underscores as
  formatting delimiters. Fixed in the Telegram HTML renderer and covered by regression tests.
- Second real send after the renderer fix visibly returned the exact synthetic marker with
  underscores intact, persisted one exact assistant message in Mongo, and persisted zero stripped
  marker messages. The always-voice setting also sent a `Voice.mp3` reply.
- That second real send also exposed a cold Telegram hot-path stall: `loadtools_ms` was about
  `4068ms` before the model request, caused by independent MCP server definition hydration stacking
  serially.
- MCP definition hydration was changed to fetch unique MCP server definitions concurrently with a
  four-server cap. The package-level regression tests prove both independent server fetches are in
  flight before either response resolves, and that larger fan-out stays bounded.
- Third real send after the MCP fix visibly returned the exact synthetic marker and persisted one
  exact assistant message with zero stripped marker rows. `loadtools_ms` improved from about
  `4068ms` to about `611-664ms`. The remaining slow pieces were outside Telegram delivery:
  main-agent DB/config/init, prompt assembly, blocking Phase A detection, Opus first-token latency,
  and xAI voice-note delivery.
- The shipped voice-mode Phase A default was then changed to keep async enabled through configured
  tool-hold candidates: `VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=true`. Runtime generation
  after restart proved the value in both `runtime.env` and `service-env/librechat.env`.
- Fourth real send after the async tool-hold default visibly returned the exact synthetic marker and
  persisted one exact assistant message with zero stripped marker rows. Logs show main chat
  completion began at about `948ms`; activation detection ran in parallel and completed around the
  voice budget (`691ms`, no activation), rather than forcing the first answer to wait. The main
  initialized in about `338ms`, `loadtools_ms` was about `328ms`, and first model delta arrived
  around `3200ms`.
- The fourth send used the Telegram/main text model path (`claude-opus-4-7`) with a large Telegram
  prompt frame: about `16,987` estimated main-instruction tokens plus about `648` surface prompt
  tokens. This is intentional for Telegram always-voice: it is text-mode reasoning with an audio
  attachment, not a LiveKit voice call or Voice Call LLM override path.
- Always-voice Telegram TTS is working but adds delivered audio latency after the text answer; the
  fourth pass produced xAI voice audio in about `3.8s`.

Verdict: PASS for real Telegram send, visible exact text rendering, backend persistence, and
always-voice audio delivery. Performance verdict for the Telegram surface is now aligned with the
product contract: the serial MCP cold-load stall was fixed, while Telegram intentionally remains on
the main text model/prompt and only adds TTS delivery after the text answer.

## Automated Tests

- Browser latest-user activation harness: PASS after patch/restart.
- Browser latest-user activation harness after final-cleanup restart: PASS.
- Browser latest-user activation harness after final runtime restart: PASS.
- Modern LiveKit synthetic audio after final-cleanup restart: PASS.
- Modern LiveKit synthetic audio after final runtime restart: PASS.
- Modern LiveKit synthetic audio after async tool-hold default restart: PASS.
- Telegram synthetic live bridge after final-cleanup restart: PASS.
- Telegram synthetic live bridge after final runtime restart: PASS.
- LibreChat API targeted suites: 3 passed, 206 tests for follow-up/client/Telegram route group.
- BackgroundCortexService activation policy suite: 33 tests passed.
- `packages/api` initialize/recall plus RAG suite: 2 passed, 41 tests.
- `packages/api` RAG restore-marker focused suite: 1 passed, 22 tests.
- `packages/api` initialize/recall suite: 19 tests passed.
- `packages/api` recall/RAG suites: 4 passed, 57 tests.
- Voice gateway follow-up scheduler: 11 tests passed.
- Full voice gateway suite: 331 tests passed, 20 subtests passed.
- Telegram bridge: 95 tests passed.
- Full Telegram suite: 287 tests passed.
- Telegram HTML + bridge focused suite after underscore renderer fix: 103 tests passed.
- Full Telegram suite after underscore renderer fix: 289 tests passed.
- Telegram text-mode audio correction: focused voice preferences / bot stream / bridge suite passed
  with 129 tests; full Telegram suite passed with 292 tests.
- LibreChat surface prompt and Voice Call LLM override suites passed with 64 tests, including
  Telegram `voice_note` staying in Telegram text-output mode.
- Runtime was reactivated/restarted after the Telegram text-mode audio correction; API, LibreChat
  web, and modern playground health checks returned `200`, and the Telegram bot process was running
  from the active checkout.
- `packages/api` MCP definition concurrency/cap suite: 18 tests passed.
- Voice Phase A async policy suite: 8 tests passed.
- Config compiler release suite after `VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=true`: 108
  tests passed.
- Browser latest-user activation harness after async tool-hold default restart: PASS.
- `packages/api` build after MCP definition hydration/cap change: PASS.
- Public QA evidence safety scanner now covers `qa/results` and dated `qa/*/reports`; 1 test passed.
- Release governance/harness tests: 5 passed.
- Syntax checks passed for changed JS and Python files.
- `git diff --check` passed for the relevant source, docs, and QA paths.

## Claude Review

Initial Claude Opus 4.8 review was run after my own implementation and first QA pass. It agreed with
the Phase B/latest-turn direction but found additional gaps before completion:

- Meeting transcript recall used the raw user personalization flag instead of the resolved recall
  scope. Fixed by requiring `conversationRecallScope === 'all'`.
- Voice and Telegram pollers treated any `suppressionReason` as terminal even when
  `result=persisted`. Fixed by making terminal behavior depend on the structured `result`.
- Public QA safety scanning covered `qa/results` but not dated report folders. Fixed by scanning
  `qa/*/reports` as public evidence too.
- Telegram terminal-silent handling ran before canonical main-answer recovery. Fixed by delivering
  canonical text first when a brief/placeholder answer was replaced by a real final answer.
- Non-blocking RAG verification could reuse cached vector ids during restore/rebuild windows. Fixed
  by honoring the recall rebuild marker before any cached result is served.
- Real Telegram desktop send remained partial at that point pending action-time confirmation. After
  explicit user approval, the real Telegram send path was exercised and the evidence is recorded in
  the Telegram QA section above.

The fixes above were followed by the focused and broader automated suites listed here.

A second review-only Claude Opus 4.8 pass was launched after the real Telegram QA, MCP definition
hydration fix, async tool-hold default change, post-change browser/LiveKit QA, and public-safety
scan. The structured JSON helper failed after repeated schema retries, so a shorter review-only
fallback prompt was run without allowing file edits.

Accepted findings from the second Claude review:

- The docs over-relied on a "budget is shorter than TTFT" safety statement for nevermind+redo. The
  runtime guard is actually streamed-state based: if visible answer text already exists, the
  speculative answer is committed and late cortices surface through Phase B. The docs were tightened
  to state this explicitly, which matters before any faster voice-model override is enabled.
- MCP definition hydration should not fan out to every configured MCP server at once. The
  implementation now keeps independent hydration parallel but caps concurrency at four servers; the
  package suite now includes a fan-out cap regression.
- The earlier "Telegram should maybe use the fast voice Grok override" interpretation was rejected.
  Telegram always-voice is a text-mode surface with optional audio delivery, so the main text
  model/prompt path is intentional.

Deferred findings from the second Claude review:

- A real spoken direct-action/tool-hold voice case is still needed before calling the async
  tool-hold default fully accepted for action-bearing audio UX.
- Any future proposal to make Telegram use a separate low-latency text model must be documented as a
  Telegram text-routing change, not as reuse of the LiveKit Voice Call LLM override.

## Build / Runtime

- `packages/api` build passed after the final RAG restore-marker hardening and again after the MCP
  definition hydration change.
- Local runtime was restarted from the active checkout before QA, after the final Claude-finding
  patch, and again after regenerating runtime env with
  `VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=true`.
- Health checks after restart:
  - API `200`
  - LibreChat web `200`
  - Modern playground `200`
- Final health checks after the last runtime restart:
  - API `200`
  - LibreChat web `200`
  - Modern playground `200`
- Agent Builder visible state previously showed the main agent's Voice Chat Model set to `grok-4.3`;
  final DB verification confirmed `voice_llm_provider=xai`, `voice_llm_model=grok-4.3`, and
  `reasoning_effort=none`. The main text model remains separate.
- Generated runtime verification after the async tool-hold default change confirmed
  `VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=true` in both `runtime.env` and
  `service-env/librechat.env`.

## Follow-Ups

- Run a fresh spoken two-turn MPV-003 overlap case to prove terminal silent Phase B decisions in an
  audible call, not only the scheduler unit and fake-microphone STT surfaces.
- Run a spoken direct-action/tool-hold voice case with
  `VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=true` and verify the first audible answer stays
  non-committal while late/tool context surfaces through Phase B or follow-up evidence.
- Investigate the residual blank-primary-response case where Phase B had to promote a forced synthesis
  onto the canonical parent.
- Keep Telegram always-voice text and voice-note responses on the main text model/prompt. Any future
  Telegram-specific latency optimization must preserve that surface as text mode with audio delivery,
  and must not silently opt into the LiveKit voice-call override.
