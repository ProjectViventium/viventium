# GlassHive User Control Plane QA

## Feature Summary

This area owns cross-feature acceptance for authenticated personal GlassHive control: identity,
personal provider accounts, persistent workspaces, brokered connections, curated Library changes,
MCP client connection, recurring schedules, Viventium direct-conversation preservation, and the
source-to-installed delivery chain.

Detailed provider, worker, workspace, scheduler, and release behavior remains owned by the existing
specialized QA areas. This folder is the control-plane traceability spine and records whether the
complete user journey has actually been proven.

## Requirement Links

- [User control plane and persistent workspaces](../../docs/requirements_and_learnings/55_GlassHive_User_Control_Plane_and_Persistent_Workspaces.md)
- [Key principles](../../docs/requirements_and_learnings/01_Key_Principles.md)
- [GlassHive workstation runtime](../../docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md)
- [MCPs](../../docs/requirements_and_learnings/07_MCPs.md)
- [Scheduling Cortex](../../docs/requirements_and_learnings/11_Scheduling_Cortex.md)
- [Installer and compiler](../../docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md)
- [Public/private boundaries](../../docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md)

## User-Grade Surfaces

- Glass Drive login and control-plane UI in a real browser
- GlassHive MCP through real Codex and Claude clients
- native provider setup terminal/browser/device flow
- persistent workspace desktop/browser and artifact surfaces
- recurrence creation, fire, activity, callback, and MCP status
- Viventium direct GlassHive conversation through web plus applicable channel/voice surfaces
- supported public installer, upgrade, helper/launcher, and installed runtime

## Supporting Evidence

- focused GlassHive runtime and Glass Drive automated tests
- runtime API responses and scoped database rows
- identity-gateway, internal-assertion, scheduler, worker, and broker logs with secrets redacted
- workspace filesystem, browser-profile, provider-home, lease, grant, occurrence, and activity state
- canonical config, compiler output, component lock, bootstrap resolution, built artifact, and installed
  process provenance
- hosted edge route ownership, trusted-header scrubbing, public JWKS/MCP challenges, and negative
  external runtime reachability
- separate signer/runtime service identities and mounts, verifier-only runtime/worker environments,
  and bounded key-rotation evidence
- quiesced SQLite/WAL backup, restore-tested clone migration, integrity/FK/schema/count checks, and
  database-inclusive rollback evidence
- atomic runtime/MCP/BFF staging, readiness, ingress switch, failure cleanup, and rollback evidence
- public-safety and license scans

Automated checks and source inspection support acceptance but do not replace a required real browser,
provider, MCP client, scheduler, or installed-runtime path.

## Status Vocabulary

- `PASS`: the complete required user path and supporting evidence were run for the stated build.
- `FAIL`: the observed result contradicted the expected outcome.
- `PARTIAL`: useful supporting evidence exists, but one or more required layers were not proven or a
  focused check failed.
- `BLOCKED`: the user-grade path could not run because a named prerequisite was unavailable.
- `PENDING`: the case has not yet been run for the candidate.

## Current Status

**PARTIAL overall — the installed Ultimate Phase 1 user journey is accepted.** The complete
accepted-release GlassHive runtime and Glass Drive suites, compiler tests, local browser matrix,
sealed hosted cutover, authenticated Edge Workspaces journey, personal-subscription missions, and
real Codex and Claude MCP
OAuth/tool/persistence paths pass. The hosted run also proved modern navigation, safe direct output,
view-only live control, controller-driven continuation, exact artifact persistence, and targeted OAuth
failure handling. Native connected-service use/reuse passed in both Codex and Claude without
connector-specific GlassHive wiring. The product owner retested and accepted this scoped journey on
2026-08-21. The current source baseline and the focused Library/template slice are green, and
native Codex and Claude plugin packages pass official validation and isolated installation. The
broader control plane still has explicit open gates for two-owner denial, brokered third-party
connections, scheduled fire, a second healthy provider account, clean install, upgrade/restore,
signer isolation, and the full organization-IdP denial matrix.

## Files

- [completion-ledger.md](completion-ledger.md): exact final outcome, current snapshot, ordered
  workstreams, blockers, and completion gates; this is the execution/status layer and does not
  replace Requirement 55 or the durable case catalog
- [cases.md](cases.md): canonical happy and unhappy path checklist
- [coverage.md](coverage.md): requirement and acceptance-item traceability
- [reports/2026-08-05-source-and-unit-baseline.md](reports/2026-08-05-source-and-unit-baseline.md):
  initial public-safe source baseline
- [reports/2026-08-05-implementation-and-local-browser.md](reports/2026-08-05-implementation-and-local-browser.md):
  current implementation, automated, browser, state, and open-gate evidence
- [reports/2026-08-05-deployment-readiness-gap-closure.md](reports/2026-08-05-deployment-readiness-gap-closure.md):
  independent deployment-topology findings, source guards added, and remaining hosted gates
- [reports/2026-08-18-ultimate-phase1-qa.md](reports/2026-08-18-ultimate-phase1-qa.md):
  accepted browser, personal-account, native-connector, workspace-reuse, removal, and fresh
  Codex/Claude MCP evidence, with the wider gates kept explicit

## Related Specialized QA Owners

- [GlassHive workspaces](../glasshive_workspaces/)
- [GlassHive host workers](../glasshive_host_workers/)
- [GlassHive capability broker](../glasshive-mcp-capability-broker/)
- [GlassHive core provider](../glasshive-core-provider/)
- [MCP OAuth](../mcp-oauth/)
- [Scheduling Cortex](../scheduling-cortex/)
- [Connected Accounts handoff](../connected-accounts-handoff/)
- [Release readiness](../release-readiness/)
- [Installer resilience](../installer-resilience/)

## Public-Safety Rules

Use only synthetic users, tenants, domains, workspaces, provider states, schedules, and artifacts.
Do not save credentials, signed URLs, provider homes, browser profiles, raw runtime databases, raw
logs, private screenshots, customer names, personal email addresses, local absolute paths, or
machine identifiers in this folder.
