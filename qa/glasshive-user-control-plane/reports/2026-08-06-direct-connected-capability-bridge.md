# Direct Connected-Capability Bridge QA — 2026-08-06

Last source-verification run: `2026-08-06 10:20 EDT (UTC-04:00, America/Toronto)`.

## Summary

- Result: PARTIAL.
- Source under test: isolated uncommitted public-source candidate.
- Runtime/artifact under test: source test environments; no installed or hosted artifact.
- Environment: neutral synthetic identities and connected-capability fixtures.

## Scope Run

| Case area | Result | Evidence | Notes |
| --- | --- | --- | --- |
| Direct capability lookup, mint, use, and revoke | PASS | Focused GlassHive and LibreChat suites below | Synthetic source-level path. |
| Shared OIDC and operator ownership mappings | PASS | Two-user isolation and backfill tests | No email or provider-label fallback. |
| Real connected account through browser and MCP client | BLOCKED | Not run | Requires approved hosted identity/provider configuration. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: direct user-scoped connected capabilities for Glass Drive and MCP work.
- Requirement: requirement 55 connection ownership and least-privilege bridge.
- Use case: a user starts work and the worker receives a fresh, narrow capability grant without copying provider credentials.
- QA case: GHUCP-014 through GHUCP-018 and GHUCP-026.
- Expected result: readiness is owner scoped, grants remain memory-only, and terminal boundaries revoke them.
- Actual evidence: source-level GlassHive and LibreChat bridge tests passed as recorded below.
- Remaining gap or fix: real browser consent, two real users, external MCP clients, and hosted revoke/failure recovery.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Requirement and use case | Requirement 55 and connected-capability GHUCP cases. |
| Code owning path | GlassHive capability broker/runtime wrapper and LibreChat user-scoped capability issuer. |
| Docs and nested docs/repos | Requirement 55 plus nested GlassHive and LibreChat integration source. |
| Scripts or harnesses | Focused suites and compile/syntax checks listed below. |
| Local/external prerequisite state | Synthetic identity and provider readiness only; external consent was absent. |
| Logs | Sanitized test summaries; no live provider logs. |
| DB/state/persistence | Tests assert opaque owner mappings and absence of credential persistence. |
| Generated/shipped artifact | Compiler split environments were inspected; no installed artifact. |
| Real user path | BLOCKED for hosted browser consent and external Codex/Claude MCP assignment. |
| Visual/UX comparison | BLOCKED because this run did not exercise the real hosted UI. |
| Not run / blocked | Hosted OIDC, provider consent/revoke, client OAuth, installed worker, and failure classification. |

## User-Grade Evidence

- Surface exercised: local API/MCP integration harness; hosted browser and external clients were BLOCKED.
- Real user path: synthetic direct mission and MCP assignment crossed the same grant boundary; no real provider login was attempted.
- Visible outcome: no user-visible hosted outcome was claimed; source responses exposed only redacted readiness.
- Expanded/detail state: grant binding, replay rejection, redaction, in-memory projection, and revoke assertions were inspected.
- Persistence/reload result: stored worker state remained unchanged and no literal grant persisted in synthetic state.
- Backend/log/DB confirmation: focused assertions confirmed two-owner isolation, nonce consumption, owner mapping, and terminal revoke.
- Final model/runtime wording check: unavailable Claude API-key and consumer-subscription paths stayed explicitly unavailable.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting evidence, not substitutes for any required visible-UI, detail-state, persistence, or wording step.

## Automated Evidence

- The focused GlassHive, LibreChat, compiler, Glass Drive, compilation, and syntax suites passed with the exact counts recorded below.
- The one broader supervisor timing failure was reproduced outside this feature path and remains disclosed rather than suppressed.

## Findings

- Defects: direct work previously lacked one shared, owner-scoped runtime wrapper for current LibreChat capabilities.
- Regressions: none found in the focused bridge suites.
- Environment issues: real identity and provider prerequisites were not provisioned.
- Residual risks: every hosted and external-client gate listed below remains open.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, channel chat IDs, database object ids, or raw provider request/response ids.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, database exports, application-support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.

## Outcome

Source-level acceptance is **PARTIAL**. Direct Glass Drive missions and authenticated GlassHive MCP
assignments now share one runtime wrapper that asks LibreChat for current user-scoped capability
readiness, mints a fresh worker/run grant in memory, and revokes it at the terminal boundary. No
provider-specific consent UI or second OAuth/token store was added.

## Automated evidence run

- GlassHive capability broker, inference broker, and mission account suites: 33 passed.
- GlassHive direct bridge focused suite: 5 passed, covering shared-OIDC and operator mappings,
  two-user isolation, fresh grants for UI-labelled and MCP-labelled runs, redacted readiness,
  in-memory projection, and revoke.
- LibreChat capability bootstrap, issuer-auth, and shared-OIDC identity suites: 46 passed.
- LibreChat direct issuer route suite: 7 passed, including opaque-principal resolution, first-class
  unmapped state before re-login backfill, and replay.
- LibreChat authenticated OpenID strategy suite: 40 passed, including new-user principal creation,
  existing-user re-login backfill, and missing-claim refusal without email fallback.
- GlassHive compiler/split-environment suite: 58 passed, including explicit token audiences,
  full delegated scopes, allowlisted pre-registered clients, canonical public Codex resource,
  both fixed callback ports, incomplete/mismatched rejection, non-empty validated OIDC role maps,
  distinct ownership/token tenants, safe logout URI projection, and service-environment placement.
- Glass Drive auth/server suite: 173 passed. It covers immutable issuer-plus-subject identity,
  registration closed/open behavior, bounded callback failures, replay, redaction, CSRF-protected
  local/provider logout, deep-link recovery, current-user UI, and Connect AI. Connect AI coverage
  includes the exact Codex and Claude commands,
  known Codex callback-hash fixture, both displayed redirect URIs, missing registration, verifier
  audience/scope/client-allowlist drift, canonical resource drift, and truthful unavailable Claude
  API-key/consumer-subscription paths.
- Local client inspection confirmed Codex `0.147.0-alpha.1.2` accepts
  both `mcp_oauth_callback_port` and an exact loopback `mcp_oauth_callback_url` through
  `codex mcp login -c ...`; a non-existent synthetic server name reached the expected server lookup
  error, proving the generated options parse without changing a real client registration.
- Candidate-pin correction: the supported runtime remains Codex `0.146.1`. A later repeat against
  `0.146.1` confirmed the same callback port and exact callback URL options; the alpha version above
  is historical inspection evidence, not a release recommendation or shipped pin.
- The combined focused LibreChat OpenID, direct-issuer, shared-identity, and direct-route run passed
  69 tests after fork-marker formatting.
- Python compilation and JavaScript syntax checks passed for changed bridge files.
- The broader profile-runtime suite passed 212 cases and failed one pre-existing host-supervisor
  timing case whose child did not start inside its 0.5-second fixture deadline. The same failure
  reproduced in isolation and does not traverse the capability bridge.

## Security and compatibility evidence

- Shared-OIDC mode derives the same unique opaque issuer-plus-subject principal during authenticated
  LibreChat login and GlassHive login, so new users need no per-user config. The compiler requires
  exact issuer parity and an explicit principal claim; missing claims never fall back to email.
  Existing users backfill on their next LibreChat sign-in. Operator-reviewed static mapping remains
  available for deployments without a shared issuer; an unmapped owner fails before grant issue.
- Hosted multi-user compilation rejects an empty or invalid OIDC role map. The Entra contract
  requires `Assignment required? = Yes` (or a separately reviewed and tested equivalent gate) on
  both web and API enterprise applications; `allow_registration` is enrollment after IdP admission,
  not authorization for any tenant user.
- S2S assertions are tenant/user/action scoped, expire within 60 seconds, and are bound to worker,
  run, and execution mode for grant/revoke. Every nonce is consumed through the shared replay cache
  before user/grant work; replay or production cache outage fails closed.
- Readiness returns only connection id, label, kind, adapter, and ready/action-required state.
- Provider credentials remain in LibreChat. The runtime overlays the broker bundle on a copied
  worker object in memory; the stored worker bundle is unchanged. Literal workspace MCP config uses
  an environment-variable reference, not the grant.
- Broker configuration is additive. With no direct issuer configuration, existing runtimes and the
  prior empty/local Connections behavior remain unchanged.
- The public HTTPS MCP URL is compiled as the RFC 8707 client resource while access-token `aud`
  values are explicit independent verifier inputs. A Codex resource override that differs from the
  public URL fails compilation, and manually drifted gateway environment cannot produce a copyable
  command without token audiences, scopes, and an allowlisted client id.
- Connect AI returns exact fixed redirect URIs for identity-provider registration. Codex uses its
  deterministic URL-derived callback suffix; Claude Code uses its fixed localhost callback. The
  companion skill consumes only deployment-generated commands and stops on `action_required`.
- LibreChat's existing OpenAI Responses broker remains the only fixed API-key inference adapter.
  GlassHive explicitly reports Claude API-key support as
  `fixed_anthropic_broker_not_implemented`, never copies the key, and does not advertise the
  experimental hosted consumer-auth switch as a supported subscription path.
- Generated split environments place the direct issuer URL, signer secret, tenant, identity mode,
  owner mappings, and timeout only in `glasshive-runtime.env`; the matching verifier secret and
  shared-OIDC issuer/claim only in `librechat.env`. Neither reaches `glasshive-gateway.env`, and the
  internal assertion private key remains excluded from the worker runtime. MCP token audiences and
  verifier policy reach the gateway and MCP runtime; pre-registered client ids and callback settings
  are gateway-only and do not enter worker runtime state.

## Not run / live-only gates

- Hosted OIDC login/re-login with two real browser users, verified opaque-principal backfill, and
  two-user isolation through readiness and grant use.
- Real connected-account consent/reconnect through the existing LibreChat UI.
- Real direct Glass Drive create, open/resume, and authenticated Codex/Claude MCP assignment using a
  connected service, followed by DB/log/workspace negative scans.
- Real Entra API registration with its delegated scope/token audience, exact displayed Codex and
  Claude redirects, then copy/paste login from fresh client profiles. No command has been presented
  as live-ready before this identity-provider configuration exists.
- A fixed Anthropic Messages broker adapter (or an independently approved native Claude hosted
  subscription route). The current source truthfully leaves both unavailable instead of exposing a
  secret or consumer OAuth experiment.
- Live provider revoke, timeout, rate limit, successful-empty, bounded long-run renewal, and harmless
  confirmed-write recovery.
- Installed artifact, edge routing, process environment, restart, rollback, and hosted deployment.

The bridge is not a live-environment completion claim until those gates pass.
