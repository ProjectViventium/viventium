# Continuity Ops QA

## Scope

Verify that the supported local continuity operations prevent stale-state drift without leaking
private data into the public repo or asking operators to hand-edit runtime state.

Covered surfaces:

1. continuity metadata capture
2. manual snapshot creation
3. restore-age gating and pre-apply safety copies
4. upgrade-time continuity review
5. recall stale-restore gating
6. helper backup UX
7. helper install/update refresh proof

## Requirements Under Test

- `bin/viventium snapshot` always writes a sanitized `continuity-manifest.json` under the selected
  snapshot root.
- The public snapshot wrapper still succeeds when no private companion snapshot helper exists.
- The manifest stays metadata-only:
  - no secrets
  - no raw message text
  - no raw prompts
  - no raw DB URIs
  - no absolute private home-directory paths
- The helper backup button uses the same supported CLI snapshot path instead of a second
  implementation.
- `bin/viventium restore` captures a live continuity audit and refuses an older snapshot unless the
  operator passes `--allow-older-snapshot`.
- Restore creates a pre-apply safety backup before overwriting directly affected local state.
- If restore leaves recall-derived state stale, the recall rebuild-required marker is written and
  vector-backed recall stays unavailable until the operator intentionally clears it.
- `bin/viventium upgrade --restart` captures pre/post continuity audits and blocks automatic
  restart on `error`.
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
2. Continuity audit command
   - capture live continuity metadata
   - confirm severity is honest when some surfaces cannot be inspected
3. Restore-age comparison
   - compare snapshot and live manifests
   - confirm older snapshot surfaces produce `error`
   - confirm no comparable timestamps produces `warning`
4. Upgrade gating
   - confirm upgrade writes pre/post continuity audit paths
   - confirm `--restart` is blocked when the post-upgrade audit reports `error`
5. Recall stale-restore gate
   - confirm the runtime reports an explicit stale-restore reason while the marker exists
   - confirm operator clear path exists separately from startup
6. Helper backup UI
   - confirm the status bar helper shows `Create Backup Snapshot`
   - confirm it runs the snapshot CLI path and logs to `helper-snapshot.log`
7. Helper refresh after install/update
   - refresh the installed helper bundle from the shipped prebuilt
   - prove the visible menu item is present in the live status menu after refresh
   - trigger the menu action once and confirm the live helper logs the request/completion pair

## Expected Results

- The continuity manifest path is public-safe and stable even without private helper enrichment.
- Restore refuses to roll continuity backward by default.
- Upgrade does not auto-restart through known continuity errors.
- Recall cannot silently pretend restored vector state is fresh.
- The helper backup action is easy to use and stays on the same supported backup path as the CLI.
- Helper refresh drift is detectable and recoverable with the supported install-helper path.
- Public docs and QA evidence describe only sanitized metadata and synthetic examples.
