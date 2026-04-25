# Scheduled Live-Fact Truthfulness QA - 2026-04-25

## Scope

Public-safe QA record for a scheduled Telegram morning-briefing incident where a model-generated
background insight included an unverified live weather placeholder and Telegram delivered it as a
normal scheduled message.

## Sanitized Incident Shape

- Surface: scheduled Telegram delivery.
- Schedule type: daily morning briefing.
- Requested content: live weather plus calendar/inbox/open-loop summary.
- Observed behavior: the delivered message included a weather sentence that admitted live weather was
  not cleanly available and then guessed practical advice.
- Scheduler ledger: run was recorded as ordinary `sent/delivered`, because the text was normal model
  output rather than transport/runtime fallback.

## Root Cause Classification

- Output ownership: `model-generated`.
- Telegram transport: not the root cause.
- Scheduler fallback suppression: not the root cause.
- Owning failure: background-cortex truthfulness. A provider-owned productivity cortex correctly
  activated for calendar/inbox work, but its insight included non-provider live weather content
  without a verified weather/web result. The final scheduled response then merged that insight.

## Fix Contract

- Scheduler self-prompts now state that live external facts such as weather, news, markets, and web
  facts require verified tool/cortex evidence.
- The scheduler live-fact contract is appended idempotently for default prompts, env-overridden
  prefixes, and pre-baked scheduled self-prompts that already contain brewing markers.
- If verified live evidence is unavailable, scheduled answers should omit that requested section
  instead of guessing or apologizing about missing data.
- Main-agent source-of-truth instructions now explicitly cover weather/news/markets/web facts.
- Every shipped background cortex now carries an omit-instead-of-guess guard for
  weather/news/markets/web facts.
- Google Workspace and MS365 cortices additionally scope synthesis to verified provider-owned
  results and omit out-of-scope live facts from their insights.

## Tests Executed

- `cd viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex && uv run --with pytest pytest tests -q`
  - Result: `68 passed`.
- `uv run --with pytest --with pyyaml pytest tests/release/test_background_agent_governance_contract.py -q`
  - Result: `10 passed`.
- `python3` YAML parse for `viventium/source_of_truth/local.viventium-agents.yaml`
  - Result: source-of-truth YAML parsed successfully.
- Scheduler prompt-composition verification with `uv run python`
  - Result: default prompt, existing self-prompt, and env-override paths all contained the live-fact
    contract.
- Agent sync dry-run:
  - Mode: `--prompts-only --activation-fields=enabled`.
  - Result: only prompt documents were selected; runtime repair and tool/model changes were skipped.
- Agent sync live push:
  - Mode: `--prompts-only --activation-fields=enabled --compare-reviewed`.
  - Result: all shipped prompt documents updated in live Mongo; tool/model fields were not synced.
- Post-sync live pull and Mongo spot-check:
  - Result: main, Google, and MS365 persisted instructions contained the live-fact guard; pulled live
    bundle verified all background agents contained the guard.
- ClaudeViv review:
  - Result: RCA and no-runtime-filter approach confirmed.
  - Follow-up fixes applied from review: scheduler guard now survives env overrides and pre-baked
    self-prompts; all shipped background cortices now include a live-fact truthfulness guard.

## Installed Runtime Validation

- Nested component commit pushed: `25134b3f` (`Enforce scheduled live-fact truthfulness`).
- Parent commit pushed: `061b4c4` (`Enforce scheduled live-fact truthfulness`).
- Installed runtime refreshed from pushed `main` and restarted through `bin/viventium upgrade --restart`.
- Installed parent checkout verified at `061b4c4`; installed LibreChat component verified at `25134b3f`.
- Installed scheduler source verified to contain the live-fact contract.
- Live service status after restart: LibreChat API, frontend, Modern Playground, Telegram bridge, web search, Google Workspace MCP, and MS365 MCP reported running/configured.
- Post-upgrade continuity audit status: warning only; warning was limited to Mongo continuity introspection being skipped because `MONGO_URI` was unavailable to the audit process; audit errors were empty.
- Live Mongo verification after restart: main agent and every shipped background cortex had the weather/news/markets/web omit-instead-of-guess guard in persisted instructions.
- Synthetic scheduled generation through the installed scheduler/LibreChat route used public-safe QA prompts and did not produce the prior live-weather placeholder. One broader briefing prompt returned `{NTA}` instead of a guessed weather line; one weather-only prompt returned no placeholder text.

## Public-Safe Boundary

This QA record intentionally excludes local usernames, chat IDs, schedule IDs, message IDs, private
calendar/email content, real prompt names, screenshots, local paths, tokens, and raw logs.
