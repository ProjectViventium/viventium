# QA System Audit Cases

## Case ID Convention

Use stable `QASYS-NNN` IDs for QA-system structure, traceability, evidence, and process checks.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `QASYS-001` | QA operating contract is present and authoritative | Developers know the minimum QA bar | `qa/README.md`, `01_Key_Principles.md`, agent instructions | `test_qa_operating_contract.py` plus source inspection | 2026-05-17 pass |
| `QASYS-002` | Every feature maps requirement -> QA owner -> cases -> tests -> results | No feature is orphaned from QA | Requirement docs, `45_Runtime_Feature_QA_Map.md`, QA folders | Manual traceability matrix | 2026-05-17 pass |
| `QASYS-003` | QA folders use the living README/cases/reports shape or are tracked in migration | QA records are predictable and easy to update | `qa/<feature>/` | Folder inventory plus migration review | 2026-05-17 pass |
| `QASYS-004` | User-grade full-view evidence is required and recorded | Visible UX, logs, DB, code, docs, and artifacts agree | Browser, Telegram, voice, CLI, MCP, scheduler, GlassHive | Manual evidence review plus feature harnesses | 2026-05-17 contract pass; feature runs required |
| `QASYS-005` | Automated tests reference QA cases or owning QA docs | Release failures point to product requirements | `tests/release/`, QA cases | Source grep plus planned parity test | 2026-05-17 pass |
| `QASYS-006` | Agent instructions point to real QA docs and the same evidence rule | AI agents do not follow stale paths or backend-only acceptance | `AGENTS.md`, `CLAUDE.md`, `01_Key_Principles.md`, `qa/README.md` | Link/path review plus planned contract test | 2026-05-17 pass |
| `QASYS-007` | Public QA records are tracked or intentionally private/ignored | Fresh clones and public exports have reproducible QA context | `qa/`, `.gitignore`, release tests | Git ignored/tracked review plus public-safety scan | 2026-05-17 pass |
| `QASYS-008` | Full-view evidence gate blocks hand-waved completion | Agents must name unrun user paths as blocked/partial | Agent docs, QA templates, dated reports | `test_qa_operating_contract.py` plus report-template review | 2026-05-18 pass |
| `QASYS-009` | Product-wide natural user use-case checklist is mandatory | QA starts from all features and obvious user actions, not one symptom | `45_Runtime_Feature_QA_Map.md`, `qa/feature-user-use-case-checklist.md`, `qa/*/cases.md` | `test_qa_operating_contract.py` plus feature checklist review | 2026-05-18 pass |

## Natural User Use Case Checklist

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `QASYS-UC-001` | Developer starts a fix by reading the feature map and enumerating all obvious user use cases. | `QASYS-009` | Docs and QA contract | `45_Runtime_Feature_QA_Map.md`, `qa/feature-user-use-case-checklist.md`, affected `qa/<feature>/cases.md`, release tests | A checklist exists before pass/fail claims. | 2026-05-18 PASS |
| `QASYS-UC-002` | Escaped user-visible failure crosses feature boundaries. | `QASYS-004`, `QASYS-009` | Real browser/computer plus logs/DB/state | Feature cases, visible UI, logs, DB/state, docs, generated config | A synthetic regression is added to every affected owner and unrun fixes remain visible. | 2026-05-18 PASS for contract; product fix pending in affected owners |
| `QASYS-UC-003` | Agent prepares a release/public-ready diff. | `QASYS-007` | Git diff and QA/report scan | tracked files, ignored files, public-safety scan, staged diff | No private data, local paths, raw IDs, screenshots, or secrets are published. | 2026-05-18 pending final diff review |

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
- Last run: 2026-05-17 pass; contract exists, tests pass, and agent-instruction paths resolve.

## `QASYS-002` - Feature Traceability

- Requirement: feature truth in `docs/requirements_and_learnings/`; acceptance truth in `qa/`.
- Risk covered: features have docs but no cases, cases but no requirements link, or tests with no
  user-facing acceptance record.
- Preconditions: current requirement docs, QA folders, and release tests.
- Steps:
  1. List every feature requirement doc.
  2. For each feature, identify QA owner, case IDs, latest result, automated tests, and user-grade
     surface.
  3. Mark missing or indirect mappings as gaps.
- Expected result: one simple table answers "what proves this feature works?"
- Forbidden result: feature ownership depends on memory or scattered reports.
- Evidence to capture: traceability matrix and orphan list.
- Automation: `tests/release/test_qa_operating_contract.py` plus `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md` review.
- Last run: 2026-05-17 pass; requirement rows have QA owners and case catalogs.

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
- Last run: 2026-05-17 pass; top-level feature folders have standard README/cases/reports homes.

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
- Last run: 2026-05-17 pass for QA-system enforcement; feature-specific runs must record this loop.

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
- Last run: 2026-05-17 pass; every release test has a central cases-based QA owner.

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
- Last run: 2026-05-17 pass; `AGENTS.md` and `CLAUDE.md` QA/requirement paths resolve.

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
- Last run: 2026-05-17 pass; required public QA docs are unignored and timestamped raw result
  subfolders stay ignored.

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
- Last run: 2026-05-18 pass; full-view evidence gate is enforced for agent docs and new reports.

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
- Last run: 2026-05-18 pass for contract additions; individual feature reruns still own their
  feature-specific pass/fail status.

## Release Test Traceability

- `tests/release/test_qa_operating_contract.py`
- `tests/release/test_qa_results_public_safety.py`
