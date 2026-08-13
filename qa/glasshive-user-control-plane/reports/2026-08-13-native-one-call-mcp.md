# Native One-Call GlassHive MCP QA Run — 2026-08-13

## Summary

- Result: **PASS for the real Codex connect/list/rename/refresh/restore path; PARTIAL for the exact
  candidate UI and current Claude Code rerun**.
- Build/source under test: GlassHive `aa64d2b6d8ad811dfbe5ee3a535e24dc9fae4e4e` plus its parent
  pin candidate.
- Runtime/artifact under test: the previously accepted additive hosted canary remained live while
  the next candidate waited behind an Azure command-agent control-plane stall.
- Environment: real Codex `0.147.0`, real Claude Code `2.1.231`, and the intended signed-in Edge
  browser profile. No customer data or unrelated account was used for the GlassHive actions.
- Related change: make MCP the sole integration, keep the companion skill as a short tool guide,
  self-select one client, and verify with one `workspace_list` call.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHUCP-005` | PARTIAL | Native scoped Codex OAuth succeeded; one MCP list plus one-call rename and restore succeeded | Exact candidate copy not yet installed; current Claude account auth expired |
| `GHUCP-020` | PARTIAL | Edge showed the MCP rename after refresh and the restored name after a second refresh | Full resource/pagination/two-owner parity not run |
| `GHUCP-030` | PARTIAL | Public MCP OAuth and tool calls succeeded while the accepted browser canary remained usable | Candidate cutover and broader denial/spoof matrix pending |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `GHUCP-UC-MCP-01` | Connect Codex to GlassHive | Codex CLI + Edge | PASS | One native scoped browser round trip completed without a custom listener or token handling | Client reported OAuth connected; only one GlassHive registration remained | Candidate UI copy still awaiting install |
| `GHUCP-UC-MCP-02` | List saved workspaces | Fresh Codex task | PASS | Final answer returned two human-readable workspace names | Exactly one `workspace_list` start/completion pair | None for this action |
| `GHUCP-UC-MCP-03` | Rename and restore a workspace | Fresh Codex tasks + Edge Workspaces | PASS | New synthetic name appeared after refresh; original name reappeared after restore and refresh | One successful rename call in each direction; no run was started | Full create/delete lifecycle not applicable to this narrow regression |
| `GHUCP-UC-MCP-04` | Connect and list from Claude Code | Claude Code + Edge | BLOCKED | Claude MCP transport reported connected, but the separate Claude account login page required authentication | CLI reported an expired, non-refreshable account session before any model/tool call | Complete account login, then rerun one tool call |
| `GHUCP-UC-MCP-05` | See the simplified candidate setup | Hosted Edge UI | BLOCKED | Accepted release still showed its older combined copy | Candidate source and 282 UI tests pass; staged activation had not begun | Install candidate, hard refresh, and inspect/copy exact text |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: external AI control of GlassHive through native MCP.
- Requirement: `GH-UCP-004` in requirement 55.
- Use case: connect the current AI once, call only the requested GlassHive tool, and see the same
  named workspace state in the browser.
- QA cases: `GHUCP-005`, `020`, and `030`.
- Expected result: no second protocol/plugin/auth helper, no other-client setup, no full tool dump,
  one native OAuth flow, and one MCP call for the requested read or update.
- Actual evidence: scoped Codex native login, one-call list, one-call rename, refresh-persistent Edge
  state, one-call restore, and refresh-persistent restored state.
- Remaining gap: candidate installation and current Claude Code account authentication.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which source owns the outcome? | Requirement 55 `GH-UCP-004`; `GHUCP-005` / `020` / `030` |
| Code owning path | Which code generates setup? | Glass Drive `/api/connect-ai`, Connections renderer, and `connect-glasshive` skill |
| Docs and nested docs/repos | What defines MCP/skill/plugin roles? | Nested MCP publication guide and companion skill; official Codex/Claude docs cited there |
| Scripts or harnesses | What automated proof ran? | Complete Glass Drive UI suite: 282 passed; focused generated-prompt regression passed |
| Local/external prerequisite state | Were clients and identity provider usable? | Codex and GlassHive OAuth usable; Claude MCP transport usable; Claude account auth expired |
| Logs | Did the requested tool actually run? | Sanitized CLI ledger showed one start/completion pair per successful action |
| DB/state/persistence | Did state persist? | Browser refresh showed the renamed value and, after restoration, the original value |
| Generated/shipped artifact | Was the changed artifact installed? | Source and staged release exist; activation had not begun, so this row remains blocked |
| Real user path | Was this used like a user? | Real Edge Connections/Workspaces plus real fresh Codex tasks |
| Visual/UX comparison | Did the visible state match MCP? | Yes for rename and restore after refresh |
| Not run / blocked | What remains? | Exact candidate copy and current Claude tool call |

## User-Grade Evidence

- Surface exercised: hosted Edge GlassHive, Codex CLI, Claude Code CLI.
- Real user path: copied the deployment instruction, replaced duplicate Codex registrations with one
  exact registration, completed the native scoped login, started a fresh task, listed workspaces,
  renamed one synthetic workspace, refreshed Edge, restored the name, and refreshed again.
- Visible outcome: Codex returned the same two named workspaces shown in Edge; rename and restore were
  both visible after reload.
- Expanded/detail state: Workspaces cards remained closed/paused; no worker run or compute was started.
- Persistence/reload result: both update and restoration survived browser refresh.
- Local/external prerequisite state: the local Codex launcher initially referenced a missing optional
  companion host even though the signed application already shipped it. A local alias to that same
  vendor binary restored normal direct MCP execution. Claude's separate account session remained expired.
- Evidence retrieval classification: Claude was `auth/config missing`; Codex/GlassHive was successful.
- Backend/log/DB confirmation: successful actions each produced one MCP start/completion pair; browser
  persistence corroborated the stored state. Raw logs and identifiers are not published.
- Final model/runtime wording check: the successful Codex task returned only the requested count/names
  or success result. It did not enumerate the tool catalog.
- Substitution check: automated tests and source inspection support, but do not replace, the real
  Codex and Edge path. Candidate install and current Claude remain explicitly blocked.

## Automated Evidence

```text
Glass Drive UI suite: 282 passed
Generated connect prompt regression: passed
JavaScript syntax checks: passed
Nested and parent diff checks: passed
```

## Findings

- Defect fixed in candidate: fresh `codex mcp add` saves the server and then starts a known unscoped
  OAuth detour. The generated instruction now tells Codex to interrupt only that automatic attempt
  after `Added`, then open the exact scoped native login once.
- Local client prerequisite repaired: the Codex launcher lacked a companion-host alias to the binary
  already shipped by the same signed application.
- Claude limitation: MCP transport was connected, but the Claude account session needed a new login;
  no Claude tool success is claimed for this run.
- Environment issue: Azure's command agent stayed pending before candidate activation; the accepted
  canary remained healthy and was not mislabeled as the candidate.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
