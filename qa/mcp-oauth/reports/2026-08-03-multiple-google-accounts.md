# Multiple Google Accounts QA Run - 2026-08-03

## Summary

- Result: `PASS` for the supported two-account user path; `PARTIAL` for the complete degraded-path catalog because destructive live revocation and provider rate limiting were not performed on owner-authorized grants.
- Build/source under test: current sanitized release candidate and its pinned LibreChat and Google Workspace MCP components.
- Runtime/artifact under test: installed native local runtime, generated LibreChat config, production client build, and rebuilt Google Workspace MCP extension bundle.
- Environment: local native Viventium with synthetic public-safe prompts and two owner-authorized Google OAuth grants.
- Tester: Codex using real browser and desktop user surfaces plus automated suites.
- Related change: independent provider slots for multiple Google Workspace accounts, shared provider callback validation, local-time Gmail boundaries, and credential-safe connector logging.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `MCPOAUTH-007` | `PARTIAL` | Two live grants, two restarts, three user surfaces, generated config, sanitized token-record counts, and focused automation | Supported path passed; destructive live revoke and imposed provider rate limit were not run. |
| `MCPOAUTH-UC-006` | `PASS` | Agent Builder, direct web agent, GlassHive Main, and Telegram Desktop | Every all-account turn issued one fresh provider query per connected slot and one combined answer. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `MCPOAUTH-UC-006` | Connect two Google accounts, restart, and ask Viventium to check every Gmail inbox. | Agent Builder, web chat, GlassHive activity, Telegram Desktop | `PASS` | Both account cards remained connected; each chat surface returned one concise combined result. | Six distinct credential records, two fresh provider calls per all-account turn, two generated slot identities, and zero credential-bearing connector log URLs after hardening. | None for the supported two-account path. |
| `MCPOAUTH-007-DEGRADED` | Continue truthfully when one slot is denied, revoked, empty, unavailable, or rate-limited. | Automated callback, credential, broker, and compiler paths | `PARTIAL` | Typed error and partial-result contracts passed in automation. | Focused route/broker tests cover denial, duplicate callback, callback mismatch, missing or unreadable credentials, and provider unavailability. | Live destructive grant revocation and forced provider rate limiting were intentionally not run. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: multiple independently connected Google Workspace accounts per Viventium user.
- Requirement: [`docs/requirements_and_learnings/07_MCPs.md`](../../../docs/requirements_and_learnings/07_MCPs.md), multiple-account Google Workspace section.
- Use case: connect two Google accounts and retrieve current Gmail evidence across both after refresh and restart.
- QA case: `MCPOAUTH-007` and `MCPOAUTH-UC-006` in [`qa/mcp-oauth/cases.md`](../cases.md).
- Expected result: independent slot identity and persistence, one current provider call per relevant slot, truthful combined output, no credential leakage, and no prompt- or user-specific routing.
- Actual evidence: the supported real user path passed in Agent Builder, direct web chat, GlassHive Main, and Telegram Desktop; generated config, logs, and private persistence counts agreed.
- Remaining gap or fix: retain `PARTIAL` on the full case until a disposable account fixture can safely exercise live revoke and rate-limit recovery.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | `07_MCPs.md`, `MCPOAUTH-007`, and `MCPOAUTH-UC-006`. |
| Code owning path | Which code path owns the behavior? | Config compiler slot generation, LibreChat MCP schema and callback route, Agent Builder labels, native agent bundle projection, and Google connector logging setup. |
| Docs and nested docs/repos | Which docs define expected behavior? | MCP requirement, LibreChat prompt source, and this living MCP OAuth case catalog. |
| Scripts or harnesses | Which suites exercised it? | Parent release tests, LibreChat route/schema/broker suites, frontend CI/build, and Google connector tests. |
| Local/external prerequisite state | Which required dependency was proven healthy or degraded? | LibreChat API/web, GlassHive, Telegram bridge, and Google Workspace MCP were running; both OAuth slots were connected. |
| Logs | Which sanitized logs confirm the result? | Fresh runs contained one query per slot; post-hardening connector logs contained zero credential-bearing tokeninfo URLs or bearer-token prefixes. |
| DB/state/persistence | Which sanitized state confirms it? | Exactly three credential records per slot remained after two full restarts; no identifiers or token values are published. |
| Generated/shipped artifact | Which generated or prebuilt output was inspected? | Generated LibreChat YAML contained both titles and shared callback metadata; the rebuilt connector extension bundle passed its full tests. |
| Real user path | Which surface was used like a user? | Agent Builder in a real browser, direct web chat, GlassHive Main chat, and Telegram Desktop. |
| Visual/UX comparison | Does delivered output match the expectation? | Yes. Both cards showed connected state and each conversation produced one concise combined response without exposing account plumbing. |
| Not run / blocked | Which required surface was not run? | Live revoke and forced provider rate limiting on owner-authorized grants; automated degraded paths support but do not replace those destructive runs. |

## User-Grade Evidence

- Surface exercised: Agent Builder, direct LibreChat conversation, GlassHive-backed Main, and Telegram Desktop.
- Real user path: connect two distinct Google accounts, refresh, restart twice, and request a bounded current-day unread-inbox check across every connected Gmail account.
- Visible outcome: both account cards stayed connected and each conversation returned one combined count-only response.
- Expanded/detail state: Agent Builder exposed separate account cards; the GlassHive activity detail showed brokered execution rather than a wrapper-model substitution.
- Persistence/reload result: both slots remained connected after browser refresh and two complete runtime restarts.
- Local/external prerequisite state: LibreChat, GlassHive, Telegram, and Google Workspace MCP reported running throughout the final pass.
- Evidence retrieval classification, if applicable: successful provider results from both authenticated slots; no empty-result or unavailable state occurred in the supported live path.
- Fallback path, if applicable: none; no web search, memory, cached response, or direct wrapper model substituted for either Gmail slot.
- Backend/log/DB confirmation: two fresh provider queries per all-account turn, six distinct credential rows across two slot identities, and generated config with two independent account entries.
- Final model/runtime wording check: each surface returned one concise answer and did not claim that a background worker would check later or that a disconnected account succeeded.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting evidence, not substitutes for any required visible-UI, detail-state, persistence, or wording step. The real browser and Telegram paths were run.

## Automated Evidence

```bash
uv run --with pytest --with pyyaml pytest -q tests/release/test_config_compiler.py
uv run --with pytest --with pyyaml pytest -q tests/release/test_install_summary.py
uv run --with pytest --with pyyaml --with pydantic --with croniter --with md2tgmd --with fastmcp --with fastapi python -m pytest tests/release/ -q
npm run test:api -- --runInBand server/routes/__tests__/mcp.spec.js
npm run test:api -- --runInBand server/services/Tools/mcp.spec.js server/services/viventium/__tests__/GlassHiveCapabilityBroker.spec.js
npm run test:packages:data-provider -- --runInBand src/mcp.spec.ts
npm run frontend:ci
npm run build
uv run pytest -q
```

- Config compiler: 188 passed, including a three-slot agent-tool projection regression and the canonical LIFE-instruction default.
- Install summary: 72 passed.
- Complete parent release suite: 2,246 passed and 6 skipped.
- LibreChat shared-callback route: 87 passed.
- LibreChat broker and MCP loading: 45 passed.
- LibreChat MCP schema: 4 passed.
- Google Workspace MCP source and extension bundle: 35 passed.
- Production LibreChat browser build, browser-compliance collection, and browser-only verification: passed.

## Findings

- Defects: fixed one portability defect where slots three through ten were compiled but were not projected into the default Connected Accounts agent's tool list.
- Regressions: none remaining in the supported two-account path.
- Flakes: one transient parallel parser failure disappeared when the owning LibreChat route suite ran alone; the complete isolated route suite passed.
- Environment issues: Claude Opus review was unavailable because the authenticated account had reached its weekly usage limit.
- Residual risks: destructive live revoke and forced provider-rate-limit recovery need disposable account fixtures before the complete case can move from `PARTIAL` to `PASS`.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
