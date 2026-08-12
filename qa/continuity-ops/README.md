# Continuity Ops QA

## Scope

Verify that the supported local continuity operations prevent stale-state drift without leaking
private data into the public repo or asking operators to hand-edit runtime state.

Covered surfaces:

1. continuity metadata capture
2. manual snapshot creation
3. complete-bundle candidate validation and no-mutation restore refusal
4. upgrade-time continuity review
5. recall stale-restore gating
6. helper backup UX
7. helper install/update refresh proof
8. positive complete-bundle structural validation and independent-target refusal safety

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
- The current public apply path is explicitly unavailable. After validation, every non-validation
  invocation returns `4` before creating an audit, copying channels, writing a Recall marker, or
  changing the target. Legacy apply/age/marker flags are accepted only to return truthful unavailable
  guidance. Validation must not be described as restoration.
- Snapshot and target roots must not overlap. Structural, checksum, and bounded format validation
  does not perform Mongo semantic validation and returns `semanticValidation: not_performed`.
- The manifest stays metadata-only:
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
- `bin/viventium upgrade --restart` captures pre/post continuity audits, stops a running stack before
  pull, installs the helper without launch, and permits restart/helper launch only for explicit
  `ok` or `warning`. Error, unknown, malformed, and capture failures do not auto-restart.
- `bin/viventium continuity-audit` can both capture the current continuity state and intentionally
  clear the recall rebuild marker after rebuild.
- Manual on-demand snapshot creation is the default product path; the public contract does not rely
  on mandatory daily full backups.

## Environments

- parent public repo checkout
- nested LibreChat repo checkout
- macOS helper source + rebuilt matching prebuilt helper binary
- synthetic or sanitized machine-local continuity manifests only

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
3. Restore refusal and candidate validation
   - point `LATEST_PATH` at a metadata-only attempt and confirm restore fails before live audit
   - explicitly select the same kind of attempt and confirm the same fail-closed result
   - validate positive complete candidates with standard-library-only Python
   - reject source/target overlap, marker-less, partial, corrupt, oversized, and expansion-bomb inputs
   - confirm legacy apply flags return `4` without touching target/channel/Recall state
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
8. Complete-bundle candidate validation
   - validate a synthetic complete bundle and verify every required domain and artifact role
  - reject marker-less, partial, malformed, corrupt, traversal, collision, symlink, hardlink, and
    undeclared-file variants before target mutation
   - run `--validate-only` against an absent independent target and verify the target remains absent
  - run the unavailable apply path and verify it exits `4` with an explicit PARTIAL/no-mutation result

## Expected Results

- The continuity manifest path is public-safe and unique per attempt without private helper
  enrichment; a metadata audit is never presented as a recoverable backup.
- Metadata-only attempts cannot be dereferenced as default or explicit restore payloads.
- Arbitrary legacy/marker-less directories cannot become restore payloads merely because they lack
  the metadata-only marker.
- Positive candidate validation is content- and domain-aware, public-safe, and
  target-side-effect-free, but returns `recoverable: false` until independent restore is proven.
- Until every apply adapter exists, the CLI never enters partial follow-through, returns apply
  success, or claims complete recovery after validation.
- Restore refuses every apply until a transactional engine can prove independent-target recovery.
- Upgrade does not auto-restart through known continuity errors.
- Recall cannot silently pretend restored vector state is fresh.
- The helper action stays on the same supported CLI path and reports whether it created a backup or
  metadata-only audit.
- Helper refresh drift is detectable and recoverable with the supported install-helper path.
- Public docs and QA evidence describe only sanitized metadata and synthetic examples.
