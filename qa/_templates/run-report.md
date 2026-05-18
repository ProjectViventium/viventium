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

## Natural User Use Case Checklist Run

This section must be a real checklist, not a narrative shortcut. Include every applicable natural
use case from the owning `cases.md` file and mark unrun items `BLOCKED` or `PARTIAL`.

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `<FEATURE>-UC-001` | `<user action>` | `<browser/voice/Telegram/etc>` | `<PASS/FAIL/BLOCKED/PARTIAL>` | `<sanitized observation>` | `<sanitized pointer>` | `<none or fix>` |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature:
- Requirement:
- Use case:
- QA case:
- Expected result:
- Actual evidence:
- Remaining gap or fix:

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | |
| Code owning path | Which code path owns the behavior? | |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | |
| Local/external prerequisite state | Which required local service, provider, Docker-backed sidecar, OAuth grant, API key, model, or hosted dependency was proven healthy or degraded? | |
| Logs | Which sanitized logs confirm or contradict the result? | |
| DB/state/persistence | Which sanitized state, DB count/hash, persisted message, config, or artifact confirms it? | |
| Generated/shipped artifact | Which generated config, compiled bundle, prebuilt helper, or installed artifact was inspected when applicable? | |
| Real user path | Which browser/computer, Telegram, voice, installer, CLI, MCP/tool, scheduler, or GlassHive path was used like a user? | |
| Visual/UX comparison | Does the visible UI/UX or delivered result match the expected behavior and supporting evidence? | |
| Not run / blocked | Which required surface was not run, and why is the result partial or blocked? | |

If a required real user path was not run, mark the case `BLOCKED` or `PARTIAL`. Do not replace that
user-path evidence with mocks, unit tests, API responses, source inspection, logs, DB rows, or model
review; supporting evidence cannot replace required user-path evidence. The report must include docs
and nested docs evidence and logs, DB/state/persistence evidence when those surfaces define or prove
the feature.

## User-Grade Evidence

- Surface exercised:
- Real user path:
- Visible outcome:
- Expanded/detail state:
- Persistence/reload result:
- Local/external prerequisite state:
- Evidence retrieval classification, if applicable: successful-empty, provider unavailable, timeout,
  rate limit, auth/config missing, request rejected, unsupported configuration, or local prerequisite
  unavailable.
- Fallback path, if applicable: browser/computer/local-delegation used or blocked reason recorded.
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

Confirm every item below, then change `- [ ]` to `- [x]`; the v2 contract test rejects unchecked
boxes.

- [ ] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [ ] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [ ] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [ ] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [ ] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
