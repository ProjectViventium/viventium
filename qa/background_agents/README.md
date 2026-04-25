# Background Agents QA

## Scope

Verify Anthropic background-cortex execution stays compatible with provider thinking defaults while
the shipped built-in bundle remains truthful for fresh installs and local restarts.

Additional current QA artifacts:

- `qa/background_agents/report.md` — historical April 5, 2026 Anthropic execution compatibility report
- `qa/background_agents/activation_reliability_2026-04-12.md` — corrected live activation-provider benchmark using the Anthropic connected-account path, Mongo-backed runtime bootstrapping, and per-scenario cooldown reset
- `qa/background_agents/telegram_scheduler_fallback_2026-04-24.md` — scheduled Telegram degraded-delivery regression for deferred fallback provenance
- `qa/background_agents/scheduled_live_fact_truthfulness_2026-04-25.md` — scheduled live-fact truthfulness regression for weather/news/markets/web facts without verified tool evidence

## Requirements Under Test

- Background cortices must not send `temperature` when Anthropic thinking is active.
- The guard must cover thinking that appears only after runtime initialization, not just explicit
  source-of-truth fields.
- Built-in Anthropic cortices that intentionally use `temperature` must set `thinking: false`
  explicitly in the source-of-truth bundle.
- Deep Research must ship with `web_search` in its built-in tool surface whenever runtime web
  search is enabled.
- Deep Research on `openAI / gpt-5.4` must ship `model_parameters.reasoning_effort: xhigh` and must
  not drift onto Anthropic/Google-only `thinkingBudget`.
- When Anthropic is the execution family, only `Red Team`, `Deep Research`, and `Strategic
  Planning` may use `claude-opus-4-7`; other background agents must stay on
  `claude-sonnet-4-6`.
- Built-in background-agent provider rewrites must replace provider-specific `model_parameters`
  with the canonical bag for the final provider family instead of blindly merging stale keys.
- Local LibreChat startup must continue sourcing built-in agent truth from
  `viventium/source_of_truth/local.viventium-agents.yaml` via the built-in seed path.

## Environments

- Local public repo checkout on macOS shell tooling
- Nested `viventium_v0_4/LibreChat` workspace test environment
- Public-safe synthetic inputs only

## Test Cases

1. Anthropic endpoint tests verify Sonnet 4.6 and Opus 4.7 remove `temperature` when default
   thinking becomes active.
2. Memory-agent tests verify Anthropic adaptive thinking also strips `temperature`, while disabled
   thinking does not.
3. Background-cortex service tests verify both:
   - explicit pre-initialize thinking + temperature
   - post-initialize hydrated thinking + temperature
   - post-initialize hydrated thinking for a generic user-created Anthropic cortex, not just the
     shipped built-ins
4. Source-of-truth YAML audit verifies there are zero shipped Anthropic background agents with
   `temperature` but no explicit `thinking`/`thinkingBudget`.
5. Deep Research source/runtime audit verifies:
   - its source-of-truth tool list contains `web_search`
   - runtime normalization keeps `web_search` when `VIVENTIUM_WEB_SEARCH_ENABLED=true`
   - seed-style upgrades do not preserve stale existing tools when the incoming built-in bundle
     restores `web_search`
   - its OpenAI execution parameters use `reasoning_effort: xhigh`, not `thinkingBudget`
6. Provider-matrix audit verifies:
   - the documented OpenAI-only, Anthropic-only, and mixed execution matrix matches compiler
     assignments
   - Anthropic Opus is limited to `Red Team`, `Deep Research`, and `Strategic Planning`
   - runtime normalization and seed/upsert repair stale cross-provider model-parameter drift
7. Start-script inspection verifies local startup still re-seeds built-ins from the source-of-truth
   agents bundle through `viventium-seed-agents.js`.

## Expected Results

- Targeted Jest suites pass for Anthropic endpoint, memory, and background-cortex execution.
- The source-of-truth audit reports zero remaining Anthropic built-ins with ambiguous
  `temperature`-plus-default-thinking behavior.
- The Deep Research audit proves fresh installs and upgrade/restart reseeds restore both:
  - `web_search` when runtime web search is enabled
  - `reasoning_effort: xhigh` on the shipped OpenAI execution bag
- The provider-matrix audit proves Anthropic-only installs keep Opus limited to `Red Team`,
  `Deep Research`, and `Strategic Planning`, while other Anthropic background agents stay on
  Sonnet.
- Start-path inspection confirms fresh installs and restarts consume the corrected bundle instead of
  relying on live Mongo edits.
- Live QA separates activation success from downstream user-scoped auth:
  - one connected-account user must complete a real Google Workspace or Microsoft 365 task
  - any duplicate/local QA user used for realism must have those service connections reseeded or
    reconnected explicitly before it is treated as parity coverage
- Scheduled Telegram runs must not deliver the generic deferred failure sentence when a `scheduleId`
  is available. They must either suppress the empty fallback or record visible fallback insight text
  as `fallback_delivered` in `last_delivery_outcome`.
- Scheduled live-fact sections such as weather/news/markets/web facts must only be included when a
  verified tool/cortex result exists; productivity cortices must omit out-of-scope live facts instead
  of guessing.
