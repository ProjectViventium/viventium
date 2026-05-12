# <Feature> QA Run - YYYY-MM-DD

## Summary

- Result:
- Build/source under test:
- Runtime/artifact under test:
- Environment:
- Tester:
- Related change:

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `<FEATURE>-001` | `<pass/fail/blocked>` | `<sanitized link/count/hash>` | `<notes>` |

## User-Grade Evidence

- Surface exercised:
- Real user path:
- Visible outcome:
- Expanded/detail state:
- Persistence/reload result:
- Backend/log/DB confirmation:
- Final model/runtime wording check:
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Automated Evidence

```bash
<commands run>
```

## Findings

- Defects:
- Regressions:
- Flakes:
- Environment issues:
- Residual risks:

## Public-Safety Review

- [ ] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [ ] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [ ] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [ ] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [ ] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
