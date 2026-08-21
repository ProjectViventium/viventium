# Hosted personal Claude code handoff and workspace reuse — 2026-08-17

## Summary

- Result: PASS for installed personal-Claude authorization, mission, continuation, refresh, and Favorite retention.
- Build/source under test: exact release and source revisions recorded below.
- Runtime/artifact under test: installed three-service hosted canary.
- Environment: authenticated Microsoft Edge browser and installed GlassHive.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHUCP-007` | PASS | Provider-issued code reached Ready and survived refresh | The code itself was not retained |
| `GHUCP-009` | PASS | Two selected-account missions used the same workspace and delivered the same file | Wider contention remained separate |
| `GHUCP-012` | PASS | Favorite and completed output persisted after refresh | Full service-restart matrix remained open |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: personal Claude account and persistent workspace reuse.
- Requirement: `GH-UCP-005` through `GH-UCP-007`.
- Use case: connect once, run work, continue it, and return to the same Favorite workspace.
- QA case: `GHUCP-007`, `GHUCP-009`, and `GHUCP-012`.
- Expected result: one owner-scoped account and workspace persist without exposing the one-time code.
- Actual evidence: installed Edge authorization, two missions, delivered file, refresh, and backend state.
- Remaining gap or fix: wider two-owner, rotation, and full contention paths remained open.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Requirement, docs, and nested docs | Requirement 55 and cases `007`, `009`, `012` own the behavior |
| Code, scripts, and automated harness | Provider setup, mission binding, UI/BFF, pin, and release suites |
| Local/external prerequisite state | Provider consent and installed canary were healthy |
| Logs, DB/state/persistence | Two observed runs, zero observed failures, persisted output and Favorite metadata |
| Generated/shipped artifact | Exact release and source identities recorded below |
| Real user path and visual comparison | Edge Connections -> Run project -> Watch -> Continue -> Favorite -> refresh |
| Not run / blocked | Two-owner, rotation, and full contention/recovery were not run here |

## User-Grade Evidence

- Surface exercised: installed GlassHive Connections, Run project, Watch, and Workspaces in Microsoft Edge.
- Real user path: authorize personal Claude -> submit code -> run -> inspect output -> continue -> Favorite -> refresh.
- Visible outcome: Ready persisted; two missions updated one delivered file in the same workspace.
- Expanded/detail state: Watch exposed the completed file and Workspaces showed Personal Claude ready.
- Persistence/reload result: hard refresh kept account readiness, Favorite, workspace identity, and output.
- Backend/log/DB confirmation: account metadata recorded two runs and zero failures; exact canary health passed.
- Final model/runtime wording check: the UI reported completed work and never echoed the submitted code.
- Substitution check: tests, API metadata, and logs support but do not replace the installed Edge path above.

## Result

**PASS** for the requested installed path: a user can connect a supported personal Claude
subscription through the normal Connections UI, paste the provider-issued one-time code into a
masked GlassHive field, refresh, run a real Claude Code workspace, continue the same workspace, and
retain it as a Favorite. The plain hosted origin also redirects to the current full GlassHive app.

## Installed build

- release: `glasshive-20260817-claude-code-input-33`
- parent revision: `d756f8fe6a3e35d30e75455bc44db3944b87f3f4`
- GlassHive revision: `490a0817808f6491610d842f91d28bc572953271`

The exact three-service canary was committed only after real browser acceptance. The prior stable
root still served an older two-tab UI; the deployment edge now issues one temporary redirect from
that root to the current hosted GlassHive origin while preserving the current app and MCP route.

## Real browser flow

Run in an authenticated Microsoft Edge profile against the installed hosted development release:

1. Open **Connections**, choose the personal Claude setup, and open the reviewed official sign-in
   destination.
2. Complete provider consent, copy the returned authentication code, return to GlassHive, paste it
   into the masked **Authentication code** field, and choose **Finish connecting**.
3. Confirm the field clears, the account becomes **Ready**, and a hard refresh keeps it **Ready**.
4. Open **Run project**, select **Claude Code worker**, confirm **Personal Claude (default)** and
   **Only my account; never fall back**, and launch a synthetic file task.
5. Watch the real workspace progress from running to Completed and expand the delivered file.
6. Continue the same completed workspace with a second short instruction. Confirm the original
   content remains and the requested second line is appended exactly.
7. Return to **Workspaces**, switch to all workspace types, mark the Claude workspace as Favorite,
   refresh, and confirm the same completed card shows **Personal Claude: ready** and **Remove
   favorite**.
8. Navigate to the plain hosted origin with a fresh query. Confirm it lands on the current app and
   exposes Run project, Workspaces, Connections, Library, Schedules, and Activity.

## Evidence

- The account API reported the personal Claude account as Ready after the browser handoff.
- The account recorded two observed runs, zero observed failures, and updated last-used metadata.
- The first mission delivered `claude-reuse-proof.txt` with the requested single synthetic line.
- The continuation reused the same workspace and delivered the same file with both exact lines.
- The workspace catalog reported Claude Code, Completed, Personal Claude ready, and Favorite after
  refresh.
- The edge redirect returned the current app without changing its six-view navigation.
- Full affected parent release tests passed: 108 passed, 1 skipped.
- Full nested runtime and UI/BFF suites, focused code-input regressions, syntax checks, component pin
  checks, and diff checks passed before rollout.

The one-time code and provider credential were not written to this report, source, logs, API output,
or the runtime database. The UI clears the masked field after one submission and persists only the
provider-owned authenticated home.

## Automated Evidence

- Parent release suite: 108 passed, 1 skipped.
- Full nested runtime/UI suites, focused code-input regressions, syntax, pin, and diff checks passed.

## Findings

- The normal GlassHive handoff supported the provider-issued code without storing or echoing it.
- The same personal account and workspace were reusable across a second mission and refresh.
- No scoped defect remained; wider lifecycle gates stayed explicit.

## Remaining boundary

This run does not claim the separate reconnect/expiry/forget matrix, concurrent two-account
contention, two-user isolation, or a native Outlook/SharePoint connection inside the Claude worker.
Those remain PARTIAL. Personal Claude login, real mission execution, same-workspace continuation,
refresh persistence, and Favorite retention are no longer open.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots, personal emails, account identifiers, or customer data.
- [x] No conversation, message, session/call, provider-request, or database identifiers.
- [x] No local absolute paths, hostnames, machine names, private stack traces, exports, or runtime dumps.
- [x] Private observations are summarized only as sanitized outcomes and counts.
