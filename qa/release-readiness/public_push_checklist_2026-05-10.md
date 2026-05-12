# Public Push Readiness Checklist - 2026-05-10

## Scope

Prepare the current local Viventium prompt-architecture, background-agent, MCP, memory, voice,
Telegram, and QA fixes for public-safe feature branches and pull requests.

This checklist is the acceptance contract for this packaging pass. It intentionally separates local
working-tree validation from pushed/reviewable Git state.

## Checklist

### Scope And Evidence

- [x] Convert the user's prompt/history into a concrete acceptance checklist.
- [x] Keep public QA artifacts hash-only and synthetic; keep raw browser transcripts, logs, account
      data, and local runtime output out of the repo.
- [x] Add durable QA entrypoints so future agents find the background-agent and release-readiness
      coverage before making claims.
- [x] Promote escaped background-card issues into reusable ACT-18/ACT-19 browser cases.
- [x] Replace business-specific browser-QA default prompt text with a generic synthetic scenario.
- [x] Keep eval runner stdout from printing absolute private artifact paths.
- [x] Update this checklist after every new final review finding until it matches the latest truth.

### Product Fixes Under Review

- [x] Make background-cortex activation failures visible through structured cortex cards instead of
      contradictory main-agent wording.
- [x] Preserve completed/error cortex parts through Phase B fallback and reload persistence.
- [x] Show multiple activated background agents by name with independent card/result state.
- [x] Keep direct-action hold decisions aware of MCP tool definitions instead of text-only prompts.
- [x] Harden GlassHive callback/deliverable metadata before it reaches public-facing artifacts.
- [x] Remove free-text GlassHive active-worker fallback matching from runtime routing.
- [x] Prevent Scheduling Cortex list/search summaries from falling back to raw stored prompt text.
- [x] Prevent GlassHive text-only active-worker failures from leaking worker/run plumbing.
- [x] Keep GlassHive callback polling state from exposing worker/run/callback identifiers.
- [x] Sanitize changed background/completion error logs so raw provider/user-adjacent payloads are not logged.
- [x] Add cleanup coverage for timed-out MCP server-instruction temporary connections.
- [x] Add full source-agent YAML promptRef resolution coverage for the sync resolver.
- [x] Harden Telegram numeric environment parsing, including max file size.
- [x] Add prompt-registry, prompt-frame, compiler, dashboard, and eval-harness tests for the prompt
      architecture baseline.
- [x] Add MCP trusted-instruction caching, timeout, and degraded-status coverage in source.
- [x] Rebuild the ignored local package API `dist/` artifact so local browser QA can reflect the MCP
      source changes; keep generated `dist/` out of the public commit.
- [x] Resolve the runtime-card guard duplication by moving the primary text into the prompt registry
      and keeping the runtime copy as fallback only.

### Line-By-Line Review And Sanitization

- [x] Parent repo diff reviewed by an independent subagent for correctness and public/private
      boundary risks.
- [x] Nested LibreChat diff reviewed by an independent subagent for correctness and public/private
      boundary risks.
- [x] First-round subagent blockers were fixed or turned into explicit open gates.
- [x] Rerun line-by-line independent public-safety review after the final doc/test/status patches.
- [x] Rerun line-by-line independent correctness/release-readiness review after the final patches.
- [x] Run Claude review-only line-by-line diff check through ClaudeViv after local Claude auth
      returned `CLAUDE_OK`.
- [x] Run ClaudeViv review-only forensic line-by-line diff check after the sanitizer/doc/Groq fixes.
- [x] Reconcile every material ClaudeViv finding before packaging: logging/doc/Groq findings were
      fixed, and the ACT-21 tracked FAIL was corrected with a passing browser rerun.

### Automated And Browser QA

- [x] Parent release tests passed after the new QA shape was added.
- [x] Nested `packages/api` full Jest suite passed after MCP/usage/config fixes.
- [x] Nested `packages/api` build passed after MCP connection and usage changes.
- [x] Nested backend focused suites passed for background cortex, GlassHive, prompt telemetry, and
      follow-up behavior.
- [x] Nested frontend focused suites passed for cortex card rendering/collapsing behavior.
- [x] Nested MCP manager tests passed in source.
- [x] Scheduling Cortex tests passed.
- [x] Telegram numeric env test passed.
- [x] Browser QA harness now verifies visible cards, reload persistence, stored DB content parts,
      terminal state, console errors, and critical HTTP errors.
- [x] Real browser QA for ACT-18/ACT-19 passed on the latest local synthetic run. The run proves
      required cards are visible, persisted after reload, and stored as successful terminal insights
      in that local QA environment; final public-release readiness still depends on clean committed
      diffs, nested pin agreement, and review-only gates.
- [x] Provider/fallback health is fixed or a working fallback model path is configured without
      exposing credentials.
- [x] Rerun browser QA after provider/fallback health is restored and save a public-safe pass report.
- [x] ACT-21 latest-user browser QA passed after narrowing the harness to the actual latest-turn
      contract: setup cards appear, the simple `TEST_OK` turn answers before and after reload, and
      no stale-history cortex cards attach to that latest turn.

### Public Push And PR Gates

- [x] `git diff --check` passes in parent and nested repos after final patches.
- [x] Public/private scans pass for added tracked lines and intended untracked artifacts.
- [x] PR-base public/private diff is safe. Final parent, LibreChat, and GlassHive PR-base scans
      found no real private values; broad-scan hits were removed or classified as synthetic test
      fixtures.
- [x] Prompt registry source tree is intentionally tracked; no required prompt source remains
      untracked.
- [x] Provider-native structured Phase B and full doc-49 runtime/source/compiled A/B/C drift gate are
      documented as post-baseline gates if not implemented in this pass.
- [x] Generated/live artifact chain is verified after packaging: source files, compiled prompt
      bundle, runtime YAML/env, running local process, nested component commit, and parent
      `components.lock.json`.
- [x] Nested LibreChat feature branch is committed and pushed to `origin`.
- [ ] Parent feature branch is committed after updating the nested component pin.
- [ ] Pull requests to `main` are opened for each changed public repo.
- [ ] Pull requests are reviewed against this checklist before merge.
- [ ] Do not merge while any production blocker remains.

## Current Known Blockers

- Parent commit, push, PR creation, and PR review/merge remain the final packaging gates.
- Client typecheck is not a clean release gate yet; Jest passes, but the broader client typecheck
  still reports existing unrelated type debt.
