# GlassHive Core Provider QA

## Scope

- Owning requirements: GlassHive Core Provider Rule, background-provider routing, GlassHive core
  provider surface, installer/LIFE compiler contract, and Feelings exactly-once contract.
- Primary outcome: any eligible main or cortex Agent can select GlassHive through the normal
  Provider/Model layer and receive one reliable harness-authored result in the selected folder.
- User-visible surfaces: Agent Builder, web chat, Telegram, harness activity, and provider errors.
- Explicit control surface: LiveKit real-time calls continue to use Voice LLM.

## Quality Bar

- Score Quality (intelligence, relevance, usefulness, alignment) and Performance together.
- Run every applicable case like a user on the real installed runtime; source, mocks, unit tests,
  logs, and DB rows are supporting evidence only.
- Correlate visible results with LibreChat SSE/Mongo, generated config, GlassHive session/request/run
  state, private App Support state, component pins, built artifacts, and running processes.
- Use only synthetic public-safe prompts/files in committed evidence.

## Required Suites

| Suite | Command or manual path | Required when |
| --- | --- | --- |
| GlassHive provider/runtime | `pytest runtime_phase1/tests/test_conversation_provider.py runtime_phase1/tests/test_profile_runtime.py` | Every provider/runtime change |
| LibreChat Agent/provider | Focused backend, package, schema, and client tests | Every Agent/UI/routing change |
| Compiler/LIFE | `pytest tests/release/test_config_compiler.py tests/release/test_life_bootstrap.py` | Every install/config change |
| Portable endpoint | Standard OpenAI SDK plus negative auth/parameter/idempotency probes | Every provider contract/security change |
| Real web | Playwright CLI through installed Agent Builder and chat | Every user-visible change |
| Real desktop/cross-surface | Computer Use through web, Telegram, and LiveKit | Before acceptance |
| Clean install | Supported public install entrypoint in a fresh directory | Before release-ready claim |

## Current Status

- Case catalog: [`cases.md`](cases.md).
- Reports: [`reports/`](reports/) for dated public-safe runs.
- Latest recovery result: configured fallback and cross-process reconciliation passed the recorded
  2026-08-06 Telegram/runtime run; the full original cross-surface release acceptance remains
  partial. See
  [`reports/2026-08-06-telegram-reconciliation-fallback-recovery.md`](reports/2026-08-06-telegram-reconciliation-fallback-recovery.md).
