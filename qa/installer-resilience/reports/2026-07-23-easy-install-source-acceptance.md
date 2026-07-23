# Easy Install Source Acceptance — 2026-07-23

## Summary

- Result: **PASS** for the supported non-Docker source Easy Install path.
- Build/source under test: isolated parent source plus the PR 72 product tree merged at
  `37fe3b7ea6f8091a554df69d88bf846961afbd30`; the final pin
  `85a2e326cd5672f00c927984f00a92c9b3f07f9c` adds only optional publisher workflow gates.
- Runtime/artifact under test: source Native/non-Docker runtime; not a signed distribution artifact.
- Environment: isolated support, browser, database, cache, temp, and loopback provider roots on macOS.
- Tester: Codex with independent review-only agents and Claude Fable 5 Extra review gates.
- Related change: one-command setup, provider/background handoff, Connected Channels, responsive
  navigation, safe upgrade, and immutable parent pins.

A new user can run one Easy Install command, complete local browser setup, connect a preferred
provider, receive the public optimized Viventium agent/prompt configuration, optionally open and
configure Telegram, Slack, or WhatsApp under Settings > Channels, and preserve their work through
restart, warm reinstall, and established-user upgrade. The run contained only synthetic accounts,
messages, credentials, and loopback providers. No owner database, conversations, prompts, browser
profile, Keychain, application state, or unrelated files were used.

This result accepts the public source entrypoint. Signing, notarization, and vendor-side account
approval are separate release/distribution boundaries and are not represented as source failures.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `INST-033` one-command install | PASS | Headless public installer completed; warm idempotent rerun completed in under one second. | Source Easy Install. |
| `INST-033` optimized baseline | PASS | Exactly 12 public agents, 74 prompts, and stable normalized bundle hash. | No owner data. |
| `INST-033` provider lifecycle | PASS | OpenAI, Groq, and Grok/xAI each passed the headed 12-step lifecycle. | Two answers plus failures/recovery. |
| `INST-033` background handoff | PASS | User-scoped custom endpoint, headers, and fetch options reached Background Cortex. | Capability marker was not used as a key. |
| `INST-033` Channels | PASS | Telegram, Slack, and WhatsApp setup/cancel, masking, guidance, repair, refresh, and reopen. | Headed browser. |
| `INST-033` responsive/a11y | PASS | Six headed desktop/mobile cases; zero accessibility violations; mutation reproduced the prior interception. | Production-built client. |
| `INST-033` continuity | PASS | Warm reinstall and established-user upgrade preserved six users, 35 conversations, 80 messages, 12 agents, 74 prompts, and the public bundle hash. | Synthetic counts only. |
| `INST-033` uninstall | PASS | Supported owned uninstall stopped task listeners and followed the selected recoverable-state policy. | Isolated root only. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `INST-UC-019` | Install, register, connect a provider, chat twice, open Channels, restart, reinstall, upgrade, and uninstall. | Public CLI plus headed production browser | PASS | Setup, answers, failure guidance, Channels, responsive reopen, and healthy post-upgrade status matched the contract. | Loopback request ledgers, continuity status `ok`, stable counts/hash, merged nested SHA, aligned parent pins. | None for the non-Docker source path. |

## Sanitized Evidence Ledger

This table is the durable public record of the isolated run. Values are synthetic aggregates or
content hashes; no raw provider payload, credential, browser state, database row, local path, user
identifier, or machine identity is retained.

| Evidence | Result | Sanitized value |
| --- | --- | --- |
| Easy Install warm rerun | PASS | Completed in under one second with unchanged synthetic data. |
| Optimized public baseline | PASS | 12 agents; 74 prompts; normalized bundle SHA-256 `281f112db71766d4b47ec230a07c6b407bd1cbed3443f06bc8047d565e7b6980`. |
| OpenAI lifecycle | PASS, 12/12 stages | 27 synthetic chat requests; 20 successful answers; zero external attempts; six browser-residue checks; ledger SHA-256 `43fd8c32804fa855e7ecb2dd7a1f08c6eac75e5ac210b522f88447ddc80525bc`. |
| Groq lifecycle | PASS, 12/12 stages | 24 synthetic chat requests; 17 successful answers; zero external attempts; six browser-residue checks; ledger SHA-256 `8f5b37390a51ee8fb9cca1e43e6e9f3cd7580d6abbf8c5e3144c9d180ad439a7`. |
| Grok/xAI lifecycle | PASS, 12/12 stages | 26 synthetic chat requests; 19 successful answers; zero external attempts; six browser-residue checks; ledger SHA-256 `a892a5660289e75ea2307777fb7e380f81d51f16286cad8dbd83d8c0865d5bce`. |
| Provider visual evidence | PASS | 13 headed-browser screenshots across saved credential, two answers, missing-key recovery, and re-added-key answer states. |
| Connected Channels | PASS, 6/6 cases | Telegram, Slack, and WhatsApp setup/cancel/masking/official-link/refresh paths; zero accessibility violations; zero unexpected external requests; mutation failed without the navigation fix and passed with it. |
| Established-user continuity | PASS | Before/after: six users, 35 conversations, 80 messages, 12 agents, 74 prompts; continuity audit `ok`; normalized bundle hash unchanged. |
| Upgrade failure recovery | PASS | Three synthetic escaped defects reproduced, rolled back without data loss, fixed with regressions, then the supported upgrade/restart completed healthy. |
| Owned uninstall | PASS | Five isolated listeners closed; recoverable backup directory mode `0700`; source checkout intact; helper correctly skipped because the ownership receipt recorded no helper ownership. |
| Nested product identity | PASS | Product merge `37fe3b7ea6f8091a554df69d88bf846961afbd30`; final pinned commit `85a2e326cd5672f00c927984f00a92c9b3f07f9c`; 14/14 product checks passed. |
| Parent candidate identity | PASS at review boundary | This report is part of the exact parent pull-request head; hosted checks bind their results to that immutable head SHA. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Easy Install non-Docker source path, Connected Accounts, and Connected Channels.
- Requirement: `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`.
- Use case: a new or established user runs one command, connects their account, and immediately uses
  the optimized public Viventium configuration without receiving owner data.
- QA case: `INST-033` / `INST-UC-019`.
- Expected result: a useful first answer, truthful optional setup, persistence, safe upgrade, and
  ownership-bounded removal.
- Actual evidence: headed provider/channel flows, live source upgrade/restart, stable synthetic
  counts/hash, automated suites, hosted checks, and exact component pins.
- Remaining gap or fix: none for the accepted source path; Apple distribution and provider-owned
  external activation remain separate boundaries.

## Failure And Recovery Coverage

- Missing provider configuration stays setup-pending and points back to Connected Accounts.
- Invalid credential, quota, provider unavailable, network failure, and disconnected states remain
  distinct and each provides a specific repair path.
- Disconnect prevents further provider requests; re-adding the credential restores use.
- Telegram worker unavailability remains scoped to Telegram and recovers without blocking chat.
- Slack and WhatsApp setup failures preserve existing active connection state rather than replacing
  it with a partial candidate.
- WhatsApp remains action-required until its stable public HTTPS callback is verified by Meta.
- Optional channel setup and vendor/network prerequisites never block installation or first chat.
- Collapsed responsive navigation no longer leaves an invisible sidebar above the account menu.

## Full-View Evidence Checklist

| Evidence surface | Required question | Evidence / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which contract is proven? | Installer/compiler doc 39, `INST-033`, and `INST-UC-019`. |
| Code owning path | Which path owns behavior? | Parent CLI/compiler/summary/launcher plus LibreChat custom endpoints, Background Cortex, navigation, Channels UI/API/transports. |
| Docs and nested docs/repos | What defines expected behavior? | Installer requirements/cases, channel cases/report, runtime QA map, and merged LibreChat source. |
| Scripts or harnesses | What exercised it? | Permanent provider lifecycle and connected-channel Playwright harnesses, continuity audit, installer/upgrade/uninstall CLI, release tests. |
| Local/external prerequisite state | What was healthy? | Local MongoDB, API, web, artifact listener, production client, and loopback providers; no external vendor credentials were used. |
| Logs | What confirms it? | Sanitized provider ledgers, seed bundle hash/count, successful upgrade health wait, and continuity status. |
| DB/state/persistence | What confirms it? | Aggregate before/after counts and stable public agent hash; no raw rows or IDs retained. |
| Generated/shipped artifact | What output was inspected? | Generated runtime config and aligned nested parent pins; no signed/notarized distribution artifact claimed. |
| Real user path | What was used like a user? | Public installer/upgrade/uninstall CLI and production-built headed browser setup/chat/Channels. |
| Visual/UX comparison | Did visible state match? | Yes; desktop/mobile controls, answers, errors, repair, refresh, and reopened Settings matched supporting state. |
| Not run / blocked | What remains outside this PASS? | Apple signing/notarization and real vendor account approval/message delivery require separate external authority. |

## User-Grade Evidence

- Surface exercised: public Easy Install/upgrade/uninstall CLI and production-built LibreChat in a
  headed Chromium browser.
- Real user path: run one command, register locally, add a provider key, chat twice, refresh/restart,
  repair failures, open Settings > Channels, inspect all three setups, reinstall, upgrade, and remove.
- Visible outcome: optimized agents and prompts were present; answers rendered; errors were specific;
  Telegram, Slack, and WhatsApp were one settings action away with only necessary fields.
- Expanded/detail state: masked credential fields, official links, Slack manifest, WhatsApp HTTPS
  prerequisite/callback guidance, desktop and 320-pixel navigation, keyboard and accessibility state.
- Persistence/reload result: two answers and account state survived refresh/restart; warm reinstall
  and upgrade preserved six users, 35 conversations, 80 messages, 12 agents, and 74 prompts.
- Local/external prerequisite state: local services and loopback synthetic providers were healthy;
  external vendor credentials, Apple signing, and notarization were intentionally absent.
- Evidence retrieval classification, if applicable: invalid credential, quota/rate limit, provider
  unavailable, network failure, and auth/config missing were distinct.
- Fallback path, if applicable: browser repair/re-entry restored each provider; optional channel
  degradation stayed scoped and did not require an unsafe fallback.
- Backend/log/DB confirmation: request counters proved disconnect caused no later request; aggregate
  DB counts, continuity status `ok`, and public bundle hash agreed with the visible result.
- Final model/runtime wording check: Groq and Grok/xAI remained distinct, source endpoint settings
  survived background initialization, Voice stayed deferred, and lab-only OpenClaw was absent.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for the headed browser and supported CLI paths that
  were actually run.

## Configuration And Artifact Alignment

- LibreChat final pinned source: `85a2e326cd5672f00c927984f00a92c9b3f07f9c`.
- Product implementation tree under user QA: `37fe3b7ea6f8091a554df69d88bf846961afbd30`;
  PR 72's reviewed head had the identical product tree.
- Nested hosted checks: 14 of 14 passed across Linux, Windows, API, packages, build, lint,
  accessibility, circular dependencies, and static inventory checks.
- Post-merge publishing distinction: the earlier merge triggered failing Docker Hub and Locize
  workflows because this public fork has no publisher credentials. PR 73 made both publishers
  explicitly opt-in; its post-merge Locize workflow skipped cleanly, and the Docker workflow did not
  trigger because no product path changed.
- Parent component lock and Native payload component manifest pin the same LibreChat commit.
- Groq and xAI source-template endpoints are supplied by the parent compiler instead of relying on
  machine-local defaults.
- Easy Install public setup/status omits lab-only OpenClaw.
- Source, generated configuration, runtime behavior, browser behavior, and the immutable component
  pin agree for the accepted source path.

## Automated Evidence

```bash
python -m pytest tests/release/ -q
npx playwright test --config=e2e/playwright.config.channels.ts
bin/viventium continuity-audit
bin/viventium upgrade --restart
bin/viventium uninstall
```

- Full parent release suite on the final source candidate: 1,569 passed, 31 skipped.
- Focused parent installer/compiler/lifecycle suite: 167 passed.
- LibreChat Background Cortex tests: 61 passed.
- LibreChat custom-endpoint tests: 41 passed.
- LibreChat package API suite: 458 passed.
- Connected Channels headed browser suite: 6 passed.
- Independent code, regression, and privacy reviews found no merge blocker.
- Final source diff, generated outputs, JSON, JavaScript/Python syntax, component pins, and public
  privacy scans passed locally; pull-request checks independently bind results to the reviewed head.

## Findings

- Defects: the live upgrade rehearsal found and fixed incomplete-system-Python selection,
  same-component migration handoff rejection, and parent/child restart lock contention.
- Regressions: each defect has a deterministic release regression and passed the real isolated
  upgrade after the fix.
- Flakes: none in the final headed channel/provider or upgrade acceptance runs.
- Environment issues: external vendor credentials and Apple distribution authority were unavailable
  and were not simulated as real external acceptance.
- Residual risks: third-party approval/policy changes and Apple distribution remain independently
  testable release boundaries.

## Public-Safety Review

- [x] No secret, token, password, cookie, or credential-bearing command.
- [x] No personal account, email, chat, prompt, attachment, database row, or customer data.
- [x] No local absolute path, username, hostname, machine name, private URL, or owner runtime dump.
- [x] No browser storage, Keychain content, raw environment, or provider payload.
- [x] Evidence uses only aggregate counts, public commit identities, and synthetic conclusions.

## External Boundaries

The following are not silently claimed by this source acceptance:

- Apple Developer ID signing and notarization of a final immutable Native payload;
- a provider-owned Telegram bot, Slack workspace app, or Meta Business app approval and real external
  inbound/outbound message, which requires credentials and external messaging authority belonging
  to the installing user; and
- macOS Keychain/TCC prompts for Custom Settings credentials, because Easy Install uses encrypted
  per-user browser-connected credentials.

These boundaries do not leave the non-Docker source Easy Install path partial. They remain explicit
distribution or third-party activation checks to run when the necessary external authority exists.
