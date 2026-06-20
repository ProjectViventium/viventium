<!-- qa-evidence-exempt: legacy sanitized RCA/QA note retained for historical context; current acceptance must use cases plus a fresh v2 report. -->

# 2026-06-14 GlassHive Capability Preservation And Tool Plumbing QA

## Scope

Escaped regression review for GlassHive worker capability preservation and user-visible tool
plumbing. This report covers source/runtime fixes across GlassHive host/workstation launches,
LibreChat rendering, Telegram rendering, docs, and QA case updates.

## Requirements Linked

- `docs/requirements_and_learnings/01_Key_Principles.md`
- `docs/requirements_and_learnings/07_MCPs.md`
- `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md`
- `qa/glasshive_host_workers/cases.md` `GHHOST-005`
- `qa/glasshive-mcp-capability-broker/cases.md` `GH-MCP-BROKER-019`
- `qa/telegram-detached-api-stability/cases.md` `TGAPI-006`

## RCA Summary

The disconnect happened at the launch/config boundary, not in the worker intelligence. GlassHive
projected broker MCP config by pointing host Codex at a worker-local `CODEX_HOME`, but that config
contained only the broker block. That removed native Codex MCP capability from the worker. The
workstation Codex path also defaulted to ignoring worker-local config and disabling browser/computer
feature families. Host Claude Code launched without its native Chrome integration flag. Separately,
LibreChat and Telegram treated newer GlassHive workspace/tool plumbing as ordinary visible content.

The corrected invariant is: broker projection is additive over the selected worker type's native
capability surface. Lockdown is explicit configuration, not the default.

## Automated Evidence

PASS: Python syntax compile for changed GlassHive runtime modules.

PASS: GlassHive runtime profile tests:
`cd viventium_v0_4/GlassHive/runtime_phase1 && .venv/bin/pytest tests/test_profile_runtime.py -q`

PASS: GlassHive runtime profile, bootstrap, MCP server, and API tests:
`cd viventium_v0_4/GlassHive/runtime_phase1 && .venv/bin/pytest tests/test_profile_runtime.py tests/test_bootstrap.py tests/test_mcp_server.py tests/test_api.py -q`
Result: exit code 0.

PASS: Telegram bridge and HTML tests:
`cd viventium_v0_4/telegram-viventium && TelegramVivBot/.venv/bin/pytest tests/test_librechat_bridge.py tests/test_telegram_html.py -q`
Result: 116 passed.

PASS: LibreChat client rendering tests:
`cd viventium_v0_4/LibreChat/client && npx jest src/components/Chat/Messages/Content/__tests__/contentParts.test.ts src/components/Chat/Messages/Content/__tests__/ToolCall.test.tsx --watch=false --runInBand --coverage=false`
Result: 2 suites passed, 52 tests passed.

NOTE: Running the same client test file paths from the LibreChat repo root failed before execution
because the root Jest command did not load the client TypeScript transform. The passing command above
is the client harness that owns these TS/TSX tests.

PASS: Config compiler release slice:
`viventium_v0_4/GlassHive/runtime_phase1/.venv/bin/pytest tests/release/test_config_compiler.py -q`
Result: 109 passed.

BLOCKED: full `tests/release` through the borrowed GlassHive venv. A first run without `PYTHONPATH=.`
failed collection on the parent `scripts` package. With `PYTHONPATH=.` fixed, collection blocked on
missing `croniter` for prompt-workbench tests in that venv. No product failure was observed from this
blocked run.

## Runtime Probes

PASS: Synthetic host Codex materialization probe using the installed local Codex app and a public-safe
broker grant:

- worker-local config contained `glasshive-user-capabilities`
- worker-local config contained `computer-use`
- worker-local config contained `node_repl`
- worker-local config did not contain the literal broker grant
- `codex mcp list` under the worker-local `CODEX_HOME` reported `computer-use`,
  `glasshive-user-capabilities`, and `node_repl`
- worker-local Codex config permissions were owner-only
- after the TOML renderer hardening, `codex mcp list` continued to load the worker-local config
  successfully

PASS: Synthetic host Claude command probe:

- host Claude launch command included `--chrome` by default
- host Claude preflight passed on the installed local CLI

PASS: diff whitespace checks across the touched parent, GlassHive, LibreChat, and Telegram files.

SUPPORTING DB evidence: sanitized Mongo inspection of the reported local conversation found stored
tool-call/tool-plumbing structures: 25 messages, 5 tool-call parts, 2 GlassHive tool-call parts, and
3 text messages matching raw-plumbing patterns. No private transcript text was captured here.

SUPPORTING SQLite evidence: local GlassHive run store contains historical `failed|unknown` runs.
The new `runtime_terminated` classifier covers SIGTERM/143-style terminations going forward; this
report did not mutate historical rows.

## User-Path QA

PARTIAL: isolated Playwright opened the reported local conversation URL and redirected to the login
page. This proves isolated browser QA is auth-blocked for that private conversation; it does not prove
the authenticated visible UI.

BLOCKED: the computer-use MCP failed before app listing/state capture in this session. Chrome
AppleScript DOM inspection is disabled by the local browser setting that blocks JavaScript from Apple
Events. A temporary local screenshot attempt was not retained as evidence because the active Chrome
window was not the target Viventium conversation.

NOT RUN: live post-change Telegram send/receive. The sanitizer regression tests passed, but the active
Telegram user path was not exercised after rebuild/restart in this pass.

NOT RUN: a live post-change GlassHive worker launch through the authenticated LibreChat UI. Source,
unit/API tests, config materialization, and CLI capability probes passed; final user-path acceptance
still requires a rebuilt/restarted runtime and authenticated browser/Telegram run.

## Review Evidence

PASS: independent subagent review found capability-preservation and UI/Telegram hygiene gaps before
the first final patch set. Follow-up changes addressed the reported structural gaps: host Codex now
preserves non-MCP config while filtering unallowlisted MCP blocks, user-provider OAuth/session-like
bundle env keys are filtered in local and enterprise mode, Claude Chrome support is preflighted, and
result-bearing GlassHive tool rows remain visible.

PASS: ClaudeViv structured review-only pass using `claude-opus-4-8` with max effort completed. It
confirmed the RCA and root-level alignment, found no P0, and identified two medium follow-up edges:
non-canonical Codex TOML MCP declarations and over-broad free-text GlassHive/tool transcript
sanitization. Both were fixed before this report was finalized.

PASS: follow-up regression coverage for the ClaudeViv medium findings:

- non-canonical inline/aggregate Codex MCP tables strip private MCP entries and secrets while
  preserving allowlisted native MCPs
- TOML rendering preserves Unicode strings without invalid surrogate escapes
- LibreChat and Telegram preserve non-GlassHive `run_*` / `project_*` examples while still stripping
  GlassHive raw tool plumbing

## Result

PASS for source/runtime/test alignment of the root fixes.

PARTIAL for end-to-end user acceptance because authenticated browser and live Telegram surfaces were
blocked or not rerun after the code changes. Do not call this release-ready until those live surfaces
are exercised on the active rebuilt runtime.
