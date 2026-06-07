<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-30 Structural Read Scope Local QA

## Scope

GlassHive + LibreChat broker only. Voice, speculative async, background-agent governance, STT,
cloud deploy, and live production config were intentionally out of scope.

## Requirement

Connected-account read capability for GlassHive workers must be brokered as real capability context
without relying on the host chat model to choose tools or flip an authorization flag. Provider
credentials stay inside LibreChat. The worker receives a short-lived broker grant, MCP config, and
instructions that let it choose the best path.

## Changes Validated

- LibreChat broker bootstrap now grants `content_read` from reviewed `viventiumGlassHive` policy on
  projected servers instead of requiring `connected_account_content_intent`.
- The reviewed read policy name is `require_broker_grant`; the older `require_explicit_intent`
  value remains a compatibility alias only.
- A host/model-provided intent flag cannot mint read scope when policy does not authorize content
  read.
- GlassHive MCP tool descriptions now describe `connected_account_content_intent` as a compatibility
  hint for missing-broker warnings, not an authorization switch.
- GlassHive MCP projection docs now state that read-only broker scope is structural and policy-owned.

## Automated Evidence

- `npm run test:ci -- --runInBand server/services/viventium/__tests__/GlassHiveCapabilityBroker.spec.js server/routes/viventium/__tests__/glasshiveCapabilities.spec.js`
  - PASS: 2 suites, 27 tests.
- `npm run test:ci -- src/mcp.spec.ts`
  - PASS: 1 suite, 2 tests.
- `runtime_phase1/.venv/bin/python -m pytest runtime_phase1/tests/test_mcp_server.py -q`
  - PASS.
- `runtime_phase1/.venv/bin/python -m pytest runtime_phase1/tests -q`
  - PASS.
- `frontends/glass-drive-ui/.venv/bin/python -m pytest frontends/glass-drive-ui/tests/test_server.py -q`
  - PASS.
- `git diff --check`, `git -C viventium_v0_4/LibreChat diff --check`,
  `git -C viventium_v0_4/GlassHive diff --check`
  - PASS.

## Local Surface Evidence

- `http://localhost:3190/` responded with HTTP 200 and redirected Playwright to `/login`.
- Playwright isolated browser profile was not authenticated, so no chat prompt was submitted.
- Current local LibreChat logs show connected-account auth blockers for provider MCP initialization,
  including Google Workspace `invalid_token` / authentication-required errors.

## Result

Code-level broker behavior is PASS for the structural authorization boundary:

- reviewed source-of-truth policy can grant read-only broker scope without a host-model intent flag
- worker-authored/self-asserted intent still cannot authorize content reads
- writes remain host-confirmed
- provider secrets are not projected to the worker bootstrap

Review-only Claude pass found the main design sound and recommended renaming the old
`require_explicit_intent` tier. That follow-up was applied as `require_broker_grant`, with the old
value retained only as a compatibility alias.

End-user connected-inbox browser QA is PARTIAL/BLOCKED in this pass because the available Playwright
profile is not logged in and the local provider auth state is degraded. The next user-level pass
should use an authenticated browser session with valid Google/MS365 connected accounts and verify:

1. no Gmail-vs-Outlook clarification for a generic inbox read
2. broker MCP appears in the worker bootstrap
3. read tools are attempted or exact auth/provider blockers are reported
4. no forced downloadable artifact for a simple chat-answer task
5. visible final answer matches worker/tool evidence
