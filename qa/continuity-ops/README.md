# Continuity Ops QA

## Scope

Verify that the supported local continuity operations prevent stale-state drift without leaking
private data into the public repo or asking operators to hand-edit runtime state.

Covered surfaces:

1. continuity metadata capture
2. manual snapshot creation
3. complete logical-bundle capture and independent-target transactional restore
4. upgrade-time continuity review
5. recall stale-restore gating
6. helper backup UX
7. helper install/update refresh proof
8. positive complete-bundle structural, semantic, privacy, rollback, and target-isolation safety
9. transactional source-install upgrade checkpoint, rollback, interruption recovery, and prior-state restart
10. immutable Native complete snapshot, same-profile restore, journal recovery, and helper UX

## Requirements Under Test

- `bin/viventium snapshot` always writes a sanitized `continuity-manifest.json` under a newly
  allocated attempt directory inside the selected snapshot root.
- The public snapshot wrapper still succeeds when no private companion snapshot helper exists.
- Metadata fallback never reuses or rewrites the latest prior snapshot. It carries an explicit
  metadata-only marker and says that no recoverable backup payload was created.
- `LATEST_PATH` is replaced atomically only after manifest capture succeeds; capture failure keeps
  the prior last-good pointer.
- Restore rejects a metadata-only `LATEST_PATH` or explicit snapshot selection before creating a
  live audit, recall marker, safety copy, or other restore-side state.
- Absence of the metadata-only marker is never proof of recovery. Restore requires both
  `.viventium-recoverable` with marker version `v1` and a valid `recoverable-manifest.json` before
  any target mutation.
- A complete bundle declares every continuity domain exactly once: canonical config, logical Mongo
  state, user files, schedules, derived Recall/RAG state, auth reauthentication, and channels.
- Every payload artifact has one canonical relative path, domain/role, capture method, schema,
  media type, byte size, and SHA-256. Validation rejects traversal, case collisions, symlinks,
  hardlinks, special files, undeclared files, checksum/size mismatch, invalid config/gzip/SQLite/JSON,
  boolean schema versions, archive expansion bombs, and missing/duplicate domains. The validator is
  standard-library-only so a stock macOS Python can run it without bootstrapping App Support.
- `restore --validate-only --target-config-home <empty-target>` validates the producer assertion,
  structure, declared content formats, and hashes without creating the target. It does not prove
  recovery. Marker-less, partial, malformed, or corrupt bundles fail before target state exists.
- A restore-ready public bundle adds a sanitized canonical config, allowlisted logical Mongo exports
  with per-collection hashes/counts, a bounded uploads archive, and a SQLite schedule backup. The
  manifest records the runtime profile plus generated-runtime/helper-regeneration policy.
- Complete capture performs a conservative capacity check using known source bytes plus bounded
  allowlisted Mongo collection statistics before creating a snapshot attempt, retains a 10 GiB
  floor between phases, and removes an incomplete attempt when that floor is lost.
- Independent restore counts both compressed and declared uncompressed working bytes, groups them by
  destination filesystem with one 10 GiB reserve per volume, and refuses low capacity before Mongo
  inspection, a transaction journal, or target state. Phase-floor failure uses the same owned-state
  rollback path.
- Provider keys, OAuth/session tokens, action/MCP/plugin-auth credentials, channel credentials, and
  browser passwords are excluded. Restore writes an explicit reauthentication ledger; it never
  describes those credentials as migrated. Inline canonical-config secrets are nulled while safe
  Keychain references may remain. Source installs reuse LibreChat's pinned Node MongoDB/BSON
  packages rather than requiring separate host Mongo command-line tools.
- The bundle is owner-only and explicitly not self-encrypted. The supported policy requires an
  encrypted host/external volume for at-rest cryptographic protection; the product must not imply
  that mode bits alone provide portable encryption.
- Apply requires an absent independent App Support target, a fresh separate checkout with no
  uploads directory, and an empty credential-free loopback Mongo database whose name differs from
  the source. The bundle must remain current-user owner-only. Existing/personal state, overlap,
  nonempty databases, symlinks, hardlinks, and unsafe ownership fail before mutation.
- Restore stages all filesystem adapters, transaction-claims the proven-empty isolated Mongo
  database, imports logical data, activates only after validation, and removes only claimed
  Mongo/filesystem state on failure or handled interruption. Pending activation flags cover a fault
  immediately after rename. Recall/RAG stays blocked behind a rebuild-required marker.
- Successful apply writes a strict owner-only runtime-selection ledger. The compiler accepts only
  the current schema/profile/config/output binding and, for the restartable `v2` contract, binds the
  declared independent loopback Mongo port and owner-only data path into generated runtime output.
  Restore creates a new target-local internal call-session secret; it never copies provider,
  channel, browser, or source-runtime credentials.
- Snapshot and target roots must not overlap. Legacy structural-only candidates return
  `semanticValidation: not_performed`; current logical bundles validate the collection index,
  document syntax/counts/hashes, and secret policy and return `semanticValidation: performed`.
- The separate `continuity-manifest.json` audit stays metadata-only:
  - no secrets
  - no raw message text
  - no raw prompts
  - no raw DB URIs
  - no absolute private home-directory paths
- The helper backup button uses the same supported CLI snapshot path instead of a second
  implementation.
- A private helper's new directory is published as a backup only after the public complete-bundle
  validator accepts it. A marker-less, partial, or corrupt new directory is retained as an invalid
  attempt but `LATEST_PATH` is moved to a new metadata-only attempt instead.
- The helper distinguishes complete, metadata-only, and invalid proof. Missing markers/manifests
  can never produce a success alert.
- `bin/viventium upgrade --restart` captures pre/post continuity audits, registers rollback and arms
  its trap before shutdown, then checkpoints stopped config/runtime/product-owned state and the
  active Mongo backend before source mutation. Candidate config/runtime are staged and validated
  separately. Pull, component, compile, doctor, continuity, restart, and interruption failures
  restore recognized source/component revisions, exact checkpointed bytes, and prior running state.
  Unknown local work makes rollback fail closed. System prerequisite installation is never hidden
  inside the transaction; upgrade checks and asks the user to apply missing prerequisites separately.
- `bin/viventium continuity-audit` can both capture the current continuity state and intentionally
  clear the recall rebuild marker after rebuild.
- Manual on-demand snapshot creation is the default product path; the public contract does not rely
  on mandatory daily full backups.
- Native snapshot and restore use the shipped immutable payload only. Snapshot binds capture to the
  exact owner-checked Mongo Unix socket, quiesces proxy/API writers, restores the exact prior service
  set, and publishes `LATEST_PATH` only after complete semantic validation. Restore accepts only a
  schema-compatible Native bundle, privately copies and hash-verifies the input before use, stages on
  the App Support filesystem, uses a separate socket-only Mongo staging process, proves complete
  process/socket/open-handle quiescence, and journals each exact mutable-root rename.
- Native restore preserves the immutable release pointer, generated Native runtime, machine secrets,
  and helper binding. The strict phase/flag journal prevalidates the complete remaining checkpoint,
  records every rollback root transition and the prior service intent, and resumes after process loss
  during activation or rollback. Read-only lifecycle paths fail closed; mutating paths recover only
  under the installed release identity; signed Bootstrap installation stops before download while a
  journal exists. Success explicitly requires browser password recovery, account/channel
  reconnection, and Recall rebuild.
- Complete logical capture excludes the raw `toolcalls` collection and strips argument/result
  payloads from tool-call message parts. Arbitrary tool output can contain credentials under safe
  keys or in plaintext, so this intentional fidelity loss is required for the backup secret boundary;
  ordinary message text remains in the owner-only bundle.
- Helper logs are opened only through owner-only, no-follow regular-file descriptors. Restore input,
  hashing, copying, adapter execution, file count, byte expansion, disk reserve, and service waits are
  bounded and fail closed. Tar headers are checked incrementally before extraction with per-archive
  and bundle-total member caps, UTF-8 path-byte and depth caps, exact upload-manifest count binding,
  and the same checks repeated at extraction. Capacity plans reserve conservative per-member metadata
  overhead as well as compressed and expanded bytes.

## Environments

- parent public repo checkout
- nested LibreChat repo checkout
- macOS helper source + rebuilt matching prebuilt helper binary
- synthetic or sanitized machine-local continuity manifests only
- synthetic local Mongo adapter binaries and `.invalid` identities for automated data-plane tests
- disposable Apple Silicon macOS VM with synthetic accounts/data, a distinct loopback Mongo target,
  real source-install services, and a real Chromium browser; private commands, logs, and screenshots
  stayed outside the public repo

Latest result: [`reports/2026-07-20-complete-snapshot-independent-restore.md`](reports/2026-07-20-complete-snapshot-independent-restore.md)

Native transaction result: [`reports/2026-07-20-native-snapshot-restore-transaction.md`](reports/2026-07-20-native-snapshot-restore-transaction.md)

## Test Cases

1. Manifest-only snapshot path
   - force the public snapshot wrapper to run without a private companion helper
   - confirm it still writes `LATEST_PATH` and `continuity-manifest.json`
   - confirm the manifest stays metadata-only
   - seed a prior snapshot and confirm repeated fallback creates a distinct attempt without changing
     the prior manifest
   - inject manifest capture failure and confirm the prior `LATEST_PATH` remains unchanged
   - repeat with a private helper that exits successfully without recording a new snapshot path
2. Continuity audit command
   - capture live continuity metadata
   - confirm severity is honest when some surfaces cannot be inspected
3. Restore validation and independent-target transaction
   - point `LATEST_PATH` at a metadata-only attempt and confirm restore fails before live audit
   - explicitly select the same kind of attempt and confirm the same fail-closed result
   - validate positive complete candidates with standard-library-only Python
   - reject source/target overlap, marker-less, partial, corrupt, oversized, and expansion-bomb inputs
   - simulate separate App Support, uploads, and Mongo filesystems; verify compressed plus expanded
     requirements and one reserve per filesystem, and verify low disk fails before Mongo inspection,
     journal creation, uploads staging, or App Support target creation
   - confirm legacy apply flags return `4` without touching target/channel/Recall state
   - restore a synthetic ready bundle to an absent App Support target, separate checkout, and empty
     synthetic loopback Mongo adapter; verify config, chats/users, uploads, schedules, Recall marker,
     reauthentication ledger, and runtime selection
   - inject faults after staging, Mongo import, and activation; verify all transaction-owned state
     rolls back while unrelated sentinels remain byte-for-byte unchanged
   - repeat on a disposable live source install using an independent loopback Mongo port/data path;
     compile, start, recover the browser user through the supported one-time reset link, verify chat,
     saved memory, agent, upload, schedules, stop/start, and verify the same browser-visible answer
   - tamper the bundle; use existing/symlink targets, nonempty databases, missing/mismatched database
     claims, and a fault after real Mongo import; verify refusal or transaction-owned rollback
4. Upgrade gating
   - confirm upgrade writes pre/post continuity audit paths
   - confirm `--restart` is blocked when the post-upgrade audit reports `error`
5. Recall stale-restore gate
   - confirm the runtime reports an explicit stale-restore reason while the marker exists
   - confirm operator clear path exists separately from startup
6. Helper backup UI
   - confirm the helper distinguishes a recoverable snapshot from continuity metadata
   - confirm it runs the snapshot CLI path and logs to `helper-snapshot.log`
7. Helper refresh after install/update
   - refresh the installed helper bundle from the shipped prebuilt
   - prove the visible menu item is present in the live status menu after refresh
   - trigger the menu action once and confirm the live helper logs the request/completion pair
8. Complete-bundle capture and semantic validation
   - validate a synthetic complete bundle and verify every required domain and artifact role
   - verify low disk fails before snapshot/Mongo capture, and a reserve-floor loss between phases
     removes the incomplete attempt
   - reject marker-less, partial, malformed, corrupt, traversal, collision, symlink, hardlink, and
    undeclared-file variants before target mutation
   - stream exact-cap and cap-plus-one zero-byte members; reject overlong/deep PAX paths, a declared
     upload count above the cap, and a bundle-total member overflow before extraction
   - replace a validated archive before apply and verify extraction rechecks count/path limits before
     creating its destination; include per-member metadata overhead in restore capacity plans
   - run `--validate-only` against an absent independent target and verify the target remains absent
   - run the supported independent-target apply path and verify transactional success plus explicit
    reauthentication/Recall follow-up
   - run a live independent restore, compile/start the recovered runtime, complete supported browser
     password recovery, verify canonical content and schedules, then stop/start and verify persistence
9. Transactional upgrade rollback
   - inject source/component, candidate compile, doctor, and restart failure boundaries
   - mutate synthetic config/runtime/bootstrap/legacy Mongo/runtime database bytes after checkpoint
   - mutate a synthetic Docker named Mongo volume after checkpoint and verify its content manifest
     returns exactly to the stopped checkpoint
   - interrupt at a journaled stage and verify the next upgrade recovers before new mutation
   - create a managed component absent at transaction start and verify rollback quarantines it
   - create an unrecognized post-interruption commit and verify rollback preserves it and refuses
10. Native snapshot and same-profile restore
   - capture through the shipped CLI against the exact private Mongo socket and confirm the prior
     `LATEST_PATH` remains unchanged on injected capture failure
   - reject source/Docker profiles, overlapping snapshot roots, symlinks, hardlinks, unsafe modes,
     altered manifests, and a staging directory on another filesystem before live mutation
   - inject failure after each mutable-root activation and verify config, Mongo, uploads, schedules,
     continuity state, and immutable release-pointer bytes return exactly
   - leave an activation or staging journal and verify the next lifecycle recovery removes only
     transaction-owned state
   - interrupt rollback after a prior-root rename but before its completed flag; rerun recovery and
     verify exact bytes and prior stopped/Mongo-only/full service intent return
   - remove/stale pid records while listeners, sockets, or mutable-root handles remain and verify no
     live root rename occurs
   - mutate the selected snapshot during its private no-follow copy; verify the stage is removed and
     the healthy runtime/journal remain untouched
   - reject corrupt phase/flag sequences, incompatible data schemas, insufficient disk, excessive
     file/byte/time work, and pending-journal signed Bootstrap before live mutation or download
   - prove secret-key case/separator/acronym variants are removed in Python and Node and prove raw
     tool-call argument/result plaintext never enters the logical bundle
   - build and inspect the helper source; verify Native backup and restore call the same shipped CLI,
     produce owner-only no-follow local logs, and never report failed proof as success

## Expected Results

- The continuity manifest path is public-safe and unique per attempt without private helper
  enrichment; a metadata audit is never presented as a recoverable backup.
- Metadata-only attempts cannot be dereferenced as default or explicit restore payloads.
- Arbitrary legacy/marker-less directories cannot become restore payloads merely because they lack
  the metadata-only marker.
- Positive current-format validation is content-, domain-, secret-policy-, and logical-Mongo-aware
  and returns `recoverable: true`; legacy complete candidates stay inspection-only with
  `recoverable: false`.
- Independent-target apply is transactional and never overwrites existing App Support, uploads, or
  Mongo state. Failure rolls back only transaction-owned state.
- The restored runtime remains bound to its declared independent Mongo port/data path after a full
  stop/start, while source state remains separate.
- Restore success truthfully requires account/channel reauthentication, browser password recovery,
  generated-runtime/helper regeneration, and Recall rebuild before normal use.
- Upgrade does not auto-restart through known continuity errors and does not leave a recognized
  failed candidate as the active source/config/runtime/database state.
- Recall cannot silently pretend restored vector state is fresh.
- The helper action stays on the same supported CLI path and reports whether it created a backup or
  metadata-only audit.
- Helper refresh drift is detectable and recoverable with the supported install-helper path.
- Public docs and QA evidence describe only sanitized metadata and synthetic examples.
- Capture and restore capacity checks fail before durable target mutation, retain their declared
  reserve, and clean only their own incomplete or transaction-owned state.
- Native backup publication is atomic, same-profile restore is rollback-safe, and the immutable
  release and machine secrets are not part of the replacement set.
