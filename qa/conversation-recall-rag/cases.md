# Conversation Recall RAG QA Cases

## Case ID Convention

Use stable `RAG-NNN` IDs for conversation recall rag cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `RAG-001` | Recall answers are grounded in retrieved conversation/RAG evidence and omit unsupported live facts. | User-visible behavior matches source, docs, persisted state, and logs | browser chat, RAG API, embeddings preflight, logs | `tests/release/test_rag_api_override_contract.py` plus user-grade QA when visible | PASS-SERVICE/PROOF GAP 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); generated config expected local RAG, `/health` returned `UP`, Docker-backed prerequisites were reachable, and browser recall/source grounding remains unrun |
| `RAG-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); report summarizes recovered RAG service health and the remaining browser-proof gap without raw private runtime data |
| `RAG-003` | Background conversation-recall maintenance must not starve live recall search during voice calls. | Voice users get either fast grounded recall or an honest fast degraded result, not a 8-30s tool stall. | voice call, RAG API, vector DB, embeddings service, logs | Synthetic active-call recall/query harness plus RAG queue and voice latency logs | PARTIAL 2026-05-21 ([report](reports/2026-05-21-voice-call-recall-latency-rca.md)); RCA proved starvation risk, product fix not yet applied |
| `RAG-004` | Planned Easy Docker and Custom Settings Recall/RAG opt-in must stay honest about Docker/Ollama/vector prerequisites; Native Easy must say it is not packaged. | A new Native user reaches chat without a false failure, while a Docker-profile user can opt in and see exact readiness/degraded state before recall is called ready. | installer wizard, preflight, generated env, RAG API, vector DB, browser recall | `test_wizard.py`, `test_install_summary.py`, `test_ollama_embeddings_prereqs.py`, user-grade browser recall QA | PASS-SERVICE/PARTIAL-USER 2026-07-21; Docker source-candidate opt-in, doctor, status, synthetic embed/query, and restart persistence pass in an isolated no-host-share Docker daemon; the Docker artifact is not shipped and browser model-answer proof remains unrun |
| `RAG-005` | Lexical and vector recall run together and fail independently; lexical source hits preserve bounded adjacent-turn context through one batched expansion. | Exact names/recent events remain recoverable during vector degradation without suppressing healthy semantic evidence, splitting one natural event across isolated messages, or issuing per-hit before/after queries. | `file_search`, Mongo lexical rescue, RAG API, browser/voice recall | focused hybrid/context/query-count regressions plus isolated-account recall QA | PASS-AUTOMATED/PARTIAL 2026-07-20; focused memory/recall API 137/137, complete API 3,365 pass/19 skip, data schemas 405 pass/3 skip plus build; dedicated isolated-account browser and audible voice proof is NOT RUN |
| `RAG-006` | RAG health and recovery are semantic, dependency-aware, serialized, and portable to an explicitly selected no-host-share Docker daemon. | Recall is never called healthy because a DOWN tuple arrived with HTTP 200, concurrent helpers cannot thrash one Compose project, and remote daemon binds do not touch unrelated client or daemon paths. | RAG route, PGVector/RAG Compose healthchecks, launcher recovery | `test_rag_api_override_contract.py`, compose validation, shell syntax | PASS-LIVE 2026-07-20; 20 parent contracts, 5 nested Compose/dependency contracts, semantic HTTP 200 `UP`, long-bind inspection, product-owned daemon namespace, and supported restart/query persistence pass |
| `RAG-007` | PGVector is restart-persistent derived state, but snapshots and independent restores must require rebuild from restored canonical state. | Ordinary restart retains Recall; independent restore never presents copied/stale vectors as current. | snapshot, restore, RAG API, PGVector bind, continuity markers | continuity bundle validation plus synthetic live query | PASS-RESTART/PARTIAL-REBUILD 2026-07-20; pre/post supported restart query returned both synthetic facts, complete snapshot and independent restore passed, restored target contained 7 nonempty Mongo collections and an explicit rebuild-required marker; actual restored-corpus rebuild and browser answer remain unrun |

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
- Last run: PASS/PARTIAL-REPAIRED 2026-06-07
  ([repair follow-up](../memory-hardening/reports/2026-06-07-nightly-repair-follow-up.md));
  generated config expected `localhost:8110`, the live container had lost its host binding after a
  Docker-side failure, and the launcher now has a regression-covered self-heal for that binding
  mismatch. After restarting Docker and bringing up the declared RAG compose graph, `/health`
  returned `UP` on the generated port. Browser recall/source grounding was not rerun in this repair
  pass and remains a separate RAG user-path gate, not evidence that the nightly RAG service is down.

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

## `RAG-004` - Installer Recall/RAG Opt-In Readiness

- Requirement: Conversation Recall/RAG is core to the cognitive system but remains guided opt-in
  because it requires Docker/Ollama/vector resource consent.
- Risk covered: Easy install turns recall on from ambient Docker detection, or status calls recall
  ready while RAG API, embeddings, vector DB, or browser recall grounding is missing.
- Preconditions: synthetic installer configs can simulate Docker present/missing and RAG enabled/
  disabled; user-grade proof needs a local runtime with public-safe recall content.
- Steps:
  1. Build Easy Install configs with Docker absent and present; confirm recall remains off unless the
     user explicitly opts in.
  2. When opted in without Docker, confirm preflight/readiness tells the user Docker/Ollama will be
     required before readiness.
  3. Compile generated env and verify RAG/embeddings keys align with the opt-in state.
  4. Run status and confirm `Conversation Recall/RAG` is `Needs setup`, `Ready`, or `Degraded`
     with a concrete next action.
  5. For release signoff, ask a browser recall question and verify grounded visible sources plus
     backend/vector evidence.
- Expected result: skipping recall is not a failure; opting in requires real prerequisites and
  browser recall proof before full readiness.
- Forbidden result: Docker presence alone enables recall, missing vectors are hidden, or public QA
  includes private conversations/query text/screenshots.
- Evidence to capture: wizard choices, generated env key summary, status row, RAG/vector health,
  browser visible result, and public-safety scan.
- Last run: PASS-SERVICE/PARTIAL-USER 2026-07-20; supported Easy Install with Recall enabled
  reached API, web, PGVector, and RAG health in an isolated no-host-share daemon. A synthetic file
  embedded and queried successfully, and both distinctive facts survived supported stop/launch.
  Browser model-answer grounding remains unrun because this lane did not bind a synthetic chat
  provider.

## `RAG-005` - Hybrid Retrieval Failure Isolation

- Seed synthetic prior-conversation evidence with both exact/named-entity and semantic phrasing.
- Confirm lexical hits do not skip vector calls and fused results contain both channels.
- Split a synthetic event across adjacent eligible messages and confirm a matching source hit returns
  bounded same-conversation context containing the complete event.
- Select four source hits and prove their context is expanded by one bounded aggregate/facet
  operation, not up to eight overlapping before/after reads. Force expansion failure and prove the
  primary authorized hits remain available.
- Prime an existing authorized corpus while vector health is degraded and confirm the transient
  source-only mode survives DB metadata hydration without changing authorization-owned fields.
- Fail lexical Mongo retrieval while vector succeeds, then fail vector retrieval while lexical
  succeeds. Finally fail both channels.
- Expected: either healthy channel remains usable; both failures return an operational retrieval
  failure, not “nothing found”; current conversation, active message, and Listen-Only rows stay out.
- Forbidden: first lexical hit short-circuits vector search, one rejected promise discards the other
  channel, a provider outage is represented as a successful empty result, or context expansion
  crosses conversations or admits ineligible transcript/derived rows.
- Evidence: focused tool tests, structured error/latency logs, source artifacts, visible grounded
  answer, and DB/RAG health correlation.
- Last run: PASS-AUTOMATED/PARTIAL 2026-07-20; focused memory/recall API 137/137, complete API
  3,365 pass/19 skip, and data schemas 405 pass/3 skip plus build. Dedicated isolated-account browser
  grounding, audible delivery, linked-chat reload, and runtime-corpus cleanup remain NOT RUN.

## `RAG-006` - Truthful Health And Serialized Recovery

- Return healthy and unhealthy synthetic vector states through the overridden RAG `/health` route.
- Probe `UP`, `DOWN`, tuple-shaped legacy, malformed, and unreachable responses through the launcher.
- Validate PGVector health ordering and run two synthetic lock owners against the same compose lock.
- Simulate an uninspectable Compose container id and confirm recovery stops with a Docker-level
  blocker rather than repeatedly force-recreating.
- Launch from different caller environments and confirm every RAG Compose command selects the
  canonical project; a healthy foreign-project port is an ownership conflict.
- Expected: only semantic `UP` passes; DOWN is HTTP 503; one owner mutates Compose; RAG waits for
  PGVector health; phantom state is explicit.
- Forbidden: HTTP-only green, tuple body with status 200, concurrent compose mutation, infinite
  retry/recreate, or deleting vector state as automated recovery.
- Last run: PASS-LIVE 2026-07-20; 20 parent behavioral/contract tests and 5 nested Compose/dependency
  contracts pass. A no-host-share daemon used long bind syntax for a product-owned PostgreSQL path
  and a byte-identical read-only route mirror, reached semantic HTTP 200 `UP`, and retained both
  synthetic facts across the supported stop/launch lifecycle. Browser recall grounding is tracked
  separately under `RAG-004`.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Conversation Recall Rag. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `RAG-UC-001` | On browser chat, RAG API, embeddings preflight, logs, verify that recall answers are grounded in retrieved conversation/RAG evidence and omit unsupported live facts. | owning requirement for `RAG-001` / `RAG-001` | browser chat, RAG API, embeddings preflight, logs | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to RAG-001. | User-visible behavior matches source, docs, persisted state, and logs | PASS-SERVICE/PROOF GAP 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)); service health passed and browser recall signoff remains unrun |
| `RAG-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `RAG-002` / `RAG-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to RAG-002. | The user sees an honest setup, retry, or degraded-state result for RAG-002; no fake success is accepted. | PASS 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)) |
| `RAG-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `RAG-002` / `RAG-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to RAG-002. | RAG-002 remains correct after the persistence or parity step and final wording matches evidence. | PASS 2026-06-11 ([nightly review](../memory-hardening/reports/2026-06-11-nightly-routines-health-review.md)) |
| `RAG-UC-004` | During a voice call, ask for earlier conversation or transcript recall while a background recall refresh is active. | owning requirement for `RAG-003` / `RAG-003` | voice call, RAG API, vector DB, embeddings service, logs | Voice timing logs, RAG queue/upload/query logs, DB corpus metadata, and visible/user-facing result. | The user gets fast grounded recall or a clear fast degraded response; no 8-30s recall/tool stall. | PARTIAL 2026-05-21 ([report](reports/2026-05-21-voice-call-recall-latency-rca.md)); RCA only, fix not yet applied |
| `RAG-UC-005` | Confirm Native Easy says Recall/RAG is not packaged; in the planned Easy Docker or Custom Settings profile, skip it, opt in without prerequisites, and opt in with services healthy. | `39_Installer_and_Config_Compiler.md` / `RAG-004`, `INST-004` | installer wizard, preflight, status, RAG API/vector DB, browser chat | Wizard output, generated env keys, preflight/degraded state, RAG/vector health, browser-visible grounded answer. | Native wording is truthful; Docker Recall is pending when skipped, prerequisite-gated when opted in, and only Ready after service and browser grounding proof. | PASS-SERVICE/PARTIAL-USER 2026-07-21; source-candidate opt-in and synthetic API retrieval pass on no-host-share Docker, while the shipped Docker artifact and browser model answer remain unrun |
| `RAG-UC-006` | Mention a synthetic event in an isolated channel without explicitly saving it, then ask about it in a new voice conversation. | `32_Conversation_Recall_RAG.md` / `RAG-005` | isolated channel, Modern Playground voice, `file_search` | fixture message, recall corpus/freshness, tool sources, transcript/audio, logs | Voice visibly and audibly recovers the event through recall; saved memory is confirmed absent. | PARTIAL 2026-07-14; synthetic retrieval regressions pass, but the dedicated isolated-account channel-to-voice journey is NOT RUN |
| `RAG-UC-007` | Start or inspect local Recall while PGVector is down or Compose state is inconsistent. | `32_Conversation_Recall_RAG.md` / `RAG-006` | launcher/status, RAG `/health`, Docker Compose | HTTP status/body, semantic probe result, compose health, serialized recovery log | Recall stays degraded with one actionable Docker blocker; no false ready state or repeated repair loop. | PASS-LIVE 2026-07-20; semantic health, long-bind ownership, isolated restart, and query persistence pass |
| `RAG-UC-008` | Restart an enabled local Recall install, then snapshot and restore into an independent empty target. | `32_Conversation_Recall_RAG.md` / `RAG-007` | CLI stop/launch, snapshot, restore, RAG API | pre/post query, bundle manifest, restored Mongo counts, rebuild and reauth markers | Restart retains derived vectors; restore retains canonical state but explicitly blocks vector Recall until rebuild. | PASS-RESTART/PARTIAL-REBUILD 2026-07-20; complete snapshot and independent restore pass, restored target is correctly marked rebuild-required, actual rebuilt browser answer remains unrun |

## Release Test Traceability

- `tests/release/test_ollama_embeddings_prereqs.py`
- `tests/release/test_rag_api_override_contract.py`
- `tests/release/test_rag_compose_resource_guardrails.py`
