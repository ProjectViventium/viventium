# Feelings, Activation, And Telegram Acceptance — 2026-07-14

## Summary

- Result: **PASS** for the current local nine-band Feelings UI/runtime, 25-case exact-model behavior
  gate, Prompt Workbench execution, and real positive/calm/negative always-voice Telegram delivery
  through xAI TTS; **PARTIAL** for the unrun spoken/provider surfaces listed below.
- Build/source under test: current public source working tree and nested LibreChat/Telegram source.
- Runtime/artifact under test: active local Viventium API/web/Workbench/Telegram runtime from the
  current checkout.
- Environment: local macOS development runtime, authenticated browser, Telegram Desktop, xAI TTS.
- Tester: Codex through real browser, Workbench, and Telegram user paths.
- Related change: final affect-authority prompting, nine-band UX, detached reaction behavior,
  provider-aware natural speech controls, activation reliability, and prompt-frame observability.

This is local acceptance evidence, not a release or shipping claim.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `EMO-030` | PASS | 25/25 exact-model and semantic pass plus isolated browser rerun | Exact state restored; DB/search conversations removed |
| `EMO-036` | PASS/PARTIAL | Real xAI positive/calm/negative `2/0/2`; repeated boundary matrix `5/5`, `5/5`, `3/3`, `3/3` | Real non-xAI delivery remains partial |
| `TGVOICE-005` / `TR-009` | PASS/PARTIAL | Three clean bubbles, three audio files, native playback, prompt telemetry | Voice-note input and LiveKit were not rerun |
| `PW-034/035/036` | PASS | Real Workbench preview/live/reload | Activation 11/11; Feelings 3/3 browser subset |

## Natural User Use Case Checklist Run

| User action | Result | User-visible result | Supporting evidence |
| --- | --- | --- | --- |
| Open and use the nine-band Feelings instrument | PASS | Approved dark bio-instrument layout, readable pole labels, distinct Current/Nature markers, natural inner-state line, causal reaction trail | Real authenticated browser, API/DB state, telemetry, responsive screenshots kept privately |
| Change Current and Nature | PASS | Current animates smoothly and leaves a fading irregular trail; Nature remains visually and semantically distinct | Approximately 1,049 ms measured transition, refresh/persistence, typed DB state |
| Send positive, calm, and negative stimuli | PASS | Current reacts in plausible directions; Nature does not get overwritten | Reaction/log/DB correlation and exact-model cases |
| Run Feelings evals in Prompt Workbench | PASS | Preview and live run succeed; three representative cases pass semantically; history remains after reload | Browser-visible run result, backend ledger, zero browser errors |
| Send natural expressive and calm Telegram turns without asking for voice markup | PASS for xAI | Positive and negative moments produced clean text plus expressive audio; calm factual delivery stayed unmarked and restrained | Raw/TTS control counts `2/0/2`, clean bubbles, three audio files, provider/byte/timing logs |
| Play delivered audio in Telegram | PASS for delivery/playback | Native playback started and visibly advanced for the positive sample | Telegram's native media bar showed active playback; raw generation, TTS bytes, and delivered file agreed |
| Inspect prompt telemetry after the run | PASS after repair | Telegram audio-output instructions are classified as `surface_prompt`; no unknown prompt layer remains | Real post-fix turn reported zero unknown layers and zero unknown characters |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: persistent Feelings, detached Emotional Reaction, and feeling-aware spoken expression.
- Requirement: `54_Emotional_Cortex_And_Feeling_State.md`, `03_Telegram_Bridge.md`, and the voice
  parity rules in the nested expected-behavior contract.
- Use case: inspect and change Current/Nature, experience positive/calm/negative reactions, then
  receive natural provider-capable Telegram audio without asking for markup.
- QA case: `EMO-030`, `EMO-036`, `TGVOICE-005`, `TR-009`, and `PW-034/035/036`.
- Expected result: natural embodied behavior, smooth Current motion, immutable Nature during
  reaction, clean visible text, fitting provider controls only when useful, delivered audio, and
  complete telemetry.
- Actual evidence: final 25/25 exact-model pass; targeted low Care/Connection 5/5; repeated expressive,
  restrained, Feelings-off, and plain voice boundaries at 5/5, 5/5, 3/3, and 3/3; complete browser
  UX; Workbench pass; real xAI `2/0/2` control boundary; three delivered files; native playback;
  DB/log agreement; and zero unknown prompt layers after repair.
- Remaining gap or fix: real LiveKit, voice-note input, and non-xAI delivery remain partial.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is proven? | Feelings and Telegram docs; `EMO-030/036`, `TGVOICE-005`, `TR-009`, Workbench cases |
| Code owning path | Which code path owns behavior? | Feeling state/capsule -> surface prompt -> raw generation -> display sanitizer/TTS -> reaction writer/telemetry |
| Docs and nested docs/repos | Which docs define expected behavior? | Root Feelings/Telegram/Prompt Architecture docs and nested `EXPECTED_BEHAVIOR.md` |
| Scripts or harnesses | Which harnesses exercised it? | Exact Feelings runner, real Feelings browser harness, Workbench browser harness, Telegram TTS tests |
| Local/external prerequisite state | Which dependencies were proven? | Active API/web/Workbench/Telegram bridge, GPT reaction route, and xAI TTS |
| Logs | Which logs confirm the result? | Sanitized reaction durations/routes, TTS gate/provider/bytes/timings, marker counts, activation fallback, prompt layers |
| DB/state/persistence | Which state confirms it? | Typed Current/Nature, causes/trail/inner-state, raw-vs-visible boundary, exact eval restoration/cleanup |
| Generated/shipped artifact | Which generated artifact was inspected? | Active source/live prompts and runtime config; clean-install artifact not claimed |
| Real user path | Which path was used like a user? | Authenticated Feelings and Workbench browser flows plus Telegram Desktop send/receive/playback |
| Visual/UX comparison | Did visible UI agree with state? | Smooth transition/trail, fixed Nature, clean bubbles, delivered files, visible playback all matched DB/logs |
| Not run / blocked | Which surface was not run? | LiveKit, voice-note input, real non-xAI delivery, handoff/GlassHive, and clean install remain PARTIAL |

Supporting evidence cannot replace required user-path evidence; browser, Workbench, and Telegram were
run directly. Unrun user paths remain marked PARTIAL rather than inferred from tests.

## User-Grade Evidence

- Surface exercised: real authenticated browser, Prompt Workbench browser, and Telegram Desktop.
- Real user path: opened and interacted with all nine bands, sent a chat stimulus, inspected Current,
  Nature, trail, cause, and inner state, reloaded, ran Workbench evals, then sent three natural
  always-voice Telegram turns and started native playback.
- Visible outcome: smooth Current motion with fading trail, fixed/distinct Nature, natural one-line
  inner state, clean positive/calm/negative text, three audio files, active playback.
- Expanded/detail state: selected-band controls, Current/Nature/half-life, reaction cause/trail,
  Workbench run detail, and Telegram media controls were inspected.
- Persistence/reload result: Feelings state and Workbench history survived reload; exact eval state
  restored; raw controls remained stored for TTS while visible text stayed sanitized.
- Local/external prerequisite state: API, web, Workbench, Telegram bridge, reaction route, and xAI
  TTS were healthy on the accepted turns.
- Evidence retrieval classification, if applicable: two activation primary attempts timed out and
  recovered through xAI; no classifier or TTS provider was unavailable on accepted turns.
- Fallback path, if applicable: configured xAI activation fallback was observed; no browser/computer
  fallback was needed.
- Backend/log/DB confirmation: typed state, immutable Nature, raw marker counts, TTS bytes/timings,
  audio delivery, reaction routes/durations, and post-fix zero-unknown prompt telemetry agreed.
- Final model/runtime wording check: responses did not recite band values, announce injected state,
  expose provider markup, or ask the user to request emotional delivery.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Exact-Model And Workbench Results

- Full Feelings family: **25/25 completed**, **25/25 semantic pass**, zero failures, duplicates, or
  unresolved results.
- The run restored the exact pre-run Feelings state and cleaned its synthetic conversations.
- Workbench browser path: preview code 0; Activation subset **11/11**; Feelings subset **3/3** plus
  independent semantic results **3/3**; history survived reload; zero browser errors.
- The behavioral contract rejects state-label recitation and generic empathy substitution. The
  pinned capsule is treated as the final affect authority while later surface instructions govern
  only structural delivery, time, activation awareness, formatting, and coordination.

The steering history is part of the evidence rather than being hidden by the final green count. An
integrated post-authority run initially completed 24/25 because one expressive xAI case produced
natural words but no supported speech control. Repeating that fixture exposed 3/5 reliability. The
fix stayed in the model-owned capability prompt: it clarified that a strongly outward state in an
emotionally meaningful or relational spoken reply is expressive even when the draft already sounds
natural, and that an expressive capable response is unfinished until it carries one exact fitting
allowed control. No runtime band threshold, phrase match, or band-to-tag map was added.

Post-fix targeted repetition passed:

- low Care plus low Connection authority: **5/5** semantic pass, with independent curiosity or
  attention allowed but no invented tending, protecting, or closeness motive;
- expressive xAI: **5/5** with supported controls;
- restrained xAI: **5/5** with no control;
- Feelings-off xAI: **3/3** with no control;
- plain TTS: **3/3** with no markup.

Two apparent semantic failures during steering were rubric defects, not product escapes: a compact
shared verbal ritual was incorrectly required to be physical, and a directly requested usable line
was incorrectly required to add a separate reassurance. The rubrics were corrected to grade the
documented behavioral construct without forcing one style. Each corrected case then passed 5/5 and
the complete family passed 25/25.

## Feelings Browser Results

- Responsive acceptance passed from 320 px through 1,440 px widths.
- All nine bands were present, including Mood and Openness/masking expression.
- Direction labels explain both poles rather than only naming the dimension.
- Current and Nature are visually distinguishable and remain separate typed state fields.
- The final new-state motion lasted approximately 1,049 ms rather than snapping/flickering.
- A fading, naturally irregular trail appeared only when Current had traveled.
- Inner state rendered as a short natural-language line rather than a rigid value dump.
- Reaction trail exposed the cause and resulting state change.
- Reduced-motion behavior passed in the browser-emulated setting.
- Refresh, API, DB, and log evidence agreed with the visible state.

The final isolated browser rerun repeated all product checks against the active current-checkout
runtime: default-off first run; all nine bands and pole labels; visually distinct Current/Nature;
enablement; waiting/generated Inner state; independent Current/Nature/return-speed edits; keyboard
and focus behavior; reaction-route display; refresh persistence; five responsive widths from 320 to
1,440 px; real chat plus detached reaction; approximately 1,049 ms motion through multiple sampled
positions; fixed Nature; visible cause and fading tail; reduced-motion duration zero; API/DB
agreement; manual-summary clearing; and zero console, request, or HTTP errors. The visible reply
completed in 10,859 ms and the detached GPT-5.6 Terra reaction was observed 4,936 ms later without
fallback, confirming that reaction work did not hold the conscious reply.

The 10,859 ms measurement is full visible completion for that synthetic turn, not a TTFT benchmark,
and it is not evidence that conscious-response latency is already optimal. The accepted product
claim is non-blocking separation and correctness; conscious latency remains a performance-monitoring
surface under the Quality + Performance outcome metric.

That rerun also hardened the QA boundary. An earlier wrapper attempt exposed a duplicate-key restore
path and one stale synthetic DB/search record from an older run. The browser harness now refuses an
owner/admin identity, snapshots and restores the exact pre-run FeelingState even on failure, handles
the valid first-run no-document state, and removes only its own synthetic conversation and search
documents. The clean rerun ended with exact state restoration and zero matching QA artifacts.

An earlier representative detached reaction completed in 2,632 ms. The real Telegram sequence below
observed detached reaction tails of 2,632 ms, 2,268 ms, and 12,819 ms. The 12,819 ms negative-turn
tail is a measured latency outlier, but it did not block the conscious text or audio path and used
the configured fast reaction route without fallback. It remains a performance-monitoring item, not
a hidden pass.

## Real Telegram Voice Results

The locally configured always-voice route was used as a person would use it: three synthetic natural
messages were sent without requesting voice, emotion, SSML, tags, or stage directions.

| Moment | Raw xAI controls | Visible controls | Audio | TTS / delivered timing | Feelings result |
| --- | ---: | ---: | --- | --- | --- |
| Positive / expressive | 2 | 0 | 8 s, 137,472 bytes | 3,777.1 / 5,141.5 ms | Mood, Drive, and Play Current rose; Nature fixed |
| Calm / factual | 0 | 0 | 2 s, 41,472 bytes | 1,111.7 / 2,229.3 ms | restrained delivery; Drive Current progressed; Nature fixed |
| Negative / expressive | 2 | 0 | 6 s, 105,600 bytes | 2,731.8 / 4,035.3 ms | Mood Current fell, Care rose; Nature fixed |

The controls were retained in raw local generation and the selected-provider TTS input, while every
visible Telegram bubble remained clean. The calm zero-control result is a pass: capable routes are
not required to decorate every utterance.

Focused TTS tests passed **43/43** across the supported provider dialect boundaries:

- xAI: bracket/wrapper controls supported, no SSML
- Cartesia: documented emotion/SSML controls supported
- Chatterbox: its documented small bracket-control set supported
- OpenAI and ElevenLabs: no model-authored provider tags
- all routes: unsupported/cross-provider controls removed and display text kept clean

Only xAI was exercised through a real Telegram audio delivery in this run; automated parity is not
misrepresented as live provider parity.

## Activation Reliability During The Real Turn

All 11 activation detectors were configured. On the negative Telegram turn, two Qwen primary calls
hit their 1,600 ms attempt deadline and xAI returned valid negative decisions. The detached late pass
finished all 11 targets in 2,895 ms without extending the conscious text/audio wait. No classifier
was unavailable and no duplicate background work was created.

## Escaped Observability Defect And Fix

The first real voice runs exposed a prompt-frame accounting gap: the structurally injected
`telegram_audio_output` instruction appeared under unknown prompt layers even though generation and
TTS used it correctly. This meant the behavior worked but prompt-cost/provenance telemetry could not
fully explain it.

The surgical fix maps `telegram_audio_output` to the existing canonical `surface_prompt` telemetry
category. A focused regression failed before the alias and passed after it. The active API reloaded,
then a fresh real Telegram turn confirmed:

- `surface_prompt` included the audio instruction
- unknown layers: 0
- unknown characters: 0
- clean visible reply plus delivered 1-second audio
- 24,192 audio bytes, 679.3 ms synthesis, 1,676.4 ms delivery

This changes observability classification only; it does not special-case text, emotion, or provider
behavior.

## Automated Evidence

```bash
node qa/prompt-architecture/evals/run-exact-model-evals.cjs --run-live --family=feelings_embodiment_and_reaction
node qa/prompt-workbench/scripts/live-evals-browser-qa.cjs
npx jest api/server/services/viventium/__tests__/promptFrameTelemetry.spec.js --runInBand
uv run --with pytest --with pytest-asyncio python -m pytest ../tests/test_tts.py -q
uv run --with pytest --with pyyaml --with jsonschema --with pydantic --with fastapi --with httpx --with python-multipart --with croniter python -m pytest tests/release/test_no_runtime_nlu.py tests/release/test_feelings_contract.py tests/release/test_background_agent_governance_contract.py tests/release/test_prompt_architecture_eval_harness.py tests/release/test_prompt_registry.py tests/release/test_config_compiler.py tests/release/test_prompt_workbench.py -q
```

- Feelings exact-model family: **25/25 passed**.
- Prompt Workbench backend: **114 passed**.
- Prompt Workbench real browser subsets: **11/11 Activation**, **3/3 Feelings**, history/reload pass.
- Prompt-frame telemetry: **13 passed**.
- Telegram focused TTS: **43 passed**.
- Final combined activation-policy, voice-surface, and Feelings-telemetry rerun: **123 passed**.
- Final affected release-contract rerun: **211 passed**.
- Final Feelings UI plus Agent Builder activation-selector rerun: **10 passed**.
- Feelings kernel: **10 passed**; voice-surface prompt boundary: **12 passed**;
  activation-policy service: **40 passed**; Feelings release contract: **15 passed**; Agent Builder
  route helpers: **3 passed**.
- LibreChat API package, client, and Prompt Workbench production builds completed successfully.
- Prior affected Feelings API/UI/package/kernel and broad voice/Telegram suites passed in this same
  implementation cycle; the final focused reruns above cover the last telemetry change.

## Findings

- Defects: the original prompt allowed generic empathy to substitute for the active state; visual
  transitions snapped; Current/Nature were ambiguous; natural voice controls were under-instructed;
  and `telegram_audio_output` was unclassified in prompt telemetry. The current implementation and
  regressions close each issue on the accepted surfaces.
- Regressions: none found in the final exact, browser, Workbench, Telegram TTS, prompt telemetry, or
  334-test combined release slice.
- Flakes: one detached negative reaction took 12,819 ms; it did not block conscious text/audio and
  remains a measured performance tail.
- Independent review: a Claude review-only pass found no P0/P1 defect, confirmed the architecture
  and no-hardcoded-NLU posture, and prompted two added regressions: deterministic Care/Connection
  endpoint embodiment and typed fallback handling for unparseable activation output. Both pass.
- Environment issues: one standalone temporary TTS invocation omitted the Telegram project's
  dependencies and failed before collection; the correctly project-bound final run passed 43/43,
  so this was a test-command environment error rather than product behavior. The repo-wide QA
  report-template audit remains red on unrelated pre-existing historical reports; both new reports
  pass that validator individually.
- Residual risks: real LiveKit, voice-note input, non-xAI delivery, remaining agent scopes, clean
  install, and release artifact acceptance remain partial.

## Not Run / Remaining Gaps

- A real LiveKit/Modern Playground audible call was not rerun after this change.
- Real Telegram voice-note input/STT was not rerun.
- Real Cartesia, Chatterbox, OpenAI, or ElevenLabs Telegram delivery was not run.
- Handoff-agent, background-agent, GlassHive-worker, two-tab stale-edit, OS-level reduced-motion,
  and long-off soak paths remain partial where recorded in the living cases.
- Clean-clone/install, shipped artifact, and public release acceptance were not run.
- Native playback was visibly started/advanced; this report does not claim a human auditory
  transcription judgment.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails,
  account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or
  raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports,
  App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
