# Activation Reliability QA

## Date

- 2026-04-12

## Scope

- Explain why the earlier Anthropic benchmark was wrong.
- Re-run activation-provider benchmarks through the real runtime path used by production activation.
- Compare Groq, Anthropic Haiku 4.5, and SambaNova candidates under the shipped Phase A activation budget.
- Measure both speed and activation quality across the full 11-cortex parallel workload.

## Corrected Root Cause

The earlier Anthropic "failure" was a benchmark bug, not a product verdict.

The bad path had two defects:

1. Activation benchmarking was not using Anthropic's connected-account initializer path.
   - `BackgroundCortexService.buildActivationLlmConfig()` now uses `initializeAnthropic(...)`
     with `thinking: false` for activation checks instead of an env-only shortcut.
2. The standalone benchmark script was not bootstrapping Mongo before invoking activation checks.
   - That meant connected-account lookups could not resolve correctly from the CLI harness.

There was a third benchmark distortion after that fix:

3. The benchmark re-used one real connected-account user across many scenarios, so
   `cooldown_ms` was suppressing later scenarios.
   - The harness now clears activation cooldown state between independent benchmark scenarios.

There was also a config-layer gap for SambaNova:

4. The activation runtime did not have an env-backed `sambanova` custom-endpoint mapping.
   - That mapping now exists, so SambaNova is being tested through the same activation runtime
     path rather than through a separate synthetic probe only.

## Build Under Test

- `viventium_v0_4/LibreChat/api/server/services/BackgroundCortexService.js`
  - Anthropic activation now uses the connected-account initializer path with `thinking: false`
  - env-backed `sambanova` endpoint support added
  - activation cooldown reset helper exported for diagnostics/benchmarking
- `viventium_v0_4/LibreChat/scripts/benchmark-activation-providers.js`
  - connects to Mongo before activation runs
  - clears activation cooldown state between independent scenarios
  - supports benchmarking the real connected-account user path
- `viventium_v0_4/LibreChat/api/test/services/viventium/backgroundCortexService.test.js`
  - coverage for Anthropic connected-account activation init
  - coverage for cooldown reset
  - coverage for env-backed Sambanova endpoint config

## Environment

- Local runtime
- Phase A shipping budget: `2000 ms`
- Additional diagnostic budget used for one Anthropic ceiling test: `10000 ms`
- Source-of-truth bundle:
  - `viventium_v0_4/LibreChat/viventium/source_of_truth/local.viventium-agents.yaml`
- Anthropic measured through the real connected-account runtime path, not a raw API key shortcut

## Method

1. Loaded the real activation prompts from the source-of-truth YAML.
2. For each provider candidate, ran `checkCortexActivation()` across all 11 background cortices in
   parallel for each scenario.
3. Used a real connected-account user context for Anthropic so the benchmark matched the app path.
4. Cleared cooldown state between scenarios to avoid anti-spam logic distorting model comparisons.
5. Recorded:
   - target-hit rate
   - exact-match rate
   - clean-negative rate
   - spillover activations
   - average and P95 batch latency
   - completed, timed-out, and errored activation calls

## Corrected Provider Comparison

| Candidate | Budget | Target Hit Rate | Exact Match Rate | Clean Negative Rate | Avg Spillover | Avg Batch | P95 Batch | Completed Calls | Timeouts | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `groq / meta-llama/llama-4-scout-17b-16e-instruct` | 2s | 100.0% | 50.0% | 100.0% | 1.42 | 475 ms | 654 ms | 132/132 | 0 | Best current production primary. Fast, zero timeouts, but noticeably over-activates adjacent analytical cortices. |
| `anthropic / claude-haiku-4-5` | 2s | 85.7% | 41.7% | 100.0% | 0.92 | 1910 ms | 2004 ms | 122/132 | 10 | Real path works. Accuracy is strong, but it is too close to the 2s budget and misses time-sensitive activation cases. |
| `anthropic / claude-haiku-4-5` | 10s | 100.0% | 50.0% | 100.0% | 1.00 | 2244 ms | 4023 ms | 132/132 | 0 | Accurate when allowed to finish, but too slow to be the shipping 2s primary without changing Phase A budget. |
| `sambanova / Meta-Llama-3.3-70B-Instruct` | 2s | 0.0% | 8.3% | 100.0% | 0.00 | 2010 ms | 2017 ms | 0/132 | 132 | Not viable. The runtime path reaches SambaNova correctly now, but every activation call burns the full budget. |
| `sambanova / Meta-Llama-3.1-8B-Instruct` | 2s | 0.0% | 8.3% | 100.0% | 0.00 | 2011 ms | 2018 ms | 0/132 | 132 | Not viable. Same timeout profile as the 70B candidate. |
| `sambanova / Llama-4-Maverick-17B-128E-Instruct` | 2s | 0.0% | 8.3% | 100.0% | 0.00 | 2010 ms | 2016 ms | 0/132 | 132 | Not viable. Same timeout profile as the other SambaNova candidates. |

## Key Findings

### 1. The user was right about Anthropic

- Anthropic Haiku 4.5 does work through the real connected-account path when activation uses:
  - the existing Anthropic initializer
  - `thinking: false`
- The earlier benchmark failure was invalid because it measured the wrong runtime path.

### 2. Groq is still the best fit for the shipped 2-second Phase A budget

- Groq was the only candidate that hit every target scenario with zero timeouts inside the actual
  shipping activation budget.
- Its weakness is not misses. Its weakness is spillover:
  - it often activates adjacent analytical cortices beyond the minimum exact set.

### 3. Anthropic Haiku 4.5 is a credible fallback, not the best primary at 2 seconds

- At 2 seconds, Haiku hit `85.7%` of targets and timed out `10` activation calls.
- The missed target in the corrected 2-second run was the `ms365_provider_clarification` scenario,
  which is exactly the kind of latency-sensitive path that matters.
- At 10 seconds, Haiku reached `100%` target-hit rate with zero timeouts, proving this is a speed
  problem, not a reasoning-capability problem.

### 4. SambaNova is not usable for this activation topology right now

- After wiring SambaNova into the actual activation runtime path, all three tested models still
  exhausted the full 2-second budget on every activation call.
- This is no longer a configuration artifact. It is now a real measured runtime result for this
  workload.

## Live Local Verification

- The corrected classifier-first activation path was also verified against the local running app on
  April 12, 2026.
- A duplicate local QA user reached the MS365 handoff state (`Checking MS365...`) but did not
  complete the task because that duplicated user did not have valid user-scoped Microsoft 365 OAuth
  at runtime.
- The primary connected local user completed the same synthetic Outlook inbox summary request
  successfully after the real tool run finished, proving the local machine was running the corrected
  activation pattern end to end.
- Product truth from that run:
  - activation health and workspace-tool auth are separate layers
  - a live activation success does not prove that a duplicated QA user has Google/Microsoft parity
  - install/setup/status guidance must tell users to connect both their foundation model account and
    any workspace accounts they expect to use

## Recommendation

1. Keep Groq as the primary activation provider for the current shipped 2-second Phase A budget.
2. Keep Anthropic Haiku 4.5 as the connected-account fallback when the primary is unavailable.
3. Do not switch Anthropic Haiku 4.5 to primary unless one of these changes is intentional:
   - increase the Phase A time budget materially above 2 seconds, or
   - accept missing some latency-sensitive activation cases.
4. Do not pursue SambaNova as a production activation provider for the current 11-cortex parallel
   topology without a materially different rate-limit / latency outcome.

## Raw Artifacts

- Groq, 2s:
  - `qa/results/activation_provider_benchmarks/2026-04-12T20-44-32-533Z/activation-provider-benchmark.json`
  - `qa/results/activation_provider_benchmarks/2026-04-12T20-44-32-533Z/activation-provider-benchmark.md`
- Anthropic Haiku 4.5, 2s:
  - `qa/results/activation_provider_benchmarks/2026-04-12T20-44-46-405Z/activation-provider-benchmark.json`
  - `qa/results/activation_provider_benchmarks/2026-04-12T20-44-46-405Z/activation-provider-benchmark.md`
- Anthropic Haiku 4.5, 10s:
  - `qa/results/activation_provider_benchmarks/2026-04-12T20-45-19-138Z/activation-provider-benchmark.json`
  - `qa/results/activation_provider_benchmarks/2026-04-12T20-45-19-138Z/activation-provider-benchmark.md`
- SambaNova 70B, 2s:
  - `qa/results/activation_provider_benchmarks/2026-04-12T20-45-53-549Z/activation-provider-benchmark.json`
  - `qa/results/activation_provider_benchmarks/2026-04-12T20-45-53-549Z/activation-provider-benchmark.md`
- SambaNova 8B, 2s:
  - `qa/results/activation_provider_benchmarks/2026-04-12T20-46-40-713Z/activation-provider-benchmark.json`
  - `qa/results/activation_provider_benchmarks/2026-04-12T20-46-40-713Z/activation-provider-benchmark.md`
- SambaNova Maverick, 2s:
  - `qa/results/activation_provider_benchmarks/2026-04-12T20-46-44-157Z/activation-provider-benchmark.json`
  - `qa/results/activation_provider_benchmarks/2026-04-12T20-46-44-157Z/activation-provider-benchmark.md`

## Superseded Evidence

- Earlier benchmark artifacts from the same day created before the connected-account, Mongo
  bootstrap, and cooldown-reset fixes should not be used for provider-selection decisions.
