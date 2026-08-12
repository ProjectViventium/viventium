# Workspace Control Room Hosted Canary QA — 2026-08-12

## Summary

- Result: **PASS for the isolated hosted Workspaces/provider-mission and external-client canary;
  PARTIAL for installed two-owner denial, a second healthy provider account, and fresh
  bootstrap/upgrade continuity**.
- The exact sealed candidate was accepted only after the authenticated browser run and a zero-work
  release gate; the stable endpoint remained unchanged.
- All browser content and prompts were synthetic and public-safe. No private host, account, worker,
  project, token, callback, or local-machine value is recorded here.

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
| Real external clients | PASS | Codex `0.147.0` and Claude Code `2.1.220` each used the deployment-generated configuration, completed organization OAuth in the designated existing browser profile, listed the same owner-scoped workspaces, and repeated the tool call from a second fresh client process after acceptance. |
| Conversational control | PASS | From a fresh Claude Code conversation, the user-facing controller listed workspaces, inspected the selected workspace, continued it with a synthetic instruction, and returned an exact success marker. Workspaces then showed the new artifact and exact content after completion and refresh. |
| OAuth unhappy paths | PASS for the exercised matrix | An expired authorization required a fresh login, an occupied loopback callback port failed before consent, and a wrong-scope attempt ended at the identity provider with `invalid_client`. None produced a usable token or GlassHive tool result. The last result proves fail-closed behavior, not that scope validation specifically caused the rejection; broader wrong-audience/client/tenant verifier boundaries remain automated rather than real-client browser runs. |
| Parallel mixed-account state | PARTIAL | The dashboard displayed and controlled simultaneous personal and deployment-managed work. The personal mission completed; the deployment-managed mission surfaced its upstream `401` instead of claiming success. A second healthy deployment account was not available, so two successful concurrent provider missions remain open operational QA. |

## Release And Runtime Evidence

- Before acceptance: zero queued/running runs, nonterminal provider requests, active provider leases,
  delivering callbacks, and rootless worker containers.
- The activation transaction reported `committed_after_explicit_browser_acceptance` only after local
  release health, canary-edge provenance, and stable-endpoint equality passed.
- After acceptance: runtime, UI, and MCP services were active; all three reported the exact sealed
  release provenance; UI nested runtime provenance matched; stable HTTPS still returned its original
  authenticated redirect.
- A post-accept idempotent release invocation repeated exact local and edge provenance checks, and
  fresh Codex and Claude processes repeated the real MCP call without reconfiguration.
- Browser refresh served the expected revisioned stylesheet and application module. No app-origin
  exception or visible failure occurred. Repeated message-channel errors were classified as
  browser-extension noise because they came from the installed extension and did not correspond to a
  product request or visible failure.

## Automated Evidence

- Complete Glass Drive server/UI file: **222 passed**.
- Parent manifest/bootstrap boundary: **47 passed**.
- MCP OAuth file: **27 passed**. The three affected compiler/schema gates: **3 passed**.
- Direct-conversation compatibility guards: **4 passed**; installed web/channel/voice acceptance
  remains owned by its existing QA gate and was not relabeled as a live pass here.
- A broad parent compiler-file rerun was attempted but is not a clean acceptance signal in the
  component-sparse review worktree: the nested LibreChat checkout is intentionally absent and
  unrelated existing cases fail. The owning focused compiler gates above pass.
- Focused runtime/UI/security regressions from the owning implementation report: PASS.
- JavaScript syntax, Python compilation, nested/parent diff checks, public-safety scan, sealed release
  verification, and independent release-helper reviews: PASS.

## Remaining Gates

- Hosted two-owner/wrong-owner denial on the exact installed release.
- Hosted duplicate/template reapproval with two users and a real scheduled fire.
- Reconnect or replace the unhealthy deployment-managed provider credential, then repeat two
  successful provider missions concurrently; the personal-subscription route itself passed.
- Fresh public bootstrap/install and upgrade-continuity acceptance.
- The corrected terminal failed/cancelled/interrupted Pause policy is automated and the earlier escaped
  failure/recovery is recorded, but a deliberately failed post-fix hosted mission was not induced in
  this accepted run; `GHWS-006` therefore remains PARTIAL.

These remaining items are not represented as passed by this report.

## Public-Safety Review

- [x] Synthetic prompts, filenames, states, and labels only.
- [x] No private hostname, email, raw identifiers, secret, callback value, local path, or screenshot.
- [x] No client/customer names or unrelated project context.
- [x] Raw browser, Azure, and database evidence remained private and untracked.
