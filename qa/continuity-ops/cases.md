# Continuity Ops QA Cases

## Case ID Convention

Use stable `CONT-NNN` IDs for continuity ops cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `CONT-001` | Backup, restore, upgrade, and continuity checks keep user data recoverable across runtime changes. | User-visible behavior matches source, docs, persisted state, and logs | CLI/helper, snapshots, restore markers, runtime status | `tests/release/test_continuity_audit.py` plus user-grade QA when visible | PARTIAL 2026-07-20; live independent restore, supported password recovery, browser-visible chat, saved memory, agent, upload, schedules, and stop/start persistence pass. Actual Recall rebuild and provider/channel reconnect remain blocked or outside this isolated lane |
| `CONT-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-07-19; final public-safety test and explicit private-path/identity/connection scan passed after the report update; raw evidence stays outside the repo |
| `CONT-003` | Metadata-only fallback never mutates a prior snapshot, becomes a restore source, or is presented as a recoverable backup. | Failed or unavailable payload capture cannot destroy recovery history or give false safety. | CLI/helper, `LATEST_PATH`, attempt marker, manifests, restore | Snapshot/restore fallback regressions plus helper wording contract | PASS 2026-07-19; synthetic prior snapshot stayed unchanged, failed capture preserved the atomic pointer, invalid marker-less private-helper output was not published, helper wording distinguishes complete/metadata/invalid proof, and restore rejected non-payload selections before creating state |
| `CONT-004` | Restore accepts only a positive, complete, content- and secret-policy-verified candidate and never calls legacy structural validation a complete restore. | An arbitrary/corrupt/private-state-overlapping directory cannot mutate a target or give false recovery confidence. | bundle validator, restore CLI, independent target, domain/artifact manifest | `tests/release/test_continuity_bundle.py` and `test_continuity_audit.py` | PASS 2026-07-20; automated and live Mongo runs rejected tampered, existing, symlink, nonempty, and unclaimed/misclaimed targets and rolled back an injected post-import fault without touching unrelated sentinels |
| `CONT-006` | Provider/channel/browser secrets do not migrate silently; Recall/RAG derived state never becomes canonical. | Restored users get explicit recovery/reconnect work instead of broken or leaked credentials, and stale Recall stays blocked. | manifest, restored ledgers, config, Mongo collection policy, runtime marker | `tests/release/test_continuity_bundle.py` | PASS 2026-07-20; excluded-secret policy and ledgers passed automation, the restored old browser password failed, supported one-time reset restored access, and Recall stayed marked rebuild-required while its unavailable service was reported honestly |
| `CONT-005` | Source-install upgrade is journaled and restores its exact stopped checkpoint after a recognized failure or interruption. | An existing user gets either a healthy validated candidate or the prior source/config/runtime/database/running state without lost local work. | upgrade CLI, parent/components, config/runtime, App Support state, native/legacy Mongo, Docker Mongo volume, bootstrap Python | `tests/release/test_upgrade_transaction.py`, `tests/release/test_cli_upgrade.py` | PARTIAL 2026-07-19; 9 transaction tests and 65 CLI upgrade tests pass, including no pre-checkpoint bootstrap mutation, immutable pre-pull runner use, pull/preflight/bootstrap/compile/doctor/restart failure injection, next-run interruption recovery, exact filesystem and synthetic named-volume restoration, safe bootstrap-environment symlink restoration, complete/partial new-component quarantine, and unrecognized-commit refusal. Physical power-loss and real headed Docker restart injection remain pending |
| `CONT-007` | Immutable Native snapshot publishes only complete semantic proof; same-profile restore privately validates/stages before stopping services, journals exact-root activation and resumable rollback, and restores exact prior data/service state after failure or process loss. | Easy Install users can create and restore a backup without replacing the signed release, leaking credentials/tool output, stopping a healthy runtime for invalid input, or accepting a mixed state. | Native CLI/helper, private Mongo socket, logical bundle, App Support checkpoint/journal | `tests/release/test_native_continuity.py`, `test_continuity_bundle.py`, `test_native_payload_assembler.py`, `test_native_bootstrap_ui.py`, helper Swift build | PARTIAL 2026-07-21; the pristine no-tools payload exposed and now guards a Darwin `lsof` absent-socket incompatibility. With the corrected source temporarily overlaid, the supported CLI created a complete backup and restored it into an independent target. The restored target passed password recovery, browser login, Connected Accounts/Feelings visibility, refresh and runtime-restart persistence, and zero external browser attempts. Exact rebuilt-artifact and visible helper recovery proof remain pending. |
| `CONT-008` | Complete capture and independent restore must reserve bounded working storage before mutation and remove only attempt/transaction-owned state when capacity disappears. | A backup or restore cannot silently fill the Mac, exhaust memory/inodes with archive headers, leave a partial snapshot, or create target state after a low-disk refusal. | snapshot/restore CLI, bundle manifest, App Support/uploads/Mongo filesystems | `tests/release/test_continuity_bundle.py` | PARTIAL 2026-07-21; thirteen focused synthetic capacity cases, six archive-bound regressions, and the 65-case continuity-bundle suite pass. A public-CLI low-disk run on a disposable filesystem remains pending. |

## `CONT-003` - Immutable Metadata-Only Fallback

- Preconditions: a synthetic prior snapshot with a sentinel manifest, plus private-helper absent and
  private-helper-success-without-new-path variants.
- Steps:
  1. Run the public snapshot wrapper twice against the same output root.
  2. Repeat with a synthetic private helper that exits successfully without recording a new path.
  3. Inject a manifest-capture failure and confirm `LATEST_PATH` still names the prior good snapshot.
  4. Compare the prior directory and manifest before/after.
  5. Inspect the new attempt marker, atomic `LATEST_PATH`, CLI warning, and helper success wording.
  6. Invoke restore through `LATEST_PATH` and an explicit path; confirm both fail before a live audit
     or restore-side state is created.
- Expected result: every fallback creates a distinct metadata-only attempt, prior snapshots remain
  unchanged, the user is told that no recoverable backup payload was created, and restore refuses
  to treat the attempt as payload.
- Forbidden result: latest prior manifest rewritten, history collapsed, metadata called a backup,
  a no-op private helper treated as a new payload snapshot, or default/explicit restore continuing
  against a metadata-only directory.
- Evidence to capture: prior/new paths, manifest hashes, marker, sanitized CLI/helper wording, and
  focused test output.
- Last run: PASS 2026-07-18 through synthetic wrapper, manifest-failure, restore-refusal, and helper
  source-contract tests, extended 2026-07-19 with positive marker-less refusal. Full browser-visible
  payload restore remains separately blocked.

## `CONT-001` - Core User Flow

- Requirement: Backup, restore, upgrade, and continuity checks keep user data recoverable across runtime changes.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_continuity_audit.py` plus any narrower feature tests discovered during implementation.
- Last run: PARTIAL 2026-07-20. A disposable live source install captured and restored to a distinct
  checkout, App Support root, Mongo port, and Mongo data path. Supported browser password recovery,
  history/answer visibility, saved memory, agent, upload, schedule health, and full stop/start
  persistence passed. Actual Recall rebuild was blocked because the optional RAG service was not
  available; provider/channel reconnect was intentionally not performed in this continuity lane.

## `CONT-005` - Transactional Upgrade And Rollback

- Preconditions: synthetic parent and managed-component repositories; private temporary App Support;
  old config/runtime/bootstrap/native/legacy Mongo sentinels; synthetic Docker volume adapter.
- Steps:
  1. Register the transaction while the prior runtime is logically running, arm recovery, stop, and
     create the stopped checkpoint before source/component mutation.
  2. Move parent and component revisions, alter every checkpointed sentinel, and roll back.
  3. Repeat with `compat` storage, mutate the named-volume database and add a candidate-only file,
     then compare the restored content manifest and bytes.
  4. Clone a component whose managed path was absent at begin; roll back and inspect quarantine.
  5. Create an unrecognized clean commit after interruption and verify no config/state overwrite.
  6. Exercise the CLI component failure path and the compile/doctor/restart transaction ordering
     contracts; rerun the complete focused suites.
- Expected result: known candidate state is removed, exact stopped bytes and known revisions return,
  candidate-only Docker content disappears, prior running/stopped intent is retained, and unexpected
  local work is preserved by fail-closed refusal.
- Forbidden result: live database copied as the checkpoint, Homebrew/system install inside the
  rollback promise, reset/checkout that discards work, metadata-only audit called a backup, newly
  cloned component left at an originally absent path, or semantic data-migration reversal claimed.
- Evidence to capture: transaction ledger stages, before/after hashes and Git heads, storage backend
  inventory, named-volume content manifest, process exit status, and public-safe test output.
- Last run: PARTIAL 2026-07-19. Synthetic stopped-file and named-volume rollback is PASS; physical
  power-loss and a real headed Docker/TCC restart run remain open and are not substituted by unit tests.

## `CONT-002` - Public-Safe Evidence Record

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
- Last run: PASS 2026-07-19. The dated installer report and owning QA/docs were scanned after the
  final changes; no personal path, identity, connection handoff, secret, or staged file was found.

## `CONT-007` - Immutable Native Snapshot And Restore

- Preconditions: immutable Native release layout; owner-only synthetic App Support; complete Native
  logical bundle; synthetic old/new config, Mongo, uploads, schedules, and continuity state.
- Steps:
  1. Run Native `snapshot` with an owned private Mongo socket; inject capture failure and compare the
     prior `LATEST_PATH` bytes.
  2. Validate the complete bundle, profile/database identity, owner/mode/link policy, and exact
     snapshot/schema boundary before preparing any active mutation. Copy through no-follow source
     descriptors into a private stage, hash source before/after and the copy, and mutate the source
     during copy to verify fail-closed cleanup.
  3. Stage a separate socket-only Mongo database and all file adapters on the App Support filesystem.
  4. Prove frontend/API writer quiescence for snapshot and complete listener/socket/process/open-handle
     quiescence for restore even when pid files are missing or stale; compare the exact prior service
     set after success/failure.
  5. Inject failure after each journaled activation root and compare the old mutable-state digest and
     immutable `native-runtime.json` bytes.
  6. Leave staging/activation journals and interrupt rollback after a durable prior-root rename but
     before its completed flag. Invoke recovery and verify only transaction-owned paths move, every
     remaining checkpoint validates before the next deletion, exact prior service intent returns,
     and unrelated state stays unchanged.
  7. Try impossible phase/flag sequences, corrupt/missing prior roots, incompatible data schema,
     insufficient disk, timeout/excessive input, and a signed Bootstrap with a pending journal;
     verify refusal precedes service stop, root rename, or release download.
  8. Exercise Python/Node secret variants across casing/separators/acronyms and arbitrary nested/JSON
     tool payloads. Verify raw tool-call collection/result/argument plaintext is omitted while
     ordinary message text and non-secret metadata remain.
  9. Build the helper source and inspect that Native backup/restore call the same shipped CLI, open
     only owner/private no-follow logs, and report password reset, reconnection, Recall rebuild, and
     rollback uncertainty honestly.
  10. After the API writer stops and removes its Unix socket, run snapshot on vanilla macOS whose
      system `lsof` emits an error for an absent path. Confirm the absent socket is treated as no
      listener while an existing unsafe or unverifiable path still fails closed.
- Expected result: only semantically complete Native bundles publish; restore either commits a
  health-checked Native state or restores the exact prior mutable roots; immutable release/runtime
  selection and machine secrets are never replacement roots.
- Forbidden result: metadata-only success, source/Docker cross-profile import, TCP Mongo exposure,
  service stop for an invalid snapshot, direct use of a mutable source after validation,
  symlink/hardlink traversal, partial activation, non-resumable rollback, pid-file-only quiescence,
  raw tool output/credentials in the bundle, credentials called migrated, or helper success while
  proof/rollback failed.
- Evidence to capture: sanitized pass counts, stage/journal phases, before/after synthetic hashes,
  helper build result, shipped-artifact alignment result, and real user-visible result when run.
- Last run: PARTIAL 2026-07-20. The first supported snapshot attempt on a pristine no-tools macOS
  guest reproduced a post-quiescence failure because Darwin `lsof` returns status 1 plus diagnostic
  text for the API socket that was correctly removed. A failing regression proved the source defect;
  the root fix distinguishes an absent path from an existing unsafe/unverifiable path. Four focused
  ownership/continuity tests pass, and a second supported CLI run on the same isolated guest produced
  a complete backup, restored it into an independent short-path App Support target, and started the
  restored runtime healthy while temporarily overlaying only the corrected runtime source; the
  baseline payload bytes and original running target were then restored. A separate long custom
  path failed early with the specific socket-length explanation rather than after database staging.
  The restored target then passed supported one-time password recovery, a fresh Chromium login,
  visible Connected Accounts and Feelings, refresh persistence, a complete runtime stop/start, and
  authenticated post-restart visibility with zero external browser attempts. The original QA target
  was returned to its prior healthy running state. A rebuilt exact candidate, visible helper restore,
  provider reconnect, and Recall rebuild remain pending. See
  [`reports/2026-07-20-native-snapshot-restore-transaction.md`](reports/2026-07-20-native-snapshot-restore-transaction.md).

## `CONT-008` - Storage-Bounded Capture And Restore

- Preconditions: owner-only synthetic App Support, a restore-ready bundle, synthetic config/uploads/
  schedules, and controllable capacity observations for same- and separate-filesystem layouts.
- Steps:
  1. Report less than the 10 GiB reserve before capture; verify no snapshot attempt or Mongo capture.
  2. Start capture with adequate capacity, drop below the reserve after config staging, and verify the
     incomplete attempt is removed before Mongo export.
  3. Estimate allowlisted logical Mongo bytes through the product adapter, reject boolean, negative,
     or over-bound estimates, and include the conservative working multiplier in the capture plan.
  4. Build restore plans with App Support, uploads, and Mongo on separate devices; verify compressed
     plus uncompressed bytes and one reserve per device.
  5. Repeat with all targets on one device and verify payload bytes aggregate with one reserve.
  6. Omit a visible Mongo data path and verify the unseen database gets a second conservative Mongo
     footprint on the target volume.
  7. Report low restore capacity and verify refusal precedes Mongo inspection, a journal, uploads,
     and the App Support target.
  8. Drop below the reserve after restore filesystem staging; verify the claimed database is dropped
     and every transaction-owned stage/journal is removed without touching unrelated state.
  9. Stream zero-byte archive headers at the exact per-archive cap and cap plus one; test an overlong
     PAX path, an over-deep path, a manifest count above the cap, and a bundle whose individually valid
     archives exceed the total cap.
  10. Replace a previously validated archive before extraction and verify extraction rechecks the
      header/count contract before creating its destination. Confirm capacity plans include the
      conservative per-member metadata reserve for Mongo and upload extraction.
- Expected result: capture and restore retain 10 GiB on every affected destination filesystem,
  conservative working bytes and file metadata are never discounted by compression, archive headers
  cannot grow without bound, and capacity/limit failures leave no attempt or target state owned by
  the failed operation.
- Forbidden result: starting Mongo capture/inspection on failed preflight, one reserve incorrectly
  shared across different devices, double reserve on one shared device, partial snapshot promotion,
  unbounded archive-header materialization, accepting a cap-plus-one or manifest-mismatched archive,
  target/journal creation, or deletion of unrelated state.
- Evidence to capture: focused synthetic test results, capacity-plan byte totals, absence of snapshot/
  target/journal paths, and sanitized public-CLI wording when the disposable low-disk lane runs.
- Last run: PARTIAL 2026-07-21. Thirteen focused synthetic capacity cases pass, including preflight
  ordering, bounded logical-Mongo statistics, compressed/expanded estimates, same/separate
  filesystems, unseen Mongo storage, and mid-capture/restore cleanup. Six archive-bound regression
  nodes pass for exact-cap/cap-plus-one zero-byte members, declared count, total count, UTF-8 path
  bytes, depth, and extraction recheck; capacity-plan assertions also prove the metadata reserve.
  The complete 65-case continuity-bundle suite passes.
  A real public-CLI low-disk lane remains pending and is not replaced by unit evidence.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Continuity Ops. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `CONT-UC-001` | On CLI/helper, snapshots, restore markers, runtime status, verify that backup, restore, upgrade, and continuity checks keep user data recoverable across runtime changes. | owning requirement for `CONT-001` / `CONT-001` | CLI/helper, snapshots, restore markers, runtime status | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to CONT-001. | User-visible behavior matches source, docs, persisted state, and logs | PARTIAL 2026-07-20; live browser recovery and restart persistence pass for canonical state and schedules; Recall rebuild is blocked by unavailable RAG and provider/channel reconnect was not run in this lane |
| `CONT-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `CONT-002` / `CONT-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to CONT-002. | The user sees an honest setup, retry, or degraded-state result for CONT-002; no fake success is accepted. | PASS 2026-07-19; report explicitly separates structural validation, manual recovery, and missing public restore, and public-safety checks pass |
| `CONT-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `CONT-002` / `CONT-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to CONT-002. | CONT-002 remains correct after the persistence or parity step and final wording matches evidence. | PASS 2026-07-19; final post-update scans found zero private-path/identity/connection hits and zero staged files |
| `CONT-UC-004` | Run a supported source-install upgrade against synthetic old state and inject a candidate failure or interruption. | `CONT-005` | CLI, parent/components, App Support, Mongo storage, runtime status | Ledger, hashes, Git heads, visible failure/recovery wording, and restart status | The candidate never becomes an unrecoverable mixed state; the prior state returns or rollback refuses before overwriting unexpected work. | PARTIAL 2026-07-19; focused filesystem/Docker/component/CLI automation passes; physical power-loss and headed Docker restart evidence remain open |
| `CONT-UC-005` | In Easy Install, create a complete Native backup, choose it in the helper, confirm restore, recover the local browser password, reconnect accounts, and rebuild Recall. | `CONT-007` | Native CLI/helper, installed immutable payload, browser, local state | Bundle proof, journal/checkpoint, immutable release hash, helper log, visible restored state, restart persistence | Backup publishes only after complete proof; restore keeps or rolls back one coherent state; tool argument/result payloads are explicitly omitted; the user sees accurate recovery work and restored state persists. | PARTIAL 2026-07-21; provisional-payload CLI backup/independent restore, password recovery, browser login, Connected Accounts/Feelings visibility, refresh, and runtime restart persistence pass. Rebuilt exact artifact, helper interaction, provider reconnect, and Recall rebuild remain pending. |
| `CONT-UC-006` | Create a backup or restore while the destination is low on storage, including separate App Support, uploads, and Mongo volumes. | `CONT-008` | snapshot/restore CLI, local filesystems | Capacity plan, visible refusal, snapshot/target/journal absence, and unchanged unrelated sentinels | The command refuses before durable mutation with one recovery action; no partial snapshot/target remains and no unrelated state is removed. | PARTIAL 2026-07-21; focused synthetic capacity and cleanup automation passes, while a disposable public-CLI low-disk run remains pending. |

## Release Test Traceability

- `tests/release/test_continuity_audit.py`
- `tests/release/test_continuity_bundle.py`
- `tests/release/test_upgrade_transaction.py`
- `tests/release/test_cli_upgrade.py`
- `tests/release/test_native_continuity.py`
- `tests/release/test_native_payload_assembler.py`
