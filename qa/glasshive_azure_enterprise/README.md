# GlassHive Azure Enterprise QA

Scope: local verification for `azure_enterprise_vm_docker` before any Azure deployment. This QA area
owns enterprise auth/tenancy, config-only LibreChat MCP integration, worker idle cost controls,
upload/download, and operator takeover behavior.

Owning docs:

- `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
- `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`
- Private enterprise deployment runbook under the enterprise deployment repo

Quality bar:

- Local mode must keep passing existing GlassHive API/MCP tests.
- Enterprise mode must fail closed, ignore caller-supplied owner IDs, and scope every project,
  worker, run, artifact, and UI/watch route by authenticated tenant/user context.
- Browser QA must use synthetic users and public-safe files only.
