# Workspace Control Room Local Browser QA — 2026-08-11

## Summary

- Result: **PASS for the local synthetic browser implementation; PARTIAL for the exact installed
  multi-user release**.
- Surface: the real Glass Drive HTML, CSS, JavaScript, BFF, auth gateway, and runtime APIs were run
  in Chromium against synthetic public-safe state.
- Scope: modern navigation, direct output, bounded multi-worker overview, parallel steering,
  capability reapproval, weekly scheduling, local-only login presentation, and external AI setup.
- No private deployment, customer, browser-profile, account, or credential data was captured.

## User-Level Results

| Flow | Result | Visible and supporting evidence |
| --- | --- | --- |
| Home and workspace navigation | PASS | The GlassHive brand is a link; pointer activation of the inert preview and keyboard activation of the single visible Open workspace action opened modern Watch; the Watch brand returned to Workspaces; no ordinary action navigated to `/ui/projects/*`. |
| Completed output | PASS | Chromium observed completed run A, running run B, then completed B without rebuilding the grid. B replaced A's label/links; keyboard activation changed View to Hide with matching `aria-controls`; Open rendered B in a new tab, Download remained distinct, and the lifecycle ledger stayed empty. |
| Control-room scale | PASS locally | Browser runs with 1, 4, 5, and 25 mixed workers used compact visible-card refresh without overlap. Preview surfaces were capped at three and view-only. An active-to-idle transition hid the pointer overlay, exposed one keyboard-focusable Resume workspace action, and emitted the exact resume lifecycle request. Synthetic noVNC failures removed the unavailable frames. |
| Parallel steering | PASS | Two different workspace cards accepted distinct steer instructions concurrently; both reached the correct worker; no resume/pause lifecycle request was emitted. |
| Responsive layout | PASS | At 320, 768, and 1024 CSS pixels all six primary tabs stayed visible and in bounds, the grid used one/one/two columns, every More disclosure started closed, and document width equaled viewport width. |
| Capability review | PASS locally | Duplicate routed to Library; the exact read-only scope was preselected; clearing tab storage and refreshing restored the review from server state; human waiver used the confirmation page and removed only that action. |
| Weekly schedule | PASS locally | Browser submission produced an RFC 5545 weekly rule, browser-selected time zone, exact first local time, and concise `Schedule created.` feedback. Missing workspace and first-run time produced focused, specific validation. |
| Local-only login | PASS locally | Only email/password was presented; unknown and wrong-password failures were identical; successful login used the preapproved issuer+subject principal, survived refresh, hid provider switching, kept Sign out, and cleared review state on logout. Signup/reset remained absent. |
| External AI setup | PASS for local presentation | The primary Automatic tab showed one copyable prompt containing the exact deployment-generated add/sign-in commands. Real keyboard ArrowRight moved Automatic to Manual. Codex-only and Claude-only states rendered only the supported card/name/commands; Manual kept one server address, terminal commands, and non-clickable administrator callback data secondary. Clipboard denial selected the exact text. A synthetic setup `503` left the ready worker account usable and disabled misleading copy actions. |

## Automated Evidence

- Complete Glass Drive server/UI file: **222 passed**.
- Complete runtime API file: **232 passed**.
- Focused control-plane, provider-account duplication, and template files: **29 passed**.
- Focused MCP OAuth/tool/owner-scope paths: **7 passed**.
- Parent compiler/schema contract: **3 passed**.
- JavaScript syntax, Python compilation, nested/parent `git diff --check`, and JSON parsing: PASS.
- Escaped response-model regression: pending duplicate and template-origin reports reload through
  worker/live response models before execution.

## Hosted Canary Attempt

- The first sealed candidate was activated behind the isolated canary endpoint and tested through
  the authenticated browser before acceptance.
- Navigation, modern Workspaces, safe artifact Open/Download, completed Watch wording, concise
  Connections, and Automatic/Manual external-AI presentation behaved as expected.
- Acceptance was rejected because the prominent completed-output action still exposed a
  worker-local `file:` target and the generated Codex command duplicated the OAuth resource that
  the client already derives from protected-resource metadata.
- Explicit rollback restored the verified predecessor; the stable endpoint and out-of-scope
  services remained unchanged.
- A second sealed candidate reached authenticated Workspaces, where the browser exposed another
  escaped state transition before acceptance: `Open workspace` on a completed retained card resumed
  compute because the handler consulted the older raw `paused` worker state instead of the latest-run
  `Completed` state shown on the card. The synthetic
  QA workspace was closed, explicit rejection restored the predecessor, and stable/out-of-scope
  surfaces again remained unchanged. Auto-resume now uses that same user-visible state and is limited to actual paused/idle/stopped named
  workspaces; completed work requires explicit Continue/Send.
- A third sealed candidate proved the catalog object still retained raw `paused` even after the card
  refreshed visibly to `Completed`. Its click displayed `Resuming…`; acceptance was again rejected,
  the synthetic QA workspace was closed, and the predecessor was restored. The final policy now reads
  the rendered card state itself and uses catalog state only before a card has rendered live state.
- A later sealed candidate completed the modern navigation, output, Connections recovery, and
  external-AI presentation checks, then exposed a fifth recovery mismatch during a real
  provider-backed follow-up: the failed card instructed the user to pause a stale sandbox while
  Workspaces and Watch hid Pause for failed/cancelled/interrupted runs. The candidate was explicitly
  rejected after a product-scoped pause and orphan-compute cleanup; predecessor health/provenance
  and the stable endpoint remained unchanged. Terminal attention cards now retain enabled Pause,
  keep Resume unavailable, and have a reusable policy regression.
- All five escaped failures now have synthetic regressions. Exact post-fix installed browser and client
  reruns remain required before this report can mark the hosted release PASS.

## Expected And Forbidden Outcomes

- Expected: one glossy control surface, one primary Open workspace action, direct safe output,
  explicit Continue/Send mutations, bounded preview cost, exact server-owned capability decisions,
  and one deployment-specific address for external AI clients.
- Forbidden and not observed: inert brand, primary legacy UI navigation, output inspection resuming
  compute, offscreen polling storm, interactive overview frames, storage-only review authority,
  widened copied scopes, an impossible review for a forgotten account, raw callback links as setup
  actions, unsupported-client advertising, or a hidden fallback provider run.

## Remaining Installed-Release Gates

- Exact sealed component/parent provenance and clean bootstrap/install.
- Real desktop/noVNC stream, reconnect, refresh, and backend WebSocket correlation.
- Exact hosted browser rerun with two synthetic owners and wrong-owner denial.
- Real Codex and Claude Code MCP add/authenticate/tool/persistence flows against the configured
  deployment URL, including port collision, cancelled consent, wrong resource/scope, and retry.
- Real provider-backed mission, artifact bytes/download, schedule fire, restart persistence, and
  rollback on the installed release.

These items remain **PARTIAL**. Source tests and the local browser run are supporting evidence, not a
substitute for the installed multi-user paths.

## Public-Safety Review

- [x] Synthetic domains, labels, prompts, states, and credentials only.
- [x] No private hostnames, emails, account IDs, local paths, screenshots, tokens, or raw logs.
- [x] No customer/client names or unrelated project context.
- [x] Raw local Playwright artifacts remain untracked and outside this report.
