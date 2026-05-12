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
- If the user and assistant have already exchanged newer visible messages before Phase B completes,
  the follow-up adjudicator must see that newer exchange and decide whether the background result is
  still useful now or should resolve to `{NTA}`.

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

Model inventory rule:

- Do not configure a phantom Anthropic model to satisfy UI expectations. On the May 6, 2026 local
  inventory, `claude-sonnet-4-7` is not exposed by source-of-truth model specs or the local runtime;
  the launch-ready Sonnet family remains `claude-sonnet-4-6`.
- Background agents that are latency-sensitive but still use Anthropic Sonnet must declare a
  reachable execution fallback. The mixed local baseline uses `xai / grok-4.3` for Confirmation
  Bias because OpenAI can be rate-limited on local QA, while other timeout-prone cortices may use
  `openAI / gpt-5.4` with `reasoning_effort: high` when that provider is the intended backup.
  Phase B runtime owns retrying the configured backup once for provider timeout/abort/recoverable
  provider failures; prompt-only changes must not be used to hide those errors.
- Every built-in background cortex activation classifier uses
  `groq / meta-llama/llama-4-scout-17b-16e-instruct` as the primary Phase A detector. It must
  carry provider fallbacks: `xai / grok-4.20-non-reasoning` first, then `openai / gpt-5.4`, then
  `anthropic / claude-haiku-4-5`. This is a reliability contract for provider outages such as
  activation-provider 403/401/429 responses; it must not change activation intent semantics, add
  runtime keyword heuristics, or silently promote fallback providers into the default fast path.
- Phase A OpenAI activation fallback must apply the same reasoning-model sampling guard as Phase B:
  Viventium's configured `gpt-5.4` activation run must not receive `temperature`, `topP`, penalties,
  `n`, or logprob sampling controls.
- Phase B execution has a bounded outer guard so a stuck or aborted background run cannot leave the
  UI on permanent progress. The guard is the agent execution timeout plus a small grace window;
  `VIVENTIUM_CORTEX_EXECUTION_GUARD_GRACE_MS` may tune only that grace window, defaults to 15s,
  and is clamped between 0s and 60s.

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
  - sampling controls such as `temperature`, `topP`, penalties, `n`, or `logprobs` surviving on an
    OpenAI reasoning-style execution bag known to reject sampling, such as `gpt-5`, `gpt-5-pro`,
    Viventium's configured `gpt-5.4` runtime family, or `o1`/`o3`
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
- Background cortices must not claim that a tool, worker, browser, file, email, or OS action
  happened unless that same cortex received a verified tool result for it during the current run.
  When the main agent is handling a direct execution request and a cortex has no independent
  verified result, the cortex should emit no visible insight.
- The shared activation policy lives in
  `config.viventium.background_cortices.activation_policy`. It is a source-of-truth prompt/config
  contract, not runtime NLU. It declares direct-action MCP surfaces by exact tool names, such as
  GlassHive worker/project tools and Scheduling Cortex tools. Runtime may pass the main agent's
  configured tool list into the activation prompt, but must not infer intent from user text or parse
  tool-name substrings to decide behavior.
- If a user request is primarily a direct action, status check, follow-up, approval, or result
  request for a declared direct-action surface, generic cortices should not activate unless their
  configured scope owns a separate part of the request. When they do activate for that separate
  part, they must not narrate tool, worker, browser, schedule, or runtime status.
- Cortex execution that returns empty output or the exact no-response token `{NTA}` is silent
  success. It must not render a visible "Insight from ..." card.
- Silent success is still terminal. Runtime must emit and persist a structured completion payload
  with `status=complete`, `silent=true`, and `no_response=true` so any previous brewing/progress row
  is replaced instead of leaving the UI stuck on "checking" or "analyzing".
- Activation detection always judges the latest human/user message as the decision subject.
  Configured history depth provides context only. Older user requests in that history must not
  reactivate a cortex when the latest user turn is a simple reply, acknowledgement, test
  instruction, correction, thanks, provider clarification, or output-only instruction that does not
  itself meet the cortex activation criteria. The shared rule is source-owned at
  `viventium.background_cortices.activation_subject_rule.prompt` and applies to every background
  cortex activation prompt.

## Non-Blocking Main-Agent Communication Contract

Background agents are not a second chat surface. They are non-blocking evidence producers for the
main agent path.

Requirements:

- Non-negotiable brain-inspired flow:
  1. Phase A starts with Groq-first activation detection. The primary detector is
     `groq / meta-llama/llama-4-scout-17b-16e-instruct`; configured fallbacks are reliability
     backups, not a semantic replacement for Groq-first behavior.
  2. Within the activation-detection wait budget, every activated background agent is passed into
     the main-agent Phase A context with its name, reason, confidence, and scope.
  3. The main agent streams its Phase A answer immediately and that authored answer remains visible
     and durable.
  4. Cortex cards/rows are additive status surfaces. They appear as soon as activation is detected,
     update independently as each background agent runs, and never replace the main answer.
  5. Each activated background agent card must expose a user cancel affordance. Canceling one
     background agent must not interrupt the other activated background agents. If the user cancels
     all activated background agents before useful results exist, Phase B has no insights to raise
     and must not synthesize a follow-up.
  6. Phase B waits for the non-canceled activated background agents to finish. It may append a
     separate same-conversation follow-up only when the finished results add useful new value.
  7. Reloading the conversation must show both the original Phase A answer and the background
     cortex cards/results. Cards must never erase, replace, or become the only durable parent
     assistant content unless Phase A intentionally produced a structured no-visible-answer marker
     such as `{NTA}`.
- The main assistant turn must never wait on background agents before answering the user.
- Background agent results must travel over a durable, structured, DB-backed communication line
  tied to the originating conversation and assistant message. In-memory callbacks may improve
  latency, but they must not be the only delivery path.
- The communication payload should carry structured provenance such as cortex id/name, activation
  scope, activated-agent one-line description, direct-action surface scope keys, result text,
  tool-call counts, timestamps, and error/degradation state. It must not carry secrets, raw logs,
  browser screenshots, local absolute paths, or private runtime artifacts.
- Completion payloads must distinguish three terminal outcomes: visible insight, silent no-response
  success, and error. Logs should report visible insight counts, silent completion counts, and error
  counts separately so empty `{NTA}` output is not misclassified as an unexpected failure.
- Activation awareness injected into the main-agent turn must tell the main agent which background
  agents activated, why they activated, what scope they own, and which activated scopes the main
  agent can cover through connected direct tools.
- If an activated background scope is also covered by a connected main-agent direct-action surface,
  Phase A must run the main agent first. The main agent should use its own verified tool results for
  the directly owned portion while Phase B continues as supplemental evidence.
- Direct-action scope declarations may mark `same_scope_background_allowed=true` when the matching
  background agent should still activate for supplemental Phase B evidence. This flag is generic; it
  must not branch on agent names or prompt text.
- If a background agent's configured activation scope exactly matches a connected main-agent
  direct-action scope and `same_scope_background_allowed` is not true, runtime must structurally
  suppress that activation after classifier output. This is not user-text NLU; it is a guardrail
  between two structured scope declarations.
- Background agents provide evidence only. They do not decide whether the user should see a
  follow-up message.
- The main-agent follow-up/adjudication path owns the visible decision. It receives the background
  evidence as an injected continuation prompt, compares it to the response the main agent already
  gave, and either writes a concise same-conversation follow-up as a new assistant message or outputs
  exactly `{NTA}`.
- Phase B follow-ups are nonblocking additions. Runtime must not replace, overwrite, or rewrite the
  original Phase A assistant message when Phase B completes.
- Phase B may still upsert structured cortex status/insight parts onto the Phase A message for
  durable progress/history. That parent content-part upsert is not a Phase A text replacement; the
  Phase A text and authored answer remain unchanged.
- If the primary main model fails before visible assistant text and runtime retries a configured
  fallback model, the original Phase B execution still belongs to the same originating assistant
  message. Runtime must not erase, restart, or orphan that in-flight background work; durable
  persistence and follow-up adjudication should wait for the final primary-or-fallback answer.
- If the final primary-or-fallback main path still leaves the canonical parent with no visible text
  while Phase B has substantive completed insights, runtime may promote the forced Phase B synthesis
  onto that otherwise empty parent. This is the only parent-text promotion exception: it must not
  rewrite a valid authored Phase A answer, must not run after the conversation has moved on, must not
  apply to scheduled `{NTA}` holds, and must preserve structured cortex parts on the same parent.
- If the main model stream terminates after visible assistant text already exists, runtime must
  preserve the authored text and structured cortex parts without appending a generic fatal error
  card to the same message. The failure remains diagnostic/log evidence. Error-only turns and
  non-termination provider failures must still surface honestly.
- User-facing cortex status rows and expanded cards must show which background cortex/agent
  activated, why it activated, and its result. The collapsed row should use the cortex/agent name
  directly, and the expanded card should use clear labels such as "Result from <cortex name>" and
  "Background agent: <cortex name>". Avoid generic labels such as "Additional thought" and harsher
  phrasing like "Insight from <cortex name>". Raw implementation IDs stay in structured metadata,
  logs, diagnostics, and developer views.
- Background-agent acceptance is outcome-first: a green activation decision is insufficient unless
  the end user receives a fast useful first answer, named cortex visibility, durable terminal
  results after refresh/restart, and clear degraded-provider behavior. Any production miss in those
  areas must be converted into a public-safe synthetic regression in `qa/background_agents/`, with
  both positive and negative controls when prompt wording or recent context is part of the failure.
- If the originating Phase A response text is exactly `{NTA}` and Phase B later has substantive
  insight text, merged context, or an allowed deferred error, `{NTA}` is treated as an internal
  no-visible-answer marker for adjudication. Phase B may force a visible new assistant follow-up,
  but it must still append as a separate message rather than editing Phase A.
- If the conversation has moved on since the originating response, the adjudication prompt must also
  include the newer visible user/assistant exchange so the main agent can avoid stale or interruptive
  follow-ups without runtime text matching.
- `{NTA}` means silent success. It is valid for redundant, irrelevant, or non-actionable
  background results and must not be delivered to web, Telegram, or voice users.
- Web rendering must hide runtime-generated hold text parts marked as no-response, such as a
  scheduler Phase A `{NTA}` marker, using the structured runtime-hold flag rather than broad
  keyword filtering. The stored parent message is not edited; only the internal hold token is not
  rendered.
- For moved-on conversations, empty generation or follow-up LLM failure usually stays silent; forced
  follow-up fallback is reserved for cases where Phase A intentionally had no visible answer or a
  deterministic hold while useful Phase B evidence arrived.
- Errors and degradation are not hidden behind `{NTA}`. If a background worker or cortex has a real
  blocker that changes the user outcome, the follow-up path must surface a concise blocker or
  failure message.
- Deferred error copy should preserve the failure class when known: provider access denied,
  provider credentials rejected, rate-limited provider, timeout, and runtime-restart recovery are
  different user-visible situations and should not all collapse to the same generic line.
- Surface adapters such as web, Telegram, and voice poll the same persisted follow-up state. They
  must not invent separate delivery logic that bypasses the main-agent adjudication/NTA gate.
- Direct-action worker callbacks that are already adjudicated as user-visible still need durable
  surface delivery when they originate from Telegram or voice. The same principle applies: in-memory
  pollers are fast paths only; DB-backed callback/delivery rows own late, restart-safe delivery.
- The implementation must stay generic: no runtime prompt-text matching, no hardcoded cortex names,
  and no tool-substring NLU. Structured metadata and source-of-truth activation prompts own scope.

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

## OpenAI Runtime Compatibility

- OpenAI reasoning-style background and follow-up runs must not send sampling controls that the
  configured provider runtime rejects.
- This guard applies before and after agent initialization because runtime hydration can materialize
  model parameters after the source-of-truth copy is made.
- The source-of-truth bundle and runtime canonical parameter map must not ship `temperature`,
  `topP`, penalties, `n`, `logprobs`, or related sampling fields for OpenAI no-sampling reasoning
  runs such as `gpt-5`, dash-suffixed `gpt-5` reasoning variants, Viventium's configured `gpt-5.4`
  runtime family, or `o1`/`o3`.
- Do not blindly generalize the `gpt-5.4` runtime rule to every dotted `gpt-5.x` model id. Some
  upstream OpenAI initialization paths treat versioned dotted IDs as sampling-capable; new dotted
  model IDs must be added to the no-sampling compatibility set only after runtime evidence or an
  upstream provider-contract change.

## Memory Context Parity

Background cortices should receive the same shared context blocks the main agent sees when the
feature is enabled:

- canonical time context
- attached file context when relevant
- existing user memories when allowed

## Tool Cortex Breathing Hold

When a tool-focused cortex activates and the main agent has no matching connected direct-action
surface for that activation scope, the system should avoid producing a premature answer from memory.
Instead, it should emit a short holding acknowledgement and post the actual result once the
background cortex finishes.

Runtime rules:

- hold decisions come from structured activation metadata plus declared direct-action scope keys
- live tool requests may defer only when no activated direct-action scope is available to the main
  agent
- generic conversational follow-ups should not defer just because a productivity cortex activated
- stale active cortex rows from a process restart must be repaired to terminal error state on startup
  so web, Telegram, scheduler, and voice clients do not display permanent progress
- activation cooldowns are duplicate-request protection, not user-level suppression. They must use
  structured user/conversation/message identity when available, and must not block a distinct live
  productivity request such as email immediately after a calendar request from the same user.
- stale recovery cutoff must be at least the configured Phase B execution timeout plus a grace
  window, so a routine restart does not mark legitimate in-flight Phase B work as failed

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
- Product-help cortices are for user-facing usage/navigation/onboarding help, not operator
  diagnostics. They must not activate for incident triage, root-cause analysis, logs/database/code
  investigation, model inventory questions, provider routing issues, activation mistakes, QA, or
  fix requests.
- When the classifier provider is unavailable, fix reliability with source-of-truth activation
  routing/fallbacks, not with deterministic runtime heuristics.
- Phase A fallback reliability must be bounded inside the same activation-detection wait budget.
  Groq remains the first attempted classifier, but a slow primary attempt must not consume the
  entire turn when configured fallbacks are available. Runtime should use per-attempt activation
  timeouts so xAI/OpenAI/Anthropic fallbacks can rescue provider reachability failures without
  changing activation semantics.
- Late background activation recovery is opt-in only. By default, if activation was not known before
  the main answer starts, runtime must not later surface new activation cards that the main model
  never saw in its Phase A context.
- On May 10, 2026, local QA reproduced a Groq outage while the operator's VPN was enabled. That is
  an environment/provider-reachability failure, not evidence to change Viventium's default
  activation model family. The supported baseline remains
  `groq / meta-llama/llama-4-scout-17b-16e-instruct` as the primary activation detector.
  xAI, OpenAI, and Anthropic remain true fallbacks or explicit user-selected overrides. Browser
  QA for activation must record whether VPN/provider reachability was healthy, prove named
  cards are visible, persist after reload, and store successful terminal insights.
- Activation and execution must be diagnosed separately. A productivity cortex can activate
  correctly and still fail later if its execution-model credential or connected account is expired.
- Direct proof-by-execution requests, such as asking Viventium to run a GlassHive/Codex/Claude
  worker on the local machine, are owned by the main agent and the worker/tool path. Analysis,
  planning, support, and research cortices should not activate just to speculate about whether the
  dispatch is possible.
- Background insight text must never fabricate tool transcripts, run ids, worker ids, or dispatch
  confirmations. Those values are authoritative only when they come from the tool result or durable
  runtime store.
- On April 24, 2026, a scheduled Telegram check exposed two separate issues: an Anthropic malformed
  thinking-content execution failure and a scheduler ledger that treated the resulting deferred
  fallback as ordinary `sent/delivered`. Scheduled cortex polling must thread `scheduleId` into
  cortex-state recovery and preserve structured fallback provenance so degraded fallback delivery is
  either suppressed or recorded as `fallback_delivered`, never hidden as a normal successful result.
	  The owning boundaries are the deferred fallback helper
	  (`api/server/services/viventium/cortexFallbackText.js`), cortex-state provenance
	  (`api/server/services/viventium/cortexMessageState.js`), scheduler polling and fallback
	  visibility classification (`viventium/MCPs/scheduling-cortex/scheduling_cortex/dispatch.py`),
	  and persisted degradation metadata
	  (`viventium/MCPs/scheduling-cortex/scheduling_cortex/scheduler.py`).
- On April 14, 2026, a shipped-source audit caught a Deep Research drift:
  - the built-in bundle still carried `web_search`, but its OpenAI execution bag was using
    `thinkingBudget` instead of the documented OpenAI `reasoning_effort`
  - the supported fix is source-of-truth correction plus reseed/runtime tests proving upgrades and
    restarts restore the intended tool surface for built-in users
- Activation-provider benchmarks must use the same auth/runtime path as the product:
  - connected-account providers must be measured through their connected-account initializer path
  - standalone eval scripts must bootstrap Mongo/runtime dependencies before running activation
  - cooldown state must be cleared between benchmark scenarios when one real user is reused
- On April 12, 2026, corrected live benchmarking under the real 11-cortex parallel load showed
  Groq as the best primary for the shipping activation topology. The May 10, 2026 VPN incident did
  not supersede that benchmark; it tightened the requirement that fallback QA distinguish provider
  reachability from activation reasoning quality.
  - `groq / meta-llama/llama-4-scout-17b-16e-instruct` was the best shipping primary for that
    2-second Phase A budget: fast, zero timeouts, and full target-hit rate
  - `anthropic / claude-haiku-4-5` worked correctly through the connected-account path with
    `thinking: false`, but at the shipping 2-second budget it was too close to timeout to replace
    Groq as the primary
  - the same Haiku model hit full target coverage when given a larger 10-second diagnostic budget,
    proving the limitation was latency, not activation reasoning quality
  - the tested SambaNova candidates remained non-viable for the current 11-cortex topology because
    they exhausted the full 2-second budget under parallel activation
