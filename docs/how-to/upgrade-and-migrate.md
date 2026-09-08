# Upgrade, restore, and migrate

## Upgrade

```sh
bin/viventium snapshot
bin/viventium upgrade
```

Use `bin/viventium upgrade --restart` only when the pre-upgrade snapshot and continuity checks are
acceptable. Upgrade must preserve user state, recompile generated artifacts, validate the active
candidate, and refuse false readiness.

## Startup changes in this source upgrade

GlassHive is a required startup dependency when the configured Main route uses its harness.
Startup now stops on missing or unhealthy GlassHive instead of reporting a ready chat whose
configured Main cannot execute. Resolve the reported GlassHive health or authentication failure
and retry; optional Redis retains bounded readiness and deferred recovery.

Existing source installations must explicitly adopt their verified LibreChat instance credentials
before first startup when `state/native-secrets.json` is absent. Use the existing credential
owner's `source-secrets --help` and its exact instance/legacy-env checks; do not generate replacement
keys or delete existing state to bypass adoption. Fresh source installation initializes a new
instance; Native instances keep their existing secret owner. The public Easy Install bootstrap
now enforces the complete payload's macOS 15 minimum; compatible helper binaries alone do not
lower the complete package requirement.

## Restore validation

```sh
bin/viventium continuity-audit
bin/viventium restore --snapshot-dir /path/to/snapshot --validate-only
```

Validation checks bundle structure, hashes and the applicable logical data contract without changing
target state. A legacy structurally valid bundle can still be ineligible for restore; inspect
`recoverable`, `restoreEngine`, and `semanticValidation` rather than treating validation as a
completed recovery.

## Restore an independent source target

The implemented transactional source restore requires a complete eligible bundle, an absent
independent App Support target, a fresh independent checkout with LibreChat, and an empty
credential-free loopback Mongo database with a different database name. Source, snapshot and
destination roots cannot overlap.

```sh
bin/viventium restore --snapshot-dir /path/to/snapshot \
  --target-config-home /path/to/independent-state \
  --target-repo-root /path/to/independent-checkout \
  --target-mongo-uri mongodb://127.0.0.1:27018/restored_chat \
  --target-mongo-data-path /path/to/independent-mongo
```

The transaction validates and stages data, claims the empty target database, restores only owned
state, and activates the target with a rollback journal. Failure rolls back its own writes; an
incomplete rollback remains an explicit error with its journal. Restore records required Recall
rebuild and account/channel reauthentication; credentials and browser sessions are not portable.
The optional independent Mongo data directory binds restart to the same persistence store.

Native payload snapshots use the existing Native restore transaction in
[`native_runtime.py`](../../scripts/viventium/native_runtime.py). Snapshots with Native GlassHive
state are refused by the source restore command. Follow the installed Native command's
`restore --help` and its exact-root
activation/rollback contract. Do not route Native state through a source-checkout apply command.

An eligible bundle and a successful transaction are supporting evidence. Complete recovery still
requires opening the independent target's real history and artifacts, checking memories and
schedules, rebuilding derived Recall, reconnecting permitted accounts, and proving restart and
rollback. See [continuity acceptance](../../qa/continuity-ops/cases.md) and the
[runtime journey](../../qa/runtime-install-release/cases.yaml).

## Component delivery

For a managed nested repository, keep these aligned where applicable:

1. reviewed component source and commit
2. parent pin in `components.lock.json`
3. compiled or prebuilt output
4. installed and running artifact
5. user-visible behavior and durable state

Do not call a local source edit shipped when another machine cannot obtain those same bytes through
the supported install or upgrade path.

The v0.3 comparison guide remains historical context at
[`07_MIGRATION_GUIDE.md`](../07_MIGRATION_GUIDE.md); v0.4 is the active product.
