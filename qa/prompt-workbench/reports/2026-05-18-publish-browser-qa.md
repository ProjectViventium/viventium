# Prompt Workbench Publish Browser QA - 2026-05-18

## Summary

- Result: PASS for publish smoke scope; live push and live model eval intentionally not run.
- Build/source under test: local working tree production Prompt Workbench bundle.
- Runtime/artifact under test: built static workbench served by the local FastAPI app.
- Environment: local development loopback server with Docker available.
- Tester: Codex with Playwright CLI.
- Related change: publish readiness review for Prompt Workbench, QA catalog cleanup, and nested repo release.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `PW-001` | pass | Prompt detail for `main.conscious_agent` rendered in browser; release test already passed. | Verified registry-backed prompt detail, frontmatter, includes, variables, and rendered preview. |
| `PW-002` | pass | Live Drift Board showed explicit `Needs merge` state and reviewed push remained blocked. | No live push was attempted. |
| `PW-005` | pass | No-live eval preview recorded sanitized local run `20260518T063247Z`. | Preview displayed `no model call, no score`. |
| `PW-009` | pass | Flow view displayed source, rendered prompt, live agent, eval bank, eval results, and include nodes. | Browser network requests were all 200. |
| `PW-010` | pass | Evals panel displayed families, linked prompt, controls, empty linked-case table, and run history. | Selected prompt `surface.web` has zero linked cases; the preview path stayed honest. |
| `PW-014` | pass | Search for `web` narrowed the Prompt Atlas to web-related surface prompts. | Labels stayed human-readable and hash noise was absent. |
| `PW-015` | pass for served artifact | `/api/health` returned ok and `/api/build-version` returned a public-safe bundle hash. | Helper menu itself was covered by prior local helper QA, not rerun here. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `PW-UC-001` | Open the workbench, search the atlas, select a prompt, and inspect Flow, Prompt, Live Drift, Drafts, Evals, and Prompt Traces. | Real browser against `http://127.0.0.1:8781` | PASS | Prompt Atlas loaded 63 prompts; search for `web` showed web prompts; `surface.web` Prompt and Evals panels opened. | Browser network showed `/api/prompts`, `/api/sync/status`, `/api/drafts`, `/api/evals/runs`, prompt detail, and workbench-context calls returning 200. | Prompt Traces tab was not opened in this smoke pass; covered by prior report and remains a narrower follow-up for trace changes. |
| `PW-UC-002` | Use no-live eval controls and blocked sync controls before any reviewed live push. | Real browser Evals and Live Drift panels | PASS | Live Drift showed `Needs merge`; reviewed push was disabled; Evals said preview is no model call/no score. | `POST /api/evals/run` returned 200 and visible run history showed sanitized preview run `20260518T063247Z`. | Live exact-model eval and reviewed live push intentionally not run for public publish smoke. |
| `PW-UC-003` | Reopen the workbench after an eval preview and confirm state persists. | Browser reopen plus backend APIs | PASS | Reopened browser, selected `surface.web`, and Evals still showed one run for the prompt. | `/api/health` returned ok; `/api/build-version` returned hash `f7c75415ca6cf86f`; static index response used `no-store`; assets were hashed. | None for publish smoke scope. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: Prompt Workbench.
- Requirement: `docs/requirements_and_learnings/49_Prompt_Architecture_and_Token_Efficiency.md`, `qa/prompt-workbench/cases.md`.
- Use case: `PW-UC-001`, `PW-UC-002`, `PW-UC-003`.
- QA case: `PW-001`, `PW-002`, `PW-005`, `PW-009`, `PW-010`, `PW-014`, `PW-015`.
- Expected result: workbench opens through a real browser, surfaces source/live/eval state truthfully, records only public-safe summaries, and keeps live push guarded.
- Actual evidence: browser snapshots showed Prompt Atlas, Flow, Prompt detail, Live Drift, Evals, no-live preview result, and persistence after reopen; browser console had 0 errors/warnings; network API calls returned 200.
- Remaining gap or fix: live exact-model eval, live prompt push, and helper menu were not rerun in this publish smoke; existing QA cases keep those as separate guarded runs.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | `PW-UC-001` through `PW-UC-003` against Prompt Workbench cases and prompt architecture requirement. |
| Code owning path | Which code path owns the behavior? | `viventium_v0_4/prompt-workbench/` frontend/backend plus `scripts/viventium/prompt_workbench.py` lifecycle. |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | Prompt architecture requirement doc, Prompt Workbench README, QA cases, and release tests. |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Release tests, `npm run build`, Playwright CLI, curl health/build-version checks. |
| Local/external prerequisite state | Which required local service, provider, Docker-backed sidecar, OAuth grant, API key, model, or hosted dependency was proven healthy or degraded? | Docker was available; no external OAuth/API/model dependency was used; local loopback server was healthy. |
| Logs | Which sanitized logs confirm or contradict the result? | Browser console reported 0 errors and 0 warnings; browser request log showed all API calls in this pass returned 200. |
| DB/state/persistence | Which sanitized state, DB count/hash, persisted message, config, or artifact confirms it? | Private workbench eval run persisted as sanitized run id `20260518T063247Z` with public-safe hash suffix `daab7c007b2f27d1`; no private path recorded here. |
| Generated/shipped artifact | Which generated config, compiled bundle, prebuilt helper, or installed artifact was inspected when applicable? | Build-version API reported public-safe index hash `f7c75415ca6cf86f`; index used `no-store`; assets were hashed. |
| Real user path | Which browser/computer, Telegram, voice, installer, CLI, MCP/tool, scheduler, or GlassHive path was used like a user? | Real browser opened the workbench, searched, selected prompt, switched panels, ran no-live preview, closed, reopened, and verified persisted result. |
| Visual/UX comparison | Does the visible UI/UX or delivered result match the expected behavior and supporting evidence? | Yes for smoke scope: visible panels matched backend status and run history; blocked live push state was explicit. |
| Not run / blocked | Which required surface was not run, and why is the result partial or blocked? | Live push, live exact-model eval, helper menu, and full trace-tab regression were not run because this was a publish smoke pass and live/external actions are guarded separately. |

## User-Grade Evidence

- Surface exercised: Prompt Workbench browser UI.
- Real user path: open, search prompt atlas, select `surface.web`, inspect Prompt detail, Live Drift, Evals, run no-live preview, reopen, and verify persisted run history.
- Visible outcome: atlas search worked; selected prompt loaded; Live Drift showed `Needs merge`; Evals showed zero linked cases and one sanitized preview run after execution.
- Expanded/detail state: prompt metadata, source status, draft count, eval count, run result, and drift status were visible.
- Persistence/reload result: after browser close/reopen, Evals still showed one run for `surface.web`.
- Local/external prerequisite state: Docker available; local workbench server healthy; no external credentials or live model calls required.
- Evidence retrieval classification, if applicable: not applicable; no web or external factual retrieval was used.
- Fallback path, if applicable: not applicable.
- Backend/log/DB confirmation: request log showed relevant API calls returned 200; private eval state summarized by sanitized run id and hash only.
- Final model/runtime wording check: no model response was produced; UI wording correctly said preview has no model call and no score.
- Substitution check: automated tests and API calls supported the browser evidence; they did not replace the browser UI path.

## Automated Evidence

```bash
docker info --format '{{.ServerVersion}}'
uv run --with pytest --with pyyaml python -m pytest tests/release -q
cd viventium_v0_4/prompt-workbench && npm run build
curl -sS http://127.0.0.1:8781/api/health
curl -sS http://127.0.0.1:8781/api/build-version
bash "$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh" open http://127.0.0.1:8781
bash "$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh" snapshot
bash "$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh" fill search-box-ref web
bash "$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh" click surface-web-ref
bash "$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh" click live-drift-ref
bash "$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh" click evals-ref
bash "$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh" click run-preview-ref
bash "$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh" console warning
bash "$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh" requests
```

## Findings

- Defects: corrected placeholder natural-use rows in `qa/prompt-workbench/cases.md` before publication.
- Regressions: none observed in publish smoke scope.
- Flakes: none observed.
- Environment issues: none for this pass.
- Residual risks: live exact-model eval, reviewed live push, and helper menu are intentionally separate guarded QA surfaces and were not rerun in this smoke pass.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
