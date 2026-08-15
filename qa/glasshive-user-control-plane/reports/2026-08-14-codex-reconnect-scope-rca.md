# Codex Reconnect Scope RCA — 2026-08-14

## Result

**PASS for the live Codex client repair; PARTIAL for product rollout.** The local native config now
persists renewable Entra authorization, ordinary login completed in the already-open AITP Edge
profile, the GlassHive MCP was restarted in place, the reconnect banner cleared, and the current
Codex process completed a real `workspace_list` call. The product source and regression are fixed;
the generated setup still needs deployment to the hosted environment.

## Root cause and smallest fix

- The original successful login requested the canonical GlassHive API scope but omitted
  `offline_access`. Entra therefore issued no refresh token; when the roughly hour-lived access token
  expired, Codex correctly became unauthenticated and the reconnect banner was real.
- The already-running desktop process still held the older MCP setup. Its Reconnect attempt paired
  the canonical GlassHive resource with stale generic scopes, producing `AADSTS9010010 invalid_target`.
- GlassHive now publishes the exact operation scope in protected-resource metadata and its initial
  Bearer challenge, matching the MCP authorization contract.
- Current Codex can still ignore those discovered scopes during Reconnect. Its persistent MCP
  `scopes` setting now contains the canonical API scope plus `offline_access`; the first produces the
  correct resource authorization and the second asks Entra for renewable authorization.
- The candidate's one copied Codex instruction therefore adds or updates the native MCP config once,
  restarts Codex/ChatGPT once so the process reloads it, then invokes native login. It does not
  construct OAuth URLs, inspect tokens, run a callback helper, or enumerate the MCP tool catalog.

## Evidence

| Surface | Result |
| --- | --- |
| Reproduction | Generic OpenID/no-scope requests with the canonical resource failed visibly with `invalid_target` |
| Reproduction | Generic scopes with the canonical resource failed visibly with `invalid_target`; the client later reported `Not logged in` after its non-renewable token expired |
| Native client | Codex persisted the canonical API scope plus `offline_access`, then reported authentication complete |
| Browser | Native callback completed in the already-open AITP Edge profile; no other profile was used |
| Desktop reload | Only the GlassHive MCP was toggled off/on; it returned enabled with OAuth and the orange reconnect banner stayed absent |
| MCP | The current Codex process made one actual successful `workspace_list` call and received one item; no shell fallback or guessed count was accepted |
| Source tests | Focused generated-config/client-contract tests and the complete 223-test Glass Drive server suite passed after the regression first failed on missing `offline_access` |
| Installed build | Pending deployment of the generated renewable config/instruction |

## Remaining coverage

Hosted generated-setup deployment, current Claude Code, and the wider wrong-audience/client/tenant/
key/revocation matrix remain separate follow-up coverage. The previous plain `0` answer in the old
task is not evidence because no MCP call occurred; only the verified post-reload tool call counts.

## Public safety

No tokens, authorization URLs, callback state, personal identifiers, private hostnames, workspace
identifiers, or customer data are included in this report.
