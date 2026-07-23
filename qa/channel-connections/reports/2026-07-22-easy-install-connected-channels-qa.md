# Easy Install Connected Channels QA Run - 2026-07-22

## Summary

- Result: `PARTIAL`; production-built browser, persistence, security, upgrade, and failure
  paths passed, while real external-provider delivery, signed Native bootstrap, and physical clean-Mac
  acceptance remain blocked by external credentials, approvals, or unavailable access.
- Build/source under test: isolated public parent and pinned LibreChat source candidates.
- Runtime/artifact under test: production-built LibreChat client and API on Node 24.16.
- Environment: isolated mode-`0700` temporary state, dedicated localhost MongoDB, headed Google
  Chrome, no Docker or virtual machine.
- Tester: Codex with an independent review-only second-opinion gate before public release.
- Related change: Easy Install optimized-agent continuity plus Settings > Channels onboarding for
  Telegram, Slack, and WhatsApp.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `CHANNEL-001` | PARTIAL | Headed browser plus parent installer contracts | Browser path passes; signed clean-Mac bootstrap is external-blocked. |
| `CHANNEL-002` | PARTIAL | Headed pairing and hash/storage checks | Dedicated Telegram delivery credentials were unavailable. |
| `CHANNEL-003` | PARTIAL | Headed `503` recovery plus authenticated-envelope/conflict tests | Local repair passed; revoked-token provider proof was not run. |
| `CHANNEL-004` | PARTIAL | Manifest, secret handling, thread/recovery automation | No dedicated Slack workspace. |
| `CHANNEL-005` | PARTIAL | Settings-owned public-origin field, Cloud API UI, HTTPS/HMAC/staged verification/idempotency tests | No dedicated Meta app or provider-controlled public callback acceptance. |
| `CHANNEL-006` | PARTIAL | Compiler and ownership/conflict regressions | Real Keychain state was intentionally not accessed. |
| `CHANNEL-007` | PARTIAL | Durable retry/degraded-start/upgrade automation | Real external delivered-message proof unavailable. |
| `CHANNEL-008` | PARTIAL | Two headed local users, hash-only code, cross-user automation | Two external identities unavailable. |
| `CHANNEL-009` | PARTIAL | Lease, fencing, takeover, durable-delivery automation | Real two-process provider delivery unavailable. |
| `CHANNEL-010` | PASS | Cross-service restore/disconnect, stale-test, late provider-health/cleanup, and reconnect races | Stale ciphertext/tests/health events/cleanup/workers fail closed; Settings reconnects without database repair. |
| `CHANNEL-011` | PASS | Bounded Agent/provider retries and partition tests | Poisoned turns are scrubbed and unrelated conversations continue. |
| `CHANNEL-012` | PASS | Stable Slack event/message dedupe tests | Socket delivery-envelope IDs are never dedupe identities. |
| `CHANNEL-013` | PASS | Timer-before-readiness and retryable-readiness tests | A transient index failure can self-heal on periodic reconciliation. |
| `CHANNEL-014` | PASS | Gateway ledger/replay and client SSE tests | Empty success is terminal once; errors and truncation still fail. |
| `CHANNEL-015` | PASS | Real local Unix HTTP server and timer recovery | Signed POST/SSE stayed on the private socket; missing/stale paths recovered without loopback fallback. |
| `CHANNEL-016` | PASS | Telegram transport and signed gateway SSE regressions | HTML fallback, code-point-safe Unicode chunks, explicit unsupported-media replies, and generated-file disclosure passed. |
| `CHANNEL-017` | PASS | WhatsApp service, transport, real-Mongo, and client cache regressions | Public origin persistence, outbound HMAC proof, and pending replacement state after Test Connection passed with synthetic credentials. |
| `CHANNEL-018` | PASS | Quota, pairing-attempt, ingress-admission, and durable queue concurrency regressions | Strict identity fairness, atomic first-window attempts, durable unsupported-media admission, and pre-Agent remap recovery passed. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `CHANNEL-001` | Open Settings > Channels after Easy Install | Headed Chrome | PARTIAL | Three channels and self-service pairing shown; admin setup separated | Production bundle, API state, installer contracts | Signed clean-Mac bootstrap |
| `CHANNEL-002/004/005` | Configure Telegram, Slack, or WhatsApp | Headed Chrome | PARTIAL | Official-provider instructions, password fields, manifest, public-HTTPS origin, setup guide, and generated-callback guidance | No browser storage; transport, origin validation/persistence, encryption, webhook and queue suites pass | Dedicated external accounts and provider callback acceptance |
| `CHANNEL-003` | Recover from provider save failure | Headed Chrome | PARTIAL | Actionable error; typed value remains editable | Synthetic `503`; no local/session storage persistence | Revoked-token provider proof |
| `CHANNEL-008` | Pair as admin and regular local user | Headed Chrome | PARTIAL | Focused, copyable code; regular user never sees setup secrets | Only SHA-256 code hash and expiry persisted | Two external identities |
| `CHANNEL-007/009` | Restart, retry, fence competing workers | Automated runtime surfaces | PARTIAL | No substitute visible-provider claim made | Durable ingress/egress, leases, offsets, fencing, upgrade tests | External multi-process delivery |
| `CHANNEL-010/011` | Race restore, test, or late provider health against replacement/disconnect; leave a turn permanently failing | Automated runtime surfaces | PASS | No visible false-ready state | Generation CAS, source-generation health fence, stale-worker stop, bounded retry, scrubbed terminal rows | None for these failure classes |
| `CHANNEL-012/013/014` | Redeliver Slack, recover startup readiness, replay an empty completion | Automated provider/gateway surfaces | PASS | Empty completion receives truthful open-Viventium fallback | Stable dedupe, retryable readiness, terminal ledger and SSE error checks | External-provider delivery remains separate |
| `CHANNEL-015` | Run a Native channel turn without a TCP API listener, then repair a missing/stale socket | Real local Unix HTTP server | PASS | Channel answer arrives through the existing signed gateway | POST chat, GET SSE, socket ownership/mode, failure class, and 30-second retry | Signed installed-artifact and provider delivery remain separate |
| `CHANNEL-016/017/018` | Exercise formatting, media/file disclosure, WhatsApp replacement, quota floods, pairing races, and queued remaps | Automated provider/gateway/client/durable-store surfaces | PASS | Every unsupported item has a truthful next step; pending setup remains visible; recovery is bounded | Exact request bodies, reconstructed Unicode, SSE attachment, cache, atomic counters, and Agent call count | External provider delivery remains separate under `CHANNEL-002/004/005/007/009` |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Easy Install and Connected Channels.
- Requirement: `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md` and
  `docs/requirements_and_learnings/03_Telegram_Bridge.md`.
- Use case: install, open Channels, configure or pair, recover from failure, restart, and keep core
  browser chat usable.
- QA case: `CHANNEL-001` through `CHANNEL-018`.
- Expected result: truthful admin setup, least-privilege user pairing, encrypted server-side secrets,
  durable ordered delivery, and no optional-channel failure blocking Viventium.
- Actual evidence: six production-built headed-browser journeys passed after one earlier four-case
  run and one transient first-run harness wait; complete channel,
  encryption, transport, queue, lease, upgrade, build, and release suites passed after fixes.
- Remaining gap or fix: run dedicated external Telegram/Slack/Meta lifecycles, exact signed Native
  artifact, and supported physical clean-Mac matrix when those authorities and surfaces are available.

## Full-View Evidence Checklist

| Evidence surface | Required question | Evidence / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is proven? | Installer/compiler and Telegram docs; `CHANNEL-001` through `CHANNEL-018`. |
| Code owning path | Which path owns behavior? | LibreChat channel contract, admin/pairing/runtime/transports, API routes/services, Settings UI; parent compiler/runtime readiness and upgrade reseed. |
| Docs and nested docs/repos | Which sources define expected behavior? | Owning requirements, runtime QA map, channel README/cases, installer cases. |
| Scripts or harnesses | What exercised it? | Permanent connected-channel Playwright spec; nested Jest suites; parent release suite. |
| Local/external prerequisite state | What was healthy or degraded? | Local MongoDB and production build healthy; provider credentials, provider-controlled Meta callback acceptance, signing authority, and physical relay unavailable. |
| Logs | What confirms the result? | Sanitized test counts and channel-disabled warning when the synthetic gateway secret was intentionally absent. |
| DB/state/persistence | What confirms persistence? | Pairing record held only a SHA-256 hash and expiry; synthetic users and fixtures were removed. |
| Generated/shipped artifact | What was inspected? | Production client/API builds and Native payload/agent-migration contracts; exact signed artifact not available. |
| Real user path | What was used like a user? | Headed Chrome Settings > Channels as an administrator and a regular user. |
| Visual/UX comparison | Did visible UX match state? | Yes; final screenshots showed responsive cards, recovery error, focused pairing code, and least-privilege regular-user view. |
| Not run / blocked | What remains? | Real external delivery/provider callback acceptance, signed/notarized Native artifact, and physical clean-Mac run. |

## User-Grade Evidence

- Surface exercised: production-built LibreChat client and API in headed Google Chrome.
- Real user path: open account menu, select Connected Channels, inspect and cancel all setup forms,
  trigger a provider failure, connect/disconnect/reconnect, inspect the ambiguous-delivery warning,
  generate/copy a pairing code, then repeat as a regular user.
- Visible outcome: Telegram, Slack, and WhatsApp guidance is clear; failure is actionable; an
  ambiguous send warns against a blind retry; reconnect needs no database repair; only an
  administrator sees global installation credentials; a regular user sees only self-service pairing.
- Expanded/detail state: all three setup cards, password fields, Slack manifest, WhatsApp public
  HTTPS field/guide/callback instructions, focused pairing output, copy confirmation, and
  regular-user empty states were checked at desktop and 320-pixel widths.
- Persistence/reload result: setup cancellation and failed save persisted no browser secret; pairing
  persisted only a hash and expiry. Cross-restart delivery remains automated rather than external.
- Local/external prerequisite state: production build and dedicated local MongoDB healthy; real
  provider credentials, Meta provider callback acceptance, signing approval, and physical relay
  unavailable.
- Evidence retrieval classification, if applicable: external provider auth/config missing and local
  physical prerequisite unavailable.
- Fallback path, if applicable: deterministic local provider fixtures exercised failure, ordering,
  webhook, lease, and recovery behavior without being presented as external-user proof.
- Backend/log/DB confirmation: six Playwright journeys passed; DB inspection found a 64-character
  SHA-256 pairing hash and no plaintext code; teardown removed both users and all channel fixtures.
- Final model/runtime wording check: no direct-model channel path exists; the gateway routes through
  the existing Viventium conversation/agent path, while missing gateway readiness disables workers.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for external provider, signed-artifact, or physical
  clean-Mac evidence; those rows remain `PARTIAL`.

## Automated Evidence

```bash
npm ci
npm run build:data-schemas
npm run build:data-provider
npm run build:api
npm run build:client-package
npm run frontend
npm run test:client
npm run test:api
npm run test:packages:api
npm run test:packages:client
npm run test:packages:data-provider
npm run test:packages:data-schemas
npm audit --omit=dev
# Provide a dedicated QA/test MONGO_URI and private synthetic example.test E2E credentials.
VIVENTIUM_E2E_CHANNEL_FIXTURES=true VIVENTIUM_QA_HEADED=true \
  npx playwright test --config=e2e/playwright.config.channels.ts
python -m pytest tests/release/ -q
```

- Headed browser: 6 passed in the final production-built run; the original four journeys also passed
  in the preceding complete rerun.
- Final complete bounded suites: 1,474 LibreChat client tests passed; all 209 API test files passed
  with 4,831 assertions and 19 expected skips; API packages passed 3,068 with 2 skipped; client
  package passed 130; data-provider passed 815 with 1 skipped; data-schemas passed 413 with 3
  skipped.
- Post-hardening changed-path verification: 50/50 startup-recovery, Native Unix-socket, gateway
  security, and gateway route tests passed; 28/28 Easy Install registry and QA-contract tests
  passed; 8/8 production dependency/runtime audit tests passed.
- Channel parity hardening: 97/97 complete package-channel, 157/157 affected API
  route/service/security, 36/36 Connected Channels component, and 16/16 durable-delivery queue tests
  passed. The public-origin field also passed client submission, service callback generation, and
  real-Mongo persistence regressions. These prove deterministic local behavior, not external
  Telegram, Slack, or Meta acceptance.
- Parent upgrade continuity: 10 migration-state, 3 frozen-history, 77 CLI-upgrade, 85
  Native-payload, and 30 managed-agent seed tests passed.
- Parent release suite: 1,560 passed and 30 skipped. The isolated runner first omitted optional test
  imports (`pydantic`, `croniter`, then `fastapi`); after supplying the declared test dependencies,
  every collected release assertion passed.
- Nested publication: LibreChat PR 71 passed all 14 exact-head hosted checks, including the complete
  API suite from a full-history standalone checkout, and merged to `main` at
  `9e859bcac6a691bb67224380842b44b96a6e3073`. The parent component lock and Native payload policy
  both pin that exact merged commit; the complete 1,560-test parent release suite passed again after
  the pin update.
- Production dependency audit: zero moderate-or-higher vulnerabilities; post-prune Sharp and MCP
  runtime loading passed.

## Findings

- Defects: responsive pairing cards clipped at narrow widths; cleanup aborted on no conversations;
  restore could resurrect stale credentials or leave a stale worker; old-generation provider health
  could demote a newly repaired connection; poison turns retried without a
  bound and shared one user's partition; Slack used a delivery ID for dedupe; readiness cached one
  rejection forever; Native channel turns incorrectly targeted a loopback API port; gateway shared-
  secret comparison was not digest-based timing-safe; empty successful responses could repeat the
  Agent turn; the QA report initially missed its contract; macOS/Python 3.14 could report `EPERM`
  while an owned child process group still needed bounded termination. All received code/test fixes
  and reruns.
- Regressions: none observed in the final complete suites or post-hardening changed-path runs.
- Flakes: one headed global-setup attempt timed out waiting for the Sign up link before any test ran;
  the server config showed registration open, a clean visual inspection showed the link, and two
  clean account-registration/full-browser reruns passed. The backend suite retained pre-existing
  open-handle/listener warnings after passing; bounded fresh Jest processes prevented memory growth.
- Environment issues: the physical relay refused the approved port under strict verification.
- Residual risks: real provider delivery/provider callback acceptance, signed/notarized immutable
  Native payload, and physical Apple Silicon/Intel accessibility/fault coverage need external
  access or release authority.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
