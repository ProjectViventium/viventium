# GlassHive Native Microsoft Workspace Reuse

Date: **2026-08-16**
Result: **PASS for the tested personal-Codex read/reuse path; broader completion remains PARTIAL**

## Summary

The installed personal-Codex path passed: one short request from a fresh projectless Codex task
reused one private favorite GlassHive workspace, returned real read-only Outlook and SharePoint
metadata through the worker's official native connections, created no duplicate, released compute,
survived an Edge refresh, and remained resumable. The wider cross-client and destructive-lifecycle
matrix remains PARTIAL and is listed under Findings.

## Scope Run

- Exact parent source: `71f4057971dc219ece6fd4235cf7ba538d404262`
- Exact GlassHive source: `b0dc8321554a188be170c5b38b3e77e1a34a3b79`
- Installed release: `glasshive-20260816-workspace-control-room-28`
- Real happy path: fresh external Codex -> hosted OAuth MCP -> existing favorite personal workspace ->
  Outlook and SharePoint native reads -> result -> compute release -> Edge refresh.
- Real unhappy path: a missing explicit alias failed before mutation; aggregate project, worker, and
  run counts were unchanged.
- Not run: personal Claude worker, confirmed write, revoke/renew/reconnect/outage/two-user matrix,
  automatic clock-fired schedule reuse, real Library package use, and clean install/full restore.

## Traceability

| Feature | Requirement | Use case | QA case | Expected result | Actual evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| One-prompt private favorite workspace with native connected-service reuse | `GH-UCP-004`, `005`, `007`, `011`, `018` | `GHUCP-UC-012` | `GHUCP-034` | One simple request reuses one owner-scoped workspace, uses the selected personal account and native connections, and remains reusable without duplicated state | Fresh Codex used one `workspace_launch` plus one `workspace_wait`; browser, MCP, runtime, and catalog evidence agreed on the same favorite worker and a completed read-only result | Personal Claude and full connection-lifecycle/two-owner matrix |
| Exact fail-closed workspace reuse | `GH-UCP-007`, `018` | `GHUCP-UC-003`, `009` | `GHUCP-011`, `012`, `034` | Missing, closed, ambiguous, or incompatible targets never create a replacement workspace | Automated alias/state/kind/mode regressions passed; installed missing-alias check left counts unchanged | Large-catalog and two-owner installed matrix |

## Full-View Evidence Checklist

- [x] Owning MCP resolver, catalog, lifecycle-state, and downstream alias lookup inspected.
- [x] Parent component pin, staged release manifest, activation provenance, and installed runtime
  health agreed on the exact source pair.
- [x] Fresh external-client transcript showed one goal call and one bounded wait, with no
  client-side catalog/discovery call.
- [x] Real worker returned bounded metadata from both official native connections without a write.
- [x] The intended signed-in Edge profile showed the same favorite workspace, ready personal route,
  completed delivery, and
  paused/released compute before and after refresh.
- [x] Runtime detail showed `resumed_by_alias`, Completed with empty error, no active run, and no
  live sandbox; aggregate runtime metrics were idle.
- [x] Public docs and evidence exclude private identities, hosts, tenant/account/worker/run ids,
  message/file values, tokens, cookies, callback values, and screenshots.

## User-Grade Evidence

- Surface exercised: Fresh projectless Codex task, hosted GlassHive MCP, personal Codex worker, and installed GlassHive Workspaces view in the intended signed-in Edge profile.
- Real user path: A short plain request asked GlassHive to reuse one favorite workspace and read one Outlook subject plus one SharePoint file or site name without changing anything.
- Visible outcome: Codex returned both requested metadata values; the Workspaces card showed Completed, Favorite, delivery ready, and the personal account ready.
- Expanded/detail state: The live worker view showed the same worker alias, a terminal Completed run, empty error text, `resumed_by_alias`, no active run, and no live sandbox.
- Persistence/reload result: Refresh returned to Workspaces and retained the same favorite card, personal route, completed delivery, and resumable paused compute with no active duplicate or reconnect banner.
- Backend/log/DB confirmation: The run completed with output and no failure class; aggregate metrics reported zero queued/active runs and zero pending/delivering callbacks; the earlier DB correlation returned active personal leases to zero.
- Final model/runtime wording check: The fresh client returned only the requested two values; worker/runtime evidence reported no change, no blocker, and no fabricated broker result.

## Automated Evidence

- `runtime_phase1/tests/test_mcp_server.py`: 158 tests collected and passed in the combined run.
- `runtime_phase1/tests/test_public_compatibility_contract.py`: 13 tests collected and passed in
  the same combined run.
- Dedicated regressions prove explicit alias precedence, all canonical closed states, exact
  scoped/unscoped aliases, legacy alias reuse, missing/ambiguous no-mutation behavior, and
  execution-mode mismatch no-creation behavior.
- Independent Claude review reproduced the escaped failures, verified the fixes, re-ran the prior
  full suite, validated the release-28 helper hashes/payloads/actions, and returned GO with no P0-P2.
- Release stage, preflight, activation, and explicit acceptance each passed; stable ingress stayed
  unchanged throughout the canary transaction.

## Findings

- PASS: installed personal-Codex native Outlook/SharePoint read-and-reuse path.
- PASS: explicit `workspace_alias` wins over a colliding description title.
- PASS: `terminating`, `termination_failed`, and `terminated` workspaces are excluded through one
  shared lifecycle constant.
- PASS: legacy aliases remain reusable, while missing/ambiguous/incompatible reuse fails without a
  project, worker, or run creation.
- PARTIAL: personal Claude worker; harmless confirmed write; revoke, renewal, reconnect/forget,
  outage/rate-limit, and two-user isolation.
- PARTIAL: automatic clock-fired scheduling with the native connection, a real Library package used
  by a worker, and clean public install/full upgrade-restore acceptance.

## Public-Safety Review

- [x] No secret, token, cookie, callback, private URL, account id, owner id, worker/run id, email,
  personal name, message subject, file name, or tenant value is recorded.
- [x] No local absolute path, host name, IP address, private screenshot, or customer-specific example
  is recorded.
- [x] The public report distinguishes official worker-native authorization from GlassHive-owned
  broker authorization and does not imply that GlassHive stores Microsoft OAuth credentials.
- [x] Open gaps are stated explicitly; real personal-Codex proof is not generalized to Claude,
  writes, two users, scheduling, Library, or clean install/restore.

Substitution check: source inspection, unit tests, model review, and backend diagnostics support but
do not replace the fresh external-client run, real worker-connected-service result, installed Edge
view, refresh/persistence check, or explicit canary acceptance.
