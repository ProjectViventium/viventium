# Workspace Control Room Local Browser QA — 2026-08-11

## Summary

- Result: **PASS for the local synthetic browser implementation; PARTIAL for the exact installed
  multi-user release**.
- Surface: the real Glass Drive HTML, CSS, JavaScript, BFF, auth gateway, and runtime APIs were run
  in Chromium against synthetic public-safe state.
- Scope: modern navigation, direct output, bounded multi-worker overview, parallel steering,
  capability reapproval, weekly scheduling, local-only login presentation, and external AI setup.
- No private deployment, customer, browser-profile, account, or credential data was captured.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHWS-003` | `PASS` | Headed Chromium modern navigation, direct output, and state-transition observations | Local synthetic runtime only |
| `GHWS-004` | `PASS` | Headed Chromium 1/4/5/25-worker matrix, responsive layouts, and parallel steering | Preview cost and interaction remained bounded |
| `GHWS-005` | `PARTIAL` | Local duplicate/review persistence and waiver flows plus server tests | Exact installed two-user execution remains open |
| `GHWS-006` | `PARTIAL` | Escaped hosted failure shape and automated terminal-state policy regression | Corrected installed failure-to-recovery path remains open |

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

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: GlassHive workspace control room, direct output, capability review, scheduling, and
  external-AI setup.
- Requirement: the user control-plane requirements and nested GlassHive workspace/runtime contract.
- Use case: `GHWS-UC-004` through `GHWS-UC-007`.
- QA case: `GHWS-003` through `GHWS-006`.
- Expected result: modern non-mutating output inspection, bounded view-only previews, durable exact
  capability decisions, and actionable terminal recovery.
- Actual evidence: headed Chromium flows, DOM/network observations, persisted synthetic state, and
  the automated suites summarized below.
- Remaining gap or fix: exact installed two-owner denial, corrected terminal recovery, MCP-client
  consent, and release continuity remain `PARTIAL` or `BLOCKED` until run.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | PASS — workspace-control requirements and `GHWS-003` through `GHWS-006` |
| Code owning path | Which code path owns the behavior? | PASS — Glass Drive HTML/CSS/JavaScript, BFF/auth gateway, runtime APIs, and parent compiler were exercised |
| Docs and nested docs/repos | Which docs define expected behavior? | PASS — parent user-control-plane requirements and nested GlassHive workspace/runtime docs were compared |
| Scripts or harnesses | Which suites exercised it? | PASS — headed Chromium harness plus Glass Drive, runtime API, compiler, and MCP security suites |
| Local/external prerequisite state | Which prerequisites were healthy or degraded? | PARTIAL — synthetic local services were healthy; exact installed multi-user and external MCP clients were unavailable |
| Logs | Which sanitized logs confirm the result? | PASS — local browser/API requests and lifecycle call counts matched visible state; raw logs remained private |
| DB/state/persistence | What confirms persistence? | PASS locally — refresh restored server-owned capability review and login state; installed two-user persistence remains open |
| Generated/shipped artifact | Which generated or shipped output was inspected? | PARTIAL — parent compiler output and local UI/runtime source were exercised; sealed installed release remained open |
| Real user path | Which path was used like a user? | PASS locally — headed Chromium navigation, output, steering, capability, schedule, login, and setup flows |
| Visual/UX comparison | Did visible behavior match expectations? | PASS locally — responsive and interaction states matched the requirements |
| Not run / blocked | Which surface remains open? | BLOCKED — exact installed two-owner denial, real external MCP clients, and installed continuity |

Supporting evidence cannot replace required user-path evidence. The installed and external-client
paths remain `PARTIAL` or `BLOCKED` even where source and automated checks passed.

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

## User-Grade Evidence

- Surface exercised: headed Chromium browser against the real Glass Drive UI, BFF, auth gateway,
  runtime APIs, and synthetic public-safe state.
- Real user path: open Workspaces, navigate to Watch, inspect output, steer parallel workers, review
  capabilities, create a weekly schedule, sign in/out, and inspect external-AI setup.
- Visible outcome: modern navigation, non-mutating output inspection, bounded previews, distinct
  steering, truthful authentication, and concise setup states rendered as expected.
- Expanded/detail state: artifact details, More disclosures, capability review, schedule validation,
  and Automatic/Manual setup states were opened and inspected.
- Persistence/reload result: refresh restored the synthetic login and server-owned review state;
  output replacement persisted within the exercised local run.
- Local/external prerequisite state: local synthetic services were available; exact installed
  multi-user, provider-backed, and external MCP-client prerequisites were unavailable.
- Evidence retrieval classification, if applicable: external client and exact installed release
  paths were local prerequisite unavailable, not successful-empty results.
- Fallback path, if applicable: no mock or source-only substitute was accepted for the missing
  installed multi-user paths.
- Backend/log/DB confirmation: sanitized API/lifecycle counts and persisted server state agreed with
  the browser; raw logs and state remained private.
- Final model/runtime wording check: this report claims local browser success only and labels the
  exact installed release `PARTIAL`.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Findings

- Defects: five escaped hosted-state or release-presentation defects were rejected and converted to
  synthetic regressions before this candidate was accepted.
- Regressions: none observed in the final local synthetic browser matrix.
- Flakes: none recorded.
- Environment issues: exact installed multi-user, external MCP-client, and provider-backed release
  prerequisites were not available to this local run.
- Residual risks: installed two-owner denial, terminal recovery, external client consent, scheduled
  fire, and release continuity require the explicit gates above.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
- [x] Raw local browser artifacts remain untracked and outside this public report.
