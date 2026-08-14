# Codex Reconnect Scope RCA — 2026-08-14

## Result

**PARTIAL pending candidate deployment.** The user-visible reconnect failure is reproduced and the
client/server mismatch is understood. Current Codex completed ordinary native login in the intended
existing Edge profile, without a per-login scope override, after its GlassHive server config persisted
the deployment's exact scope. One `workspace_list` call then succeeded.

## Root cause and smallest fix

- Entra rejected the request because Codex paired the canonical GlassHive resource with generic
  OpenID scopes, producing `AADSTS9010010 invalid_target`.
- GlassHive now publishes the exact operation scope in protected-resource metadata and its initial
  Bearer challenge, matching the MCP authorization contract.
- Current Codex can still ignore those discovered scopes during Reconnect. Its supported persistent
  MCP `scopes` setting has precedence and produces the correct authorization request.
- The candidate's one copied Codex instruction therefore adds or updates the native MCP config once,
  including the exact persistent scope, then invokes native login. It does not construct OAuth URLs,
  inspect tokens, run a callback helper, or enumerate the MCP tool catalog.

## Evidence

| Surface | Result |
| --- | --- |
| Reproduction | Generic OpenID/no-scope requests with the canonical resource failed visibly with `invalid_target` |
| Native client | Codex `0.148.0-alpha.9` used the exact configured resource and scope, then reported authentication complete |
| Browser | The native callback completed in the already-open intended Edge profile |
| MCP | One direct `workspace_list` call succeeded; no catalog narration was used |
| Source tests | Full Glass Drive UI suite plus focused MCP OAuth/server/skill suites passed |
| Candidate install | Pending; copied setup, restart persistence, and final CRUD still require the deployed build |

## Acceptance still required

Deploy the exact nested component and parent pin, hard-refresh Connections, copy the new Automatic
instruction, reauthenticate through the intended Edge profile, restart the client, and perform a
minimal create/read/update/cleanup flow with browser refresh and backend corroboration. Claude Code
and the wider wrong-audience/client/tenant/revocation matrix remain separate follow-up coverage.

## Public safety

No tokens, authorization URLs, callback state, personal identifiers, private hostnames, workspace
identifiers, or customer data are included in this report.
