# Synthetic Groq And Grok API-Key Lifecycle QA — 2026-07-20

## Summary

**Result: PARTIAL.** The scoped synthetic Groq/Grok raw-provider browser lifecycles passed; optimized
Viventium answer parity and the exact signed installed-artifact path were outside this run.

Headed Chromium exercised the ordinary Easy Install path for both Groq and Grok (xAI) against the
integrated source candidate on a disposable Apple Silicon macOS VM. Each provider used its own
browser-entered synthetic key and loopback-compatible provider. No real provider account, real
credential, external browser request, personal state, or cloud mutation was used.

Both providers passed all 11 required stages: first and second useful answers, browser-refresh and
runtime-restart persistence, invalid-key repair, quota repair, outage repair, network repair, local
Disconnect, zero new provider request from the disconnected chat attempt, and key re-add.

## Scope Run

| Stage | Groq | Grok (xAI) | Visible / correlated evidence |
| --- | --- | --- | --- |
| Connected Accounts key save | PASS | PASS | The correct provider card reported `Local credential saved`; experimental subscription controls were absent. |
| Two useful answers | PASS | PASS | The selected Groq or Grok model rendered both synthetic answers in the ordinary conversation UI. |
| Browser refresh | PASS | PASS | Both answers remained visible. |
| Runtime restart | PASS | PASS | The authenticated session and both answers survived a real disposable-runtime stop/start. |
| Invalid key and repair | PASS | PASS | Invalid-key guidance appeared and replacing the key restored chat. |
| Quota, outage, network | PASS | PASS | Each distinct degraded state rendered repair guidance. |
| Local Disconnect | PASS | PASS | The provider card returned to `No local credential saved`. |
| Disconnected send | PASS | PASS | Key/setup guidance appeared and the synthetic provider chat-request counter did not increase. |
| Key re-add | PASS | PASS | A final useful answer rendered for the same selected provider. |

The Groq ledger recorded 32 bounded synthetic chat requests and 22 successful answers. The Grok
ledger recorded 34 bounded synthetic chat requests and 24 successful answers. The additional
requests are expected background-agent traffic within the fenced runtime. Both ledgers recorded
zero external browser attempts and zero unexpected browser-visible HTTP failures.

## Traceability And Boundaries

`Easy Install -> local account -> Connected Accounts -> Groq or Grok key -> selected model -> useful chat -> persistence -> repair -> Disconnect -> re-add`

- Requirement: `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md` and
  `qa/installer-resilience/cases.md` `INST-010` / `INST-017`.
- Real surface: headed Chromium, Account > Connected Accounts, model selector, and conversation UI.
- Supporting state: encrypted user-key API, runtime restart, persisted conversation, sanitized
  provider counters, and fenced browser traffic.
- Not run: real Groq/xAI accounts, provider-side revocation, signed/notarized payload installation,
  Intel, Docker, full restore, native Keychain/TCC, and the complete accessibility matrix.
- Delivery boundary: this proves the integrated source candidate. It does not substitute for final
  nested commit, parent pin, immutable payload, or installed-artifact hash alignment.

## Full-View Evidence Checklist

| Evidence surface | Required question | Evidence / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Does the result map to a declared contract? | Docs 39, `INST-010`, and `INST-017`. |
| Real user path | Which product surface ran? | Headed Chromium on Connected Accounts, model selection, and ordinary chat. |
| Visible outcome | What did the person see? | Provider-specific saved/disconnected states, useful answers, distinct repair guidance, and restored chat after re-add. |
| Persistence | Did state survive reload/restart? | Both first answers survived browser refresh and a real runtime stop/start for each provider. |
| Backend/log/DB state | Did supporting state agree? | Encrypted key lifecycle, runtime restart, conversation persistence, and sanitized request counters agreed with the UI. |
| Generated/shipped artifact | Was the final release artifact tested? | Integrated source candidate only; signed payload/pins/installed hashes remain separate. |
| Public/private boundary | Is evidence safe to publish? | Synthetic `.invalid` account, loopback providers, content hashes only; raw screenshots stay private. |

## User-Grade Evidence

- Surface exercised: headed Chromium on LibreChat Settings > Account > Connected Accounts, model
  selector, and conversation view.
- Real user path: open Connected Accounts, save the selected provider key, select Groq or Grok,
  chat twice, refresh, restart, repair invalid/quota/outage/network states, Disconnect, attempt a
  disconnected send, re-add the key, and chat again.
- Visible outcome: the correct provider/model produced useful answers; failure states rendered
  repair guidance; Disconnect showed missing credentials; re-add restored chat.
- Expanded/detail state: each provider card, truthful local-only Disconnect copy, model badge,
  persistent answer history, and final re-added answer were inspected.
- Persistence/reload result: both initial answers survived browser refresh and a real disposable
  runtime restart for Groq and Grok.
- Backend/log/DB confirmation: encrypted credential deletion/re-add, sanitized request counters,
  conversation persistence, and runtime health agreed with the visible state.
- Final model/runtime wording check: Groq remained Groq and Grok remained Grok; no silent provider
  remap or official-subscription claim appeared.
- Substitution check: source/tests/logs/hashes support the headed browser run; none substitutes for
  signed-payload, pristine-install, restore, Intel, Docker, native-security, or accessibility QA.

## Automated Evidence

```bash
VIVENTIUM_QA_PROVIDER=groq node \
  qa/installer-resilience/scripts/openai-api-key-lifecycle-qa.cjs --headed

VIVENTIUM_QA_PROVIDER=xai node \
  qa/installer-resilience/scripts/openai-api-key-lifecycle-qa.cjs --headed
```

- Harness contract tests: 4 passed.
- Groq lifecycle: 11/11 stages passed.
- Grok lifecycle: 11/11 stages passed.
- External browser attempts: 0 for each run.
- Unexpected browser HTTP failures: 0 for each run.

## Private Evidence Integrity

Raw screenshots remain outside the public repository. Public-safe integrity pointers:

- Groq final re-add screenshot SHA-256:
  `f9d422c2e871bc1109e82b039c1139f8ebe55d540631d1b11573403f8b0ffe76`
- Groq sanitized ledger SHA-256:
  `e08d298e8682fb6b303e8563beb2024e0bed6de9ee87dcf131a9f70718fefc4f`
- Grok final re-add screenshot SHA-256:
  `c3d41fa82ce2fc7682153602bb5fc355a5c4768ce26bfa11c0e76ccdc5c2f5b1`
- Grok sanitized ledger SHA-256:
  `726f8d4358a6bb94c8955f50073a17e1fed41144f29a205a2adeb2ef563c4d98`

## Findings

- Groq and Grok now use the same novice Connected Accounts lifecycle as the already-proven OpenAI
  stable API-key path.
- QA exposed and corrected the provider-model selection, Settings closure, custom-key state refresh,
  and disconnected-request baselining needed to make the real headed run deterministic and honest.
- No flake was accepted: the final Groq and Grok runs completed cleanly from start to final re-add.
- Overall release status remains PARTIAL until the separate delivery, platform, restore, Docker,
  native-security, and inclusive-UX gates are closed.

## Public-Safety Review

- Synthetic account data only; email domain was `.invalid`.
- Synthetic provider keys were never written to the report, screenshots, commands, or hashes.
- Browser traffic was fenced to loopback and recorded zero external attempts.
- Raw screenshots/logs remain in owner-only private QA storage outside the public repository.
- The report contains no local username, hostname, personal email, home path, secret, or private URL.
