# Local-Prod GlassHive Cold-Start Readiness QA Run - 2026-08-12

## Summary

- Result: PASS
- Build/source under test: isolated clean parent candidate
- Runtime/artifact under test: installed local-prod GlassHive runtime, MCP, and UI
- Environment: local macOS installation with persisted GlassHive state
- Tester: Codex plus independent runtime-drift agent and review-only Claude second opinion
- Related change: bounded three-surface readiness polling replaces a fixed three-second gate

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GCP-035` | PASS | isolated timing probes, focused regression, two supported activations | Existing state reached readiness after the old deadline. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: GlassHive persisted-state cold startup
- Requirement: a live but slow candidate is not destroyed at an arbitrary three-second boundary
- Use case: activate local prod with existing GlassHive state
- QA case: `GCP-035`
- Expected result: three surfaces become ready inside a bounded window or candidate fails closed
- Actual evidence: persisted-state probe ready at 4.634 seconds; supported activation completed
- Remaining gap or fix: voice soak and other release surfaces remain separate gates

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Code owning path | GlassHive launcher, readiness probes, PID checks, and candidate teardown reviewed. |
| Docs and nested docs/repos | Stable runtime requirement and GlassHive case updated. |
| Scripts or harnesses | Isolated cold-start probe and focused shell-behavior test ran. |
| Local/external prerequisite state | Persisted local DB state was available; candidate ports were isolated. |
| Logs, DB/state/persistence | Process liveness and runtime/MCP/UI readiness timings agreed. |
| Generated/shipped artifact | Supported activation validated compiler output and helper artifact. |
| Real user path | Public dev-runtime activation completed and status showed GlassHive running. |
| Not run / blocked | Audible voice, connected-account OAuth, and long soak are separate cases. |

Supporting evidence cannot replace required user-path evidence; the applicable CLI/helper/GlassHive path was run.

## User-Grade Evidence

- Surface exercised: installed Viventium CLI, helper, GlassHive runtime, MCP, and UI
- Real user path: activated a reviewed checkout through the supported transactional command
- Visible outcome: activation completed and GlassHive reported running instead of rolling back at three seconds
- Expanded/detail state: runtime, MCP, UI, helper, selected pins, and process roots matched the candidate
- Persistence/reload result: restart reused existing state and returned all three surfaces healthy
- Local/external prerequisite state: persisted state was present; no stale port or dependency blocker matched
- Backend/log/DB confirmation: all candidate processes stayed alive past three seconds and reached readiness at 4.634 seconds
- Final model/runtime wording check: status reported actual readiness rather than optimistic startup
- Substitution check: isolated timing and tests support the real activation; they do not replace it

## Automated Evidence

```bash
uv run --with pytest --with-requirements scripts/viventium/requirements.txt python -m pytest tests/release/test_config_compiler.py -q
bash -n viventium_v0_4/viventium-librechat-start.sh
```

## Findings

- Defects: one fixed sleep destroyed a valid cold candidate.
- Regressions: none after bounded polling and transactional activation.
- Flakes: none in repeated isolated cold starts.
- Environment issues: initial macOS Documents permission paused later Life bootstrap, not GlassHive readiness.
- Residual risks: the deadline is bounded but user-tunable state outside the observed size needs its own capacity QA.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
