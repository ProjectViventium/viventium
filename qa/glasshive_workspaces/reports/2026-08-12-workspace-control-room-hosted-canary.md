# Workspace Control Room Hosted Canary QA — 2026-08-12

## Summary

- Result: **PASS for the isolated hosted Workspaces/provider-mission canary; PARTIAL for external
  MCP client consent, installed two-owner denial, and fresh bootstrap/upgrade continuity**.
- The exact sealed candidate was accepted only after the authenticated browser run and a zero-work
  release gate; the stable endpoint remained unchanged.
- All browser content and prompts were synthetic and public-safe. No private host, account, worker,
  project, token, callback, or local-machine value is recorded here.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `GHWS-003` | `PASS` | Authenticated headed browser navigation, signed output, two provider follow-ups, and refresh | Exact accepted hosted canary |
| `GHWS-004` | `PASS` | Real view-only desktop stream and clean active-to-completed teardown | Stable endpoint remained unchanged |
| `GHWS-005` | `PARTIAL` | Connection/setup presentation passed | Hosted two-user duplicate/template reapproval remains open |
| `GHWS-006` | `PARTIAL` | Terminal-policy automation and prior rejection evidence | Deliberately failed post-fix hosted mission was not induced |

## Real User Results

| Flow | Result | Evidence |
| --- | --- | --- |
| Login recovery | PASS | An expired hosted session reached the bounded login page. Organization sign-in in the designated existing browser profile returned to the requested Workspaces route; signup/reset remained absent. |
| Home and modern navigation | PASS | GlassHive was a native Home link. Workspaces opened modern Watch and Watch returned to Workspaces. No normal path entered `/ui/projects/*` or exposed a worker-local `file:` URL. |
| Direct output | PASS | A completed card expanded in place without resuming compute. Signed HTML and text artifact landings opened in new tabs; the HTML rendered as a sandboxed page preview and the text landing showed the exact 36-byte synthetic result. The browser download action completed without opening an error tab. |
| Provider reuse | PASS | A ready personal subscription completed two real follow-up missions in the retained workspace. The first created an exact QA note; the second created a preview-check note after a bounded observation window. Both returned to Completed and the account remained Ready. |
| Live control room | PASS | The active card first showed an honest warming state, then mounted the real view-only desktop stream. The iframe carried the preview query, `pointer-events: none`, `tabindex=-1`, and the visible “VIEW ONLY” indicator. Completion removed the live frame and restored delivery state. |
| Delivery replacement and persistence | PASS | The second run replaced the card summary/artifact set without rebuilding the grid. Refresh preserved Completed state, both new files, the modern actions, and the installed cache revision. |
| Responsive layout | PASS | At 320, 768, and 1024 CSS pixels the document width equaled the viewport, all six primary tabs stayed visible, and workspace actions remained available. |
| Connections and external-AI presentation | PASS for presentation | The personal worker account stayed Ready. The collapsed external-AI section opened to Automatic with one exact deployment-bound prompt; keyboard Manual remained secondary and callback plumbing remained admin-only. No duplicate OAuth-resource flag was present. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: hosted GlassHive workspace control room and provider-mission delivery.
- Requirement: modern non-mutating workspace navigation, bounded control-room previews, durable
  delivery state, and public-safe external-AI presentation.
- Use case: `GHWS-UC-004` through `GHWS-UC-007`.
- QA case: `GHWS-003` through `GHWS-006`.
- Expected result: direct signed output, no accidental resume, view-only live preview, provider
  reuse, refresh persistence, and concise deployment-bound setup.
- Actual evidence: authenticated headed-browser observations, artifact byte count, runtime
  provenance, release-gate state, and automated suites.
- Remaining gap or fix: external MCP consent, exact installed two-owner denial, deliberately failed
  post-fix recovery, and fresh install/upgrade remain `PARTIAL` or `BLOCKED`.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | PASS — hosted portions of `GHWS-003` through `GHWS-006` |
| Code owning path | Which code path owns the behavior? | PASS — Glass Drive UI/BFF, runtime APIs, provider account path, artifact landing, and release helper were traced |
| Docs and nested docs/repos | Which docs define expected behavior? | PASS — parent control-plane requirements and nested GlassHive workspace/release docs were compared |
| Scripts or harnesses | Which suites exercised it? | PASS — authenticated headed browser, release gate, runtime/UI/compiler/security suites |
| Local/external prerequisite state | Which prerequisites were healthy or degraded? | PARTIAL — hosted runtime/provider account were healthy; external MCP clients and two-owner setup were unavailable |
| Logs | Which sanitized logs confirm the result? | PASS — release health, provenance, product requests, and zero-work gate agreed with visible state; raw logs remained private |
| DB/state/persistence | What confirms persistence? | PASS for exercised path — refresh preserved Completed state and artifact set; two-owner review remains open |
| Generated/shipped artifact | Which generated or shipped output was inspected? | PASS for canary — exact sealed provenance, revisioned UI assets, signed landings, and installed cache revision were inspected |
| Real user path | Which path was used like a user? | PASS — authenticated headed browser login recovery, Workspaces/Watch, artifact open/download, missions, and refresh |
| Visual/UX comparison | Did visible behavior match expectations? | PASS for accepted flows — UI state, output, stream teardown, responsive layout, and setup presentation agreed |
| Not run / blocked | Which surface remains open? | BLOCKED — real Codex/Claude MCP consent and exact installed two-owner denial; other listed gates are PARTIAL |

Supporting evidence cannot replace required user-path evidence. External-client, two-owner, and
fresh continuity paths remain `PARTIAL` or `BLOCKED` until their real surfaces are exercised.

## Release And Runtime Evidence

- Before acceptance: zero queued/running runs, nonterminal provider requests, active provider leases,
  delivering callbacks, and rootless worker containers.
- The activation transaction reported `committed_after_explicit_browser_acceptance` only after local
  release health, canary-edge provenance, and stable-endpoint equality passed.
- After acceptance: runtime, UI, and MCP services were active; all three reported the exact sealed
  release provenance; UI nested runtime provenance matched; stable HTTPS still returned its original
  authenticated redirect.
- Browser refresh served the expected revisioned stylesheet and application module. Product-page
  console checks were clean; repeated extension message-channel noise on artifact/navigation tabs was
  classified as browser-extension noise because it originated from the installed browser extension
  and did not correspond to a product request or visible failure.

## Automated Evidence

- Complete Glass Drive server/UI file: **222 passed**.
- Parent manifest/bootstrap boundary: **47 passed**.
- Focused runtime/UI/compiler/security regressions from the owning implementation report: PASS.
- JavaScript syntax, Python compilation, nested/parent diff checks, public-safety scan, sealed release
  verification, and independent release-helper reviews: PASS.

## Remaining Gates

- Real Codex and Claude MCP OAuth consent, tool call, refresh/restart persistence, and unhappy paths.
- Hosted two-owner/wrong-owner denial on the exact installed release.
- Hosted duplicate/template reapproval with two users and a real scheduled fire.
- Fresh public bootstrap/install and upgrade-continuity acceptance.
- The corrected terminal failed/cancelled/interrupted Pause policy is automated and the earlier escaped
  failure/recovery is recorded, but a deliberately failed post-fix hosted mission was not induced in
  this accepted run; `GHWS-006` therefore remains PARTIAL.

These remaining items are not represented as passed by this report.

## User-Grade Evidence

- Surface exercised: authenticated headed Chromium browser on the isolated hosted Workspaces canary,
  backed by the exact sealed runtime/UI/MCP release.
- Real user path: recover login, open Workspaces and Watch, expand completed output, open and download
  artifacts, run two provider-backed follow-ups, observe the live desktop, and refresh.
- Visible outcome: direct signed output, view-only stream, completed-state teardown, responsive
  navigation, provider reuse, and external-AI presentation behaved as expected.
- Expanded/detail state: completed output, artifact landings, Connections, and Automatic/Manual setup
  states were opened and inspected.
- Persistence/reload result: refresh preserved Completed state, both synthetic files, modern actions,
  and the installed cache revision.
- Local/external prerequisite state: hosted runtime and provider account were available; external MCP
  clients, two-owner denial, and fresh install/upgrade prerequisites were not part of the canary.
- Evidence retrieval classification, if applicable: unrun external-client and two-owner checks were
  local prerequisite unavailable, not successful-empty results.
- Fallback path, if applicable: no supporting-evidence substitute was accepted for the unrun real
  MCP-client, two-owner, or continuity paths.
- Backend/log/DB confirmation: sanitized release health, provenance, queue/lease/container counts,
  requests, and persisted artifact state agreed with the browser.
- Final model/runtime wording check: this report claims only the accepted hosted flows and labels all
  unrun release gates `PARTIAL` or `BLOCKED`.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Findings

- Defects: no blocker remained in the accepted hosted canary; the earlier rejected defects are
  recorded in the local-browser report and reusable cases.
- Regressions: none observed in the accepted navigation, output, provider mission, preview, refresh,
  responsive, or setup-presentation flows.
- Flakes: browser-extension message-channel noise was isolated from product requests and visible UI.
- Environment issues: external MCP clients, exact two-owner setup, and fresh install/upgrade were not
  in this canary environment.
- Residual risks: the explicit remaining gates above must run before full installed-release signoff.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
- [x] Raw browser, cloud, and database evidence remains private and untracked.
