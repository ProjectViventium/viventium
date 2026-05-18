# Documentation / Implementation Audit QA

## Scope

- Owning requirements docs: `docs/requirements_and_learnings/01_Key_Principles.md`,
  `docs/02_ARCHITECTURE_OVERVIEW.md`, `docs/03_SYSTEMS_MAP.md`,
  `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`,
  `docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md`,
  `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`,
  `docs/requirements_and_learnings/50_Stable_Dev_Runtime.md`, and
  `docs/requirements_and_learnings/51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`.
- Runtime/code owners: parent installer/config/compiler/QA tree, `viventium_v0_4/LibreChat`,
  `viventium_v0_4/voice-gateway`, `viventium_v0_4/GlassHive`,
  `viventium_v0_4/telegram-viventium`, `viventium_v0_4/telegram-codex`,
  `viventium_v0_4/prompt-workbench`, MCP component repos, and macOS helper surfaces.
- User-visible surfaces: install/configure/upgrade CLI, status-bar helper, LibreChat web UI,
  voice calls, Telegram, prompt workbench, GlassHive/workflow command surfaces, remote access, and
  continuity/restore flows.
- Out of scope: fixing the identified gaps in this audit run.

## Quality Bar

- Primary user outcome: the public docs, QA contracts, source-of-truth config, implementation, and
  release checks describe the same product.
- Speed/latency expectation: not applicable to this meta-audit except where runtime features
  already carry latency requirements in their owning docs.
- Persistence/reload expectation: docs and QA reports must preserve reusable evidence without
  raw private runtime state.
- Failure behavior: release-blocking mismatches should be explicit, testable, and linked to owners.
- Public/private boundary: reports must summarize logs, DBs, ignored artifacts, and local runtime
  evidence without exposing secrets, personal identifiers, raw IDs, raw private prompts, local
  absolute paths, or runtime dumps.

## Environments

- Local: current public Viventium checkout with nested component repos present.
- CI: release pytest suites under `tests/release/`.
- Connected-account or external-service assumptions: none required for this audit; connected-account
  runtime evidence was not exported.
- Synthetic fixtures: test suites and public-safe docs/QA artifacts only.

## Required Suites

| Suite | Command or Manual Path | Required When | Last Run |
| --- | --- | --- | --- |
| Release docs/config guardrails | `uv run --with pytest --with pyyaml python -m pytest tests/release/test_config_compiler.py tests/release/test_no_runtime_nlu.py tests/release/test_qa_operating_contract.py tests/release/test_project_boundary_contamination.py -q` | Every broad docs/runtime audit | 2026-05-17 pass |
| Background-agent governance | `uv run --with pytest --with pyyaml python -m pytest tests/release/test_productivity_activation_source_of_truth.py tests/release/test_background_agent_governance_contract.py -q` | Every agent source-of-truth or docs audit | 2026-05-17 fail |
| Prompt registry / sync resolver | `uv run --with pytest --with pyyaml python -m pytest tests/release/test_prompt_registry.py -q` | Every prompt registry or live-sync change | 2026-05-17 fail |
| Markdown link scan | Local markdown link scanner excluding ignored/private runtime folders | Every docs topology audit | 2026-05-17 fail |
| Nested repo/pin inventory | `git status`, `git rev-parse HEAD`, `components.lock.json` comparison | Before release-readiness claims | 2026-05-17 pass with dirty/behind caveats |
| User-grade surface QA | Browser/Telegram/voice/manual flow appropriate to the changed feature | Before closing a feature implementation fix | Not applicable: audit-only report |

## Coverage Matrix

| Requirement / Surface | Cases | Last Full Run |
| --- | --- | --- |
| Docs and implementation inventory agree on components and responsibilities | `DOCIMPL-001` | 2026-05-17 partial |
| Broken or stale documentation references are reusable defects | `DOCIMPL-002` | 2026-05-17 fail |
| Config schema, examples, wizard, compiler, tests, and docs agree | `DOCIMPL-003` | 2026-05-17 fail |
| Agent source-of-truth matches governance docs and release checks | `DOCIMPL-004` | 2026-05-17 fail |
| Runtime intent/provider/productivity behavior avoids undocumented keyword gates | `DOCIMPL-005` | 2026-05-17 fail/gap |
| Public/private boundary is preserved in QA artifacts | `DOCIMPL-006` | 2026-05-17 pass for this report |
| Vendored or shipped component provenance is documented and pinned | `DOCIMPL-007` | 2026-05-17 fail/gap |

## Current Status

- Last full QA: 2026-05-17 audit pass.
- Current result: significant documentation/implementation drift found; details in the dated report
  and Claude second-opinion summary.
- Known gaps: this audit did not repair the drift, run connected-account UI flows, or verify a fresh
  clone/install.
- Next required hardening: fix the release-test failures first, then refresh the high-level docs and
  schema/examples around the corrected product truth.
