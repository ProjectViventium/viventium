# Config Alignment QA Cases

## Case ID Convention

Use stable `CFGALIGN-NNN` IDs for config alignment cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `CFGALIGN-001` | Source YAML, generated runtime YAML, live sync review, and model picker inventory agree before release claims. | User-visible behavior matches source, docs, persisted state, and logs | source YAML, generated YAML, sync compare, model picker | `tests/release/test_config_compiler.py` plus user-grade QA when visible | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `CFGALIGN-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `CFGALIGN-003` | Generated web-search config matches configured provider health and user-visible capability | Source YAML, generated YAML, local env, status output, Agent Builder | config compiler tests plus live config/status inspection | FAIL (escaped 2026-05-18; rerun pending) |
| `CFGALIGN-004` | GPT-5.6 model inventory and Agent Builder defaults match provider/API requirements. | The user can select, save, reload, and run a GPT-5.6 agent without hidden endpoint incompatibility. | Launcher env, model API, Agent Builder, chat, persisted agent state, backend logs | `tests/release/test_openai_model_inventory.py`, focused LibreChat package/client tests, and real-browser QA | PASS (2026-07-09; [report](reports/2026-07-09-gpt-5-6-agent-builder.md)) |

## `CFGALIGN-001` - Core User Flow

- Requirement: Source YAML, generated runtime YAML, live sync review, and model picker inventory agree before release claims.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_config_compiler.py` plus any narrower feature tests discovered during implementation.
- Last run: NOT YET RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `CFGALIGN-002` - Public-Safe Evidence Record

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
- Last run: NOT YET RUN (cataloged 2026-05-17; run on each new public report).

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Config Alignment. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `CFGALIGN-UC-001` | On source YAML, generated YAML, sync compare, model picker, verify that source YAML, generated runtime YAML, live sync review, and model picker inventory agree before release claims. | owning requirement for `CFGALIGN-001` / `CFGALIGN-001` | source YAML, generated YAML, sync compare, model picker | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to CFGALIGN-001. | User-visible behavior matches source, docs, persisted state, and logs | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `CFGALIGN-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `CFGALIGN-002` / `CFGALIGN-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to CFGALIGN-002. | The user sees an honest setup, retry, or degraded-state result for CFGALIGN-002; no fake success is accepted. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `CFGALIGN-UC-003` | Inspect generated web-search config after the UI shows Web Search enabled and providers are unavailable. | `docs/requirements_and_learnings/37_LibreChat_v083_Config_Alignment.md` / `CFGALIGN-003` | Source YAML, generated runtime YAML/env, status output, Agent Builder browser UI | Config compiler output, generated `webSearch` block, local provider URLs, status health, logs, persisted search tool-call state | Generated config explains why search is enabled, degraded, or disabled; visible capability and runtime readiness do not drift silently. | FAIL (escaped 2026-05-18; rerun pending) |
| `CFGALIGN-UC-004` | Build a synthetic agent with an auth-surface-compatible OpenAI GPT-5.6 model, save it, refresh Agent Builder, and send a deterministic prompt. | `docs/requirements_and_learnings/37_LibreChat_v083_Config_Alignment.md` / `CFGALIGN-004` | Local Viventium QA account in Agent Builder and web chat | Generated `OPENAI_MODELS`, `/api/models`, saved agent model/parameter state, response model/log class, visible answer | Direct API inventory exposes all four official IDs; the connected-account inventory exposes the verified Sol/Terra subset; the saved QA agent keeps `gpt-5.6-sol` and Responses enabled after refresh; the response completes without model/endpoint/tool compatibility errors. | PASS (2026-07-09; [report](reports/2026-07-09-gpt-5-6-agent-builder.md)) |

## `CFGALIGN-004` - GPT-5.6 Agent Builder And Runtime

- Requirement: `docs/requirements_and_learnings/37_LibreChat_v083_Config_Alignment.md`.
- Risk covered: a new OpenAI model is documented but remains absent from generated model lists, or
  Agent Builder saves a Chat Completions configuration that is incompatible with GPT-5.6 tools.
- Preconditions: the local runtime is built/restarted from the changed checkout; the Viventium QA
  account has a working OpenAI connected account or API-key route.
- Steps:
  1. Verify direct API inventory carries all four official GPT-5.6 IDs and the generated
     connected-account inventory carries only the verified Sol/Terra subset.
  2. In a real browser using the Viventium QA connected account, create a synthetic agent and select
     OpenAI `gpt-5.6-sol`.
  3. Open Model Parameters and verify Responses API defaults on; save the agent.
  4. Refresh/reopen Agent Builder and verify model plus parameter persistence.
  5. Start a chat with the saved agent and request exactly `GPT56_AGENT_QA_OK`.
  6. Verify the visible answer, persisted agent/message state, and backend logs agree; remove the
     synthetic agent after evidence is recorded.
- Expected result: auth-surface-specific model discovery, visible form state, saved state, runtime
  route, response, and logs all agree and no invented `gpt-5.6-pro` entry appears.
- Forbidden result: source-only support; a picker row that fails on save/run; hidden Chat Completions
  tool incompatibility; mocked/API-only evidence used instead of browser QA; private account data in
  the public report.
- Evidence to capture: sanitized model counts/IDs, browser observations, persistence result, focused
  test results, response success marker, backend error-class summary, and shipped/runtime artifact
  confirmation.
- Last run: PASS (2026-07-09; [report](reports/2026-07-09-gpt-5-6-agent-builder.md)).

## `CFGALIGN-003` - Generated Web-Search Config Must Match Runtime Readiness

- Requirement: `docs/requirements_and_learnings/37_LibreChat_v083_Config_Alignment.md` and
  `docs/requirements_and_learnings/10_Open_Source_Web_Search.md`.
- Risk covered: source/generated config enables Web Search while provider health is degraded after a
  user asks Viventium to look something up, but QA does not compare that generated state with the
  visible Agent Builder capability and final answer.
- Preconditions: generated local runtime config exists; local or hosted search providers are either
  healthy or intentionally unavailable for the degraded-path run.
- Steps:
  1. Inspect source-of-truth web-search settings and generated LibreChat config/env.
  2. Inspect local status/preflight for SearXNG/Firecrawl or hosted providers.
  3. Compare Agent Builder's Web Search capability state and the final answer from a synthetic
     current-data prompt.
  4. Record whether the generated config accurately maps to healthy, degraded, or disabled runtime
     behavior.
- Expected result: source, generated config, provider health, visible capability, persisted
  `web_search` state, and final wording agree.
- Forbidden result: generated config enables a tool path that appears usable to the user while
  provider health is action-required and the final answer gives only generic degraded wording.
- Evidence to capture: source/generated config diff, status output, sanitized browser observation,
  provider health, API log failure/source summary, persisted tool-call counts.
- Automation: `tests/release/test_config_compiler.py`, `tests/release/test_local_web_search_compose.py`,
  and user-grade browser QA.
- Last run: FAIL (escaped 2026-05-18; rerun pending).
