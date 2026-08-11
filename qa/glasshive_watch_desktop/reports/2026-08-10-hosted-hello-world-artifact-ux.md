# Hosted Hello-World Artifact UX QA Run - 2026-08-10

## Summary

- Result: PASS for the exact installed core user path; the pre-fix defects were reproduced, corrected,
  and then rerun successfully through real Chrome. Hosted narrow-width repetition remains open.
- Build/source under test: parent merge `889ae68c7d3bf26c459f0c96d473e46532f19568`
  with GlassHive merge `94c99e3fdcf05d799b5d02e6a188071dc4fbc0eb`.
- Runtime/artifact under test: additive hosted GlassHive canary; stable LibreChat was observed only for
  availability and was not modified.
- Environment: hosted multi-user GlassHive through real Chrome, with sanitized synthetic task content.
- Tester: Viventium release QA.
- Related change: safe rendered HTML artifact preview and same-origin attachment download.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHWATCH-003` | PASS | Real Chrome, durable completed run, source suites, and exact installed rerun | Rendered Open, direct Download, opaque workspace return, and refresh passed after the correction. |
| `GHWATCH-013` | PASS | 436 affected tests, headed benign/adversarial Chromium probe, and exact installed Chrome | The installed preview rendered `Hello world`; Download emitted the exact 423-byte file without navigation or an error tab. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `GHWATCH-UC-004` | Complete one HTML task, open and download it, then return to the workspace. | Real hosted Chrome and GlassHive Watch | PASS | Watch showed `Worker completed` / `Workspace complete`; Open visibly rendered `Hello world`; Download completed without leaving the preview; View workspace and refresh returned to the completed Watch. | Completed/ready run and workspace, zero active provider leases, exact 423-byte downloaded file, artifact present, and clean browser console. | None for the core use case. |
| `GHWATCH-UC-013` | Open the HTML as a page, download exact bytes, return, refresh, and check supported widths. | Exact installed Chrome plus local headed Chromium | PARTIAL | Exact installed Open/Download/return/refresh passed; local 320/768/1024 layout and adversarial sandbox probes passed. | Full affected suites, exact release provenance, merged source/docs, and installed browser assets reviewed. | Repeat the exact hosted surface at narrow widths. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: GlassHive completed HTML artifact experience.
- Requirement: browser-visible deliverables end on a usable result while the live desktop remains primary.
- Use case: complete a simple HTML page, open it as a page, download it, and return to its workspace.
- QA case: `GHWATCH-003` and escaped regression `GHWATCH-013`.
- Expected result: rendered page, exact attachment, opaque workspace return, safe refresh, no raw errors.
- Actual evidence: recovery, personal-only launch, opaque handoff, completion, rendered Open, direct
  Download, workspace return, refresh persistence, merged source, and adversarial Chromium passed.
- Remaining gap or fix: repeat the exact hosted surface at narrow widths; no core user-path defect remains.

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
| Generated/shipped artifact | Which installed artifact was inspected? | Exact sealed additive canary for parent `889ae68c...` and GlassHive `94c99e3...`; runtime, UI, MCP, and nested runtime health all reported the same provenance. |
| Real user path | Which real surface was used like a user? | Real Chrome: Check connection -> Run Project -> Watch -> Open/Download -> View workspace -> refresh. |
| Visual/UX comparison | Does visible behavior match? | Yes for completion, rendered preview, download, workspace return, and refresh. |
| Not run / blocked | Which required surface was not run? | Exact hosted narrow-width repetition and a fresh hosted public bootstrap remain open. |

## User-Grade Evidence

- Surface exercised: real Chrome against the installed additive GlassHive HTTPS canary.
- Real user path: recover the existing personal account, submit `Show a simple hello world html
  page`, follow the automatic opaque handoff, inspect completion, Open, Download, View workspace,
  and refresh.
- Visible outcome: `Worker completed` and `Workspace complete` appeared. After the fix, Open rendered
  the `Hello world` heading inside the sandboxed page preview and Download completed without navigation
  or an error tab.
- Expanded/detail state: the Watch result identified the delivered `index.html` and its actions.
- Persistence/reload result: View workspace returned through the opaque route to the completed Watch
  surface and refresh restored the completed state.
- Local/external prerequisite state: the personal provider account was Ready before and after the
  mission; no active provider lease remained afterward.
- Evidence retrieval classification, if applicable: provider and artifact evidence retrieved
  successfully; the preview/download mismatch was a product defect, not missing evidence.
- Fallback path, if applicable: no fallback provider was allowed or used.
- Backend/log/DB confirmation: sanitized state showed completed run, ready workspace/account, zero
  active leases, and the HTML artifact present.
- Final model/runtime wording check: visible completion wording matched durable state and the exact
  installed artifact UX passed its post-fix Chrome rerun.
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
- Environment issues: none for the core exact installed rerun.
- Residual risks: exact hosted narrow-width repetition and a fresh hosted public bootstrap remain open.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
