# Feelings Embodiment, Motion, and Reaction QA
<!-- qa-evidence-exempt: Historical local QA format retained without retroactively inventing evidence; current release acceptance is recorded separately. -->

Date: 2026-07-09

Status: production web UI/runtime accepted; final live Prompt Workbench matrix passed 10/10.
Cross-surface voice, Telegram, handoff, and GlassHive user runs remain partial.

## Acceptance map

| Requirement | User path exercised | Actual evidence | Status |
| --- | --- | --- | --- |
| Feel rather than announce injected labels | Prompt Workbench, exact main agent, direct “How are you feeling?” fixture | The adjective-based capsule reproduced the reported label echo. The revised private action-tendency capsule produced a natural relational answer without quoting any injected UI scale word or exposing prompt mechanics. All six embodiment cases passed independent semantic grading in the first complete matrix. | PASS |
| Reaction changes Current, never Nature | Authenticated web chat stimulus beside `/feelings`, then API/DB readback | Three typed band changes committed; all Nature values stayed fixed. The playful example produced `playful_exchange`. | PASS |
| Reaction arrives as motion, not flicker | Open `/feelings` while the detached reaction commits | Current marker positions were sampled at four distinct points during the 1,050 ms eased transition, followed by the arrival pulse. | PASS |
| Current and Nature are visually distinct | Desktop and 390 px browser views, lane and inspector interaction | Every lane shows explicit NOW and NATURE values, solid colored Current, amber dashed/diamond Nature, a tether, and low/high poles. | PASS |
| Trail explains why a band moved | Expand the live Reaction trail after a synthetic turn | Entry showed human-readable typed cause, band, before/after values, direction, strength, and source; raw message text was absent. | PASS |
| Direct manipulation works | Pointer drag and keyboard interaction on Current/Nature markers | Pointer and arrow-key changes passed as a user; Shift+arrow, Home, and End are also exposed by the accessible slider contract and covered in component logic. | PASS |
| No hidden reaction failures | Correlate browser, structured logs, reaction health, and DB | Schedule, activation, model attempt/retry, parse issues, typed cause counts, atomic write/conflict, duration, and terminal health are observable without raw stimulus text. | PASS |
| Eval fixtures leave no residue | Run/timeout/retry through Prompt Workbench | QA auth spans the run; unrelated memory/recall/background work is isolated; the judge cannot inherit Feelings; all 20 synthetic conversations and 40 messages were removed; the raw Feelings document was restored exactly in `finally`. | PASS |

## Real browser evidence

- Exact detached route: GPT-5.6 Terra, Responses API, reasoning `none`, Priority/Fast, activation
  `always`, agent scope `all_agents`, with declared Anthropic Haiku fallback and an 8-second
  per-route bound.
- Final settled-stack visible reply: 9.483 seconds; the detached reaction completed in 2.348
  seconds and did not delay that visible reply.
- The final animation capture recorded six rendered marker positions across 1.032 seconds. A prior
  pass recorded the same transition across 1.024 seconds, proving the probe is repeatable after its
  pre-stimulus transition-event fix.
- Refresh and a full runtime stop/start preserved Current/Nature/trail agreement with the database.
- The final authenticated browser run passed 27/27 checks, including default/off, enable, direct
  Current/Nature interaction, keyboard control, drawer route display, refresh, mobile layout,
  visible reply, detached reaction, fixed Nature, typed cause, persisted/visible actual route and
  service tier, health, Mongo confirmation, and synthetic-chat cleanup.
- Desktop and 390 px layouts, inspector, trail, drawer, console, and network state were exercised.
- No browser console error or failed product request occurred in the passing run.

Evidence is stored only in the private local QA root because it contains an authenticated session.
No account identity, local path, raw chat, credential, or private screenshot is published here.

## Prompt Workbench findings and corrections

The user-level matrix attempts were intentionally retained as diagnostic run records. They found:

1. the adjective capsule still caused exact label copying;
2. a 15-minute local QA token expired during a ten-case run;
3. unrelated background cortices competed with the preview models and produced provider 429s;
4. saved memory/recall could leak an older synthetic eval scenario into a new answer;
5. the semantic judge inherited Feelings and scheduled reactions of its own;
6. a fixed orchestration timeout could kill the runner before its restore/cleanup path;
7. reaction timeouts did not receive the same single recovery attempt as invalid JSON.

The first completed ten-case matrix retained this evidence rather than hiding it: all ten main turns
and independent judgments completed, all six embodiment cases and the mechanical control passed,
but three reaction-persistence cases failed because Terra exhausted both detached attempts under the
sustained suite. Nature remained unchanged and the database was restored exactly. Result: **7/10**.

The next completed matrix produced **6/10** and exposed two distinct integration/eval defects. Three
reaction cases proved that direct `executeCortex` callers bypassed the fallback used by activated
batch cortices. The remaining failure was a false-negative rubric that treated one ordinary use of
“curious” as a mechanical state recital. The shared direct executor now owns validated fallback for
every caller, and the rubric now fails actual multi-label/state-report behavior rather than natural
language.

Corrections now in the reusable harness/runtime:

- private action-tendency prompt phrases are distinct from the UI scale adjectives;
- temporary structured eval isolation disables only saved memory, recall, and unrelated background
  cortices for the target case, while leaving Feelings active;
- the independent judge additionally disables Feelings;
- main turns retry one transient provider/stream failure with a cooldown;
- reaction appraisal retries one transient timeout/rate-limit/empty result while remaining detached;
- direct and activated cortex execution now share the same validated fallback executor and prevent
  a second outer fallback after recovery;
- the approved Terra/Fast primary now has a declared Haiku recovery route; the configured primary,
  configured fallback, actual completing route, fallback use, and primary error class are visible in
  the drawer/health/telemetry;
- orchestration budget scales to one hour for ten exact-model cases;
- local QA auth spans that budget;
- exact raw Feelings state and synthetic case/judge conversations are restored/removed.

## Automated verification

- LibreChat backend Feelings/reaction/fallback/client focused suites: 6 suites passed.
- API package changed-file suite: 198 passed.
- Data-schema suite: 387 passed, 3 skipped; FeelingState schema/method tests passed.
- Feelings UI: 5 passed.
- Parent compiler/Feelings/Workbench contracts: 190 passed, 20 skipped after loading their declared
  optional test dependencies.
- Data schemas, data provider, API package, client package, and production frontend builds passed;
  the production frontend transformed 9,555 modules and completed post-build verification.

## Remaining release scope

The production web implementation and its behavioral matrix are accepted. Voice, Telegram, handoff,
GlassHive worker, two-tab browser conflict, reduced-motion OS toggle, and long-off soak remain
separate `PARTIAL` cross-surface gates and are not represented as passed by this report.

## Final matrix result

Final Workbench run `20260710T025741Z`: **10/10 semantic pass**, 10/10 main turns completed, 10/10
independent judgments completed, zero main-turn retries, no duplicate response hashes, and no
unresolved async quality failures.

- Six embodiment cases passed, including the direct “How are you feeling?” case without a mechanical
  UI-state recital.
- Playful, uncertainty, and care cases changed only Current with typed causes; Nature delta was zero
  for every band. Reaction health recorded Terra as the actual route in 1.459–4.578 seconds.
- The mechanical control completed in 1.027 seconds with zero band operations.
- Every case reported `restored_exact`; aggregate cleanup removed 20 conversations and 40 messages.
- The final run did not need fallback because Terra was healthy. The shared direct fallback path is
  separately covered by the real service executor test, and the live drawer/config/telemetry expose
  primary, fallback, actual route and service tier, fallback use, and primary error class.
