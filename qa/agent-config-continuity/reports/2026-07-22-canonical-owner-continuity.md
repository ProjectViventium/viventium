# Canonical Built-In Agent Owner Continuity QA Run - 2026-07-22

## Summary

- Result: `PARTIAL`; automated source and rebuilt-helper checks pass, while the replacement
  exact-payload browser/DB/ACL restart path was not run.
- Build/source under test: isolated Easy Install release-candidate parent and LibreChat source trees
- Runtime/artifact under test: source scripts, synthetic process/database/state harnesses, and rebuilt universal prebuilt helper; no installed payload
- Environment: isolated local test processes with synthetic non-personal state
- Tester: Codex independent implementation/QA pass
- Related change: durable exact administrator ownership across source and Native restart

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `AGCFG-006` | `PARTIAL` | Native payload test file `85 passed`; macOS helper suite `31 passed`; combined LibreChat seed suite `30 passed` | Automated source and rebuilt-helper checks pass; replacement exact-payload browser/DB/ACL restart path not run |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `AGCFG-UC-006` | Complete first admin, add a second synthetic administrator, restart, and open the shipped main agent | Supported Native Easy Install browser path was not available; source/Native script harnesses only | `PARTIAL` | No browser-visible evidence captured | Synthetic exact-ID, file-mode, baseline, author-selection, ACL-verifier, and cleanup assertions; requirement and case updated | Run the replacement exact payload through browser, DB/ACL inspection, and two restarts |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: canonical built-in main/background agent ownership
- Requirement: `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
- Use case: first admin configures Viventium, later adds another administrator, and restarts
- QA case: `AGCFG-006` / `AGCFG-UC-006`
- Expected result: the first verified administrator remains owner without query-order inference
- Actual evidence: exact-owner Native recovery/verification, protected baseline owner selection,
  legacy closed-state canonical-author backfill without administrator enumeration or DB writes,
  deleted/demoted production-filter rejection, stable health/doctor recovery, zero-write seeder
  preflight, unsafe-state rejection, and bounded cleanup regressions
- Remaining gap or fix: replacement immutable payload browser, Mongo author/ACL, and restart acceptance

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Installer/config compiler owner contract; `AGCFG-006` / `AGCFG-UC-006` |
| Code owning path | Which code path owns the behavior? | Native first-admin recovery/verifier and LibreChat agent seeder |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | Installer/config compiler requirement plus Agent Config Continuity README/cases |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Native payload pytest harness and LibreChat seed Jest harness |
| Local/external prerequisite state | Which required local service, provider, Docker-backed sidecar, OAuth grant, API key, model, or hosted dependency was proven healthy or degraded? | No provider, Docker, OAuth, model, or external service required by the focused synthetic tests |
| Logs | Which sanitized logs confirm or contradict the result? | Test exit/results only; no runtime logs claimed |
| DB/state/persistence | Which sanitized state, DB count/hash, persisted message, config, or artifact confirms it? | Synthetic owner state remained byte-identical; mode-`0600` baseline retained the canonical synthetic ID |
| Generated/shipped artifact | Which generated config, compiled bundle, prebuilt helper, or installed artifact was inspected when applicable? | Rebuilt prebuilt helper is a hash-aligned universal `arm64`/`x86_64` Mach-O; no replacement installed payload was substituted |
| Real user path | Which browser/computer, Telegram, voice, installer, CLI, MCP/tool, scheduler, or GlassHive path was used like a user? | Required Native Easy Install browser first-admin/multi-admin path was not run; result remains partial |
| Visual/UX comparison | Does the visible UI/UX or delivered result match the expected behavior and supporting evidence? | Not evaluated; actionable recovery wording was asserted only at the script boundary |
| Not run / blocked | Which required surface was not run, and why is the result partial or blocked? | Replacement exact payload and safe disposable headed machine were unavailable to this focused lane |

## User-Grade Evidence

- Surface exercised: synthetic Native installer/recovery and LibreChat source-seed process surfaces; the required browser surface was not exercised.
- Real user path: the supported Native Easy Install browser first-admin, second-admin, restart, and Agent Builder journey was not run.
- Visible outcome: no visible UI outcome was captured; this report does not claim browser acceptance.
- Expanded/detail state: synthetic protected state, exact user query, agent authors, ACL verifier, and managed baseline were inspected by assertions only.
- Persistence/reload result: synthetic restart preserved exact owner state bytes; replacement-payload reload remains not run.
- Local/external prerequisite state: no external provider dependency applied; a disposable replacement Native payload environment was unavailable.
- Evidence retrieval classification, if applicable: not applicable to this owner-continuity flow.
- Fallback path, if applicable: no browser/computer fallback can replace the missing exact installed payload; none was claimed.
- Backend/log/DB confirmation: synthetic database collection behavior and state files confirmed exact-ID selection; no live Mongo database was inspected.
- Final model/runtime wording check: invalid protected owner state and a closed state without an
  owner ID returned restore/promote-or-backup guidance without a traceback, Native CLI propagated
  it, and helper source/build selected Native recovery instead of Docker advice; headed helper
  rendering remains not run.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting evidence, not substitutes for the required visible-UI, persistence, DB/ACL, and installed-artifact steps.

## Automated Evidence

```bash
uv run --with pytest --with pyyaml python -m pytest tests/release/test_native_payload_assembler.py -q
uv run --with pytest python -m pytest tests/release/test_macos_helper_install.py -q
(cd viventium_v0_4/LibreChat/api && npm run test:ci -- test/scripts/viventium-seed-agents.test.js --runInBand)
uv run --with pytest --with pyyaml python -m pytest tests/release/test_qa_operating_contract.py -q
swift build --package-path apps/macos/ViventiumHelper
node --check scripts/viventium/native_first_admin_recovery.js
node --check scripts/viventium/native_verify_agent.js
node --check viventium_v0_4/LibreChat/scripts/viventium-seed-agents.js
```

## Findings

- Defects: fixed owner re-inference after later administrators, arbitrary two-admin verification,
  failure to recover an historical closed state without an owner ID after a second administrator,
  missing source canonical-owner persistence, unsafe existing-state acceptance, raw health/doctor
  failures for a closed state without an owner ID, late owner-author mismatch detection after ACL
  mutation, log-only/incorrect-Docker stored-owner recovery, and missing deterministic `EPERM`
  cleanup coverage. Deleted and demoted exact-owner production filters now have explicit regressions.
- Regressions: none in the completed Native and combined seed suites.
- Flakes: none observed.
- Environment issues: replacement exact-payload headed environment was not available to this lane.
- Residual risks: real helper recovery visibility, exact-payload first-admin, multi-admin restart, Mongo author/ACL persistence, and signed/notarized artifact acceptance remain open.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
