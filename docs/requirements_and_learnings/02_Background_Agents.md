# Background Agents (Cortices) - Requirements, Specs, and Learnings

## Overview

Background agents ("cortices") run in a two-phase flow:

1. Activation detection.
2. Asynchronous execution and insight merge.

They must never degrade tool or MCP capabilities compared to running the same agent directly.

For the manager-readable handbook, start with:

- `docs/requirements_and_learnings/52_Background_Agent_QA_and_Persona.md`
- `qa/background_agents/README.md`

## Core Requirements

- Activation is fast, accurate, and low-noise.
- Execution is non-blocking and does not delay the main response.
- Background agents retain full capabilities: tools, MCPs, code interpreter, web search.
- Background agents must receive the same user memory context as the main agent when memories are
  enabled, so insights do not regress to fresh-chat behavior.
- Output is merged as background insights and can be voiced in playground mode.
- Follow-up realizations should still surface shortly after the original request within a
  configurable grace window.

## Public-Safe Implementation Notes

- Keep activation logic in source-of-truth prompts and structured metadata.
- Keep runtime plumbing generic and reusable.
- Use explicit tests and evidence collection to verify activation and follow-up behavior.
- Do not encode private names, machine names, or client examples into the runtime contract.

## Anthropic Runtime Compatibility

- Anthropic background cortices must never send `temperature` when `thinking` is active.
- This includes provider-default thinking that can be materialized later during runtime hydration, not
  just explicit `thinking` fields already present in the source-of-truth YAML.
- Background-cortex execution should therefore re-check the final initialized Anthropic config before
  Phase B execution and remove `temperature` if thinking is active.
- When a shipped Anthropic cortex is intentionally temperature-tuned rather than thinking-enabled,
  its source-of-truth `model_parameters` must set `thinking: false` explicitly so fresh installs and
  runtime reseeding preserve the intended behavior.

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
