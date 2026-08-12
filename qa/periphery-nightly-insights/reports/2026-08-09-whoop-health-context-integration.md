# WHOOP Health-Context Integration QA — 2026-08-09/10

## Summary

- Result: **PASS-ONGOING** for the requested connected local runtime.
- WHOOP OAuth is active with the six documented read scopes and offline refresh.
- The explicit all-history import completed: 15 cycles, 14 recovery records, 14 sleeps, 6
  workouts, one profile, and one body measurement (51 provider items).
- Exactly one loaded acquisition job runs at 06:00 local time with a three-day correction overlap.
- Exactly one Health Context definition runs at 06:15 `America/Toronto`, uses GlassHive Sol/xHigh,
  and keeps memory writes off.
- Activation completed a real scheduler-owned catch-up, produced a passed grounded artifact, and
  advanced the next run to the following day.
- Private raw provider bodies remain in the Viventium health archive. The optional Life projection
  is owner-only metadata, counts, status, and hashes only.

The next ordinary wall-clock occurrence had not elapsed when the report closed. This is not a
substitute for the scheduler path: the actual catch-up occurrence ran through Scheduling Cortex,
GlassHive, callback reconciliation, artifact validation, and persisted scheduling state.

## Scope And Results

| Case | Result | Actual evidence | Remaining gap |
| --- | --- | --- | --- |
| `PERI-010` | PASS-CONNECTED | OAuth, six-resource all-history import, exact reads, and real correction run completed | Live revoke intentionally not run because ongoing access is the requested end state |
| `PERI-012` | PASS-ISOLATED / PASS-LIVE | Component head, parent pin, installed manifest/hash, public CLI, archive-preserving install, and read-only MCP agree | Fresh external clone/install not run in this session |
| `PERI-013` | PASS-LIVE | Complete snapshot inspected 48 summaries, included 18 exact bodies, and reported zero failures/truncations | None |
| `PERI-014` | PASS-ACTIVE | One loaded 06:00 acquisition owner; one active 06:15 correlation owner; real catch-up completed; next run advanced | Next ordinary wall-clock occurrence not yet elapsed |
| `PERI-015` | PASS-COMPLETE | Life directory/file were `0700`/`0600`; projection was complete and metadata-only | None |
| `PERI-016` | PASS-LIVE | Fresh `P1D` sidecar passed with 4/4 sources resolved, zero ungrounded claims, zero actions, and zero memory proposals | None |
| `PERI-017` | PASS-CLASSIFICATION | Historical provider-limit failure remains specifically classified; later manual and scheduled runs completed | None |
| `PERI-018` | PASS | No-follow read/list parity, hard-link rejection, safe index replacement, explicit degraded/blocked state, and live owner-only modes | Orphan Markdown without a sidecar relies on the enclosing `0700` root until writer-owned creation modes are added |
| `PERI-UC-006` | PASS-ONGOING | Real OAuth, import, correction, schedule, browser, worker, artifact, Life, privacy, and persistence paths agree | Live disconnect not run |

## Full-View Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> gap`

- Feature: ongoing WHOOP acquisition and private health-context correlation.
- Requirement: exact owner-only archive; least-privilege authorization; bounded source-cited
  correlation; distinct recurrence owners; metadata-only Life projection; memory off; non-diagnostic
  interpretation; fail-closed private artifacts.
- User use case: connect WHOOP once, import official history, keep it corrected daily, and let
  Viventium correlate device evidence with relevant private context without duplicating raw health
  data into Life or memory.
- Expected result: provider failures remain honest; acquisition and analysis do not duplicate
  pulls; every accepted claim resolves to snapshot evidence; schedule state survives reload; private
  files cannot be reached through links or permissive worker umasks.
- Actual evidence: all requested live paths passed. Remaining non-blocking gaps are listed above.

## User-Grade Browser Evidence

- Opened the real Prompt Workbench Health Context definition through Playwright.
- Before activation, Workbench showed paused, 06:15, `America/Toronto`, GlassHive host execution,
  complete evidence, 48 summaries inspected, 18 bodies included, and Memory Off.
- Opening Periphery Artifacts exercised the live hardened ingestion path. The index was available
  with zero privacy blockers and the latest pre-activation artifact was passed.
- Enabled Health Context through the visible control. Once the full runtime was healthy, Scheduling
  Cortex claimed the missed occurrence, ran it as a scheduled run, and advanced the next due time.
- The scheduled run completed. The new `health_context` artifact was passed, fresh for `P1D`, and
  fully grounded (4/4 source references, zero ungrounded claims).
- Reloaded the page, reopened Health Context, and verified: enabled, next 06:15 occurrence,
  completed scheduled run, complete 48/18 snapshot, passed latest artifact, and Memory Off.
- Backend schedule state agreed: one active definition, daily 06:15 `America/Toronto`,
  `glasshive_host`, memory mode off, future next-run time.

## Provider And Archive Evidence

- The all-history run had an open minimum-time boundary, fixed capture end, and all six resource
  results complete.
- The six response pages belonging to that run all passed stored SHA-256 integrity verification.
- Parsed provider item counts were 15 cycles, 14 recovery, 14 sleep, 6 workout, 1 profile, and 1
  body measurement.
- The wider current archive inventory contained 48 complete response summaries, eight for each
  official resource, all with hashes.
- The latest daily correction run used a bounded start and fixed end and completed all six
  resources.
- The single acquisition LaunchAgent was configured and loaded for 06:00; its last exit code was
  zero.

## Privacy And Security Evidence

- The escaped worker-umask defect was reproduced before repair: a valid health-context Markdown/JSON
  pair was `0644` under `0755` directories.
- Listing and body reads now share descriptor-relative `O_NOFOLLOW` traversal and use content from
  the validated open descriptor.
- Symlinks and multiple-hard-link files are withheld; no outside target is read or chmodded.
- Index writes use an exclusive random no-follow temporary file, `0600` from creation, fsync, and a
  descriptor-relative rename.
- All discovered sidecars are hardened even when they exceed the 100-item index limit.
- Availability is `degraded` when safe artifacts remain and `blocked` only when none remain.
  Agent-facing reasons and remediation are allowlisted and path-free.
- Live acceptance after the scheduled run found 26 discovered sidecars and 26 paired Markdown files,
  all `0600`; the relevant private directories were `0700`; the index was a regular `0600` file;
  all were owned by the runtime user.
- An independent review-only security pass reported no remaining Critical privacy/integrity issue
  and explicitly approved live application. Its availability residuals were repaired before the
  live restart and covered by new tests.

## Automated Evidence

- Viventium-Health: 29 synthetic component tests plus two opt-in live public WHOOP contract checks
  passed in the implementation acceptance run.
- Parent health runtime/MCP/integration slice: 25 focused tests passed.
- Workbench Periphery/scheduling/privacy slice: 38/38 applicable focused tests passed after the
  final availability repair.
- The full Workbench file passed 166 tests. Two unrelated pre-existing assertions still fail: one
  uses a now-stale fixed memory-health date and one hardcodes an 11-agent roster while source truth
  currently contains 12. Neither touches WHOOP, Periphery permissions, or scheduling behavior.
- Scheduling Cortex agent contract: 10/10 passed after the degraded/blocked guidance repair.
- Python compilation and diff-whitespace checks passed for every changed implementation file.
- Independent review found no remaining Critical privacy/integrity finding.

## Not Run Or Intentionally Preserved

- Live WHOOP disconnect/revoke was not run because it would undo the requested ongoing connection.
  Disconnect remains covered synthetically.
- The next ordinary 06:15 wall-clock occurrence had not elapsed. The scheduler-owned catch-up run
  completed and persisted the next occurrence, so the real recurrence path was exercised.
- A fresh external clone/install was not repeated in this continuation; isolated install/runtime,
  component pin, installed manifest, and live artifact parity were already verified.
- WHOOP's app-only 0–3 Stress Monitor value remains outside the documented developer API and is not
  scraped. Owner-provided screenshots remain a separate manual evidence lane.

## Public-Safety Review

- [x] No secrets, OAuth values, tokens, cookies, passwords, or credential-bearing commands.
- [x] No private health bodies, observations, conversations, prompts, screenshots, or model output.
- [x] No account, record, run, callback, conversation, or message identifiers.
- [x] No local usernames, hostnames, machine names, or absolute owner paths.
- [x] Evidence is limited to public-safe counts, modes, statuses, and conclusions.
<!-- qa-evidence-exempt: Historical or specialized supporting artifact retained without retroactively inventing missing evidence; current release acceptance requires a fresh full-view report. -->
