# QA System Audit Cases

## Case ID Convention

Use stable `QASYS-NNN` IDs for QA-system structure, traceability, evidence, and process checks.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `QASYS-001` | QA operating contract is present and authoritative | Developers know the minimum QA bar | `qa/README.md`, `01_Key_Principles.md`, agent instructions | `test_qa_operating_contract.py` plus source inspection | PASS 2026-05-17 |
| `QASYS-002` | Every feature maps requirement -> QA owner -> cases -> tests -> results; `CC-064` preserves the private source history behind that map | No feature or retained source requirement is orphaned, rewritten, or leaked | Requirement docs, private continuity source boundary, public-safe receipt, `45_Runtime_Feature_QA_Map.md`, QA folders | Exact join audit, authorized private append/history integrity check, and public-safety scan | PARTIAL 2026-08-30; current source/owner/case joins resolve, but private append/history verification is NOT RUN and several owners and the source receipt are not clean-checkout durable |
| `QASYS-003` | QA folders use the living README/cases/reports shape or are tracked in migration | QA records are predictable and easy to update | `qa/<feature>/` | Folder inventory plus migration review | FAIL 2026-08-30; multiple current standard QA owners or report homes exist only as untracked working-tree files |
| `QASYS-004` | User-grade full-view evidence is required and recorded | Visible UX, logs, DB, code, docs, and artifacts agree | Browser, Telegram, voice, CLI, MCP, scheduler, GlassHive | Manual evidence review plus feature harnesses | PASS 2026-05-17 for the contract; feature runs remain separately required |
| `QASYS-005` | Automated tests reference QA cases or owning QA docs | Release failures point to product requirements | `tests/release/`, QA cases | Source grep plus planned parity test | PARTIAL 2026-08-30; mappings are complete in the working tree, but an owning case file remains untracked |
| `QASYS-006` | Agent instructions point to real QA docs and the same evidence rule | AI agents do not follow stale paths or backend-only acceptance | `AGENTS.md`, `CLAUDE.md`, `01_Key_Principles.md`, `qa/README.md` | Link/path review plus planned contract test | PASS 2026-05-17 |
| `QASYS-007` | Public QA records are tracked or intentionally private/ignored | Fresh clones and public exports have reproducible QA context | `qa/`, `.gitignore`, release tests | Git ignored/tracked review plus public-safety scan | FAIL 2026-08-30; required current QA/source records are untracked or differ from `HEAD` |
| `QASYS-008` | Full-view evidence gate blocks hand-waved completion | Agents must name unrun user paths as blocked/partial | Agent docs, QA templates, dated reports | `test_qa_operating_contract.py` plus report-template review | PASS 2026-05-18 |
| `QASYS-009` | Product-wide natural user use-case checklist is mandatory | QA starts from all features and obvious user actions, not one symptom | `45_Runtime_Feature_QA_Map.md`, `qa/feature-user-use-case-checklist.md`, `qa/*/cases.md` | `test_qa_operating_contract.py` plus feature checklist review | PASS 2026-05-18 |
| `QASYS-010` | Requested iterative independent reviews are fresh, revised, scored, and reported honestly; a separately requested Claude review-only pass runs after the bounded loop and remains distinct from tests | Developers receive useful criticism without a fabricated completion score or collapsed reviewer roles | Review receipts, affected docs/QA/tests, private source bundle, distinct Claude review receipt when requested | Fresh-context review loop, deterministic revalidation, then separate review-only reconciliation | PARTIAL 2026-08-30; review and correction loops remain active, so no final gate is claimed |
| `QASYS-011` | `CORE-014`: preserve unrelated work and separate diagnosis from implementation authority | A bounded request produces only the smallest authorized source-backed change | Request, owner files, repository diff | Synthetic authorization/diff fixture | NOT RUN — cataloged 2026-08-30 |
| `QASYS-012` | `CORE-015`: completion reports are short, plain, evidence-based, and honest about open gates | The reader sees verified result and remaining gap immediately | Final report and cited evidence | Synthetic result/report fixture | NOT RUN — cataloged 2026-08-30 |
| `QASYS-013` | `CORE-003`/`CORE-004`: models own semantic judgment; runtime owns typed structure and never keyword-routes intent | Equivalent wording produces model-owned decisions without regex, substring, or provider-name branches | Runtime source, prompt/config owner, exact-model cases | Branch scan plus paired semantic fixtures | NOT RUN — cataloged 2026-08-30 |
| `QASYS-014` | `CORE-005`: choose the smallest proven native mechanism and reject speculative duplicate infrastructure | A design reuses existing Viventium/LibreChat/GlassHive/Codex/Claude primitives unless evidence requires more | Proposal, source inventory, resulting diff | Native-primitive decision ledger | NOT RUN — cataloged 2026-08-30 |
| `QASYS-015` | `CORE-007`: every authorized direct/provider/channel/scheduler/callback path independently preserves outcome capability | No supported path silently narrows intelligence, relevance, usefulness, alignment, or required ability | Direct Main, GlassHive Codex/Claude, Web, Telegram, Voice, scheduler, callback | One enumerated cross-surface parity matrix | NOT RUN — cataloged 2026-08-30 |
| `QASYS-016` | `CORE-001`: Quality plus Performance is graded together on every applicable path | A faster but less intelligent, relevant, useful, aligned, smooth, or reliable result fails | Exact-model and real-path scorecards | Locked quality/performance rubric | NOT RUN — cataloged 2026-08-30 |
| `QASYS-017` | `CORE-009`: acceptance and runtime-truth claims require exact evidence for the named fact | No completion, delivery, fallback, memory, tool, route, model, Feeling, or readiness claim exceeds evidence | Visible result, typed state, logs, artifacts | Adversarial claim/evidence matrix | NOT RUN — cataloged 2026-08-30 |
| `QASYS-018` | `GOV-004`/`GOV-005`: private source retention and public-safe per-requirement joins are complete and non-leaking | Every retained requirement has owner, natural use case, QA case, expected, evidence, and gap without publishing private source | Authorized private ledger and public-safe receipts | Exact join audit plus safety scan | NOT RUN — cataloged 2026-08-30 |
| `QASYS-019` | `GOV-006`: current truth, history, proposal, superseded idea, review finding, uncertainty, and open choice remain distinct | Readers never mistake a historical or proposed statement for current product truth | Owning docs and QA catalogs | Status-taxonomy fixture review | NOT RUN — cataloged 2026-08-30 |
| `QASYS-020` | `GOV-007`: primary sources are revalidated before correcting contradictions, stale status, links, owners, or evidence | Corrections reflect current source bytes and do not replace one stale assertion with another | Primary owners, affected docs/QA, diff | Before/after source-validation receipt | NOT RUN — cataloged 2026-08-30 |
| `QASYS-021` | `GOV-008`: one owning source gives future developers full background, goal, behavior, edge, integration, and development context | A fresh developer can make the right change without reconstructing private conversation history | Owning requirement, runtime owner, QA owner | Fresh-context handoff review | NOT RUN — cataloged 2026-08-30 |
| `QASYS-022` | `GOV-009`: fully aligned means no recoverable omission, contradiction, wrong owner, stale-only evidence, or overclaim | Every retained row resolves or exposes an exact remaining gap | Requirement/owner/use-case/case/evidence inventory | Fail-closed alignment audit | NOT RUN — cataloged 2026-08-30 |
| `QASYS-023` | `GOV-013`: routine blockers use authorized local setup/browser/computer paths without widening authority | In-scope work continues through ordinary local setup while genuine approval/security gates remain closed | Local setup, browser/computer path, authorization record | Synthetic blocker/authority matrix | NOT RUN — cataloged 2026-08-30 |
| `QASYS-024` | `GOV-010`/`GOV-015`: user-facing design changes use a sparse, obvious, product-specific UI and receive responsive, theme, interaction, keyboard, and accessibility QA | The changed surface contains only necessary actions, is immediately understandable and usable, and is proved on the real path; design review cannot substitute for use | Real browser/desktop at supported states | Primary-action inventory plus responsive/theme/a11y interaction matrix | NOT RUN — cataloged 2026-08-30 |
| `QASYS-025` | `GOV-021`: retain only sourced behavior, safety, compatibility, or UX gates | Ceremonial checks, date-bumped stale cases, recreated history, and unjustified architecture are rejected | Proposed requirement/QA changes and source ledger | Value/necessity review | NOT RUN — cataloged 2026-08-30 |
| `QASYS-026` | `GOV-011`: real affected surfaces and supporting code/state/artifacts are jointly proven and reported truthfully | Browser/Desktop/Telegram/Voice evidence agrees with logs, DB, docs, generated and installed artifacts | Every affected real surface and supporting layer | Full-view evidence receipt | NOT RUN — cataloged 2026-08-30 |

## Natural User Use Case Checklist

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `QASYS-UC-001` | Developer starts a fix by reading the feature map, enumerating user use cases, and appending newly authorized source messages at the private boundary before updating public joins. | `CC-064` / `QASYS-002`, `QASYS-009` | Private continuity source boundary plus docs and QA contract | Byte comparison, stable message IDs, SHA-256 values, supersession links/history, sanitized aggregate public proof, feature map, checklist, cases, and release tests | New source is appended byte-exactly with stable IDs and SHA-256; superseded records remain; public artifacts expose only sanitized aggregate proof; a use-case checklist exists before pass/fail claims. | PARTIAL 2026-08-30; the checklist contract passed 2026-05-18, but the private append/history and aggregate-proof branch is NOT RUN. |
| `QASYS-UC-002` | Escaped user-visible failure crosses feature boundaries. | `QASYS-004`, `QASYS-009` | Real browser/computer plus logs/DB/state | Feature cases, visible UI, logs, DB/state, docs, generated config | A synthetic regression is added to every affected owner and unrun fixes remain visible. | PASS 2026-05-18 for the contract; product fix pending in affected owners |
| `QASYS-UC-003` | Agent prepares a release/public-ready diff. | `QASYS-007` | Git diff and QA/report scan | tracked files, ignored files, public-safety scan, staged diff | No private data, local paths, raw IDs, screenshots, or secrets are published. | PARTIAL 2026-05-18; final diff review pending |
| `QASYS-UC-004` | User requests an iterative independent review of complex work plus a separate Claude review-only pass. | `GOV-012`, `QASYS-010` | Fresh reviewer contexts, the exact reviewed files, and a distinct Claude review context after the loop | Review scores, actionable findings, revision log, deterministic checks, remaining gaps, and the separate Claude receipt | At least two fresh reviews occur with a revision between them; the final loop score is actual, a sub-8 result after four loops stays explicit, and the separately requested Claude review runs afterward without replacing tests or being merged into the loop score. | PARTIAL 2026-08-30; current loop is not final |
| `QASYS-UC-005` | Ask for diagnosis only, then ask for one bounded fix while unrelated local changes are present. | `CORE-014` / `QASYS-011` | request text, repository diff, and affected owner files | authorization boundary, before/after diff, source evidence, and unrelated-file status | Diagnosis changes nothing; the authorized fix changes only the smallest source-backed scope and preserves unrelated work. | NOT RUN — cataloged 2026-08-30. |
| `QASYS-UC-006` | Ask for a completion report after a run with both verified evidence and one open gate. | `CORE-015` / `QASYS-012` | final user-facing report and cited evidence | executed commands, visible result, supporting state, canonical statuses, and unrun-gate list | The report is short and plain, states what evidence proves, and names the open gate without a completion claim. | NOT RUN — cataloged 2026-08-30. |
| `QASYS-UC-007` | Ask semantically equivalent requests with changed wording/provider labels and inspect how the decision is made. | `CORE-003`, `CORE-004` / `QASYS-013` | exact configured model boundary and runtime source | paired decisions, typed metadata, prompt/config lineage, and regex/keyword branch scan | The model owns semantic judgment; runtime uses typed structure and contains no wording/provider-name intent branch. | NOT RUN — cataloged 2026-08-30. |
| `QASYS-UC-008` | Review a proposed new subsystem against existing Viventium, LibreChat, GlassHive, Codex, and Claude primitives. | `CORE-005` / `QASYS-014` | architecture proposal, existing source/contracts, and resulting diff | native capability inventory, measured gap, decision, and changed paths | The smallest proven native mechanism is reused; duplicate/speculative infrastructure is rejected unless evidence proves it necessary. | NOT RUN — cataloged 2026-08-30. |
| `QASYS-UC-009` | Run the same authorized goal through direct Main, GlassHive Codex/Claude, Web, Telegram, Voice, scheduler, and callback paths. | `CORE-007` / `QASYS-015` | every declared supported path | exact input/context/capabilities, visible result, state, latency, and gaps per path | Every path independently meets the outcome and ability contract; one passing path cannot hide another path's loss. | NOT RUN — cataloged 2026-08-30. |
| `QASYS-UC-010` | Compare a faster candidate with the current path using the combined quality and performance rubric. | `CORE-001` / `QASYS-016` | exact-model evaluation and real affected surface | per-dimension quality, latency, smoothness, reliability, failures, and visible result | Speed is accepted only when intelligence, relevance, usefulness, alignment, smoothness, and reliability do not regress. | NOT RUN — cataloged 2026-08-30. |
| `QASYS-UC-011` | Challenge claimed completion, delivery, fallback, memory, tools, route, model, Feeling, and readiness with truthful and stale fixtures. | `CORE-009` / `QASYS-017` | visible surface plus typed runtime/evidence owners | claim text, exact typed state, logs, DB, artifact identity, and negative controls | Each claim is made only when its exact current evidence exists; stale or adjacent evidence produces a precise partial/blocked result. | NOT RUN — cataloged 2026-08-30. |
| `QASYS-UC-012` | Rebuild the retained-requirement inventory from the authorized private ledger and inspect the public-safe receipt. | `GOV-004`, `GOV-005` / `QASYS-018` | private ledger plus public owner/QA tree | source retention, per-ID owner/UC/case/expected/evidence/gap joins, and privacy scan | Every retained row joins exactly; missing joins stay explicit; raw private prompts, IDs, screenshots, and paths remain private. | NOT RUN — cataloged 2026-08-30. |
| `QASYS-UC-013` | Classify mixed current, historical, proposed, superseded, review, uncertain, and open-choice statements. | `GOV-006` / `QASYS-019` | owning documents and QA catalogs | source date/authority, status label, links, and visible wording | Every statement retains the correct truth class and no historical/proposed item reads as current acceptance. | NOT RUN — cataloged 2026-08-30. |
| `QASYS-UC-014` | Correct a contradiction, stale status, broken link, wrong owner, and overclaimed result after reopening each primary source. | `GOV-007` / `QASYS-020` | primary owners and affected public files | source bytes, before/after assertion, links, evidence status, and scoped diff | Every correction follows current primary evidence; unknowns stay explicit and unrelated statements remain unchanged. | NOT RUN — cataloged 2026-08-30. |
| `QASYS-UC-015` | Give a fresh developer only the owning sources and ask them to explain and safely change the feature. | `GOV-008` / `QASYS-021` | owner doc, runtime owner, QA owner | explanation of background, goal, behavior, edges, integrations, development method, and proposed change | The developer recovers the complete public-safe contract without private conversation context or guesswork. | NOT RUN — cataloged 2026-08-30. |
| `QASYS-UC-016` | Run the full retained-row alignment audit with injected omission, contradiction, wrong owner, stale evidence, and overclaim controls. | `GOV-009` / `QASYS-022` | exact requirement/owner/QA/evidence inventory | per-row verdicts and remaining-gap records | Each defect fails closed and the inventory says aligned only when every recoverable defect is resolved. | NOT RUN — cataloged 2026-08-30. |
| `QASYS-UC-017` | Encounter routine missing local setup, an already-authorized browser path, and a genuine approval/security gate in one bounded task. | `GOV-013` / `QASYS-023` | local setup plus browser/computer path | actions, authorization boundary, blocker classification, and resulting state | Routine setup is completed without repeated user work; the genuine authority boundary remains blocked and is reported exactly. | NOT RUN — cataloged 2026-08-30. |
| `QASYS-UC-018` | Change one visible placement, remove unnecessary controls, and use it at supported widths, light/dark modes, keyboard/focus states, and accessibility settings. | `GOV-010`, `GOV-015` / `QASYS-024` | real browser or desktop surface | primary-action inventory, screenshots/DOM, interactions, focus order, contrast, reduced motion, console, and persistence | The result is sparse, obvious, product-specific, responsive, accessible, and interaction-complete; reviewer opinion is supporting evidence only. | NOT RUN — cataloged 2026-08-30. |
| `QASYS-UC-019` | Review proposed gates containing one sourced regression, a date-only refresh, a recreated old report, and an unrelated architecture expansion. | `GOV-021` / `QASYS-025` | source ledger, owner docs, QA diff | source-to-gap link, necessity, duplication, scope, and disposition | Only the sourced behavior/safety/compatibility/UX gate remains; ceremonial or scope-expanding items are removed. | NOT RUN — cataloged 2026-08-30. |
| `QASYS-UC-020` | Exercise every affected Browser/Desktop/Telegram/Voice surface and compare it with code, logs, DB, docs, generated files, and installed identity. | `GOV-011` / `QASYS-026` | real affected surfaces and supporting layers | visible/audible result, interactions, logs, DB/state, docs, generated and installed artifacts | All layers agree; unrun surfaces stay partial/blocked and the final report states the result briefly and truthfully. | NOT RUN — cataloged 2026-08-30. |

## `QASYS-001` - QA Operating Contract

- Requirement: `qa/README.md` and `docs/requirements_and_learnings/01_Key_Principles.md`.
- Risk covered: QA rules are tribal knowledge instead of clear project law.
- Preconditions: current checkout.
- Steps:
  1. Verify the QA operating contract and templates exist.
  2. Verify the user-grade evidence loop is present in project instructions.
  3. Verify public-safety terms are present in the QA contract and templates.
- Expected result: every agent can find the authoritative QA bar quickly.
- Forbidden result: a user-visible feature can be accepted by backend/log evidence alone.
- Evidence to capture: command result and missing instruction paths.
- Automation: `tests/release/test_qa_operating_contract.py`.
- Last run: PASS 2026-05-17; contract exists, tests pass, and agent-instruction paths resolve.

## `QASYS-002` - Feature Traceability

- Requirement: feature truth in `docs/requirements_and_learnings/`; acceptance truth in `qa/`;
  private source preservation in `CC-064` of
  `docs/requirements_and_learnings/56_Main_Continuity_Kernel.md`.
- Risk covered: features have docs but no cases, cases but no requirements link, or tests with no
  user-facing acceptance record; new exact source is lost or rewritten; superseded history is
  erased; or private text/identity enters the public proof.
- Preconditions: current requirement docs, QA folders, release tests, the authorized private
  continuity source ledger, and its public-safe aggregate receipt.
- Steps:
  1. List every feature requirement doc.
  2. For each feature, identify QA owner, case IDs, latest result, automated tests, and user-grade
     surface.
  3. At the private boundary, append every newly authorized user message byte-exactly. Assign its
     stable message ID and SHA-256 without changing an earlier record.
  4. When current truth changes, keep the superseded record and its stable identity, record the
     supersession link/disposition, and append the replacement instead of rewriting history.
  5. Regenerate only sanitized aggregate public proof: opaque aliases, counts, joins, dispositions,
     and digests. Do not publish raw text, task IDs, private paths, or private identity.
  6. Mark missing, indirect, non-durable, or non-verifiable mappings as gaps.
- Expected result: one simple public-safe table answers "what proves this feature works?" while the
  authorized private ledger proves byte-exact append/history continuity with stable IDs and hashes.
- Forbidden result: feature ownership depends on memory or scattered reports; a prior source row is
  modified or dropped; superseded history disappears; or raw/private evidence enters public proof.
- Evidence to capture: traceability matrix and orphan list, private byte/hash/ID append receipt,
  preserved supersession chain, and sanitized aggregate receipt/digest.
- Automation: `tests/release/test_qa_operating_contract.py`, exact public joins and privacy scan,
  authorized private ledger integrity check, and
  `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md` review.
- Last run: PARTIAL 2026-08-30; the current public-safe source receipt, requirement owners, exact
  case definitions, natural-use-case joins, links, and local trace checks resolve. The private
  byte-exact append, stable-ID/hash, superseded-history, and aggregate-only branch is NOT RUN. The
  durability gate also fails because several current owners and the receipt do not match `HEAD`.

## `QASYS-003` - QA Folder Shape

- Requirement: `qa/README.md` feature folder standard.
- Risk covered: a future agent cannot tell which report is current, what cases exist, or what gaps
  remain.
- Preconditions: current `qa/` folder.
- Steps:
  1. Inventory each top-level QA folder.
  2. Check for `README.md`, `cases.md`, and `reports/`.
  3. Verify legacy exceptions are tracked in `qa/_migration.md`.
- Expected result: active features converge on the standard shape; legacy gaps are explicit.
- Forbidden result: flat one-off reports accumulate with no case catalog.
- Evidence to capture: folder-shape table and migration backlog status.
- Automation: shell inventory plus `test_qa_operating_contract.py`.
- Last run: FAIL 2026-08-30; the current working tree contains the expected shapes, but multiple
  active owners and report homes are untracked, so a clean checkout loses them.

## `QASYS-004` - Full-View User Evidence

- Requirement: user-grade QA loop in `qa/README.md`, `01_Key_Principles.md`, and `AGENTS.md`.
- Risk covered: QA passes when code/logs look good but the user-facing product is broken.
- Preconditions: changed feature has a user-visible surface.
- Steps:
  1. Use the feature like a user through browser, computer, Telegram, voice, installer, CLI, MCP, or
     scheduler surface as appropriate.
  2. Compare visible result/UX with code, docs, logs, DB, generated artifacts, nested repos, and
     persisted state.
  3. Capture sanitized evidence and residual risk.
- Expected result: visible UX and supporting evidence agree.
- Forbidden result: logs, DB rows, unit tests, model completions, or source inspection substitute for
  required visible evidence.
- Evidence to capture: dated public-safe report with visible outcome, detail state, persistence,
  backend/log/DB confirmation, and final wording check.
- Automation: feature-specific Playwright/browser/computer/voice/Telegram harnesses where available.
- Last run: PASS 2026-05-17 for QA-system enforcement; feature-specific runs must record this loop.

## `QASYS-005` - Release Test Traceability

- Requirement: automated checks should point to requirements/cases they protect.
- Risk covered: tests fail without telling maintainers which user contract is broken, or cases go
  stale while tests evolve.
- Preconditions: current `tests/release/` and QA cases.
- Steps:
  1. Search release tests for QA case IDs or owning QA docs.
  2. Search cases for automation commands and last-run links.
  3. Identify tests without case links and cases without automation/result links.
- Expected result: release test names, case IDs, and QA reports form a lightweight graph.
- Forbidden result: release tests and QA reports become parallel, unsynchronized systems.
- Evidence to capture: test-to-case gap list.
- Automation: `tests/release/test_qa_operating_contract.py`.
- Last run: PARTIAL 2026-08-30; every release test has a central cases-based owner in the working
  tree, but the durability check fails while an owning case file remains untracked.

## `QASYS-006` - Agent Instruction Alignment

- Requirement: every agent-facing instruction file points to real docs and the same evidence rule.
- Risk covered: AI agents follow stale paths, skip QA, or treat partial evidence as done.
- Preconditions: current `AGENTS.md`, `CLAUDE.md`, `01_Key_Principles.md`, and QA docs.
- Steps:
  1. Verify the full-view evidence rule is present or clearly linked.
  2. Verify quick maps point to existing docs and QA folders.
  3. Verify agent instructions do not duplicate stale QA file names.
- Expected result: agent instructions stay lean and route to `qa/README.md` plus real feature QA.
- Forbidden result: always-loaded context references missing QA docs.
- Evidence to capture: broken path list and recommended replacements.
- Automation: `tests/release/test_qa_operating_contract.py`.
- Last run: PASS 2026-05-17; `AGENTS.md` and `CLAUDE.md` QA/requirement paths resolve.

## `QASYS-007` - Reproducible Public QA Records

- Requirement: public QA artifacts are tracked, sanitized, and reproducible from a fresh clone.
- Risk covered: local ignored records make tests pass on one machine but fail in a clean checkout.
- Preconditions: current git ignore rules and QA files.
- Steps:
  1. Compare QA files required by tests against tracked files.
  2. Inspect ignored QA result folders for public-safety or path-leak risks.
  3. Decide which artifacts are public records and which are private/local raw evidence.
- Expected result: required QA docs are tracked; raw results are ignored or private; public summaries
  use repo-relative paths and synthetic data.
- Forbidden result: a release test depends on an ignored local file.
- Evidence to capture: git ignored/tracked status and path-leak summary.
- Automation: `tests/release/test_qa_operating_contract.py`.
- Last run: FAIL 2026-08-30; public-safety scanning passes, but required source/QA records are
  untracked or have current bytes that do not match `HEAD`. Raw private evidence remains outside
  the public repository.

## `QASYS-008` - Full-View Evidence Gate

- Requirement: `qa/README.md` full-view evidence gate and `docs/requirements_and_learnings/01_Key_Principles.md`.
- Risk covered: an agent claims completion after reading code, logs, DB rows, mocks, or another
  model review without executing the required real user path.
- Preconditions: current agent docs, QA templates, and dated report rules.
- Steps:
  1. Verify agent-facing docs require the chain:
     `feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`.
  2. Verify the run-report template captures code, docs/nested docs, scripts/harnesses, logs,
     DB/state, generated/shipped artifacts, real user path, visual/UX comparison, and blocked/unrun
     surfaces.
  3. Verify new dated reports must include the full-view evidence checklist or explicitly carry a
     justified evidence exemption.
- Expected result: every non-trivial user-visible report makes the real QA path explicit.
- Forbidden result: a pass result that quietly substitutes mocks, unit tests, source inspection,
  logs, DB rows, or model review for a required user path.
- Evidence to capture: `test_qa_operating_contract.py` result and template/source inspection.
- Automation: `tests/release/test_qa_operating_contract.py`.
- Last run: PASS 2026-05-18; full-view evidence gate is enforced for agent docs and new reports.

## `QASYS-009` - Product-Wide Natural User Use-Case Checklist

- Requirement: `qa/README.md`, `qa/feature-user-use-case-checklist.md`, and
  `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`.
- Risk covered: QA starts with the one reported failure, one local test, or one code path and misses
  an obvious natural user action elsewhere in the product.
- Preconditions: current requirement docs, feature map, QA owners, and release tests.
- Steps:
  1. Verify the QA contract says to build a complete feature inventory before signoff.
  2. Verify the product-wide checklist lists natural use-case classes and maps them to feature areas.
  3. Verify each top-level feature case catalog has a `Natural User Use Case Checklist` section or is
     the template that creates one.
  4. Verify escaped cross-surface failures create cases in each affected owner.
- Expected result: every non-trivial feature QA pass has a feature inventory, natural use-case list,
  real user path, supporting evidence, and visible unresolved gaps.
- Forbidden result: a pass claim based on one mocked test, one config check, one log, or one
  successful case while other obvious user flows remain unlisted.
- Evidence to capture: contract-test output, checklist path, affected feature case links, and public
  safety scan.
- Automation: `tests/release/test_qa_operating_contract.py`.
- Last run: PASS 2026-05-18 for contract additions; individual feature reruns still own their
  feature-specific pass/fail status.

## `QASYS-010` - Honest Independent Review Loop

- Requirement: `GOV-012` in `qa/README.md` and the invoked `review-loop` workflow.
- Risk covered: a reviewer inherits the worker's reasoning, reviews stale bytes, skips revision,
  or reports a convenient score instead of the actual result.
- Preconditions: a bounded work product and explicit review criteria exist.
- Steps:
  1. Give a fresh-context reviewer the work product and evidence, not the worker's private reasoning.
  2. Record the score and actionable findings.
  3. Revalidate each accepted finding against primary sources, revise the work, and run a second
     fresh review.
  4. Continue toward 8/10 for no more than four loops. If the gate is still unmet, report the real
     score and remaining defects as `PARTIAL` or `BLOCKED`; never alter or suppress the verdict.
- Expected result: at least two fresh reviews, a revision between them, deterministic checks after
  the final edit, and an exact final score with any remaining defects.
- Forbidden result: a stale or self-review is called independent, model opinion replaces required
  tests/user-path evidence, or a score is inflated to support a completion claim.
- Evidence to capture: review receipts, scores, findings, accepted/rejected rationale, revisions,
  verification commands, and residual gaps.
- Automation: exact receipt and source-coverage contract assertions in
  `tests/release/test_qa_operating_contract.py`; review judgment remains independent.
- Last run: PARTIAL 2026-08-30; the current source-alignment review loop has not reached its final
  frozen-byte verdict.

## `QASYS-011` - Change Scope And Authorization Boundary

- Requirement: `CORE-014` in `docs/requirements_and_learnings/01_Key_Principles.md`.
- Risk covered: a diagnosis or proposal is treated as implementation authority, or a bounded fix
  overwrites unrelated work.
- Preconditions: one diagnosis-only request, one explicit bounded-fix request, and an unrelated
  synthetic dirty-file fixture.
- Steps:
  1. Verify the diagnosis-only path performs read-only inspection and proposes no external write.
  2. Verify the bounded-fix path changes only the exact owner files needed by source evidence.
  3. Compare before/after status and prove the unrelated fixture is byte-identical.
- Expected result: action stays inside the request's authority and the smallest evidence-backed
  change preserves unrelated work.
- Forbidden result: diagnosis mutates state, the fix expands scope without authority, or unrelated
  bytes are rewritten, staged, stashed, or discarded.
- Evidence to capture: sanitized request classes, before/after paths and hashes, scoped diff, and
  verification result.
- Automation: focused QA operating-contract test plus a synthetic repository fixture.
- Last run: NOT RUN — cataloged 2026-08-30.

## `QASYS-012` - Short Honest Completion Report

- Requirement: `CORE-015` in `docs/requirements_and_learnings/01_Key_Principles.md`.
- Risk covered: a long or vague completion report hides an unrun, failed, partial, or blocked gate.
- Preconditions: a synthetic work result with verified evidence and at least one explicit open gate.
- Steps:
  1. Build the final report from the exact executed and unexecuted checks.
  2. Verify the wording is short, plain, evidence-based, and uses canonical status terms.
  3. Verify no open gate is converted into a completion claim.
- Expected result: the reader can distinguish verified results from open gates without reading
  internal reasoning or raw evidence.
- Forbidden result: omitted blockers, unsupported success language, raw private evidence, or detail
  that obscures the result.
- Evidence to capture: sanitized source status, final report, status-token check, and privacy scan.
- Automation: focused QA operating-contract test and report-lint fixture.
- Last run: NOT RUN — cataloged 2026-08-30.

## Release Test Traceability

- `tests/release/test_qa_operating_contract.py`
- `tests/release/test_qa_results_public_safety.py`
