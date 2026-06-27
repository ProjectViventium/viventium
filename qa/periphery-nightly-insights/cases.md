# Periphery Nightly Insights Cases

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `PERI-001` | Current nightly executor health is classified before new insight routines are activated. | Viventium does not add prediction/risk work on top of an unknown broken substrate. | Scheduling DB, Workbench, GlassHive, callback outbox, logs | Focused scheduler/Workbench tests plus live ledger audit | PASS 2026-06-25 ([live run report](reports/2026-06-25-nightly-risk-radar-live-run.md)); canonical Workbench -> GlassHive -> callback -> ledger path completed and queues cleared; stale old/test residue remains a cleanup item |
| `PERI-002` | Private periphery artifacts use a typed `.md` plus `.json` sidecar contract. | Nightly insight is retained, inspectable, and not lost in loose scratch files. | private scratchpad folder, Workbench run details | `test_prompt_workbench.py` periphery metadata tests | PASS 2026-06-25 ([live run report](reports/2026-06-25-nightly-risk-radar-live-run.md)); live nightly produced one valid sidecar pair and happy/unhappy metadata paths passed |
| `PERI-003` | Risk/opportunity/blind-spot artifacts are not injected into the main prompt or saved-memory keys by default. | Viventium has peripheral awareness without prompt bloat or memory pollution. | prompt source, memory config, Workbench prompt, chat output | Prompt/source diff tests and memory-key assertions | PASS 2026-06-25 ([live run report](reports/2026-06-25-nightly-risk-radar-live-run.md)); artifact remains private metadata by default, no saved-memory key or main-prompt injection added |
| `PERI-004` | A private snapshot harness labels QA/test/synthetic corpus content before insight evals. | Nightly predictions are evaluated against real signal instead of QA exhaust. | private snapshot, eval harness, sanitized QA report | Snapshot classifier tests | NOT RUN - proposal documented 2026-06-24 |
| `PERI-005` | Risk radar output is evidence-cited, confidence-calibrated, stale-aware, and propose-only. | The user gets useful blind-spot/opportunity insight without hallucinated certainty. | Workbench scheduled run, artifact sidecar, memory proposals | Model evals and artifact schema checks | PARTIAL/PASS 2026-06-25 ([live run report](reports/2026-06-25-nightly-risk-radar-live-run.md)); live sidecar schema/counts and worker validation passed, private snapshot harness/model eval suite still future |
| `PERI-006` | Conscious-agent surfacing is on-demand or explicitly policy-approved, never nagging by default. | Viventium can call things out tastefully without becoming intrusive. | browser chat, Telegram if enabled, Workbench artifact read path | User-level QA plus final-answer review | NOT RUN - proposal documented 2026-06-24 |
| `PERI-007` | Health-pressure awareness shares generation/governance only; persistence is decided separately. | Health tracking can shape empathy without being reduced to a generic scratchpad note or unsafe diagnosis. | health module proposal, memory config, prompt instructions | Health eval bank once approved | NOT RUN - proposal documented 2026-06-24 |

## Natural User Use Case Checklist

Use this checklist before claiming Viventium Periphery or nightly insight work is complete. These
rows are intentionally product-specific: they protect the vision without turning it into hardcoded
chat behavior.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `PERI-UC-001` | The user opens Workbench after a nightly insight routine should have run and checks whether a private insight exists. | `53_Viventium_Periphery_Nightly_Insights.md` / `PERI-001`, `PERI-002` | Prompt Workbench run history, Scheduler ledger, GlassHive run detail | Redacted run counts, callback state, artifact sidecar hash, logs, Workbench visible state | Workbench shows a completed, failed, or skipped run with an honest reason; no private raw prompt or result leaks into public evidence. | PASS 2026-06-25 ([live run report](reports/2026-06-25-nightly-risk-radar-live-run.md)); actual Chrome Workbench shows the `risk_radar` artifact metadata/counts and keeps private bodies out of public evidence |
| `PERI-UC-002` | The user asks Viventium for blind spots, risks, opportunity costs, or strategic pressure around recent work. | `53_Viventium_Periphery_Nightly_Insights.md` / `PERI-003`, `PERI-005`, `PERI-006` | Browser chat with optional on-demand artifact access | Prompt source, memory state, private artifact metadata, model/tool trace, eval score summary | Viventium cites available evidence, labels uncertainty, avoids unsupported facts, and does not inject nightly output unless the model deliberately retrieves or the user asks. | NOT YET RUN as an on-demand read flow; generation and private metadata are PASS 2026-06-25 ([live run report](reports/2026-06-25-nightly-risk-radar-live-run.md)) |
| `PERI-UC-003` | A nightly module encounters missing scheduler, GlassHive, memory, file, or snapshot prerequisites. | `53_Viventium_Periphery_Nightly_Insights.md` / `PERI-001`, `PERI-004` | Workbench scheduled run, Scheduler health, GlassHive host worker, snapshot harness | Failure class, health/status, retry/catch-up policy, sanitized logs, no-result artifact marker | The run is classified as blocked, skipped, or degraded with a concrete reason and no invented insight. | PARTIAL 2026-06-25 ([Phase 0 report](reports/2026-06-25-phase-0-periphery-metadata.md)); malformed sidecars are classified, snapshot harness still not implemented |
| `PERI-UC-004` | The user reviews whether a nightly insight should become memory, a task, a health-pressure signal, or stay as private scratch. | `53_Viventium_Periphery_Nightly_Insights.md` / `PERI-003`, `PERI-007` | Workbench artifact review plus memory proposal surface once implemented | Memory proposal dry-run, health module state, artifact labels, approval log | Durable memory and health-pressure state are updated only through governed proposals or approved module policy; raw scratchpad text is not silently promoted. | NOT YET RUN (cataloged 2026-06-25 - proposal only) |
| `PERI-UC-005` | The user or QA reruns the same insight eval against a private snapshot corpus that includes useful signal and junk/test conversations. | `53_Viventium_Periphery_Nightly_Insights.md` / `PERI-004`, `PERI-005` | Private snapshot harness and sanitized eval report | Corpus labels, junk/test exclusion counts, output rubric, false-positive/false-negative examples | The eval proves the module resists overfitting to QA noise and reports evidence quality, confidence, staleness, and opportunity/risk value. | NOT YET RUN (cataloged 2026-06-25 - proposal only) |

## `PERI-001` - Nightly Executor Classification Gate

- Requirement: classify and repair or bound current nightly scheduled-run failures before activating
  new insight routines.
- Expected result: the failure class is named, evidence is public-safe, and the canonical scheduled
  prompt -> GlassHive -> callback -> ledger -> Workbench path is proven.
- Forbidden result: a new risk-radar schedule is added while recent Workbench failures remain
  unclassified.
- Evidence to capture: sanitized status counts, failure class, focused tests, callback backlog
  status, and visible Workbench state when applicable.

## `PERI-005` - Risk Radar Insight Quality

- Requirement: generated risks, blind spots, and opportunities must be evidence-cited and calibrated.
- Expected result: each claim is labeled as observation, inference, hypothesis, risk, opportunity,
  stale thought, or unsupported thought.
- Forbidden result: unsupported current facts, medical claims, private leakage, direct memory writes,
  or generic nagging.
- Evidence to capture: sanitized artifact schema result, eval score summary, and governed proposal
  dry-run state.
