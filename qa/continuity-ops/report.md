# Continuity Ops QA Report

## Date

- 2026-04-14

## Build Under Test

- Parent repo working tree on 2026-04-14
- Nested LibreChat working tree on 2026-04-14
- Public-safe local verification of continuity manifests, restore-age gating, helper snapshot UX,
  and recall stale-restore runtime behavior

## Verification Gate Claimed

- `Local development implementation gate`
- Meaning:
  - the continuity-aware snapshot / restore / upgrade design is implemented
  - owned automated suites pass
  - one real metadata-only snapshot path was exercised outside the unit-test harness
- Not yet claimed:
  - `full public release gate`
  - `cross-machine restore drill gate`

## Steps Executed

1. Reviewed the owning docs:
   - `docs/requirements_and_learnings/01_Key_Principles.md`
   - `docs/requirements_and_learnings/20_Memory_System.md`
   - `docs/requirements_and_learnings/32_Conversation_Recall_RAG.md`
   - `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
   - `docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md`
   - `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`
2. Ran a review-only Claude design pass before implementation and a focused Claude pass on the
   stale-restore recall gate.
3. Implemented:
   - shared private companion discovery helpers
   - continuity manifest capture/compare tooling
   - continuity-aware snapshot wrapper
   - restore-age gating plus pre-apply Telegram safety backup
   - upgrade-time pre/post continuity audits with restart blocking on `error`
   - explicit recall rebuild marker export and runtime stale-restore gating
   - helper `Create Backup Snapshot` action
4. Rebuilt the matching prebuilt helper binary after the helper source change.
5. Exercised the public snapshot wrapper with `VIVENTIUM_PRIVATE_REPO_DIR=/nonexistent` so the
   private helper was absent by design.
6. Verified that the wrapper still wrote:
   - `LATEST_PATH`
   - `continuity-manifest.json`
   - only sanitized metadata
7. Ran a direct continuity-audit capture against the live App Support root and confirmed it
   degraded honestly to `warning` because `MONGO_URI` was unavailable to the audit on this machine.
8. Verified the already-running installed helper was stale by checking the live app bundle strings
   and confirming the new backup-menu strings were absent before refresh.
9. Ran `bin/viventium install-helper`, confirmed the refreshed installed helper binary now carried
   the backup-menu strings, enumerated the live status menu via System Events, and triggered
   `Create Backup Snapshot` once from the actual menu.
   - live menu proof after refresh:
     - `Open`
     - `Stop`
     - `Running`
     - `Create Backup Snapshot`
     - `Start at Login`
     - `Show in Status Bar`

## Automated Checks Executed

### Parent repo

- `python3 -m py_compile scripts/viventium/continuity_audit.py`
  - Result: passed
- `bash -n bin/viventium scripts/viventium/common.sh scripts/viventium/restore.sh viventium_v0_4/viventium-local-state-snapshot.sh viventium_v0_4/viventium-librechat-start.sh viventium_v0_4/viventium-skyvern-start.sh`
  - Result: passed
- `uv run --with pytest pytest tests/release/test_continuity_audit.py tests/release/test_private_repo_resolution_contract.py tests/release/test_macos_helper_install.py tests/release/test_cli_upgrade.py -q`
  - Result: `55 passed`

### Nested LibreChat repo

- `cd viventium_v0_4/LibreChat/packages/api && npx jest --runInBand src/agents/__tests__/conversationRecallAvailability.test.ts src/agents/__tests__/initialize.test.ts`
  - Result: `12 passed`
- `cd viventium_v0_4/LibreChat && npm run build:api`
  - Result: passed

## Findings

### 1. The public snapshot path now has a real metadata-only fallback

- With the private companion helper intentionally absent, the public wrapper still completed.
- It wrote:
  - `LATEST_PATH`
  - `continuity-manifest.json`
- The manifest contained sanitized `~/...` path labels, repo heads, runtime metadata, surface
  timestamps/counts, and warnings.
- It did not contain raw message text, raw prompts, raw DB URIs, or absolute home-directory paths.

### 2. Continuity severity is now explicit instead of implicit

- The continuity audit reports `ok`, `warning`, or `error`.
- The manual-check capture on this machine returned `warning`, not a false green, because Mongo
  continuity introspection could not run without `MONGO_URI`.
- That is the intended contract: unknown surfaces must degrade honestly.

### 3. Restore and upgrade now fail closed on continuity rollback risk

- Restore compares snapshot and live manifests and refuses an older snapshot by default.
- Upgrade records pre/post continuity audits and blocks `--restart` when the post-upgrade audit
  reports `error`.
- This closes the earlier class of issues where runtime could come back up on stale continuity
  state and look superficially healthy.

### 4. Restore-aware recall gating is explicit

- The runtime now exposes an explicit stale-restore reason while the recall rebuild marker exists.
- Marker removal is an intentional operator step, not an automatic side effect of startup.
- That keeps vector-backed recall from silently presenting restored or rolled-back state as fresh.

### 5. Manual backups are now a first-class supported UX

- The macOS helper now shows `Create Backup Snapshot`.
- The helper runs the same supported CLI snapshot flow and writes to `helper-snapshot.log`.
- The default product path is manual on-demand capture rather than hidden mandatory daily full
  backups.

### 6. Helper-menu drift is now a QA-proven install surface, not an assumption

- The visible menu item was missing only because the installed helper bundle was stale.
- Refreshing through the supported `bin/viventium install-helper` path updated the live app bundle.
- After refresh, the live status menu showed `Create Backup Snapshot`, and the action wrote the
  expected request/completion evidence to the helper logs.

## Remaining Gaps

- This pass did not run a full cross-machine restore drill on a fresh second machine.
- The continuity audit can only inspect surfaces for which the current runtime exposes enough local
  metadata; missing tools or env now produce warnings rather than fake success.
- Because the helper source changed, release readiness still requires shipping the rebuilt matching
  prebuilt helper binary together with the source hash update.
