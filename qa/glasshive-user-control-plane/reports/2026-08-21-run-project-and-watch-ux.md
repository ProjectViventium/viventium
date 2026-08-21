# Run Project and Watch UX QA Run - 2026-08-21

## Summary

- Result: PARTIAL. The visible UX passed, but installed acceptance was withdrawn after a later
  workspace read exposed database I/O failures that process-only health had missed.
- Corrective source candidate: GlassHive `3cb0bf8...`; installed pin pending.
- Runtime/artifact under test: the affected canary was recovered from its verified rollout snapshot;
  the corrected health gate still needs installed acceptance.
- Environment: signed-in hosted Microsoft Edge desktop plus prior local headed Chromium at desktop
  and 390-pixel viewport.
- Tester: automated agent plus visible browser inspection.
- Related change: six surgical workspace, launch, account-route, and active-status UX corrections.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHUCP-019` | PARTIAL | 237 UI tests, local responsive browser, recovered Edge run, and database-health regressions | The six UX paths pass; corrected installed health and wider accessibility remain open. |
| `GHUCP-034` | PARTIAL | installed Codex/Claude route switching and refresh proof | No connector or provider behavior changed in this run. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `UC-004` | Open Workspaces and find saved and one-off work | Installed Edge | PASS after recovery | All workspaces again showed saved, one-off, and legacy entries. | Verified snapshot restored workspace state; the new health check reads the schema. | Deploy and accept the corrected health gate. |
| `UC-005` | Choose a worker and account before starting work | Installed Edge | PASS | Worker appeared before Advanced; Codex and Claude each showed the correct personal account route. | POST contract and route-helper regressions passed. | Wider account-policy matrix. |
| `UC-011` | Watch active work without console noise | Installed Edge + real worker | PASS | Human lifecycle copy was visible; raw status stayed in collapsed Technical details; completed result remained unchanged. | Run completed, file opened, refresh persisted, lease count returned to zero, and error-level service logs were empty. | Keyboard/screen-reader matrix. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: GlassHive Run Project, Workspaces, and Watch UX.
- Requirement: `GH-UCP-006`, `GH-UCP-007`, `GH-UCP-011`.
- Use case: find work, understand the selected execution route, and monitor active work.
- QA case: `GHUCP-019`, with account-route coverage from `GHUCP-034`.
- Expected result: one clear Worker selector, honest account route, All workspaces default, and collapsed diagnostics.
- Actual evidence: complete UI test file, local responsive browser, recovered installed Edge,
  snapshot integrity, and focused database-health regressions.
- Remaining gap or fix: corrected installed health plus the wider keyboard-only and screen-reader matrix.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which contract is proven? | `GH-UCP-006`, `007`, `011`; `GHUCP-019`. |
| Code owning path | Which code owns it? | Glass Drive static launch, workspace, route-summary, and Watch presenters. |
| Docs and nested docs/repos | Which docs define it? | Requirement 55, cases, coverage, and nested UI tests. |
| Scripts or harnesses | What exercised it? | Complete UI pytest file, local headed Chromium, and installed Edge. |
| Local/external prerequisite state | What was healthy? | Hosted runtime, UI, MCP, personal Codex, and personal Claude routes were healthy. |
| Logs | What confirms it? | No error-level runtime/UI/MCP journal entries during the accepted run. |
| DB/state/persistence | What persisted? | Run completed without a failure class; refresh preserved result and links; provider lease returned to zero. |
| Generated/shipped artifact | Was the installed artifact inspected? | The prior triplet was exact but falsely healthy; corrected artifact proof is pending. |
| Real user path | What was used like a user? | Fresh Edge tab, Run Project, worker-route switch, Workspaces/filter, real Watch, file open, and refresh. |
| Visual/UX comparison | Did it match? | Desktop and 390-pixel layouts matched the reviewed hierarchy with no horizontal overflow. |
| Not run / blocked | What remains? | Keyboard-only and screen-reader acceptance; installed 390-pixel rerun. |

## User-Grade Evidence

- Surface exercised: installed hosted Edge on Glass Drive and Watch, plus prior local responsive Chromium.
- Real user path: fresh tab, open Run Project, switch Codex/Claude, open Workspaces, filter, launch,
  watch, open the delivered file, and refresh.
- Visible outcome: All workspaces by default; Worker before Advanced; honest account route; concise active status.
- Expanded/detail state: Technical details stayed collapsed until clicked, then showed redacted raw text.
- Persistence/reload result: reload returned to All workspaces and retained the saved default worker preference.
- Local/external prerequisite state: installed three-service canary and personal AI routes healthy.
- Evidence retrieval classification, if applicable: not applicable.
- Fallback path, if applicable: none.
- Backend/log/DB confirmation: completed run, empty failure class, recorded output, zero active provider
  leases, exact three-service health, unchanged stable ingress, and no error-level service logs.
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

- Defects: the old runtime health route did not read SQLite, so rollout acceptance could miss an
  unreadable workspace store. The source fix now fails closed with a redacted `503`.
- Regressions: retained workspaces load again after verified snapshot recovery.
- Flakes: none observed.
- Environment issues: the first post-cache-cleanup attempt rebuilt the worker image and timed out;
  retry was actionable, and the final run completed after the image was available.
- Residual risks: keyboard-only, screen-reader, and installed narrow-viewport acceptance remain open.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
