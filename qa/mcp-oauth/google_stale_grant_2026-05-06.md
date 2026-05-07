# Google MCP OAuth Stale Grant QA - 2026-05-06

## Scope

Validate the local Google Workspace MCP behavior when stored OAuth state exists but the upstream
Google grant is expired or revoked.

## Sanitized Evidence

- The affected local user had stored Google MCP client and refresh token records.
- No current usable Google MCP access-token record existed for that user.
- Durable Google MCP proxy storage existed on disk, proving that persistence was present.
- Runtime logs showed `invalid_token` followed by refresh failure with `invalid_grant`.

No token values, private emails, message contents, or account data are recorded in this QA artifact.

## Root Cause

This was not a missing-persistence bug. The persisted grant was no longer refreshable upstream.
When Google returns `invalid_grant`, retrying the same stored refresh state will keep reopening
OAuth and can make the connection look like it is not persisting.

## Product Fix Under Test

- Classify terminal OAuth refresh failures such as `invalid_grant`, `unauthorized_client`,
  `invalid_client`, `consent_required`, `interaction_required`, and `login_required` as
  non-refreshable grant failures.
- Clear only the exact affected user/server MCP OAuth token set using AND semantics across
  `userId`, `type`, and `identifier`.
- Preserve stored OAuth state on transient refresh failures such as network errors.
- Let the next attempt start a clean OAuth reconnect with clear logs.

## Automated Checks

| Check | Result |
| --- | --- |
| `packages/data-schemas npx jest src/methods/token.spec.ts --runInBand` | 42 passed |
| `packages/api npx jest src/mcp/__tests__/tokens.test.ts src/mcp/__tests__/MCPConnectionFactory.test.ts --runInBand --coverage=false` | 25 passed |
| `LibreChat npm run build:api` | pass |
| `LibreChat git diff --check` | pass |

The terminal OAuth code fallback matcher is bounded, so a transient error that merely contains a
terminal-code substring inside a longer token, such as a filename, does not clear OAuth state.

## Acceptance

Pass for product logic and regression coverage.

Fresh Google browser consent is still required after a real revoked grant. That is the correct user
journey after upstream revocation and is distinct from a local-session persistence failure.
