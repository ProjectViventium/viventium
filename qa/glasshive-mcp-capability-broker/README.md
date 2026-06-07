# GlassHive MCP Capability Broker QA

Scope: brokered projection of LibreChat-managed MCP capabilities into GlassHive workers without
copying provider credentials or letting the host chat model choose connected-account tools.

Live browser QA must use a copied non-owner local QA account with connected-account credentials. Do
not treat an unauthenticated Playwright profile, empty duplicate account, or owner account as valid
evidence. Before running `GH-MCP-BROKER-014`, verify by metadata counts only that the QA account has
the expected Google/MS365/model credential rows; if it does not, locally reseed or reconnect that QA
account from the owner account under the private user-data folder, preserving the owner account and
never writing token values or private message content into public QA artifacts.

Owning docs:

- `docs/requirements_and_learnings/07_MCPs.md`
- `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`
- `viventium_v0_4/GlassHive/docs/03_Bootstrap_Auth_and_Identity_Projection.md`
- `viventium_v0_4/GlassHive/docs/09_Dynamic_MCP_Projection_and_Bidirectional_Availability.md`
