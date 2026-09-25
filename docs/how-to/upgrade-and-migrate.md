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

## xPerfect component migration

xPerfect replaces the managed GlassHive source at `viventium_v0_4/xPerfect/`.
Existing `integrations.glasshive` settings and state paths continue to work. Keep the original
GlassHive checkout; do not repoint its remote or replace it with a symlink.

For an existing runtime, record its active checkout and take a consistent state snapshot. Use
the existing validated activation transaction to promote the candidate; it checks component pins
before state mutation and owns rollback when activation fails. Verify the new component pin,
serving process, and persistent workspace. A healthy old listener is rejected; stop that runtime
through its owning checkout before retrying. Retain any incomplete recovery journal.

Test recovery on isolated state before promotion. Older code may not support a database opened by
a newer runtime. Preserve both the pre-upgrade backup and any new state; changing the source pointer
alone does not prove rollback. Use the source or Native restore owner and its independent-target
requirements described above.

### Main context V1 caller migration

After upgrade, a Viventium Main turn must use the current Core-owned `main_context_v1` carrier from
its accepted conversation history. Keep the existing `integrations.glasshive` setting, selected
`glasshive-harness` provider, model, and owner credentials. The upgrade does not require a provider
or model change. Verify a resumed Main conversation and a new turn against the same owner before
calling the migration complete.

For a prior provider-owned V1 conversation, the selected owner-bound Mongo branch must contain
every meaningful prior message. Core carries the exact old messages as protected sources on the
new V1 request, including after reload. If an ancestor is missing or cyclic, pruning removes a
message, an old entry cannot be represented exactly, or the branch exceeds the bounded source
carrier, the turn stops with
`source_context_unavailable` instead of
silently claiming full continuity. A clipped provider ledger row cannot fill missing Mongo
history; pause cutover when the needed context exists only there.

An external caller that declares `main_context_owner=provider_legacy` with `main_context_v1` must
move to the Core-owned carrier through Viventium. The old provider-owned cross-thread claim is
rejected; removing only the owner field does not convert its bounded old ledger to Core history.
Standalone callers may instead use ordinary conversation requests without a V1 claim and retain
their normal session behavior. Keep the old provider context rows with the pre-upgrade checkpoint;
the source upgrade does not rewrite them. If the old caller requires provider-owned cross-thread
Main memory, pause that caller's cutover until an explicit owner-scoped migration is implemented and
tested. A successful source transaction alone does not prove this semantic migration.
