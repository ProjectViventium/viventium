# Periphery Nightly Insights Cases

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `PERI-001` | Current nightly executor health is classified before new insight routines are activated. | Viventium does not add prediction/risk work on top of an unknown broken substrate. | Scheduling DB, Workbench, GlassHive, callback outbox, logs | Focused scheduler/Workbench tests plus live ledger audit | PASS-EXECUTOR / WATCH-HISTORY 2026-08-09 ([nightly review](../memory-hardening/reports/2026-08-09-nightly-routines-health-review.md)); the natural Workbench chain completed through GlassHive, callbacks, and artifact validation; old queued/dead-letter rows remain cleanup debt. |
| `PERI-002` | Private periphery artifacts use a typed `.md` plus `.json` sidecar contract. | Nightly insight is retained, inspectable, and not lost in loose scratch files. | private scratchpad folder, Workbench run details | `test_prompt_workbench.py` periphery metadata tests | PASS-ARTIFACT 2026-08-09 ([nightly review](../memory-hardening/reports/2026-08-09-nightly-routines-health-review.md)); the current run produced a paired `risk_radar` Markdown/JSON artifact and Workbench validated it as passed. |
| `PERI-003` | Risk/opportunity/blind-spot artifacts are not injected into the main prompt or saved-memory keys by default. | Viventium has peripheral awareness without prompt bloat or memory pollution. | prompt source, memory config, Workbench prompt, chat output | Prompt/source diff tests and memory-key assertions | PASS 2026-07-11; memory mode is off, ordinary browser chat made no periphery call, and access remains tool-owned |
| `PERI-004` | A private snapshot harness labels QA/test/synthetic corpus content before insight evals. | Nightly predictions are evaluated against real signal instead of QA exhaust. | private snapshot, eval harness, sanitized QA report | Snapshot and eval-harness tests | PASS 2026-07-11; bounded real snapshot, exact structured quarantine labels, private files, and six-case bank verified with zero verbatim evidence copies |
| `PERI-005` | Risk radar output is evidence-cited, confidence-calibrated, stale-aware, and memory-off. | The user gets useful blind-spot/opportunity insight without hallucinated certainty. | Workbench scheduled run, artifact sidecar, private snapshot | Model evals and artifact schema checks | PASS 2026-08-09 ([nightly review](../memory-hardening/reports/2026-08-09-nightly-routines-health-review.md)); fresh artifact passed with high confidence, 8/8 sources resolved, explicit staleness, and zero memory proposals. |
| `PERI-006` | Conscious-agent surfacing is on-demand or explicitly policy-approved, never nagging by default. | Viventium can call things out tastefully without becoming intrusive. | browser chat, Workbench artifact read path | User-level QA plus tool/log/DB trace | PASS 2026-07-11; ordinary control made no periphery call; final explicit retrieval used one list plus one newest-per-module read, produced one concise calibrated answer, and persisted after refresh. |
| `PERI-007` | Health-pressure awareness shares generation/governance only; persistence is decided separately. | Health tracking can shape empathy without being reduced to a generic scratchpad note or unsafe diagnosis. | health module proposal, memory config, prompt instructions | Health eval bank once approved | NOT RUN - proposal documented 2026-06-24 |
| `PERI-008` | Agent-facing periphery tools expose evidence and uncertainty without storage/run/source internals. | Expanded tool details are useful and private rather than a raw storage dump. | Scheduling MCP, browser tool cards | Serializer unit tests, direct live MCP read, browser detail-state QA | PASS 2026-07-11; unit, direct live, expanded browser, persisted Mongo, and refresh checks found no paths, private pointers, run/snapshot ids, or source refs in agent-facing outputs. |
| `PERI-009` | Unattended analytical automations use the compiled Sol/xHigh route consistently. | Nightly quality is not silently downgraded by stale metadata, an absent route-proof flag, or ambient CLI config. | compiler, Workbench, memory hardening, Scheduling dispatch, GlassHive command/ledger, UI | Compiler/dispatch tests plus real process command and DB metadata | PASS-WORKBENCH / SEPARATE-MEMORY-TUPLE 2026-08-09 ([nightly review](../memory-hardening/reports/2026-08-09-nightly-routines-health-review.md)); Workbench visibly preserved Sol/xhigh requested/effective effort and completed. Memory hardening independently used its configured Luna/medium route. |
| `PERI-010` | Wearable evidence enters through a consented, least-privilege connector or explicit private import and remains distinct from saved memory and health-context inference. | Viventium can use fresh, traceable device evidence without leaking raw biometrics, inventing health advice, or requiring a mobile app when a vendor cloud API suffices. | vendor API, private raw archive, read-only MCP, browser chat, Periphery health-context artifact | Component contract tests, real owner-device acquisition/MCP A/B, then parent integration and revoke/correction QA | PASS-CONNECTED 2026-08-10; owner OAuth, the six-resource 51-item all-history import, a real three-day correction run, exact archive reads, bounded correlation, and a passed live artifact are complete. Live revoke was intentionally not run because the accepted end state is ongoing access; disconnect remains synthetic regression coverage. |
| `PERI-011` | Degraded snapshot prerequisites downgrade artifact quality. | A fresh nightly artifact cannot appear healthy when its evidence corpus was unavailable. | Workbench periphery snapshot, artifact quality summary, browser detail | Focused artifact-quality regression plus live snapshot/artifact audit | PASS-FRESH 2026-08-09 ([nightly review](../memory-hardening/reports/2026-08-09-nightly-routines-health-review.md)); current snapshot was complete with no missing prerequisites and the fresh artifact passed. The degraded-input branch remains regression-covered rather than live-exercised today. |
| `PERI-012` | Clean install, upgrade, and start materialize the pinned health component and executable runtime before advertising its MCP. | The health tools work on a clean machine instead of depending on an owner laptop's leftovers. | component bootstrap, lock pin, App Support runtime, generated MCP config | Bootstrap selection, isolated runtime install/status, MCP initialize/list/call, pin/artifact parity | PASS-ISOLATED / PASS-LIVE / FRESH-CLONE-NOT-RUN 2026-08-10; the reviewed component head, parent pin, installed manifest/hash, public CLI, preserved archive, and read-only MCP/runtime tests agree. |
| `PERI-013` | Health-context snapshots are bounded, private, source-cited, and failure-aware. | Correlation can use exact WHOOP evidence without exposing credentials, paths, opaque record IDs, or unlimited payloads. | Workbench private snapshot, health CLI, snapshot manifest/API | Synthetic archive fixtures for complete/empty/missing/partial/truncated/timeout states plus permission/privacy assertions | PASS-LIVE 2026-08-10; the scheduled snapshot inspected 48 summaries, included 18 exact bodies, had zero read failures/truncations/missing prerequisites, and exposed metadata only in Workbench. |
| `PERI-014` | WHOOP acquisition and health-context analysis have distinct scheduler owners. | Daily acquisition and correlation run once, recover honestly, and never duplicate network pulls. | Health LaunchAgent, Scheduling Cortex definition, Workbench run ledger | Schedule rendering/status, seeded-definition reconciliation, catch-up, restart/persistence, no-pull assertion | FAIL-ACQUISITION / PARTIAL-CORRELATION 2026-08-11 ([nightly review](../memory-hardening/reports/2026-08-11-nightly-routines-health-review.md)); the distinct 06:00 and 06:15 owners fired, but expired-token refresh failed all six provider resources. Correlation truthfully used a degraded snapshot and performed no pull; its occurrence ledger also retained a duplicate queued row. |
| `PERI-015` | The optional Life projection contains connector metadata only and updates from the private health-context path. | The user's Life health folder shows freshness and integration state without becoming a second raw biometric store. | private Life folder, App Support archive, Workbench snapshot | Synthetic projection shape/permissions/hash tests and real private status refresh | PASS-COMPLETE 2026-08-10; the refreshed projection was `0700`/`0600`, reported complete with 18 bounded records included, and contained status/count/hash metadata with no raw body, record locator, or credential. |
| `PERI-016` | Health-context sidecars use an internally consistent expiry interval, and managed template repairs do not overwrite owner-customized prompts. | A completed worker cannot leave an invalid artifact hidden behind a successful run, and product upgrades remain safe for private customization. | Workbench prompt definition/version, GlassHive result, artifact validator, browser detail | Strict timestamp/duration prompt regression, managed-revision reconciliation, owner-edit preservation, real rerun | PASS-LIVE 2026-08-10; the scheduler-owned rerun produced a fresh `P1D` artifact with 4/4 sources resolved, zero ungrounded claims, zero actions, and zero memory proposals; Workbench kept it passed after reload. |
| `PERI-017` | Native provider terminal errors keep a structured failure class through GlassHive, callback reconciliation, Scheduling Cortex, and Workbench without treating task prose as control evidence. | A blocked health-context run names the actionable provider condition instead of showing `unknown`, while ordinary prompt/output text cannot manufacture a provider outage. | GlassHive CLI evidence parser, worker callback, scheduled-run ledger, Workbench run history | Focused classification and callback regressions, exact sanitized log replay, real manual run plus reload | PASS-CLASSIFICATION 2026-08-10; the historical provider-limit attempt remains truthfully classified after reload, and later manual plus scheduler-owned runs completed successfully with accepted artifacts. |
| `PERI-018` | Private Periphery files remain owner-only across worker creation, listing, body reads, indexing, and partial rejection. | Health-derived context cannot leak through permissive umasks, links, index replacement, or misleading all-or-nothing availability. | private continuity folder, Workbench API, Scheduling Cortex agent serializer | No-follow/hard-link/index/permission/over-limit tests, independent security review, live mode and browser checks | PASS 2026-08-10; all discovered live sidecars and paired Markdown were `0600`, relevant directories were `0700`, the index was regular `0600`, privacy blockers were zero, partial rejection uses `degraded`, and blocked/degraded agent output is path-free. |
| `PERI-019` | Local owners receive minimal-click, capability-complete WHOOP onboarding without embedded public secrets or hidden provider limits. | A provisioned owner uses one Connect action plus WHOOP consent; an unprovisioned owner gets a combined save/connect fallback, automatic history/schedule setup, readable six-family counts, and honest recovery state. | Settings UI, admin API, macOS URL helper, health CLI/runtime, LaunchAgent | Component/command/route/UI/helper tests, built artifacts, installed browser and persistence QA | PASS-INSTALLED-BROWSER 2026-08-10; direct setup, owner consent handoff, readable six-family status, automatic schedule, refresh persistence, tests, and builds pass. |
| `PERI-020` | API, official export, and manual image evidence form one honest WHOOP coverage boundary. | Journal/export fields and app-only Stress Monitor context can reach Viventium without scraping, private endpoints, false normalization, or arbitrary file access. | Settings UI, admin API, exact archive, read-only MCP text/image | ZIP abuse regressions, image magic/size/hash regressions, MCP image parsing, browser uploads, private archive inspection | PARTIAL-LIVE 2026-08-10; exact ZIP/image preservation, abuse limits, MCP parsing, and installed lanes pass, but a real export was not supplied and expired image attachments must be reattached. |
| `PERI-021` | Host-wide health tools are owner-only and recovery is bounded across every product entry point. | Sharing the main agent cannot share private health; disabled installs advertise nothing; expired/repeated setup recovers without races, infinite polling, shell launch, or duplicate exports. | MCP tool loader, compiler, admin API, Settings UI, helper/CLI/archive | Audience-policy role tests, enabled/disabled compile tests, all-mutation gates, OAuth TTL/single-flight/background lifetime, degraded/pending UI, exact-hash idempotency | PASS-INSTALLED-ROLE-QA 2026-08-10; owner chat/tool startup passed, ordinary-account card/projection/process startup were denied, and refresh/recovery tests passed. |

## Natural User Use Case Checklist

Use this checklist before claiming Viventium Periphery or nightly insight work is complete. These
rows are intentionally product-specific: they protect the vision without turning it into hardcoded
chat behavior.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `PERI-UC-001` | The user opens Workbench after a nightly insight routine should have run and checks whether a private insight exists. | `53_Viventium_Periphery_Nightly_Insights.md` / `PERI-001`, `PERI-002` | Prompt Workbench run history, Scheduler ledger, GlassHive run detail | Redacted run counts, callback state, artifact sidecar hash, logs, Workbench visible state | Workbench shows a completed, failed, or skipped run with an honest reason; no private raw prompt or result leaks into public evidence. | PASS-VISIBLE 2026-08-09 ([nightly review](../memory-hardening/reports/2026-08-09-nightly-routines-health-review.md)); Workbench showed the completed natural run, complete snapshot, passed fresh artifact, and preserved them after reload. |
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
