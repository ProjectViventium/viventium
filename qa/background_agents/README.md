# Background Agents QA

- `reports/2026-07-10-qa-memory-contamination-prevention.md` — owner-targeted QA contamination RCA,
  surgical cleanup evidence, structured QA isolation, derived-index reconciliation, and real
  connected-account browser acceptance.

## Scope

Verify the shipped conscious/subconscious execution matrix, provider-native fallback behavior, and
background-cortex runtime remain truthful for fresh installs and local restarts.

Additional current QA artifacts:

- `qa/background_agents/report.md` — historical April 5, 2026 Anthropic execution compatibility report
- `qa/background_agents/activation_reliability_2026-04-12.md` — corrected live activation-provider benchmark using the Anthropic connected-account path, Mongo-backed runtime bootstrapping, and per-scenario cooldown reset
- `qa/background_agents/telegram_scheduler_fallback_2026-04-24.md` — scheduled Telegram degraded-delivery regression for deferred fallback provenance
- `qa/background_agents/scheduled_live_fact_truthfulness_2026-04-25.md` — scheduled live-fact truthfulness regression for weather/news/markets/web facts without verified tool evidence
- `qa/background_agents/phase_a_phase_b_reliability_2026-05-06.md` — Phase A direct-tool / Phase B supplemental background-agent reliability regression with terminal silent-completion coverage
- `qa/background_agents/cortex_phase_b_fallback_2026-05-06.md` — Phase B execution fallback and activation narrowing regression for support/confirmation cortices
- `qa/background_agents/phase_b_main_fallback_persistence_2026-05-09.md` — main-model fallback regression proving in-flight Phase B work is preserved and persisted against the final fallback/primary answer
- `qa/background_agents/late_stream_termination_rendering_2026-05-09.md` — web rendering/backend persistence regression for assistant messages that have visible text plus a late stream-termination error part
- `qa/background_agents/visible_cards_browser_qa_2026-05-10.md` — real browser regression proving named background-agent cards are visible, persisted after reload, and stored as successful terminal cortex insights
- `qa/background_agents/reports/2026-07-09-gpt-5-6-conscious-subconscious-routing.md` — GPT-5.6 Sol/Terra workload routing, Opus 4.8 fallback, live sync, and QA-account browser acceptance
- `qa/background_agents/reports/2026-07-09-activation-routing-model-eval.md` — full 11-cortex Prompt Workbench classifier corpus, Scout/Qwen/GPT-OSS comparison, prompt repair, runtime model controls, and QA-account acceptance
- `qa/background_agents/reports/2026-07-09-interruption-restart-browser-qa.md` — ACT-37 real browser/Mongo supported-stop-start acceptance proving active-state durability, stale startup recovery, expanded terminal reload detail, and no generation placeholder

## Outcome Philosophy

Viventium background-agent QA is judged by end-user outcome quality and speed, not by isolated
internal green lights. A case is not production-ready when the classifier merely returns the
expected boolean. It must also prove the user gets a useful first answer quickly, background work
does not block that first answer, activated cortices are visible by name, terminal results persist
after refresh/restart, and degraded provider paths still produce a clear outcome instead of silent
loss.

Every production miss should be promoted into a public-safe synthetic regression case in
`cases.md` / `03_eval_prompt_bank.md` and cross-referenced from `05_coverage_matrix.md`. Preserve
the behavior shape, not private transcript text. Include both positive and negative controls when
the issue is prompt-sensitive, especially for multi-turn activation decisions such as confidence,
sarcasm, denial, and recent-context carryover.

## Requirements Under Test

- Background cortices must not send `temperature` when Anthropic thinking is active.
- The guard must cover thinking that appears only after runtime initialization, not just explicit
  source-of-truth fields.
- Built-in Anthropic cortices that intentionally use `temperature` must set `thinking: false`
  explicitly in the source-of-truth bundle.
- Deep Research must ship with `web_search` in its built-in tool surface whenever runtime web
  search is enabled.
- Deep Research on `openAI / gpt-5.6-sol` must ship
  `model_parameters.reasoning_effort: xhigh`, `useResponsesApi: true`, and must
  not drift onto Anthropic/Google-only `thinkingBudget`.
- Red Team must ship with `web_search` in its built-in tool surface whenever runtime web search is
  enabled.
- Red Team on `openAI / gpt-5.6-sol` must ship and runtime-normalize to
  `model_parameters.reasoning_effort: xhigh`, `useResponsesApi: true`, and must not drift onto
  Anthropic/Google-only `thinkingBudget`.
- The conscious agent uses Sol/medium; Strategic Planning uses Sol/high; Background Analysis,
  Confirmation Bias, Parietal Cortex, and Pattern Recognition use Terra/medium; MS365, Google,
  Emotional Resonance, and Viventium User Help use Terra/low.
- Every conscious/subconscious text route uses `anthropic / claude-opus-4-8` as fallback. Voice
  remains `xai / grok-4.3 / none` with a latency-preserving Terra/none voice fallback.
- High-effort Opus fallbacks preserve the source-owned Anthropic thinking budgets, and cross-provider
  fallback initialization strips OpenAI-only `reasoning_effort` and `useResponsesApi` fields.
- Built-in background-agent provider rewrites must replace provider-specific `model_parameters`
  with the canonical bag for the final provider family instead of blindly merging stale keys.
- Local LibreChat startup must continue sourcing built-in agent truth from
  `viventium/source_of_truth/local.viventium-agents.yaml` via the built-in seed path.

## Environments

- Local public repo checkout on macOS shell tooling
- Nested `viventium_v0_4/LibreChat` workspace test environment
- Public-safe synthetic inputs only

## Test Cases

1. Anthropic endpoint tests verify Sonnet 4.5 removes `temperature` when enabled thinking becomes
   active, and Opus 4.7 removes `temperature` for adaptive thinking.
2. Memory-agent tests verify Anthropic adaptive thinking also strips `temperature`, while disabled
   thinking does not.
3. Background-cortex service tests verify both:
   - explicit pre-initialize thinking + temperature
   - post-initialize hydrated thinking + temperature
   - post-initialize hydrated thinking for a generic user-created Anthropic cortex, not just the
     shipped built-ins
4. Source-of-truth YAML audit verifies there are zero shipped Anthropic background agents with
   `temperature` but no explicit `thinking`/`thinkingBudget`.
5. Deep Research and Red Team source/runtime audit verifies:
   - each source-of-truth tool list contains `web_search`
   - runtime normalization keeps `web_search` when `VIVENTIUM_WEB_SEARCH_ENABLED=true`
   - seed-style upgrades do not preserve stale existing tools when the incoming built-in bundle
     restores `web_search`
   - each OpenAI execution bag uses `reasoning_effort: xhigh` plus Responses API, not
     `thinkingBudget`
6. Provider-matrix audit verifies:
   - the documented OpenAI-only, Anthropic-only, and mixed execution matrix matches compiler
     assignments
   - GPT-5.6 Sol/Terra and effort assignments match the documented workload map
   - Anthropic Opus 4.8 is the explicit fallback for every conscious/subconscious text route
   - runtime normalization and seed/upsert repair stale cross-provider model-parameter drift
7. Start-script inspection verifies local startup still re-seeds built-ins from the source-of-truth
   agents bundle through `viventium-seed-agents.js`.

## Expected Results

- Targeted Jest suites pass for Anthropic endpoint, memory, and background-cortex execution.
- The source-of-truth audit reports zero remaining Anthropic built-ins with ambiguous
  `temperature`-plus-default-thinking behavior.
- The Deep Research and Red Team audits prove fresh installs and upgrade/restart reseeds restore both:
  - `web_search` when runtime web search is enabled
  - `reasoning_effort: xhigh` on the shipped OpenAI execution bag
- The provider-matrix audit proves OpenAI-capable installs use the GPT-5.6 workload map and
  Anthropic-only installs use the explicit Opus 4.8 fallback profile for built-in agents.
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
- Promoted outcome regressions must verify the full user-facing path:
  - the first assistant response remains fast and useful
  - activated background agents are named in visible rows/cards
  - activation detection judges the latest user message as the decision subject; older
    activation-worthy turns in `activation.max_history` are context only and must not create stale
    duplicate cards on a later simple/test/acknowledgement turn
  - each terminal result is a structured `messages.content` cortex part
  - refresh/reload preserves those rows/cards
  - the originating Phase A parent assistant message still contains visible answer text when cards
    attach; a cortex-only parent is a failed run unless the turn intentionally produced `{NTA}`
  - provider degradation resolves through configured fallbacks or a visible terminal error
