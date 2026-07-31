<!-- qa-evidence-exempt: Isolated LaunchAgent transaction implementation record; headed macOS acceptance remains tracked in the owning cases catalog. -->
# LaunchAgent Transaction Rollback QA — 2026-07-24

## Outcome

`PASS-AUTOMATED` for exact memory-hardening LaunchAgent rollback and upgrade ordering.

The reconciler now restores the exact prior plist bytes/mode, dry-run marker bytes/mode, and
launchd loaded/unloaded state when install, reinstall, uninstall, verification, or receipt work
fails. Upgrade no longer mutates this derived host state before its strict comparison and source
commit.

## User Risk Covered

- A failed desired bootstrap cannot strand a previously loaded user schedule in the unloaded state.
- A failed fresh install cannot leave an unverified new plist behind.
- A failed uninstall after file removal cannot erase the existing plist or dry-run-first marker.
- A later failed upgrade acceptance gate cannot inherit an earlier LaunchAgent mutation.
- Symlinked, special, or non-current-user-owned reconciliation inputs fail before mutation.

## Evidence Run

- `tests/release/test_memory_hardening_contract.py`: `67 passed`
- Focused memory schedule matrix: `14 passed`
- Focused upgrade/bridge ordering: `2 passed`
- Shell syntax check and the final integrated upgrade suites are tracked by the parent universal
  upgrade acceptance run.

All lifecycle fault injection used temporary synthetic files and a fake `launchctl` state machine.
No live LaunchAgent, App Support config, database, conversations, schedules, prompts, or account
state was mutated.

## Expected And Forbidden Results

Expected:

- failed lifecycle receipts include `rollback_status: restored` when receipt storage is available;
- exact prior file bytes and permission bits return;
- loaded/unloaded state returns;
- schedule sync follows commit and protected runtime/uploads finalization;
- the retry path is `bin/viventium compile-config`.

Forbidden:

- parsed-plist-only reconstruction;
- forced mode `0644` on a restored prior file;
- precommit `bootout`, bootstrap, replacement, or uninstall;
- success wording when rollback itself cannot be proven;
- public evidence containing plist commands, account values, local paths, or private runtime data.

## Not Run

A real installed LaunchAgent failure was intentionally not induced because doing so would mutate
the operator's live schedule. The synthetic state-machine coverage is the appropriate safety proof
for destructive failure paths; a later non-failing live reconciliation may verify normal installed
artifact alignment without fault injection.
