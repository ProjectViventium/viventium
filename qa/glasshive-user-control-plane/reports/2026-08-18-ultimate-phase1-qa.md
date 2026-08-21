# Ultimate Phase 1 QA — 2026-08-18

## Summary

- Result: PASS
- Scope note: the installed Ultimate Phase 1 journey passed; the broader control-plane roadmap remains PARTIAL.
- Build/source under test: exact tested and source-follow-up identities are separated in the completion ledger.
- Runtime/artifact under test: installed hosted GlassHive release.
- Environment: authenticated Edge, native Claude/Codex workers, and fresh Codex/Claude MCP clients.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHUCP-007` | PASS | Stale account removed; intended personal accounts stayed Ready after refresh | Provider-native logout uncertainty was stated honestly |
| `GHUCP-009`, `034B` | PASS | Setup window blocked mission creation; exit released the lease; retry completed | Wider live contention matrix remains open |
| `GHUCP-012`, `034A` | PASS | Same Favorite Claude workspace retained native Gmail state and delivered files after reuse/refresh | Gmail was already connected; fresh Claude connector consent was not claimed |
| `GHUCP-020`, `034` | PASS | Fresh Codex and Claude controllers each used one launch plus one bounded wait against the same workspace | No catalog discovery or duplicate workspace |
| `GHUCP-034` Codex rerun | BLOCKED | Provider usage limit rejected the current rerun | Prior installed Outlook/SharePoint connect/read/reuse evidence remains valid |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Ultimate Phase 1 personal accounts, persistent workspaces, native tools, and MCP control.
- Requirement: `GH-UCP-004` through `GH-UCP-012` and `GH-UCP-018`.
- Use case: connect personal AI, reuse one Favorite workspace with native tools, and control it from fresh clients.
- QA case: `GHUCP-007`, `009`, `012`, `020`, and `034` including subcases `034A`–`034C`.
- Expected result: one short path, native connector ownership, durable reuse, honest failures, and no duplicate/global wiring.
- Actual evidence: installed Edge workflow, native Gmail read/reuse, account removal, refresh, and fresh Codex/Claude launch/wait.
- Remaining gap or fix: two-owner, confirmed write/revoke/renewal, automatic schedule, Library worker use, and clean install/restore.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Requirement and use case | Requirement 55, completion ledger, coverage matrix, and `GHUCP-034` |
| Code owning path | Provider lifecycle/leases, workspace catalog/MCP launch-wait, UI, and deliverable handling |
| Docs and nested docs/repos | Parent requirement/QA plus nested Ultimate Phase 1 release notes |
| Scripts or harnesses | Provider, runtime, MCP, and Glass Drive suites recorded below |
| Local/external prerequisite state | Personal Claude healthy; current Codex rerun provider-quota blocked |
| Logs, DB/state/persistence | Completed runs, released lease, Favorite workspace, delivered files, and idle backend |
| Generated/shipped artifact | Installed provenance recorded separately from source-only follow-up commits |
| Real user path | Edge, native Claude workspace, fresh Codex task, and fresh Claude Desktop session |
| Visual/UX comparison | Removal, contention copy, Favorite card, output, and refresh matched the intended contract |
| Not run / blocked | Wider gates listed in Traceability; current Codex rerun blocked by external quota |

## User-Grade Evidence

- Surface exercised: installed GlassHive in Edge, native Claude workspace, Codex MCP, and Claude MCP.
- Real user path: remove stale account -> set up tools -> native read -> close -> run -> refresh -> fresh-client reuse.
- Visible outcome: one Ready account per provider, one Favorite reusable workspace, and distinct delivered proof files.
- Expanded/detail state: native tool catalog, setup conflict, delivered files, and account removal detail were inspected.
- Persistence/reload result: refresh retained account readiness, Favorite state, workspace identity, and latest output.
- Backend/log/DB confirmation: run/lease/catalog state correlated with the visible completion and no duplicate workspace.
- Final model/runtime wording check: quota, sign-out uncertainty, and setup contention were reported honestly.
- Substitution check: tests, logs, DB rows, API responses, source inspection, and model reviews support but do not replace the real user paths above.

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

## Findings

### Connector findings

- Connector availability is owned by the native worker account, not hardcoded by GlassHive.
- Atlassian was not present in the tested Claude account's native catalog. GlassHive did not pretend
  that it was available.
- The same account already exposed several native services; Gmail provided the shortest safe live
  proof. Microsoft 365 was listed but required separate native authorization.
- Existing Codex evidence covers a different native family—Outlook/SharePoint—so the combined proof
  is not tied to one connector or one provider.

### UX findings

- The one-button Remove flow is now discoverable and reversible on failure.
- Native setup and mission execution cannot silently share one account at the same time. The visible
  conflict told the user to finish or close setup; retry worked immediately after exit.
- External clients needed no workspace discovery or tool-catalog narration. One short prompt was
  enough in both Codex and Claude.
- Provider quota remains external and is surfaced honestly. It must not trigger connector-specific
  code or release infrastructure.

## Automated Evidence

- The owning provider lifecycle suite passed `42/42`.
- The owning Glass Drive UI suite passed `233/233`.
- Independent Claude review found no P0/P1 issue. Its two actionable removal P2s were reproduced and
  fixed; the suggested grant-row deletion change was rejected because those legacy rows carry a real
  foreign-key dependency on the account being removed.
- The exact live observations remain private operator evidence rather than public screenshots or
  customer/account identifiers in this repository.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots, personal emails, account identifiers, or customer data.
- [x] No conversation, message, session/call, provider-request, or database identifiers.
- [x] No local absolute paths, hostnames, machine names, private stack traces, exports, or runtime dumps.
- [x] Private observations are summarized only as sanitized outcomes and counts.

## Provenance and acceptance follow-up

- The installed test baseline and later source-only follow-up revisions are recorded separately in
  the [completion ledger](../completion-ledger.md); later documentation commits are not presented as
  the exact installed artifact that produced this evidence.
- On 2026-08-21, the product owner retested the accepted user journey and confirmed it was satisfactory.
  This records acceptance of the scoped behavior above; it does not promote any wider pending gate.
- The final public candidate adds documentation, release notes, and regression traceability without
  connector-specific behavior or private evidence.

## Verdict

The foundational Phase 1 design is proven for the installed Claude path, reusable native connector
state, browser persistence, connection removal, and both external MCP clients. The broader product
ledger remains `PARTIAL` because two-user isolation, confirmed write/revoke/renewal, clean install/
restore, and unrelated Library/scheduler gates are outside this exact QA slice. The only blocked
lane inside this rerun is the personal Codex worker's provider quota; repeat that one mission after
the provider reset without changing GlassHive.
