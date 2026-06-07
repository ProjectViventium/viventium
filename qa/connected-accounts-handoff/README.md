# Connected Accounts Handoff QA

## Scope

Historical evidence only. The dedicated **Connected Accounts** hand-off agent was a measured speed
experiment, but it is retired for the supported GlassHive broker-first design. Current connected
Google Workspace / Microsoft 365 work should go through GlassHive workers with the
`glasshive-user-capabilities` broker; the main agent must not recreate a LibreChat hand-off edge that
lets an in-process specialist choose provider tools instead of the worker.

This folder remains as historical comparison data for speed/quality and for the Responses-API
specialist-agent bug it uncovered. It is not a current acceptance owner for connected-account
routing.

## Owning docs / surfaces

- `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`
- Historical provisioner, default-off:
  `viventium_v0_4/LibreChat/scripts/viventium-provision-connected-accounts-agent.js`
- Runtime fix: `viventium_v0_4/LibreChat/api/server/services/viventium/openaiResponsesOutputPatch.js`
- Current QA owner: `qa/glasshive-mcp-capability-broker/`

## Quality bar

Historical acceptance was visible UI outcome (handoff chip + tool calls + inline answer), no error
bubble, no `View / Steer` / worker plumbing in the reply, and no main-agent direct provider tools.
Current acceptance is the GlassHive broker path: visible browser prompt, worker launch/callback,
broker MCP evidence, no forced artifact, and user-scoped provider credentials.

## Latest status

2026-05-30: retired as supported routing. Keep the old reports for comparison only; do not use this
handoff to satisfy current connected-account QA.
