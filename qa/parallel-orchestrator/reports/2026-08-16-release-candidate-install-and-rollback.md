# Parallel Work QA Run - 2026-08-16

## Summary

- Result: PARTIAL overall; `PWK-018` PASS and `PWK-032` PARTIAL.
- Build/source under test: parent `4a10643b911f147a917f2623b5e0d2e09308f82e`, LibreChat
  `2842e7b9534fb6ade7050d14f3a191c8caccfe00`, GlassHive
  `6167132ad0aa1d8d6d30746fe9c9631f56310d9f`.
- Runtime/artifact under test: a new public-installer checkout with freshly compiled client and
  package artifacts, isolated state, and isolated loopback ports.
- Environment: local macOS development QA; disposable synthetic account and state only.
- Tester: Codex.
- Related change: local GlassHive account-API port derivation, startup config-log redaction,
  credential-safe launcher status, Python 3.10/3.11 compiler compatibility, a derived
  LiveKit-only runtime secret, and one-way-safe secret recovery.

The clean source/pin/build/install/runtime contract now passes. The wider Parallel Work release does
not: provider-backed running controls, scheduler delivery, maximum-load fairness, two-owner real
surfaces, and rollback with running work remain incomplete, so deployment stays dark and focused.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `PWK-001` | PARTIAL | Headed Web toggle, account API response, reload | Focused→parallel persisted; unlinked safe-link and timing sample remain. |
| `PWK-004` | PARTIAL | Empty roster, retained failed card, rollback, Dismiss, reload | Stale/unavailable and Voice parity remain. |
| `PWK-005` | PARTIAL | Headed Web Dismiss with accepted action and reload | Running Pause/Steer/Retry and lost-response user paths remain. |
| `PWK-018` | PASS | Exact hashes/pins, generated runtime contract, built artifacts, healthy processes, safe logs, clean teardown | All delivery layers agree and remain dark/focused. |
| `PWK-032` | PARTIAL | Deployment disablement retained failed work and exact Dismiss through reload | No mission was running; callbacks, delivery, capacity reduction, Telegram, and Voice remain. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `PWK-UC-001` | Enable Parallel work and reload. | Headed Playwright Web | PARTIAL | Switch became checked; success toast appeared; checked state survived full reload. | Account API returned available/parallel; one synthetic account held the parallel preference. | Telegram current-candidate parity, unlinked safe-link, rapid running missions. |
| `PWK-UC-002` | Inspect empty work and work retained after rollback. | Headed Playwright Web | PARTIAL | Empty state was explicit. After rollback, the toggle hid but the failed card remained until Dismiss. | Deployment API was dark after restart; retained card and preference existed before Dismiss. | Stale/unavailable and Voice paths. |
| `PWK-UC-003` | Dismiss exact terminal work and reload. | Headed Playwright Web | PARTIAL | Accepted-action toast appeared; the card disappeared and stayed absent after reload. | No new delegation or run action was created by the degraded launch; Dismiss affected only the terminal card. | Remaining controls, races, and lost-response paths. |
| `PWK-UC-004` | Attempt work without a connected provider. | Headed Playwright Web | PARTIAL | Main reported that isolation was unavailable and no task was created; card stated that no worker started. | Provider account was disconnected; no background delegation/action row existed. | Connected-provider execution, reauthorization, expiry, quota, and files/media. |
| `PWK-UC-008` | Clean install, inspect shipped layers, enable, and roll back. | Public CLI plus headed Web | PARTIAL | Clean runtime was dark; separate isolated headed run enabled/reloaded and disabled/reloaded truthfully. | Exact refs/pins, generated API/MCP/UI origins, compiled artifacts, process roots, safe logs, and closed teardown ports passed. | Rollback with running work and remaining isolation/provider gates. |
| `PWK-UC-012` | Disable automatic admission while retaining work. | Headed Playwright Web plus runtime restart | PARTIAL | New-admission UI hid; failed work remained visible and dismissible after restart/reload. | Dark deployment state and retained account preference persisted. | Running mission, callback/delivery, capacity change, Telegram, and Voice. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: account-wide Parallel Work delivery and rollback.
- Requirement: [Parallel Work rollout and completion gates](../../../docs/requirements_and_learnings/55_Parallel_Work_Orchestration.md#rollout-and-completion-gates).
- Use case: install the exact candidate, expose it only in an isolated enabled runtime, reload it,
  disable new admission, and verify retained work.
- QA case: `PWK-001`, `PWK-004`, `PWK-005`, `PWK-018`, and `PWK-032`.
- Expected result: every shipped layer agrees; default remains dark/focused; enabled preference and
  retained work survive reload; rollback never invents success or hides existing work.
- Actual evidence: exact remote/pin parity, new installer checkout, built artifacts, healthy local
  processes, safe startup logs, headed toggle/reload, explicit degraded wording, retained card,
  persisted Dismiss, and complete disposable teardown.
- Remaining gap or fix: connect a synthetic provider and rerun A/B/C, running controls, callback and
  scheduler delivery, maximum-load/fairness, real two-owner surfaces, and running-work rollback.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Requirement 55; `PWK-001`, `PWK-004`, `PWK-005`, `PWK-018`, `PWK-032`; use cases above. |
| Code owning path | Which code path owns the behavior? | Config compiler, public launchers, LibreChat config loader, account orchestration API, Active Work UI. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | Requirement 55, this QA catalog, pinned LibreChat and GlassHive repos. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Public installer/start CLI, release pytest suite, LibreChat backend/client suites, Playwright CLI. |
| Local/external prerequisite state | Which required dependency was healthy or degraded? | Local runtime health passed; the synthetic provider account was disconnected, so background execution failed closed. |
| Generated/shipped artifact | Which artifact was inspected? | Exact refs/pins, compiler-derived non-default GlassHive API/MCP/UI origins without an input runtime-port override, client build, API/data-provider package builds, shipped helper, clean process roots. |
| Runtime API | Did the generated account API origin reach the process actually bound there? | Yes. The generated bind was the non-default account-API port; an authenticated `GET /v1/projects` returned 200. |
| Logs | Which sanitized logs confirm or contradict the result? | Thirteen persisted service logs plus the launcher stream: one validated-config message, one health-pass marker, zero full-config/private-instruction dumps, zero matches across 23 configured credential values, zero duplicate-key warnings. |
| DB/state/persistence | Which sanitized state confirms it? | One synthetic account retained parallel preference; one conversation survived restart; no background delegation/action row was created by the degraded ask. |
| Real user path | Which real path was used? | Headed Web toggle, prompt, card inspection, restart, rollback, Dismiss, and reload; public install/start/stop CLI. |
| Visual/UX comparison | Did visible UX match? | Yes for the scoped branches: explicit empty/degraded copy, persistent toggle, retained rollback card, persistent Dismiss. |
| Not run / blocked | Which required surface was not run? | Provider-backed mission completion, running controls, scheduler, maximum load/fairness, two-owner Web/Telegram, and running-work rollback. |

## User-Grade Evidence

- Surface exercised: headed Web and public installer/CLI.
- Real user path: sign in with a disposable synthetic non-admin account; observe dark state; enable the
  isolated deployment; toggle Parallel; reload; attempt one synthetic mission; inspect failure card;
  disable deployment; restart; inspect retained work; Dismiss; reload.
- Visible outcome: the toggle and roster appeared only when effective availability was true; the
  preference persisted; missing provider/isolation was explicit; rollback hid new admission without
  hiding work; Dismiss persisted.
- Expanded/detail state: failed work stated that no worker was started; no fabricated running or
  completed claim appeared.
- Persistence/reload result: conversation, preference, retained card, and later Dismiss state each
  matched the preceding visible action after reload.
- Local/external prerequisite state: local services passed health checks; provider authorization was
  missing and classified distinctly rather than treated as an empty result.
- Evidence retrieval classification, if applicable: auth/config missing for provider-backed mission;
  local runtime otherwise healthy.
- Fallback path, if applicable: no unsafe host/provider fallback was used.
- Backend/log/DB confirmation: account preference persisted; no background delegation/action rows
  existed for the degraded ask; clean runtime refs, pins, processes, and logs matched source.
- Final model/runtime wording check: the visible response said the background start was blocked and no
  task was created, matching the card and persistence evidence.
- Substitution check: automated/source/log/DB evidence supports, but does not replace, the headed Web
  and public CLI evidence above.

## Automated Evidence

```bash
# Parent release gate
.venv/bin/python -m pytest tests/release/ -q

# Compiler and launcher regression
.venv/bin/python -m pytest tests/release/test_config_compiler.py -q
bash -n viventium_v0_4/viventium-librechat-start.sh viventium_v0_4/viventium-start-all.sh

# LibreChat regression
cd viventium_v0_4/LibreChat
CI=true npm run test:api -- --runInBand --watch=false

# Public clean install and isolated runtime
bin/viventium install --headless --config-input path/to/private-temporary-config.yaml --no-start
bin/viventium start
```

- Parent release: 950 passed, 2 skipped.
- Compiler: 134 passed; the exact compiler also parsed successfully under Python 3.10 and 3.11.
- LibreChat backend after config-log hardening: 4,065 passed, 19 skipped.
- Earlier unchanged-surface final-candidate evidence: client 1,396/1,396; data provider 814/814 with
  one skip; data schemas 403/403 with three skips; production build passed.

## Findings

- Defects: local custom-port compilation originally left the GlassHive provider account API on the
  legacy port, making effective availability false. Startup then exposed interpolated config values,
  launcher status exposed the LiveKit key/value prefix, Python 3.10/3.11 could not parse one
  multiline f-string, a short call-session secret caused LiveKit to log its key identifier while
  rejecting startup, and the legacy recovery map could invert the derived LiveKit secret back into
  the base call-session secret. All six are fixed and regression-guarded; the final LiveKit secret is
  derived, service-specific, 64 characters, absent from every scanned log, and never used as a base
  recovery source.
- Regressions: none remain in the scoped install/log/toggle/rollback branches.
- Flakes: the full backend suite still reports its known forced-exit warning after all assertions pass;
  no scoped test failed.
- Environment issues: synthetic provider authorization was intentionally absent; running mission
  acceptance therefore remains blocked.
- Residual risks: the remaining case catalog is authoritative. This report does not convert any
  provider-backed, scheduler, concurrency, owner-isolation, or running-work rollback item to PASS.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
