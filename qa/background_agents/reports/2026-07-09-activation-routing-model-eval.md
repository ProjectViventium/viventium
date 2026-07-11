# Activation Routing, Conscious/Subconscious Browser QA
<!-- qa-evidence-exempt: Historical local QA format retained without retroactively inventing evidence; current release acceptance is recorded separately. -->

Date: 2026-07-09 local / 2026-07-10 UTC

## Verdict

`PASS` for activation semantics and the browser/reload path in `ACT-36`.
`PASS` for `ACT-37`, including a deliberate real-browser interruption after visible/persisted active
status, supported local stop/start, changed API process, same-conversation reload, DB-backed stale
recovery, expanded terminal detail, and no misleading generation placeholder.
`PASS` for the post-quota whole-turn browser path. The earlier approximately 84-100 second conscious
stall was operator-confirmed exhaustion of the account's five-hour Codex/GPT subscription usage
window, not a Viventium activation or provider-rate-limit defect. No speculative first-token deadline
was added. After the account window recovered, a fresh browser turn rendered a 1,127-character
conscious answer, completed both intended cortices, persisted/reloaded cleanly, and produced zero
console, request, or critical HTTP errors.

`PASS` for the restored Red Team comfort-avoidance scope on the dedicated QA Test Viventium
account. A final implicit prompt did not name any cortex, yet visibly activated and completed Red
Team and Confirmation Bias, preserved a 3,559-character parent answer and both expanded cards after
reload, and matched terminal Mongo state with zero stored cortex, console, request, or critical HTTP
errors. This was run only after a protected source/live A/B/C review and a one-agent/one-activation-
prompt sync; the post-sync reviewed agent and adjacent-config drift counts were both zero.

`PASS` for current prompt semantics and `PARTIAL` for full-gate provider availability. The final
63-case bank produced zero semantic false positives, false negatives, or required/forbidden
inconsistencies; all 1,381 completed decisions passed. Five of 1,386 non-required decisions were
unavailable after the shared 2-second activation budget was exhausted, so the current release
availability gate remains open. Four optional allowed-activation overlaps varied across repetitions
and are reported separately rather than mislabeled as semantic errors.

This is local acceptance evidence, not a release/shipping claim. The parent and nested repositories
contain other uncommitted work; a local data-provider package rebuild verified schema behavior, but
no component pin, shippable release artifact, commit, push, or fresh-clone proof was produced.

## What changed

- Replaced the retiring Groq Scout Phase A default with `groq / qwen/qwen3.6-27b` across source,
  compiler, runtime defaults, model inventory, and live built-in agent activation config.
- Moved all 11 activation prompts to registry-owned `promptRef` values and added compact positive
  gates, negative precedence, sibling boundaries, and contrastive examples.
- Expanded the public-safe activation family to 63 cases that evaluate all 11 classifier targets through
  the exact `BackgroundCortexService.checkCortexActivation` path.
- Added a dedicated Prompt Workbench dispatch path with preview/live selection, case and cortex
  filters, repetition, private raw evidence, and public-safe aggregate metrics.
- Added Qwen controls in runtime: no reasoning, hidden reasoning, deterministic seed, and JSON-object
  output. Provider/model removal and JSON-validation failures can use configured fallbacks.
- Restored the source/live Phase A fallback chain: xAI, OpenAI, then Anthropic.
- Enforced each Phase A attempt deadline with a local promise race as well as `AbortSignal`, so a
  non-cooperative provider cannot consume the whole global budget and prevent fallback execution.
- Aligned the nested LibreChat config schema and runtime resolver with source-owned activation-policy
  `promptRef` objects; raw source config now validates and resolves without `[object Object]` text.
- Added coalesced incremental Phase B persistence. Visible status is now written before all
  background work finishes, while the final snapshot drains older writes so stale state cannot win.
- Enabled the existing non-blocking late Phase A recovery path with a compiled 4,000 ms budget when
  the fast pass returns zero activations after a timeout. It reuses the canonical prompts, provider
  fallbacks, ownership gates, Phase B, and persistence path without extending the conscious wait.
- Added a local-only ACT-37 real browser/Mongo/runtime-restart harness with guarded JWT/restart opt-in,
  public-safe evidence, detached-launcher health verification, normal stale-recovery timing, and
  explainable diagnostic classification.
- Reused the newer local-QA access-token fallback in the older visible-card browser harness so a
  startup refresh-token rotation race cannot falsely block local QA. The fallback remains guarded by
  explicit local JWT opt-in, production/CI exclusion, short-lived signed access, and session cleanup;
  production authentication was not changed.
- Repaired the latest-turn browser case: its positive setup now supplies the concrete plan required
  by the Red Team contract and waits like a user for the prior response's send control to recover.

No runtime keyword/regex classifier, prompt-text branch, agent-name branch, or broader specialist
enablement was introduced.

## Why Qwen 3.6

Groq announced that Scout shuts down on July 17, 2026 and recommends migration to newer models.
Qwen 3.6 is a preview model, so it is accepted as the current measured primary—not as a permanent
unconditional dependency. The mitigation is a source-owned fallback chain plus a repeatable eval
gate. Sources: [Groq deprecations](https://console.groq.com/docs/deprecations),
[Groq Qwen 3.6](https://console.groq.com/docs/model/qwen/qwen3.6-27b), and
[Groq prompting guidance](https://console.groq.com/docs/prompting).

The corpus uses synthetic conversation shapes inspired by the public
[WildChat paper](https://arxiv.org/abs/2405.01470) and
[LMSYS-Chat-1M paper](https://arxiv.org/abs/2309.11998). No real conversation text, private prompt,
or account data was copied into the repository.

## Model comparison

| Route | Evaluated slice | Result | Decision |
| --- | ---: | --- | --- |
| Scout, old prompts | 220 | 181 pass; 39 false positives; 26.4% activation precision; p50/p95 425/801 ms | Reject: retiring and materially leakier |
| Qwen 3.6, old prompts | 220 | 203 pass; 17 false positives; p50/p95 409/564 ms | Better model, prompts still weak |
| Qwen 3.6, repaired prompts | 220 | 220/220; p50/p95 370/471 ms | Promote to full gate |
| GPT-OSS 120B, repaired prompts | 220 | 191 completed; 186 pass; 5 FP; 3 FN; 28 JSON validation failures; p50/p95 403/878 ms | Reject as primary |
| Qwen 3.6, current expanded full two-pass | 1,386 | 1,381 completed and passed; 0 FP/FN/required-or-forbidden inconsistency; 5 unavailable | Accept semantics; provider availability remains PARTIAL |

Strict GPT-OSS JSON Schema was tested because Groq supports structured outputs, but the real runtime
trial was less reliable than JSON-object mode. Sources:
[Groq structured outputs](https://console.groq.com/docs/structured-outputs),
[Groq GPT-OSS 120B](https://console.groq.com/docs/model/openai/gpt-oss-120b), and
[OpenAI GPT-OSS model card](https://openai.com/index/gpt-oss-model-card/).

## Final exact-runtime metrics

| Metric | Result |
| --- | ---: |
| Cases / targets / repetitions | 63 / 11 / 2 |
| Total decisions | 1,386 |
| Completed decisions | 1,381 (99.64%) |
| Completed-call semantic required recall | 100% |
| End-to-end required recall | 100% |
| Activation precision | 100% |
| Semantic false positives / false negatives | 0 / 0 |
| Required/forbidden semantic inconsistencies | 0 |
| Optional allowed-activation variance | 4 |
| Provider-attempt timeout/error rows / unavailable decisions / availability flaps | 223 / 5 / 5 |
| Latency p50 / p95 / max | 287 / 1,457 / 1,775 ms |

The semantic gate is green for every completed decision, but the availability gate is not: five rows
exhausted the shared 2-second activation budget before a provider returned a decision. They remain
failures, not correct negatives. A prior 59-case run completed 1,298/1,298 with only 19 recovered
provider-attempt errors; the current 63-case run exposed materially worse provider latency after
repeated load. The final fallback hardening proved that a primary which ignores cancellation now
yields to xAI inside the same budget; the owning service suite passes that non-cooperative-provider
regression. Direct Qwen and xAI probes for the previously discovered sibling leaks passed 40/40,
the final Pattern-vs-Confirmation xAI regression passed 2/2, and the four new
comfort/self-care/changed-goal cases passed 88/88 across all cortices. A
separate invalid-primary probe also proved `MODEL_NOT_FOUND` falls through to xAI and correctly
activates Red Team in 763 ms.

## Real QA-account browser and DB evidence

### Positive cards and interruption-safe persistence — PASS

- Used the local synthetic QA account through the supported local JWT/browser harness and the live
  Mongo-backed runtime.
- Red Team and Confirmation Bias appeared visibly by name.
- Expanded terminal state and "why this ran" detail were visible.
- The conscious answer remained visible before and after reload.
- Mongo stored exactly two successful terminal cortex parts and no cortex error.
- Browser console errors, failed requests, and critical HTTP errors were all zero.
- Live activation config matched source; all required activation fallbacks were present.
- The post-quota rerun repeated this path with a 1,127-character conscious answer and no visible or
  persisted cortex error.
- The final implicit comfort-avoidance run used the dedicated QA Test Viventium account, not the
  canonical agent-owner account. It completed Red Team and Confirmation Bias through the UI and DB,
  preserved a 3,559-character conscious answer after reload, and recorded zero browser/network
  errors. Backend logs additionally show both OpenAI Phase B attempts classified as rate-limited and
  both configured Anthropic fallbacks completing successfully; the final execution summary was
  three visible insights and zero errors.
- After the final v3 sibling-boundary sync, the same implicit browser case passed again with a
  353-character conscious answer, both required cards complete and persistent after reload, zero
  stored cortex errors, and zero console/request/critical HTTP errors.
- After rebuilding the local config package and restarting the current checkout, the final
  helper-managed run passed with a 447-character conscious answer, visible and reloaded Red Team and
  Confirmation Bias cards, terminal/"why this ran" detail, matching complete Mongo parts, and zero
  console/request/critical HTTP errors. A preceding run launched while foreground and helper
  lifecycle control overlapped was rejected: Mongo completed its synthetic turn, but the browser did
  not observe it before timeout. The clean acceptance used the supported helper as the sole stack
  owner.
- No DB credential copy was performed: the intended QA account already held the freshest healthy
  OpenAI and Anthropic connected-account records. A preliminary mis-targeted run against a different
  local account correctly surfaced rejected fallback credentials; it was not accepted as QA evidence.

### Deliberate interruption/restart recovery — PASS

- A natural Red Team request produced a visible active card and a persisted active cortex part.
- The harness used supported `bin/viventium stop` / `start`; the API process fingerprint changed.
- The same conversation and active Red Team state survived restart and were visible immediately.
- The normal 180-second execution timeout plus 60-second grace recovered the stale active row to
  terminal `error` with `stale_cortex_startup_recovery` and `unfinished=false`.
- Reload preserved the terminal card; expanded detail was visible and no `Generation in progress`
  placeholder remained.
- Raw reload diagnostics retained three expected local-JWT bootstrap 401 console messages and two
  401 HTTP responses; unexpected console/request/HTTP error counts were zero. See
  [the dedicated ACT-37 report](2026-07-09-interruption-restart-browser-qa.md).

### Latest-user negative control — PASS

- A concrete synthetic plan activated Red Team and Confirmation Bias on the setup turn.
- The next output-only turn activated 0/11 in 817 ms; fallback retry also remained 0/11 in 800 ms.
- Exactly one direct assistant response was stored.
- No cortex part and no visible Phase B child attached to the control turn.
- Exact `TEST_OK` remained visible after reload.

The earlier vague setup phrase was correctly rejected by the strengthened Red Team gate. The QA
harness—not the product prompt—was misaligned and was repaired to provide a concrete plan.

### Prompt Workbench — PASS

- The browser listed `background_activation_routing`; the final expanded bank contains 63 cases.
- Preview completed without model calls.
- The request returned HTTP 200 and recent run history reloaded.
- Source/live sync reported a match.
- Browser console errors and warnings were zero.

## Persistence proof

`AgentClient` now uses one per-turn persistence coordinator:

1. The first status snapshot begins persistence immediately.
2. Updates arriving behind an in-flight write coalesce to the latest full snapshot.
3. A failed write is reported and does not poison later writes.
4. The completion pipeline drains incremental writes before writing the authoritative final state.

The complete `client.test.js` suite passed 138/138, including first-write, coalescing, recovery, and
final-ordering cases. The post-change browser reload/Mongo check and the deliberate supported
stop/start acceptance both passed.

## Remaining issues

1. **Qwen preview/provider capacity — release blocker, not a semantic blocker.** The current
   1,386-decision run had 223 provider-attempt errors and five all-provider unavailable decisions
   even at concurrency 2. Completed-call semantics remained perfect, and direct Qwen/xAI probes
   passed. The runtime now advances even when a provider ignores cancellation, but simultaneous
   Qwen and xAI latency can still exhaust the global budget before later routes can answer. The full
   release gate is `PARTIAL` until a clean complete run succeeds; keep the fallback chain and add
   controlled concurrency/rate-budget testing before multi-user claims.
2. **Late-pass provenance — acceptance gap.** Code/config/unit evidence proves the 4,000 ms pass is
   zero-activation-gated and non-blocking, and browser evidence proves normal activation plus crash
   recovery. A browser case that deliberately makes the fast pass miss and then attributes the
   rendered/persisted card to `late_recovery` is still needed before claiming late-pass efficacy,
   rather than only mechanism correctness.
3. **Exhausted-subscription UX — environment gap.** The operator-confirmed five-hour account window
   is healthy now, so the actual exhausted state cannot be replayed. Deterministic ACT-33 coverage
   proves fallback retry and public provider-class wording, while the post-window browser path is
   clean. The final QA-account run also proves real Phase B `provider_rate_limited` -> Anthropic
   fallback recovery for Red Team and Confirmation Bias, but an actually exhausted main-agent
   subscription window remains unproven. Do not add a generic first-token timeout in its place.
4. **Repository-wide stale tests outside this change — review needed.** Seven broader productivity
   source tests currently expect an older execution-model/tool inventory and five generic exact-model
   harness tests expect stale formatting/runner contracts. Activation-focused tests pass; these
   existing failures must be reconciled by their owning GPT-5.6/tool/runtime work before a clean
   repository-wide release claim.
5. **Shipping state — not ready.** Source/live activation config matches, but dirty parent/nested
   repositories and unverified component pins/artifacts mean this local result is not yet shipped.

## ClaudeViv second opinion

The requested review-only ClaudeViv pass inspected the Key Principles, prompts, exact-runtime
runner, runtime model controls, persistence code/tests, dirty repo boundaries, and QA report.

- Confirmed: Qwen should replace Scout now with preview/fallback/eval caveats.
- Confirmed: registry prompt changes align with Key Principles and add no forbidden runtime NLU.
- Partially confirmed: semantic ACT-36 acceptance is strong; provider availability is not yet a
  multi-user or release-tier pass.
- Confirmed at review time: incremental ordering was correct; explicit process-kill/restart evidence
  was still needed. That gap is now closed by the dedicated ACT-37 pass above.
- Confirmed: browser/DB/Workbench evidence supports local acceptance, not release readiness.
- Partially confirmed at review time: the conscious stall was separate. Its proposed first-token
  deadline is superseded by the operator-confirmed five-hour subscription-window cause and the clean
  post-window browser rerun; adding a product timeout for that account condition would be misaligned.

ClaudeViv also flagged the unrelated Feelings/GlassHive/minimal-context work present in the same dirty
tree. That work was not evaluated by this report and must not ride on the activation evidence. Its
fixture concern was checked: the latest-turn harness change only made the positive setup concrete
and increased the wait for a still-running prior response; the strict 0/11, zero-cortex-part,
zero-Phase-B-child, exact-answer, and reload assertions were unchanged and passed in the browser.

The final max-effort ClaudeViv follow-up directly inspected the completed code and evidence. It
confirmed Qwen selection, the non-blocking late-pass mechanism, ACT-37 local acceptance, the
no-runtime-NLU posture, and that tests were strengthened rather than weakened. It identified three
additive residuals: late-pass browser provenance, live exhausted-subscription fallback/blocker UX,
and two lifestyle-avoidance Red Team triggers that had been dropped. The third was a real regression
against `29_Red_Team_Cortex.md`; the trigger was restored as a narrow material-commitment/goal-conflict
gate with a recovery/rest negative control. Its final delta review found no blocker and recommended
two more implicit comfort domains, dedicated changed-goal/self-care negatives, and exact doc wording
for the narrowed plan gate. Those additions were applied. The four new cases passed 88/88; all
discovered Qwen/xAI semantic pairings passed after sibling-boundary repair; and the current full run
has zero semantic FP/FN/required-or-forbidden inconsistency but five unavailable decisions. Four
optional allowed overlaps varied and are reported separately. Late-path provenance and actual
main-account exhaustion remain explicitly tracked because current evidence cannot honestly close
them without a forced late-path run or an actually exhausted account.

A final ClaudeViv reliability-delta review found no blocker. It independently confirmed the local
deadline race, late-settlement/timer cleanup, promptRef schema/runtime boundary, optional-variance
methodology, no-runtime-NLU posture, and the semantic-PASS/availability-PARTIAL conclusion. It
sharpened the availability RCA: within a 2-second global budget, the flat 900 ms attempt caps make
Qwen plus xAI the only realistically reachable routes when both are slow, while OpenAI/Anthropic are
best-effort tail fallbacks. It also noted that timeout-aware primary backoff would change the current
deliberate always-probe-primary policy. Adaptive budgeting/backoff or right-sizing the declared
chain therefore remains an explicit product latency/cost/reliability decision for review, not a
silent local change. ClaudeViv also confirmed that shared eval files contain unrelated Feelings work;
no commit or staging was performed, so that user-owned work was not split, reverted, or swept into a
shipping claim.

## Automated verification

- Final focused activation/browser/compiler/governance selection: 161 passed.
- Prompt Workbench: 87 passed.
- Final affected nested `AgentClient`, activation policy/service, runtime-model, and seed selection:
  261 passed.
- Nested data-provider config schema suite: 59 passed.
- Real browser positive: PASS.
- Real browser latest-turn positive-to-negative control: PASS.
- Real browser deliberate interruption/restart/stale recovery: PASS.
- Post-quota conscious + Red Team + Confirmation Bias browser/reload path: PASS.
- Real browser implicit Red Team comfort-avoidance + execution fallback + reload path: PASS.
- Live source-vs-agent DB diff after sync: 0.
- Diff whitespace check: PASS.
- Broader parent audit: 64 passed and 12 pre-existing stale assertions failed (seven obsolete
  productivity/model/tool expectations and five obsolete generic exact-model formatting contracts);
  those failures are outside this activation/recovery slice and are listed under Remaining issues.

## Not run / claim boundaries

- No voice/audio, Telegram, or productivity connected-account tool execution was required or run for
  this browser activation classifier change.
- No clean-clone install, public build, component-pin update, commit, push, or release artifact QA
  was performed.
- The QA account was authenticated locally; no credentials or raw account data were added to the
  repository or public report.
