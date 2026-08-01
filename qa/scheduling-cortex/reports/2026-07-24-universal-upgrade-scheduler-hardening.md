# Universal Upgrade Scheduler Hardening - 2026-07-24

<!-- qa-evidence-exempt: Source and isolated installed-component note; real scheduler delivery evidence belongs in the universal-upgrade run report. -->

## Status

- `SCHED-017` canonical choice migration: `PASS-AUTOMATED`
- `SCHED-017` protected-folder helper component install: `PASS-AUTOMATED`
- `SCHED-017` isolated installed-component dependency sync/import/MCP health: `PASS-AUTOMATED`
- Real user helper launch, restart persistence, and visible scheduled delivery: `NOT RUN`
- Overall: `PARTIAL`

This pass used only synthetic temporary homes/config/runtime state. It did not read or modify a
user's live App Support config, schedules DB, conversations, prompts, helper binding, or running
processes.

## Requirement And RCA

Legacy canonical config may predate `integrations.scheduling_cortex.enabled` even though generated
runtime had Scheduler enabled. Blindly defaulting that missing key off loses prior behavior; blindly
defaulting it on changes fresh installs and users who disabled Scheduler. Separately, helper launch
previously selected Scheduler code inside the source checkout, so `uv sync` could build a `.venv`
inside a macOS protected folder and trigger unavailable/TCC behavior.

The accepted boundary is:

- explicit canonical true or false wins
- a missing legacy key migrates to true only when predecessor generated runtime explicitly proves
  `START_SCHEDULING_MCP=true`
- schedules DB existence alone is never an enablement signal
- the migrated choice is persisted canonically because continuity restore regenerates runtime from
  canonical config
- helper install copies a code-only Scheduler component to App Support; helper launch always uses
  that component
- the per-runtime schedules DB remains separate App Support state and is untouched

## Automated Evidence

- Failure-first compiler test proved enabled predecessor state was discarded before the fix.
- Failure-first launcher/helper tests proved no installed Scheduler component path existed before
  the fix.
- Focused migration tests cover missing+enabled predecessor, explicit false override, retained DB
  without enablement, unrelated config preservation, file-mode preservation, and dry-run no-write.
- Synthetic protected-folder helper install covers source `.venv`/DB exclusion, installed package
  inventory, wrapper binding, and byte-for-byte preservation of an existing schedules DB.
- A second synthetic helper install ran `uv sync --frozen` in the App Support component, imported
  bundled Prompt Workbench support from that component, started the real Scheduling Cortex server,
  and verified `/health` returned the expected service/status plus the matching DB identity hash.
  Reinstall then preserved both the installed dependency environment and the generated schedules DB
  byte-for-byte while refreshing component source.
- Full config compiler suite: `151 passed`.
- Full helper installer suite: `32 passed`.
- Scheduling Cortex package suite: `113 passed`, `6 subtests passed`.
- Launcher and helper installer shell syntax: pass.
- Scheduling supervision contract: pass.

## Not Run

- The real installed helper was not replaced or relaunched.
- No live schedules DB was opened or queried.
- No browser/Telegram schedule was created, triggered, restarted, or visibly delivered.
- No exact shipped release archive or clean-machine upgrade was exercised.

Those user-grade steps remain mandatory before calling `SCHED-017` fully accepted or the universal
upgrade path release-ready.

## Public-Safety Review

The tests and this report use only synthetic paths, values, and state. No personal paths, account
identifiers, schedule content, prompts, conversations, tokens, raw DB records, or private logs are
included.
