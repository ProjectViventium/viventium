# Changelog

## Unreleased

### Preserve work during dependency recovery

- The menu-bar helper and command-line status distinguish a running service from a dependency
  that needs attention. Available owned services keep running instead of restarting the stack.
  Redis command readiness is visible; each write still checks its own acceptance.
- Commands started with relative paths retain their checkout ownership checks. Helper bundle
  refresh reuses one validated supervisor and preserves intentional Stop.
- Upgrade and missing-process repair stops keep the saved Run/Stop choice. A verified upgrade
  handoff can validate its candidate with background writers disabled; a later user Stop still
  prevents automatic restart. Explicit Start can resume pending upgrade recovery, and its
  finalizer preserves later Stop requests. Older helper formats and valid path aliases remain
  compatible with upgrade finalization.
- Telegram can tell the sender that an input is saved when Core returns a valid retained-input
  receipt during an outage. It does not ask the user to resend accepted work or start a duplicate
  reply. Ambiguous failures and requests rejected before intake keep their separate recovery paths.

### Keep worker costs and recovery clear

- Updated the reviewed xPerfect source pin with exact-attempt usage, safe provider failure
  details and optional owner/project work pauses. Unknown cost stays unknown; repeated receipts
  do not count twice. Resume keeps the accepted work instead of creating another job.
- Claude Code connections can declare separate Bedrock regions and model choices. AWS access
  and model entitlement still need the owner's configuration and verification.
- xPerfect offers an optional evidence/delivery kit and native Linux arm64/amd64 package pairs.
  These remain standalone capabilities with their own qualification limits. The Core source pin
  does not upgrade an existing service or certify a new installed Viventium Native payload.

### Reuse expertise and return to saved work

- Updated the pinned xPerfect component with saved expert versions and recoverable
  Archive, Remove and Restore. Reuse a reviewed worker setup for another job without
  changing existing workers or losing their saved files and results.
- The standalone control panel has a clearer job, context, worker and workspace form,
  section icons, and a simple Create card beside the five starter experts.
- In configured Linux shared-workspace desktops, an already-open human browser stays usable
  while AI work is paused. After supported idle maintenance, Resume then Open browser reuses
  the saved profile. Storage, account and access refusals give specific recovery steps.
- Published the reviewed standalone Linux arm64 package and
  [visual user guide](https://www.xperfect.ai/docs/). Core records the component source pin;
  installed Viventium acceptance remains separate.

### GlassHive Ultimate Phase 1 (earlier milestone)

- Added owner-scoped personal Codex and Claude subscriptions with native setup, reconnect, test,
  removal, exclusive leases, and isolated credential projection.
- Added private persistent workspaces with prefilled editable names, favorites, reuse, duplication,
  native tool setup, and the same owner-scoped control through Glass Drive, Codex MCP, and Claude MCP.
- Added concise native Codex and Claude packages that share one canonical MCP-first skill, and aligned
  the Viventium MCP prompt to the same one-matching-tool/one-call contract without catalog narration.
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
