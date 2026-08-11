# Hosted Hello-World Artifact UX QA Run - 2026-08-10

## Summary

- Result: PARTIAL; the real pre-fix user path exposed two defects and the merged source correction
  passed automated and local Chromium security gates. Exact post-fix hosted acceptance remains open.
- Build/source under test: merged GlassHive PR 74 plus its parent pin candidate.
- Runtime/artifact under test: additive hosted GlassHive canary; stable LibreChat was observed only for
  availability and was not modified.
- Environment: hosted multi-user GlassHive through real Chrome, with sanitized synthetic task content.
- Tester: Viventium release QA.
- Related change: safe rendered HTML artifact preview and same-origin attachment download.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHWATCH-003` | PARTIAL | Real Chrome, durable completed run, and source suites | Open/Download failed before the correction; opaque workspace return passed. |
| `GHWATCH-013` | PARTIAL | 436 affected tests and headed benign/adversarial Chromium probe | Exact pinned installed Open/Download rerun remains open. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `GHWATCH-UC-004` | Complete one HTML task, open and download it, then return to the workspace. | Real hosted Chrome and GlassHive Watch | FAIL before fix / PARTIAL after source fix | Watch showed completion; View workspace and refresh worked; Open showed source and Download opened an error tab. | Completed/ready run and workspace, zero active provider leases, and `index.html` present. | Repeat on the exact post-fix installed canary. |
| `GHWATCH-UC-013` | Open the HTML as a page, download exact bytes, return, refresh, and check supported widths. | Local headed Chromium plus pre-fix hosted Chrome | PARTIAL | Local rendered page and sandbox boundary passed; exact hosted post-fix UX not yet run. | Full affected suites and merged source/docs reviewed. | Exact installed Chrome Open/Download and width checks. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: GlassHive completed HTML artifact experience.
- Requirement: browser-visible deliverables end on a usable result while the live desktop remains primary.
- Use case: complete a simple HTML page, open it as a page, download it, and return to its workspace.
- QA case: `GHWATCH-003` and escaped regression `GHWATCH-013`.
- Expected result: rendered page, exact attachment, opaque workspace return, safe refresh, no raw errors.
- Actual evidence: recovery, personal-only launch, opaque handoff, completion, workspace return, and
  persistence passed; pre-fix Open/Download failed; merged source plus adversarial Chromium passed.
- Remaining gap or fix: seal and activate the exact parent/nested pair, then repeat the real hosted
  Chrome loop and update this report.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | `GHWATCH-003`, `GHWATCH-013`, `GHWATCH-UC-004`, and `GHWATCH-UC-013`. |
| Code owning path | Which code path owns the behavior? | GlassHive runtime artifact landing/download routes and Glass Drive Watch link rendering. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | Minimal operator UI requirement, GlassHive nested artifact behavior, and this living Watch QA catalog. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Full runtime API/UI suites and a real headed Chromium sandbox probe. |
| Local/external prerequisite state | Which required dependency was proven? | Personal Codex account reached Ready and completed the hosted task; provider lease returned to zero. |
| Logs | Which sanitized logs confirm or contradict the result? | Service health stayed active; no raw log or identifier is retained publicly. |
| DB/state/persistence | Which sanitized state confirms it? | Latest workspace ready, run completed, account ready, zero active leases, artifact present. |
| Generated/shipped artifact | Which installed artifact was inspected? | Pre-fix sealed additive canary was exercised; post-fix pin/build is pending activation. |
| Real user path | Which real surface was used like a user? | Real Chrome: Check connection -> Run Project -> Watch -> Open/Download -> View workspace -> refresh. |
| Visual/UX comparison | Does visible behavior match? | Completion and return matched; pre-fix preview/download did not. |
| Not run / blocked | Which required surface was not run? | Exact post-fix hosted Open/Download and fresh public bootstrap remain open. |

## User-Grade Evidence

- Surface exercised: real Chrome against the installed additive GlassHive HTTPS canary.
- Real user path: recover the existing personal account, submit `Show a simple hello world html
  page`, follow the automatic opaque handoff, inspect completion, Open, Download, View workspace,
  and refresh.
- Visible outcome: `Worker completed` and `Workspace complete` appeared. Before the fix, Open showed
  escaped source and Download opened a browser error tab.
- Expanded/detail state: the Watch result identified the delivered `index.html` and its actions.
- Persistence/reload result: View workspace returned to the completed Watch surface and refresh kept
  the completed state.
- Local/external prerequisite state: the personal provider account was Ready before and after the
  mission; no active provider lease remained afterward.
- Evidence retrieval classification, if applicable: provider and artifact evidence retrieved
  successfully; the preview/download mismatch was a product defect, not missing evidence.
- Fallback path, if applicable: no fallback provider was allowed or used.
- Backend/log/DB confirmation: sanitized state showed completed run, ready workspace/account, zero
  active leases, and the HTML artifact present.
- Final model/runtime wording check: visible completion wording matched durable state; this report
  does not call the post-fix hosted artifact UX passed before it is rerun.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for the required post-fix visible Chrome path.

## Automated Evidence

```bash
pytest runtime_phase1/tests/test_api.py
pytest frontends/glass-drive-ui/tests/test_server.py
node --check frontends/glass-drive-ui/src/glass_drive_ui/static/watch.js
git diff --check
```

- Runtime API: 232 passed.
- Glass Drive UI: 204 passed.
- Headed Chromium benign/adversarial sandbox probe: passed. The self-contained page rendered; parent
  state remained intact; blocked active content did not act; confined same-origin navigation sent
  neither authentication nor referrer data.
- Two independent review-only security/UX passes: GO, no P0-P2 source blocker.

## Findings

- Defects: pre-fix Open displayed escaped HTML source; pre-fix Download opened a browser error tab.
- Regressions: both escaped defects are now represented by `GHWATCH-013`.
- Flakes: none observed in the affected source suites.
- Environment issues: exact post-fix release was not yet installed at the time of this report revision.
- Residual risks: exact installed Chrome Open/Download, width checks, and fresh public bootstrap remain
  PARTIAL until executed.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
