# 2026-05-12 Meeting Transcript Inventory, Sidecar, And Failure Observability QA

## Scope

Validated the follow-up hardening for meeting transcript recall:

- source-backed transcript inventory / TOC for broad list questions
- deterministic sidecar ignore globs for downloader bookkeeping
- redacted failure artifacts for failed memory-hardening runs
- runtime attachment of `meeting_inventory:*` alongside summary artifacts in normal summary mode

## Evidence

- `cd viventium_v0_4/LibreChat/api && npm test -- --runInBand test/scripts/viventium-memory-hardening.test.js test/app/clients/tools/util/fileSearch.test.js`
  - Result: 79 passed.
- `cd viventium_v0_4/LibreChat/packages/api && npx jest --runInBand --watch=false src/agents/meetingTranscripts.test.ts src/agents/__tests__/initialize.test.ts`
  - Result: 25 passed.
- `node qa/meeting-transcript-memory/evals/run-evals.cjs`
  - Result: 10 passed, 0 failed.
- `cd viventium_v0_4/LibreChat/packages/data-schemas && npm run build`
  - Result: passed.
- `cd viventium_v0_4/LibreChat/packages/api && npm run build`
  - Result: passed with the existing TypeScript warning about `req.user` possibly undefined in `src/agents/initialize.ts`.

## Findings

- The transcript inventory belongs in meeting transcript recall/RAG, not saved memory. It is derived,
  source-scoped, and regenerated from current processed summary metadata.
- The summarizer owns semantic inventory fields. Runtime only stores and formats them.
- Source-folder sidecar prevention is path/lifecycle configuration, not transcript-content
  classification.
- The inventory is source-backed for broad list questions but ranked behind strong focused summary
  hits on narrow detail questions.
- Default ignores now cover hidden files/directories, temp/download partials, and common `state/`
  sidecar folders; operator globs remain available for downloader-specific files.
- Failed runs now leave inspectable redacted artifacts instead of empty run directories.

## Residual Risk

- This pass proves the CLI/tool/runtime contracts with synthetic fixtures and unit-level runtime
  attachment tests. A logged-in browser QA pass against the local test account should still be run
  before release signoff for the full visible chat surface.
