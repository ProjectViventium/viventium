# Prompt Architecture QA

This directory is the public-safe QA source of truth for prompt architecture, token efficiency,
prompt-frame observability, MCP instruction ownership, structured follow-up decisioning, prompt
compaction, memory-context tiering, drift gates, and browser QA.

Raw prompts, connected-account payloads, transcripts, local paths, user identifiers, account
tokens, screenshots with private content, and full model responses stay in the private user-data
backup/eval run. Public artifacts in this directory may contain only synthetic prompts, redacted
examples, aggregate metrics, hashes, counts, pass/fail status, and sanitized findings.

## Safety Rules

- Use the local QA account for browser and model-route QA.
- Preserve QA login identity and existing QA history.
- Do not copy sessions, active cookies, or login state.
- Do not overwrite QA conversations or owner data.
- External connected-account evals are read-only.
- Do not add runtime string, keyword, prompt-text, provider-name, tool-substring, or user-intent
  heuristics.
- Treat MCP/tool descriptions, structured metadata, config fields, and model-visible context as the
  ownership surface for cognitive behavior.
- Stop compaction if exact-model evals regress tool routing, truthfulness, follow-up suppression,
  voice behavior, memory/recall behavior, or Viventium identity.

## Phase Gates

| Phase | Public evidence required before next phase |
| --- | --- |
| 0. Branch, backup, QA parity | Redacted backup manifest, dry-run parity plan, QA post-verify summary |
| 1. Docs and ownership audit | Provider-doc index, prompt ownership map, current prompt token baseline |
| 2. Observability | Redaction tests, prompt-frame metadata tests, no-output-regression evals |
| 3. MCP instruction readiness | MCP description checklist tests and additive eval report |
| 3.5. Productivity MCP readiness | MS365/Google instruction ownership, read-only/write/auth/failure contracts, and additive eval report |
| 4. Exact-model eval harness | No-mock QA account eval runner and baseline aggregate metrics |
| 5. Structured follow-up | Old-vs-new exact-model follow-up eval report and rollback flag proof |
| 6. Main prompt compaction | Side-by-side current-vs-compact report with no behavioral regressions |
| 7. Memory tiering | Memory token telemetry, recall preservation evals, memory doc update |
| 8. Drift/status/browser QA | Fail-closed drift tests, connected-account status tests, Playwright report |

## Report Name Mapping

Some early reports were created before the rollout numbering stabilized. Treat files named
`phase-5-prompt-registry-*` as the prompt-registry implementation slice that supports Phase 0-2,
not as approval to start the doc-49 Phase 5 structured follow-up work. Exact-model reports named
`phase-4-*` are completion baselines unless they explicitly include semantic grader results.

## Prompt Registry

The managed prompt source tree is
`viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/`. Public QA may reference prompt IDs,
hashes, owners, targets, token counts, and redacted examples. Raw assembled prompt/response evidence
belongs only in the private prompt-observability directory.

## Eval Families

The canonical synthetic prompt bank lives in [evals/prompt-bank.json](evals/prompt-bank.json).
Private eval runners may enrich those cases with QA-account live context, but public reports must
only store redacted examples and aggregate metrics.
