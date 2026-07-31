# Telegram cross-architecture dependency assembly QA run - 2026-07-31

## Summary

- Result: **PASS-ARM64 / PENDING-HOSTED-X86_64**
- Build/source under test: reviewed parent PR candidate
- Runtime/artifact under test: sealed Telegram dependency component
- Environment: real local Apple Silicon assembly; synthetic Intel selection; hosted Intel pending
- Tester: Codex
- Related change: architecture-aware `pywhispercpp` build and recoverable sealed-stage cleanup

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `TR-014` | PARTIAL | fresh arm64 assembly plus 2,100 release tests | hosted x86_64 gate pending |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `TR-UC-001` | Install/start Telegram runtime with voice dependencies | local runtime component CLI | PARTIAL | arm64 candidate assembled and native import passed | sealed selection and dependency manifest verified | hosted Intel install; bot delivery |
| `TR-UC-002` | Recover after failed dependency staging | synthetic component failure harness | PASS | original failure is not masked by cleanup | sealed-stage removal and symlink refusal assertions pass | none for automated contract |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: sealed Telegram runtime
- Requirement: architecture-compatible immutable dependency assembly
- Use case: install or upgrade on Apple Silicon and Intel without first-message package mutation
- QA case: `TR-014`
- Expected result: native module imports before publication; failed stages cleanly recover
- Actual evidence: real arm64 assembly/import and full release suite pass
- Remaining gap or fix: final GitHub-hosted x86_64 easy-install execution and installed bot delivery

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement and case are proven? | requirement 39, `TR-014` |
| Code owning path | Which code path owns behavior? | Telegram runtime component dependency sync |
| Docs and nested docs/repos | Which truth defines it? | requirement 39 and Telegram runtime cases |
| Scripts or harnesses | What exercised it? | runtime-component and complete release pytest suites |
| Local/external prerequisite state | What dependency state was proven? | arm64 Python/native toolchain healthy; hosted Intel pending |
| Logs | What logs confirm it? | sanitized result counts and import outcome |
| DB/state/persistence | What state confirms it? | immutable selection and dependency manifest |
| Generated/shipped artifact | What artifact was inspected? | sealed dependency environment and component selection |
| Real user path | What user path ran? | local component assembly CLI; Telegram Desktop delivery pending |
| Visual/UX comparison | Does UX match? | not applicable to assembly; delivered bot UX pending |
| Not run / blocked | What remains? | hosted x86_64 easy install and installed Telegram delivery |

## User-Grade Evidence

- Surface exercised: local Telegram runtime component CLI
- Real user path: fresh Apple Silicon dependency assembly and execution probe
- Visible outcome: assembly succeeds and native transcription import exits successfully
- Expanded/detail state: selection modes, executable Python, dependency presence, and unsafe path refusal
- Persistence/reload result: sealed selection reopens and verifies; installed bot restart pending
- Local/external prerequisite state: Apple Silicon toolchain healthy; hosted Intel result pending
- Evidence retrieval classification, if applicable: not applicable
- Fallback path, if applicable: not applicable
- Backend/log/DB confirmation: selection and manifest checks pass; no DB surface applies to assembly
- Final model/runtime wording check: Telegram response delivery not yet rerun
- Substitution check: assembly/tests do not replace hosted Intel or delivered Telegram evidence; the
  result remains PENDING-HOSTED-X86_64.

## Automated Evidence

```bash
python -m pytest tests/release/test_telegram_runtime_component.py -q
python -m pytest tests/release -q
```

Results:

- Runtime component regression: 18/18 PASS.
- Focused parent continuity/CLI/config/Telegram: 226/226 PASS.
- Complete parent release: 2,100 PASS, 8 skipped, 0 failed.
- Fresh real Apple Silicon assembly, seal, selection, execution, and native import: PASS.
- Unsafe temporary symlink parent: correctly refused.

## Findings

- Defects: Intel source build entered unsupported wheel repair; sealed cleanup could mask root failure.
- Regressions: none in local automated/arm64 evidence.
- Flakes: none.
- Environment issues: final hosted x86_64 job has not run on the parent fix yet.
- Residual risks: hosted Intel and post-change installed Telegram text/voice/video delivery.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
