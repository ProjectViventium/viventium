# Hosted Local-Password Canary — 2026-08-09

## Summary

- Result: **PASS for the optional local-password browser factor; PARTIAL for the complete GlassHive
  user control plane**.
- Environment: additive hosted canary listener with a single isolated, administrator-provisioned
  synthetic deployment principal. The stable listener and LibreChat were observation-only.
- Installed provenance: parent `4d021f0258f92bdbc350c41655651de9b6c1b1ef`, GlassHive
  `35c82be4275f72ec3019e19580003d8947cd73d5`, release
  `release-20260809-maisydev-local-auth-1`.
- Identity boundary: no customer, client, or unrelated browser identity was used.
- Primary remaining defect: the deployment-managed Codex fallback reached its provider boundary but
  returned upstream `401 Unauthorized`; no personal provider account was substituted.

## Scope Run

| Case ID | Result | Actual evidence | Remaining gap |
| --- | --- | --- | --- |
| `GHUCP-002` | PARTIAL | Real Chrome local login, refresh, UI-service restart, logout, and reauthentication passed | Organization/IdP path was not repeated |
| `GHUCP-003` | PARTIAL | Unknown-account failure was generic; missing login CSRF returned `403`; signup/reset returned `404`; flag-off revoked the session | Full live throttle/rotation and IdP negative matrix |
| `GHUCP-011`–`012` | PARTIAL | One synthetic workspace was created and rediscovered after restart and the flag-off/on drill | Provider execution failed upstream; compute/profile continuity and two-user proof remain open |
| `GHUCP-026` | PARTIAL | Merged source, parent pin, sealed release health, and visible installed feature reported one exact build | Fresh public bootstrap/install |
| `GHUCP-027` | PARTIAL | UI restart plus flag-off/session-revocation/re-enable drill passed | Full install/upgrade/database restore/preceding-binary rollback |
| `GHUCP-030` | PARTIAL | Real browser login passed the edge; missing CSRF failed; stable listener behavior remained unchanged | Spoof probes, negative runtime reachability, and real MCP clients |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: optional administrator-provisioned GlassHive local-password factor.
- Requirement: `GH-UCP-002`, `GH-UCP-007`, and `GH-UCP-017` in requirement 55.
- Use case: enter GlassHive without public signup, retain one immutable owner/session, create and
  rediscover private work, and roll the factor off without weakening organization login.
- QA cases: `GHUCP-002`, `003`, `011`, `012`, `026`, `027`, and `030`.
- Expected result: local credentials remain gateway-private; login is CSRF-protected and
  non-enumerating; local sessions are independently revocable; stable services remain untouched.
- Actual evidence: real Chrome actions, real canary restart/toggle, visible workspace state,
  candidate database counts, installed release health, and stable-listener probes.
- Remaining gap: personal-provider and MCP OAuth consent paths, deployment Codex credential repair,
  hosted two-user isolation, schedule delivery, full stable cutover, and clean-install continuity.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Requirement and QA source | Requirement 55 and the updated `cases.md` / `coverage.md` entries above |
| Owning code/artifact | Exact merged parent and GlassHive revisions reported by the installed canary `/health` response |
| Generated configuration | `/auth/config` reported local login enabled, local signup disabled, and principal enrollment disabled after rollback recovery |
| Real browser | Chrome showed both organization and local choices, accepted the synthetic local credential, retained the session across refresh/restart, and logged out cleanly |
| Expanded/detail state | Connections showed zero personal worker accounts; Workspaces showed one retained failed workspace with a truthful deployment-account fallback error |
| Persistence | The same local principal and retained workspace remained visible after UI restart and the flag-off/on drill |
| DB/state | One credential with Argon2id PHC, separate local-session rows, non-locked account state, and HMAC-shaped source keys |
| Services/edge | All three next services active; missing login CSRF returned `403`; signup/reset routes returned `404`; stable listener retained its existing `302` behavior |
| Browser logs | No console warnings or errors during the accepted local-auth flow |
| Secret lifecycle | The one-time provisioning envelope private key was securely removed after the last administrator operation |
| Not run | Organization/IdP login, personal Codex/Claude, real MCP clients, two-user isolation, schedule fire, stable cutover, and clean install/restore |

## User-Grade Evidence

- Surface exercised: real Chrome against the installed additive Glass Drive HTTPS canary.
- Real user path: opened login, visually inspected both choices, signed in locally, refreshed,
  opened Workspaces and Connections, created one synthetic workspace, logged out, exercised a
  generic failure, signed back in, restarted the UI service, disabled/re-enabled the factor, and
  reopened the same catalog.
- Visible outcome: local login entered the correct private catalog; logout and failure copy were
  clear; flag-off removed only the local form while organization sign-in remained; re-enable restored
  the form and credential.
- Expanded/detail state: Connections truthfully showed no personal worker account; the retained
  workspace status exposed the deployment-managed Codex `401` instead of claiming completion.
- Persistence/reload result: the session survived refresh and UI restart; flag-off revoked it; after
  re-enable the same principal saw the same retained workspace.
- Local/external prerequisite state: the auth gateway and all next services were healthy; the
  deployment-managed Codex credential was not healthy; no unrelated personal account was used as a
  fallback.
- Backend/log/DB confirmation: installed health matched the merged source pair; the candidate DB had
  one Argon2id credential, independent session rows, HMAC-shaped source keys, and no account lock;
  stable-listener probes remained unchanged.
- Final model/runtime wording check: the UI reported the provider failure as `failed` / needs
  attention and identified deployment-account fallback. It did not claim the file task completed.
- Substitution check: source/tests, API/health, DB rows, and service probes support the real browser
  run; they do not substitute for the unrun IdP, personal-provider, MCP, two-user, scheduler, or
  stable-cutover paths, which remain explicitly PARTIAL or open.

## Automated Evidence

The exact local-password candidate had already passed the complete affected nested auth/admin/server
suite (240 tests) and the parent compiler/rollout suites before merge. This report changed only QA
documentation. The owning public QA, manifest, and boundary selection passed **41/41** after the
report was added; `git diff --check` also passed.

## Findings

- Local-password browser factor: accepted on the additive canary.
- Rollback contract: accepted for flag-off local-session revocation and re-enable recovery.
- Privacy boundary: accepted for Argon2id-only verifier storage, HMAC-shaped source identifiers, no
  public signup/reset, and no personal-account substitution.
- Provider execution: open defect/precondition. The deployment-managed Codex fallback returned
  upstream `401 Unauthorized`; provider mission success is not claimed.
- Chrome blocked the signed `/r/...` redirect as a client-side navigation, so the workspace was
  inspected through the authenticated Workspaces catalog instead. The durable workspace creation and
  truthful failure state were still visible; direct signed-watch acceptance remains open.

## Public-Safety Review

- [x] No secrets, passwords, tokens, cookies, private keys, or credential-bearing commands.
- [x] No account locators, personal emails, customer/client names, unrelated identities, or private
  browser profile names.
- [x] No private hostnames, machine names, local absolute paths, state paths, screenshots, stack
  traces, or raw database/log exports.
- [x] Synthetic prompts and sanitized counts/revisions only.
- [x] Stable-listener and LibreChat behavior are reported without publishing deployment-specific
  configuration.
