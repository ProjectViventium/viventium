<!-- qa-evidence-exempt: Isolated transaction implementation record; installed user-path acceptance remains tracked in the owning cases catalog. -->
# Quiesced Successor Acceptance And Local Promotion QA

Date: 2026-07-24

## Outcome

The exact supported predecessor and the current upgrade controller now share one fail-closed
quiesced runtime primitive. Candidate acceptance keeps the declared autonomous-writer inventory
disabled through strict continuity comparison and outer commit. Running and stopped intent are
handled separately; same-source refreshes cannot skip runtime acceptance.

Local checkout promotion now validates isolated generated output before changing the active
checkout or live runtime. Its owner-private journal declares staging/backup paths before live
renames and restores the prior generated runtime, active checkout, complete helper config, and
running/stopped state after pre-commit failure or interruption. Once the healthy core commits,
installed-helper refresh is forward-only and receipt-backed because the core journal does not own
the app bundle, helper scripts, scheduling component, login item, or LaunchAgent.

Public `start`/`launch` now pass through interrupted-upgrade recovery before runtime preparation,
and direct use of the full-stack launcher routes back through the locked public CLI. The local
promotion transaction allocates its journal and candidate directory through one fail-closed
`begin-new` operation, revalidates that the live runtime is the canonical App Support runtime before
rename or removal, and persists helper `stopped` intent before candidate validation so late helper
supervision cannot relaunch the predecessor during the validation window.

## Evidence Run

- `tests/release/test_first_upgrade_bridge.py`: 21 passed.
- `tests/release/test_dev_runtime_activation.py`: 11 passed.
- Combined stable-dev/quiesced focused set: 74 passed, 1 unrelated Telegram assertion deselected.
- Broad public-CLI upgrade/dev-runtime selection: 82 passed.
- Current stable-dev plus activation set: 61 passed, including executable direct-launcher
  `start`/`stop` routing.
- Swift helper supervision plus helper install/source/prebuilt set: 43 passed.
- The executable pre-checkpoint interrupted-upgrade `start` recovery passed: the active transaction
  rolled back before the runtime launcher ran and returned the explicit recovery/retry exit.
- Combined helper/install/activation/stable-dev focused verification: 104 passed.
- QA operating-contract suite: 26 passed.
- Shell syntax passed for the public CLI and stack launcher.
- Python compilation passed for both transaction controllers.
- Node syntax passed for both LibreChat API startup entrypoints.
- The rebuilt universal helper independently verified as `arm64` + `x86_64`, with source digest
  `3a54d2e806c04fe4b04db30b5663e630d9f954ba229c0397ec398be57aaa6884` and binary digest
  `cd2154a6ae812c7922dd15203eac2849fb43779d23c721f4b96eb2849c4fcbf6`.

The exact-shell matrix covers running/stopped × healthy/corrupt helper, a forced old-shell restart,
post-commit full start, and running rollback. Activation crash tests cover process loss after
stopping the prior runtime but before publish, after the live-runtime backup, and after candidate
swap. A post-commit identity race proves cleanup cannot trigger a split binding/runtime rollback,
and the helper finalization receipt proves a committed core cannot be rolled back after wider helper
mutation. A real Swift file-write harness proves supervision preserves unknown top-level/nested
helper fields and `0600` mode; the rebuilt universal helper matches its source/binary digests.
Successful stopped-runtime promotion merges the pre-validation helper-supervision values back into
the live config while retaining unknown top-level/nested fields that appeared during activation, so
temporary quiescence does not become owner-setting drift.
Five hard-kill windows across helper config, scheduling component, launcher scripts, bundle
activation, and registration leave a durable receipt and converge on the next installer invocation
without abandoned transaction artifacts. Configured managed-sidecar health, including Scheduling
Cortex, now contributes to the helper health snapshot and receives the same bounded repair loop as
core runtime death instead of remaining indefinitely `Unavailable`.
Scheduler component failure immediately after prior-venv transfer restores exact predecessor bytes
and modes before cleaning its journal-owned paths. Failure injection also exposed and fixed a shared
preflight wrapper that had returned the
subsequent Python-refresh status instead of the prerequisite check status; preflight, bootstrap,
compiler, and doctor failures now prove exact stopped-checkpoint rollback.

## Truthful Remaining Boundary

This is `PARTIAL`, not a fully atomic universal-upgrade claim. Full database migration/index
reconciliation and all configured sidecar health gates run after source commit. A failure is
receipt-backed, protected state remains unchanged in the synthetic recovery proof, and the next
`start`/upgrade retries finalization, but source commit has already occurred.

Not run in this protected lane:

- installed personal runtime promotion or failure injection
- real Native/Docker first upgrade
- browser-visible conversation/agent/schedule/upload persistence
- audible/Telegram/channel user paths
- shipped/pinned/installed artifact parity

No personal App Support data, conversations, schedules, prompts, databases, or helper installation
were read or changed.
