# Prompt Architecture QA Cases

## Case ID Convention

Use stable `PROMPT-NNN` IDs for prompt architecture cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `PROMPT-001` | Prompt source, registry, compiled bundle, and runtime prompt use stay aligned without prompt/private-data drift. | User-visible behavior matches source, docs, persisted state, and logs | prompt registry, eval harness, prompt workbench, runtime prompts | `tests/release/test_prompt_registry.py` plus user-grade QA when visible | PARTIAL 2026-06-25 ([heart prompt live sync](reports/2026-06-25-heart-prompt-live-sync.md)); source/live sync verified, exact-model/user-path eval still pending |
| `PROMPT-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PARTIAL 2026-06-25 ([heart prompt live sync](reports/2026-06-25-heart-prompt-live-sync.md)); public report uses counts/statuses only, no raw private text |
| `PROMPT-003` | A semantic judge is calibrated against a predeclared hand-graded subset before it gates behavior | Users are not given false prompt-quality claims from an uncalibrated model judge | private eval evidence, public-safe aggregate report, Workbench history | Judge-schema and calibration-contract tests plus human grading | NOT RUN — cataloged 2026-08-29 |
| `PROMPT-004` | Python compile, JavaScript sync, and JavaScript runtime resolution obey one semantic prompt-reference contract | The same configured prompt means the same thing in every runtime path | source registry, compiler, sync, runtime loader | Shared cross-language fixture and mutation suite | NOT RUN — cataloged 2026-08-29 |
| `PROMPT-005` | Prompt compilation rejects generated/installed input roots and undeclared placeholders while preserving declared runtime placeholders | A stale installed file or placeholder typo cannot silently change live behavior | source tree, compiler, bundle, sync, installed runtime | Input-boundary, traversal/symlink, placeholder, and lineage tests | NOT RUN — cataloged 2026-08-29 |
| `PROMPT-006` | Scheduling and GlassHive MCP cognition is discoverable from server/tool contracts by every supported client | A supported non-LibreChat client can use the same capability without a copied hidden manual | MCP metadata, generic client, LibreChat, scheduler, GlassHive | MCP instruction/tool-schema parity plus generic-client contract QA | NOT RUN — cataloged 2026-08-29 |
| `PROMPT-007` | Prompt/model behavior changes compare the same positive, negative, and adjacent cases on the exact configured models, old versus proposed | Users keep semantic quality while prompt changes remove drift or waste | Prompt Workbench, exact-model runner, configured routes | Frozen paired-bank, route/parameter identity, repetition, semantic and latency comparison | NOT RUN — cataloged 2026-08-30 |

## `PROMPT-001` - Core User Flow

- Requirement: Prompt source, registry, compiled bundle, and runtime prompt use stay aligned without prompt/private-data drift.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. In Prompt Workbench, inspect every prompt's canonical source and owner, inclusion/injection
     order, composed bytes/hash, version, compiled/rendered/live state, and linked eval evidence.
  2. Enumerate runtime prompt loaders and fallbacks; verify each active prompt or fallback resolves
     to visible versioned Workbench lineage and no hidden inline behavioral fallback exists.
  3. Exercise the affected feature through the real user surface, not only a unit test.
  4. Compare the visible result with source code, generated/runtime config, logs, persisted state,
     duplication/drift indicators, and the owning requirement doc.
  5. Capture a public-safe report with expected result, forbidden result, evidence, residual risk,
     and follow-up.
- Expected result: Workbench exposes exact ownership, order, composition, version, source-to-live
  lineage, duplication/drift, and eval evidence for every active prompt/fallback; visible behavior
  matches the documented bytes and supporting state.
- Forbidden result: an unowned or hidden inline fallback, missing order/composition/version, a
  duplicate source, silent source/rendered/live drift, or supporting logs/model output treated as
  user acceptance when a real surface exists.
- Evidence to capture: sanitized registry/fallback inventory, owner and order map, source/rendered/live
  hashes, version and duplication/drift result, eval identity, visible result, and supporting state.
- Automation: `tests/release/test_prompt_registry.py` plus any narrower feature tests discovered during implementation.
- Last run: PARTIAL 2026-06-25
  ([heart prompt live sync](reports/2026-06-25-heart-prompt-live-sync.md)); source/live sync and
  string guards passed, but exact-model/user-path eval remains pending.

## `PROMPT-002` - Public-Safe Evidence Record

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
- Last run: PARTIAL 2026-06-25
  ([heart prompt live sync](reports/2026-06-25-heart-prompt-live-sync.md)); the report keeps private
  identifiers, raw chats, and raw memory values out of public evidence.

## `PROMPT-003` - Calibrated Semantic Judge

- Requirement: a schema-valid model judgment cannot gate prompt behavior until a predeclared
  hand-graded subset meets its declared agreement threshold.
- Risk covered: a consistent-looking judge silently rewards the wrong behavior.
- Preconditions: a versioned public-safe case bank, private candidate responses, a frozen grading
  rubric, the subset selection rule, and the agreement threshold exist before judging begins.
- Steps:
  1. Freeze the case-bank/version hash, judge route, rubric, subset selection, and threshold.
  2. Grade the selected subset without exposing the model verdict to the human grader.
  3. Compare human and judge outcomes and dimension scores; include boundary and disagreement cases.
  4. Change one expected human grade and remove one grade; verify agreement or completeness fails.
  5. Publish only hashes, counts, threshold, agreement result, and sanitized blocker classes.
- Expected result: the complete subset meets the predeclared threshold and every accepted judge
  result is bound to that calibration version.
- Forbidden result: accepting structured JSON alone, selecting only agreeable rows after results,
  missing human grades, threshold changes after scoring, or raw prompt/response/grade publication.
- Evidence to capture: private per-case grading ledger and public-safe aggregate receipt.
- Automation: judge schema/completeness/mutation checks; human grading remains an independent gate.
- Last run: NOT RUN — cataloged 2026-08-29.

## `PROMPT-004` - Cross-Language Resolver Semantic Parity

- Requirement: Python compile, JavaScript sync, and JavaScript runtime resolution share one
  versioned semantic contract.
- Risk covered: the same source prompt resolves differently across compiler, synchronization, and
  runtime paths.
- Preconditions: one fixture bank covers nested references, include order, strict and non-strict
  variables, `promptVars`, runtime placeholders, cycles, missing references, and invalid metadata.
- Steps:
  1. Run every valid fixture through all three resolvers and compare exact UTF-8 output bytes and
     preserved metadata.
  2. Run every invalid fixture and compare typed failure class and owning source locator.
  3. Mutate each contract field in turn, including include order and placeholder metadata.
  4. Verify a resolver implementation cannot silently ignore or default the changed field.
- Expected result: valid output is byte-identical and invalid input fails equivalently in all paths.
- Forbidden result: type-only assertions, order-insensitive comparison, silent metadata loss,
  hidden inline fallback, or one path accepting input rejected by another.
- Evidence to capture: fixture/version hash and per-path result/failure digest.
- Automation: shared cross-language fixture and mutation suite.
- Last run: NOT RUN — cataloged 2026-08-29.

## `PROMPT-005` - Canonical Input And Placeholder Boundary

- Requirement: only tracked authoring sources can compile, and every runtime placeholder is
  declared and preserved through the complete lineage.
- Risk covered: generated or installed state poisons source truth, or a typo becomes silent live
  behavior drift.
- Preconditions: clean tracked source fixtures plus generated, compiled, installed, traversal,
  relative-alias, and symlink fixtures.
- Steps:
  1. Compile the clean tracked source and record source/bundle/sync/runtime hashes.
  2. Try each non-authoring root and every alias to it; verify rejection occurs before content read.
  3. Add an undeclared and a misspelled placeholder; verify compile/check fails with its source.
  4. Add each declared runtime placeholder; verify exact preservation through source, bundle, sync,
     and runtime resolution.
  5. Scan public evidence for expanded private/model values.
- Expected result: only canonical source compiles; valid placeholders survive exactly; invalid ones
  fail closed; public evidence contains only safe hashes and names.
- Forbidden result: Application Support/generated input, traversal or symlink acceptance, silent
  placeholder removal/defaulting, installed-file precedence, or private-value leakage.
- Evidence to capture: boundary fixture results and complete lineage digests.
- Automation: input-root, traversal/symlink, placeholder, and lineage tests.
- Last run: NOT RUN — cataloged 2026-08-29.

## `PROMPT-006` - Portable MCP Cognition

- Requirement: Scheduling and GlassHive operations, failure states, authorization boundaries, and
  duplicate-safety behavior are discoverable from MCP server instructions and tool schemas.
- Risk covered: LibreChat works only because it received a private copied manual while another
  supported client cannot use the same capability safely.
- Preconditions: a declared supported-client matrix, current MCP metadata, every supported client
  in that matrix (including LibreChat and supported non-LibreChat clients), and synthetic isolated
  state are available.
- Steps:
  1. Start a fresh session in every declared supported client without client-specific operation manuals.
  2. Discover the same supported Scheduling and GlassHive operations from MCP metadata.
  3. In every client, execute one read and one authorized mutation; repeat the mutation to prove
     duplicate safety.
  4. Exercise unavailable, unauthorized, invalid, and delayed-result states in the matrix.
  5. Compare visible outcomes and typed receipts without requiring identical presentation.
- Expected result: every declared supported client can act safely and truthfully from one
  server/tool contract.
- Forbidden result: a LibreChat-only hidden prompt, copied per-client manuals, prompt-text routing,
  silent capability narrowing, duplicate side effects, or fabricated completion.
- Evidence to capture: metadata hashes, client capability lists, typed receipts, and visible results.
- Automation: MCP instruction/tool-schema parity plus generic-client contract harness.
- Last run: NOT RUN — cataloged 2026-08-29.

## `PROMPT-007` - Exact-Model Old-Versus-Proposed Behavior Parity

- Requirement: a prompt/model behavior change runs the same frozen sanitized positive, negative,
  and adjacent cases on the exact configured model route and parameters before and after the change.
- Risk covered: token or architecture cleanup silently loses intelligence, relevance, usefulness,
  alignment, safety, or adjacent behavior.
- Preconditions: source/rendered/live hashes, configured provider/model/effort/parameters, a frozen
  case-bank/version, expected behavior, repetitions, semantic rubric, and latency method are fixed.
- Steps:
  1. Run the unchanged baseline against every positive, negative, and adjacent case.
  2. Run the proposed bytes against the same inputs, route, parameters, repetitions, and judge version.
  3. Compare operational completion, semantic dimensions, false positives/negatives, latency, and
     source-to-live lineage; inspect every disagreement.
  4. Mutate or remove one case class and change one route field; verify the comparison fails closed.
  5. Restore the exact prior live state and remove synthetic data unless a reviewed promotion is authorized.
- Expected result: the proposed prompt meets its declared improvement without regressing any frozen
  case class, and every result is bound to exact source, model, and evidence identity.
- Forbidden result: positive-only cases, different models/parameters, cherry-picked repeats,
  same-thread opinion as evidence, hidden live sync, uncalibrated judging, or latency-only success.
- Evidence to capture: private paired outputs and public-safe hashes, counts, dimension deltas,
  disagreement classes, latency summary, lineage, restoration, and cleanup receipt.
- Automation: paired-bank completeness/identity/mutation tests plus exact-model semantic evaluation.
- Last run: NOT RUN — cataloged 2026-08-30.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Prompt Architecture. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `PROMPT-UC-001` | In Prompt Workbench, inspect every active prompt and fallback from its canonical owner through inclusion/injection order, composition and version to compiled, rendered, and live bytes; then inspect duplication, drift, eval lineage, and hidden-fallback absence. | `GOV-001`, `GOV-003` / `PROMPT-001` | Prompt Workbench, registry, compiler, sync, and affected real user surface | Owner and order map, source/composed/compiled/rendered/live hashes, version, duplicate/drift scan, fallback inventory, persisted state, logs, and applicable shipped artifact | Every active prompt and fallback has one visible versioned lineage with matching bytes and no hidden inline behavioral fallback | PARTIAL 2026-06-25 ([report](reports/2026-06-25-heart-prompt-live-sync.md)); the expanded ownership/order/composition/version/duplication/drift/hidden-fallback and exact-model user-path gates remain unrun |
| `PROMPT-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `PROMPT-002` / `PROMPT-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to PROMPT-002. | The user sees an honest setup, retry, or degraded-state result for PROMPT-002; no fake success is accepted. | PARTIAL 2026-06-25 ([report](reports/2026-06-25-heart-prompt-live-sync.md)); public-safe evidence created |
| `PROMPT-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `PROMPT-002` / `PROMPT-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to PROMPT-002. | PROMPT-002 remains correct after the persistence or parity step and final wording matches evidence. | PARTIAL 2026-06-25 ([report](reports/2026-06-25-heart-prompt-live-sync.md)); linked report reviewed after creation |
| `PROMPT-UC-004` | Review an exact-model result whose semantic judge was calibrated before the run | `PROMPT-003` / `PROMPT-003` | Prompt Workbench and public-safe calibration report | Private hand grades, rubric/version hashes, aggregate agreement receipt, saved run | The user sees truthful calibrated semantic evidence or an explicit blocked state | NOT RUN — cataloged 2026-08-29 |
| `PROMPT-UC-005` | Change one prompt reference or runtime placeholder and compare compile, sync, and live resolution | `PROMPT-004`, `PROMPT-005` / `PROMPT-004`, `PROMPT-005` | Prompt Workbench, compiler, sync, runtime | Shared fixtures, source/bundle/live hashes, typed failure receipts | Every path resolves the same bytes, or the invalid change fails before activation | NOT RUN — cataloged 2026-08-29 |
| `PROMPT-UC-006` | From a fresh session in every declared supported client, discover and use Scheduling and GlassHive through MCP | `PROMPT-006` / `PROMPT-006` | Supported-client matrix plus MCP servers | Server/tool metadata, authorization and duplicate receipts, visible result for each client | Every supported client completes or reports a typed failure without a copied hidden manual | NOT RUN — cataloged 2026-08-29 |
| `PROMPT-UC-007` | Compare a proposed prompt change with its current bytes across frozen positive, negative, and adjacent cases | `PROMPT-007` / `PROMPT-007` | Prompt Workbench plus exact configured model routes | Paired source/model/case hashes, semantic and latency deltas, disagreements, restoration/cleanup | The change improves its target without losing adjacent behavior; otherwise promotion stays blocked | NOT RUN — cataloged 2026-08-30 |

## Release Test Traceability

- `tests/release/test_native_surface_eval_runner_trust_cleanup.py`
- `tests/release/test_prompt_architecture_eval_harness.py`
- `tests/release/test_prompt_registry.py`
