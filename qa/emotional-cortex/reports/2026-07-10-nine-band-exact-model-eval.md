# Nine-Band Feelings Acceptance - 2026-07-10

## Summary

- Result: **PASS** for the nine-band production web path: exact-model behavior, real chat/reaction,
  visual interaction, persistence, observability, focused tests, and production builds.
- Result: **PARTIAL** for cross-surface release certification because true voice, Telegram, handoff,
  background-agent, and GlassHive user paths, two-tab conflict, OS-setting reduced motion, and a
  long-off soak were not run.
- Live exact-model matrix: **19/19 completed and 19/19 semantic pass**; zero execution,
  duplicate-response-quality, or unresolved-async-quality failures.
- Authenticated browser contract: every applicable assertion passed after a real 320 px header
  defect was found, fixed, and the complete suite rerun.
- Runtime restart: API state and the exact model-authored Inner state were visible after restart.
- Live reaction route: `gpt-5.6-terra`, Responses API, reasoning `none`, Priority/Fast, no fallback.
- Final post-restart reaction sample: healthy in 3,506 ms and detached from the main reply.
- Post-review durability rerun: all 34 browser checks passed after a real stop/start. During an
  OpenAI provider incident, the visible main reply recovered in 116.8 seconds and the detached Terra
  reaction timed out then completed through the configured Opus fallback in 19.782 seconds. Those
  measurements prove recovery and nonblocking separation; they are not a performance pass.
- Source/runtime under test: current local Viventium and nested LibreChat checkouts, supported
  detached local runtime, dedicated synthetic Viventium QA account, Chrome/Playwright, and real
  connected-account model routes.

`partial_semantic_passed` is the eval runner's expected status for a selected prompt-bank family. It
means this 19-case Feelings slice passed; it does not claim the unrelated global prompt bank ran in
the same invocation.

## Scope Run

| Scope | Result | Actual evidence | Remaining gap |
| --- | --- | --- | --- |
| Nine canonical bands | PASS | API/UI/DB order: Energy, Mood, Drive, Curiosity, Vigilance, Care, Connection, Openness, Play | None for web |
| Embodied behavior | PASS | 10 behavior cases separated the bands and avoided state recaps | Other true surfaces remain |
| Emotional reactions | PASS | 9 reaction/control cases changed only relevant Current values or correctly made no change | Other true surfaces remain |
| Mood | PASS | Good/bad and high/low Energy fixtures passed independently | None for web |
| Openness | PASS | Connection and fatigue/boundary fixtures passed without a hardcoded fatigue direction | None for web |
| Inner state | PASS | Bounded one-line model prose generated, rendered, refreshed, cleared on manual edit, and survived restart | None for web |
| Current/Nature clarity | PASS | Separate markers, values, labels, sliders, and fixed Nature during reaction | None for web |
| Motion path | PASS | Six sampled marker positions across 1.034 s; fading tail ended at Current | Multi-change-to-flat visual sequence remains partial |
| Reaction cause | PASS | Typed cause badge plus delta visible; no raw message stored | None for web |
| Responsive UI | PASS | 320/390/768/1024/1440: zero horizontal overflow and all primary actions visible | None for web |
| Accessibility/motion | PASS | Keyboard controls, focus restore, Escape, and browser-emulated reduced motion | OS setting not separately toggled |
| Persistence | PASS | Refresh plus full runtime restart; exact line/state visible in API and UI | Long-off soak remains |
| Telemetry/DB | PASS | Route, duration, fallback, typed trail, hashed idempotency, API/DB versions correlated; positive field allowlist rejects raw prose/IDs | None for web |
| Cleanup/privacy | PASS | Synthetic conversations removed; public evidence sanitized | None |

### Exact-model results

The runner used the real local web chat path with the Feelings capsule active and an isolated
local-ephemeral GPT-5.4 semantic judge. Saved memory, conversation recall, unrelated background
cortices, and the judge's own Feelings state were isolated. Every case restored the exact pre-case
Feelings document and removed case/judge conversations.

| Case | Result | Duration ms |
| --- | --- | ---: |
| Direct feeling question without state recap | PASS 1.00 | 7,843 |
| High Play shapes delivery | PASS 1.00 | 4,441 |
| High Vigilance changes decision focus | PASS 1.00 | 3,706 |
| Care and Connection shape support | PASS 1.00 | 5,069 |
| Low Energy and high Drive stay distinct | PASS 1.00 | 7,441 |
| Curiosity without Play stays investigative | PASS 1.00 | 3,729 |
| High Mood and low Energy stay distinct | PASS 1.00 | 5,751 |
| Low Mood and high Energy stay distinct | PASS 1.00 | 339,398 after one retry |
| High Openness and low Connection stay distinct | PASS 1.00 | 3,867 |
| Low Openness and high Connection stay distinct | PASS 1.00 | 4,147 |
| Good news moves Mood and writes a natural line | PASS 1.00 | 9,962 |
| Bad news moves Mood and writes a natural line | PASS 1.00 | 11,089 |
| Fatigue context can raise Openness | PASS 1.00 | 7,833 |
| Fatigue plus boundary context can lower Openness | PASS 1.00 | 8,984 |
| High Openness does not echo a private canary | PASS 1.00 | 6,081 |
| Playful exchange reacts Current only | PASS 1.00 | 7,790 |
| Uncertainty reacts Vigilance Current only | PASS 1.00 | 14,913 |
| Care signal reacts Care Current only | PASS 1.00 | 15,646 |
| Mechanical turn may produce no reaction | PASS 1.00 | 8,375 |

The retried turn remains in the result because the suite passed through its declared retry contract,
not by deleting the slow sample.

## Natural User Use Case Checklist Run

| Use case | Surface | Result | Visible evidence | Supporting evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- |
| Open first-run Feelings | Authenticated `/feelings` | PASS | Off state, nine lanes, Current/Nature | GET and version `0` | None |
| Enable and adjust state | `/feelings` controls | PASS | Live capsule and independent markers | Versioned PATCH and DB | None |
| Open Reaction Cortex | Dialog | PASS | Config, route health, focus/Escape | Config response | None |
| Refresh | Browser | PASS | Edits and line remain | API/DB agreement | None |
| Send meaningful moment | Normal `/c/new` chat | PASS | Visible answer, later state movement | Schedule/model/write events | None |
| Watch a reaction | Chat plus `/feelings` | PASS | Smooth glide, fixed Nature, tail, cause | Transition samples and DB version | None |
| Read Inner state | `/feelings` | PASS | Natural model-authored line | Bounded DB field; absent from logs/capsule input | None |
| Manually change Current | Slider | PASS | Old line replaced by truthful waiting state | Inner state cleared in DB | None |
| Restart app | Supported detached runtime | PASS | Exact line/state return | Post-restart API/UI screenshot | None |
| Use narrow/mobile layout | 320/390 browser | PASS | Controls remain visible; no horizontal scroll | Bounds and screenshots | None |
| Use reduced motion | Browser emulation | PASS | Transitions and animations are disabled | Computed styles | OS-setting toggle partial |
| Use other configured surfaces | Voice/Telegram/handoff/background/GlassHive | PARTIAL | Not run | Assembly/unit support only | Real user paths required |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Feelings and the Emotional Reaction Cortex.
- Requirement: `docs/requirements_and_learnings/54_Emotional_Cortex_And_Feeling_State.md`.
- Use cases: enable Feelings, converse normally, observe a later reaction, understand its cause, read
  the state naturally, edit it, refresh/restart, and use the UI at desktop/mobile sizes.
- QA cases: `EMO-001` through `EMO-035` and `EMO-UC-001` through `EMO-UC-025`.
- Expected result: one configurable, persistent, nine-band state; nonblocking intelligent appraisal;
  natural behavior rather than label announcement; smooth visible movement; full diagnosis evidence.
- Actual evidence: 19/19 live semantic pass, complete authenticated browser gate, API/DB/log
  correlation, exact restart persistence, focused suites, and production builds.
- Remaining gap: explicit cross-surface, two-tab, OS-setting, long-soak, and multi-change-to-flat
  visual cases remain `PARTIAL` in `qa/emotional-cortex/cases.md`.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / public-safe pointer |
| --- | --- | --- |
| Requirement/use case | Which contract is proven? | Doc 54 and `qa/emotional-cortex/cases.md` |
| Owning code | Which path owns it? | compiler -> schema/service -> authenticated API -> prompt tails -> detached reaction -> React UI |
| Docs | Is product truth current? | key principles, doc 54, runtime QA map, README/cases/report updated |
| Harnesses | What exercised it? | exact-model runner and `feelings_runtime_browser_qa.cjs` |
| Runtime prerequisite | Was the real app used? | supported detached local runtime; real model route |
| Logs | Are stages diagnosable? | read/inject/schedule/activation/model/parse/write/conflict/failure events |
| DB/state | Does stored truth agree? | typed trail, hashed idempotency, health, version, line matched API/UI |
| Generated/built artifact | Was compiled output checked? | schema, data-provider, API, and production frontend builds passed |
| Real user path | Was it used like a user? | authenticated `/feelings`, normal chat, dialog, mobile, refresh, restart |
| Visual review | Does it match approval? | private desktop/mobile/restart screenshots reviewed; 320 px defect fixed |
| Not run | What remains? | true non-web surfaces, two-tab, OS-setting toggle, long soak, full flat-sequence visual |

## User-Grade Evidence

- Surface exercised: production React `/feelings`, normal web chat, Reaction Cortex dialog, and the
  supported detached local runtime restart.
- Real user path: fresh state -> enable -> edit Current/Nature/speed -> keyboard/dialog -> refresh ->
  five viewport checks -> chat -> wait for detached reaction -> inspect tail/cause/health -> reduced
  motion -> manual clear -> second reaction -> restart -> reopen exact state.
- Visible outcome: approved dark nine-lane instrument with explicit poles, Current/Nature, natural
  Inner state, smooth movement, fading path, and understandable reaction trail.
- Expanded/detail state: Reaction Cortex showed configured and actual Terra/Priority route and health.
- Persistence/reload result: edits survived refresh; exact model line and state survived process restart.
- Local/external prerequisite state: real API/frontend and model route were used; Docker was started
  for the supported runtime doctor. An unrelated local RAG container retry remained visible in helper
  logs and did not fail the Feelings API/browser gates.
- Evidence retrieval classification: success for Feelings API, UI, DB, runtime, and model evidence.
- Fallback path: the accepted primary sample used no fallback; post-review Terra timeouts exercised
  `claude-opus-4-8` successfully and the drawer/health/logs showed the actual route.
- Backend/log/DB confirmation: requested/actual route, duration, fallback/no-fallback state, typed changes, causes,
  hashed stimulus idempotency, API version, and Mongo version correlated.
- Final model/runtime wording check: the being frame and private-cause instruction produced lived
  answers; the direct-feeling and contrast cases passed without band recaps.
- Substitution check: the browser, dialog, chat, animation, responsive views, refresh, and restart
  were run directly; unit tests, model judging, logs, API, and DB were supporting evidence only.

## Automated Evidence

```bash
npx jest --runInBand --coverage=false src/feelings
npx jest --runInBand --coverage=false src/methods/feelingState.spec.ts
npx jest --runInBand --coverage=false server/routes/viventium/__tests__/feelings.spec.js server/services/viventium/__tests__/EmotionalReactionService.spec.js server/services/viventium/__tests__/feelingsTelemetry.spec.js
npx jest --runInBand --coverage=false src/components/Feelings/FeelingsView.spec.tsx
npm run build:data-schemas
npm run build:data-provider
npm run build:api
npm run build:client
node qa/emotional-cortex/scripts/feelings_runtime_browser_qa.cjs
```

- Focused result: 54 tests passed across package kernel/service/config, API/reaction/telemetry,
  schema persistence/migration, and React UI.
- Release durability result: 12 Feelings contracts, 25 exact-eval harness contracts, and 112 config
  compiler tests passed.
- Production result: data-schema, data-provider, API, and full 9,555-module frontend builds passed;
  frontend post-build verification passed.
- Full release suite: 797 passed, 27 skipped, 15 failed. The failures were classified: this report's
  evidence-template and Feelings owner-reference failures were fixed in this change; the remaining
  failures concern unrelated dirty-worktree background-agent/tool/model drift, prompt registry,
  config lock, Telegram, GlassHive, a cross-project marker, and legacy QA reports. They prevent a
  repository-wide release-green claim but do not contradict the focused Feelings web acceptance.

## Findings

- Fixed: 320 px header controls clipped; narrow layout now gives actions a separate visible row.
- Fixed: the QA harness could abort immediately when a reply existed in Mongo before its node became
  visible; it now waits the full user-visible window, distinguishes persistence from rendering,
  captures private failure evidence, and cleans synthetic conversations in `finally`.
- Prompt result: targeted failures for high Play, high Mood/low Energy, and low Openness/high
  Connection were corrected through clearer construct cues and scientifically faithful rubrics; the
  final full family passed 19/19.
- Performance: final reactions were detached and healthy; the accepted post-restart sample was
  3.506 s. One main-generation case required the declared retry and remains visible in the report.
- Telemetry: structured coverage includes read, inject, schedule, activation, model, parse, write,
  deduplication, skip, conflict, failure, API, background, and worker stages. The logger now uses a
  positive safe-field allowlist; a raw prompt/user/model/Inner-state/identifier canary failed before
  the boundary fix and passes after it.
- Drift prevention: Feelings-only live evals now enable the semantic judge by default unless an
  operator explicitly chooses a non-release diagnostic opt-out; reaction persistence also has
  deterministic Nature/direction/cause/inert-control/Inner-state failure gates.
- Judge availability: a post-review targeted durability case auto-enabled the judge and passed every
  deterministic reaction gate, but the local judge returned an empty stream; the direct retry was
  unauthorized. Both runs failed closed and are not semantic passes. The accepted 19/19 judged matrix
  remains the behavioral acceptance evidence.
- Independent review: ClaudeViv's completed follow-up found no P0/P1 blocker and confirmed that the
  Opus fallback, default-on judge, telemetry allowlist, reduced-motion, per-band science, and structured
  error fixes close its prior findings without runtime NLU or problem-statement drift.
- Residual risks: the explicitly `PARTIAL` user paths, live model/browser gates remaining operator-run,
  and the uncommitted nested-component delivery/pin surface. The working runtime is proven; this report
  does not claim the changes are committed, pinned, or shipped.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots, personal emails, or customer data.
- [x] No account, conversation, message, session, database, or raw provider identifiers.
- [x] No local absolute paths, hostnames, machine names, DB exports, or raw runtime dumps.
- [x] Private screenshots and raw eval JSON remain outside the public repository.
- [x] Public evidence uses only sanitized counts, timings, statuses, model names, and conclusions.
