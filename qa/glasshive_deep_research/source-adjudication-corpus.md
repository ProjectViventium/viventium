# Public-Safe Source Adjudication Corpus

This corpus gives reviewers a reusable, non-private way to exercise the source-adjudication workflow
from `source-adjudication.md`. It is QA evidence only. It must not become runtime logic, prompt
matching, or a domain-specific rubric.

## How To Use

1. Copy one case into `source-adjudication.md`.
2. Check the linked primary/public source.
3. Mark `EXCLUDED`, `FLAGGED`, `KEPT`, or `UNRESOLVED`.
4. Record whether the worker artifact needs a correction, a caveat, or no change.
5. If a worker repeatedly mishandles this generic class, add verifier or prompt-contract coverage
   for the class, not a rule about the named source.

## Cases

| Case ID | Constraint | Worker Claim Under Review | Primary/Public Source To Check | Expected Decision | What This Tests |
| --- | --- | --- | --- | --- | --- |
| `SRC-ADJ-001` | Use final standards or recommendations only; drafts may be mentioned only as rejected/out-of-scope evidence. | "WCAG 2.2 should be excluded because it is only a draft." | W3C WCAG 2.2, current Recommendation page: `https://www.w3.org/TR/WCAG22/` | `KEPT` if the artifact uses WCAG 2.2 as a final Recommendation; `FLAGGED` if the artifact also relied on editor's drafts without caveat. | Correcting an exclusion based on stale status. |
| `SRC-ADJ-002` | Separate final frameworks from later concept notes and profiles; do not treat related future updates as the same source. | "NIST AI RMF 1.0 is a 2026 framework update." | NIST AI RMF page: `https://www.nist.gov/itl/ai-risk-management-framework` | `FLAGGED` or `EXCLUDED` for the specific 2026-update claim; `KEPT` for AI RMF 1.0 only when dated and described as the released framework. | Preventing date/scope blending between an original source and later related materials. |
| `SRC-ADJ-003` | Version-specific claims must match the source version exactly. | "PEP 703 proves optional no-GIL support belongs in Python 3.12." | PEP 703: `https://peps.python.org/pep-0703/` | `FLAGGED` if the result needs a version correction; `EXCLUDED` if the wrong version materially changes the recommendation. | Version-boundary adjudication without hardcoding a technology domain. |

## Acceptance Notes

- Passing this corpus means the reviewer records the right decision class and rationale; it does not
  prove the runtime can research every domain.
- These cases are intentionally general: stale status, source/date blending, and version mismatch.
- Add new cases only when they represent a reusable failure class. Do not add cases named after a
  private customer, private prompt, or one-off benchmark entity.
