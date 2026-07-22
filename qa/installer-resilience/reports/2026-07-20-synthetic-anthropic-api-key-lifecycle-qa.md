# Synthetic Anthropic API-Key Lifecycle QA — 2026-07-20

## Summary

**Result: PARTIAL.** The scoped synthetic Anthropic-card browser lifecycle passed; the optimized
Viventium first-answer and exact signed installed-artifact paths were outside this run.

Headed Chromium exercised the ordinary Easy Install Anthropic card and Claude model path against
the integrated source candidate on a disposable Apple Silicon macOS VM. The synthetic provider
implemented Anthropic's native Messages streaming protocol and required `x-api-key`; it was not an
OpenAI-compatible substitution. No real provider account, credential, cloud mutation, personal
state, or external browser request was used.

## Scope Run

| Stage | Result | Visible / correlated evidence |
| --- | --- | --- |
| Save Anthropic key | PASS | The Anthropic card reported `Local credential saved`; only stable API-key controls were visible. |
| First and second useful answers | PASS | `Claude Opus 4.8` rendered both synthetic answers in the ordinary conversation UI. |
| Browser refresh persistence | PASS | Both answers remained visible after refresh. |
| Runtime restart persistence | PASS | The session and both answers survived a real disposable-runtime stop/start. |
| Invalid-key repair | PASS | Authentication guidance appeared; replacing the key restored a useful answer. |
| Quota repair | PASS | Visible quota/rate-limit guidance appeared. |
| Provider-outage repair | PASS | Visible unavailable/retry guidance appeared. |
| Network-failure repair | PASS | Visible connection/retry guidance appeared. |
| Local Disconnect | PASS | The Anthropic card returned to `No local credential saved`. |
| Disconnected send | PASS | Key/setup guidance appeared and the Messages request counter did not increase. |
| Key re-add | PASS | Re-adding the synthetic key restored a final useful Claude answer. |

All 11 required stages passed. The sanitized ledger recorded 22 bounded Messages requests and 13
successful synthetic answers, including background work, with zero external browser attempts and
zero unexpected browser-visible HTTP failures.

## Traceability

`Easy Install -> local account -> Connected Accounts -> Anthropic key -> Claude Opus 4.8 -> useful chat -> persistence -> repair -> Disconnect -> re-add`

- Requirement: `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md` and
  `qa/installer-resilience/cases.md` `INST-017`.
- Real surface: headed Chromium, Settings > Account > Connected Accounts, model selector, and
  conversation UI.
- Protocol evidence: the provider accepted only Anthropic Messages requests using `x-api-key` and
  emitted Anthropic `message_start`, content-block, message-delta, and `message_stop` events.
- Persistence evidence: the two initial answers survived browser refresh and a real runtime restart.
- Delivery boundary: this proves the integrated source candidate, not the final signed payload,
  Intel build, Docker lane, or nested commit/pin/shipped-artifact alignment.

## Full-View Evidence Checklist

| Evidence surface | Evidence / sanitized pointer |
| --- | --- |
| Requirement and use case | Docs 39 and `INST-017`; stable Anthropic provider lifecycle. |
| Code owning path | Connected Accounts UI, encrypted user-key API, Anthropic chat endpoint, persistence, and lifecycle harness. |
| Docs and nested docs | Installer cases/README plus the integrated LibreChat candidate. |
| Logs, DB/state/persistence | Runtime restart, credential deletion/re-add, conversation persistence, and sanitized request counters agreed. |
| Generated/shipped artifact | Integrated source candidate; final signed payload and aligned nested pin were not under test. |
| Real user path | Account navigation, key save, model selection, chat, failure repair, Disconnect, and re-add in headed Chromium. |
| Visual/UX comparison | Three screenshots showed the saved card, persistent answers, and re-added answer; the ledger agreed. |
| Remaining gap | Signed payload, Intel, Docker, native-security, accessibility, and delivery alignment remain separate gates. |

## User-Grade Evidence

- Surface exercised: headed Chromium on Settings > Account > Connected Accounts, model selection,
  and the ordinary conversation UI.
- Real user path: save the Anthropic key, select Claude Opus 4.8, chat twice, refresh, restart,
  repair four failure classes, Disconnect, try a disconnected send, re-add, and chat again.
- Visible outcome: the Anthropic card showed saved and disconnected states with truthful
  local-only wording.
- Expanded/detail state: the selected badge remained `Claude Opus 4.8`; no provider remap occurred.
- Persistence/reload result: two initial answers survived browser refresh and runtime restart, and
  the final re-added answer rendered without a final
  provider-error bubble.
- Degraded states: invalid credential, quota, provider unavailable, network failure, and credential
  missing were exercised distinctly and each rendered repair guidance.
- Backend/log/DB confirmation: encrypted credential deletion/re-add, conversation persistence, runtime
  health, and sanitized Messages counters agreed with the browser.
- Final model/runtime wording check: the UI said `Disconnect` and described local credential
  removal; it did not claim provider-side revocation or official subscription connection.
- Substitution check: source, tests, logs, and hashes support the headed browser proof; they do not
  replace the separate signed-payload, platform, native-security, accessibility, or delivery gates.

## Automated Evidence

```bash
VIVENTIUM_QA_PROVIDER=anthropic node \
  qa/installer-resilience/scripts/openai-api-key-lifecycle-qa.cjs --self-test

VIVENTIUM_QA_PROVIDER=anthropic node \
  qa/installer-resilience/scripts/openai-api-key-lifecycle-qa.cjs --headed
```

- Native Messages stub self-test: PASS; 0 model-list requests, 2 Messages requests, 1 answer.
- Headed lifecycle: 11/11 stages PASS.
- Browser external network attempts: 0.
- Unexpected browser-visible HTTP failures: 0.
- Visual inspection: saved Anthropic card, two persistent Claude answers, and final re-add answer
  matched the sanitized ledger.

## Private Evidence Integrity

Raw screenshots and the sanitized ledger remain mode-restricted outside the public repository.
Public-safe integrity pointers:

- saved-state image integrity SHA-256:
  `e6764438a207547eac3b4af2a330eb397562dee0d91aa1fe7d0c4be5106189ed`
- two-answer screenshot SHA-256:
  `c506cc7e2e63952523fb8b803925ddc220bddaf9de0da05524e3c2227f6ca7db`
- final re-add screenshot SHA-256:
  `18f7855dacca37427a0739fed59d124d52878d96baa2fc1e77e29fe6e969afde`
- sanitized ledger SHA-256:
  `80072bd26abb6550a2031f74fe662a050bd71df41342a2ea5b6c956cb6096dc4`

## Findings

- Product result: the existing stable Anthropic Connected Accounts path passed without a product
  defect or workaround.
- QA gap fixed: the shared provider harness previously implemented only OpenAI-compatible routes;
  it now owns a separately tested native Anthropic Messages implementation and provider-specific UI
  selection contract.
- No flake was accepted; the final headed run completed from key save through final re-add.
- Overall release remains PARTIAL for the separately tracked delivery and platform gates.

## Public-Safety Review

- Synthetic `.invalid` account data and synthetic provider keys only.
- No real provider, external browser traffic, provider-side change, or cloud mutation.
- No credential values, cookies, local paths, usernames, hostnames, private screenshots, or personal
  identifiers in this report.
- Raw evidence remains outside the repository with owner-only permissions; only content hashes are
  published.
