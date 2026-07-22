# Synthetic Provider Lifecycle Gap Audit — 2026-07-21

## Summary

- Result: **PARTIAL**.
- Build/source under test: integrated source candidate.
- Runtime/artifact under test: compiler outputs and the synthetic provider lifecycle harness; no
  final immutable installed artifact.
- Environment: isolated local source checkout with loopback-only provider self-tests.
- Related change: complete Groq Custom Settings export and fail closed on browser credential residue.

The supported Easy Install browser lifecycle remains headed-PASS for OpenAI, Anthropic, Groq, and
Grok/xAI from the 2026-07-20 integrated source-candidate runs. This follow-up found and fixed one
Custom Settings compiler omission and added browser-persistence inspection. Neither change is final
signed-artifact, real-provider, or macOS Keychain/TCC proof.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `INST-017` browser lifecycle | PARTIAL | Prior headed four-provider run plus new harness regression | New residue inspection has not run headed. |
| `INST-010` Custom Settings provider export | PASS | Compiler regression suite | Synthetic compiler fixtures show all four provider references map independently; missing reference preserves prior runtime. |
| `INST-010` real provider / native Keychain | BLOCKED | No authorized account or headed Keychain/TCC surface | Supporting simulation cannot replace required user-path evidence. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `INST-017` happy path and retry/recovery | Add a key, chat twice, refresh/restart, repair failures, Disconnect, and re-add. | Headed browser on 2026-07-20 | PARTIAL | The scoped synthetic raw-provider states and answers rendered. | Sanitized request counters and persisted conversation agreed. | Rerun the residue inspection headed and prove the optimized exact-artifact first answer. |
| `INST-017` persistence/privacy | Confirm no synthetic key remains in browser persistence after lifecycle stages. | Harness offline self-test | PARTIAL | No new visible browser run. | Storage-state guard accepts clean state and rejects Local Storage/IndexedDB leaks without emitting a key. | Run in headed browser on exact final artifact. |
| `INST-010` Custom Settings happy path | Compile OpenAI, Anthropic, Groq, and xAI Keychain references. | CLI compiler test double | PARTIAL | Not user-visible; synthetic compiler fixtures passed. | Source/service values, Native sentinels, and mode `0600` asserted. | Native Keychain/TCC run. |
| `INST-010` missing auth/config | Compile with a missing Groq Keychain reference. | CLI compiler test double | PARTIAL | Not user-visible; synthetic compiler fixtures passed. | Compile fails and prior generated runtime remains byte-identical. | Headed repair UX on exact artifact. |
| `INST-010` generated/shipped artifact verification | Install and use final immutable payload. | Not available | BLOCKED | Not run. | Source output only. | Signed/notarized payload and installed-artifact identity. |
| `INST-010` public/private safety | Inspect changed public evidence for private values. | Public diff and QA safety suite | PASS | Public report contains synthetic conclusions only. | Diff scan and QA public-safety tests pass. | None in this slice. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Easy Install and Custom Settings provider credentials.
- Requirement: `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`.
- Use case: a new or existing user can add the intended provider without credential drift or leakage.
- QA case: `INST-010` and `INST-017`.
- Expected result: each provider uses its own credential; browser persistence has no raw key; failure
  preserves the prior runtime.
- Actual evidence: 149 compiler/lifecycle tests, four provider self-tests, storage self-test, and
  prior headed four-provider lifecycle.
- Remaining gap or fix: exact headed storage rerun, real Keychain/TCC, final artifact, provider-side
  lifecycle, upgrade/restore/uninstall user paths.

## Full-View Evidence Checklist

| Evidence surface | Required question | Evidence / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which contract is proven? | Docs 39, `INST-010`, and `INST-017`. |
| Code owning path | What owns credential export and residue checks? | Config compiler provider map and provider lifecycle browser harness. |
| Docs and nested docs/repos | What defines expected behavior? | Installer requirements, README, cases, and continuity credential-exclusion contract. |
| Scripts or harnesses | What exercised it? | Compiler release tests and loopback provider/storage self-tests. |
| Local/external prerequisite state | What was healthy? | Local Node/Python test runtimes only; real providers and native Keychain/TCC were not used. |
| Logs | What confirms or contradicts the result? | Sanitized PASS counts only; no raw storage or provider payload was recorded. |
| DB/state/persistence | What confirms persistence? | Prior headed run confirms conversation/key lifecycle; new browser-residue inspection is offline-only. |
| Generated/shipped artifact | What output was inspected? | Mode-`0600` source/service env and secret-free Native env; no final installed artifact. |
| Real user path | What was used like a user? | Prior headed browser Connected Accounts/chat lifecycle; no new headed run in this follow-up. |
| Visual/UX comparison | Did visible UI match expected behavior? | Prior provider states and answers matched; current compiler fix has no direct UI evidence. |
| Not run / blocked | What remains? | Exact headed residue scan, real provider/Keychain/TCC, final artifact, upgrade, restore reconnect, and uninstall recovery. |

Supporting tests and source inspection cannot replace required user-path evidence; those missing
surfaces remain `PARTIAL` or `BLOCKED`.

## User-Grade Evidence

- Surface exercised: prior headed browser Connected Accounts, model selector, and ordinary chat;
  this follow-up exercised only compiler and harness test surfaces.
- Real user path: the 2026-07-20 run added each provider key, produced useful answers, refreshed,
  restarted, repaired failures, disconnected, and re-added; the new residue scan was not rerun there.
- Visible outcome: prior saved/disconnected/re-added states and answers passed; no new visible outcome
  is claimed for the compiler fix.
- Expanded/detail state: prior provider cards and failure guidance were inspected; no native
  Keychain prompt or final-artifact setup panel was inspected here.
- Persistence/reload result: prior answers and account state survived browser refresh and runtime
  restart; the new storage guard has offline proof only.
- Local/external prerequisite state: loopback synthetic providers and local test runtimes were used;
  no real provider, external network, signed payload, Docker/Tart, or personal runtime was used.
- Evidence retrieval classification, if applicable: invalid credential, quota, provider unavailable,
  network failure, and auth/config missing were distinct in the prior headed lifecycle.
- Fallback path, if applicable: repair/re-entry was exercised in the prior browser run; no browser,
  computer, or local-delegation fallback was required by the compiler test.
- Backend/log/DB confirmation: prior sanitized counters and persistence agreed with visible UI; current
  compiler tests confirm env ownership and atomic failure, not live DB behavior.
- Final model/runtime wording check: prior UI kept Groq distinct from Grok/xAI and used `Disconnect`,
  not provider-side revoke; Native output retains `user_provided` capability sentinels.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for the missing headed residue, Keychain/TCC, or
  installed-artifact paths.

## Automated Evidence

```bash
python -m pytest -q \
  tests/release/test_config_compiler.py \
  tests/release/test_openai_api_key_lifecycle_qa.py

node --check qa/installer-resilience/scripts/openai-api-key-lifecycle-qa.cjs
node qa/installer-resilience/scripts/openai-api-key-lifecycle-qa.cjs --storage-self-test
VIVENTIUM_QA_PROVIDER=openai node qa/installer-resilience/scripts/openai-api-key-lifecycle-qa.cjs --self-test
VIVENTIUM_QA_PROVIDER=anthropic node qa/installer-resilience/scripts/openai-api-key-lifecycle-qa.cjs --self-test
VIVENTIUM_QA_PROVIDER=groq node qa/installer-resilience/scripts/openai-api-key-lifecycle-qa.cjs --self-test
VIVENTIUM_QA_PROVIDER=xai node qa/installer-resilience/scripts/openai-api-key-lifecycle-qa.cjs --self-test
```

- Combined compiler/provider lifecycle suite: 149 passed.
- OpenAI, Anthropic, Groq, and xAI loopback provider self-tests: PASS.
- Browser-persistence guard self-test: PASS and secret-free.
- JavaScript syntax, diff hygiene, and public-safety checks: PASS.

## Findings

- Defects: Groq in `llm.extra_provider_keys` resolved but was omitted from runtime export; fixed by
  one normalized provider-to-env table.
- Regressions: tests now require all four source/service values, Native sentinels, mode `0600`,
  missing-reference atomicity, and fail-closed browser-residue inspection.
- Flakes: none observed in the focused automated runs.
- Environment issues: final immutable artifact and native Keychain/TCC were unavailable in this slice.
- Residual risks: headed residue rerun, real provider lifecycle, doctor/restart/upgrade/restore/
  uninstall on the final artifact, and external release gates remain open.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, timestamps, and conclusions only.

No provider call, cloud mutation, commit, push, Docker/Tart action, or personal runtime access was
performed. Overall installer release status remains **PARTIAL**.
