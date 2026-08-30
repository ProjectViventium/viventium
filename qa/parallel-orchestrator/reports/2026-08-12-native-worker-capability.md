# Parallel Work Native-Worker Capability QA Run - 2026-08-12

## Summary

- Result: PARTIAL.
- Build/source under test: the Parallel Work native-event projection in the active source checkout.
- Runtime/artifact under test: installed Codex CLI `0.147.0-alpha.6.5` and Claude Code `2.1.220`.
- Environment: isolated local GlassHive CLI workspaces with synthetic public-safe tasks.
- Tester: Codex implementation and independent integration-review agents.
- Related change: capability-gated native session, child, team-message, settling, and Stop projection.

Claude emitted a real isolated child lifecycle and a background-child activity event. Codex reported
multi-agent support but did not emit an observable child start/activity event in two real runs, so
Codex child projection correctly remains disabled. Restart/recursive-Stop and visible surface proof
remain incomplete; this run does not release the feature.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `PWK-009` | PARTIAL | Two installed Codex CLI runs plus native-event tests | Root session observed; no real child lifecycle, so capability stays false. |
| `PWK-010` | PARTIAL | Installed Claude CLI child/background runs plus native-event tests | Real child lifecycle passed; restart, recursive Stop, and visible roster remain. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `PWK-UC-006` | Ask a mission root to create native child work and observe its lifecycle. | GlassHive CLI with installed Codex and Claude harnesses | PARTIAL | Claude stream showed child start and completion; Codex returned the correct root result without a child event. | Sanitized normalized event types and aggregate test counts below. | Restart/recursive Stop and Telegram/Web topology were not run. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Parallel Work native provider teams.
- Requirement: native children remain internal to a durable root and project only proven lifecycle truth.
- Use case: Main inspects and controls a root using native children without seeing unrelated sessions.
- QA case: `PWK-009`, `PWK-010`, and `PWK-UC-006`.
- Expected result: real child events enable a bounded capability; missing evidence leaves it false.
- Actual evidence: Claude emitted `init`, `task_started`, completed `task_notification`, terminal
  success, and `background_tasks_changed`; Codex emitted a root session and no child-start event.
- Remaining gap or fix: real restart/recursive Stop, visible roster/detail, and a future Codex build
  that proves child lifecycle.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which contract is proven? | Native teams section in the Parallel Work requirement; `PWK-009/010`. |
| Code owning path | Which path owns behavior? | GlassHive native-team normalizer, run/event store, runtime stream observer, and account projection. |
| Docs and nested docs/repos | What defines expected behavior? | Parallel Work and GlassHive workstation/runtime requirements. |
| Scripts or harnesses | What exercised it? | Installed CLI probes and native-team/lease/runtime tests listed below. |
| Local/external prerequisite state | Were provider CLIs available? | Both installed CLIs executed real synthetic tasks; no external customer data was used. |
| Logs | What confirms the result? | Sanitized provider event names only; raw streams and IDs were intentionally not retained. |
| DB/state/persistence | What confirms projection? | Tests verified native session/capability/child-summary persistence and bounded settling. |
| Generated/shipped artifact | What artifact was tested? | Installed CLI versions stated in Summary; installed Viventium stack was not yet promoted. |
| Real user path | What real surface was used? | GlassHive CLI/provider execution, not a mocked provider stream. |
| Visual/UX comparison | Did visible product UI match? | Not run; Telegram/Web roster evidence remains required. |
| Not run / blocked | What remains? | Restart/recursive Stop, visible roster/detail, installed Viventium artifact, and Codex child event. |

## User-Grade Evidence

- Surface exercised: GlassHive CLI with installed Codex and Claude provider harnesses.
- Real user path: submit a synthetic child-delegation objective to each installed CLI under an
  isolated worker configuration and inspect the normalized lifecycle result.
- Visible outcome: Claude completed real child work; Codex completed the root task without claiming
  an unobserved child.
- Expanded/detail state: normalized session/child capability state was inspected; Web/Telegram
  expanded detail was not run, so the overall result is PARTIAL.
- Persistence/reload result: native session/capability persistence passed automated checks; a live
  service restart was not run.
- Local/external prerequisite state: both installed CLIs were executable and authenticated for the
  synthetic run.
- Evidence retrieval classification, if applicable: not applicable; this was provider lifecycle QA.
- Fallback path, if applicable: Codex truthfully retained root-only capability instead of inventing
  child visibility.
- Backend/log/DB confirmation: normalized event types and aggregate test counts matched the expected
  capability gates; raw IDs, prompts, and streams were not retained.
- Final model/runtime wording check: no user-facing completion wording was exercised in this
  provider-only run.
- Substitution check: CLI, event, DB, and unit evidence support the finding but do not replace the
  outstanding Telegram/Web detail, restart, and recursive-Stop user paths.

## Automated Evidence

The public-safe command shapes used installed CLIs with synthetic task text and run-scoped access
provided only through the local process environment. Exact prompts, IDs, paths, and credentials are
intentionally omitted.

```sh
codex --version
codex features list
codex exec --json --skip-git-repo-check -c features.multi_agent=true synthetic-child-task

CLAUDE_CONFIG_DIR=/workspace/isolated-run-config \
  claude -p --verbose --output-format stream-json \
  --permission-mode bypassPermissions --setting-sources '' synthetic-child-task

python -m pytest runtime_phase1/tests/test_native_team.py \
  runtime_phase1/tests/test_parallel_runtime_safety.py \
  runtime_phase1/tests/test_host_run_leases.py -q
```

- Native-team focused tests: 16 passed.
- Native-team plus parallel-runtime safety and lease tests: 28 passed.
- Account API plus run-action tests: 53 passed.
- Profile-runtime tests: 213 passed.

## Findings

- Defects: no verified projection defect remained in this slice.
- Regressions: none in the focused suites.
- Flakes: none observed.
- Environment issues: Codex did not emit a child event despite reporting multi-agent support.
- Residual risks: restart/recursive Stop and visible cross-surface topology remain unproven; Codex
  child projection must remain false until a real event is observed.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, versions, event names, and conclusions only.
