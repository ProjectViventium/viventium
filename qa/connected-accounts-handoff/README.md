# Connected Accounts Handoff QA

## Scope

The main Viventium agent stays lean (no direct provider tools) and reaches the user's connected
Google Workspace / Microsoft 365 accounts through a dedicated **Connected Accounts** hand-off agent
via a native LibreChat handoff edge (`edges[].edgeType: "handoff"`, auto-generated
`lc_transfer_to_<agent>` tool). Writes are not in the hand-off agent's tool set; they stay on the
broker/worker path with confirmation. Deep Research and delegated/long tasks stay under GlassHive.

This area proves the **routing** of that handoff: when it hands off, when it must not, which
providers it covers, that the answer returns inline with no worker and no plumbing leak, and that
OpenAI Responses-API models (gpt-5.4) used by specialist agents no longer throw a spurious error.

## Owning docs / surfaces

- `docs/requirements_and_learnings/02_Background_Agents.md` (broker-first baseline; connected accounts under GlassHive / hand-off)
- Provisioning: `viventium_v0_4/LibreChat/scripts/viventium-provision-connected-accounts-agent.js`
- Runtime fix: `viventium_v0_4/LibreChat/api/server/services/viventium/openaiResponsesOutputPatch.js`
- Surfaces: LibreChat Web UI (primary), main agent `agent_viventium_main_95aeb3`, hand-off agent `agent_viventium_connected_accounts_95aeb3`

## Quality bar

Real-browser acceptance: visible UI outcome (handoff chip + tool calls + inline answer), no error
bubble, no `View / Steer` / worker plumbing in the reply, main agent never gains direct provider
tools. Public-safe evidence only (counts/timestamps, no private message bodies, IDs, or tokens).

## Latest status

2026-05-28: routing PASS for email + calendar (both providers, inline) and PASS for the
no-handoff negative case; gpt-5.4 Responses error fixed and regression-tested. See `cases.md`.
