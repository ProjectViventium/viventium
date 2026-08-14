# Codex Reconnect Scope RCA — 2026-08-14

## Result

**PASS for the reported Codex reconnect incident.** The accepted hosted build now publishes and copies
the durable native Codex configuration. Ordinary login completed in the already-open AITP Edge profile
without a per-login scope override, survived the release restart, and a fresh Codex process completed
the basic request with one MCP call.

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
| Browser | Native callback completed in the already-open AITP Edge profile; Workspaces retained the renamed result and expanded delivery after hard refresh |
| MCP | A fresh process made exactly one successful `workspace_list` call, with no shell/setup/catalog call |
| CRUD | One synthetic workspace launched, completed, exposed its requested artifact, renamed, refreshed, and terminated with compute released |
| Source tests | Full Glass Drive UI suite plus focused MCP OAuth/server/skill suites passed |
| Installed build | Exact parent/component provenance, canary health, stable-edge invariant, explicit browser acceptance, and commit passed |

## Remaining coverage

Current Claude Code and the wider wrong-audience/client/tenant/key/revocation matrix remain separate
follow-up coverage; they are not needed to close this Codex-specific reconnect incident.

## Public safety

No tokens, authorization URLs, callback state, personal identifiers, private hostnames, workspace
identifiers, or customer data are included in this report.
