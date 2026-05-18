# 2026-05-17 Local Runtime and QA-System Repair

## Summary

- Result: pass for QA-system repair and core local browser smoke.
- Build/source under test: current local checkout plus nested Viventium source-of-truth files.
- Runtime/artifact under test: local Viventium runtime started through the public CLI.
- Environment: local development runtime.
- Related change: QA operating-contract repair, feature traceability repair, and prompt/source drift
  repair.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `QASYS-001` | pass | QA contract tests | Operating contract, agent docs, templates, and public-safety terms verified |
| `QASYS-002` | pass | Feature QA map and standard case catalogs | Requirement rows now have direct QA owners or owner sets |
| `QASYS-003` | pass | Folder-shape enforcement | Feature QA folders have README/cases/reports homes |
| `QASYS-004` | contract pass | Playwright smoke plus substitution-check enforcement | Core browser surfaces verified; feature-specific flows must rerun when changed |
| `QASYS-005` | pass | `qa/release-test-owners.yaml` and release test | Release tests have cases-based owners |
| `QASYS-006` | pass | Agent path contract test | `AGENTS.md` and `CLAUDE.md` QA/requirement paths resolve |
| `QASYS-007` | pass | Git-ignore contract and public-safety scan | Public QA docs are unignored; raw timestamped results remain ignored |

## User-Grade Evidence

- Repair the QA operating-system gaps identified in the QA audit verdict.
- Verify the local Viventium runtime through public/local entrypoints.
- Keep evidence public-safe: no local absolute paths, account identifiers, raw logs, raw DB rows,
  tokens, screenshots, or private runtime dumps.

| Surface | Evidence | Result |
| --- | --- | --- |
| Viventium status | Public CLI status command | Core local surfaces ready; frontend, API, playground, Telegram bridge, Telegram Codex, Google Workspace MCP, Scheduling Cortex, GlassHive, MongoDB, Meilisearch, and LiveKit reported reachable or configured as expected, with degraded optional services called out below |
| LibreChat login | Playwright browser visit to `http://localhost:3190/login` | Page title `Viventium`; visible login copy, email/password inputs, and Continue action; 0 console errors |
| Modern Playground | Playwright browser visit to `http://localhost:3300/` | Page title `Viventium Voice Assistant`; visible voice assistant controls for listening, speaking, and backup voice; 0 console errors |
| Core HTTP smoke | Local HTTP status probes | API health, login page, playground, GlassHive API, Scheduling Cortex MCP, GlassHive MCP, and Google Workspace MCP responded with expected ready/auth-negotiation classes |

Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
tests were treated as supporting evidence, not substitutes for the required visible browser check.

## Automated Evidence

```bash
uv run --with pytest --with pyyaml python -m pytest tests/release/test_qa_operating_contract.py -q
uv run --with pytest --with pyyaml python -m pytest tests/release/test_background_agent_governance_contract.py tests/release/test_productivity_activation_source_of_truth.py tests/release/test_prompt_registry.py -q
uv run --with pytest --with pyyaml python -m pytest tests/release -q
```

Results:

- QA operating contract: `12 passed`
- Background/productivity/prompt source contracts: `54 passed`
- Full release suite: `587 passed, 3 skipped`
- Browser smoke: 2 surfaces passed, 0 console errors
- Public-safety scan: clean across changed/untracked text candidates in the root repo and nested
  LibreChat repo

## Findings

### Degraded Or Optional Local Services

- Conversation Recall/RAG endpoint did not respond during this run.
- Microsoft 365 MCP endpoint did not respond during this run.
- Local SearXNG and Firecrawl endpoints did not respond during this run.
- These are recorded as local runtime availability notes, not public-release pass claims. The QA
  contract now requires the owning feature cases to rerun with the real service enabled before
  claiming those flows work end to end.

### Code And QA Repairs Completed

| Gap From Audit Verdict | Repair |
| --- | --- |
| Feature-to-QA traceability incomplete | Expanded `45_Runtime_Feature_QA_Map.md` with direct QA owners and case links, including previously orphaned citation, streaming, branding, no-response, scheduling, MCP, Red Team, web-search, and config-alignment areas |
| Legacy QA folder shape | Added standard `README.md`/`cases.md`/`reports/` homes for feature QA folders and updated `qa/_migration.md` to track only legacy flat-report cleanup |
| Release tests not tied to QA cases | Added `qa/release-test-owners.yaml` and enforced central cases-based ownership in `test_qa_operating_contract.py` |
| Stale agent instruction paths | Updated always-loaded agent docs and added release checks that backticked QA/requirement paths resolve |
| Weak enforcement for required QA files | `test_qa_operating_contract.py` now checks required QA files are present, not ignored, and that raw timestamped results remain ignored |
| Prompt/source drift affecting background agents | Source YAML now resolves registry-owned prompts, activation subject rules, activation fallbacks, and launch-ready background model/tool contracts |

## Public-Safety Review

- This report uses repo-relative paths and synthetic/public-safe summaries only.
- Raw local logs, DB rows, account state, process command lines, screenshots, and tokens were not
  copied into the repo.
- Raw timestamped QA outputs remain ignored under `qa/results/*`; the public `qa/results/README.md`
  remains unignored as the contract document.
- Changed public text candidates in the root repo and nested LibreChat repo passed the local
  public-safety scan for personal paths, non-example emails, common token formats, and private key
  blocks.

## Residual Risk

- This run proves the QA system and core local browser surfaces, not every feature-specific user flow.
- This run is valid for the current local checkout. Before public PR/merge, nested LibreChat
  source-of-truth changes must be committed in the nested repo, the parent component pin must be
  bumped to that commit, and the release suite must be rerun from the pinned state.
- Feature owners must still run their own real user-grade cases before claiming Telegram media,
  RAG, MS365, web search, remote access, voice call audio, or GlassHive workstation flows are fully
  release-ready.
