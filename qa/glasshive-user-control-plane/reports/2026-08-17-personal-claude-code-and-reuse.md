# Hosted personal Claude code handoff and workspace reuse — 2026-08-17

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

## Remaining boundary

This run does not claim the separate reconnect/expiry/forget matrix, concurrent two-account
contention, two-user isolation, or a native Outlook/SharePoint connection inside the Claude worker.
Those remain PARTIAL. Personal Claude login, real mission execution, same-workspace continuation,
refresh persistence, and Favorite retention are no longer open.
