# GlassHive MCP Capability Broker QA

Scope: brokered projection of LibreChat-managed MCP capabilities into GlassHive workers without
copying provider credentials or letting the host chat model choose connected-account tools.

When selected, live broker QA needs an explicitly authorized isolated account and its own approved
connections. Verify readiness using non-secret metadata. Missing access is a named prerequisite;
do not copy owner credentials or seed private state merely to make QA run. Use the supported
connection flow within existing authorization and preserve any required human-only grant. Keep
tokens and private messages out of public evidence.

Owning docs:

- `docs/requirements_and_learnings/07_MCPs.md`
- `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`
- `viventium_v0_4/GlassHive/docs/03_Bootstrap_Auth_and_Identity_Projection.md`
- `viventium_v0_4/GlassHive/docs/09_Dynamic_MCP_Projection_and_Bidirectional_Availability.md`
