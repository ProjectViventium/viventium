<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
# Prompt Architecture Production Readiness - 2026-05-10

## Scope

This report is the public-safe summary for the prompt architecture hardening pass. Raw local run
artifacts, browser transcripts, model payloads, and machine-local logs stay outside the public repo.

## What This Pass Covers

- Prompt registry source-of-truth plumbing and fallback drift controls.
- Runtime prompt-frame telemetry safety and public dashboard redaction.
- Background cortex activation visibility, Phase B card persistence, and user-visible error safety.
- MCP server-instruction ownership for Scheduling Cortex and GlassHive workers.
- Public/private boundary checks for generated QA artifacts.

## Current Verification

- Parent release suite: `504 passed, 2 skipped` on 2026-05-11 local / 2026-05-12 UTC.
- LibreChat focused backend background-cortex/follow-up suites: `254 passed`.
- LibreChat focused frontend cortex-card suites: `14 passed`.
- LibreChat MCP/config focused suites: `63 passed`.
- Scheduling Cortex: `85 passed`.
- GlassHive runtime: `109 passed, 3 skipped`; focused MCP/API rerun after final URL-safety patch
  passed.
- Browser-visible background-card QA: passing in the latest public-safe run. Required cards were
  visible by name, persisted after reload, stored as successful terminal insights, kept Groq-first
  activation config with no drift, and produced no critical HTTP errors.
- Latest-user activation browser QA: passing. A setup turn produced ready background cards, then a
  simple `TEST_OK` latest turn answered exactly before and after reload with no stale cortex cards.

## Public-Safe Evidence Policy

- Public QA files may contain synthetic prompts, aggregate pass/fail status, and sanitized
  implementation notes.
- Private QA files may contain raw prompts, model payloads, local account evidence, browser
  screenshots, runtime logs, database rows, and local machine paths.
- Any escaped bug must be converted into a reusable synthetic regression case under the owning
  `qa/<feature>/cases.md` file before the fix is considered production-ready.

## Remaining Gates

- Commit nested component repos first, update the parent component pins to those pushed SHAs, and
  then commit the parent release/QA/tooling slice.
- Keep PR-base public/private diff safety as an explicit review gate for the nested LibreChat PR.
- Do not mark the branch production-ready or merge if final committed diffs, pins, or browser QA
  regress from the evidence above.
