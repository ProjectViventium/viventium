# Helper Desired-State Supervision QA — 2026-07-24

<!-- qa-evidence-exempt: Source and prebuilt-helper note; installed helper lifecycle evidence belongs in the universal-upgrade run report. -->

## Scope

This pass covers the escaped helper lifecycle failure where local prod could die after the
45-second login auto-start window and remain down indefinitely even though the helper kept polling.
It does not contain owner-machine logs, configuration values, or personal runtime data.

## Root Cause

The helper stored a process-lifetime `didAttemptLaunchAutostart` latch. The first healthy result or
launch attempt set the latch permanently, and the 45-second window later expired. Subsequent
four-second polls refreshed status but could never submit another start.

## Implemented Contract

- Missing legacy supervision state defaults to desired `running`.
- Helper `Stop` and `Quit` persist desired `stopped` before shutdown; helper `Start` persists
  desired `running`.
- Unexpected stopped state submits the existing detached public CLI launch.
- Configured managed-sidecar health, including Scheduling Cortex, contributes to the same helper
  health snapshot and bounded repair loop instead of being display-only.
- Failed or short-lived recoveries use exponential backoff from 15 seconds to a 15-minute cap.
- Attempt history clears only after five stable healthy minutes.
- The supervision record is nested in the existing helper config so the installer’s merge-preserve
  behavior retains it without adding another settings source.
- Helper refresh records a durable owner-only install receipt before mutating config, scheduling,
  launcher scripts, the app bundle, or registration state. A subsequent invocation completes an
  activated transaction or safely retries the staged install.

## Evidence Run

| Evidence | Result |
| --- | --- |
| Regression first failed because no supervision policy or reconciler existed | PASS (RED reproduced) |
| Compiled Swift policy harness: stop intent, start resume, persistence round-trip, exponential cap, short-lived crash retention, stable reset | PASS |
| Configured-sidecar/Scheduling health enters bounded repair after core readiness | PASS |
| Five helper-install hard-kill windows converge without abandoned artifacts on retry | PASS |
| Helper package debug build | PASS |
| Existing helper lifecycle source contract updated for desired-state supervision | PASS |
| Shipped universal prebuilt/source/binary hash alignment (`arm64` + `x86_64`) | PASS |
| Complete helper supervision/install focused set | PASS (43 tests) |
| Installed helper late-death recovery after the former launch window | NOT RUN |
| Installed Scheduling Cortex late-death recovery from the status-bar helper | NOT RUN |
| Headed Stop -> helper relaunch -> remains stopped -> Start | NOT RUN |

## Remaining Acceptance

Refresh the installed helper only after the complete candidate is accepted. Then capture
timestamped helper/start logs and process/port health for a synthetic late-death recovery, two
short-lived failure cycles, explicit Stop across helper relaunch, and manual Start recovery. The
local runtime and App Support state must not be modified for this source-only pass.
