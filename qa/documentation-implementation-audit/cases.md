# Documentation / Implementation Audit QA Cases

## Case ID Convention

Use stable `DOCIMPL-NNN` case IDs for repository-wide documentation/implementation alignment checks.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `DOCIMPL-001` | Repo topology and systems map reflect real product parts | Users and maintainers can find the owning code/doc/test for every major feature | Docs, scripts, nested repos | Inventory plus manual trace | 2026-05-17 partial |
| `DOCIMPL-002` | Markdown docs do not point to missing local targets | Public docs are navigable | Docs | Local markdown link scanner | 2026-05-17 fail |
| `DOCIMPL-003` | Config schema/examples/wizard/compiler/runtime docs agree | Installers and users configure the product using documented fields | Config compiler, examples, docs | Release compiler tests plus manual schema trace | 2026-05-17 fail |
| `DOCIMPL-004` | Background-agent source of truth matches governance contracts | Agent behavior, tools, model routing, and prompt governance match docs/tests | LibreChat source-of-truth YAML, tests | Background-agent governance tests | 2026-05-17 fail |
| `DOCIMPL-005` | Runtime code does not use undocumented keyword gates for intent/tool behavior | Natural-language requests are not silently suppressed by brittle word lists | Telegram/runtime tool loading | Source inspection plus guardrail test review | 2026-05-17 fail/gap |
| `DOCIMPL-006` | Audit reports remain public-safe | QA artifacts can be shared without leaking private runtime state | QA docs | Manual public-safety review | 2026-05-17 pass |
| `DOCIMPL-007` | Shipped/vendored components have provenance, pins, docs, and QA owners | Release reviewers can prove what code is shipped and why | Component repos, vendored services, MCPs | Component inventory plus provenance test | 2026-05-17 fail/gap |

## `DOCIMPL-001` - Repo Topology and Systems Map Coverage

- Requirement: `docs/02_ARCHITECTURE_OVERVIEW.md`, `docs/03_SYSTEMS_MAP.md`,
  `docs/requirements_and_learnings/01_Key_Principles.md`.
- Risk covered: high-level docs omit active product surfaces or still describe retired topology.
- Preconditions: current checkout with nested repos present.
- Steps:
  1. Inventory parent repo files, docs, tests, scripts, and QA folders.
  2. Inventory nested git repos and compare local HEADs to `components.lock.json`.
  3. Compare discovered components to architecture, systems map, runtime docs, and requirement docs.
- Expected result: each active product surface has a current owning doc, runtime owner, and QA owner.
- Forbidden result: high-level docs still send users to missing or retired paths without status labels.
- Evidence to capture: public-safe component list, missing docs list, stale section references.
- Automation: shell inventory plus manual doc/code trace.
- Last run: 2026-05-17, partial; report captures current gaps.

## `DOCIMPL-002` - Markdown Link Integrity

- Requirement: public docs must be navigable and traceable.
- Risk covered: setup, runtime, and feature docs reference deleted files or private-only artifacts.
- Preconditions: current checkout; ignored runtime/private folders excluded.
- Steps:
  1. Scan markdown files for local links.
  2. Ignore external URLs and intentional non-file placeholders when clearly marked.
  3. Verify each local markdown/file link exists in the public tree.
- Expected result: no missing public local links, or every intentionally historical link is clearly
  marked as archived/private.
- Forbidden result: public setup/runtime docs point to nonexistent `.md` files, missing examples, or
  unstated private-only documents.
- Evidence to capture: missing target list with repo-relative source files.
- Automation: local markdown link scanner.
- Last run: 2026-05-17 fail; 32 missing local markdown targets were found, with several likely
  high-impact docs links.

## `DOCIMPL-003` - Config Compiler Source of Truth Alignment

- Requirement: `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md` and public
  config examples/schema.
- Risk covered: users follow documented config fields that schema rejects or examples omit; runtime
  behavior differs from docs.
- Preconditions: current `config.schema.yaml`, examples, wizard, compiler, and release tests.
- Steps:
  1. Compare documented config fields to schema properties.
  2. Compare schema to `scripts/viventium/config_compiler.py` and `scripts/viventium/wizard.py`.
  3. Run release compiler/guardrail tests.
- Expected result: schema, examples, wizard, compiler, generated outputs, docs, and tests agree.
- Forbidden result: fields implemented in compiler are absent from schema, docs contradict runtime,
  or examples encode conflicting defaults.
- Evidence to capture: field names, source/doc references, test command result.
- Automation: compiler tests plus manual trace.
- Last run: 2026-05-17 fail/gaps found.

## `DOCIMPL-004` - Background-Agent Governance Contract

- Requirement: `docs/requirements_and_learnings/02_Background_Agents.md`,
  `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`, and release tests.
- Risk covered: source-of-truth agent YAML drifts from documented models, tools, fallback behavior,
  prompt refs, cards, and voice routing.
- Preconditions: current `viventium_v0_4/LibreChat/viventium/source_of_truth/local.viventium-agents.yaml`.
- Steps:
  1. Run productivity activation and background-agent governance release tests.
  2. Inspect failing assertions against source-of-truth YAML and docs.
  3. Treat failures as release blockers until docs/tests/source are intentionally reconciled.
- Expected result: tests pass or the docs/tests are intentionally updated to the new product truth.
- Forbidden result: release docs promise unavailable fallback/tool/card/model behavior.
- Evidence to capture: failing test names and sanitized mismatch summaries.
- Automation: background-agent governance pytest suites.
- Last run: 2026-05-17 fail; 13 failures.

## `DOCIMPL-004B` - Prompt Registry Sync Resolver Coverage

- Requirement: prompt source-of-truth files must resolve into live-syncable instructions without
  dropping included guardrail blocks.
- Risk covered: docs/source markdown contains the right behavior but the sync resolver omits it from
  generated agent instructions.
- Preconditions: current LibreChat source-of-truth prompt registry and sync script.
- Steps:
  1. Run `tests/release/test_prompt_registry.py`.
  2. Verify `resolvePromptRefs` output includes prompt blocks referenced by `includes:` frontmatter.
  3. Compare resolved output to governance tests for main-agent instructions and runtime cards.
- Expected result: included prompt fragments are present in resolved agent instructions.
- Forbidden result: live sync silently drops included guardrails while source markdown appears correct.
- Evidence to capture: failing test name, missing resolved text summary, source include path.
- Automation: prompt-registry pytest suite.
- Last run: 2026-05-17 fail; one prompt-registry failure reproduced.

## `DOCIMPL-005` - Runtime Keyword-Gate Drift

- Requirement: `docs/requirements_and_learnings/01_Key_Principles.md` no-runtime-NLU rule and
  background activation source-of-truth rules.
- Risk covered: runtime behavior silently depends on hardcoded keyword lists not represented in
  activation prompts, config schema, or QA.
- Preconditions: current LibreChat fork.
- Steps:
  1. Search runtime code for keyword/regex gates that affect intent, providers, tools, or productivity scope.
  2. Compare findings to `tests/release/test_no_runtime_nlu.py`.
  3. Add a synthetic regression when an undocumented runtime gate is found.
- Expected result: either no runtime keyword gates exist, or any intentional exception is explicitly
  documented, configured, and covered by tests.
- Forbidden result: generic natural-language requests fail because the runtime word list did not
  include a valid phrasing.
- Evidence to capture: source path, behavior affected, missing guardrail test.
- Automation: source inspection plus release guardrail tests.
- Last run: 2026-05-17 fail/gap; a Telegram tool-intent keyword guard exists and the guardrail test
  does not currently catch that class of drift.

## `DOCIMPL-006` - Public-Safe Audit Artifact

- Requirement: public/private boundary in `docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md`.
- Risk covered: documentation audits accidentally publish local runtime paths, logs, private account
  identifiers, raw DB rows, or secret-bearing evidence.
- Preconditions: public report draft exists.
- Steps:
  1. Keep raw logs, DB rows, private prompts, local App Support state, and IDs out of the report.
  2. Use repo-relative paths for public docs.
  3. Summarize runtime evidence with counts and conclusions only.
  4. Review the public-safety checklist before finalizing.
- Expected result: report is reusable and public-safe.
- Forbidden result: leaked tokens, personal identifiers, private paths, raw runtime rows, or private
  account content in QA docs.
- Evidence to capture: checklist status.
- Automation: manual public-safety review.
- Last run: 2026-05-17 pass for newly added audit docs.

## `DOCIMPL-007` - Vendored/Shipped Component Provenance

- Requirement: public/private boundary and nested-component release rules in `AGENTS.md` and
  `docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md`.
- Risk covered: full vendored projects ship without a nested repo pin, provenance note, source-of-truth
  doc, or QA owner.
- Preconditions: current `viventium_v0_4/` component tree and `components.lock.json`.
- Steps:
  1. Walk component directories for project roots with their own license/build/test metadata.
  2. Verify each shipped project is either a nested git repo represented in `components.lock.json` or
     an intentional vendored component with explicit provenance and QA docs.
  3. Verify public docs explain whether the component is active, paused, experimental, or historical.
- Expected result: every shipped component has a clear pin/provenance story and acceptance owner.
- Forbidden result: release reviewers cannot tell whether an in-tree service/MCP is public-shipped,
  private-only, stale, or intentionally vendored.
- Evidence to capture: component path, project markers, lock-file status, owning doc/QA status.
- Automation: component-provenance release test to add.
- Last run: 2026-05-17 fail/gap; multiple unpinned/underdocumented vendored component surfaces found.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Documentation Implementation Audit. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `DOCIMPL-UC-001` | On Docs, scripts, nested repos, verify that repo topology and systems map reflect real product parts. | owning requirement for `DOCIMPL-001` / `DOCIMPL-001` | Docs, scripts, nested repos | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to DOCIMPL-001. | Users and maintainers can find the owning code/doc/test for every major feature | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `DOCIMPL-UC-002` | On Docs, try markdown docs do not point to missing local targets with missing setup, missing auth/config, empty state, or a degraded dependency. | owning requirement for `DOCIMPL-002` / `DOCIMPL-002` | Docs | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to DOCIMPL-002. | The user sees an honest setup, retry, or degraded-state result for DOCIMPL-002; no fake success is accepted. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `DOCIMPL-UC-003` | After config schema/examples/wizard/compiler/runtime docs agree, refresh, restart, retry, or switch linked surfaces and verify persistence/parity. | owning requirement for `DOCIMPL-003` / `DOCIMPL-003` | Config compiler, examples, docs | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to DOCIMPL-003. | DOCIMPL-003 remains correct after the persistence or parity step and final wording matches evidence. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
