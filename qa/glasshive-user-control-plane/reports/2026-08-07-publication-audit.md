# GlassHive user control plane publication audit — 2026-08-08

## Verdict

GO for source publication after nested components merge first and the parent pins their exact merged commits. Read-only privacy, functionality, and release audits found no unresolved P0–P2 source-publication blocker. The hosted rollout remains a separate acceptance gate.

## Evidence

- Every changed, added, and relevant untracked candidate file was reviewed against public `main`; no deletion, rename, binary, database, runtime state, screenshot, or generated secret file is proposed.
- Exact changed-file secret scans used Gitleaks and Detect Secrets plus protected-identifier and credential-family scans. Scanner hits below were synthetic rejection fixtures or ordinary UI text and were manually adjudicated.
- `git diff --check` passes in all three repositories. Public-safe author and committer identity is configured repository-locally and verified on the nested commits.
- Independent focused reviews found no unresolved isolation, persistence, OAuth/MCP, provider-account, scheduling, connector, direct-conversation, or compatibility blocker.
- Local verification includes the complete GlassHive runtime and UI suites, LibreChat route/package suites and builds, Scheduling Cortex, parent release/compiler suites, and real-browser control-plane flows.

## Per-file ledger

| Repository | File | Change | Purpose | Include | Privacy | Functional risk / judgment |
| --- | --- | --- | --- | --- | --- | --- |
| GlassHive | `docs/04_MCP_Publication_and_Client_Compatibility.md` | M | Public product, operator, or QA documentation | Yes | Clean | Low; reviewed |
| GlassHive | `docs/07_Minimal_Unified_Operator_UI.md` | M | Public product, operator, or QA documentation | Yes | Clean | Low; reviewed |
| GlassHive | `docs/11_Enterprise_Cost_Security_and_Provider_Guardrails.md` | M | Public product, operator, or QA documentation | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `frontends/glass-drive-ui/pyproject.toml` | M | Supporting implementation | Yes | Clean | Low; reviewed |
| GlassHive | `frontends/glass-drive-ui/src/glass_drive_ui/auth_gateway.py` | A | Identity and user-scoped account boundary | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `frontends/glass-drive-ui/src/glass_drive_ui/internal_assertions.py` | A | Identity and user-scoped account boundary | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `frontends/glass-drive-ui/src/glass_drive_ui/prompt_template.py` | M | Supporting implementation | Yes | Clean | Low; reviewed |
| GlassHive | `frontends/glass-drive-ui/src/glass_drive_ui/runtime_client.py` | M | Supporting implementation | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `frontends/glass-drive-ui/src/glass_drive_ui/server.py` | M | Supporting implementation | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `frontends/glass-drive-ui/src/glass_drive_ui/signed_links.py` | M | Supporting implementation | Yes | Clean | Low; reviewed |
| GlassHive | `frontends/glass-drive-ui/src/glass_drive_ui/static/app.js` | M | User-facing control-plane experience | Yes | Clean | Low; reviewed |
| GlassHive | `frontends/glass-drive-ui/src/glass_drive_ui/static/auth.js` | A | User-facing control-plane experience | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `frontends/glass-drive-ui/src/glass_drive_ui/static/confirm.html` | A | User-facing control-plane experience | Yes | Clean | Low; reviewed |
| GlassHive | `frontends/glass-drive-ui/src/glass_drive_ui/static/confirm.js` | A | User-facing control-plane experience | Yes | Clean | Low; reviewed |
| GlassHive | `frontends/glass-drive-ui/src/glass_drive_ui/static/control-plane.js` | A | User-facing control-plane experience | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `frontends/glass-drive-ui/src/glass_drive_ui/static/desktop.js` | M | User-facing control-plane experience | Yes | Clean | Low; reviewed |
| GlassHive | `frontends/glass-drive-ui/src/glass_drive_ui/static/index.html` | M | User-facing control-plane experience | Yes | Clean | Low; reviewed |
| GlassHive | `frontends/glass-drive-ui/src/glass_drive_ui/static/login.html` | A | User-facing control-plane experience | Yes | Clean | Low; reviewed |
| GlassHive | `frontends/glass-drive-ui/src/glass_drive_ui/static/styles.css` | M | User-facing control-plane experience | Yes | Clean | Low; reviewed |
| GlassHive | `frontends/glass-drive-ui/tests/test_auth_gateway.py` | A | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `frontends/glass-drive-ui/tests/test_runtime_client.py` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `frontends/glass-drive-ui/tests/test_server.py` | M | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `frontends/glass-drive-ui/uv.lock` | M | Reproducible dependency lock | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/pyproject.toml` | M | Supporting implementation | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/README.md` | M | Public product, operator, or QA documentation | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/api.py` | M | Supporting implementation | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/auth.py` | M | Identity and user-scoped account boundary | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/bootstrap.py` | M | Supporting implementation | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/capability_broker.py` | A | User-scoped provider and capability brokerage | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/control_plane_models.py` | A | Persistent workspace control plane | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/control_plane.py` | A | Persistent workspace control plane | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/docker_sandbox.py` | M | Supporting implementation | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/inference_broker.py` | A | User-scoped provider and capability brokerage | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/library_registry.py` | A | User-scoped provider and capability brokerage | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/mcp_internal_assertions.py` | A | Identity and user-scoped account boundary | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/mcp_oauth.py` | A | Identity and user-scoped account boundary | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/mcp_server.py` | M | Supporting implementation | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/mission_provider_accounts.py` | A | User-scoped provider and capability brokerage | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/models.py` | M | Supporting implementation | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/openclaw_runtime.py` | M | Supporting implementation | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/profile_runtime.py` | M | Supporting implementation | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/provider_accounts.py` | A | User-scoped provider and capability brokerage | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/recurrence.py` | A | Durable recurring worker scheduling | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/release_provenance.py` | A | Supporting implementation | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/runtime_env.py` | M | Supporting implementation | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/runtime_requirements.py` | M | Supporting implementation | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/scheduling_owner.py` | A | Supporting implementation | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/schema_version.py` | A | Configuration and runtime integration | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/service.py` | M | Persistent workspace control plane | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/signed_links.py` | M | Supporting implementation | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/state_permissions.py` | A | Supporting implementation | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/src/workers_projects_runtime/store.py` | M | Persistent workspace control plane | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/tests/conftest.py` | M | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/tests/fixtures/public_compatibility_origin_main_449eb5d.json` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/tests/library_test_support.py` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/tests/test_api.py` | M | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/tests/test_bootstrap.py` | M | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/tests/test_capability_broker.py` | A | Regression or acceptance evidence | Yes | Clean; synthetic scanner match reviewed | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/tests/test_control_plane_api.py` | A | Regression or acceptance evidence | Yes | Clean; synthetic scanner match reviewed | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/tests/test_control_plane_mcp.py` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/tests/test_control_plane.py` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/tests/test_conversation_provider.py` | M | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/tests/test_docker_sandbox.py` | M | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/tests/test_inference_broker.py` | A | Regression or acceptance evidence | Yes | Clean; synthetic scanner match reviewed | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/tests/test_internal_assertions.py` | A | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/tests/test_library_lifecycle.py` | A | Regression or acceptance evidence | Yes | Clean; synthetic scanner match reviewed | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/tests/test_mcp_oauth.py` | A | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/tests/test_mcp_server.py` | M | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/tests/test_mission_provider_accounts.py` | A | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/tests/test_profile_runtime.py` | M | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/tests/test_public_compatibility_contract.py` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/tests/test_recurring_schedule_api.py` | A | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/tests/test_recurring_schedule_mcp.py` | A | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/tests/test_recurring_schedules.py` | A | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| GlassHive | `runtime_phase1/tests/test_runtime_requirements_configuration.py` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/tests/test_schema_version.py` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/tests/test_workspace_account_switch.py` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/tests/test_workspace_catalog.py` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/tests/test_workspace_lifecycle_catalog.py` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/tests/test_workspace_templates.py` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/uv.lock` | M | Reproducible dependency lock | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/workstation-requirements.in` | A | Supporting implementation | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `runtime_phase1/workstation-requirements.lock` | A | Reproducible dependency lock | Yes | Clean | Medium; reviewed and tested |
| GlassHive | `skills/connect-glasshive/agents/openai.yaml` | A | Public GlassHive connection skill | Yes | Clean | Low; reviewed |
| GlassHive | `skills/connect-glasshive/SKILL.md` | A | Public product, operator, or QA documentation | Yes | Clean | Low; reviewed |
| LibreChat | `api/server/routes/__tests__/connectedAccounts.spec.js` | M | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `api/server/routes/__tests__/viventiumConnectedAccountsConfig.spec.js` | M | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `api/server/routes/config.js` | M | Configuration and runtime integration | Yes | Clean | Medium; reviewed and tested |
| LibreChat | `api/server/routes/connectedAccounts.js` | M | Identity and user-scoped account boundary | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `api/server/routes/viventium/__tests__/glasshiveCapabilities.spec.js` | M | Regression or acceptance evidence | Yes | Clean | Low; reviewed |
| LibreChat | `api/server/routes/viventium/__tests__/glasshiveCapabilitiesDirect.spec.js` | A | Regression or acceptance evidence | Yes | Clean | Low; reviewed |
| LibreChat | `api/server/routes/viventium/__tests__/glasshiveInference.spec.js` | A | Regression or acceptance evidence | Yes | Clean; synthetic scanner match reviewed | High; covered by focused and broader tests |
| LibreChat | `api/server/routes/viventium/__tests__/scheduler.spec.js` | M | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `api/server/routes/viventium/glasshiveCapabilities.js` | M | Supporting implementation | Yes | Clean | Low; reviewed |
| LibreChat | `api/server/routes/viventium/glasshiveInference.js` | A | User-scoped provider and capability brokerage | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `api/server/routes/viventium/index.js` | M | Supporting implementation | Yes | Clean | Low; reviewed |
| LibreChat | `api/server/routes/viventium/scheduler.js` | M | Durable recurring worker scheduling | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `api/server/services/viventium/__tests__/GlassHiveCapabilityBroker.spec.js` | M | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `api/server/services/viventium/__tests__/GlassHiveCapabilityDirectIssuerAuth.spec.js` | A | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `api/server/services/viventium/__tests__/GlassHiveSharedOidcIdentity.spec.js` | A | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `api/server/services/viventium/GlassHiveCapabilityBootstrapService.js` | M | User-scoped provider and capability brokerage | Yes | Clean | Low; reviewed |
| LibreChat | `api/server/services/viventium/GlassHiveCapabilityBrokerAuth.js` | M | Identity and user-scoped account boundary | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `api/server/services/viventium/GlassHiveCapabilityDirectIssuerAuth.js` | A | Identity and user-scoped account boundary | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `api/server/services/viventium/GlassHiveSharedOidcIdentity.js` | A | Identity and user-scoped account boundary | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `api/strategies/openIdJwtStrategy.js` | M | Supporting implementation | Yes | Clean | Low; reviewed |
| LibreChat | `api/strategies/openIdJwtStrategy.spec.js` | M | Regression or acceptance evidence | Yes | Clean | Low; reviewed |
| LibreChat | `api/strategies/openidStrategy.js` | M | Supporting implementation | Yes | Clean | Low; reviewed |
| LibreChat | `api/strategies/openidStrategy.spec.js` | M | Regression or acceptance evidence | Yes | Clean | Low; reviewed |
| LibreChat | `client/src/components/Nav/SettingsTabs/Account/ConnectedAccounts.spec.tsx` | M | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `client/src/components/Nav/SettingsTabs/Account/ConnectedAccounts.tsx` | M | User-facing control-plane experience | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `client/src/locales/en/translation.json` | M | User-facing control-plane experience | Yes | Clean; synthetic scanner match reviewed | Low; reviewed |
| LibreChat | `packages/api/src/cache/keyvMongo.ts` | M | Supporting implementation | Yes | Clean | Low; reviewed |
| LibreChat | `packages/api/src/endpoints/anthropic/initialize.spec.ts` | M | Regression or acceptance evidence | Yes | Clean | Low; reviewed |
| LibreChat | `packages/api/src/endpoints/anthropic/initialize.ts` | M | Supporting implementation | Yes | Clean | Low; reviewed |
| LibreChat | `packages/api/src/endpoints/connectedAccounts/index.ts` | A | Identity and user-scoped account boundary | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `packages/api/src/endpoints/connectedAccounts/inferenceBroker.spec.ts` | A | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `packages/api/src/endpoints/connectedAccounts/inferenceBroker.ts` | A | Identity and user-scoped account boundary | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `packages/api/src/endpoints/connectedAccounts/policy.ts` | A | Identity and user-scoped account boundary | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `packages/api/src/endpoints/index.ts` | M | Supporting implementation | Yes | Clean | Low; reviewed |
| LibreChat | `packages/api/src/endpoints/openai/initialize.spec.ts` | M | Regression or acceptance evidence | Yes | Clean | Low; reviewed |
| LibreChat | `packages/api/src/endpoints/openai/initialize.ts` | M | Supporting implementation | Yes | Clean | Low; reviewed |
| LibreChat | `packages/data-provider/src/config.ts` | M | User-scoped provider and capability brokerage | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `packages/data-provider/src/connectedAccounts.spec.ts` | A | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `packages/data-provider/src/connectedAccounts.ts` | A | Identity and user-scoped account boundary | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `packages/data-provider/src/index.ts` | M | User-scoped provider and capability brokerage | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `packages/data-schemas/src/schema/user.ts` | M | Configuration and runtime integration | Yes | Clean | Medium; reviewed and tested |
| LibreChat | `packages/data-schemas/src/types/user.ts` | M | Configuration and runtime integration | Yes | Clean | Medium; reviewed and tested |
| LibreChat | `viventium/MCPs/scheduling-cortex/pyproject.toml` | M | Durable recurring worker scheduling | Yes | Clean | Low; reviewed |
| LibreChat | `viventium/MCPs/scheduling-cortex/README.md` | M | Public product, operator, or QA documentation | Yes | Clean | Low; reviewed |
| LibreChat | `viventium/MCPs/scheduling-cortex/scheduling_cortex/dispatch.py` | M | Durable recurring worker scheduling | Yes | Clean | Low; reviewed |
| LibreChat | `viventium/MCPs/scheduling-cortex/scheduling_cortex/glasshive_assertions.py` | A | Identity and user-scoped account boundary | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `viventium/MCPs/scheduling-cortex/scheduling_cortex/glasshive_workspace_schedules.py` | A | Durable recurring worker scheduling | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `viventium/MCPs/scheduling-cortex/scheduling_cortex/models.py` | M | Durable recurring worker scheduling | Yes | Clean | Low; reviewed |
| LibreChat | `viventium/MCPs/scheduling-cortex/scheduling_cortex/scheduler.py` | M | Durable recurring worker scheduling | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `viventium/MCPs/scheduling-cortex/scheduling_cortex/server.py` | M | Durable recurring worker scheduling | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `viventium/MCPs/scheduling-cortex/scheduling_cortex/storage.py` | M | Durable recurring worker scheduling | Yes | Clean | Low; reviewed |
| LibreChat | `viventium/MCPs/scheduling-cortex/scheduling_cortex/workspace_recurrence.py` | A | Durable recurring worker scheduling | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `viventium/MCPs/scheduling-cortex/tests/test_dispatch.py` | M | Regression or acceptance evidence | Yes | Clean | Low; reviewed |
| LibreChat | `viventium/MCPs/scheduling-cortex/tests/test_glasshive_workspace_schedules.py` | A | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `viventium/MCPs/scheduling-cortex/tests/test_server.py` | A | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| LibreChat | `viventium/MCPs/scheduling-cortex/uv.lock` | M | Reproducible dependency lock | Yes | Clean | Medium; reviewed and tested |
| Parent | `components.lock.json` | M | Exact reviewed nested-component pins | Yes | Clean | High; merged commits verified |
| Parent | `config.full.example.yaml` | M | Configuration and runtime integration | Yes | Clean | Medium; reviewed and tested |
| Parent | `config.minimal.example.yaml` | M | Configuration and runtime integration | Yes | Clean | Medium; reviewed and tested |
| Parent | `config.schema.yaml` | M | Configuration and runtime integration | Yes | Clean | Medium; reviewed and tested |
| Parent | `deploy/glasshive/systemd/.gitignore` | A | Immutable hosted rollout and rollback | Yes | Clean | High; covered by focused and broader tests |
| Parent | `deploy/glasshive/systemd/glasshive_rollout.py` | A | Immutable hosted rollout and rollback | Yes | Clean | High; covered by focused and broader tests |
| Parent | `deploy/glasshive/systemd/glasshive_rootless_docker_probe.py` | A | Immutable hosted rollout and rollback | Yes | Clean | High; covered by focused and broader tests |
| Parent | `deploy/glasshive/systemd/glasshive_ui_readiness_probe.py` | A | Immutable hosted rollout and rollback | Yes | Clean | High; covered by focused and broader tests |
| Parent | `deploy/glasshive/systemd/glasshive-mcp.service` | A | Immutable hosted rollout and rollback | Yes | Clean | High; covered by focused and broader tests |
| Parent | `deploy/glasshive/systemd/glasshive-runtime.service` | A | Immutable hosted rollout and rollback | Yes | Clean | High; covered by focused and broader tests |
| Parent | `deploy/glasshive/systemd/glasshive-ui.service` | A | Immutable hosted rollout and rollback | Yes | Clean | High; covered by focused and broader tests |
| Parent | `deploy/glasshive/systemd/glasshive.target` | A | Immutable hosted rollout and rollback | Yes | Clean | High; covered by focused and broader tests |
| Parent | `deploy/glasshive/systemd/README.md` | A | Public product, operator, or QA documentation | Yes | Clean | High; covered by focused and broader tests |
| Parent | `deploy/glasshive/systemd/rollout.example.json` | A | Immutable hosted rollout and rollback | Yes | Clean | High; covered by focused and broader tests |
| Parent | `docs/02_ARCHITECTURE_OVERVIEW.md` | M | Public product, operator, or QA documentation | Yes | Clean | Low; reviewed |
| Parent | `docs/03_SYSTEMS_MAP.md` | M | Public product, operator, or QA documentation | Yes | Clean | Low; reviewed |
| Parent | `docs/requirements_and_learnings/01_Key_Principles.md` | M | Public product, operator, or QA documentation | Yes | Clean | Low; reviewed |
| Parent | `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md` | M | Public product, operator, or QA documentation | Yes | Clean | Medium; reviewed and tested |
| Parent | `docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md` | M | Public product, operator, or QA documentation | Yes | Clean | Low; reviewed |
| Parent | `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md` | M | Public product, operator, or QA documentation | Yes | Clean | Medium; reviewed and tested |
| Parent | `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md` | M | Public product, operator, or QA documentation | Yes | Clean | Medium; reviewed and tested |
| Parent | `docs/requirements_and_learnings/55_GlassHive_User_Control_Plane_and_Persistent_Workspaces.md` | A | Public product, operator, or QA documentation | Yes | Clean | Medium; reviewed and tested |
| Parent | `qa/feature-user-use-case-checklist.md` | M | Regression or acceptance evidence | Yes | Clean | Low; reviewed |
| Parent | `qa/glasshive-mcp-capability-broker/cases.md` | M | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| Parent | `qa/glasshive-user-control-plane/cases.md` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| Parent | `qa/glasshive-user-control-plane/coverage.md` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| Parent | `qa/glasshive-user-control-plane/README.md` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| Parent | `qa/glasshive-user-control-plane/reports/2026-08-05-deployment-readiness-gap-closure.md` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| Parent | `qa/glasshive-user-control-plane/reports/2026-08-05-implementation-and-local-browser.md` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| Parent | `qa/glasshive-user-control-plane/reports/2026-08-05-source-and-unit-baseline.md` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| Parent | `qa/glasshive-user-control-plane/reports/2026-08-06-direct-connected-capability-bridge.md` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| Parent | `qa/glasshive-user-control-plane/reports/2026-08-06-final-local-acceptance-and-approval-gate.md` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| Parent | `qa/glasshive-user-control-plane/reports/2026-08-06-hosted-atomic-rollout-source-validation.md` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| Parent | `qa/glasshive-user-control-plane/reports/2026-08-07-publication-audit.md` | A | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| Parent | `qa/installer-resilience/installer-lifecycle-inventory-2026-07-18.md` | M | Current merged-component inventory | Yes | Clean | Medium; pin contract tested |
| Parent | `qa/release-readiness/cases.md` | M | Current release pin acceptance evidence | Yes | Clean | Medium; pin contract tested |
| Parent | `qa/release-test-owners.yaml` | M | Regression or acceptance evidence | Yes | Clean | Low; reviewed |
| Parent | `qa/scheduling-cortex/cases.md` | M | Regression or acceptance evidence | Yes | Clean | Low; reviewed |
| Parent | `qa/scheduling-cortex/reports/2026-08-06-glasshive-principal-authority-and-retry-budget.md` | A | Regression or acceptance evidence | Yes | Clean | High; covered by focused and broader tests |
| Parent | `release/native-payload/components.json` | M | Exact merged LibreChat payload pin | Yes | Clean | High; manifest contract tested |
| Parent | `scripts/viventium/config_compiler.py` | M | Configuration and runtime integration | Yes | Clean | Medium; reviewed and tested |
| Parent | `tests/release/test_config_compiler.py` | M | Regression or acceptance evidence | Yes | Clean | Medium; reviewed and tested |
| Parent | `tests/release/test_glasshive_systemd_rollout.py` | A | Regression or acceptance evidence | Yes | Clean | Low; reviewed |
| Parent | `viventium_v0_4/viventium-librechat-start.sh` | M | Configuration and runtime integration | Yes | Clean | Low; reviewed |

## Exclusions

Ignored caches, build output, dependency directories, logs, databases, runtime state, credentials, machine-local configuration, and unchanged nested components are excluded and must never be force-added. Hosted/private QA evidence stays outside the public repositories.
