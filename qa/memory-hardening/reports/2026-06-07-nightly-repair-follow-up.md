<!-- qa-evidence-exempt: legacy sanitized RCA/QA note retained for historical context; current acceptance must use cases plus a fresh v2 report. -->

# 2026-06-07 Nightly Routines Repair Follow-Up

## Verdict

Overall: **REPAIRED for the known built-in nightly blockers** after the morning partial audit.

This follow-up fixed the causes that would have made the next automation keep reporting partial:
early audit timing, strict Workbench misfire behavior, RAG sidecar host-port loss, stale
memory-hardening LaunchAgent paths, and PID-reused CLI locks.

Browser recall/source-card QA is still a separate RAG user-path proof, but the local RAG sidecar
itself is healthy again. Separate user-level provider/account reconnect rows are not built-in
nightly failures unless they block the built-in routine under review.

Important confidence limit: the Jun 7 live Workbench run proves the normal due chain, not a live
late-catch-up chain. The Jun 6 miss pattern is covered by a focused regression that reproduces the
late timing and verifies bounded catch-up; a deliberately delayed live catch-up proof remains a
future QA hardening gate.

## Root Causes

1. **Audit fired before the real due window.** The Codex Desktop RRULE is interpreted as UTC in this
   environment. The earlier 07:15 RRULE fired at 07:15Z / 03:15 America/Toronto, before the
   Workbench schedule's 10:00Z due time.
2. **Workbench Jun 6 miss was strict misfire behavior.** The built-in Workbench task had no bounded
   catch-up policy, so a late Scheduler tick marked the due run `misfire_grace_exceeded` and created
   no child run, GlassHive run, callback, or Workbench completed row.
3. **RAG was enabled but not actually listening.** Generated config expected `localhost:8110`, but
   the live RAG API container had no host-port binding. During repair, Docker also had a transient
   metadata/content-store failure and needed a bounded restart.
4. **Memory hardening LaunchAgent drifted to stale temp paths.** The loaded LaunchAgent pointed at a
   prior temporary install/App Support tree, so launchd evidence could not be trusted for the real
   checkout.
5. **The global CLI lock trusted only PID existence.** A stale lock PID had been reused by an
   unrelated macOS process, which made read-only wrappers report a false concurrent operation.

## Fixes

- Automation timing context:
  - Private automation RRULE remains set to 11:15Z so the audit runs after the current 10:00Z
    Workbench cadence during EDT.
  - Automation memory now says to judge by runtime/DB/LaunchAgent due windows, not by a single
    assumed local time.
- Workbench/Scheduler:
  - Built-in nightly task metadata now includes `misfire_policy: catch_up` with a 12-hour maximum
    lateness.
  - Existing built-in tasks are reconciled on Workbench startup.
  - Live built-in task metadata was reconciled in the local runtime.
- RAG:
  - Launcher detects when the RAG API container is missing the generated host-port binding and
    recreates the API container through the compose graph.
  - Live RAG compose graph was brought back up without deleting vector data.
- Memory hardening:
  - LaunchAgent was reinstalled through the supported `memory-harden install-schedule` path.
- CLI/status:
  - CLI operation locks now store a process-command fingerprint and creation timestamp.
  - CLI/status treat mismatched live process command as a reused/stale PID.
  - If command inspection is unavailable, lock handling is conservative rather than deleting a
    possibly live operation.

## Live Evidence

- Workbench/Scheduler:
  - Built-in task active, executor `glasshive_host`, next due `2026-06-08T10:00:00Z`.
  - Latest Jun 7 due run started near `2026-06-07T10:00:31Z`, completed near
    `2026-06-07T10:04:32Z`, and recorded success/sent delivery with a GlassHive run id.
  - Workbench browser detail showed the built-in schedule enabled, next Jun 8 6:00 AM local, and
    Jun 7 completed in Recent Runs.
- RAG:
  - `http://127.0.0.1:8110/health` returned `{"status":"UP"}`.
  - RAG API and vector DB containers were both up with expected loopback host ports.
- Memory hardening:
  - Latest hardener status remains successful: OpenAI/GPT-5.5, one selected user, no fallback.
  - Transcript index summary remained fully processed at the state level.
  - LaunchAgent now uses the stable generated runtime path rather than a stale temp install path.
- Continuity:
  - Continuity capture completed.
  - Memory dedupe dry-run reported zero duplicate groups, zero duplicate docs, and zero deletes.

Private prompt text, memory values, transcript text, account identifiers, raw callback payloads,
browser snapshots, secrets, and local private paths were not written to this report.

## Checks

- `uv run --with pytest --with pyyaml --with pydantic --with croniter --with fastapi --with httpx --with fastmcp python -m pytest tests/release/test_cli_upgrade.py tests/release/test_install_summary.py tests/release/test_prompt_workbench.py tests/release/test_scheduled_glasshive_prompts.py tests/release/test_rag_api_override_contract.py -q -ra`
  - **PASS:** 194 passed, 1 warning.
- `uv run --with pytest --with pyyaml --with pydantic --with croniter --with fastmcp --with fastapi --with httpx python -m pytest tests/release/test_scheduled_glasshive_prompts.py::test_builtin_workbench_nightly_misfire_policy_catches_up_late_run tests/release/test_rag_api_override_contract.py::test_launcher_recreates_rag_sidecar_when_host_port_binding_is_missing -q`
  - **PASS:** 2 passed.
- `node qa/meeting-transcript-memory/evals/run-evals.cjs`
  - **PASS:** 12 passed, 0 failed.
- `bin/viventium memory-dedupe --dry-run --json`
  - **PASS:** dry-run counts only; zero duplicate groups/docs/deletes.
- `bin/viventium continuity-audit`
  - **PASS:** metadata-only continuity capture completed.
- Playwright CLI Workbench inspection:
  - **PASS:** visible built-in schedule enabled, Jun 7 completed row visible, next Jun 8 due visible.
  - Private local snapshots were deleted after inspection.

## Remaining Gates

- A live late-catch-up proof for the built-in Workbench task is still outstanding. The escaped Jun 6
  timing is regression-covered, and the Jun 7 normal due run completed, but no production run has
  yet been deliberately observed outside grace and inside the 12-hour catch-up window.
- The next scheduled memory-hardening LaunchAgent run is future evidence, not a current failure.
- Browser conversation-recall/source grounding still needs a separate safe user-path QA run before
  full RAG user-flow signoff.
- Unrelated user-level provider/account reconnect rows remain account-action follow-up; they should
  not downgrade the built-in nightly workflow unless they block the built-in chain.

## ClaudeViv Review

ClaudeViv review-only completed successfully and classified the central fix as aligned with the
documented principles:

- Confirmed the Jun 6 Workbench miss was strict recurring-task misfire behavior and that the repair
  uses structured metadata, not prompt/title/user matching.
- Confirmed the RAG self-heal is scoped to `rag_api` recreation and does not delete vector data.
- Confirmed the CLI lock fingerprint fix is real and safer than blind lock deletion.
- Confirmed public QA artifacts keep the problem statement visible: RAG browser recall remains a
  separate partial user-path gate.

ClaudeViv also flagged these residual risks:

- The live late-catch-up path is not yet observed end-to-end; Jun 7 was an in-grace normal run.
- The private automation RRULE timing is environment-specific; the durable guard is the due-window
  table and NOT-DUE classification.
- The broader working tree contains many unrelated changes, so any commit/release should keep this
  nightly repair scoped and avoid claiming unrelated diffs as part of the fix.
