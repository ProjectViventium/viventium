<!-- qa-evidence-exempt: review prompt artifact; companion run report holds the standard evidence template. -->
# ClaudeViv Review Prompt - Feature Use-Case QA Repair - 2026-05-18

You are reviewing a local Viventium repository repair. Do not edit files. Return review-only JSON.

## Objective

Validate or challenge whether the new QA-system repair addresses the user's central complaint:

QA must start from the full product feature map, enumerate natural obvious user use cases for every
affected feature, treat those use cases as a checklist, execute them like a real user through the
browser/computer/voice/Telegram/CLI/MCP/scheduler/GlassHive surface, and compare visible results with
logs, DB/state, code, scripts, docs, nested repos, generated config, and shipped artifacts. The user
specifically called out that limiting QA to one playground/search symptom is insufficient.

## Review Mode

- Review only. Do not make changes.
- Classify claims as `confirmed`, `partially_confirmed`, `cannot_confirm`, or `contradicted`.
- Be strict about gaps, but prefer simple path-of-least-resistance fixes over bureaucratic process.
- Public-safe boundary matters: no secrets, raw private logs, screenshots with private content, local
  absolute paths, account identifiers, conversation IDs, message IDs, call/session IDs, Mongo `_id`
  values, or raw provider request/response IDs should be introduced into public artifacts.

## Runtime Evidence Gathered By Codex

Sanitized evidence only:

- Local runtime status:
  - LibreChat frontend on port 3190, LibreChat API on port 3180, modern playground on port 3300, and
    Telegram bridges were running.
  - Web Search was configured for local SearXNG + local Firecrawl.
  - SearXNG and Firecrawl status were Action Required.
  - Docker CLI exists, but the Docker daemon was not running, so local Docker-backed search sidecars
    could not start in this environment.
- Real UI evidence:
  - Computer-use inspection of the user's live local Chrome/LibreChat UI showed Web Search enabled
    in Agent Builder and a visible assistant turn with generic degraded search wording after the user
    asked Viventium to look something up.
  - The same local browser context was voice-linked through modern playground.
  - Playwright CLI opened `http://localhost:3190`, reached the Viventium login page, and reported
    zero console errors. This was a surface smoke only because the Playwright context was not the
    signed-in user profile.
- Logs and DB/state:
  - API error log contained SearXNG request failures in the local runtime window.
  - Health probes to `http://localhost:8082/` and `http://localhost:3003/` failed to connect.
  - Mongo persisted the latest matching assistant turn with three `web_search` tool-call parts and
    text output. Raw IDs were not copied into public artifacts.

## Provisional RCA

1. The immediate product failure is not merely a prompt issue. The visible response happened while
   Web Search appeared enabled, persisted `web_search` tool-call parts existed, and local configured
   providers were unavailable/failing.
2. The deeper QA-system failure was that the prior repair created feature maps and QA owners but did
   not force a product-wide natural-user-use-case checklist across all features and surfaces. That
   allowed voice + web-search to escape as a cross-surface case.
3. The correct repair is not to overfit a test to one private prompt or one conversation. The QA
   system should require:
   - a product-wide feature/user-use-case checklist,
   - natural use-case sections in feature case catalogs,
   - release tests that enforce those checklist surfaces,
   - explicit escaped regression cases in both web-search and voice owners,
   - public-safe reporting that says the product path remains failing/blocked until the real
     browser/voice rerun passes.

## Alternative Explanations Already Considered

- "Web Search is disabled": contradicted by the UI state and generated config references, though
  configured local providers were unavailable.
- "A unit/config test would be enough": contradicted by the visible browser failure and the user's
  explicit requirement for real user execution.
- "A single web-search case is enough": rejected because the failed path crosses voice, web search,
  agent capability config, persistence, logs, and user-facing wording.
- "The product was fixed by the QA docs": rejected. The run report explicitly marks the product path
  as FAIL/PARTIAL until provider health and a full browser/voice rerun pass.

## Files Changed Or Added For This Repair

- `qa/README.md`
- `qa/feature-user-use-case-checklist.md`
- `qa/_templates/cases.md`
- `qa/_templates/feature-readme.md`
- `qa/_templates/run-report.md`
- `docs/requirements_and_learnings/01_Key_Principles.md`
- `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`
- `AGENTS.md`
- `CLAUDE.md`
- `viventium_v0_4/LibreChat/AGENTS.md`
- `qa/web-search/README.md`
- `qa/web-search/cases.md`
- `qa/modern-playground-voice/README.md`
- `qa/modern-playground-voice/cases.md`
- `qa/qa-system-audit/cases.md`
- `qa/qa-system-audit/reports/2026-05-18-feature-use-case-checklist-repair.md`
- all top-level `qa/*/cases.md` files were mechanically given a `Natural User Use Case Checklist`
  section when missing.
- `tests/release/test_qa_operating_contract.py`

## Verification Already Run

- `viventium_v0_4/voice-gateway/.venv/bin/python -m pytest tests/release/test_qa_operating_contract.py -q`
  - Result: `19 passed`.
- `bin/viventium status`
  - Result: core web surfaces reachable; Web Search configured but local SearXNG/Firecrawl action
    required.
- Playwright CLI:
  - `open http://localhost:3190 --headed`
  - `snapshot`
  - Result: local Viventium login page, zero console errors.

## Review Questions

1. Does this repair now make the user's required QA workflow explicit and enforceable enough?
2. Are there missing docs/tests/cases that still allow a developer or agent to hand-wave a feature
   pass without enumerating natural user use cases?
3. Are `WEB-004`, `MPV-006`, and `QASYS-009` sufficient escaped-case owners for the observed voice
   + web-search miss, or should another owner/case be added?
4. Did Codex correctly avoid claiming the product search path is fixed, given Docker/search services
   were unavailable?
5. Are there public-safety leaks in the added docs, cases, tests, or report?
6. Is any added QA structure overcomplicated relative to the user's "beautifully simple yet complete
   and powerful" requirement?
