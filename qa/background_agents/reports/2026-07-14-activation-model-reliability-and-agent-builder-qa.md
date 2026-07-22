# Activation Model Reliability And Agent Builder QA — 2026-07-14

## Summary

- Result: **PASS** for the exact-runtime classifier gate, Prompt Workbench path, Agent Builder
  selector truthfulness, reload persistence, and deterministic fallback recovery; **PARTIAL** for
  external-channel delivery, which was not run with an isolated synthetic channel account.
- Build/source under test: current public source working tree and nested LibreChat working tree.
- Runtime/artifact under test: active local Viventium runtime launched from the current checkout.
- Environment: isolated local browser QA, Prompt Workbench, and exact-runtime evals.
- Tester: Codex through browser user paths and exact-runtime evals.
- Related change: complete built-in activation routes, dynamic Agent Builder model choices, bounded
  provider fallback, and detached late recovery.

This is local acceptance evidence, not a clean-install, multi-user capacity, release, or shipping
claim.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `ACT-36` | PASS | 693/693 exact-runtime decisions | Zero unavailable, false-positive, or false-negative decisions |
| `ACT-38` | PASS | 201 recovered attempt errors in the deterministic exact-runtime eval | Attempt and late bounds did not extend the simulated conscious reply wait |
| `ACT-42` | PASS | 11/11 Agent Builder selectors before/after reload | Three saved fallbacks per agent; zero mutation |
| `ACT-43` | PASS | Typed malformed/schema regression | Invalid output retries fallback and cannot become a coerced decision |
| `PW-034` | PASS | Browser preview and 11/11 live subset | History survived reload; zero browser errors |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `BACKGROUND-UC-010` | Expand every built-in Activation Detection selector and reload | Real Agent Builder browser UI | PASS | All 11 saved Qwen routes remained visible and selected | Persisted routes, three fallbacks each, before/after hashes, source/live diff zero | None for this path |
| `PW-UC-010` | Preview and run activation evals, then reload history | Real Prompt Workbench browser UI | PASS | Preview code 0, 11/11 selected decisions, saved run after reload | Workbench ledger, guarded QA context, runtime fallbacks | None for this path |
| Fallback recovery | Submit synthetic input while primary classifiers encounter tail latency | Deterministic exact-runtime harness | PASS | The simulated conscious result completed without waiting for late detection | Bounded primary attempts, fallback recovery, and complete detector results | External-channel delivery NOT RUN |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Background Activation Detection reliability and Agent Builder route truthfulness.
- Requirement: `02_Background_Agents.md`, `49_Prompt_Architecture_and_Token_Efficiency.md`, and the
  nested expected-behavior contract.
- Use case: inspect every saved route, run the real classifier bank, reload, and survive provider
  tail latency without blocking the conscious answer.
- QA case: `ACT-36`, `ACT-38`, `ACT-42`, `ACT-43`, `BACKGROUND-UC-010`, and `PW-034`.
- Expected result: all classifiers are configured, selectors tell the truth, fallbacks recover tails,
  and no runtime text heuristic decides activation.
- Actual evidence: 693/693 exact-runtime pass, 11/11 selector/reload pass, 11/11 Workbench subset,
  zero source/live drift, and deterministic fallback recovery.
- Remaining gap or fix: repeat under release-load conditions and force Anthropic/OpenAI on a real UI
  path before broader provider-capacity claims.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is proven? | Background Agent and prompt-architecture docs; `ACT-36/38/42/43`, `BACKGROUND-UC-010`, `PW-034` |
| Code owning path | Which code path owns the behavior? | Config/compiler -> source-owned agent routes -> activation runtime -> Agent Builder -> fallback/late telemetry |
| Docs and nested docs/repos | Which docs define expected behavior? | Root Background Agent/Prompt Architecture docs and nested `EXPECTED_BEHAVIOR.md` |
| Scripts or harnesses | Which harnesses exercised it? | Exact-runtime activation runner, Agent Builder browser harness, Prompt Workbench browser harness |
| Local/external prerequisite state | Which dependencies were proven? | Isolated API/web/Workbench runtime and configured model routes |
| Logs | Which logs confirm the result? | Sanitized attempt-timeout, fallback-success, late-completion, and no-unavailable summaries |
| DB/state/persistence | Which state confirms it? | 11 persisted routes/fallback bags, source/live diff zero, before/after agent hashes |
| Generated/shipped artifact | Which generated artifact was inspected? | Compiled runtime values and active source/live config; clean-install artifact not claimed |
| Real user path | Which path was used like a user? | Isolated Agent Builder and Prompt Workbench browser flows |
| Visual/UX comparison | Did visible UI agree with state? | All selectors were nonblank/matched after reload; Workbench run/history matched backend state |
| Not run / blocked | Which surface was not run? | External-channel delivery, clean install, multi-user load, and deliberately forced provider-specific UI fallback remain PARTIAL |

Supporting evidence cannot replace required user-path evidence; the browser paths above were run
directly, while the external-channel path remains NOT RUN.

## User-Grade Evidence

- Surface exercised: isolated Agent Builder browser and Prompt Workbench browser.
- Real user path: expanded all 11 activation panels, searched a discovered route, reloaded, previewed
  and ran the eval subset, then reloaded history.
- Visible outcome: every saved route was nonblank and stable; Workbench showed successful results.
- Expanded/detail state: each Activation Detection drawer showed its selected provider/model and
  three fallbacks; Workbench run detail showed completed cases.
- Persistence/reload result: 11/11 selectors and Workbench run history remained correct after reload;
  agent hashes did not change.
- Local/external prerequisite state: API, web, Workbench, and the eval model routes were available.
- Backend/log/DB confirmation: source/live config diff was zero; all 693 decisions completed; live
  logs recorded two primary timeouts, xAI recovery, and complete late detection.
- Final model/runtime wording check: browser-visible results did not expose classifier plumbing.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

Expected outcome:

- all 11 built-in Background Agents have a complete activation route
- the saved route remains visible and selected in Agent Builder
- options come from the runtime catalog rather than a fixed provider/model menu
- Qwen is the default fast route; configured fallbacks recover provider tails without changing
  activation semantics
- late recovery is detached from the conscious answer
- no runtime phrase, keyword, agent-name, or provider-name intent heuristic is introduced

## User-Grade Results

| Surface / case | Result | Actual evidence |
| --- | --- | --- |
| Agent Builder initial view | PASS | 11/11 expanded activation selectors matched persisted provider/model state; no blank saved routes |
| Agent Builder reload | PASS | 11/11 routes remained selected after reload; every agent retained three ordered fallbacks |
| Runtime model choices | PASS | 160 selectable routes across 11 providers were available; a discovered alternative was searchable/selectable |
| Mutation safety | PASS | Before/after agent hashes matched; inspecting and reloading did not alter prompts, tools, models, or activation config |
| Prompt Workbench browser path | PASS | Preview returned code 0; live selected-family run completed 11/11; run history survived reload; zero browser errors |
| External-message recovery | NOT RUN | No isolated synthetic channel account was available; deterministic recovery is covered by `ACT-38` but is not a substitute for channel delivery |

The Agent Builder run used an isolated QA account. No personal or pre-existing external-channel
account was used for public evidence.

## Exact-Runtime Eval

The final run executed the current 63-case synthetic activation bank against every one of the 11
classifier targets through the production activation decision function, with configured fallbacks
enabled.

| Metric | Result |
| --- | ---: |
| Cases / targets / repetitions | 63 / 11 / 1 |
| Total decisions | 693 |
| Completed and semantically passed | 693 / 693 |
| Unavailable decisions | 0 |
| Required recall | 100% |
| Activation precision | 100% |
| False positives / false negatives | 0 / 0 |
| Required/forbidden inconsistencies | 0 |
| Provider-attempt timeout/error rows recovered | 201 |
| Latency p50 / p95 / max | 735 / 2,206 / 2,730 ms |

The 201 attempt-level errors are not hidden successes: they show that provider tail behavior was
actually exercised. Every affected decision recovered through the configured route chain; no case
was silently converted into a negative result.

## Source, Runtime, And Persistence Evidence

- Source-owned built-ins: all 11 use `groq / qwen/qwen3.6-27b` as primary.
- Ordered fallbacks: xAI, Anthropic Haiku, then OpenAI GPT-5.4.
- Attempt bounds: 1,600 ms primary and 2,500 ms fallback, configurable through public runtime
  config.
- Detached late-recovery bound: 6,000 ms; it does not extend the conscious answer wait.
- Source-to-live agent comparison: 13 agents inspected, zero live/source differences.
- Adjacent LibreChat config comparison: zero differences.
- Agent Builder reload and before/after hashes confirmed persistence without incidental mutation.

## Automated Evidence

```bash
node qa/background_agents/evals/run-activation-model-evals.cjs --run-live --with-fallbacks --repetitions=1 --concurrency=1
node qa/background_agents/evals/run-agent-builder-activation-browser-qa.cjs
node qa/prompt-workbench/scripts/live-evals-browser-qa.cjs
uv run --with pytest --with pyyaml --with jsonschema --with pydantic --with fastapi --with httpx --with python-multipart --with croniter python -m pytest tests/release/test_no_runtime_nlu.py tests/release/test_background_agent_governance_contract.py tests/release/test_prompt_architecture_eval_harness.py tests/release/test_prompt_registry.py tests/release/test_config_compiler.py tests/release/test_prompt_workbench.py -q
```

- Prompt Workbench backend: **114 passed**.
- Prompt-frame telemetry regression: **13 passed**.
- Final combined activation-policy, voice-surface, and Feelings-telemetry rerun: **123 passed**.
- Final affected release-contract rerun: **211 passed**.
- Final activation-policy service regression: **40 passed**, including typed malformed/schema-
  invalid fallback and terminal-unavailability behavior.
- Agent Builder activation-option unit checks: **3 passed**.
- Final Feelings UI plus Agent Builder activation-selector rerun: **10 passed**.
- Agent Builder browser harness: **11/11 initial + 11/11 reload passed**.
- Activation Workbench browser subset: **11/11 passed**, preview code 0, reload preserved history.
- Full exact-runtime classifier gate: **693/693 passed**.
- LibreChat client and Prompt Workbench production builds completed successfully.

## Findings

- Defects: a persisted activation route could render blank when absent from transient discovery, and
  a newly attached cortex could miss the established route; both are fixed structurally. A
  completed-but-unparseable or schema-invalid provider response could also be coerced into a false
  or true decision; it is now a typed provider-invalid-response that follows configured fallback
  handling.
- Regressions: no affected regression found in the final exact, browser, Workbench, or 334-test
  combined release slice.
- Flakes: simulated provider-attempt tails occurred and were recovered; no decision became unavailable.
- Environment issues: none on the accepted feature runs. The repo-wide QA report-template audit is
  still red on unrelated pre-existing historical reports; both reports created by this change pass
  that validator individually.
- Residual risks: clean-install/release load and deliberately forced live Anthropic/OpenAI recovery
  remain outside this pass.

### Surgical fix

The user-visible blank selector was not proof that activation was absent. A valid persisted route
could disappear from a stale/discovery-limited choice list, and a newly attached cortex could be
created without inheriting the established activation route. The surgical fix was structural:

1. merge the persisted route into the dynamic catalog presented by Agent Builder
2. derive selectable routes from runtime model discovery
3. inherit the existing agent's most common complete activation route for newly attached cortices
4. keep fallback order and attempt/late bounds in source-owned config
5. test every built-in env-normalization mapping and every rendered selector
6. validate the classifier protocol and treat malformed/schema-invalid output as typed provider
   failure, never as a coerced activation decision

No classifier behavior was moved into UI logic and no user-text matching was added.

An independent Claude review-only pass found no P0/P1 defect and specifically identified the
malformed-response false-negative risk. The final typed-error and schema-validation regressions
above close that P2 finding and its adjacent coercion case; Claude was supporting review evidence,
  not a substitute for the browser, logs, state, and exact-runtime evals.

## Not Run / Remaining Gaps

- Clean-clone/install and shipped/prebuilt artifact acceptance were not run.
- Multi-user concurrency/capacity was not established by this serial semantic gate.
- Provider fallback was covered by deterministic tests but was not deliberately forced through an
  isolated external-channel account or the browser UI run.
- Full background execution/card coverage remains owned by the broader Background Agent acceptance
  suite; this report focuses on activation reliability and Agent Builder truthfulness.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails,
  account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or
  raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports,
  App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
