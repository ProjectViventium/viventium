# Canonical Source Uploads Migration — 2026-07-24

<!-- qa-evidence-exempt: Source-only migration note; the cross-surface user-grade acceptance is recorded in the universal-upgrade run report. -->

## Outcome

The source-install default now converges on App Support `data/uploads`, matching the Native storage
boundary. The implementation was developed and tested only against isolated synthetic fixtures. No
live App Support files, uploads, database, conversations, schedules, prompts, credentials, or
running user services were read or changed.

Status: **PARTIAL** for universal-release acceptance. The code and isolated transaction evidence are
green; a supported established-user upgrade and headed browser upload/download/restart run remain.

## Evidence

- RED: the new migration, canonical compiler output, launcher ordering, aggregate fingerprint,
  strict comparison, canonical capture, and canonical restore assertions initially produced 12
  expected failures.
- GREEN before final report refresh: 253 focused tests passed across:
  `test_uploads_migration.py`, `test_continuity_audit.py`, `test_continuity_bundle.py`, and
  `test_config_compiler.py`.
- The executable Python CLI migrated a checkout-shaped temporary fixture, preserved synthetic bytes
  and relative hierarchy, created the exact compatibility link, and emitted no synthetic filename
  or content.
- Security/failure fixtures cover unexpected symlinks, hardlinks, wrong ownership, file-count
  bounds, dual-populated roots, source mutation during copy, interrupted target activation,
  interrupted committed cleanup, rollback/retry, and idempotency.
- Upgrade semantic proof hashes relative paths and file contents but stores only availability,
  aggregate file count, aggregate bytes, and SHA-256. Tests prove equal trees at different roots
  compare equal, content drift fails, unsafe proof fails closed, and output contains no names or
  contents.
- Complete capture selects the recognized predecessor only before migration, canonical App Support
  after the exact link contract, and refuses ambiguous dual-populated roots. Independent restore
  stages uploads inside the new App Support target.

## Delivery Surfaces

- Tracked source: implemented in the reviewed release candidate.
- Generated runtime: compiler assertions prove canonical LibreChat/GlassHive values.
- Launcher: static ordering proves the migration gate precedes upload-consuming parallel services
  and a stopped backend start.
- Upgrade checkpoint: existing strict pre/post comparison now includes the aggregate uploads
  fingerprint, with legacy fallback for the pre-upgrade predecessor.
- Installed/running artifact: not changed or tested in this lane.

## Remaining Real QA

1. Run the supported source `upgrade --restart` from an actually supported predecessor in a
   disposable account/VM with synthetic uploads.
2. In a headed browser, download a predecessor upload, create a new upload, expand its detail state,
   refresh, restart the full runtime, and repeat the download.
3. Correlate visible results with canonical App Support bytes, generated runtime env, migration
   receipt, source compatibility link, strict pre/post audit, and logs.
4. Inject a real process/power interruption on a disposable filesystem and verify the next supported
   start takes the expected rollback or forward-recovery path.
5. Verify the built/shipped installer artifact contains the helper and launcher/compiler changes
   before calling the universal path release-ready.
