<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-31 Express Rich Brain Readiness Implementation QA

## Result

Status: PARTIAL.

The implementation adds the shared readiness registry, Express/Advanced wizard changes, install/status
readiness rows, public example cleanup, and QA case coverage for the full cognitive-system spine.
Automated coverage passed. Full release signoff is still partial because a destructive clean-machine
public entrypoint install and browser first-admin Brain Setup run were not performed in this local
development pass.

## Requirement Trace

- Source of truth: `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
- QA owner: `qa/installer-resilience/cases.md` `INST-004`
- Feature owner links: scheduling, prompt-workbench, memory-hardening, meeting-transcript-memory,
  conversation-recall-rag

## Implementation Evidence

- Added `scripts/viventium/brain_readiness.py` as the shared registry for the installer/readiness
  inventory.
- Express wizard now keeps the core spine on by default and guides Web Search, Conversation
  Recall/RAG, transcript source, Telegram, and non-Apple-Silicon hosted voice instead of silently
  claiming readiness.
- Advanced wizard uses the same feature guidance and now includes transcript ingest as a first-class
  guided setup item.
- Install/status summary now shows:
  - Scheduler health plus sanitized ledger counts/status/outcome/next-run.
  - Transcript ingest setup state.
  - Memory hardening schedule, scope, and dry-run-first state.
  - Viventium Brain Setup rows for primary AI, fallback AI, transcript ingest, Recall/RAG, web
    search, voice, Telegram, Telegram Codex, Google, MS365, WhatsApp, Code Interpreter, Skyvern,
    OpenClaw, and Remote Access.
- `config.full.example.yaml` now keeps Skyvern and OpenClaw off by default.
- A tracked handoff document was sanitized to remove private local absolute paths.

## Checks Run

- `uv run --with pytest --with PyYAML --with jsonschema --with pydantic --with fastapi --with croniter python -m pytest tests/release/test_brain_readiness.py tests/release/test_wizard.py tests/release/test_install_summary.py tests/release/test_config_compiler.py tests/release/test_preflight.py tests/release/test_default_nightly_routines.py tests/release/test_prompt_workbench.py -q`
  - Result: 320 passed, 17 skipped.
- `bin/viventium status`
  - Result: core web surfaces reachable; new Brain Setup table rendered.
  - Scheduler row correctly reported `Running with issues` from a sanitized existing ledger state
    with latest status `error` and delivery outcome `failed`.
- `git diff --check` scoped to touched implementation/docs/QA files.
  - Result: PASS.
- Public-safety scan scoped to touched implementation/docs/QA/example files for local home paths,
  personal account strings, and private workspace paths.
  - Result: PASS.

## ClaudeViv Review

- First max-effort Opus review attempt failed with a Claude API `thinking` block error before a
  usable JSON review was produced.
- Fallback review-only Sonnet pass completed.
- ClaudeViv agreed the implementation is an acceptable `PARTIAL`: structurally aligned, not a fake
  pass, and blocked only by user-grade release gates.
- ClaudeViv findings:
  - Medium: verify the worker-auth preflight regression exists for GlassHive enabled with no Codex
    or Claude login.
  - Low: the registry is a real structural improvement but status health checks are not yet fully
    registry-dispatched.
- Follow-up check: `tests/release/test_preflight.py` already contains
  `test_preflight_blocks_glasshive_when_no_worker_cli_is_logged_in`, which asserts the missing
  worker-login item and one clear manual action.

## Remaining Release Gates

- Run a clean public entrypoint Express install in a new directory or separate Mac.
- Run browser first-admin Brain Setup with Playwright:
  connect later, connect provider, enable Recall/RAG, add transcript folder, open Workbench.
- Prove the full visible nightly chain on the clean install:
  scheduled prompt -> filled placeholders -> GlassHive run -> callback -> scheduler ledger ->
  Workbench shows completed.
- Run feature-owner user-grade checks for Telegram, Google Workspace MCP, MS365 MCP, and voice only
  with synthetic or sanitized evidence.

## Public-Safety Notes

This report intentionally omits raw prompts, transcript text, account emails, local absolute paths,
tokens, callback payloads, screenshots, and raw DB rows.
