# 2026-05-18 Whisper.cpp Turn-Taking Endpointing QA

## Summary

- Result: PARTIAL pass for source, docs, focused tests, browser reachability, and local STT benchmark; live promoted microphone-level acceptance remains open.
- Build/source under test: current local checkout, nested LibreChat voice route changes, and nested voice gateway source.
- Runtime/artifact under test: local Modern Playground, local LiveKit voice route, local Whisper.cpp STT route, voice gateway logs, generated runtime env defaults, and source-of-truth voice prompts.
- Environment: local development runtime with public-safe synthetic evidence.
- Tester: Codex.
- Related change: local Whisper endpointing defaults, voice `{NTA}` guard, voice stream abort/persistence, and LiveKit `TurnHandlingOptions` migration.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `MPV-004` | PARTIAL PASS | Focused voice gateway tests, LibreChat route/prompt tests, real pywhispercpp benchmark, browser reachability | Source and reachable UI were proven; installed local runtime still needed safe promotion/restart before microphone acceptance. |
| `MPV-003` | PARTIAL PASS | Voice stream abort tests, route persistence tests, source prompt check | Barge-in cancellation is covered; full post-launch continuation/edit protocol remains future work. |
| `MPV-006` | PARTIAL | Prompt and endpointing changes support safer voice web-search turns | Full voice web-search run remains tracked by the web-search escaped-case QA report. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `MPV-UC-001` | Start a call from an authenticated LibreChat conversation and send a simple typed or spoken prompt. | Modern Playground browser reachability and local voice runtime evidence. | PARTIAL | Browser opened the local voice assistant page and showed the local Whisper.cpp route. | Voice gateway logs, generated env defaults, config compiler coverage, and focused route tests align with the new endpointing profile. | Microphone-level run on the promoted installed runtime remains required. |
| `MPV-UC-002` | Interrupt or send a second turn while prior work is still active. | Voice gateway stream tests and LibreChat voice abort route tests. | PARTIAL | Browser surface was reachable, but no public-safe live barge-in call was recorded in this report. | Abort endpoint and shielded cancellation tests passed; partial assistant persistence is covered. | Post-launch continuation/edit protocol and microphone-level barge-in QA remain open. |
| `MPV-UC-003` | Ask the voice agent to look something up when Web Search appears enabled. | Prompt/source review plus linked web-search QA report. | PARTIAL | Not rerun through voice in this report. | Voice prompt guard and web-search failure classification docs/tests support the behavior. | Connected-model voice web-search fallback run remains required. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Modern Playground local Whisper endpointing and turn interruption.
- Requirement: `docs/requirements_and_learnings/06_Voice_Calls.md`, `docs/requirements_and_learnings/14_Voice_Latency_and_Memory_RCA.md`, and `docs/requirements_and_learnings/34_Voice_Chat_LLM_Override.md`.
- Use case: `MPV-UC-001`, `MPV-UC-002`, and supporting `MPV-UC-003`.
- QA case: `MPV-004`, `MPV-003`, and supporting `MPV-006`.
- Expected result: local Whisper turns finish after about `0.5s` silence by default, cut-off spoken turns can return `{NTA}` without runtime intent heuristics, interrupted assistant streams are aborted/persisted safely, and evidence separates source readiness from installed-runtime acceptance.
- Actual evidence: focused suites passed, pywhispercpp benchmark matched the selected local model, generated defaults changed to `0.5s`, browser reachability confirmed the voice surface, and logs showed the unpromoted installed runtime still had old defaults.
- Remaining gap or fix: promote/restart the supported runtime safely, rerun microphone-level transcript and barge-in acceptance, and implement a full post-launch user-message continuation/edit protocol.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Voice calls, voice latency RCA, voice LLM override, `MPV-UC-001`, `MPV-UC-002`, `MPV-004`, and `MPV-003`. |
| Code owning path | Which code path owns the behavior? | Voice gateway local Whisper provider, voice gateway worker turn handling, LibreChat voice stream abort route, and voice source-of-truth prompt bundle. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | Parent voice requirement docs, nested voice gateway docs, LibreChat voice prompt source, and modern-playground voice cases. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Voice gateway pytest suite, LibreChat voice route/prompt tests, config compiler tests, prompt registry tests, pywhispercpp benchmark, and browser reachability check. |
| Local/external prerequisite state | Which required local service, provider, Docker-backed sidecar, OAuth grant, API key, model, or hosted dependency was proven healthy or degraded? | Local voice route used Whisper.cpp `large-v3-turbo`; Docker-backed search health was outside this report and is tracked by web-search QA. |
| Logs | Which sanitized logs confirm or contradict the result? | Voice gateway logs showed the currently installed runtime was still using old endpointing defaults before promotion, so live acceptance was not claimed. |
| DB/state/persistence | Which sanitized state, DB count/hash, persisted message, config, or artifact confirms it? | Runtime env/config shape and recent call-session state confirmed the local pywhispercpp route; public report records shape only, not raw ids or transcript text. |
| Generated/shipped artifact | Which generated config, compiled bundle, prebuilt helper, or installed artifact was inspected when applicable? | Generated runtime env defaults and source compiler output were inspected; installed runtime still needed promotion/restart before final acceptance. |
| Real user path | Which browser/computer, Telegram, voice, installer, CLI, MCP/tool, scheduler, or GlassHive path was used like a user? | Browser opened the local Modern Playground voice assistant and observed the visible local Whisper route. |
| Visual/UX comparison | Does the visible UI/UX or delivered result match the expected behavior and supporting evidence? | Visible route matched local Whisper configuration; microphone-level timing and barge-in UX were not accepted in this report. |
| Not run / blocked | Which required surface was not run, and why is the result partial or blocked? | Full microphone-level run on the newly promoted runtime was not run because the installed runtime had not yet been safely restarted from this checkout. |

## User-Grade Evidence

- Surface exercised: local Modern Playground voice assistant in a browser, plus focused voice gateway and LibreChat route tests.
- Real user path: browser opened the local voice page and observed the configured listening route.
- Visible outcome: the page rendered with Whisper.cpp Local `large-v3-turbo` as the listening route.
- Expanded/detail state: route details showed the local listening/speaking choices; no browser application error was recorded.
- Persistence/reload result: DB/state shape confirmed local pywhispercpp call-session usage; no raw ids, private transcript text, or message contents are recorded here.
- Local/external prerequisite state: selected STT route was local Whisper.cpp; installed runtime logs still reflected old endpointing defaults, so promotion/restart was explicitly required before final acceptance.
- Evidence retrieval classification, if applicable: not applicable to this endpointing report; web-search degradation classification is tracked in the web-search report.
- Fallback path, if applicable: `{NTA}` voice fallback is prompt-owned and source-tested; browser/local-delegation fallback for current-fact search remains tracked by web-search QA.
- Backend/log/DB confirmation: source tests, route tests, generated env defaults, pywhispercpp benchmark, and sanitized runtime logs all point to the same endpointing root cause and partial fix state.
- Final model/runtime wording check: this report does not claim live microphone acceptance; it says the source and focused runtime contracts are ready for a promoted-runtime acceptance run.
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

## Findings

- Defects: old source defaults kept local Whisper transcript visibility behind a `1.0s` silence gate plus local inference; interruption cleanup did not abort the matching LibreChat generation job.
- Regressions: none found in focused source, route, compiler, and prompt tests.
- Flakes: none recorded in this report.
- Environment issues: installed local runtime still needed safe promotion/restart to pick up the new source defaults.
- Residual risks: full microphone-level acceptance, connected-model voice web-search fallback, and post-launch continuation/edit protocol remain open.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
