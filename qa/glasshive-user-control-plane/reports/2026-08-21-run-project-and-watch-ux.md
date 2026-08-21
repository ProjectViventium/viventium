# Run Project and Watch UX QA Run - 2026-08-21

## Summary

- Result: PASS for the affected local browser surface; installed acceptance remains PARTIAL.
- Build/source under test: reviewed GlassHive feature revision `0442614d...`.
- Runtime/artifact under test: local synthetic UI runtime from the reviewed source tree.
- Environment: local headed Chromium, desktop and 390-pixel viewport.
- Tester: automated agent plus visible browser inspection.
- Related change: six surgical workspace, launch, account-route, and active-status UX corrections.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHUCP-019` | PARTIAL | 237 UI tests plus headed browser | Affected local paths pass; installed and accessibility matrix remains open. |
| `GHUCP-034` | PARTIAL | account-route UI and refresh proof | No connector or provider behavior changed in this run. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `UC-004` | Open Workspaces and find saved and one-off work | Headed local Chromium | PASS | All workspaces showed both kinds before and after reload; Saved filtered correctly. | One bounded `kind=named,ephemeral,legacy` request; no console error. | Hosted artifact proof. |
| `UC-005` | Choose a worker and account before starting work | Headed local Chromium | PASS | Worker and effective account appeared before Advanced; account copy updated with selections. | POST contract and route-helper regressions passed. | Hosted account-data proof. |
| `UC-011` | Watch active work without console noise | Headed local Chromium | PASS | Human lifecycle copy was visible; raw text appeared only after Technical details opened. | Lifecycle-only rendering regressions passed. | Real hosted running worker. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: GlassHive Run Project, Workspaces, and Watch UX.
- Requirement: `GH-UCP-006`, `GH-UCP-007`, `GH-UCP-011`.
- Use case: find work, understand the selected execution route, and monitor active work.
- QA case: `GHUCP-019`, with account-route coverage from `GHUCP-034`.
- Expected result: one clear Worker selector, honest account route, All workspaces default, and collapsed diagnostics.
- Actual evidence: complete UI test file plus desktop/mobile headed Chromium checks.
- Remaining gap or fix: validate the installed hosted artifact and wider keyboard/screen-reader matrix.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which contract is proven? | `GH-UCP-006`, `007`, `011`; `GHUCP-019`. |
| Code owning path | Which code owns it? | Glass Drive static launch, workspace, route-summary, and Watch presenters. |
| Docs and nested docs/repos | Which docs define it? | Requirement 55, cases, coverage, and nested UI tests. |
| Scripts or harnesses | What exercised it? | Complete UI pytest file plus headed Chromium browser harness. |
| Local/external prerequisite state | What was healthy? | Local synthetic UI API and browser were healthy; no external provider was required. |
| Logs | What confirms it? | Browser console contained no errors. |
| DB/state/persistence | What persisted? | Page reload restored All workspaces and the saved default worker preference regression passed. |
| Generated/shipped artifact | Was the installed artifact inspected? | Not in this local run; remains PARTIAL. |
| Real user path | What was used like a user? | Clicked Run Project, Workspaces, filters, worker/account/policy controls, Watch, and Technical details. |
| Visual/UX comparison | Did it match? | Desktop and 390-pixel layouts matched the reviewed hierarchy with no horizontal overflow. |
| Not run / blocked | What remains? | Installed hosted artifact, noVNC stream, keyboard-only, and screen-reader acceptance. |

## User-Grade Evidence

- Surface exercised: real local headed Chromium on Glass Drive and Watch.
- Real user path: open Run Project, change worker/account/policy, open Workspaces, filter, reload, and expand Watch details.
- Visible outcome: All workspaces by default; Worker before Advanced; honest account route; concise active status.
- Expanded/detail state: Technical details stayed collapsed until clicked, then showed redacted raw text.
- Persistence/reload result: reload returned to All workspaces and retained the saved default worker preference.
- Local/external prerequisite state: local synthetic runtime healthy; no external provider was required.
- Evidence retrieval classification, if applicable: not applicable.
- Fallback path, if applicable: none.
- Backend/log/DB confirmation: bounded workspace request and zero browser console errors.
- Final model/runtime wording check: active copy used structured lifecycle state only and did not parse prompt prefixes.
- Substitution check: automated and network evidence supported the real browser result; it did not replace it.

## Automated Evidence

```bash
uv run --project frontends/glass-drive-ui --with pytest pytest frontends/glass-drive-ui/tests/test_server.py -q
node --check frontends/glass-drive-ui/src/glass_drive_ui/static/app.js
node --check frontends/glass-drive-ui/src/glass_drive_ui/static/watch.js
node --check frontends/glass-drive-ui/src/glass_drive_ui/static/launch-policy.js
node --check frontends/glass-drive-ui/src/glass_drive_ui/static/delivery-presenter.js
git diff --check
```

## Findings

- Defects: none remaining in the six affected local paths.
- Regressions: none observed.
- Flakes: none observed.
- Environment issues: none.
- Residual risks: installed hosted artifact and broader accessibility acceptance remain open.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
