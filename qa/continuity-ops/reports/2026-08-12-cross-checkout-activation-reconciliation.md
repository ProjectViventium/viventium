# Cross-Checkout Activation Reconciliation QA Run - 2026-08-12

## Summary

- Result: PASS
- Build/source under test: isolated clean parent candidate
- Runtime/artifact under test: installed local-prod helper and detached launcher
- Environment: local macOS installation
- Tester: Codex plus review-only Claude second opinion
- Related change: classify the explicit nonblocking search-parity warning as nonterminal

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `CONT-017` | PASS | focused classifier regression, helper log, supported activation receipt | Real terminal failures remain terminal. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: cross-checkout activation and rollback safety
- Requirement: stable dev runtime preserves a valid successor when only optional search parity is degraded
- Use case: activate a reviewed clean checkout while local conversation search still needs repair
- QA case: `CONT-017`
- Expected result: warning stays visible; required surfaces start; predecessor is not restored
- Actual evidence: classifier GREEN, warning retained in the helper log, transactional activation PASS
- Remaining gap or fix: none for this case

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Code owning path | Detached-start failure classifier and launcher warning producer reviewed. |
| Docs and nested docs/repos | Stable runtime requirement and continuity case updated. |
| Scripts or harnesses | Focused release classifier test plus supported dev-runtime activation. |
| Local/external prerequisite state | Required local services and helper were healthy after activation. |
| Logs, DB/state/persistence | Helper log retained the warning; activation ownership persisted. |
| Generated/shipped artifact | Candidate compiler output and shipped helper were validated. |
| Real user path | Public CLI activation and status-bar helper restart completed. |
| Not run / blocked | Browser login and audible voice were outside this classifier case. |

Supporting evidence cannot replace required user-path evidence; the applicable CLI/helper path was run.

## User-Grade Evidence

- Surface exercised: installed Viventium CLI and macOS status-bar helper
- Real user path: ran supported transactional activation, then inspected live status and process ownership
- Visible outcome: activation completed instead of rolling back a healthy candidate
- Expanded/detail state: required services, selected pins, helper checkout, and live owner matched
- Persistence/reload result: the helper relaunched and retained the isolated checkout binding
- Local/external prerequisite state: local search parity remained visibly degraded but nonblocking
- Backend/log/DB confirmation: helper log retained the exact warning and showed successful startup
- Final model/runtime wording check: operator-facing degraded wording remained truthful and visible
- Substitution check: logs and tests support the completed real CLI/helper path; they do not replace it

## Automated Evidence

```bash
uv run --with pytest --with-requirements scripts/viventium/requirements.txt python -m pytest tests/release/test_cli_upgrade.py -q
bash -n bin/viventium
```

## Findings

- Defects: generic failure matching previously contradicted the launcher's nonblocking contract.
- Regressions: none after the exact exclusion and supported activation.
- Flakes: none observed.
- Environment issues: local search parity remains separately repairable.
- Residual risks: exact-string producer/filter coupling requires the focused regression.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
