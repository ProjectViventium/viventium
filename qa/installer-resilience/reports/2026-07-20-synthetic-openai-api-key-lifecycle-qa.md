# Synthetic OpenAI API-Key Lifecycle QA — 2026-07-20

## Summary

**Result: PARTIAL.** The scoped synthetic raw-provider browser lifecycle passed; the optimized
Viventium first-answer and exact signed installed-artifact paths were outside this run.

The supported Easy Install provider path was exercised in headed Chromium against the integrated
LibreChat candidate on a disposable Apple Silicon macOS VM. The browser and synthetic
OpenAI-compatible provider were fenced to loopback. No real account, provider credential, cloud
mutation, personal state, or external browser request was used.

This result closes the stable browser-provider portion of `INST-017`. It does not prove the signed
Native payload, pristine installation, Intel parity, full restore, Docker parity, accessibility
matrix, or nested commit/pin/shipped-artifact alignment.

## Scope Run

| Stage | Result | Visible / correlated evidence |
| --- | --- | --- |
| Register and open Connected Accounts | PASS | Synthetic `.invalid` user reached the ordinary Account > Connected Accounts surface. |
| Save a browser-entered OpenAI API key | PASS | UI reported `Local credential saved`; experimental direct-subscription control was absent. |
| First and second useful answers | PASS | Both synthetic answers rendered in the conversation without a provider-error bubble. |
| Browser refresh persistence | PASS | Both answers remained visible after refresh. |
| Runtime restart persistence | PASS | Both answers and the authenticated account survived a real disposable-runtime stop/start. |
| Invalid-key repair | PASS | The invalid-key state produced repair guidance; re-entering the valid synthetic key restored a useful answer. |
| Quota exhaustion | PASS | Visible quota/rate-limit repair guidance rendered. |
| Provider outage | PASS | Visible provider-unavailable/retry guidance rendered. |
| Network failure | PASS | Visible connection/retry guidance rendered. |
| Local Disconnect | PASS | The encrypted local credential was deleted and the UI returned to `No local credential saved`. |
| No request after Disconnect | PASS | A chat attempt showed key/setup guidance and the provider request count did not increase. |
| Key re-add | PASS | Re-adding the key restored a final useful answer. |

The sanitized ledger recorded 34 bounded synthetic provider requests, 26 successful synthetic
answers (including background-agent requests), zero external browser attempts, and no unexpected
browser-visible HTTP failures. All 11 required lifecycle stages were `PASS`.

## Traceability

`Easy Install -> local account -> Connected Accounts -> encrypted user key -> Viventium chat -> persistence and repair`

- Feature: supported browser-entered provider API-key onboarding.
- Requirement: `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md` and
  `qa/installer-resilience/cases.md` `INST-017`.
- Use case: a new user adds one provider key, receives useful answers, survives refresh/restart,
  repairs common failures, disconnects locally, and reconnects.
- Expected result: visible useful answers and actionable degraded states without external browser
  traffic or secret disclosure.
- Actual evidence: all 11 stable-path stages passed in a real headed browser.
- Remaining gap: signed-payload installation, restore, accessibility, Intel, Docker, final delivery
  alignment, and the optional experimental bridge remain separate gates.

## Full-View Evidence Checklist

| Evidence surface | Evidence / sanitized pointer |
| --- | --- |
| Requirement and use case | Docs 39 and `INST-017`; stable provider lifecycle only. |
| Code owning path | Connected Accounts UI, encrypted user-key API, agent chat, persistence, and the lifecycle harness. |
| Docs and nested docs/repos | Installer cases/README plus the integrated LibreChat candidate. |
| Scripts or harnesses | `openai-api-key-lifecycle-qa.cjs` in headed mode with its loopback provider. |
| Local/external prerequisite state | Disposable arm64 macOS runtime; no real provider or external browser access. |
| Logs | Expected invalid/quota/outage/network failures were correlated; no final-answer error remained. |
| DB/state/persistence | Conversation and credential state survived refresh and a real runtime restart; local Disconnect removed the credential. |
| Generated/shipped artifact | Integrated source candidate; signed immutable payload and final component pin were not under test. |
| Real user path | Registration, ordinary account-menu navigation, key save, chat, repair, Disconnect, and re-add in headed Chromium. |
| Visual/UX comparison | Screenshots showed saved/disconnected/re-added states and useful answers; the sanitized ledger agreed. |
| Not run / blocked | Signed/notarized payload, pristine/Intel/Docker/accessibility/restore matrices, and experimental bridge browser run. |

## User-Grade Evidence

- Surface exercised: headed Chromium on the ordinary LibreChat registration, Connected Accounts,
  and conversation surfaces.
- Real user path: register, open Account > Connected Accounts, add a key, chat twice, refresh,
  restart, repair four failures, Disconnect, attempt chat, and re-add.
- Visible outcome: useful answers rendered before and after restart; each failure rendered repair
  guidance; Disconnect returned to `No local credential saved`; re-add restored chat.
- Expanded/detail state: OpenAI account status, Disconnect wording, chat history, degraded messages,
  and final re-added answer were inspected.
- Persistence/reload result: both initial answers survived browser refresh and a real runtime
  stop/start; the final answer rendered after key re-add.
- Local/external prerequisite state: disposable local runtime healthy; loopback synthetic provider
  only; signed publisher trust was not part of this run.
- Evidence retrieval classification, if applicable: provider success, invalid credential, quota,
  provider unavailable, network failure, and credential missing were exercised distinctly.
- Fallback path, if applicable: the UI guided repair/re-entry; it did not silently remap providers.
- Backend/log/DB confirmation: sanitized request counters, runtime restart, credential deletion, and
  conversation persistence agreed with the visible browser state.
- Final model/runtime wording check: the UI said `Disconnect` and described local deletion; it did
  not claim provider-side revocation or official subscription OAuth.
- Substitution check: source, tests, logs, and hashes support the headed browser evidence; they do
  not substitute for the separate signed-payload, restore, Docker, Intel, or accessibility gates.

## Automated Evidence

```bash
python -m pytest \
  tests/release/test_openai_api_key_lifecycle_qa.py \
  tests/release/test_qa_operating_contract.py \
  tests/release/test_qa_results_public_safety.py -q

VIVENTIUM_QA_CLIENT_BASE=http://127.0.0.1:3190 \
VIVENTIUM_QA_EMAIL="$SYNTHETIC_QA_EMAIL" \
VIVENTIUM_QA_PASSWORD="$SYNTHETIC_QA_PASSWORD" \
VIVENTIUM_QA_RESTART_ARGV_JSON='["/tmp/viventium-qa-restart"]' \
VIVENTIUM_QA_PRIVATE_EVIDENCE_DIR='/tmp/viventium-private-evidence' \
node qa/installer-resilience/scripts/openai-api-key-lifecycle-qa.cjs --register --headed
```

- Harness unit/contract result: 4 passed after the headed-run regressions were added.
- Headed lifecycle result: 11 of 11 stages passed.
- External browser attempts: 0.
- Unexpected browser HTTP failures: 0.

## Findings

- Product result: stable API-key onboarding, persistence, repair, Disconnect, and re-add passed on
  the integrated disposable runtime.
- QA defects fixed before acceptance: leaked provider port on launch failure, wrong save HTTP verb,
  strict duplicate-text locator, incomplete synthetic Responses stream, non-user settings reopen,
  and missing private failure capture.
- Residual risks: the overall installer release remains PARTIAL for the separately named gates.
- Flakes: none accepted; each prior failure was reproduced and resolved before the final clean run.

## Private evidence integrity

Raw screenshots and the sanitized ledger remain outside the public repository because screenshots
are machine-local QA artifacts. Public verification uses content hashes only:

- final re-add screenshot SHA-256:
  `251490f998090cd9d763127469e13740841baf2c83a57d09bceb24b325ebfad2`
- sanitized ledger SHA-256:
  `997b1951f87584e4e4ccf01e7a28b8fb9ca67015ae792c0cee3670f2c5548b76`

The browser network fence blocked every non-loopback origin. The provider was a process-local stub;
its valid and invalid credentials were synthetic constants. Logs and screenshots were inspected for
the rendered answer, persistence, repair states, Disconnect state, and absence of a final error
bubble.

## Harness regressions added during the run

The real headed run exposed and fixed reusable QA defects before this result was accepted:

- release the loopback provider when browser launch fails;
- wait for the actual `PUT /api/keys` save response;
- distinguish conversation text from the accessibility live-region duplicate;
- emit a complete OpenAI Responses event sequence so the stub cannot create a false post-answer
  provider error;
- reopen Connected Accounts through the ordinary account-menu user path after restart;
- save a private failure screenshot and sanitized partial ledger on future failures.

The harness contract and synthetic-provider tests pass after these changes. Only the final headed
run above is treated as user-path evidence.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No personal emails, private accounts, customer data, raw prompts, or private screenshots.
- [x] No local absolute paths, usernames, hostnames, machine names, or App Support dumps.
- [x] Only synthetic counts, public-safe placeholders, artifact hashes, and conclusions are published.
- [x] Raw browser evidence remains mode-restricted outside the public repository.
