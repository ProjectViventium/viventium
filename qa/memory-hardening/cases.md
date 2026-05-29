# Memory Hardening QA Cases

## Case ID Convention

Use stable `MEMHARD-NNN` IDs for memory hardening cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `MEMHARD-001` | Memory hardening runs are bounded, public-safe, and preserve durable facts while pruning stale/private noise. | User-visible behavior matches source, docs, persisted state, and logs | memory hardener, reports, runtime env, synthetic memories | `tests/release/test_memory_hardening_contract.py` plus user-grade QA when visible | PASS 2026-05-27 ([follow-up report](../scheduling-cortex/reports/2026-05-27-glasshive-stale-project-rag-rca.md)); scheduled apply had already completed, then transcript-only repair finished with all transcript index rows processed, zero saved-memory changes, and zero vector-presence errors |
| `MEMHARD-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-05-27 ([report](reports/2026-05-27-nightly-routines-health-review.md)); public report uses sanitized counts, timestamps, statuses, and omits raw runtime/browser evidence |
| `MEMHARD-003` | Model-backed hardening and transcript ingest respect the local machine power budget. | Battery or thermally constrained laptops do not start expensive model-backed maintenance unless the operator explicitly overrides the power gate. | memory hardener CLI, helper transcript ingest, scheduled operator job | `tests/release/test_memory_hardening_contract.py` power-gate regressions plus live battery/thermal status evidence when visible | PARTIAL 2026-05-27 ([report](reports/2026-05-27-heat-power-gate-rca.md)); wrapper skip and automation policy were verified, but helper run-anyway/status visibility remain follow-ups |
| `MEMHARD-004` | Model-backed transcript maintenance remains efficient while plugged in. | Plugged-in laptops avoid repeated one-file model/probe/vector startup loops without stopping Viventium or Docker. | Node hardener, wrapper, helper, status CLI, generated env | `tests/release/test_memory_hardening_contract.py`, `tests/release/test_config_compiler.py`, `tests/release/test_macos_helper_install.py`, live cooldown/status smoke | PASS 2026-05-27 ([report](reports/2026-05-27-plugged-in-efficiency-qa.md)) |

## `MEMHARD-001` - Core User Flow

- Requirement: Memory hardening runs are bounded, public-safe, and preserve durable facts while pruning stale/private noise.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_memory_hardening_contract.py` plus any narrower feature tests discovered during implementation.
- Last run: PASS 2026-05-27
  ([follow-up report](../scheduling-cortex/reports/2026-05-27-glasshive-stale-project-rag-rca.md));
  the macOS LaunchAgent fired at the documented 03:00 local schedule and the follow-up
  transcript-only repair completed after RAG/PGVector recovery. Final status reported
  `lock_held=false`, all transcript index rows processed, zero saved-memory changes in the repair
  batches, and zero vector-presence errors in the final apply-mode check.

## `MEMHARD-002` - Public-Safe Evidence Record

- Requirement: public QA artifacts must be reproducible and free of secrets, personal data, local paths, raw IDs, and private screenshots.
- Risk covered: a useful local QA run cannot be safely reviewed or published.
- Preconditions: a dated QA report is created for this feature.
- Steps:
  1. Review the report and related diffs for local absolute paths, account identifiers, tokens, raw logs, raw DB rows, private chats, and screenshots with private content.
  2. Keep raw/private evidence outside the public repo and summarize only public-safe counts, statuses, hashes, and conclusions.
  3. Link the report back to this case and the owning requirement doc.
- Expected result: the public report proves the behavior without leaking private/local data.
- Forbidden result: a report includes private transcripts, account identifiers, raw runtime dumps, local home paths, tokens, or secret-bearing command lines.
- Evidence to capture: public-safety scan result and link to the sanitized report.
- Automation: public-safety pattern scan plus relevant release tests.
- Last run: PASS 2026-05-27
  ([report](reports/2026-05-27-nightly-routines-health-review.md)); report sanitization was reviewed
  for private paths, accounts, raw transcript text, ids, secrets, launch tokens, and raw browser
  snapshots.

## `MEMHARD-003` - Local Power Budget For Model Work

- Requirement: model-backed hardening, transcript ingest, and maintenance audits must not start
  expensive local model work while the laptop is on battery or under a recorded thermal/performance
  warning unless the operator explicitly approves that override.
- Risk covered: the local runtime stays up, but background maintenance keeps the laptop hot and
  blocks normal status/debug work.
- Preconditions: local Viventium checkout is the active runtime checkout; the machine is on battery
  or `thermal_state_constrained()` is simulated in the release test.
- Steps:
  1. Run the memory-hardening wrapper on battery with `ingest-transcripts --apply --ignore-idle-gate --json`.
  2. Confirm the command exits 0 with `status: skipped`, `reason: on_battery_power`, and no spawned
     Node/model child.
  3. Confirm `--ignore-power-gate` alone does not permit non-interactive model-backed work on
     battery; it must be paired with `VIVENTIUM_MEMORY_HARDENING_ALLOW_POWER_OVERRIDE=1`.
  4. Inspect the nightly QA automation contract and confirm it reports power-budget skips instead of
     passing `--ignore-power-gate`.
  5. Confirm local prod/dev status commands still work after stopping any pre-change maintenance run.
- Expected result: model-backed maintenance skips on battery/thermal constraint, reports the skip
  clearly, and leaves Viventium local prod running.
- Forbidden result: the audit or helper treats heat as a reason to stop local prod, delete Docker
  state, or force model work with `--ignore-power-gate` without an operator request.
- Evidence to capture: sanitized power source, command result, process absence, release-test result,
  automation prompt policy, and a fresh local-runtime status check.
- Automation: `tests/release/test_memory_hardening_contract.py` power-gate regressions.
- Last run: PARTIAL 2026-05-27 ([report](reports/2026-05-27-heat-power-gate-rca.md)); wrapper,
  tests, live battery skip, and automation policy were verified. Remaining gaps are helper
  run-anyway UX, last-skipped status surfacing, read-only CLI lock decoupling, and shared adoption by
  other model-backed maintenance entrypoints.

## `MEMHARD-004` - Plugged-In Efficiency For Transcript Maintenance

- Requirement: plugged-in model-backed transcript maintenance must remain bounded by a Node-owned
  cooldown, a transcript batch floor, and a wrapper batch cap so repeated shell/helper invocations
  do not keep the laptop hot.
- Risk covered: a loop of successful one-file `ingest-transcripts --apply --until-caught-up` runs
  repeatedly starts Python, the CLI lock path, Node, Mongo, model calls, and vector lifecycle work.
- Preconditions: local checkout and generated runtime config exist; a synthetic marker or transcript
  source is available for a public-safe smoke.
- Steps:
  1. Confirm `parseArgs` floors apply-mode transcript batches to at least 5 files by default.
  2. Confirm a recent public efficiency marker makes a second model-backed apply return
     `status: skipped`, `reason: maintenance_cooldown`, before Mongo/model work.
  3. Confirm `--ignore-power-gate` and its env override do not bypass the cooldown; only the
     separate efficiency override can.
  4. Confirm helper manual ingest uses one bounded interactive maintenance batch and keeps the power
     gate in force.
  5. Confirm `memory-harden status` can inspect state without taking the global CLI lock.
- Expected result: Viventium local prod remains running; transcript catch-up is resumable but bounded;
  repeated plugged-in invocations cool down instead of running one-file model loops.
- Forbidden result: stopping Viventium/Docker, deleting programs, relying on a Python-only guard, or
  treating a power override as an efficiency override.
- Evidence to capture: sanitized process/root-cause summary, release-test result, generated env
  values, helper/source or shipped-artifact evidence, cooldown/status smoke output, and remaining
  runtime gaps.
- Automation: `tests/release/test_memory_hardening_contract.py`,
  `tests/release/test_config_compiler.py`, and `tests/release/test_macos_helper_install.py`.
- Last run: PASS 2026-05-27
  ([report](reports/2026-05-27-plugged-in-efficiency-qa.md)); release tests, helper artifact,
  read-only status, process scan, and synthetic cooldown smoke passed. A real local efficiency
  marker will appear after the next operator-approved post-fix model-backed apply.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Memory Hardening. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `MEMHARD-UC-001` | On memory hardener, reports, runtime env, synthetic memories, verify that memory hardening runs are bounded, public-safe, and preserve durable facts while pruning stale/private noise. | owning requirement for `MEMHARD-001` / `MEMHARD-001` | memory hardener, reports, runtime env, synthetic memories | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MEMHARD-001. | User-visible behavior matches source, docs, persisted state, and logs | PASS 2026-05-27 ([follow-up report](../scheduling-cortex/reports/2026-05-27-glasshive-stale-project-rag-rca.md)); scheduled apply and transcript vector lifecycle now both have successful local evidence |
| `MEMHARD-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `MEMHARD-002` / `MEMHARD-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MEMHARD-002. | The user sees an honest setup, retry, or degraded-state result for MEMHARD-002; no fake success is accepted. | PASS 2026-05-27 ([report](reports/2026-05-27-nightly-routines-health-review.md)) |
| `MEMHARD-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `MEMHARD-002` / `MEMHARD-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MEMHARD-002. | MEMHARD-002 remains correct after the persistence or parity step and final wording matches evidence. | PASS 2026-05-27 ([report](reports/2026-05-27-nightly-routines-health-review.md)) |
| `MEMHARD-UC-004` | On battery or thermal constraint, run or audit model-backed memory hardening. | owning requirement for `MEMHARD-003` / `MEMHARD-003` | memory hardener CLI, helper transcript ingest, scheduled operator job | Source, owning requirement doc, case steps, process table, local-runtime status, and release-test evidence that apply to MEMHARD-003. | The user sees an honest skipped/degraded result instead of surprise expensive model work. | PARTIAL 2026-05-27 ([report](reports/2026-05-27-heat-power-gate-rca.md)); wrapper and automation policy verified; helper status/override UX remains |
| `MEMHARD-UC-005` | While plugged in, run or repeat transcript maintenance. | owning requirement for `MEMHARD-004` / `MEMHARD-004` | Node hardener, wrapper, helper, status CLI, generated env | Source, owning requirement doc, case steps, public marker, generated config, helper artifact, and release-test evidence that apply to MEMHARD-004. | The user sees a bounded batch, cooldown skip, or status result instead of repeated one-file model loops. | PASS 2026-05-27 ([report](reports/2026-05-27-plugged-in-efficiency-qa.md)) |

## Release Test Traceability

- `tests/release/test_memory_hardening_contract.py`
