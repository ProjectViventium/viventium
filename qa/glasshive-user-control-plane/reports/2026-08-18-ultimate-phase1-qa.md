# Ultimate Phase 1 QA — 2026-08-18

## Scope

This run stayed limited to the user journey requested for Ultimate Phase 1:

- use the installed GlassHive UI in the intended Edge profile;
- connect and remove personal worker accounts;
- use native worker connectors without connector-specific GlassHive wiring;
- reuse one clearly named Favorite workspace;
- control the same workspace from fresh Codex and Claude MCP clients;
- exercise the obvious failure boundaries.

It did not add cloud backup work, connector-specific adapters, or unrelated release machinery.

## Results

| Lane | Result | Evidence |
| --- | --- | --- |
| Connection removal | PASS | A stale duplicate Claude row exposed one **Remove** action. Confirming it removed the private local account and metadata; the UI honestly reported that provider-native sign-out could not be confirmed. Refresh showed only the intended Ready Codex and Claude accounts. The follow-up source review added regressions for reload-failure retry, absent native homes, and a no-follow final-symlink cleanup path. |
| Claude native connector setup/use | PASS | **Set up tools** opened the real isolated Claude Code workspace. The native catalog showed the account's available services. Gmail was already connected, performed a real read, and wrote only a privacy-bounded aggregate plus timestamp to `gmail-proof.md`. No sender, subject, or message body was retained. |
| Claude saved-workspace reuse | PASS | A mission attempted while native setup remained open was rejected before dispatch with an actionable setup-window conflict. Exiting native Claude released the interactive lease. The same Favorite workspace then completed a normal mission and delivered `gmail-reuse-proof.md`. |
| Browser refresh/persistence | PASS | Refresh preserved the Favorite workspace, Personal Claude Ready state, and the latest delivered file. |
| Fresh Codex MCP controller | PASS | A new isolated Codex task followed the short instruction literally: one `workspace_launch`, one bounded `workspace_wait`, no catalog listing, same saved workspace, delivered `codex-controller-gmail-proof.md`. |
| Fresh Claude MCP controller | PASS | A new Claude Desktop session used two GlassHive calls total—launch and wait—reused the same saved workspace, and delivered `claude-controller-gmail-proof.md`. |
| Codex native connected-service path | PASS from the prior installed run / BLOCKED in this rerun | The accepted installed evidence already proves Outlook and SharePoint authorization, read, refresh, restart, and same-worker reuse. In this current rerun the selected personal Codex account was Ready and GlassHive launched it, but OpenAI rejected the turn for the account's current usage limit. No product workaround was added. |

## Connector findings

- Connector availability is owned by the native worker account, not hardcoded by GlassHive.
- Atlassian was not present in the tested Claude account's native catalog. GlassHive did not pretend
  that it was available.
- The same account already exposed several native services; Gmail provided the shortest safe live
  proof. Microsoft 365 was listed but required separate native authorization.
- Existing Codex evidence covers a different native family—Outlook/SharePoint—so the combined proof
  is not tied to one connector or one provider.

## UX findings

- The one-button Remove flow is now discoverable and reversible on failure.
- Native setup and mission execution cannot silently share one account at the same time. The visible
  conflict told the user to finish or close setup; retry worked immediately after exit.
- External clients needed no workspace discovery or tool-catalog narration. One short prompt was
  enough in both Codex and Claude.
- Provider quota remains external and is surfaced honestly. It must not trigger connector-specific
  code or release infrastructure.

## Verification

- The owning provider lifecycle suite passed `42/42`.
- The owning Glass Drive UI suite passed `233/233`.
- Independent Claude review found no P0/P1 issue. Its two actionable removal P2s were reproduced and
  fixed; the suggested grant-row deletion change was rejected because those legacy rows carry a real
  foreign-key dependency on the account being removed.
- The exact live observations remain private operator evidence rather than public screenshots or
  customer/account identifiers in this repository.

## Verdict

The foundational Phase 1 design is proven for the installed Claude path, reusable native connector
state, browser persistence, connection removal, and both external MCP clients. The broader product
ledger remains `PARTIAL` because two-user isolation, confirmed write/revoke/renewal, clean install/
restore, and unrelated Library/scheduler gates are outside this exact QA slice. The only blocked
lane inside this rerun is the personal Codex worker's provider quota; repeat that one mission after
the provider reset without changing GlassHive.
