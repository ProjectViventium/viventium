<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-30 Copied-QA Broker-First Live Browser QA

## Scope

Live browser QA for the GlassHive MCP capability broker using a copied non-owner QA account with locally reseeded connected-account credentials. Public report is sanitized; raw transcript/screenshot evidence stays in the private user-data folder.

## Result

- Status: PASS
- QA user hash: f9ffb8f8a012
- Prompt hash: 91a1a4969bbecf53
- Main-agent connected-account handoff edge absent: yes
- Google Workspace status: connected
- MS365 status: connected
- GlassHive worker MCP status nuance: the local non-OAuth `glasshive-workers-projects` status row can
  appear disconnected in the generic status endpoint, but the actual GlassHive tool call succeeded.
- Used GlassHive worker/workspace tool: yes
- Used retired Connected Accounts handoff: no
- Used browser/computer fallback: no
- Forced download/local-worker artifact: no
- `workspace_launch.success_criteria` behavior:
  - post-schema run: omitted by host; GlassHive supplied the minimal internal completion check.
  - final-code rerun: supplied by host only as a direct restatement of the user's explicit read-only/no-modification constraint.
- `workspace_launch.connected_account_content_intent` behavior:
  - post-schema run: present as a compatibility hint.
  - final-code rerun: absent; broker access still came from the structural broker bootstrap/grant path.
- Follow-up `wait` path:
  - post-schema run: `workspace_wait` executed and callback arrived.
  - final-code rerun: worker callback arrived before follow-up; follow-up `wait` returned a short status text with no error, clarification, browser fallback, or forced artifact.
- Browser console errors: 0 in the post-schema Playwright run.
- Browser failed requests: 0 in the post-schema Playwright run.
- Private evidence: `<viventium-private-user>/qa/glasshive-mcp-capability-broker/live-browser-broker-first-2026-05-30-post-schema/live-browser-broker-first-evidence.json`
- Final-code rerun private evidence: `<viventium-private-user>/qa/glasshive-mcp-capability-broker/live-browser-broker-first-2026-05-30T22-36-15-580Z-final-code/live-browser-broker-first-evidence.json`

## Tool Evidence

| Message | Tool names |
| --- | --- |
| 1 assistant | `workspace_launch_mcp_glasshive-workers-projects` |
| 2 user | none |
| 3 assistant | `workspace_wait_mcp_glasshive-workers-projects` |
| 4 user | none |
| 5 callback assistant | none |

Final-code rerun tool shape:

| Message | Tool names |
| --- | --- |
| assistant | `workspace_launch_mcp_glasshive-workers-projects` |
| callback assistant | none |
| follow-up wait assistant | none; short status text after callback had already arrived |

## Runtime / Security Evidence

- Copied non-owner QA account was used; metadata-only token inspection showed Google Workspace and
  MS365 OAuth/client/refresh token rows plus model keys for the QA user before the run.
- Authenticated `/api/mcp/connection/status` returned `connected` for `google_workspace` and
  `ms-365`.
- Main agent retained zero handoff edges and zero direct Google/MS365/Gmail/Outlook tools after the
  run.
- Private helper logs showed three successful `glasshive-capability-broker` MCP tool invocations
  during the worker run window for the copied QA user, alongside Google Workspace and MS365
  connections. Public report records only invocation count/timestamps shape, not tool arguments,
  provider payloads, tokens, or inbox content.
- Final-code rerun helper logs showed four `glasshive-capability-broker` MCP tool invocations
  during the worker run window for the copied QA user. Public report stores only the count/minute
  shape.
- Worker home config contained one broker MCP entry:
  `glasshive-user-capabilities` -> `http://127.0.0.1:3180/api/viventium/glasshive/capabilities/mcp`
  with `bearer_token_env_var = "GLASSHIVE_CAPABILITY_BROKER_TOKEN"`.
- No provider refresh/access/client tokens were copied into the public report or into the worker MCP
  config inspected for this run.
- A short-lived host-signed broker grant bearer is intentionally materialized in the worker
  environment under `GLASSHIVE_CAPABILITY_BROKER_TOKEN`; it is scoped, time-bounded, and distinct
  from provider OAuth/client/refresh tokens.
- Worker runtime completed in read-only mode and the callback returned an inbox result shape; raw
  inbox content remains only in private evidence.
- Final-code rerun `workspace_launch` args had no execution-mode override, no provider tokens, no
  forced artifact instruction, and no browser/computer fallback instruction. The only
  `success_criteria` value was the user's explicit read-only/no-modification constraint.

## Automated Checks

- `runtime_phase1/.venv/bin/python -m pytest runtime_phase1/tests/test_mcp_server.py -q` PASS.
- `npm run test:ci -- --runInBand server/services/viventium/__tests__/GlassHiveCapabilityBroker.spec.js server/routes/viventium/__tests__/glasshiveCapabilities.spec.js` PASS.
- `npm run test:ci -- src/mcp.spec.ts` PASS.
- `node --check viventium_v0_4/LibreChat/scripts/viventium-provision-connected-accounts-agent.js` PASS.
- `git diff --check` PASS for the touched public docs/QA/provisioner files and the touched
  GlassHive MCP source/test files.

## Notes

- Public report omits raw assistant text and inbox content.
- PASS required GlassHive tool evidence, broker invocation evidence, no retired handoff, no
  browser/computer fallback, no forced artifact link, no clarification loop, and a non-error
  follow-up/wait outcome.
