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
| `CONT-005` | Source-install upgrade is journaled and restores its exact stopped checkpoint after a recognized failure or interruption. | An existing user gets either a healthy validated candidate or the prior source/config/runtime/database/running state without lost local work. | upgrade CLI, parent/components, config/runtime, App Support state, native/legacy Mongo, Docker Mongo volume, bootstrap Python | `tests/release/test_upgrade_transaction.py`, `tests/release/test_cli_upgrade.py`, `tests/release/test_mongo_engine_identity.py` | PARTIAL 2026-07-24; transaction, CLI, and explicit Mongo-engine identity tests cover direct running native/Docker observation, clean-stop bind/named-volume receipts, immutable engine revalidation, exact receipt rollback, no pre-checkpoint bootstrap mutation, immutable pre-pull runner use, upgrade failure injection, exact filesystem/synthetic-volume restoration, safe bootstrap symlinks, component quarantine, and unrecognized-commit refusal. Physical power-loss and real headed Docker restart injection remain pending |
| `CONT-007` | Immutable Native snapshot publishes only complete semantic proof; same-profile restore privately validates/stages before stopping services, journals exact-root activation and resumable rollback, and restores exact prior data/service state after failure or process loss. | Easy Install users can create and restore a backup without replacing the signed release, leaking credentials/tool output, stopping a healthy runtime for invalid input, or accepting a mixed state. | Native CLI/helper, private Mongo socket, logical bundle, App Support checkpoint/journal | `tests/release/test_native_continuity.py`, `test_continuity_bundle.py`, `test_native_payload_assembler.py`, `test_native_bootstrap_ui.py`, helper Swift build | PARTIAL 2026-07-21; the pristine no-tools payload exposed and now guards a Darwin `lsof` absent-socket incompatibility. With the corrected source temporarily overlaid, the supported CLI created a complete backup and restored it into an independent target. The restored target passed password recovery, browser login, Connected Accounts/Feelings visibility, refresh and runtime-restart persistence, and zero external browser attempts. Exact rebuilt-artifact and visible helper recovery proof remain pending. |
| `CONT-008` | Complete capture and independent restore must reserve bounded working storage before mutation and remove only attempt/transaction-owned state when capacity disappears. | A backup or restore cannot silently fill the Mac, exhaust memory/inodes with archive headers, leave a partial snapshot, or create target state after a low-disk refusal. | snapshot/restore CLI, bundle manifest, App Support/uploads/Mongo filesystems | `tests/release/test_continuity_bundle.py` | PARTIAL 2026-07-21; thirteen focused synthetic capacity cases, six archive-bound regressions, and the 65-case continuity-bundle suite pass. A public-CLI low-disk run on a disposable filesystem remains pending. |
| `CONT-009` | Source-install uploads move once from the ignored checkout predecessor into canonical App Support without overwrite, unsafe traversal, semantic drift, or snapshot/restore divergence. | Existing users keep every uploaded file across upgrade; new/source/Native paths converge on one durable root and ambiguous state stops with recovery guidance. | generated runtime env, source launcher, migration journal/receipt, continuity audit, complete snapshot/restore | `tests/release/test_uploads_migration.py`, `test_continuity_audit.py`, `test_continuity_bundle.py`, `test_config_compiler.py` | PARTIAL 2026-07-24; isolated executable CLI plus 349 focused and upgrade-transaction release tests pass, including owner/link/hardlink/bounds/no-overwrite, source mutation, pre-commit rollback, committed forward recovery, idempotency, privacy-safe semantic equality/drift gating, canonical capture, and App Support restore. A real established-user upgrade with non-private synthetic uploads and headed browser upload/download/restart persistence remains pending. |
| `CONT-010` | A supported predecessor shell that fast-forwards in place hands candidate acceptance to verified successor code before its outer transaction commits. | The first upgrade into the universal path either validates the actual new runtime and protected state or restores the predecessor without losing uploads, agents, auth/channel state, schedules, prompts, config, or databases. | exact shipped CLI process, immutable transaction ledger, successor bridge, helper artifact, runtime, protected-state manifests | `tests/release/test_first_upgrade_bridge.py`, `tests/release/test_first_upgrade_bridge_docker.py`, `test_cli_upgrade.py`, `test_continuity_audit.py`, `test_upgrade_support.py`, `test_mongo_engine_identity.py` | PARTIAL 2026-07-25; exact `d59c710` running/stopped × healthy/corrupt-helper lanes and real process-group `SIGKILL` after successor-owned candidate activation pass in disposable state, along with forced old-shell restart quiescence, same-source current-session acceptance, and resumable post-commit failure. Source ancestry is machine-readable but conditional: raw stopped durable Mongo without direct/clean-stop engine proof fails before mutation with recovery guidance. Full DB migrations/indexes/sidecars still gate after source commit, so recovery is proven but full atomicity is not. Installed Native/Docker, headed persistence, physical power-loss, and shipped/pinned/live parity remain required. |
| `CONT-011` | Strict upgrade continuity distinguishes schema-expired lifecycle records from active or durable state without exposing private values. | A legitimate TTL cleanup cannot force every upgrade to roll back, while active tokens/keys/content and durable connection, mapping, provider, prompt, schedule, memory, and agent personalization cannot disappear unnoticed. | private semantic manifest, Mongo TTL schemas, successor strict comparison | `tests/release/test_continuity_audit.py`, `test_continuity_bundle.py` | PARTIAL 2026-07-24; RED→GREEN synthetic coverage and the complete 102-case continuity audit/bundle suite pass for expired lifecycle cleanup, future token/delivery retention, all non-system/future Mongo collections, tool-call hashes, full scheduler tables/runs/outcomes, exact durable channel state, private-value exclusion, and atomic output. Installed legacy-index upgrade plus TTL-monitor/browser persistence remains pending. |
| `CONT-012` | Source upgrade and cross-checkout promotion protect ignored LibreChat auth/runtime state, helper preferences, and locally owned Telegram preferences/pairings across candidate validation, commit, helper refresh, restart, and rollback. | Existing users keep encryption keys, login sessions, connected-account credentials, custom env fields, helper status/protected-folder choices, Telegram response preferences, and Telegram-Codex pairings while declared runtime-owned fields can advance. | ignored `LibreChat/.env`, revision-bound owner snapshot, exact candidate checkpoint, `helper-config.json`, private transaction checkpoint/digests, App Support Telegram roots, successor bridge, quiesced launcher | `tests/release/test_librechat_env_upgrade_continuity.py`, `test_librechat_owner_env.py`, `test_dev_runtime_activation.py`, `test_macos_helper_install.py`, `test_upgrade_transaction.py`, `test_first_upgrade_bridge.py` | PASS-ISOLATED/PARTIAL-INSTALLED 2026-07-25; the complete 2,063-passed/11-skipped release suite proves established-source priority, true-freshness gating, conflict/missing/concurrent-drift refusal, one-read revision binding through commit, exact candidate rollback quarantine/hard-linked commit acceptance, process-group SIGKILL recovery, schema-v1 recovery, missing-runtime-backup refusal, protected/owner-secret/empty/unknown gates, later-start persisted precedence, exact Telegram state, helper-config semantic gating, complete activation-root staged-secret rejection, and committed canonical-ledger cleanup containment. Installed browser/Telegram persistence remains required. |
| `CONT-013` | Versioned nightly-default reconciliation is additive and cannot replace an existing canonical config choice on `start`, compile, configure, install, or upgrade. | Existing users keep explicit enabled/disabled, empty, worker-profile, schedule, extension, and unknown config values while missing fields receive current safe defaults exactly once. | canonical `config.yaml`, default-nightly reconciler, public CLI/start wrapper, generated runtime compile | `tests/release/test_default_nightly_routines.py`, `test_cli_upgrade.py` | PASS-AUTOMATED/PARTIAL-INSTALLED 2026-07-24 ([report](reports/2026-07-24-nightly-default-personalization-continuity.md)); RED reproduction showed three explicit-disable paths changing, then unit and real CLI-wrapper fixtures proved leaf-level preservation, additive missing defaults, unknown-field retention, mode retention, and byte-exact no-op. A disposable installed start/upgrade remains pending. |
| `CONT-016` | Transactional upgrade checkpoints generated runtime-state links without following their targets and omits nondurable Unix sockets. | Browser and AI harness runtime entries cannot block an otherwise healthy upgrade, cause an external target to be touched, or weaken special-file rejection. | App Support runtime state, immutable upgrade checkpoint, rollback | `tests/release/test_upgrade_transaction.py` nested/root symlink, socket, and FIFO cases plus supported installed upgrade | PASS-AUTOMATED/PARTIAL-INSTALLED 2026-08-02; RED reproduced both live blockers, 145 transaction/CLI tests pass, and the installed retry advances to its independent capacity gate. Exact continuity needs 41 GiB free on this 30 GiB state; 14 GiB is available, so mutation remains safely blocked. |

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

## `CONT-016` - Generated Runtime Links Stay Opaque During Upgrade

- Preconditions: an owner-controlled synthetic App Support root with generated runtime state, an
  external file target, an external directory target, a Unix socket, and separate FIFO and
  symlinked-root attack cases.
- Steps:
  1. Put file and directory links beneath generated runtime state, pointing outside App Support.
  2. Begin the upgrade transaction and verify only link metadata enters the private checkpoint and
     the nondurable socket does not.
  3. Replace both live links with candidate files/directories, then roll back.
  4. Compare the restored link text and both external target sentinels.
  5. Add a FIFO, then replace the runtime-state root itself with a link; verify each registration
     fails before a checkpoint is created.
  6. Run the supported installed upgrade against stopped GlassHive browser/harness runtime state.
- Expected result: nested generated-runtime links round-trip as opaque current-user-owned link
  entries without target traversal, Unix sockets are omitted as nondurable endpoints, and FIFOs,
  devices, roots, and ancestors remain fail-closed boundaries.
- Forbidden result: upgrade blocked by normal nested runtime links or stale sockets, target content
  copied into the checkpoint, external target mutation/deletion, socket restoration, or acceptance
  of a FIFO/device/symlinked checkpoint root.
- Evidence to capture: RED/GREEN focused results, exact link text, external sentinel hashes, absence
  of a transaction for the root-link case, supported upgrade result, and post-restart health.
- Last run: PASS-AUTOMATED/PARTIAL-INSTALLED 2026-08-02. The installed retry passed the link/socket
  inspection and failed before mutation with its precise capacity requirement: 41 GiB required and
  14 GiB available. The pre-existing running stack remained healthy.

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

## `CONT-009` - Canonical Source Uploads Migration

- Preconditions: an isolated checkout-shaped fixture, owner-only synthetic App Support, synthetic
  nested uploads, and no real user files or running services.
- Steps:
  1. Compile runtime output and confirm LibreChat/GlassHive upload variables all select App Support
     `data/uploads`.
  2. Execute the migration CLI against the isolated predecessor; verify relative file contents and
     aggregate semantic fingerprint at the canonical root, an exact compatibility link, owner-only
     journal/receipt state, no private names/content in CLI or manifest output, and an idempotent rerun.
  3. Inject symlink, hardlink, wrong-owner, file-count, mutation-during-copy, and both-roots-populated
     variants. Confirm no merge/overwrite and unchanged predecessor/canonical sentinels.
  4. Interrupt after canonical activation and confirm the next run rolls back/retries. Interrupt
     after the recorded commit point and confirm the next run completes cleanup forward without
     deleting canonical bytes.
  5. Compare pre-migration legacy and post-migration canonical aggregate fingerprints. Change one
     synthetic file and make one tree unsafe; strict semantic comparison must fail closed.
  6. Capture with only a predecessor, then with the exact canonical/link contract. Confirm ambiguous
     dual-populated roots refuse. Restore a complete bundle and verify files land under the new
     App Support target rather than the checkout.
  7. Point two synthetic App Support runtimes at one checkout. Confirm LibreChat resolves each
     compiler-owned uploads root independently; the second runtime preserves and never enumerates
     or overwrites the first runtime's receipted compatibility link, initializes its own owner-only
     root, and uses that root for continuity audit and capture. Remove or corrupt the receipt and
     confirm startup, audit, and capture fail closed.
- Expected result: one durable App Support authority, byte/path-equivalent migration, no silent
  merge or overwrite, per-runtime isolation in a shared checkout, restart-gated writer quiescence,
  deterministic recovery, and semantic continuity proof that discloses no filename, path, or content.
- Forbidden result: moving while LibreChat writes, following a link, accepting hardlinks/foreign
  ownership, choosing a configured-but-empty canonical root over a populated predecessor, deleting
  committed data during cleanup recovery, publishing private file metadata, or restoring user bytes
  into an ignored component checkout.
- Evidence to capture: RED/GREEN focused release counts, executable CLI result, before/after aggregate
  digests, journal/receipt modes, generated env values, launcher ordering, snapshot/restore target,
  privacy scan, and any real browser/user path status.
- Last run: PARTIAL 2026-08-01. Isolated synthetic automation passes the single-runtime migration,
  simultaneous and sequential two-App-Support shared-checkout isolation, fail-closed receipt,
  continuity audit/capture, and LibreChat path-selection cases (121 parent checks plus the focused
  nested path suite). No live App Support, database, conversation, schedule, prompt, or real upload
  was read or changed. Real supported-upgrade plus browser upload/download/restart persistence
  remains required before a universal-release completion claim. See
  [`reports/2026-07-24-canonical-source-uploads-migration.md`](reports/2026-07-24-canonical-source-uploads-migration.md).

## `CONT-010` - Successor-Owned First Upgrade

- Preconditions: exact supported predecessor shell bytes, a two-commit disposable source history,
  immutable stopped-state checkpoint, synthetic protected state/uploads, and a successor artifact.
- Steps:
  1. Start the predecessor CLI process, fast-forward its checkout to the successor, and prove the
     already-running shell still executes predecessor functions.
  2. At `candidate_activated`, require the downloaded continuity entrypoint to verify the immutable
     transaction, supported ancestry, shipped helper digest/architectures, stopped baseline, full
     candidate runtime, managed-agent completion, and strict semantic equality.
  3. Commit only after success, finalize deferred uploads/helper work, and restore the original
     running/stopped intent.
  4. Corrupt the successor helper and inject runtime, semantic, signal, helper, upload, and optional
     surface failures; verify exact source/config/runtime/database rollback and untouched uploads.
  5. Exercise native App Support, Docker named-volume, and Docker bind storage separately. Require
     checkpoint-derived profile/port/path plus the recorded Docker image; verify loopback-only
     readiness and exact identity-bound cleanup before the candidate runtime starts.
  6. Replay the exact support-floor isolated-Docker ledger and old inspected Docker-bind ledger.
     When engine/image provenance is absent, reject before starting Mongo rather than opening
     WiredTiger data with a guessed host/container engine.
     Repeat with stopped native bind, Docker bind, and named-volume storage using missing, unclean,
     corrupt, re-bound, mutable-tag-retargeted, missing-binary/image, and storage-anchor-changed
     receipts. Require direct observation or an owner-only clean-stop receipt; never infer from
     install mode or a candidate successfully opening a physical clone.
  7. Run both originally-running and originally-stopped exact-shell lanes. Force the old shell's
     ordinary restart branch after its outer post-capture and prove the durable receipt starts only
     the same quiesced writer inventory until commit. Repeat with a real process-group `SIGKILL`
     after successor-owned quiesced startup begins, then recover from a fresh supported CLI process.
  8. Run current-shell `upgrade --skip-pull --restart` with equal predecessor/successor identities;
     require a separate quiesced session receipt, post-commit full start for prior-running state,
     and stopped completion for prior-stopped state.
  9. Fail the post-commit full configured-runtime gate, then retry from `start`/the next upgrade.
     Require the receipt to remain resumable and protected synthetic state to remain byte-exact.
  10. Bind full startup to an owner-private run/source receipt. Keep `/health`, `/api/health`, API,
      and OAuth unavailable until database seed, channel index/restore, OAuth reconnect, permission
      migration inspection, stale-cortex recovery, and generation runtime initialization complete.
  11. Interrupt after the gateway-link `collMod`, each default-seed stage, and the first scheduler
      SQLite `ALTER TABLE`; retry and prove exact document/task preservation and final invariants.
  12. Upgrade a previously stopped install, preserve stopped intent, then perform its first later
      start. Keep the bridge pending through an API-ready/terminalizer-crash window and require the
      foreground or detached after-health finalizer to recheck protected LibreChat environment and
      helper config before terminal completion.
  13. Fail or skip the terminalizer health path. A pending post-commit identity must still arm the
      deferred monitor; terminalizer/receipt/ledger failure stops the owned runtime and stays
      retryable rather than leaving an accepting API behind.
  14. Under umask `022`, create a fresh public-CLI App Support layout and start an armed API without
      passing `--app-support-dir`. Require exported canonical authority, `0700` managed directories
      including `state/continuity`, an audit producer that creates a missing continuity directory
      privately, a complete `0600` receipt, and fail-closed refusal of a symlinked managed directory.
  15. Exercise contradictory armed-plus-quiesced input and clustered worker restart. The former
      must fail before any stage; the latter must keep exactly one durable receipt writer, local
      readiness on every worker, and bounded replacement backoff without receipt regression.
- Expected result: old/current shell behavior cannot bypass quiesced successor acceptance; a
  post-commit full-runtime failure is visible and resumable without protected-state drift. Fresh
  public-CLI state satisfies the same private-directory contract as the API verifier.
- Forbidden result: treating the fast-forwarded shell as new code, validating only ports, installing
  an unverified helper after commit, moving ignored uploads before rollback is impossible, or changing
  user-managed state to make comparison pass. A floor commit without required state proof must not
  be reported as supported or create an upgrade transaction. A permissive umask, missing environment
  export, contradictory startup mode, or clustered worker race may not strand an armed runtime
  without a valid receipt.
- Evidence to capture: predecessor/successor identities, immutable ledger/runner hashes, private
  bridge receipt, strict comparison status, helper source/binary hashes, runtime health, restored
  intent, upload fingerprint, and public-safe test output.
- Last run: **PASS-AUTOMATED / PARTIAL-INSTALLED 2026-07-31**. The exact nested API suite, focused
  parent contracts, and 2,100-case parent release suite pass. Installed browser/restart and live
  managed-agent reconciliation remain; see
  `reports/2026-07-31-postcommit-api-finalization.md`.
- Last run: PARTIAL 2026-07-25. Exact-shell running/stopped × healthy/corrupt-helper paths, forced
  old-shell restart quiescence, and process-group `SIGKILL` after successor-owned candidate
  activation pass in disposable/synthetic tests. The fresh recovery process restores exact
  source/config/runtime/database/upload/Telegram bytes plus original running/stopped intent.
  Same-source current-session acceptance and resumable post-commit failure also pass. Focused
  receipt/support/transaction tests pass for
  running and stopped native bind, Docker bind, and Docker named volume; they cover fsync/owner
  mode/integrity, mutable-tag retarget, missing executable/image, anchor drift, and exact rollback.
  Unsupported stopped durable state fails policy preflight before transaction creation. A real
  disposable Docker run proves both bind modes reach Mongo,
  preserve their exact mount identity, and remove the transaction container/QA volume. Exact
  support-floor ambiguous Docker-bind/isolated ledgers fail closed. Real installed Native/Docker,
  physical power-loss, and headed user-path evidence remain open. Deterministic database
  migration/index and complete
  configured-sidecar readiness still occur after source commit. They are now bound to a durable
  upgrade-only receipt and retry/fail-closed invariants, including stopped-install first start, but
  remain forward-recovery rather than one global rollback transaction. See
  [`reports/2026-07-24-first-upgrade-mongo-bridge.md`](reports/2026-07-24-first-upgrade-mongo-bridge.md)
  and
  [`reports/2026-07-24-postcommit-mutation-inventory.md`](reports/2026-07-24-postcommit-mutation-inventory.md).

## `CONT-011` - TTL-Aware Strict Semantic Continuity

- Preconditions: synthetic pre/post manifests, an already-expired legacy gateway link token, a
  future active token, durable channel connection/mapping rows, and schema-declared TTL policies.
- Steps:
  1. Fingerprint every expiring document as a canonical Extended-JSON digest plus its effective
     database expiry and aggregate non-expiring rows by count/hash; verify that the output contains
     no raw document ID, token, account, or content.
  2. Compare after a later candidate capture. Permit only the expired token to be absent.
  3. Remove or change the active token and change durable connection/mapping state independently;
     require strict refusal.
  4. Exercise zero-delay policies for API/provider keys, temporary conversations/messages,
     link/pairing/session/token rows; the one-hour file delay; and the seven-day user delay.
  5. Omit or corrupt the capture cutoff, TTL policy, digest, count, or lifecycle ledger; require
     fail-closed refusal rather than aggregate bypass.
- Expected result: natural TTL cleanup is normalized deterministically at the post-capture cutoff;
  every active, future, non-expiring, or durable record remains exact and private values never enter
  public evidence.
- Forbidden result: excluding a whole collection, trusting current wall-clock time, accepting a
  missing active token/key/file, weakening durable collection comparison, publishing raw IDs or
  values, or using TTL normalization to excuse concurrent runtime writes.
- Evidence to capture: policy field/delay inventory, red and green focused results, strict
  difference fields/counts, privacy assertion, complete focused-suite result, and installed
  TTL-index/browser persistence when that user-path lane runs.
- Last run: PARTIAL 2026-07-24. The new regression failed before lifecycle normalization, then
  passed with schema-driven per-document proof. The complete 99-case audit/bundle suite passes.
  No live database or installed user state was read or mutated. Installed legacy-index migration,
  TTL monitor timing, Settings > Channels visibility, refresh, and restart remain open. See
  [`reports/2026-07-24-ttl-semantic-continuity.md`](reports/2026-07-24-ttl-semantic-continuity.md).

## `CONT-013` - Additive Nightly Defaults Preserve Canonical Personalization

- Preconditions: synthetic legacy canonical config with no nightly-default version marker; explicit
  `false` and valid empty values at every nightly, Workbench, memory-hardening, GlassHive, and
  host-worker leaf; unknown nested and top-level extensions.
- Steps:
  1. Run the pure reconciler and the same shell wrapper used by `bin/viventium start`.
  2. Confirm every present value remains exact while only absent default leaves and the version
     marker are added.
  3. Run the file-writing CLI a second time and compare the complete bytes and file mode.
  4. Exercise existing later-disable and automatic worker-profile cases.
- Expected result: missing defaults are added once, explicit disable/empty/profile choices and
  unknown fields remain authoritative, and a later normal start performs no canonical-config write.
- Forbidden result: a new shipped default changes a present owner value, an empty profile triggers
  automatic account detection, an unknown extension disappears, or a no-op rewrite changes comments
  or formatting.
- Evidence to capture: RED then GREEN focused test output, semantic fixture comparison, exact
  second-run bytes/mode, CLI/start wrapper result, public-safe diff, and installed start/upgrade
  status when that lane runs.
- Last run: PASS-AUTOMATED/PARTIAL-INSTALLED 2026-07-24. Synthetic unit and executable shell-wrapper
  coverage passes without reading or changing live config, accounts, schedules, databases, prompts,
  or conversations. A disposable installed start/upgrade is still required before universal release
  signoff. See
  [`reports/2026-07-24-nightly-default-personalization-continuity.md`](reports/2026-07-24-nightly-default-personalization-continuity.md).

## `CONT-014` - Startup And Upgrade Are Semantic No-Ops For Existing Personalization

- Preconditions: synthetic existing roles, ACL grants, instance project, managed agents, canonical
  Telegram preferences, conflicting active legacy Telegram preferences, schedules, and exact
  pre-start logical exports.
- Steps:
  1. Seed/read all startup-owned Mongo rows twice and compare exact documents.
  2. Migrate the proven active legacy Telegram root into canonical App Support, retain canonical-only
     keys and a byte-exact backup, and rerun migration.
  3. Start twice through the installed helper/controller path and compare complete Mongo logical
     exports, preference tree bytes, config, schedules, and component selection.
  4. Inject candidate failure before and after publication; require the prior live selection or the
     verified App Support recovery component, never protected source execution.
- Expected result: an identical startup advances no role, grant, project, agent, or Telegram
  preference timestamp/content; only a real permission or preference change writes. Existing
  conversations, auth/provider state, prompts, schedules, and unknown personalization remain exact.
- Forbidden result: excluding timestamps to hide drift, read-then-return ACL races, startup default
  rewrites, source-tree preference writes, whole-document restore, or success inferred without a
  real second start and full logical comparison.
- Evidence to capture: exact before/after exports, focused Mongo tests, migration/backup hashes,
  selection bytes, process cwd/Python, two-start state fingerprints, and real browser/Telegram/
  Scheduler persistence.
- Last run: PASS-FOCUSED/PARTIAL-INSTALLED 2026-07-25. Sequential and atomic no-op regressions,
  migration idempotency, immutable recovery selection, pre-rollback authority reconciliation,
  interrupted-journal replay, stopped-core fallback, and component rollback structure pass.
  Exact `d59c710` process-group `SIGKILL` after successor-owned candidate activation also restores
  source/config/runtime/database/uploads/Telegram state and the original running/stopped intent in
  disposable tests. Installed double-start/export, physical power-loss, and real user-path evidence
  remain pending.

## `CONT-015` - Legacy Preference Permissions And Attempt-Bound Recovery

- Requirement: existing-user upgrade preserves personalization and remains crash-resumable.
- Risk covered: a legacy `0755` / `0644` canonical preference tree blocks the first universal
  upgrade, a process restart loses the random recovery selection, or a symlink swap changes an
  outside target during permission hardening.
- Steps: use synthetic legacy modes/content, interrupt after recovery staging, resume in a new
  process, swap a child to a symlink at open, and retry with an active writer.
- Expected result: bytes remain exact; the stopped writer path hardens to `0700` / `0600`; the exact
  selection is journaled; unsafe swaps/writers fail before mutation; rollback remains resumable.
- Forbidden result: preference loss/default rewrite, path-based chmod through a symlink, guessed
  staging selection, or live-writer mutation.
- Last run: PASS-AUTOMATED/PARTIAL-INSTALLED 2026-07-25. Descriptor-race, process-isolated migration,
  activation, and rollback regressions pass; final installed restart/state comparison remains open.

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
| `CONT-UC-007` | Upgrade an established source install with synthetic uploads, then upload/download in the browser and restart. | `CONT-009` | supported upgrade CLI, source launcher, browser, App Support | pre/post aggregate fingerprint, migration journal/receipt, generated env, visible file, restart persistence, logs | Existing uploads remain visible and downloadable, new uploads use App Support, and retry/restart never creates two authorities. | PARTIAL 2026-07-24; isolated executable CLI and semantic/snapshot/restore automation pass. Supported upgrade and headed browser persistence have not been run in this protected lane. |
| `CONT-UC-008` | Run the first supported upgrade from an installed predecessor, including a forced candidate/helper failure, then inspect the browser and restart. | `CONT-010` | exact predecessor CLI, installed runtime/helper, browser, App Support | bridge/ledger receipts, semantic manifests, helper hashes, visible conversations/uploads/agents/schedules, logs and DB counts | A valid successor returns healthy with all personalizations intact; a rejected successor returns the exact predecessor and original intent. | PARTIAL 2026-07-25; exact-shell disposable healthy/failure plus process-group `SIGKILL` recovery paths pass for originally running and stopped installs. Installed Native/Docker, browser refresh, restart, and physical power-loss evidence remain open. |
| `CONT-UC-009` | Upgrade an isolated established install containing an expired legacy gateway link token, an active token, and durable channel personalization, then open Channels and restart. | `CONT-011` | supported upgrade CLI, Mongo, Settings > Channels, runtime logs | pre/post private TTL ledgers, strict comparison, TTL index metadata, visible connection state, refresh/restart persistence | The expired token may age out; the active token and durable channel/auth/provider state remain exact; upgrade succeeds without exposing private values. | PARTIAL 2026-07-24; synthetic semantic and privacy automation passes. Installed TTL monitor, browser, and restart evidence has not run. |
| `CONT-UC-010` | Start an established install twice, then upgrade with legacy Telegram preferences and force rollback once. | `CONT-014`, `TR-014` | installed CLI/helper, Mongo, Telegram, browser, Scheduler | full logical exports, canonical files, component receipts, visible persistence and latency | Both starts are semantic no-ops; success and rollback preserve every personalization and use App Support execution. | PASS-FOCUSED/PARTIAL-INSTALLED 2026-07-25; real double-start and cross-surface lane pending |

## Release Test Traceability

- `tests/release/test_continuity_audit.py`
- `tests/release/test_continuity_bundle.py`
- `tests/release/test_upgrade_transaction.py`
- `tests/release/test_upgrade_support.py`
- `tests/release/test_cli_upgrade.py`
- `tests/release/test_native_continuity.py`
- `tests/release/test_native_payload_assembler.py`
- `tests/release/test_uploads_migration.py`
- `tests/release/test_first_upgrade_bridge.py`
- `tests/release/test_telegram_user_config_migration.py`
- `tests/release/test_telegram_runtime_component.py`
