# Telegram Multiple-Account Status Regression QA Run - 2026-08-12

## Summary

- Result: FAIL
- Build/source under test: isolated clean parent candidate with the merged LibreChat pin
- Runtime/artifact under test: installed local-prod generated config and immutable Telegram component
- Environment: real Telegram Desktop against local Viventium
- Tester: Codex using macOS desktop QA
- Related change: post-alignment verification of multiple connected-account slots

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `MCPOAUTH-007` | FAIL | generated config, Agent tool inventory, visible Telegram result, committed delivery acknowledgement | Both Google slots were deployed; only one appeared in the answer. |
| `MCPOAUTH-UC-006` | FAIL | privacy-bounded all-account status request on Telegram Desktop | No mail or calendar content was requested or read. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: multiple independent accounts on one OAuth MCP provider
- Requirement: all-account requests cover every configured slot exactly once and make partial failures explicit
- Use case: check connection status for every configured Google slot and Microsoft 365 without reading content
- QA case: `MCPOAUTH-007` and `MCPOAUTH-UC-006`
- Expected result: one status for Google slot one, Google slot two, and Microsoft 365
- Actual evidence: the visible answer returned one Google status and one Microsoft status, silently omitting Google slot two
- Remaining gap or fix: restore complete per-slot reporting without provider-name, prompt-text, or user-specific runtime branching

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Code owning path | Config compiler, generated MCP server catalog, Agent tool projection, Telegram bridge, and capability handoff reviewed. |
| Docs and nested docs/repos | MCP multiple-account requirement and living case catalog reviewed. |
| Scripts or harnesses | Sanitized YAML inventory and Mongo delivery-state query ran. |
| Local/external prerequisite state | Both Google slot servers and Microsoft 365 were configured; no content access was authorized for this test. |
| Logs, DB/state/persistence | No current-turn missing-server configuration error; response ended finished, non-error, with committed acknowledgement. |
| Generated/shipped artifact | Generated Agent carried 52 provider tools: 16 for each Google slot and 20 other provider tools. |
| Real user path | Real Telegram Desktop request and visible result. |
| Not run / blocked | Browser and GlassHive parity were not rerun; provider content reads were intentionally excluded. |

Supporting evidence cannot replace required user-path evidence; the real Telegram Desktop path was run.

## User-Grade Evidence

- Surface exercised: Telegram Desktop, local Telegram bot, Viventium Main, and Connected Accounts handoff
- Real user path: requested status only for every configured Google slot and Microsoft 365, explicitly forbidding mail or calendar reads
- Visible outcome: one Google slot was labeled connected and Microsoft 365 unavailable; the second Google slot was absent
- Expanded/detail state: generated runtime independently confirmed two configured Google servers and one Microsoft server
- Persistence/reload result: the assistant message finalized with a committed delivery acknowledgement; restart was not run for this case
- Local/external prerequisite state: both Google slots were deployed; credential health remains private and per-slot
- Evidence retrieval classification, if applicable: incomplete status coverage, not an empty provider result
- Fallback path, if applicable: the answer completed, but did not disclose enough evidence to credit the omitted slot
- Backend/log/DB confirmation: finished, non-error, acknowledged delivery; no missing-server configuration exception
- Final model/runtime wording check: concise but incomplete because one configured slot was silently omitted
- Substitution check: config, logs, and DB state support the visible failure; they do not replace it

## Automated Evidence

```bash
uv run --with pytest --with fastapi --with-requirements scripts/viventium/requirements.txt \
  --with-requirements viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex/requirements.txt \
  python -m pytest tests/release/ -q --disable-warnings
```

## Findings

- Defects: a current all-account Telegram status turn silently omitted the second deployed Google slot.
- Regressions: historical multi-account Telegram PASS does not hold for the current runtime response.
- Flakes: one real failure rejects the release claim; repeatability and cross-surface scope remain to be measured.
- Environment issues: Microsoft 365 was unavailable, but that does not explain omission of a separately configured Google slot.
- Residual risks: direct provider reads, browser parity, GlassHive parity, and per-slot degraded-state handling still need reruns after a structural fix.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, statuses, and conclusions only.
