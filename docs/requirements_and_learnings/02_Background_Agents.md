# Background Agents (Cortices) - Requirements, Specs, and Learnings

## Overview

Background agents ("cortices") run in a two-phase flow:

1. Activation detection.
2. Asynchronous execution and insight merge.

They must never degrade tool or MCP capabilities compared to running the same agent directly.

For the manager-readable handbook, start with:

- `qa/background_agents/README.md`
- `qa/background_agents/01_catalog.md`
- `qa/background_agents/06_agent_signoff_manifest.md`

## Core Requirements

- Activation is fast, accurate, and low-noise.
- Execution is non-blocking and does not delay the main response.
- Background agents retain full capabilities: tools, MCPs, code interpreter, web search.
- Deep Research is a shipped web-research cortex:
  - its built-in source-of-truth contract must include `web_search`
  - when its execution family is `openAI / gpt-5.4`, its shipped `model_parameters` must use
    `reasoning_effort: xhigh`, not Anthropic/Google-only thinking fields such as `thinkingBudget`
- Background agents must receive the same user memory context as the main agent when memories are
  enabled, so insights do not regress to fresh-chat behavior.
- Output is merged as background insights and can influence a later voiced follow-up in playground
  mode, but raw insight text must remain background-only.
- Follow-up realizations should still surface shortly after the original request within a
  configurable background follow-up window.

## Execution Matrix

Background-agent execution-family selection is part of the install/compiler/runtime contract, not a
browser-only post-connect side effect.

- The tracked source-of-truth bundle in
  `viventium_v0_4/LibreChat/viventium/source_of_truth/local.viventium-agents.yaml` is the mixed
  launch baseline.
- `scripts/viventium/config_compiler.py` chooses the provider/model mix for the local install.
- `viventium-agent-runtime-models.js` must then normalize each built-in background agent onto the
  canonical execution bag for that target provider family.
- Connecting OpenAI or Anthropic later in the browser unlocks auth for the configured provider mix;
  it does not currently recompute the built-in background-agent roster by itself.

Authoritative execution matrix:

| Agent | Shipped Mixed Baseline | OpenAI-only install | Anthropic-only install | OpenAI + Anthropic install |
| --- | --- | --- | --- | --- |
| Background Analysis | `anthropic / claude-sonnet-4-6` | `openAI / gpt-5.4` | `anthropic / claude-sonnet-4-6` | `anthropic / claude-sonnet-4-6` |
| Confirmation Bias | `anthropic / claude-sonnet-4-6` | `openAI / gpt-5.4` | `anthropic / claude-sonnet-4-6` | `anthropic / claude-sonnet-4-6` |
| Red Team | `openAI / gpt-5.4` | `openAI / gpt-5.4` | `anthropic / claude-opus-4-7` | `openAI / gpt-5.4` |
| Deep Research | `openAI / gpt-5.4` | `openAI / gpt-5.4` | `anthropic / claude-opus-4-7` | `openAI / gpt-5.4` |
| MS365 | `openAI / gpt-5.4` | `openAI / gpt-5.4` | `anthropic / claude-sonnet-4-6` | `openAI / gpt-5.4` |
| Parietal Cortex | `openAI / gpt-5.4` | `openAI / gpt-5.4` | `anthropic / claude-sonnet-4-6` | `openAI / gpt-5.4` |
| Pattern Recognition | `anthropic / claude-sonnet-4-6` | `openAI / gpt-5.4` | `anthropic / claude-sonnet-4-6` | `anthropic / claude-sonnet-4-6` |
| Emotional Resonance | `anthropic / claude-sonnet-4-6` | `openAI / gpt-5.4` | `anthropic / claude-sonnet-4-6` | `anthropic / claude-sonnet-4-6` |
| Strategic Planning | `anthropic / claude-opus-4-7` | `openAI / gpt-5.4` | `anthropic / claude-opus-4-7` | `anthropic / claude-opus-4-7` |
| Viventium User Help | `anthropic / claude-sonnet-4-6` | `openAI / gpt-5.4` | `anthropic / claude-sonnet-4-6` | `anthropic / claude-sonnet-4-6` |
| Google | `openAI / gpt-5.4` | `openAI / gpt-5.4` | `anthropic / claude-sonnet-4-6` | `openAI / gpt-5.4` |

Anthropic Opus budgeting rule:

- For background agents, Anthropic Opus is reserved for:
  - `Red Team`
  - `Deep Research`
  - `Strategic Planning`
- Other background agents must stay on Anthropic Sonnet when Anthropic is the selected execution
  family so the install does not silently waste Opus tokens.

Canonical model-parameter rule:

- Built-in background agents must not carry provider-family-specific execution parameters across a
  provider rewrite.
- Illegal examples:
  - `reasoning_effort` surviving on an Anthropic execution bag
  - `thinkingBudget` or `thinking` surviving on an OpenAI execution bag
- The runtime normalization and built-in seed/upsert path must both resolve the canonical
  model-parameter bag for the final provider family instead of blindly merging stale keys.

## Public-Safe Implementation Notes

- Keep activation logic in source-of-truth prompts and structured metadata.
- Keep runtime plumbing generic and reusable.
- Use explicit tests and evidence collection to verify activation and follow-up behavior.
- Do not encode private names, machine names, or client examples into the runtime contract.
- Every shipped background cortex must carry an explicit live-fact truthfulness guard for
  weather/news/markets/web facts. If the cortex lacks verified evidence for that category, it must
  omit the item rather than guess.
- Productivity cortices must scope their synthesis to verified results from their owned provider.
  Google Workspace and MS365 cortices must not answer weather, news, markets, web, or opposite-provider
  facts just because the scheduled prompt also mentions them. If a requested item is outside the
  verified provider result set, omit it from the cortex insight instead of guessing or adding a
  placeholder.

## Anthropic Runtime Compatibility

- Anthropic background cortices must never send `temperature` when `thinking` is active.
- This includes provider-default thinking that can be materialized later during runtime hydration, not
  just explicit `thinking` fields already present in the source-of-truth YAML.
- Background-cortex execution should therefore re-check the final initialized Anthropic config before
  Phase B execution and remove `temperature` if thinking is active.
- Current shipped Anthropic Sonnet 4.6 built-ins should not carry explicit `temperature` at all.
- If a future Anthropic built-in ever intentionally reintroduces temperature tuning, it must set
  `thinking: false` explicitly and be re-validated against the current Anthropic API contract before
  shipping.

## Memory Context Parity

Background cortices should receive the same shared context blocks the main agent sees when the
feature is enabled:

- canonical time context
- attached file context when relevant
- existing user memories when allowed

## Tool Cortex Breathing Hold

When a tool-focused cortex activates, the system should avoid producing a premature answer from
memory. Instead, it should emit a short holding acknowledgement and post the actual result once the
background cortex finishes.

Runtime rules:

- hold decisions should come from structured activation metadata
- live tool requests may defer
- generic conversational follow-ups should not defer just because a productivity cortex activated

## Background-Agent QA Standard

Background-agent QA should read like a launch review, not like a notebook of ad hoc observations.
Minimum standard:

- test positives, negatives, near-misses, overlaps, and regression cases
- separate activation proof from downstream behavior proof
- verify policy objects still carry canonical scope keys where applicable
- collect at least two layers of evidence: user-visible result and persisted truth/logs

## What To Do When Something Fails

Use this order so the fix stays surgical:

1. confirm whether the failure is activation, execution, or follow-up
2. check whether the problem is model/config-driven or runtime-driven
3. compare the result against the exact prompt family, not just one example
4. update the QA set if the failure exposed a new boundary
5. only then change runtime code or source-of-truth prompts

## Learnings

- On April 5, 2026, live failures for `Confirmation Bias` and `Emotional Resonance` traced to
  Anthropic rejecting `temperature` after default thinking was added during initialization.
- Fixing only the pre-initialize background-cortex copy was insufficient because the provider layer
  can still hydrate `thinking` later.
- Fixing only the provider layer would stop the crash but could silently change the intended shipped
  behavior of temperature-tuned built-ins; those built-ins also need truthful source-of-truth
  `thinking` settings.
- Activation intent detection is classifier-owned. Runtime code must not regex-match user text to
  decide activation or to prune activation history based on guessed semantics.
- When activation phrasing needs to expand, fix the source-of-truth activation prompt and prove it
  with live evals.
- When the classifier provider is unavailable, fix reliability with `activation.fallbacks`, not with
  deterministic runtime heuristics.
- Activation and execution must be diagnosed separately. A productivity cortex can activate
  correctly and still fail later if its execution-model credential or connected account is expired.
- On April 24, 2026, a scheduled Telegram check exposed two separate issues: an Anthropic malformed
  thinking-content execution failure and a scheduler ledger that treated the resulting deferred
  fallback as ordinary `sent/delivered`. Scheduled cortex polling must thread `scheduleId` into
  cortex-state recovery and preserve structured fallback provenance so degraded fallback delivery is
  either suppressed or recorded as `fallback_delivered`, never hidden as a normal successful result.
  The owning boundaries are the deferred fallback helper
  (`api/server/services/viventium/cortexFallbackText.js:74`), cortex-state provenance
  (`api/server/services/viventium/cortexMessageState.js:214`), scheduler polling
  (`viventium/MCPs/scheduling-cortex/scheduling_cortex/dispatch.py:1213`), fallback visibility
  classification (`viventium/MCPs/scheduling-cortex/scheduling_cortex/dispatch.py:1901`), and
  persisted degradation metadata (`viventium/MCPs/scheduling-cortex/scheduling_cortex/scheduler.py:29`).
- On April 14, 2026, a shipped-source audit caught a Deep Research drift:
  - the built-in bundle still carried `web_search`, but its OpenAI execution bag was using
    `thinkingBudget` instead of the documented OpenAI `reasoning_effort`
  - the supported fix is source-of-truth correction plus reseed/runtime tests proving upgrades and
    restarts restore the intended tool surface for built-in users
- Activation-provider benchmarks must use the same auth/runtime path as the product:
  - connected-account providers must be measured through their connected-account initializer path
  - standalone eval scripts must bootstrap Mongo/runtime dependencies before running activation
  - cooldown state must be cleared between benchmark scenarios when one real user is reused
- On April 12, 2026, corrected live benchmarking under the real 11-cortex parallel load showed:
  - `groq / meta-llama/llama-4-scout-17b-16e-instruct` was the best shipping primary for the
    current 2-second Phase A budget: fast, zero timeouts, and full target-hit rate
  - `anthropic / claude-haiku-4-5` worked correctly through the connected-account path with
    `thinking: false`, but at the shipping 2-second budget it was too close to timeout to replace
    Groq as the primary
  - the same Haiku model hit full target coverage when given a larger 10-second diagnostic budget,
    proving the limitation was latency, not activation reasoning quality
  - the tested SambaNova candidates remained non-viable for the current 11-cortex topology because
    they exhausted the full 2-second budget under parallel activation
