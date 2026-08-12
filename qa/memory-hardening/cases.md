# Memory Hardening QA Cases

## Case ID Convention

Use stable `MEMHARD-NNN` IDs for memory hardening cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `MEMHARD-001` | Memory hardening runs are bounded, public-safe, and preserve durable facts while pruning stale/private noise. | User-visible behavior matches source, docs, persisted state, and logs | memory hardener, reports, runtime env, synthetic memories | `tests/release/test_memory_hardening_contract.py` plus user-grade QA when visible | PASS 2026-08-09; the natural 03:00 LaunchAgent run completed Luna/medium with the full 158-message lookback, a current-tuple receipt, and joined integrity `memoryHardening=ok`. |
| `MEMHARD-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-08-06 ([nightly review](reports/2026-08-06-nightly-routines-health-review.md)); report uses sanitized counts/statuses/timestamps only and omits raw prompts, transcripts, memory values, tokens, local paths, account identifiers, and callback payloads. |
| `MEMHARD-003` | Model-backed hardening and transcript ingest respect the local machine power budget. | Battery or thermally constrained laptops do not start expensive model-backed maintenance unless the operator explicitly overrides the power gate. | memory hardener CLI, helper transcript ingest, scheduled operator job | `tests/release/test_memory_hardening_contract.py` power-gate regressions plus live battery/thermal status evidence when visible | PASS-AUDIT-SAMPLE / NO-SKIP 2026-08-09 ([nightly review](reports/2026-08-09-nightly-routines-health-review.md)); audit observed AC power, full charge, no thermal/performance warning, no power-budget skip, and no override. The constrained branch was not forced by this observer. |
| `MEMHARD-004` | Model-backed transcript maintenance remains efficient while plugged in. | Plugged-in laptops avoid repeated one-file model/probe/vector startup loops without stopping Viventium or Docker. | Node hardener, wrapper, helper, status CLI, generated env | `tests/release/test_memory_hardening_contract.py`, `tests/release/test_config_compiler.py`, `tests/release/test_macos_helper_install.py`, live cooldown/status smoke | PASS 2026-05-27 ([report](reports/2026-05-27-plugged-in-efficiency-qa.md)) |
| `MEMHARD-005` | New installs and upgrades schedule memory hardening for eligible local users without hardcoded operator identity. | A new user with memories enabled is covered by the 03:00 local hardening job automatically, and an intentionally ineligible user gets an honest healthy skip. | installer config, generated env, LaunchAgent sync, hardener eligibility | `test_default_nightly_routines.py`, `test_wizard.py`, `test_config_compiler.py`, `test_cli_upgrade.py` | PASS-SAFETY 2026-06-11 ([nightly review](reports/2026-06-11-nightly-routines-health-review.md)); active LaunchAgent used the direct wrapper with `--trigger launchd`, produced a live public-safe receipt, and reported a healthy power skip rather than a missed run |
| `MEMHARD-006` | The configured OpenAI/Codex hardener route uses a provider-compatible structured output schema. | A nightly run on the configured model can generate proposals without `model_schema_error` or silent fallback. | Codex CLI structured output, Node hardener provider fallback, redacted run telemetry | `tests/release/test_memory_hardening_contract.py::test_memory_hardening_codex_output_schema_matches_openai_structured_subset` plus live configured-account dry-run/apply proof | PASS-ROUTE-PROVEN 2026-08-09; the exact Luna/medium bank, 500k workpack, and configured-account route completed without schema failure or hidden fallback. |
| `MEMHARD-007` | QA classification distinguishes healthy empty memory-hardening skips from degraded provider/runtime failures. | Users who intentionally disable memories do not wake up to a false PARTIAL verdict. | memory-harden status/run state, eligibility evidence, QA report wording | owning docs plus public-safe report/case review | PASS 2026-06-02 ([schema repair report](reports/2026-06-02-openai-schema-repair.md)); intentional no-eligible-user runs are healthy empty/skip evidence when no provider, transcript, vector, or runtime error is present |
| `MEMHARD-008` | Apply and rollback leave public-safe audit evidence. | A guarded apply can be verified and reversed without exposing private memory values. | memory-harden apply/rollback, summary.json, redacted run log, rollback summary | `tests/release/test_memory_hardening_contract.py::test_memory_hardening_rollback_records_public_safe_summary` plus guarded live apply/rollback | PASS 2026-06-02 ([schema repair report](reports/2026-06-02-openai-schema-repair.md)); apply wrote three key updates, rollback restored one user, and summary/log recorded only counts/timestamps |
| `MEMHARD-009` | Full scheduled-shaped apply gives the configured model enough runtime for large overnight workpacks. | The nightly job does not fall back solely because a healthy large configured-model call exceeded an undersized timeout. | memory-harden apply --scheduled, model attempt telemetry, timeout default | `tests/release/test_memory_hardening_contract.py::test_memory_hardening_model_timeout_matches_large_overnight_workload` plus scheduled-shaped apply proof | PASS-ROUTE 2026-08-09; Luna/medium completed the exact 500,000-character workpack in 8.6 s without fallback; natural cadence remains a separate gate. |
| `MEMHARD-010` | Scheduled hardening leaves a process-attested public-safe trigger receipt within the local-operator trust boundary. | Nightly QA can prove the macOS maintenance job fired without guessing from UTC timestamps, travel, DST, or wake state. | LaunchAgent command, wrapper trigger receipt, hardener summary, automation report | `tests/release/test_memory_hardening_contract.py` trigger-receipt regressions plus next real scheduled run | PASS-CADENCE 2026-08-11 ([nightly review](reports/2026-08-11-nightly-routines-health-review.md)); the natural 03:00 Luna/medium run produced valid schema-v3 launchd job-PID attestation, completed successfully inside the due window, persisted the v3 observation, and closed the legacy-v2 transition. |
| `MEMHARD-011` | Proposal apply, replay, and rollback are revision protected across delete/recreate generations. | Nightly maintenance cannot overwrite, erase, or resurrect over a newer Telegram/web/voice memory write. | proposal/apply/rollback, Mongo tombstone revisions, private rollback snapshot, public-safe summary | hardener and real-Mongo memory CAS regressions | REPAIRED/PASS-AUTOMATED 2026-07-14; 78 hardener/proposal tests, retained-tombstone ABA, exact rollback, duplicate fail-closed, and path-redaction regressions pass ([report](../memory-continuity/reports/2026-07-14-memory-continuity-incident-repair.md)) |
| `MEMHARD-012` | The 03:00 LaunchAgent is single-trigger, idempotently reconciled, and lifecycle-receipted. | Repeated start/upgrade cannot unload a healthy agent, reset its evidence, or create a competing model cadence. | compiler, CLI sync, LaunchAgent, trigger/lifecycle receipts | memory-hardening contract tests plus live plist/status | PASS-SCHEDULE 2026-08-09 ([nightly review](reports/2026-08-09-nightly-routines-health-review.md)); the loaded LaunchAgent and generated schedule agreed on one 03:00 local direct-wrapper trigger, with no competing interval and a dated healthy receipt. |
| `MEMHARD-013` | A side-by-side/test root or interrupted hardener cannot damage the singleton schedule or leave an unusable rollback/lock. | Canonical passwd-home ownership, per-mutation rollback durability, and PID-lifetime lock identity. | hardener schedule owner, private rollback ledger, lock directory | noncanonical-root rejection, abrupt second-mutation failure, PID-reuse, and live LaunchAgent status tests | Noncanonical roots fail before `launchctl`; every successful mutation is rollback-addressable after interruption; a reused PID is not mistaken for the original process; the canonical loaded schedule survives the suite. | PASS-AUTOMATED/LIVE-STATE 2026-08-08; focused Python/Node regressions passed and the canonical LaunchAgent remained loaded. See [repair report](../memory-continuity/reports/2026-08-08-cognitive-continuity-capability-repair.md). |
| `MEMHARD-014` | Memory-model selection is generic, fail-closed, repeated, costed, and proven on the account-scoped writer/hardener routes. | The cheapest fast model meeting the exact mutation target is selected without overfitting one fact or silently weakening accuracy. | exact-model eval harness, compiler/runtime tuple, browser/Telegram writer, hardener dry-run | `run-memory-model-eval.cjs`, harness tests, compiler tests, live receipts | PASS-MODEL/LIVE 2026-08-09; frozen bank `memory-writer-v1.0.0` (`fc8acd04668038e3`) gave Luna/medium 32/32, Sol/xHigh 32/32, Terra/high 31/32. Only a full frozen-bank run may select a winner; subset/500k probes verify the frozen hash but are selection-ineligible. Luna remained the lowest-cost passing tier ([model eval](reports/2026-08-09-gpt-5.6-memory-model-eval.md), [ceiling](reports/2026-08-09-gpt-5.6-luna-500k-application-ceiling.md)). |
| `MEMHARD-016` | Voice-derived durable memory waits for terminal call, suppression, and speaker truth. | A conversation with guests or a cancelled task cannot silently become stable owner memory. | Call/Wing/Listen-Only messages, speaker segments/session state, suppression ledger, post-call hardener | voice persistence and memory-policy suites plus real post-call DB QA | `PARTIAL` 2026-08-09; focused policy automation exists, real post-call hardener journey pending |

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

- Requirement: Easy Install Brain Readiness must represent memory hardening truthfully while showing
  whether the current run is ready, skipped, degraded, or empty because no users are eligible.
- Risk covered: the installer claims the memory spine is healthy while dry-run-first, disabled user
  memories, power/thermal gates, transcript source, or eligible-user scope make the run partial.
- Preconditions: Easy Install (`install.experience: express`)/upgrade-shaped config and sanitized memory-hardening status/run state are
  available.
- Steps:
  1. Build Easy Install and upgrade configs and confirm `runtime.memory_hardening.enabled`,
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

- Requirement: scheduled memory hardening must leave a process-attested public-safe trigger receipt
  within the local-operator trust boundary before model work begins, then finalize it with the
  wrapper exit status.
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
  5. Confirm schema-v2 compatibility accepts only one pre-v3 receipt, closes on a second v2 or any
     v3 receipt even after receipt pruning, and every launchctl/interpreter path is absolute.
  6. On the next real scheduled window, correlate the receipt with LaunchAgent state and the
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
- Last run: PASS 2026-07-16
  ([nightly review](reports/2026-07-16-nightly-routines-health-review.md)); live launchd receipt
  correlation proved the schedule fired at 03:00 local, finalized success with exit 0, and matched
  the hardener run id. The audit classified the short zero-change run as a clean scheduled
  maintenance pass rather than overclaiming fresh model-backed rewriting.

## `MEMHARD-011` - Revision-Safe Apply And Rollback

- Generate a proposal, then advance the same memory key through a synthetic live write before apply.
- Apply and replay the proposal; confirm `revision_conflict`, zero stale overwrite, and conflict
  visibility in `apply_results`.
- On a clean synthetic key, apply once and verify the first rollback snapshot is preserved across
  replay. Advance the key again before rollback and confirm rollback preserves the newer value.
- Delete and recreate the key, then replay stale set/delete/absent-create and rollback operations.
  Confirm the retained tombstone keeps the revision monotonic and every stale operation conflicts.
- Expected: apply and rollback touch only exact expected revisions; legacy snapshots without
  post-apply state fail closed; partial rollback conflicts are explicit.
- Forbidden: delete/recreate of the user's entire memory set, silent stale overwrite, replay erasing
  the original snapshot, or raw values/ids in public logs.
- Evidence: automated 72-case hardener suite, real-Mongo tombstone/CAS regressions, Mongo revision
  delta, private snapshot schema/version, redacted summary conflict counts, and guarded live smoke.
- Last run: REPAIRED/PASS-AUTOMATED 2026-07-14; 80 proposal/hardener tests plus live guarded CAS
  evidence pass; native cross-surface journey remains separate.

## `MEMHARD-012` - Single-Trigger Idempotent LaunchAgent

- Install a synthetic 03:00 plist, reconcile it twice, then introduce real schedule/command drift.
- Verify the first install bootstraps and verifies, the identical second pass performs only a
  `launchctl print`, and real drift performs one bootout/bootstrap with post-action verification.
- Remove the generated enablement key and confirm sync preserves the installed agent; explicit
  `false` remains the only uninstall input.
- Expected: only `StartCalendarInterval` exists; trigger receipts prove scheduled fires and
  lifecycle receipts prove installer/reconciler actions with a generation hash. Requested and
  effective model tuples match; a provider mismatch is visible and non-healthy.
- Forbidden: `StartInterval`, Workbench/cron as a second trigger, bootout/bootstrap on every start,
  absent config interpreted as disable, or receipts containing paths/email/commands.
- Evidence: contract tests, installed plist, `launchctl` state, status JSON, lifecycle receipt, and
  latest public-safe trigger receipt.
- Last run: PASS-LIVE 2026-07-16
  ([nightly review](reports/2026-07-16-nightly-routines-health-review.md)); the live loaded plist
  had one 03:00 calendar trigger tied to system-local time, no competing interval trigger, a healthy
  no-op lifecycle receipt, and a successful latest scheduled run with matching requested/effective
  OpenAI Sol/xhigh tuple.

## `MEMHARD-014` - GPT-5.6 Memory-Workload Selection

- Run the frozen 16-case synthetic bank against Sol, Terra, and Luna through the exact Codex CLI
  route. Repeat final candidates twice and require 100% case correctness, structured completion,
  and zero rejected operations.
- Cover extraction, update/correction, temporal and exact-number preservation, multi-session
  learning, disambiguation, attribution, deduplication, selective forgetting, injection/noise
  rejection, and abstention. No incident entity or phrase may be a scoring condition.
- Run a near-ceiling workpack and record p50/p95, tokens, and normalized cost from current official
  rates. A cheaper model is eligible only after clearing quality.
- Compile and activate the selected provider/model/effort tuple. Prove it on a non-admin browser
  writer, native Telegram writer/read boundary, and configured-account hardener dry-run.
- Expected: Luna/medium is selected only while it meets the strict gate; deep reflection/observer
  remain separate Sol routes; account/host authentication boundaries remain explicit.
- Forbidden: average-score acceptance, selecting Terra after an exact mutation miss, assuming a
  1M context window guarantees memory use, or treating a `/host` login as the user's OAuth route.
- Last run: PASS-MODEL/LIVE 2026-08-09. Luna/medium and Sol/xHigh each passed 32/32; Terra/high
  failed one exact additive-constraint mutation (31/32). Luna's p95 was 9.6 s versus Sol's 15.9 s,
  its official normalized cost was one fifth of Sol's, and it passed the exact 500,000-character
  workpack. Real browser and Telegram writer/read paths also selected Luna/medium. The current
  joined scheduler state is still blocked until a naturally due receipt proves the current tuple.

## `MEMHARD-015` - Current-Configuration Scheduled Receipt Parity

- Seed a successful scheduled receipt whose requested/effective tuple agrees internally but differs
  from the current generated provider/model/effort.
- Expected: status reports `configured_execution_mismatch`, the joined execution mismatch is true,
  and schedule health is not green. A later real LaunchAgent execution clears the mismatch only
  when requested, effective, and configured tuples all agree.
- Verify the no-generated-env hardener fallback independently; it must select the same Luna/medium
  memory route as the compiler.
- If the LaunchAgent applies a real QA proposal, roll it back by exact run id and require one full
  restore with zero partial/conflict results.
- Forbidden: an obsolete successful receipt certifying new configuration, a direct hardener fallback
  silently selecting Sol/xHigh, or a manual dry-run masquerading as LaunchAgent proof.
- Last run: PARTIAL 2026-08-09. The failure-first stale-receipt test passes and current live status is
  correctly `execution_mismatch`; guarded Luna/medium execution and rollback were proven, but only a
  naturally due current-tuple LaunchAgent receipt can clear the present block.

## `MEMHARD-016` - Post-Call Voice Evidence Authority

- During an active Call, Wing session, and Listen-Only session, create synthetic owner, guest,
  shared-microphone, uncertain, and cancelled-task segments. Confirm no voice-derived durable write
  occurs before hangup.
- After hangup, run post-call processing with complete `speakerSegments`,
  `SpeakerSessionStateV1`, call terminal state, and suppression state. Repeat with a late-discovered
  second speaker and with each authoritative state unavailable.
- Expected: only owner-trusted single-speaker Call content may reach the normal writer. Wing,
  Listen-Only, mixed/shared-mic, guest, and unverified content remains soft; one call is one source;
  speaker revisions apply before evaluation; cancelled/late output is absent; missing durable truth
  fails closed.
- Forbidden: active-call writes, multiple diarized speakers counted as corroboration, guest speech
  promoted as owner fact, cancellation result entering memory, or unavailable state treated as safe.
- Evidence: real call/hangup, sanitized message/segment/suppression counts, hardener proposal/result,
  DB revisions, linked-chat refresh, and public-safe report.
- Last run: `PARTIAL` — 2026-08-09 — focused policy/persistence automation only; real post-call
  hardener and DB user path remains pending.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Memory Hardening. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `MEMHARD-UC-001` | On memory hardener, reports, runtime env, synthetic memories, verify that memory hardening runs are bounded, public-safe, and preserve durable facts while pruning stale/private noise. | owning requirement for `MEMHARD-001` / `MEMHARD-001` | memory hardener, reports, runtime env, synthetic memories | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MEMHARD-001. | User-visible behavior matches source, docs, persisted state, and logs | SKIPPED/PASS-SAFETY 2026-06-11 ([nightly review](reports/2026-06-11-nightly-routines-health-review.md)); launchd fired and skipped on battery, while the latest model-backed run remains healthy |
| `MEMHARD-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `MEMHARD-002` / `MEMHARD-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MEMHARD-002. | The user sees an honest setup, retry, or degraded-state result for MEMHARD-002; no fake success is accepted. | PASS 2026-06-11 ([nightly review](reports/2026-06-11-nightly-routines-health-review.md)) |
| `MEMHARD-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `MEMHARD-002` / `MEMHARD-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to MEMHARD-002. | MEMHARD-002 remains correct after the persistence or parity step and final wording matches evidence. | PASS 2026-08-06 ([nightly review](reports/2026-08-06-nightly-routines-health-review.md)); public report and case updates passed the focused public-safety scan |
| `MEMHARD-UC-004` | On battery or thermal constraint, run or audit model-backed memory hardening. | owning requirement for `MEMHARD-003` / `MEMHARD-003` | memory hardener CLI, helper transcript ingest, scheduled operator job | Source, owning requirement doc, case steps, process table, local-runtime status, and release-test evidence that apply to MEMHARD-003. | The user sees an honest skipped/degraded result instead of surprise expensive model work. | PASS-AUDIT-SAMPLE / NO-SKIP 2026-08-06 ([nightly review](reports/2026-08-06-nightly-routines-health-review.md)); audit observed AC power and no thermal/performance warning, with no supported skip or override |
| `MEMHARD-UC-005` | While plugged in, run or repeat transcript maintenance. | owning requirement for `MEMHARD-004` / `MEMHARD-004` | Node hardener, wrapper, helper, status CLI, generated env | Source, owning requirement doc, case steps, public marker, generated config, helper artifact, and release-test evidence that apply to MEMHARD-004. | The user sees a bounded batch, cooldown skip, or status result instead of repeated one-file model loops. | PASS 2026-05-27 ([report](reports/2026-05-27-plugged-in-efficiency-qa.md)) |
| `MEMHARD-UC-006` | After Easy Install or upgrade, inspect memory-hardening readiness before and after a scheduled run. | `39_Installer_and_Config_Compiler.md` / `MEMHARD-005`, `INST-004` | `bin/viventium status`, memory-harden status/run state, generated env, LaunchAgent/scheduler state | Schedule/scope/dry-run-first values, eligible-user count, skip reason, transcript setup state, public-safety scan. | Memory hardening is installed by default and honest about ready, skipped, empty, degraded, or completed state. | PASS-SAFETY 2026-06-11 ([nightly review](reports/2026-06-11-nightly-routines-health-review.md)); LaunchAgent and receipt evidence prove scheduled delivery, and the run was honestly skipped by power policy |
| `MEMHARD-UC-007` | Before accepting an OpenAI-configured hardening fix, run the real Codex/Luna synthetic proposal and transcript-summary paths plus a real configured-account dry-run/apply proof when safe. | `20_Memory_System.md` / `MEMHARD-006` | Codex CLI through the Node hardener, redacted attempt telemetry, memory-harden dry-run/apply/rollback status | Provider/model attempts, schema regression, active-runtime checkout, public-safe report. | The configured OpenAI path succeeds directly; fallback is not used to hide a schema defect. | PASS-LIVE 2026-08-08 ([model report](reports/2026-08-08-gpt-5.6-memory-model-eval-final.md)); Luna/medium completed direct model, writer, dry-run, and LaunchAgent paths without fallback |
| `MEMHARD-UC-008` | With memories intentionally disabled or no eligible users, inspect the scheduled hardener result. | `20_Memory_System.md`, `39_Installer_and_Config_Compiler.md` / `MEMHARD-007` | memory-harden status/run state and QA report wording | Selected-user count, eligibility explanation, provider/runtime/transcript/vector error absence. | The user sees a healthy empty/skip result, not a false degraded verdict. | PASS 2026-06-02 ([schema repair report](reports/2026-06-02-openai-schema-repair.md)) |
| `MEMHARD-UC-009` | Apply and roll back a hardener proposal during QA. | `20_Memory_System.md` / `MEMHARD-008` | memory-harden apply/rollback, summary.json, redacted run log, rollback summary | Changed-key counts, maintenance flag, transcript-vector counts, rollback restored count, public-safety scan. | The user gets reversible proof of the scheduled apply path without leaking private memory values. | PASS-LIVE 2026-08-08; installed LaunchAgent apply changed one user and exact run-id rollback restored one user with zero partial/conflict results |
| `MEMHARD-UC-010` | Let the full scheduled-shaped hardener run model generation and apply in one operation. | `20_Memory_System.md` / `MEMHARD-009` | memory-harden apply --scheduled, run summary/status, redacted log, rollback summary | Model attempt/failure reasons, selected provider/model, apply counts, rollback restored count. | The configured OpenAI path completes without timeout/fallback and rollback restores private state during QA. | PASS-LIVE 2026-08-08; the installed LaunchAgent completed OpenAI/Luna/medium and exact rollback restored private state |
| `MEMHARD-UC-011` | Wake up after the scheduled memory-maintenance window and inspect whether it ran. | `20_Memory_System.md`, `39_Installer_and_Config_Compiler.md` / `MEMHARD-010` | LaunchAgent plist/state, schedule trigger receipt, memory-harden status/run summary, QA report wording | Trigger source, proof method, fired-at timestamps, timezone at fire, exit status, run id/status when present, generated schedule, public-safety scan. | The user sees PASS/SKIPPED for a healthy scheduled run or healthy skip, and PARTIAL/FAIL only for missing/unattested receipt, duplicate/conflicting triggers, failed run, provider/vector errors, or unknown eligibility. | PASS-CADENCE-TRANSITION 2026-08-09; exactly one natural 03:00 Luna/medium schema-v2 receipt remains usable with an explicit legacy proof method. Automated writer/consumer tests prove the legacy path closes durably on a duplicate v2 or first v3 even after event pruning, pins canonical executable paths, and proves exact schema-v3 PID attestation plus inconsistent-proof rejection; the next natural run is required for live v3 evidence. |
| `MEMHARD-UC-012` | Apply, replay, and roll back a synthetic proposal while another surface advances the same key. | `20_Memory_System.md` / `MEMHARD-011` | hardener CLI, Mongo revisions, Telegram/web write | apply/rollback summaries, revision conflicts, preserved final value | Stale apply/rollback loses the race visibly and never erases the newer value. | PASS-AUTOMATED 2026-07-11; live smoke pending |
| `MEMHARD-UC-013` | Re-run start/upgrade reconciliation, then inspect the overnight job after travel or sleep. | `20_Memory_System.md` / `MEMHARD-012` | LaunchAgent, `memory-harden status`, trigger/lifecycle receipts | system timezone, single calendar trigger, loaded state, generation hash, latest exit/run | Reconciliation is a no-op when healthy; launchd's observed calendar fire is judged from its receipt without a competing model cadence. | BLOCKED-CADENCE 2026-08-09; schedule structure remains present, but prior Sol cadence evidence cannot certify the current Luna tuple. |
| `MEMHARD-UC-014` | Change the configured memory model after a successful scheduled run, then inspect health before and after the new route executes. | `20_Memory_System.md` / `MEMHARD-015` | generated env, memory-harden status, LaunchAgent receipt, rollback summary | configured/requested/effective tuple, health state, restored/partial/conflict counts | The old receipt becomes non-healthy until the installed LaunchAgent proves the new tuple; QA mutation is exactly restored. | PARTIAL 2026-08-09; fail-closed mismatch detection and guarded Luna execution were proven, but current integrity intentionally remains blocked until the natural scheduled receipt matches. |
| `MEMHARD-UC-015` | Finish a synthetic multi-speaker/cancelled voice call and run post-call hardening. | `20_Memory_System.md` / `MEMHARD-016`, `MPV-038` | real call, linked chat, speaker/task persistence, memory hardener | segment/session revisions, suppression state, proposal/write counts, DB revisions | Only verified single-speaker Call content is eligible; all other voice evidence remains soft and one call counts once. | `PARTIAL` 2026-08-09; real call/hardener path pending |

## Release Test Traceability

- `tests/release/test_memory_hardening_contract.py`
