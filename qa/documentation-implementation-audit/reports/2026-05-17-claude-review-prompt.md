<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
You are a second-opinion reviewer on a local engineering audit task.

Workspace:
- Repo root: the directory passed as the first argument to the Claude review helper.
- This repo has nested component repos under `viventium_v0_4/`.

Objective:
- Do a max-effort review-only pass over Codex's documentation/implementation audit.
- Verify whether the audit missed important documentation/code/test/runtime mismatches.
- Challenge weak findings, identify stronger evidence, and propose gaps to add.
- Do not make changes.

Primary audit artifact to review:
- `qa/documentation-implementation-audit/reports/2026-05-17-full-codebase-doc-implementation-audit.md`
- `qa/documentation-implementation-audit/README.md`
- `qa/documentation-implementation-audit/cases.md`

Core instructions and source-of-truth docs to inspect:
- `AGENTS.md`
- `docs/requirements_and_learnings/01_Key_Principles.md`
- `docs/02_ARCHITECTURE_OVERVIEW.md`
- `docs/03_SYSTEMS_MAP.md`
- `docs/04_SETUP_GUIDE.md`
- `docs/05_ENVIRONMENT.md`
- `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
- `docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md`
- `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`
- `docs/requirements_and_learnings/47_Remote_Access_and_Tunneling.md`
- `docs/requirements_and_learnings/50_Stable_Dev_Runtime.md`
- `docs/requirements_and_learnings/51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`
- `qa/README.md`
- `viventium_v0_4/docs/README.md`
- `viventium_v0_4/docs/IMPLEMENTATION_INDEX.md`
- `viventium_v0_4/docs/EXPECTED_BEHAVIOR.md`
- `viventium_v0_4/docs/DEVELOPMENT_GUIDE.md`

Implementation/config/test areas to inspect:
- `bin/viventium`
- `scripts/viventium/`
- `config.schema.yaml`
- `config.full.example.yaml`
- `config.minimal.example.yaml`
- `tests/release/`
- `apps/macos/ViventiumHelper/`
- `viventium_v0_4/LibreChat/viventium/source_of_truth/`
- `viventium_v0_4/LibreChat/api/server/services/viventium/`
- `viventium_v0_4/voice-gateway/`
- `viventium_v0_4/telegram-viventium/`
- `viventium_v0_4/telegram-codex/`
- `viventium_v0_4/GlassHive/`
- `viventium_v0_4/prompt-workbench/`
- `viventium_v0_4/MCPs/`

Observed evidence from Codex's pass:
- Nested component pins in `components.lock.json` matched local component HEADs at the time of the
  audit, but the parent and LibreChat working trees were dirty and several nested repos were behind
  origin.
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_productivity_activation_source_of_truth.py tests/release/test_background_agent_governance_contract.py -q`
  failed with 13 failures and 20 passes.
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_config_compiler.py tests/release/test_no_runtime_nlu.py tests/release/test_qa_operating_contract.py tests/release/test_project_boundary_contamination.py -q`
  passed with 102 tests.
- A local markdown link scan excluding ignored/private/runtime folders found 32 missing local markdown
  targets.
- Runtime evidence was intentionally sanitized: only local ignored artifact presence, selected log
  metadata, and SQLite table names/counts were inspected. Do not export raw logs, rows, IDs, secrets,
  private prompts, local runtime paths, account identifiers, or personal data.

Claims to validate or challenge:
- Background-agent governance drift is the highest-risk finding.
- Config schema/examples/wizard/compiler/docs are misaligned around `runtime.dev_env`, transcript
  `ignore_globs`, `integrations.web_search`, Telegram STT inheritance, and conversation recall default.
- Top-level architecture/system docs and runtime implementation index are stale relative to active
  v0.4 product surfaces.
- Several public markdown docs point to missing local files.
- `telegramToolGuard.js` is an undocumented runtime keyword/tool-intent gate that may fall outside
  the repo's no-runtime-NLU contract or at least needs an explicit exception and tests.
- Prompt Workbench, GlassHive workflow adapters, Telegram Codex, macOS helper, and some MCP/sidecar
  surfaces are implemented/present but underdocumented in high-level maps.
- QA coverage is uneven across some requirement docs.

Constraints:
- Review only. Do not edit files, run destructive commands, stage, commit, push, or modify runtime state.
- Keep all output public-safe.
- Tie claims to concrete evidence: file paths, test names, docs sections, or code owners.
- Prefer high-signal findings over exhaustive noise.
- If you need to inspect ignored runtime/log/db folders, summarize only counts/schema/metadata and do
  not quote private content.
- Treat existing uncommitted changes as user-owned.

Non-goals:
- Do not solve or implement the fixes in this pass.
- Do not re-litigate product strategy unless it directly affects doc/code/test mismatch.
- Do not recommend broad rewrites where a targeted doc/test/source reconciliation is enough.

What I want back:
- Findings Codex missed, ordered by severity.
- Findings Codex overstated or should weaken.
- Stronger evidence to attach to the current findings.
- Specific tests/QA cases to add.
- A recommended repair order.
- Any public/private-safety risks in the audit itself.

Return JSON that matches the structured review helper schema:
- `full_final_recommendations`
- `summary`
- `findings`
- `risks`
- `tests_to_add`
- `alternatives`
- `evidence`
