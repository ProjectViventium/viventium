# Memory Hardening QA Cases

## Case ID Convention

Use stable `MEMHARD-NNN` IDs for memory hardening cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `MEMHARD-001` | Memory hardening runs are bounded, public-safe, and preserve durable facts while pruning stale/private noise. | User-visible behavior matches source, docs, persisted state, and logs | memory hardener, reports, runtime env, synthetic memories | `tests/release/test_memory_hardening_contract.py` plus user-grade QA when visible | SKIPPED/PASS-SAFETY 2026-06-11 ([nightly review](reports/2026-06-11-nightly-routines-health-review.md)); launchd receipt fired and finalized with `on_battery_power`, so no model/vector work was expected today; latest model-backed run remains the clean Jun 8 OpenAI/GPT-5.5 apply |
| `MEMHARD-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-06-11 ([nightly review](reports/2026-06-11-nightly-routines-health-review.md)); report uses sanitized counts/statuses/timestamps only, deletes private Playwright snapshots from the run, and omits raw prompts, transcripts, memory values, tokens, local paths, account identifiers, and callback payloads |
| `MEMHARD-003` | Model-backed hardening and transcript ingest respect the local machine power budget. | Battery or thermally constrained laptops do not start expensive model-backed maintenance unless the operator explicitly overrides the power gate. | memory hardener CLI, helper transcript ingest, scheduled operator job | `tests/release/test_memory_hardening_contract.py` power-gate regressions plus live battery/thermal status evidence when visible | PASS/SKIPPED 2026-06-11 ([nightly review](reports/2026-06-11-nightly-routines-health-review.md)); scheduled receipt recorded `on_battery_power`, later audit observed AC power and no thermal/performance warning, and no power or idle override was used |
| `MEMHARD-004` | Model-backed transcript maintenance remains efficient while plugged in. | Plugged-in laptops avoid repeated one-file model/probe/vector startup loops without stopping Viventium or Docker. | Node hardener, wrapper, helper, status CLI, generated env | `tests/release/test_memory_hardening_contract.py`, `tests/release/test_config_compiler.py`, `tests/release/test_macos_helper_install.py`, live cooldown/status smoke | PASS 2026-05-27 ([report](reports/2026-05-27-plugged-in-efficiency-qa.md)) |
| `MEMHARD-005` | New installs and upgrades schedule memory hardening for eligible local users without hardcoded operator identity. | A new user with memories enabled is covered by the 03:00 local hardening job automatically, and an intentionally ineligible user gets an honest healthy skip. | installer config, generated env, LaunchAgent sync, hardener eligibility | `test_default_nightly_routines.py`, `test_wizard.py`, `test_config_compiler.py`, `test_cli_upgrade.py` | PASS-SAFETY 2026-06-11 ([nightly review](reports/2026-06-11-nightly-routines-health-review.md)); active LaunchAgent used the direct wrapper with `--trigger launchd`, produced a live public-safe receipt, and reported a healthy power skip rather than a missed run |
| `MEMHARD-006` | The configured OpenAI/Codex hardener route uses a provider-compatible structured output schema. | A nightly run configured for OpenAI/GPT-5.5 can generate proposals without `model_schema_error` or silent fallback. | Codex CLI structured output, Node hardener provider fallback, redacted run telemetry | `tests/release/test_memory_hardening_contract.py::test_memory_hardening_codex_output_schema_matches_openai_structured_subset` plus live configured-account dry-run/apply proof | PASS 2026-06-02 ([schema repair report](reports/2026-06-02-openai-schema-repair.md)); synthetic checks, real configured-account dry-run, and guarded apply all used OpenAI/GPT-5.5 with one attempt and no fallback |
| `MEMHARD-007` | QA classification distinguishes healthy empty memory-hardening skips from degraded provider/runtime failures. | Users who intentionally disable memories do not wake up to a false PARTIAL verdict. | memory-harden status/run state, eligibility evidence, QA report wording | owning docs plus public-safe report/case review | PASS 2026-06-02 ([schema repair report](reports/2026-06-02-openai-schema-repair.md)); intentional no-eligible-user runs are healthy empty/skip evidence when no provider, transcript, vector, or runtime error is present |
| `MEMHARD-008` | Apply and rollback leave public-safe audit evidence. | A guarded apply can be verified and reversed without exposing private memory values. | memory-harden apply/rollback, summary.json, redacted run log, rollback summary | `tests/release/test_memory_hardening_contract.py::test_memory_hardening_rollback_records_public_safe_summary` plus guarded live apply/rollback | PASS 2026-06-02 ([schema repair report](reports/2026-06-02-openai-schema-repair.md)); apply wrote three key updates, rollback restored one user, and summary/log recorded only counts/timestamps |
| `MEMHARD-009` | Full scheduled-shaped apply gives the configured model enough runtime for large overnight workpacks. | The nightly job does not fall back solely because a healthy large OpenAI/GPT-5.5 call exceeded an undersized timeout. | memory-harden apply --scheduled, model attempt telemetry, timeout default | `tests/release/test_memory_hardening_contract.py::test_memory_hardening_model_timeout_matches_large_overnight_workload` plus scheduled-shaped apply proof | PASS 2026-06-02 ([schema repair report](reports/2026-06-02-openai-schema-repair.md)); after the timeout default was raised to 30 minutes, full scheduled-shaped apply used one OpenAI/GPT-5.5 attempt, zero failures, zero fallback, and rollback restored private state |
| `MEMHARD-010` | Scheduled hardening leaves an authoritative public-safe trigger receipt. | Nightly QA can prove the macOS maintenance job fired without guessing from UTC timestamps, travel, DST, or wake state. | LaunchAgent command, wrapper trigger receipt, hardener summary, automation report | `tests/release/test_memory_hardening_contract.py` trigger-receipt regressions plus next real scheduled run | PASS 2026-06-11 ([nightly review](reports/2026-06-11-nightly-routines-health-review.md)); Jun 9, Jun 10, and Jun 11 live launchd receipts were public-safe and finalized as `skipped` with `on_battery_power`, proving scheduled delivery without forcing model work |

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
- Last run: PASS/REPAIRED 2026-06-02
  ([schema repair report](reports/2026-06-02-openai-schema-repair.md)); after the historical
  degraded apply run, a real configured-account dry-run used the active runtime checkout,
  OpenAI/GPT-5.5, one model attempt, zero failures, zero fallback, public-safe proposal counts, and
  clean transcript/vector telemetry. A guarded apply of that proposal wrote three key updates and a
  rollback restored the private state. The timing note from the earlier audit is tracked as schedule
  observability, not a memory-hardening provider failure.

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
- Last run: PASS 2026-06-02
  ([nightly review](reports/2026-06-02-nightly-routines-health-review.md)); report sanitization was
  reviewed for private paths, account identifiers, raw transcript text, ids, secrets, launch
  tokens, prompt/result text, callback payloads, and raw browser snapshots. Temporary Playwright
  snapshots created during Workbench inspection were deleted before public reporting.

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
- Last run: PASS 2026-06-02
  ([nightly review](reports/2026-06-02-nightly-routines-health-review.md)); the read-only nightly
  audit observed AC power, charged battery, and no current thermal/performance warning. It did not
  force power or idle overrides, and no power-budget skip was recorded today.

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

## `MEMHARD-005` - Installer Memory-Hardening Readiness

- Requirement: Express Rich Brain Readiness must install memory hardening by default while showing
  whether the current run is ready, skipped, degraded, or empty because no users are eligible.
- Risk covered: the installer claims the memory spine is healthy while dry-run-first, disabled user
  memories, power/thermal gates, transcript source, or eligible-user scope make the run partial.
- Preconditions: Express/upgrade-shaped config and sanitized memory-hardening status/run state are
  available.
- Steps:
  1. Build Express and upgrade configs and confirm `runtime.memory_hardening.enabled`,
     `dry_run_first`, schedule, and empty `operator_user_email` defaults.
  2. Run install/status summary and confirm the memory row includes schedule, scope, dry-run-first,
     and transcript setup state.
  3. Simulate disabled user memories, no eligible users, power/thermal skip, and missing transcript
     source.
  4. Confirm public QA reports distinguish successful empty selection from provider/runtime failure.
- Expected result: new users get memory hardening automatically, but status never hides a skipped,
  empty, or degraded run.
- Forbidden result: hardcoded operator email, private memory/transcript content in public evidence,
  generated-env edits as a fix, or treating zero eligible users as substantive memory work.
- Evidence to capture: generated env key summary, status row, sanitized run status/skip reason,
  focused tests, and public-safety scan.
- Last run: PASS 2026-06-02
  ([schema repair report](reports/2026-06-02-openai-schema-repair.md)); install/upgrade defaults
  still seed memory hardening without a hardcoded operator identity, and QA now classifies a
  successful zero-eligible run as healthy empty/skip when the scoped user's memories are
  intentionally disabled and no provider/runtime/transcript/vector error is present.

## `MEMHARD-006` - OpenAI/Codex Structured Output Compatibility

- Requirement: the configured OpenAI/Codex memory-hardening path must pass schemas that the Codex
  CLI/OpenAI structured-output route accepts while preserving runtime validation of memory evidence.
- Risk covered: a tiny model probe passes, but the real nightly proposal schema fails with
  `model_schema_error` and silently falls back to another provider.
- Preconditions: Codex CLI is installed and signed in; synthetic checks need no private data, and a
  real configured-account dry-run may be used when private values are kept out of public artifacts.
- Steps:
  1. Run the schema regression that normalizes the proposal and transcript-summary schemas for
     Codex/OpenAI.
  2. Run a synthetic GPT-5.5 proposal call through `invokeModelWithFallback`.
  3. Run a synthetic GPT-5.5 transcript-summary call through
     `invokeTranscriptSummaryModelWithFallback`.
  4. Confirm both live calls record one OpenAI attempt, `ok=true`, and no fallback attempt.
  5. Run one real configured-account dry-run when safe, then inspect only redacted counts and
     attempt telemetry.
  6. Apply the generated proposal through the guarded apply path and roll it back when testing
     owner/private state.
- Expected result: both model-backed paths succeed on OpenAI/GPT-5.5 with no
  `model_schema_error`.
- Forbidden result: treating a successful probe or Anthropic fallback as proof that the configured
  OpenAI proposal path is healthy.
- Evidence to capture: release-test result, sanitized live synthetic attempt counts, real dry-run
  attempt telemetry, guarded apply/rollback counts, provider/model, error reason absence, and
  active-runtime checkout alignment.
- Last run: PASS 2026-06-02
  ([schema repair report](reports/2026-06-02-openai-schema-repair.md)).

## `MEMHARD-007` - Healthy Empty Selection Classification

- Requirement: QA must classify intentional no-eligible-user hardening runs as healthy empty/skip,
  not partial, when the run exits successfully and no provider/runtime/transcript/vector error is
  present.
- Risk covered: users who disable memories see repeated false degraded nightly verdicts.
- Preconditions: memory hardening is installed and enabled, but the scoped user or all local users
  are intentionally ineligible for saved-memory hardening.
- Steps:
  1. Inspect memory-hardening status/run state and confirm exit status success.
  2. Confirm `user_count=0` or equivalent selected-user count is explained by intentional
     eligibility state, not by auth/config/runtime inspection failure.
  3. Confirm provider/model attempts, transcript scan, vector presence checks, and runtime
     prerequisites did not record errors.
  4. Mark the result `PASS/SKIPPED` or healthy empty in the QA verdict. Mark it `PARTIAL` only when
     eligibility is unknown, unexpected, or mixed with real errors.
- Expected result: the report is honest that no memory writes occurred, but does not downgrade the
  nightly automation for an intentional empty selection.
- Forbidden result: treating every zero-eligible run as degraded or claiming substantive memory work
  occurred when no user was selected.
- Evidence to capture: redacted selected-user count, explicit skip/eligibility explanation, provider
  error absence, transcript/vector error absence, and public-safe report wording.
- Last run: PASS 2026-06-02
  ([schema repair report](reports/2026-06-02-openai-schema-repair.md)).

## `MEMHARD-008` - Apply/Rollback Auditability

- Requirement: Applying a hardener proposal and rolling it back must leave public-safe audit
  evidence with counts/timestamps, while raw memory values and rollback snapshots remain private.
- Risk covered: QA proves model generation but leaves the actual scheduled apply path unobserved, or
  rollback succeeds only in terminal output with no persistent audit trail.
- Preconditions: a private proposal exists from a successful hardener dry-run or scheduled run.
- Steps:
  1. Apply the proposal by run id.
  2. Inspect only public-safe apply counts, changed key names, transcript-vector counts, and
     maintenance flags.
  3. Roll back the same run id.
  4. Confirm the run summary records `rolled_back_at`, rollback summary filename, restored-user
     count, and that the redacted log records a rollback event without raw user ids or memory
     values.
- Expected result: the apply path is observable, rollback restores private state, and public-safe
  audit fields prove both steps without leaking private contents.
- Forbidden result: claiming scheduled apply readiness from dry-run only, storing raw rollback
  contents in public artifacts, or relying only on terminal output for rollback proof.
- Evidence to capture: apply result counts, rollback restored count, rollback snapshot count,
  redacted run-log event names, regression result, and public-safety scan.
- Last run: PASS 2026-06-02
  ([schema repair report](reports/2026-06-02-openai-schema-repair.md)); guarded apply and rollback
  both succeeded on the active runtime, with persistent public-safe summary/log evidence.

## `MEMHARD-009` - Scheduled Apply Model Timeout Budget

- Requirement: unattended scheduled hardening must give the configured launch-ready model enough
  time to process a large, valid workpack before falling back.
- Risk covered: the OpenAI/GPT-5.5 schema path is healthy, but the full scheduled apply still falls
  back because the model-call timeout is too short for the real prompt size.
- Preconditions: a full scheduled-shaped hardening run is safe to apply and immediately roll back.
- Steps:
  1. Run `memory-harden apply --scheduled` so model generation and apply happen in one operation.
  2. Inspect redacted telemetry for `model_attempt_count`, `model_attempt_failures`,
     `model_attempt_reasons`, selected provider/model/effort, apply counts, and transcript-vector
     errors.
  3. Roll back the run and confirm rollback summary/status fields are present.
  4. Mark PASS only when the configured OpenAI/GPT-5.5 attempt completes without fallback.
- Expected result: full scheduled-shaped apply uses OpenAI/GPT-5.5 directly, applies bounded key
  updates, records no model timeout or vector error, and rolls back cleanly during QA.
- Forbidden result: accepting a dry-run plus run-id apply as the only proof when the scheduled path
  still times out and falls back.
- Evidence to capture: scheduled-shaped apply run id, selected provider/model, attempt/failure
  counts, timeout reason absence, apply counts, rollback restored count, and public-safety scan.
- Last run: PASS 2026-06-02
  ([schema repair report](reports/2026-06-02-openai-schema-repair.md)); a first full
  scheduled-shaped apply exposed `model_call_timeout` at the old 15-minute default and fell back.
  After raising the default to 30 minutes, the rerun completed through OpenAI/GPT-5.5 directly with
  one attempt, zero failures, zero fallback, three bounded key updates, no vector errors, and a
  successful rollback.

## `MEMHARD-010` - Scheduled Trigger Receipt

- Requirement: scheduled memory hardening must leave an authoritative public-safe trigger receipt
  before model work begins, then finalize it with the wrapper exit status.
- Risk covered: nightly QA repeatedly marks successful hardening as `PARTIAL` because observed UTC
  timing differs from audit-time timezone context and no artifact proves the actual launchd fire.
- Preconditions: memory hardening is enabled and the macOS LaunchAgent has been reconciled from
  generated config.
- Steps:
  1. Install or inspect the LaunchAgent and confirm its direct wrapper command includes the explicit
     scheduled trigger marker.
  2. Run a synthetic scheduled-shaped wrapper pass and confirm a trigger receipt is written before
     model work and finalized with success/failure/skip status.
  3. Confirm manual wrapper runs do not masquerade as launchd-triggered scheduled work.
  4. Confirm power/thermal skips finalize the receipt as `skipped` with a public-safe reason.
  5. On the next real scheduled window, correlate the receipt with LaunchAgent state and the
     hardener summary without exposing raw account, path, prompt, transcript, token, or memory data.
- Expected result: a healthy scheduled run or healthy power/eligibility skip can be classified
  `PASS`/`SKIPPED` from receipt plus run evidence even when UTC timing looks different because of
  travel, DST, or launchd wake coalescing.
- Forbidden result: classifying success as `PARTIAL` solely from UTC mismatch, recording raw private
  values in the receipt, or routing memory maintenance through Prompt Workbench/GlassHive to make it
  look like a scheduled prompt.
- Evidence to capture: explicit trigger marker in installed plist, receipt field summary, focused
  pytest result, public-safety scan, and next live scheduled receipt/run correlation.
- Automation: `tests/release/test_memory_hardening_contract.py`.
- Last run: PASS/SKIPPED 2026-06-11
  ([nightly review](reports/2026-06-11-nightly-routines-health-review.md)); live launchd receipt
  correlation proved the schedule fired and finalized a power-gate skip without forcing model work.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Memory Hardening. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `MEMHARD-UC-001` | On memory hardener, reports, runtime env, synthetic memories, verify that memory hardening runs are bounded, public-safe, and preserve durable facts while pruning stale/private noise. | owning requirement for `MEMHARD-001` / `MEMHARD-001` | memory hardener, reports, runtime env, synthetic memories | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MEMHARD-001. | User-visible behavior matches source, docs, persisted state, and logs | SKIPPED/PASS-SAFETY 2026-06-11 ([nightly review](reports/2026-06-11-nightly-routines-health-review.md)); launchd fired and skipped on battery, while the latest model-backed run remains healthy |
| `MEMHARD-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `MEMHARD-002` / `MEMHARD-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MEMHARD-002. | The user sees an honest setup, retry, or degraded-state result for MEMHARD-002; no fake success is accepted. | PASS 2026-06-11 ([nightly review](reports/2026-06-11-nightly-routines-health-review.md)) |
| `MEMHARD-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `MEMHARD-002` / `MEMHARD-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MEMHARD-002. | MEMHARD-002 remains correct after the persistence or parity step and final wording matches evidence. | PASS 2026-06-11 ([nightly review](reports/2026-06-11-nightly-routines-health-review.md)) |
| `MEMHARD-UC-004` | On battery or thermal constraint, run or audit model-backed memory hardening. | owning requirement for `MEMHARD-003` / `MEMHARD-003` | memory hardener CLI, helper transcript ingest, scheduled operator job | Source, owning requirement doc, case steps, process table, local-runtime status, and release-test evidence that apply to MEMHARD-003. | The user sees an honest skipped/degraded result instead of surprise expensive model work. | PASS/SKIPPED 2026-06-11 ([nightly review](reports/2026-06-11-nightly-routines-health-review.md)); scheduled trigger receipt finalized as `on_battery_power`, no thermal/performance warning was recorded, and no override was used |
| `MEMHARD-UC-005` | While plugged in, run or repeat transcript maintenance. | owning requirement for `MEMHARD-004` / `MEMHARD-004` | Node hardener, wrapper, helper, status CLI, generated env | Source, owning requirement doc, case steps, public marker, generated config, helper artifact, and release-test evidence that apply to MEMHARD-004. | The user sees a bounded batch, cooldown skip, or status result instead of repeated one-file model loops. | PASS 2026-05-27 ([report](reports/2026-05-27-plugged-in-efficiency-qa.md)) |
| `MEMHARD-UC-006` | After Express install or upgrade, inspect memory-hardening readiness before and after a scheduled run. | `39_Installer_and_Config_Compiler.md` / `MEMHARD-005`, `INST-004` | `bin/viventium status`, memory-harden status/run state, generated env, LaunchAgent/scheduler state | Schedule/scope/dry-run-first values, eligible-user count, skip reason, transcript setup state, public-safety scan. | Memory hardening is installed by default and honest about ready, skipped, empty, degraded, or completed state. | PASS-SAFETY 2026-06-11 ([nightly review](reports/2026-06-11-nightly-routines-health-review.md)); LaunchAgent and receipt evidence prove scheduled delivery, and the run was honestly skipped by power policy |
| `MEMHARD-UC-007` | Before accepting an OpenAI-configured hardening fix, run the real Codex/GPT-5.5 synthetic proposal and transcript-summary paths plus a real configured-account dry-run/apply proof when safe. | `20_Memory_System.md` / `MEMHARD-006` | Codex CLI through the Node hardener, redacted attempt telemetry, memory-harden dry-run/apply/rollback status | Provider/model attempts, schema regression, active-runtime checkout, public-safe report. | The configured OpenAI path succeeds directly; fallback is not used to hide a schema defect. | PASS 2026-06-02 ([schema repair report](reports/2026-06-02-openai-schema-repair.md)); real dry-run and guarded apply recorded one OpenAI attempt, zero failures, zero fallback |
| `MEMHARD-UC-008` | With memories intentionally disabled or no eligible users, inspect the scheduled hardener result. | `20_Memory_System.md`, `39_Installer_and_Config_Compiler.md` / `MEMHARD-007` | memory-harden status/run state and QA report wording | Selected-user count, eligibility explanation, provider/runtime/transcript/vector error absence. | The user sees a healthy empty/skip result, not a false degraded verdict. | PASS 2026-06-02 ([schema repair report](reports/2026-06-02-openai-schema-repair.md)) |
| `MEMHARD-UC-009` | Apply and roll back a hardener proposal during QA. | `20_Memory_System.md` / `MEMHARD-008` | memory-harden apply/rollback, summary.json, redacted run log, rollback summary | Changed-key counts, maintenance flag, transcript-vector counts, rollback restored count, public-safety scan. | The user gets reversible proof of the scheduled apply path without leaking private memory values. | PASS 2026-06-02 ([schema repair report](reports/2026-06-02-openai-schema-repair.md)); guarded apply and rollback succeeded |
| `MEMHARD-UC-010` | Let the full scheduled-shaped hardener run model generation and apply in one operation. | `20_Memory_System.md` / `MEMHARD-009` | memory-harden apply --scheduled, run summary/status, redacted log, rollback summary | Model attempt/failure reasons, selected provider/model, apply counts, rollback restored count. | The configured OpenAI path completes without timeout/fallback and rollback restores private state during QA. | PASS 2026-06-02 ([schema repair report](reports/2026-06-02-openai-schema-repair.md)); full scheduled-shaped apply and rollback succeeded after timeout fix |
| `MEMHARD-UC-011` | Wake up after the scheduled memory-maintenance window and inspect whether it ran. | `20_Memory_System.md`, `39_Installer_and_Config_Compiler.md` / `MEMHARD-010` | LaunchAgent plist/state, schedule trigger receipt, memory-harden status/run summary, QA report wording | Trigger source, fired-at timestamps, timezone at fire, exit status, run id/status when present, generated schedule, public-safety scan. | The user sees PASS/SKIPPED for a healthy scheduled run or healthy skip, and PARTIAL/FAIL only for missing receipt, duplicate/conflicting triggers, failed run, provider/vector errors, or unknown eligibility. | PASS/SKIPPED 2026-06-11 ([nightly review](reports/2026-06-11-nightly-routines-health-review.md)); live receipt correlation proved launchd fired and finalized the scheduled power skip |

## Release Test Traceability

- `tests/release/test_memory_hardening_contract.py`
