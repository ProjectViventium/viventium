# Changelog

## Unreleased

### GlassHive Ultimate Phase 1

- Added owner-scoped personal Codex and Claude subscriptions with native setup, reconnect, test,
  removal, exclusive leases, and isolated credential projection.
- Added private persistent workspaces with prefilled editable names, favorites, reuse, duplication,
  native tool setup, and the same owner-scoped control through Glass Drive, Codex MCP, and Claude MCP.
- Added concise native Codex and Claude packages that share one canonical MCP-first skill instead of
  duplicating the GlassHive server or connector logic.
- Fixed stale connection removal, expired-session recovery, Claude workspace/tool-state composition,
  interactive setup contention, and incidental external URLs being misreported or opened as results.
- Recorded the accepted installed browser, native-connector, refresh, and fresh external-client
  evidence in the [Ultimate Phase 1 QA report](qa/glasshive-user-control-plane/reports/2026-08-18-ultimate-phase1-qa.md).
- Documented the supported scope and remaining wider gates in the public
  [GlassHive release notes](https://github.com/ProjectViventium/GlassHive/blob/main/docs/12_Ultimate_Phase_1_Release_Notes.md).

## 0.5.0 - 2026-03-12

- Added the public installer and `bin/viventium` command surface.
- Added config schema/examples plus the config compiler and doctor flow.
- Added public/private/enterprise boundary tooling and approval manifests.
- Added explicit licensing matrix and public component pinning through `components.lock.json`.
- Added CI checks for secret scanning, release policy enforcement, and config compilation.
- Added the first public-release documentation set for installation, environment, licensing, and release prep.
