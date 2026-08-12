# Periphery Nightly Insights Cases

## Case Catalog

Release runtime ownership: `tests/release/test_viventium_health_runtime.py`.

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `PERI-001` | Current nightly executor health is classified before new insight routines are activated. | Viventium does not add prediction/risk work on top of an unknown broken substrate. | Fixture Scheduling DB, Workbench, GlassHive, callback outbox, logs | Focused scheduler/Workbench tests plus synthetic ledger audit | PASS-AUTOMATED/PARTIAL 2026-07-18; executor/callback/parent-child ledger fixtures pass, isolated automatic run NOT RUN |
| `PERI-002` | Private periphery artifacts use a typed `.md` plus `.json` sidecar contract. | Nightly insight is retained, inspectable, and not lost in loose scratch files. | isolated scratchpad fixture, Workbench run details | `test_prompt_workbench.py` periphery metadata tests | PASS-AUTOMATED 2026-07-18; schema-v2 paired Markdown/JSON and quality-status fixtures pass |
| `PERI-003` | Risk/opportunity/blind-spot artifacts are not injected into the main prompt or saved-memory keys by default. | Viventium has peripheral awareness without prompt bloat or memory pollution. | prompt source, memory config, Workbench prompt, chat output | Prompt/source diff tests and memory-key assertions | PASS 2026-07-11; memory mode is off, ordinary browser chat made no periphery call, and access remains tool-owned |
| `PERI-004` | A private snapshot harness labels QA/test/synthetic corpus content before insight evals. | Nightly predictions are evaluated against real signal instead of QA exhaust. | private snapshot, eval harness, sanitized QA report | Snapshot and eval-harness tests | PASS 2026-07-11; bounded real snapshot, exact structured quarantine labels, private files, and six-case bank verified with zero verbatim evidence copies |
| `PERI-005` | Risk radar output is evidence-cited, confidence-calibrated, stale-aware, and memory-off. | The user gets useful blind-spot/opportunity insight without hallucinated certainty. | Workbench scheduled fixture, artifact sidecar, synthetic snapshot | Model evals and artifact schema checks | PASS-AUTOMATED/PARTIAL 2026-07-18; synthetic quality/ref/memory-off fixtures pass, isolated nightly model artifact NOT RUN |
| `PERI-006` | Conscious-agent surfacing is on-demand or explicitly policy-approved, never nagging by default. | Viventium can call things out tastefully without becoming intrusive. | browser chat, Workbench artifact read path | User-level QA plus tool/log/DB trace | PASS 2026-07-11; ordinary control made no periphery call; final explicit retrieval used one list plus one newest-per-module read, produced one concise calibrated answer, and persisted after refresh. |
| `PERI-007` | Health-pressure awareness shares generation/governance only; persistence is decided separately. | Health tracking can shape empathy without being reduced to a generic scratchpad note or unsafe diagnosis. | health module proposal, memory config, prompt instructions | Health eval bank once approved | NOT RUN - proposal documented 2026-06-24 |
| `PERI-008` | Agent-facing periphery tools expose evidence and uncertainty without storage/run/source internals. | Expanded tool details are useful and private rather than a raw storage dump. | Scheduling MCP, browser tool cards | Serializer unit tests, direct live MCP read, browser detail-state QA | PASS 2026-07-11; unit, direct live, expanded browser, persisted Mongo, and refresh checks found no paths, private pointers, run/snapshot ids, or source refs in agent-facing outputs. |
| `PERI-009` | Unattended analytical automations use the compiled Sol/xHigh route consistently. | Nightly quality is not silently downgraded by stale metadata, an absent route-proof flag, or ambient CLI config. | compiler, Workbench, memory hardening, Scheduling dispatch, GlassHive command/ledger, UI | Compiler/dispatch tests plus synthetic process/DB metadata | PASS-AUTOMATED/PARTIAL 2026-07-18; generated/dispatch/metadata tuple fixtures pass, isolated unattended model run NOT RUN |

## Natural User Use Case Checklist

Use this checklist before claiming Viventium Periphery or nightly insight work is complete. These
rows are intentionally product-specific: they protect the vision without turning it into hardcoded
chat behavior.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `PERI-UC-001` | The user opens Workbench after a nightly insight routine should have run and checks whether a private insight exists. | `53_Viventium_Periphery_Nightly_Insights.md` / `PERI-001`, `PERI-002` | Isolated Prompt Workbench run history, Scheduler fixture, GlassHive detail | Synthetic counts, callback state, artifact sidecar hash, logs, Workbench visible state | Workbench shows a completed, failed, or skipped run with an honest reason; no private raw prompt or result leaks into public evidence. | PASS-AUTOMATED/PARTIAL 2026-07-18; metadata/ledger fixtures pass, isolated automatic browser path NOT RUN |
| `PERI-UC-002` | The user asks Viventium for blind spots, risks, opportunity costs, or strategic pressure around recent work. | `53_Viventium_Periphery_Nightly_Insights.md` / `PERI-003`, `PERI-005`, `PERI-006` | Browser chat with optional on-demand artifact access | Prompt source, memory state, private artifact metadata, model/tool trace, eval score summary | Viventium cites available evidence, labels uncertainty, avoids unsupported facts, and does not inject nightly output unless the model deliberately retrieves or the user asks. | PASS 2026-07-11; final browser used one list and one read, then passed calibrated answer, expanded detail, refresh, logs, and Mongo persistence checks. |
| `PERI-UC-003` | A nightly module encounters missing scheduler, GlassHive, memory, file, or snapshot prerequisites. | `53_Viventium_Periphery_Nightly_Insights.md` / `PERI-001`, `PERI-004` | Workbench scheduled run, Scheduler health, GlassHive host worker, snapshot harness | Failure class, health/status, retry/catch-up policy, sanitized logs, no-result artifact marker | The run is classified as blocked, skipped, or degraded with a concrete reason and no invented insight. | NOT EXERCISED / CURRENT PREREQUISITES PASS 2026-08-09 ([nightly review](../memory-hardening/reports/2026-08-09-nightly-routines-health-review.md)); current prerequisites were complete and the run passed, so the degraded live branch was not triggered today. |
| `PERI-UC-004` | The user reviews whether a nightly insight should become memory, a task, a health-pressure signal, or stay as private scratch. | `53_Viventium_Periphery_Nightly_Insights.md` / `PERI-003`, `PERI-007` | Workbench artifact review plus memory proposal surface once implemented | Memory proposal dry-run, health module state, artifact labels, approval log | Durable memory and health-pressure state are updated only through governed proposals or approved module policy; raw scratchpad text is not silently promoted. | PASS for risk-radar boundary 2026-07-11 (`memoryWriteMode=off`, zero proposal refs); health-pressure persistence remains NOT RUN. |
| `PERI-UC-005` | The user or QA reruns the same insight eval against a private snapshot corpus that includes useful signal and junk/test conversations. | `53_Viventium_Periphery_Nightly_Insights.md` / `PERI-004`, `PERI-005` | Private snapshot harness and sanitized eval report | Corpus labels, junk/test exclusion counts, output rubric, false-positive/false-negative examples | The eval proves the module resists overfitting to QA noise and reports evidence quality, confidence, staleness, and opportunity/risk value. | PASS-HARNESS / LIVE ARTIFACT PASS 2026-08-09 ([nightly review](../memory-hardening/reports/2026-08-09-nightly-routines-health-review.md)); deterministic evals passed 6/6 and the live nightly produced a fresh passed artifact. |
| `PERI-UC-006` | The user privately connects or imports a supported wearable, then asks Viventium how recent device evidence should affect today's planning. | `53_Viventium_Periphery_Nightly_Insights.md` / `PERI-007`, `PERI-010`–`PERI-020` | Owner OAuth, Settings onboarding/export/image import, read-only MCP, health-context Workbench routine, browser chat, connector status, private evidence store | Consent/scopes, source/freshness, item/evidence counts, tool trace, missing/correction state, cognitive A/B score, revoke/delete evidence, sanitized logs | The answer materially improves usefulness, cites measurement/source time, separates API observations/export/manual images/vendor scores/inferences, stays non-diagnostic, and retrieves health evidence only when relevant; disconnect fully removes live access while historical retention remains explicit. | PASS-ONGOING / HYBRID FILE ACCEPTANCE PARTIAL 2026-08-10; live owner API, minimal-click UI, first-message chat, corrections, correlation, Life projection, persistence, and cross-role isolation pass; real export is absent and expired images must be reattached. |

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
- Automated regression owner: `tests/release/test_periphery_eval_harness.py`.

## `PERI-011` - Degraded Snapshot Quality Downgrade

- Requirement: artifact quality evaluation must consider the source snapshot's health state, not
  only sidecar shape, staleness, and source-ref resolution.
- Expected result: if `snapshot.status` is degraded or `missingPrerequisites` is non-empty, the
  artifact quality is at least warning and the UI/report names the missing prerequisite.
- Forbidden result: a risk-radar artifact shows `passed` while conversations, memories, and
  messages are unavailable because snapshot prerequisites failed.
- Evidence to capture: sanitized snapshot status, missing prerequisite names, source counts,
  artifact quality status/reasons, and browser-visible detail state.
- Automated regression owner: add focused coverage beside `tests/release/test_periphery_eval_harness.py`.

## `PERI-016` - Health Artifact Expiry And Managed Prompt Revision

- Escaped failure: the first real health-context worker wrote `staleAfter` equal to `generatedAt`;
  Workbench correctly rejected the sidecar as `invalid_field_type` instead of indexing it.
- Expected result: `generatedAt` and `staleAfter` are UTC ISO-8601 strings, `ttl` is `P1D`, and
  `staleAfter` is strictly 24 hours later. A managed built-in prompt receives the repaired revision,
  while an owner-customized prompt remains unchanged.
- Forbidden result: a successful worker callback is treated as an accepted health artifact when the
  expiry interval is invalid, or a startup migration overwrites an owner-edited private prompt.
- Evidence to capture: Workbench artifact validation reason, managed revision metadata, live prompt
  detail after reload, corrected run result, memory-write mode, and proposal count.
- Automated regression owner: `tests/release/test_health_context_workbench.py` plus the shared schema
  validation cases in `tests/release/test_prompt_workbench.py`.

## `PERI-017` - Structured Provider Failure Propagation

- Escaped failure: a native model CLI wrote its provider usage-limit condition as an `ERROR:`
  control line on stderr without a JSON failure envelope, so the worker callback and Workbench
  recorded `unknown` despite the private execution log containing the real cause.
- Expected result: a structurally prefixed native CLI error maps to `provider_quota_exhausted`, is
  marked retryable, survives worker callback reconciliation, persists in the scheduled-run ledger,
  and remains visible after Workbench reload.
- Forbidden result: returning `unknown` for that control record, interpreting arbitrary task prose
  as provider evidence, or claiming an inference/artifact was produced when quota stopped the run.
- Evidence to capture: focused positive and negative classifier tests, sanitized exact-log replay,
  callback test, latest ledger status/error class, visible Workbench run history, and reload state.
- Automated regression owner:
  `viventium_v0_4/GlassHive/runtime_phase1/tests/test_profile_runtime.py` plus
  `viventium_v0_4/scheduling-cortex/tests/test_glasshive_callbacks.py`.

## `PERI-018` - Private Artifact Filesystem Boundary

- Escaped failure: worker-created Periphery Markdown and JSON used the ambient umask, leaving a
  valid health-context pair at `0644` below `0755` directories.
- Expected result: private directories are `0700`; sidecars, paired Markdown, and the index are
  `0600`; listing and body reads use the same no-follow descriptor chain; hard links and symlinks
  are withheld; partial rejection is `degraded` rather than a false total outage.
- Forbidden result: following a linked body, changing a file outside the Periphery root, replacing
  the index through a planted temporary link, skipping permission hardening after the index limit,
  or telling the agent no insights exist when healthy artifacts remain available.
- Evidence to capture: synthetic symlink/hard-link/index/chmod/over-limit results, allowlisted
  path-free availability output, independent review verdict, live file/directory modes, live index
  status, browser-visible artifact state, and reload persistence.
- Automated regression owner: `tests/release/test_prompt_workbench.py` and Scheduling Cortex
  `tests/test_prompt_contract.py`.
