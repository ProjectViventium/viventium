<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
# Claude Final Review Prompt - 2026-05-17

You are reviewing a local Viventium repository repair. Do not edit files. Return findings only.

## Goal

Review whether the current local diff adequately fixes the QA-system audit verdict:

> The QA philosophy is good and unusually explicit, but the system is not yet world-class complete.
> The biggest gaps are feature-to-QA traceability, legacy folder shape, release tests not naming QA
> cases, stale CLAUDE.md QA paths, weak enforcement of report evidence headings, and missing checks
> for ignored required QA files.

Also review the source-of-truth prompt/background-agent repairs that were needed for the full release
suite to pass.

## Constraints

- Review only; do not make changes.
- Treat user/local changes as protected. Do not recommend reverting unrelated dirty files.
- Public repo artifacts must not include secrets, personal data, raw logs, raw DB rows, local
  absolute paths, account identifiers, private screenshots, or secret-bearing command lines.
- Do not suggest cloud sync, push, commit, or live agent changes.
- Prefer simple, low-process QA structure over heavy bureaucracy.

## What Was Changed In This Repair

- Added/updated QA system docs:
  - `qa/qa-system-audit/README.md`
  - `qa/qa-system-audit/cases.md`
  - `qa/qa-system-audit/reports/2026-05-17-local-runtime-and-qa-repair.md`
  - `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`
  - `qa/_migration.md`
  - `qa/release-test-owners.yaml`
  - `qa/results/README.md`
- Added standard `README.md`, `cases.md`, and `reports/` homes for legacy/missing QA feature areas,
  including citation rendering, agent streaming usage, branding/assets, no-response, Red Team,
  scheduling cortex, MCP tooling, web search, config alignment, and the existing legacy QA folders.
- Hardened `tests/release/test_qa_operating_contract.py` so release tests have a central cases-based
  QA owner, standard QA folders have README/cases/reports, required public QA files are not ignored,
  raw timestamped results remain ignored, and agent docs do not reference missing QA/requirement paths.
- Updated `CLAUDE.md` to point at existing QA paths and the full-view evidence rule.
- Repaired Viventium source-of-truth prompt/background-agent drift:
  - `viventium_v0_4/LibreChat/viventium/source_of_truth/local.viventium-agents.yaml`
  - `viventium_v0_4/LibreChat/viventium/source_of_truth/local.librechat.yaml`
  - `docs/requirements_and_learnings/34_Voice_Chat_LLM_Override.md`
  - `tests/release/test_background_agent_governance_contract.py`
- The source-of-truth YAML now resolves registry-owned prompts, uses activation fallback chains,
  includes runtime-owned background-card guardrails, restores launch-ready background model families,
  adds declared web/code tools where prompts require them, and uses `claude-sonnet-4-5` with
  `thinking: false` for the public Anthropic voice route.

## Verification Already Run

- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_background_agent_governance_contract.py tests/release/test_productivity_activation_source_of_truth.py tests/release/test_prompt_registry.py -q`
  - Result: `54 passed`
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_qa_operating_contract.py -q`
  - Result: `10 passed`
- `uv run --with pytest --with pyyaml python -m pytest tests/release -q`
  - Result: `585 passed, 3 skipped`
- Playwright browser smoke:
  - `http://localhost:3190/login`: title `Viventium`, visible login UI, 0 console errors
  - `http://localhost:3300/`: title `Viventium Voice Assistant`, visible voice controls, 0 console errors
- Local status/curl smoke:
  - API, frontend, playground, GlassHive API, Scheduling Cortex MCP, GlassHive MCP, and Google
    Workspace MCP responded in expected ready/auth-negotiation classes.
  - RAG, Microsoft 365 MCP, SearXNG, and Firecrawl did not respond during this local run and are
    recorded as residual local availability notes, not release pass claims.
- Public-safety scan over changed QA/docs/tests/scripts and Viventium source-of-truth prompt files:
  clean after allowing only synthetic `example.com` fixtures.

## Review Questions

1. Are there any remaining high-severity gaps in the QA-system fix, especially traceability,
   cases-based release ownership, report evidence requirements, ignored required files, or stale
   agent instruction paths?
2. Does the repair introduce overcomplicated QA process, or is it a simple enough path-of-least-
   resistance structure?
3. Are any public-safety leaks visible in the reviewed public QA/docs/source-of-truth files?
4. Are there source-of-truth model/prompt/tool changes that look risky or inconsistent with the
   documented launch baseline?
5. Are the tests and browser/runtime evidence sufficient for the QA-system repair claim? If not,
   name the missing evidence precisely.

Return JSON using the required schema with findings, risks, tests_to_add, alternatives, and evidence.
