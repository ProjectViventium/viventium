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
- Productivity cortices must ship with their provider-owned MCP tools attached:
  - `MS365` owns the Microsoft 365 MCP Outlook/calendar/file tool array.
  - `Google` owns the Google Workspace MCP Gmail/calendar/Drive/docs/sheets tool array.
  - A productivity cortex that activates with an empty or generic-only tool list is degraded; it
    must not substitute memory, recall, or file search for live inbox/workspace evidence.
- Deep Research is a shipped web-research cortex:
  - its built-in source-of-truth contract must include `web_search`
  - when its execution family is `openAI / gpt-5.6-sol`, its shipped `model_parameters` must use
    `reasoning_effort: xhigh`, not Anthropic/Google-only thinking fields such as `thinkingBudget`
  - it must use the Responses API because this is a reasoning-plus-tools workload
- Red Team is a shipped adversarial decision-quality cortex:
  - its built-in source-of-truth contract must include `web_search` so evidence-first checks can
    actually use live evidence when runtime web search is enabled
  - when its execution family is `openAI / gpt-5.6-sol`, its shipped and runtime-normalized
    `model_parameters` must use `reasoning_effort: xhigh`, not Anthropic/Google-only thinking
    fields such as `thinkingBudget`
  - it must use the Responses API because this is a reasoning-plus-tools workload
- Shipping a specialist background agent does not require the main Viventium agent to auto-activate
  it. In the current local baseline, the main agent keeps `Deep Research`, `MS365`, and `Google`
  background activation disabled. Live web/productivity execution should be handled by the
  main/direct path: the Connected Accounts hand-off for immediate connected-account checks and
  explicitly confirmed non-destructive email/calendar updates, and GlassHive workers with brokered
  connected-account capability for delegated, longer, artifact, browser/computer, or co-work
  requests. The specialist agents remain defined with their owned tools for direct use, explicit
  future re-enablement, and regression coverage. Connected-account writes such as creating/updating
  calendar events or sending/drafting email require explicit user confirmation and an available
  write-capable connected-account path; Connected Accounts may handle them only when the required
  non-destructive email/calendar write tool is present. Destructive or broad mutations such as
  deleting/moving/archive/mark-read mail, deleting calendar events, sharing/permission changes, and
  file writes require GlassHive or another explicitly confirmed write-capable path. If no
  write-capable path is available, the user-visible answer must say so plainly.
- Background agents must receive the same user memory context as the main agent when memories are
  enabled, so insights do not regress to fresh-chat behavior.
- Output is merged as background insights and can influence a later voiced follow-up in playground
  mode, but raw insight text must remain background-only.
- Follow-up realizations should still surface shortly after the original request within a
  configurable background follow-up window.
- Phase B follow-up generation must preserve the live main-agent provider/model route that produced
  the parent turn. Compiled/source runtime defaults may fill missing agent fields, but must not
  override an explicit user-managed live route and accidentally send follow-ups to a different
  provider.
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
| Viventium conscious | `openAI / gpt-5.6-sol / medium` | `openAI / gpt-5.6-sol / medium` | `anthropic / claude-opus-4-8` | `openAI / gpt-5.6-sol / medium` |
| Background Analysis | `openAI / gpt-5.6-terra / medium` | `openAI / gpt-5.6-terra / medium` | `anthropic / claude-opus-4-8` | `openAI / gpt-5.6-terra / medium` |
| Confirmation Bias | `openAI / gpt-5.6-terra / medium` | `openAI / gpt-5.6-terra / medium` | `anthropic / claude-opus-4-8` | `openAI / gpt-5.6-terra / medium` |
| Red Team | `openAI / gpt-5.6-sol / xhigh` | `openAI / gpt-5.6-sol / xhigh` | `anthropic / claude-opus-4-8` | `openAI / gpt-5.6-sol / xhigh` |
| Deep Research | `openAI / gpt-5.6-sol / xhigh` | `openAI / gpt-5.6-sol / xhigh` | `anthropic / claude-opus-4-8` | `openAI / gpt-5.6-sol / xhigh` |
| MS365 | `openAI / gpt-5.6-terra / low` | `openAI / gpt-5.6-terra / low` | `anthropic / claude-opus-4-8` | `openAI / gpt-5.6-terra / low` |
| Parietal Cortex | `openAI / gpt-5.6-terra / medium` | `openAI / gpt-5.6-terra / medium` | `anthropic / claude-opus-4-8` | `openAI / gpt-5.6-terra / medium` |
| Pattern Recognition | `openAI / gpt-5.6-terra / medium` | `openAI / gpt-5.6-terra / medium` | `anthropic / claude-opus-4-8` | `openAI / gpt-5.6-terra / medium` |
| Emotional Resonance | `openAI / gpt-5.6-terra / low` | `openAI / gpt-5.6-terra / low` | `anthropic / claude-opus-4-8` | `openAI / gpt-5.6-terra / low` |
| Strategic Planning | `openAI / gpt-5.6-sol / high` | `openAI / gpt-5.6-sol / high` | `anthropic / claude-opus-4-8` | `openAI / gpt-5.6-sol / high` |
| Viventium User Help | `openAI / gpt-5.6-terra / low` | `openAI / gpt-5.6-terra / low` | `anthropic / claude-opus-4-8` | `openAI / gpt-5.6-terra / low` |
| Google | `openAI / gpt-5.6-terra / low` | `openAI / gpt-5.6-terra / low` | `anthropic / claude-opus-4-8` | `openAI / gpt-5.6-terra / low` |

Model inventory rule:

- The built-in conscious/subconscious source uses only the connected-account-proven explicit
  `gpt-5.6-sol` and `gpt-5.6-terra` slugs. Do not use the unsupported connected-account alias or
  Luna on these built-ins merely because direct API-key inventory exposes them.
- Every source-owned conscious/subconscious agent declares `anthropic / claude-opus-4-8` as its
  text fallback. That route is usable only when Anthropic auth is configured for the user/runtime;
  missing fallback auth must surface honestly rather than causing a silent model downgrade.
  Phase B runtime owns retrying the configured backup once for provider timeout/abort/recoverable
  provider failures; prompt-only changes must not be used to hide those errors.
- Every built-in background cortex activation classifier uses
  `groq / qwen/qwen3.6-27b` as the primary Phase A detector. Qwen thinking must be disabled with
  `reasoning_effort: none`, its reasoning trace must stay hidden, and JSON-object mode plus a fixed
  seed must keep the classifier fast and machine-readable. It must
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

Anthropic Opus fallback rule:

- Opus 4.8 is the explicit fallback for every conscious/subconscious text route.
- Fallback parameter bags remain provider-native: Red Team and Deep Research use
  `thinkingBudget: 4000`, Strategic Planning uses `thinkingBudget: 2000`, and the retry path must
  strip OpenAI-only `reasoning_effort` and `useResponsesApi` fields before Anthropic initialization.
- On an Anthropic-only install, Opus 4.8 becomes the execution route for all built-in agents because
  the preferred GPT-5.6 route is unavailable. This is an explicit quality-first fallback posture,
  not a cost optimization; operators who need a cheaper Anthropic-only mix must use reviewed model
  overrides rather than silently returning the shipped bundle to Sonnet.

Canonical model-parameter rule:

- Built-in background agents must not carry provider-family-specific execution parameters across a
  provider rewrite.
- Illegal examples:
  - `reasoning_effort` surviving on an Anthropic execution bag
  - `thinkingBudget` or `thinking` surviving on an OpenAI execution bag
  - sampling controls such as `temperature`, `topP`, penalties, `n`, or `logprobs` surviving on an
    OpenAI reasoning-style execution bag known to reject sampling, such as `gpt-5`, `gpt-5-pro`,
    Viventium's configured GPT-5.6 Sol/Terra runtime family, or `o1`/`o3`
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
  itself meet the cortex activation criteria. Output-only instructions include exact-text markers,
  labels, confirmations, acknowledgements, and test tokens. Activation words in older history, such
  as "red-team", "pressure-test", "plan", "pattern", or "bias", do not count unless the latest
  message repeats them or explicitly asks to continue that same work. The shared rule is source-owned at
  `viventium.background_cortices.activation_subject_rule.prompt` and applies to every background
  cortex activation prompt.

## Non-Blocking Main-Agent Communication Contract

Background agents are not a second chat surface. They are non-blocking evidence producers for the
main agent path.

Requirements:

- Non-negotiable brain-inspired flow:
  1. Phase A starts with Groq-first activation detection. The primary detector is
     `groq / qwen/qwen3.6-27b`; configured fallbacks are reliability
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
- Phase A notice mode is configurable. The shipped default is
  `VIVENTIUM_CORTEX_PHASE_A_NOTICE_MODE=any_activated_on_voice`: voice calls may release Phase A
  as soon as the first activated background detector returns `should_activate=true`, while web,
  Telegram, scheduler, and other text surfaces still wait for the complete configured detection
  budget:
  - `VIVENTIUM_CORTEX_PHASE_A_NOTICE_MODE=all_within_budget` waits for the full configured
    activation set to resolve or time out inside the budget before injecting activation awareness.
  - `VIVENTIUM_CORTEX_PHASE_A_NOTICE_MODE=any_activated` may release Phase A as soon as the first
    activation classifier returns `should_activate=true` after structured direct-action ownership
    gates are applied. Provider-unavailable and timeout terminal cards must not trigger early
    release.
  - `VIVENTIUM_CORTEX_PHASE_A_NOTICE_MODE=any_activated_on_voice` is the default and applies that
    early-release behavior only to the voice-call surface; web, Telegram, scheduler, and other text
    surfaces keep `all_within_budget`.
- The shipped voice default now keeps `VIVENTIUM_VOICE_BACKGROUND_AGENT_DETECTION_ASYNC=true` with a
  690 ms Phase A budget. Voice may start the speculative main answer immediately, then abort and
  re-run Phase A with activation awareness if a cortex activates inside that budget before TTFT.
  Text mode remains non-speculative by default unless explicitly enabled.
- Telegram voice-note and always-voice replies are text-mode turns with optional audio delivery.
  They do not use the LiveKit voice-call async policy, Voice Call LLM override, or voice-call
  prompt.
- When async voice detection is enabled, detection still runs to completion for Phase B. Voice mode
  defaults to staying async even when a configured tool-hold cortex exists; late or side-effecting
  evidence must arrive through Phase B/follow-up instead of blocking the first answer. The early
  `any_activated_on_voice` notice optimization is therefore only a Phase A timing signal, not proof
  that the first activation is the complete activated set.
- When Phase A releases early from first activation, the main-agent instruction must be generic:
  it may say background processing is already brewing and the full activated scope is still being
  determined, but it must not present the first activation as the complete list and must not quote a
  first activation reason as if all other detectors were final. The full activation detection must
  continue, and Phase B must execute the final activated set once after that final detection result
  resolves.
- Early Phase A notice must fail closed to `all_within_budget` when any configured tool-hold cortex
  has an unowned direct-action scope on the current request. Fast notice is a latency optimization,
  not proof that all direct-action context has resolved. This guard affects the notice timing only;
  it does not disable the voice-mode speculative main run when
  `VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=true`.
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
- Runtime must persist Phase B status snapshots incrementally as cards change, not only after every
  cortex finishes. Writes may be coalesced to the latest full snapshot, but the authoritative final
  snapshot must drain older writes first so stale `activated`/`running` state cannot overwrite a
  terminal result. A process interruption after a visible card must therefore leave the latest
  successfully written state available to refresh/resume clients.
- If the primary main model fails before visible assistant text and runtime retries a configured
  fallback model, the original Phase B execution still belongs to the same originating assistant
  message. Runtime must not erase, restart, or orphan that in-flight background work; durable
  persistence and follow-up adjudication should wait for the final primary-or-fallback answer.
- If the final primary-or-fallback main path still leaves the canonical parent with no visible text
  while Phase B has substantive completed insights, runtime may promote the forced Phase B synthesis
  onto that otherwise empty parent. This is the only parent-text promotion exception: it must not
  rewrite a valid authored Phase A answer, must not run after the conversation has moved on, must not
  apply to scheduled `{NTA}` holds, and must preserve structured cortex parts on the same parent.
- If a user surface already received visible Phase A assistant text but the canonical text aggregator
  did not advance, runtime must repair the canonical parent from the emitted visible delta before
  Phase B adjudication. That repaired visible answer is treated as the authored Phase A answer; Phase B
  must fail closed and record a silent terminal decision rather than using deterministic fallback text
  that could contradict the already-delivered answer. This guard is structural and surface-neutral:
  it keys on stream/canonical mismatch evidence, not user wording, provider labels, agent names, or
  safety-policy text.
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
- Phase B silent success, empty output, skipped/no-insight completion, and generated follow-up
  decisions must be persisted as structured parent-message metadata. The decision record should
  carry safe lengths, hashes, surface, moved-on state, result, and suppression reason, not raw user
  text or raw background context. Surface pollers use this record to distinguish "nothing should be
  said" from "follow-up has not happened yet."
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
- Current shipped Anthropic Sonnet 4.5 built-ins that use thinking should not carry explicit
  `temperature` at all.
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
  runs such as `gpt-5`, dash-suffixed `gpt-5` reasoning variants, Viventium's configured GPT-5.6
  Sol/Terra runtime family, or `o1`/`o3`.
- All GPT-5.6 conscious/subconscious bags set `useResponsesApi: true`; OpenAI documents Responses as
  the required path for reasoning plus tools, while Chat Completions function tools are compatible
  only at effective reasoning `none`.
- The explicit effort map is part of the runtime contract: Sol/medium for the conscious agent,
  Sol/xhigh for Red Team and Deep Research, Sol/high for Strategic Planning, Terra/medium for
  Background Analysis, Confirmation Bias, Parietal Cortex, and Pattern Recognition, and Terra/low
  for MS365, Google, Emotional Resonance, and Viventium User Help.

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
  changing activation semantics. The per-attempt deadline must be enforced independently of the
  provider client's `AbortSignal` behavior; a provider promise that ignores cancellation must still
  yield to the next configured fallback.
- Source-owned activation policy prompts may be inline strings or registry `promptRef` objects.
  The nested LibreChat config schema must accept both, and runtime must resolve the object through
  the canonical prompt registry rather than coercing it to `[object Object]` or requiring validation
  bypass.
- Late background activation recovery is opt-in only. By default, if activation was not known before
  the main answer starts, runtime must not later surface new activation cards that the main model
  never saw in its Phase A context. The explicit `any_activated` / `any_activated_on_voice` notice
  modes are the narrow exception: Phase A has already been told generically that background
  detection is still active, and late activation cards must be marked as not seen by Phase A while
  Phase B waits for and executes the final activated set.
- On May 10, 2026, local QA reproduced a Groq outage while the operator's VPN was enabled. That was
  an environment/provider-reachability failure rather than activation-reasoning evidence. The
  current supported baseline is `groq / qwen/qwen3.6-27b`; the July 2026 change is instead driven
  by Scout's announced shutdown and a same-runtime classifier benchmark.
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
- On July 9, 2026, a Red Team prompt review found that the execution instructions described web
  search and deep decision-quality pressure, but the shipped Red Team tool/model bag did not include
  `web_search` or OpenAI `reasoning_effort: xhigh`. The supported fix is source-of-truth prompt/tool
  correction plus runtime-normalization tests proving upgrades and restarts preserve the intended
  adversarial reasoning substrate.
- Activation-provider benchmarks must use the same auth/runtime path as the product:
  - connected-account providers must be measured through their connected-account initializer path
  - standalone eval scripts must bootstrap Mongo/runtime dependencies before running activation
  - cooldown state must be cleared between benchmark scenarios when one real user is reused
- On May 27, 2026, a generic plural inbox request exposed two distinct failure classes:
  - unrestricted "check my inboxes" style prompts are productivity activation prompts, not runtime
    heuristics; both Google and MS365 cortices should activate unless the latest user message or
    immediate provider clarification restricts the provider
  - if a productivity cortex initializes with owned MCP tools and the primary execution model fails
    before any tool call or insight, the error must preserve activation/tool metadata and attempt
    the configured execution fallback. Tool, MCP, OAuth, and auth failures remain non-retryable by
    LLM fallback and must be surfaced as their real failure class.
  - a productivity cortex that reaches a terminal Phase B result without any current-run live tool
    call is not a successful inbox/workspace check. Runtime must surface a sanitized
    `no_live_tool_execution` limitation instead of treating empty output as a normal silent
    completion or allowing the follow-up to claim the provider was outside scope.
  - Google/MS365 source direct-action declarations describe same-scope behavior only when those MCPs
    are actually connected to the main agent. In the shipped local default, Viv main remains
    background-only for Google/MS365 and must not gain those MCP tools just to fix activation.
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
- On July 9, 2026, Scout's announced July 17 shutdown made that April selection non-shippable.
  The Prompt Workbench activation runner therefore became the release gate for the exact
  `BackgroundCortexService` classifier path across all 11 cortices. On the same pre-fix 20-case
  slice, Qwen 3.6 improved decision accuracy from Scout's `181/220` to `203/220`; after registry
  prompt repair, Qwen reached `624/627` on the first full serialized semantic pass with zero
  provider errors (`251 ms` p50, `320 ms` p95). The remaining three scope misses were promoted to
  contrastive prompt regressions. After restoring the documented material-commitment/comfort-
  rationalization Red Team scope with a recovery/rest negative control, a 59-case two-pass gate
  covered `1,298` decisions and all passed. Final fallback-parity review then added two more implicit
  comfort domains, dedicated self-care/changed-goal negatives, and stricter sibling boundaries for
  Red Team, Confirmation Bias, Strategic Planning, Google, and MS365. On the current 63-case bank,
  the latest full run covered `1,386` decisions (`63` cases x `11` cortices x `2`): `1,381`
  completed and all completed decisions passed with `100%` semantic required recall and activation
  precision, zero semantic false positives/negatives, and zero required/forbidden semantic
  inconsistencies. Five non-required decisions were honestly unavailable after exhausting the
  shared 2-second activation budget, so required recall remained `100%` while overall classifier
  completion was `99.64%` and release availability remains `PARTIAL`; latency was
  `287/1,457/1,775 ms` p50/p95/max. Four optional allowed-activation overlaps varied across the two
  repetitions and are reported separately from semantic errors. Direct Qwen and xAI probes for
  every discovered semantic leak passed after the prompt-boundary repairs. GPT-OSS 120B was retained only as comparison evidence:
  even after simplifying its
  schema it completed `191/220`, passed `186/220`, and produced 28 provider-side JSON validation
  failures, so it is not the primary.

### GlassHive Capability Broker Retirement Gate

Google Workspace, Microsoft 365, and Deep Research background agents must not be removed merely
because the GlassHive capability broker exists. Retirement is allowed only after a shadow-mode gate
proves:

- the broker is projected through GlassHive bootstrap without provider-token leakage
- two-user isolation and OAuth revoke/update cases pass
- content-read and write-confirmation policy is enforced for productivity providers
- paired legacy-background-agent vs broker-backed-worker evals meet the agreed numeric parity target
- a server-side kill switch can disable broker projection without code changes

This gate is the release/removal gate. The current local direct-execution baseline may disable
automatic main-agent activation for `Deep Research`, `MS365`, and `Google` while keeping those
specialist agents defined, testable, and re-enableable. That local soft-retirement proves the main
agent no longer routes live connected-account work through less capable automatic background
specialists; it does not by itself prove full broker parity, scheduled-grant renewal, or permanent
removal readiness.

## 2026-05-30 Background Activation Detection — Two Independent Modes (CANONICAL)

This section is the **source of truth** for whether Activation Detection blocks the Main Agent's first
answer, and how the speculative ("async") path behaves. Owner decisions, spelled out so there is no
ambiguity for anyone — across LibreChat chat, voice, and Telegram.

### Vocabulary
- **Activation Detection** — the Phase A classifier pass that decides which Background Cortices wake.
  It has a per-mode **time budget**.
- **Phase A** — the Main Agent's primary answer, produced *with* knowledge of which Background
  Cortices activated (when detection finished in time to inject it).
- **Phase B** — after the activated Background Cortices finish and surface insights, the Main Agent
  writes a **new, non-blocking follow-up turn**, aware of the Phase A answer so it does not repeat
  itself. **Phase B is unchanged in every mode and every case below.**
- Activated Background Cortices are **always shown** to the user (activation cards), in every mode.

### Two modes, fully independent
There are exactly two main-response orchestration modes — **voice-call mode** and **text mode**.
Each owns its **own async flag** and its **own detection budget**. **Neither flag affects the other
mode** (the voice-call flag never changes text behavior, and vice versa). Telegram always-voice is
text mode with audio delivery after the text answer, not voice-call mode.

| | Voice mode | Text mode |
| --- | --- | --- |
| async flag | `VIVENTIUM_VOICE_BACKGROUND_AGENT_DETECTION_ASYNC` | `VIVENTIUM_TEXT_BACKGROUND_AGENT_DETECTION_ASYNC` |
| detection budget | `VIVENTIUM_VOICE_PHASE_A_AWAIT_MS` = **690 ms** | `VIVENTIUM_TEXT_PHASE_A_AWAIT_MS` = **1300 ms** |
| async default | **ON** | **OFF** |

`VIVENTIUM_CORTEX_DETECT_TIMEOUT_MS` (default 2000 ms) is the **shared fallback** budget; a mode uses
it only when its own `*_PHASE_A_AWAIT_MS` is unset. `VIVENTIUM_CORTEX_SPECULATIVE_PARALLEL_DETECT` is
retained only as a **back-compat alias** for `VIVENTIUM_TEXT_BACKGROUND_AGENT_DETECTION_ASYNC`.
`VIVENTIUM_CORTEX_LATE_DETECT_TIMEOUT_MS` defaults to **4000 ms** and owns the existing non-blocking
recovery pass whenever the fast window has at least one detector timeout, including partial results.
It does not extend the conscious/main-answer wait. The recovery pass reuses the same activation
prompts, provider order, direct-action ownership gates, cards, Phase B execution, and persistence
pipeline, deduplicates fast-pass activations, and executes only newly recovered cortices.

### Async OFF — blocking detection with early-exit
1. Activation Detection runs **first**, blocking the Main Agent answer, up to the mode budget.
2. **Early-exit:** the moment *all* cortex detection results are in, detection returns immediately —
   it never burns the remaining budget. (Voice additionally releases on the *first* true activation
   via the notice-mode knob.)
3. The Main Agent produces **Phase A** with the activation result injected into its instructions.
4. If the fast pass returns partial or zero activations after a detector timeout, the non-blocking
   4000 ms late pass retries the same classifier/fallback contract; any new valid activation surfaces through
   cards and **Phase B** without delaying the Main Agent answer.

### Async ON — speculative parallel with "nevermind" cancel
1. The Main Agent answer **and** Activation Detection start **simultaneously**.
2. **Cortex activates within budget →** do the **"nevermind"** action on the speculative Main Agent
   answer: cancel/terminate it as if it never happened, then run **Phase A** — the Main Agent answer
   re-run *with* the Activation Detection result (which cortices activated) injected (the exact same
   injection async-OFF uses). This is only allowed when the implementation's streamed-state guard
   confirms no user-visible text or audio has been emitted yet. The 690 ms voice / 1300 ms text
   budgets are latency targets, not the safety proof; faster models can beat those budgets.
3. **No activation within budget** (zero activation, including the timeout case) **→** the speculative
   answer **stands** as Phase A. The whole detection wait was overlapped — this is the win.
4. **Budget expires before detection finishes →** the speculative answer **stands** as Phase A; any
   cortex that activates *late* still surfaces via **Phase B**.
5. Phase B is unchanged in every case above.

Why async ON is the smarter / default direction: on the common no-activation turn it removes the
entire detection wait, while still giving an activation-aware answer (via the redo) when a cortex
fires in time. The cost is a discarded speculative prefill on activation turns — a deliberate **speed
vs. cost** trade-off, which is why async stays a per-mode flag (token-cautious operators keep it off).

### QA isolation and contamination incident contract

A local browser-QA harness once selected the owner account, minted local QA auth, and submitted a
synthetic cortex prompt without an owner guard or mandatory cleanup. The synchronous Memory Agent
wrote the synthetic premise; a later independent memory pass re-promoted related context; and a real
schedule then combined that false premise with legitimate context and delivered a fabricated update.
This was not a cross-user leak, a prompt-text routing bug, or Telegram re-ingestion.

The durable prevention contract is:

- browser QA fails closed unless an explicit owner email is configured and refuses both a requested
  or resolved owner account;
- QA requests carry structured `viventiumQaRun` / `viventiumQaRunId` metadata and isolate saved
  memory, conversation recall, and feelings without inspecting prompt text or agent names;
- saved QA messages persist `metadata.viventium.qaRun=true` and `memoryEligible=false` so the batch
  hardener, recall corpus, and Meilisearch independently exclude them even if cleanup is interrupted;
- every harness runs Mongo and Meili cleanup in `finally`, scoped to the QA user and run ID; and
- owner and QA saved-memory/message/conversation counts must match their pre-run baseline after QA.

Any pre-cleanup backup from such an incident is an immutable forensic restore source, not a clean
runtime snapshot. Restoring it blindly can reintroduce contamination; a restore must sanitize the
known rows and rebuild conversation-recall vectors and search indexes before activation.

### Worked examples (text mode, budget 1300 ms)
- *Async OFF — "hello", no cortex:* detection returns ~600 ms (all results in) → Phase A starts at
  ~600 ms (early-exit; not the full 1300 ms).
- *Async ON — "hello", no cortex:* answer + detection start at 0 ms; detection returns ~600 ms with no
  activation → the already-streaming answer stands (~600 ms of wait removed).
- *Async ON — "summarize my last meeting", recall cortex activates at ~500 ms:* "nevermind" the
  speculative answer; re-run Phase A aware the recall cortex is engaged; the recall insight lands later
  via Phase B.
- *Async ON — detection slow (>1300 ms):* the speculative answer stands as Phase A; if the cortex
  activated late it surfaces via Phase B.

### Safety: direct-action tool-hold
Voice speculation stays enabled by default even when a configured/candidate Background Cortex
declares a **direct-action surface/scope** (a side-effecting tool it owns). The first answer should
not wait on tool-hold bookkeeping; side-effecting work and late evidence surface through Phase B or a
follow-up turn. Operators can restore the older fail-closed blocking behavior by setting
`VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=false`.

### Status (spec vs shipped — be honest)
- Config, clean per-mode naming, budgets (text 1300 / voice 690), and async-OFF early-exit:
  **shipped** 2026-05-30 (`scripts/viventium/config_compiler.py`, `getCortexDetectTimeoutMs`,
  `voicePhaseAPolicy.js`, env passthrough allowlist).
- Async-ON nevermind+redo: **shipped + live-verified 2026-05-30** via the streaming-preserving
  live-reuse approach — the main answer streams live under a dedicated abort signal (a parameterized
  `runAgents(messages, signalOverride)`), and on in-budget activation the speculative run is aborted
  only if no visible answer text has streamed yet; otherwise the speculative answer is committed and
  the activated cortices surface via Phase B. Live
  evidence on the main agent (text chat, `VIVENTIUM_TEXT_BACKGROUND_AGENT_DETECTION_ASYNC=true`):
  commit path ("yo") → clean single streamed answer, detection ran in parallel (the sync `Phase A
  complete` blocking log was absent); activation path ("priorities") → nevermind → 2 named activation
  cards + a cortex-aware Phase A answer, no error card.
- Gate detail: live `speculativeMode` must use the policy-safe `voicePhaseAPolicy.enabled`, not the
  raw requested flag. The requested flag records the operator preference; the enabled flag is the
  resolved runtime decision after direct-action/tool-hold gates. Ordinary voice turns use async ON by
  default, including configured tool-hold scopes, because
  `VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=true` is now the shipped default.
- **Voice async = ON** (owner target; the orchestration is shared agent-pipeline code, so voice uses
  the identical path with the 690ms budget + the TTFT guard protecting against a mid-TTS cancel). Text
  async default **OFF**.
- Residual / remaining checks: (a) a nevermind aborts the speculative run's in-flight MCP connections,
  producing benign "operation aborted" MCP log noise (same class as baseline; the redo re-establishes
  them); (b) the voice playground (TTS + abort) was not separately exercised — shared code is proven
  via text; (c) front-end "flow style" indicator and seam integration tests are follow-ups.

### Implementation design + the streaming constraint (for the live wiring)
Seam map (verified 2026-05-30): the agents chat path is always resumable — `req._resumableStreamId`
is set unconditionally and `res.json()` returns before generation, so the live per-token sink is
`GenerationJobManager.emitChunk(streamId, …)` (not `res.write`). The answer is persisted by mutating
`this.contentParts` in place (read back to build the saved message) and billed once from
`this.collectedUsage` in the run `finally`. The main run is the reusable `runAgents(messages)` closure
(`client.js`), invoked via `runWithAnthropicRecovery`. An isolated speculative run is constructable
with a fresh `createContentAggregator()` + fresh `collectedUsage` + a fresh
`getDefaultHandlers({ …, streamId: null })`.

**Streaming constraint (critical — why a naive orchestrator wiring is wrong):**
`runSpeculativeParallelMainRun` commits via `await specRunPromise; commit()` — it awaits the *full*
speculative answer, then delivers. Wired naively against an isolated buffer, that buffers the entire
answer and replays it at once, which **defeats token-by-token streaming** (async-ON answers would
appear all-at-once — a UX regression vs async-OFF, which streams live). The live wiring must therefore
preserve streaming. Two viable shapes, with a real trade-off:
1. **Live-reuse:** the speculative run streams to the real sink from the start (preserves streaming);
   on abort, the code must first verify the visible-stream state is still empty, then clear the empty
   `this.contentParts`/`this.collectedUsage` + inject + redo. Risk: run-lifecycle SSE events for the
   aborted run reach the client under the same `messageId`; needs an idempotency/suppress check.
2. **Isolated + go-live-on-commit:** the speculative run buffers only until the decision; on commit,
   flip the sink to live and let it continue streaming (do NOT await full completion). Cleaner SSE, but
   commit no longer maps to the vanilla orchestrator's await-then-deliver ordering.
A **streamed-state guard** is required: if a user-visible token/audio chunk already streamed when the
decision lands, do not cancel mid-stream, regardless of TTFT or budget. Commit that Phase A answer and
surface cortices via Phase B. This is especially important for voice TTS and for future fast voice
LLM routes, where a mid-audio "nevermind" would feel broken.

### Related model decisions (affect Main Agent / cortex latency)
- Main Agent text: `gpt-5.6-sol` with `reasoning_effort: medium` and Responses API. Background
  execution uses the Sol/Terra effort map above. Every text route falls back to
  `anthropic / claude-opus-4-8` when that auth path is available.
- Voice LLM remains `grok-4.3` with `reasoning_effort: none`. Its latency-preserving voice fallback
  is `gpt-5.6-terra` with `reasoning_effort: none`; the text fallback policy does not replace the
  explicit voice route.
- See `qa/modern-playground-voice/reports/2026-05-29-voice-chat-latency-rca-and-fixes.md` for the
  full evidence-based RCA (memory/recall/tool-mass/model-swap disproven as latency causes).
