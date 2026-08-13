# Native Handoff And Store Lifecycle Source QA — 2026-08-13

## Summary

- Result: PARTIAL.
- Build/source under test: merged LibreChat `541a4c4fdac97f54333d25a79de9c34e4319db04`
  and merged GlassHive `987c98b399c672cc45344b69c5dcb5e9612bdf9c`.
- Runtime/artifact under test: source checkouts and generated parent component manifests only.
- Environment: isolated clean publication checkouts; the installed runtime was not changed.
- Tester: Codex with independent read-only reviews and hosted checks.
- Related change: parent component-pin candidate for the post-union integration repairs.

Post-union QA exposed two narrow integration edges: worker-native tool ownership removed the
configured Main-to-Connected Accounts topology, and SQLite/background-service shutdown did not
share one proven quiescent lifetime. The fixes preserve the existing design. Native providers still
own ordinary tools; only bounded Agent Builder transfers cross the graph. The existing Store remains
the persistence owner, with deterministic connection closure and shutdown ordering.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| CA-HANDOFF-018 | PASS | Focused API/package graph suites and two independent reviews | Main binds only the structural transfer, the specialist returns evidence to Main, and denied or missing targets leave a runnable Main-only graph. |
| CA-HANDOFF-019 | PARTIAL | Exact merged pins, strict bootstrap, and source regressions pass | Installed Telegram and browser acceptance remains pending until the exact parent merge is activated. |
| Store lifecycle integration | PASS | Full GlassHive suite: 1,252 passed and 5 existing skips | Deterministic regressions prove reconciliation and every service loop quiesce before Store close. |

## Natural User Use Case Checklist

| Use Case | Natural user action | Real surface used | Result | Visible evidence | Supporting evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| Connected-account happy path | Ask Main for connected-account status and receive a specialist-backed answer authored by Main | Telegram and LibreChat browser | PARTIAL | Not run against the final parent pin because it was not yet merged or installed | Real graph tests and exact source/pin review pass | Run after supported activation. |
| Missing or denied specialist | Ask Main when the handoff target is unavailable or unauthorized | LibreChat Agent graph | PARTIAL | No final installed browser turn was run | Real graph regression proves a non-enumerating Main-only turn | Repeat in browser after activation. |
| Persistence/reload/restart | Refresh and restart, then repeat the connected-account request | Telegram and LibreChat browser | PARTIAL | Not run against the final installed artifact | Upgrade-baseline generator and parent pin tests pass | Correlate visible result, logs, and persisted message after activation. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: native connected-account handoff plus GlassHive Store lifecycle continuity.
- Requirement: preserve existing specialist behavior and user-managed agent fields without runtime
  drift, while preventing Store close beneath active background work.
- Use case: Main transfers once for connected-account evidence, receives the result, and authors the
  final response; restart does not lose managed topology or runtime state.
- QA case: CA-HANDOFF-018 and CA-HANDOFF-019.
- Expected result: exact merged components, isolated specialist tools, Main-authored final output,
  truthful persistence, and deterministic shutdown.
- Actual evidence: source and full automated suites pass; exact configured component pins validate;
  independent reviews report no P0–P2 blocker.
- Remaining gap or fix: installed Telegram and browser QA, refresh, restart, and DB/log correlation
  must run after this exact parent merge is activated.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement and natural use case are proven? | CA-HANDOFF-018 source behavior passes; CA-HANDOFF-019 installed behavior remains PARTIAL. |
| Code owning path | Which code owns the behavior? | LibreChat Agent graph authorization/tool binding and GlassHive provider/service/Store lifecycle. |
| Docs and nested docs | Which sources define expected behavior? | Connected-account cases, installer lifecycle inventory, and merged nested source-of-truth bundles. |
| Scripts or harnesses | What exercised the change? | LibreChat graph/seeder suites, official managed-baseline generator, GlassHive lifecycle/full suite, and parent bootstrap/release suites. |
| Local/external prerequisite state | Which dependency state was proven? | Public Git origins and exact merge commits were fetched; private OAuth state was not read for source QA. |
| Logs | Which logs confirm the result? | Hosted-check conclusions confirm build/API/release execution; installed runtime logs remain pending. |
| DB/state/persistence | Which state confirms it? | Synthetic Store lifecycle tests pass; live message and agent DB checks remain pending. |
| Generated/shipped artifact | Which artifact was inspected? | Parent lock and Native LibreChat manifest match; installed artifact identity remains pending. |
| Real user path | Which user surface was used? | No final Telegram or browser turn was run because the exact parent pin was not yet merged and active. |
| Visual/UX comparison | Does visible behavior match supporting evidence? | BLOCKED until post-activation Telegram and browser QA. |
| Not run / blocked | What cannot be replaced by source evidence? | Real user-path evidence, refresh/restart persistence, and installed artifact/log/DB correlation. |

Source inspection, tests, logs, and DB/state/persistence evidence cannot replace required user-path
evidence. The publication result therefore remains PARTIAL until the post-activation run.

## User-Grade Evidence

- Surface exercised: Telegram and LibreChat browser are the required final surfaces; neither was
  exercised against the not-yet-merged parent artifact during this source-only run.
- Real user path: The natural connected-account request, specialist transfer, Main synthesis,
  refresh, and restart sequence remains scheduled for post-activation QA.
- Visible outcome: No final installed visible outcome is claimed; source regressions alone do not
  establish what Telegram or the browser will display.
- Expanded/detail state: Agent graph activity and message details were not inspected in the final
  installed browser runtime because the candidate was not activated.
- Persistence/reload result: The final installed refresh/restart result is pending; only synthetic
  reconciliation and Store lifetime persistence were exercised.
- Backend/log/DB confirmation: Final installed provider runs, delivery acknowledgement, message
  state, and runtime logs remain pending; only public-safe automated and hosted evidence is recorded.
- Final model/runtime wording check: Pending a real Telegram and browser response from the exact
  active artifact; no model wording is inferred from unit tests.
- Substitution check: automated tests, source inspection, hosted results, logs, and synthetic
  Store state support the candidate but do not substitute for required visible UI, persistence,
  or wording evidence.

## Automated Evidence

- LibreChat focused handoff API/package suites: 148 passed across the final review matrix.
- LibreChat managed-agent migration generator: exact public-history check passed; seeder suite 38/38.
- LibreChat hosted PR checks: package build, API/package/data suites, lint, circular dependencies,
  and unused-key/package scans all passed.
- GlassHive lifecycle suite: 10/10; deterministic blocked-loop repetition: 20/20.
- GlassHive complete runtime suite: 1,252 passed and 5 existing skips.
- Parent focused compiler/bootstrap/release suites: 567/567.
- Strict configured component validation: all six selected components clean at exact merged pins.
- Diff, credential, local-path, identity, and gitleaks scans: passed.

## Findings

- Defects fixed: worker-native graph selection erased configured handoff topology; detached
  reconciliation and service loops could outlive Store shutdown.
- Regressions found: none after the final nested merges and parent pin retest.
- Flakes: no product-test flake; parent release tests emitted cleanup-only warnings for copied
  ignored virtual environments while exiting successfully.
- Environment issues: a bare system Python lacked pytest; the existing component environment ran
  the final parent matrix without installing dependencies into the candidate.
- Residual risks: installed Telegram/browser behavior, refresh/restart persistence, OAuth status,
  and installed artifact identity remain post-activation gates.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots, personal emails, account identifiers,
  or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values,
  or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports,
  App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, commit hashes, and conclusions only.
