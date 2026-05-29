# Conversation Recall RAG QA Cases

## Case ID Convention

Use stable `RAG-NNN` IDs for conversation recall rag cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `RAG-001` | Recall answers are grounded in retrieved conversation/RAG evidence and omit unsupported live facts. | User-visible behavior matches source, docs, persisted state, and logs | browser chat, RAG API, embeddings preflight, logs | `tests/release/test_rag_api_override_contract.py` plus user-grade QA when visible | PARTIAL 2026-05-27 ([follow-up report](../scheduling-cortex/reports/2026-05-27-glasshive-stale-project-rag-rca.md)); RAG API, Ollama embeddings, PGVector, and transcript vector presence were repaired, but browser chat recall/source grounding was not rerun |
| `RAG-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-05-27 ([report](../memory-hardening/reports/2026-05-27-nightly-routines-health-review.md)); report summarizes degraded RAG state without raw private runtime data |
| `RAG-003` | Background conversation-recall maintenance must not starve live recall search during voice calls. | Voice users get either fast grounded recall or an honest fast degraded result, not a 8-30s tool stall. | voice call, RAG API, vector DB, embeddings service, logs | Synthetic active-call recall/query harness plus RAG queue and voice latency logs | PARTIAL 2026-05-21 ([report](reports/2026-05-21-voice-call-recall-latency-rca.md)); RCA proved starvation risk, product fix not yet applied |

## `RAG-001` - Core User Flow

- Requirement: Recall answers are grounded in retrieved conversation/RAG evidence and omit unsupported live facts.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_rag_api_override_contract.py` plus any narrower feature tests discovered during implementation.
- Last run: PARTIAL 2026-05-27
  ([follow-up report](../scheduling-cortex/reports/2026-05-27-glasshive-stale-project-rag-rca.md));
  RAG API health returned `UP`, Ollama had the configured embedding model, PGVector was running with
  vector tables, and transcript vector presence completed with zero missing vectors. Browser chat
  recall/source grounding was not rerun in this repair pass.

## `RAG-002` - Public-Safe Evidence Record

- Requirement: public QA artifacts must be reproducible and free of secrets, personal data, local paths, raw IDs, and private screenshots.
- Risk covered: a useful local QA run cannot be safely reviewed or published.
- Preconditions: a dated QA report is created for this feature.
- Steps:
  1. Review the report and related diffs for local absolute paths, account identifiers, tokens, raw logs, raw DB rows, private chats, and screenshots with private content.
  2. Keep raw/private evidence outside the public repo and summarize only public-safe counts, statuses, hashes, and conclusions.
  3. Link the report back to this case and the owning requirement doc.
- Expected result: the public report proves the behavior without leaking private/local data.
- Forbidden result: a report includes private transcripts, account identifiers, raw runtime dumps, local home paths, tokens, or secret-bearing command lines.
- Evidence to capture: public-safety scan result and link to the sanitized report.
- Automation: public-safety pattern scan plus relevant release tests.
- Last run: PASS 2026-05-27
  ([report](../memory-hardening/reports/2026-05-27-nightly-routines-health-review.md)); the public
  report summarizes degraded RAG state without raw private runtime data.

## `RAG-003` - Live Recall Search During Background Maintenance

- Requirement: background conversation-recall maintenance must not starve live recall search during voice calls.
- Risk covered: a full-corpus background embed job monopolizes the local embedding path and causes user-facing `file_search` to time out.
- Preconditions: local Viventium runtime is running with synthetic conversation-recall corpus data, RAG API, vector DB, and local embeddings enabled.
- Steps:
  1. Start or simulate a background conversation-recall corpus refresh using synthetic non-personal data.
  2. During the refresh, issue a voice-surface recall query that makes the model call `file_search`.
  3. Capture voice latency, RAG queue/upload/query timing, and returned model/tool result.
  4. Repeat after the fix with background maintenance active.
- Expected result: live recall query returns grounded evidence or a clear degraded result inside the configured voice budget.
- Forbidden result: live voice response waits for the full background embed timeout, silently drops recall, or reports success while vector search timed out.
- Evidence to capture: sanitized voice request timing, RAG query timing, maintenance queue timing, DB corpus metadata, and visible/user-facing result.
- Automation: add a synthetic active-maintenance/file-search latency harness before claiming fixed.
- Last run: PARTIAL 2026-05-21 ([report](reports/2026-05-21-voice-call-recall-latency-rca.md)); live logs proved 8s recall query and 30s transcript query timeouts while background recall uploads were active.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Conversation Recall Rag. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `RAG-UC-001` | On browser chat, RAG API, embeddings preflight, logs, verify that recall answers are grounded in retrieved conversation/RAG evidence and omit unsupported live facts. | owning requirement for `RAG-001` / `RAG-001` | browser chat, RAG API, embeddings preflight, logs | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to RAG-001. | User-visible behavior matches source, docs, persisted state, and logs | PARTIAL 2026-05-27 ([follow-up report](../scheduling-cortex/reports/2026-05-27-glasshive-stale-project-rag-rca.md)); RAG/vector service health and transcript vector presence now pass, but browser recall signoff remains pending |
| `RAG-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `RAG-002` / `RAG-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to RAG-002. | The user sees an honest setup, retry, or degraded-state result for RAG-002; no fake success is accepted. | PASS 2026-05-27 ([report](../memory-hardening/reports/2026-05-27-nightly-routines-health-review.md)) |
| `RAG-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `RAG-002` / `RAG-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to RAG-002. | RAG-002 remains correct after the persistence or parity step and final wording matches evidence. | PASS 2026-05-27 ([report](../memory-hardening/reports/2026-05-27-nightly-routines-health-review.md)) |
| `RAG-UC-004` | During a voice call, ask for earlier conversation or transcript recall while a background recall refresh is active. | owning requirement for `RAG-003` / `RAG-003` | voice call, RAG API, vector DB, embeddings service, logs | Voice timing logs, RAG queue/upload/query logs, DB corpus metadata, and visible/user-facing result. | The user gets fast grounded recall or a clear fast degraded response; no 8-30s recall/tool stall. | PARTIAL 2026-05-21 ([report](reports/2026-05-21-voice-call-recall-latency-rca.md)); RCA only, fix not yet applied |

## Release Test Traceability

- `tests/release/test_ollama_embeddings_prereqs.py`
- `tests/release/test_rag_api_override_contract.py`
- `tests/release/test_rag_compose_resource_guardrails.py`
