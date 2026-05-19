# 2026-05-18 Whisper.cpp Turn-Taking Endpointing QA

## Summary

- Result: PASS for the local Whisper endpointing, publisher-dispatch voice path, and Listen-Only
  pause continuation after promotion/restart; PARTIAL for full authenticated assistant-answer and
  full-agent live barge-in continuation.
- Build/source under test: current local checkout, nested modern playground token route, nested LibreChat voice route changes, and nested voice gateway source.
- Runtime/artifact under test: local Modern Playground, local LiveKit voice route, local Whisper.cpp STT route, voice gateway logs, generated runtime env defaults, and source-of-truth voice prompts.
- Environment: local development runtime with public-safe synthetic evidence.
- Tester: Codex.
- Related change: local Whisper endpointing defaults, LiveKit publisher-dispatch token metadata, voice `{NTA}` guard, voice stream abort/persistence, and LiveKit `TurnHandlingOptions` migration.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `MPV-001` | PARTIAL PASS | Promoted browser call connected, microphone published, LiveKit assigned publisher worker, DB persisted active job/worker state | Full assistant answer was intentionally not claimed because the synthetic call session did not belong to a real LibreChat user. |
| `MPV-004` | PARTIAL PASS | Focused voice gateway tests, real pywhispercpp benchmark, promoted browser microphone run, voice gateway timing logs | Local Whisper endpointing was proven live; full provider/TTS first-audio timing remains outside this narrow endpointing run. |
| `MPV-003` | PARTIAL PASS | Voice stream abort tests, route persistence tests, source prompt check | Barge-in cancellation is covered; full post-launch continuation/edit protocol remains future work. |
| `MPV-006` | PARTIAL | Prompt and endpointing changes support safer voice web-search turns | Full voice web-search run remains tracked by the web-search escaped-case QA report. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `MPV-UC-001` | Start a call from an authenticated LibreChat conversation and send a simple typed or spoken prompt. | Modern Playground browser with microphone permission and promoted local runtime. | PARTIAL PASS | Browser opened the local voice assistant page, showed the local Whisper.cpp route, connected to LiveKit, and published the microphone track. | Connection-details probe created explicit LiveKit dispatch; voice gateway logs showed worker job receipt, local Whisper route, `min_silence=0.5s`, `min_endpoint=0.5s`, and transcription delays of about `1.35-1.68s`; DB state showed active job/worker ids. | The run used a synthetic call session without a real user, so the LLM response leg correctly failed auth and no full answer/TTS acceptance is claimed. |
| `MPV-UC-002` | Interrupt or send a second turn while prior work is still active. | Voice gateway stream tests and LibreChat voice abort route tests. | PARTIAL | Browser surface was reachable, but no public-safe live barge-in call was recorded in this report. | Abort endpoint and shielded cancellation tests passed; partial assistant persistence is covered. | Post-launch continuation/edit protocol and microphone-level barge-in QA remain open. |
| `MPV-UC-003` | Ask the voice agent to look something up when Web Search appears enabled. | Prompt/source review plus linked web-search QA report. | PARTIAL | Not rerun through voice in this report. | Voice prompt guard and web-search failure classification docs/tests support the behavior. | Connected-model voice web-search fallback run remains required. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Modern Playground local Whisper endpointing and turn interruption.
- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`, `docs/requirements_and_learnings/14_Voice_Latency_and_Memory_RCA.md`, and `docs/requirements_and_learnings/34_Voice_Chat_LLM_Override.md`.
- Use case: `MPV-UC-001`, `MPV-UC-002`, and supporting `MPV-UC-003`.
- QA case: `MPV-004`, `MPV-003`, and supporting `MPV-006`.
- Expected result: local Whisper turns finish after about `0.5s` silence by default, call-session deep links dispatch the publisher worker after microphone publish, cut-off spoken turns can return `{NTA}` without runtime intent heuristics, interrupted assistant streams are aborted/persisted safely, and evidence separates voice-path acceptance from full authenticated answer acceptance.
- Actual evidence: focused suites passed, pywhispercpp benchmark matched the selected local model, generated defaults changed to `0.5s`, the promoted runtime restarted from the current checkout, browser QA connected and published microphone audio, LiveKit assigned the publisher worker, DB state persisted active job/worker ids, and local Whisper final transcripts showed about `1.35-1.68s` transcription delay with `0.5s` endpointing.
- Remaining gap or fix: run a real authenticated call for full LLM/TTS answer acceptance and run
  full-agent microphone-level barge-in QA. Listen-Only pause continuation is now accepted in
  `qa/modern-playground-voice/reports/2026-05-18-synthetic-audio-livekit-continuation.md`.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Voice calls, voice latency RCA, voice LLM override, `MPV-UC-001`, `MPV-UC-002`, `MPV-004`, and `MPV-003`. |
| Code owning path | Which code path owns the behavior? | Voice gateway local Whisper provider, voice gateway worker turn handling, LibreChat voice stream abort route, and voice source-of-truth prompt bundle. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | Parent voice requirement docs, nested voice gateway docs, LibreChat voice prompt source, and modern-playground voice cases. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Voice gateway pytest suite, LibreChat voice route/prompt tests, config compiler tests, prompt registry tests, pywhispercpp benchmark, and browser reachability check. |
| Local/external prerequisite state | Which required local service, provider, Docker-backed sidecar, OAuth grant, API key, model, or hosted dependency was proven healthy or degraded? | Local voice route used Whisper.cpp `large-v3-turbo`; Docker-backed search health was outside this report and is tracked by web-search QA. |
| Logs | Which sanitized logs confirm or contradict the result? | Voice gateway logs showed shared VAD `min_silence=0.5s`, local Whisper model load, publisher job receipt, AgentSession `min_endpoint=0.5s`, and live `transcription_delay` around `1.35-1.68s`. |
| DB/state/persistence | Which sanitized state, DB count/hash, persisted message, config, or artifact confirms it? | Synthetic call-session state showed dispatch confirmation and active job/worker fields after the browser microphone publish; public report records shape only, not raw ids or transcript text. |
| Generated/shipped artifact | Which generated config, compiled bundle, prebuilt helper, or installed artifact was inspected when applicable? | Generated runtime env defaults, source compiler output, Next production build, promoted helper/stack status, and runtime health endpoints were inspected. |
| Real user path | Which browser/computer, Telegram, voice, installer, CLI, MCP/tool, scheduler, or GlassHive path was used like a user? | Browser opened the local Modern Playground voice assistant, clicked Start chat, granted microphone permission, toggled the microphone, and ended the call. |
| Visual/UX comparison | Does the visible UI/UX or delivered result match the expected behavior and supporting evidence? | Visible route matched local Whisper configuration; browser console showed connection and microphone publish with no application errors. |
| Not run / blocked | Which required surface was not run, and why is the result partial or blocked? | Full authenticated assistant-answer/TTS and barge-in continuation were not accepted because this run intentionally used a synthetic call session without a real user account. |

## User-Grade Evidence

- Surface exercised: local Modern Playground voice assistant in a browser, plus focused voice gateway and LibreChat route tests.
- Real user path: browser opened the local voice page, clicked Start chat, enabled the microphone, and ended the call.
- Visible outcome: the page rendered with Whisper.cpp Local `large-v3-turbo` as the listening route and entered the connected call controls.
- Expanded/detail state: route details showed the local listening/speaking choices; browser console showed LiveKit connection, microphone track publish, remote agent participant connection, and no app errors.
- Persistence/reload result: DB/state shape confirmed dispatch and active job/worker fields after microphone publish; no raw ids, private transcript text, or message contents are recorded here.
- Local/external prerequisite state: selected STT route was local Whisper.cpp; promoted runtime logs showed the new `0.5s` VAD and endpointing profile.
- Evidence retrieval classification, if applicable: not applicable to this endpointing report; web-search degradation classification is tracked in the web-search report.
- Fallback path, if applicable: `{NTA}` voice fallback is prompt-owned and source-tested; browser/local-delegation fallback for current-fact search remains tracked by web-search QA.
- Backend/log/DB confirmation: source tests, route tests, generated env defaults, pywhispercpp benchmark, token route probe, sanitized runtime logs, and DB shape all point to the same endpointing and publisher-dispatch behavior.
- Final model/runtime wording check: this report claims live local Whisper endpointing and publisher-dispatch acceptance, but does not claim full authenticated assistant-answer/TTS or barge-in continuation acceptance.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting evidence, not substitutes for any required visible-UI, detail-state, persistence, or wording step.

## Automated Evidence

```bash
python -m pytest viventium_v0_4/voice-gateway/tests -q
npm test -- api/server/routes/viventium/__tests__/voice.spec.js api/server/services/viventium/__tests__/surfacePrompts.spec.js --runInBand
python -m pytest tests/release/test_prompt_registry.py tests/release/test_config_compiler.py -q
git diff --check HEAD
```

Additional public-safe evidence from the original run:

- Voice gateway focused pytest after endpointing, cancellation, and `TurnHandlingOptions` changes: `115 passed, 1 warning`.
- Focused post-persistence reruns: `voice-gateway/tests/test_librechat_llm.py` passed and the LibreChat voice route suite passed.
- Real pywhispercpp benchmark with the selected `large-v3-turbo` model showed source default VAD min silence `0.5s`, warm inference around one second, and a transcript matching the synthetic utterance.
- Browser reachability opened the local voice assistant and observed the visible local Whisper route.

Additional promoted-runtime evidence after restart:

- Modern playground TypeScript check passed, route formatting passed, and `next build` completed successfully.
- Focused voice-gateway endpointing/LLM tests passed: `83 passed, 1 warning`.
- Release dispatch/compiler/prompt contract tests passed after updating the dispatch contract to assert explicit LiveKit dispatch by default: `134 passed`.
- Supported runtime promotion/restart completed with local dirty-testing allowance for this patch, and health checks returned 200/OK for LibreChat API, LibreChat frontend, modern playground, and voice gateway.
- A connection-details probe for a synthetic call session created explicit LiveKit dispatch targeting `librechat-voice-gateway`, and persisted dispatch confirmation; the route now fails closed if the dispatch claim cannot be acquired. Token-room-config dispatch is now opt-in.
- Browser QA clicked Start chat, enabled microphone, observed LiveKit connection/microphone publish/remote agent participant events, and then ended the call.
- Voice gateway logs showed publisher worker receipt, local Whisper route, `min_silence=0.5s`, `min_endpoint=0.5s`, live inference times around `0.84-1.22s`, and live transcription delays around `1.35-1.68s`.

## Findings

- Defects: old source defaults kept local Whisper transcript visibility behind a `1.0s` silence gate plus local inference; interruption cleanup did not abort the matching LibreChat generation job; the browser token route used pre-connect room dispatch instead of publisher-compatible token dispatch.
- Regressions: none found in focused source, route, compiler, and prompt tests.
- Flakes: none recorded in this report.
- Environment issues: synthetic browser QA without a real user correctly blocked the LLM response leg with auth, so full assistant answer/TTS was not claimed.
- Residual risks: authenticated full-answer QA, microphone-level barge-in QA, connected-model voice web-search fallback, and post-launch continuation/edit protocol remain open.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
