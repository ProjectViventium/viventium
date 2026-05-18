<!-- qa-evidence-exempt: review-summary artifact; companion run report holds the standard evidence template. -->
# ClaudeViv Feature Use-Case QA Review Summary - 2026-05-18

## Summary

- Reviewer: local ClaudeViv structured review, review-only.
- Result: partially confirmed before follow-up; follow-up changes completed in this repair.
- Scope: product-wide natural user use-case QA contract, escaped voice + web-search case ownership,
  public-safety posture, and simplicity of the QA structure.

## ClaudeViv Findings And Follow-Up

| Finding | ClaudeViv Severity | Follow-up completed |
| --- | --- | --- |
| Per-feature checklist sections could pass with generic placeholder rows. | High | Added `test_natural_user_use_case_checklists_reject_generic_placeholder_rows` and replaced mechanically generic rows with rows tied to actual feature case IDs and names. |
| Escaped voice + web-search case was under-promoted across affected owners. | Medium | Added cases in `qa/web-search-telegram/`, `qa/agent-config-continuity/`, `qa/config-alignment/`, and `qa/citation-rendering/`; expanded the release test to require escaped-case phrases in all affected owners. |
| Cataloged-but-unrun backlog had no drain pressure. | Medium | Added a 90-day staleness gate for `NOT YET RUN (cataloged YYYY-MM-DD...)` case rows. |
| Playwright login-page smoke could be misread as real-user proof. | Low | Reworded the QA-system report to label Playwright as unauthenticated smoke only, with Chrome/computer-use as the real observed surface. |
| Run-report v2 template is heavy and partly duplicative. | Low | Recorded as a simplification risk; no template shrink in this pass because the user asked for stronger enforcement first. |

## Verification

- `tests/release/test_qa_operating_contract.py`: 21 passed after the ClaudeViv follow-up fixes.
- ClaudeViv was treated as supporting review, not as proof that the product web-search path is fixed.
- The product search/voice path remains marked `FAIL` or `PARTIAL` until Docker-backed local search
  services or hosted providers are available and a full signed-in browser/voice rerun passes.

## Public-Safety Review

- This summary uses repo-relative paths and sanitized evidence only.
- It contains no raw logs, raw DB rows, screenshots, account identifiers, local absolute paths,
  message/conversation/call/session IDs, provider request IDs, or secrets.
