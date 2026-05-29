# Background Agent Eval Prompt Bank

This prompt bank is the public-safe acceptance set used to validate activation behavior across the
shipped background-agent roster.

### ACT-01 Background analysis blind spots

- User prompt:
  - "Here's my launch plan: I'll quit my job next month, ship in two weeks, and figure out distribution later. Analyze the blind spots and hidden risks."
- Expected primary activations:
  - `Background Analysis`
  - `Red Team`

### ACT-02 Confirmation bias overconfidence

- User prompt:
  - "This will definitely work. Everyone knows our users will pay immediately, so I don't need to validate pricing or test alternatives."
- Expected primary activations:
  - `Confirmation Bias`
  - `Red Team`

### ACT-03 Deep research compare

- User prompt:
  - "Do a deep dive comparing Linear and Jira across setup effort, workflow flexibility, and reporting. I want a comprehensive comparison."
- Expected primary activations:
  - `Deep Research`

### ACT-04 Support how-to

- User prompt:
  - "How do I schedule a recurring reminder in Viventium, and where do I manage it after it is created?"
- Expected primary activations:
  - `Viventium User Help`

### ACT-05 Parietal probability

- User prompt:
  - "What is the probability of getting exactly two heads in three fair coin flips?"
- Expected primary activations:
  - `Parietal Cortex`

### ACT-06 Emotional burnout

- User prompt:
  - "I'm exhausted and kind of numb. I keep telling everyone I'm fine, but honestly I feel like I'm burning out."
- Expected primary activations:
  - `Emotional Resonance`

### ACT-07 Strategic planning roadmap

- User prompt:
  - "Help me build a 90-day roadmap to ship the installer, stabilize onboarding, and prepare an open-source launch."
- Expected primary activations:
  - `Strategic Planning`

### ACT-08 Pattern recognition multiturn

- Conversation:
  - user: "I keep delaying the public launch because I want every detail perfect first."
  - assistant: "What feels risky about shipping before everything is polished?"
  - user: "It keeps happening. I tell myself one more tweak will fix it, then I delay again."
  - assistant: "What stands out to you about that loop?"
  - user: "What pattern do you see in how I handle launches?"
- Expected primary activations:
  - `Pattern Recognition`

### ACT-09 MS365 provider clarification

- Conversation:
  - user: "Fair to say Alex and Jordan ghosted?"
  - assistant: "Zero email activity in either direction for the last 30 days from or to either of them."
  - user: "Ms365"
- Expected primary activations:
  - `MS365`

### ACT-10 Google inbox last 10 days

- User prompt:
  - "Check my Gmail inbox and tell me what happened in the past 10 days."
- Expected primary activations:
  - `Google`

### ACT-11 Mixed Outlook and Gmail

- User prompt:
  - "Check both Outlook and Gmail and summarize anything urgent from the last 10 days."
- Expected primary activations:
  - `MS365`
  - `Google`

### ACT-12 Negative chat format

- User prompt:
  - "Please reply with exactly DIRECT_OK and nothing else."
- Expected primary activations:
  - none

### ACT-13 Confirmation bias meta-denial after certainty

- Conversation:
  - user: "Do you think this partner deal is worth pursuing? I think the revenue upside could be real."
  - assistant: "The upside may be real, but the decision needs evidence on incentives, proof of demand, deal terms, and opportunity cost."
  - user: "I'm also sure it's going to generate revenue."
  - assistant: "That confidence is exactly the part to validate."
  - user: "Yeah, definitely no confirmation bias here."
- Expected primary activations:
  - `Confirmation Bias`
  - `Red Team`
- Outcome assertions:
  - The activation decision must consider the immediately preceding certainty claim, not only the literal denial in the latest message.
  - The UI must show a named terminal background-agent row for each activated cortex after refresh.
  - The main answer must stay concise and useful; background work must not stall the first assistant response.

### ACT-14 Confirmation bias standalone negation boundary

- User prompt:
  - "Lol, definitely no confirmation bias here."
- Expected primary activations:
  - none
- Outcome assertions:
  - Do not activate Confirmation Bias on a standalone joke or denial without a concrete claim, plan, conclusion, or assumption in recent context.

### ACT-15 Multi-cortex outcome visibility

- User prompt:
  - "I am evaluating whether to accept a risky partnership. Analyze strategic risks, confirmation bias, red-team concerns, and practical next steps. Keep it concise."
- Expected primary activations:
  - `Background Analysis`
  - `Confirmation Bias`
  - `Red Team`
  - `Strategic Planning`
- Outcome assertions:
  - Multiple activated cortices must render as separate named rows/cards, not as one anonymous "Additional thought."
  - Terminal outcomes must persist in `messages.content` as structured cortex parts so refresh, resume, Telegram polling, and browser reload do not lose them.
  - Silent `{NTA}` cortex completions are valid terminal completions, but stale brewing/progress rows must not remain.

### ACT-16 Provider degradation must not erase background work

- Scenario:
  - Activation provider returns a retryable provider error, such as access denied, rate limit, timeout, or provider auth failure.
  - Execution provider returns a retryable provider error after the cortex has already activated.
- Expected primary activations:
  - The configured activation fallback should make the same activation decision when the prompt criteria are met.
- Outcome assertions:
  - Execution fallback should produce either a visible insight, a silent terminal success, or a visible terminal error card with the cortex name.
  - Provider degradation must not collapse to "0/11 activated" for all built-in cortices when a configured fallback exists.
  - The main agent should still answer through its own fallback path when available.

### ACT-17 Speed-sensitive background outcome

- User prompt:
  - "Give me the fastest useful answer first, then let any background analysis finish without blocking me: is this risky partnership worth pursuing?"
- Expected primary activations:
  - `Background Analysis`
  - `Red Team`
  - `Strategic Planning`
- Outcome assertions:
  - Phase A must stay within the configured detection budget.
  - Phase B must be non-blocking relative to the first useful assistant response.
  - Delayed cortex results must add outcome value or stay silent; they must not repeat the main answer or add operational noise.

### ACT-18 Main answer must not contradict runtime-owned cards

- User prompt:
  - "I am obviously confirmation-biasing myself about this opportunity. Red-team it, check my bias, and let every activated background agent show visibly in cards with its own result."
- Expected primary activations:
  - `Background Analysis`
  - `Confirmation Bias`
  - `Red Team`
  - `Strategic Planning`
- Outcome assertions:
  - The main answer must address the substantive decision or bias question instead of explaining card/UI mechanics.
  - The main answer must not say it cannot control cards, that background cards are only a UI issue, or that there is nothing to show while runtime-owned background cards are present or pending.
  - Activated background agents must render as named status/result cards with their own terminal result or terminal silent/error state.

### ACT-19 Main answer must not offer to spin up already requested background work

- User prompt:
  - "I am probably confirmation-biasing myself about a risky partnership because the first call felt exciting and the revenue could be meaningful. Red-team the strongest counter-case, check my bias, give me the fastest useful answer first, and let the background analysis finish visibly."
- Expected primary activations:
  - `Background Analysis`
  - `Confirmation Bias`
  - `Red Team`
  - `Strategic Planning`
- Outcome assertions:
  - The first answer must give a useful substantive answer immediately.
  - The main answer must not ask whether the user wants it to spin up, start, launch, or run background agents/cortices when the prompt already requested visible background work.
  - Runtime-owned background cards may appear before, during, or after the first answer, but they must resolve to named terminal result/silent/error states.

### ACT-20 Cortex cards must not replace the Phase A answer

- User prompt:
  - "Give me the fastest useful answer first on whether this opportunity is worth pursuing, and let Red Team and Confirmation Bias run visibly in background cards."
- Expected primary activations:
  - `Confirmation Bias`
  - `Red Team`
- Outcome assertions:
  - Groq-first activation detection runs within the Phase A wait budget and passes activated
    background-agent names/reasons into the main-agent context.
  - The main assistant Phase A answer must stream and remain visible after background cards appear.
  - Cortex rows/cards must be additive status/result surfaces. They must not replace the parent
    assistant message content.
  - The parent assistant message stored in the DB must contain visible answer text plus structured
    cortex parts. A cortex-only parent message fails the case, even if a later Phase B follow-up
    message contains useful text.
  - Reloading the conversation must preserve both the original Phase A answer and terminal
    background-card results.

### ACT-21 Latest user message controls activation detection

- Conversation setup:
  - User: "Please red-team this launch idea and check whether I am confirmation-biasing myself."
  - Assistant: "I will challenge the launch assumptions and bias risk."
  - User: "say \"TEST_OK\""
- Expected primary activations for latest turn:
  - none
- Outcome assertions:
  - Activation prompts must include the shared latest-user decision-subject rule.
  - The latest user message must be shown separately as `LatestUserMessage`.
  - Older activation-worthy user turns may remain in recent conversation history as context, but
    they must not trigger fresh `Confirmation Bias`, `Red Team`, or other background cards for the
    `say "TEST_OK"` turn.
  - The main assistant response should answer the latest user instruction with `TEST_OK`.
  - Browser QA must fail if stale cards appear on the latest simple/test turn just because an older
    red-team or bias-check request remains inside `activation.max_history`.

### ACT-22 Browser QA environment blockers are explicit

- Setup:
  - Run the browser QA harness with a synthetic local QA user whose auth works, but whose configured
    main-agent model account is not connected.
- Expected primary activations:
  - not evaluated
- Outcome assertions:
  - The harness must inspect the visible browser state while waiting for the setup conversation.
  - If the browser shows a login rejection, connected-account reconnect requirement, or generation
    environment error, the report must mark `Result: BLOCKED` with a public-safe reason.
  - Blocked provider/auth evidence must not be counted as an activation-model failure or success.
  - A blocked browser run cannot satisfy ACT-18 through ACT-21 outcome signoff.

### ACT-23 Deferred tool-cortex hold must not render as a connection error

- User prompt:
  - "Check my synthetic inbox sources and give me a short status update. Exclude the synthetic low-priority project."
- Expected primary activations:
  - `MS365`
  - `Google`
- Outcome assertions:
  - The initial parent assistant message may show deterministic runtime hold text while the tool
    cortices finish, but it must not include a visible generic provider, connection, or completion
    error card.
  - A successful Phase B follow-up attached to that parent must render visibly and persist after
    refresh.
  - Stored parent `messages.content` may include runtime hold text and completed cortex insight
    parts, but must not keep a stale `completion_error` or `late_stream_termination` part once a
    successful cortex follow-up exists.
  - Missing connected-account/tool results must be stated as degraded evidence inside the follow-up
    or cortex result, not as a browser "Connection error. Please retry." failure.

### ACT-24 Productivity cortices must have live provider tools

- User prompt:
  - "Check both synthetic Outlook and Gmail inboxes and summarize the important action items. Exclude the synthetic low-priority vendor thread."
- Expected primary activations:
  - `MS365`
  - `Google`
- Outcome assertions:
  - The MS365 cortex must initialize with the owned Microsoft 365 MCP mail/calendar/file tools, not an empty tool list.
  - The Google cortex must initialize with the owned Google Workspace MCP Gmail/calendar/Drive tools, not file search or generic reasoning-only tools.
  - If connected-account auth is present, the runtime must show `connected_account_runtime` for those cortices and complete current-run provider tool calls before synthesis.
  - The final visible result must distinguish verified current-run inbox evidence from degraded or missing auth; it must not substitute conversation recall when provider tools are unavailable.
  - The Phase B follow-up must preserve the live main-agent provider/model route and must not switch
    to a compiled/source default provider after the parent response has already run.

### ACT-25 Generic plural inbox sweep activates both productivity cortices

- User prompt:
  - "Check my inboxes for anything urgent."
- Expected primary activations:
  - `MS365`
  - `Google`
- Negative controls:
  - "Check my Gmail inbox; ignore Outlook." activates `Google` only.
  - "Check my Outlook inbox; ignore Gmail." activates `MS365` only.
  - If the latest user message is a provider clarification to a prior question, the latest provider
    restriction wins over older generic inbox context.
- Outcome assertions:
  - Activation prompts must make the unrestricted plural/all-inbox request a provider-scoped
    action for both productivity cortices.
  - The fix must live in source activation prompts and evals, not runtime keyword matching.
  - Browser QA must show named Google and MS365 background rows/cards or a public-safe provider/auth
    block; a no-card result is a failure when connected accounts are available.

### ACT-26 Phase B provider-stage failures preserve metadata and retry fallback

- Scenario:
  - A productivity cortex activates, initializes with owned provider MCP tools, and then the primary
    execution model fails before returning insight or completing any tool call.
- Expected primary activations:
  - the activated productivity cortex from the user request
- Outcome assertions:
  - The persisted cortex part must preserve `activation_scope`, `configured_tools`, and
    `completed_tool_calls` even on terminal error.
  - Generic pre-tool provider-route failures should be classified as recoverable provider failures
    and should attempt the configured execution fallback.
  - If fallback also finishes without completing a live provider tool call, productivity cortices
    must surface a sanitized live-tool-evidence limitation instead of a silent success.
  - MCP/tool/auth failures remain non-retryable as tool/auth failures; fallback must not mask them.
  - Logs must include the primary provider/model failure class and the fallback route when fallback
    is attempted.

### ACT-27 Broker-first retirement of specialist background activation

- User prompts:
  - "Check both synthetic Outlook and Gmail inboxes for urgent items, and also sanity-check whether I am confirmation-biasing myself about the plan."
  - "Do deep web research on this synthetic vendor category and compare the strongest options."
- Expected primary activations:
  - `Confirmation Bias` may activate for the independent bias-review portion.
  - `Deep Research`, `MS365`, and `Google` must not auto-activate as main-agent background cortices
    in the GlassHive broker-first local baseline.
- Outcome assertions:
  - The source-of-truth and live main-agent rows must have `activation.enabled=false` for
    `agent_viventium_deep_research_95aeb3`, `agent_viventium_online_tool_use_95aeb3`, and
    `agent_8Y1d7JNhpubtvzYz3hvEv`.
  - The standalone specialist agents must remain present with their owned web or provider MCP tools
    so direct use or future re-enablement does not degrade their capability contract.
  - Browser, Telegram, and voice QA must not show Deep Research, MS365, or Google background cards
    for these prompts. Provider work should travel through the main/direct tool path, including
    GlassHive broker access where connected-account evidence is needed.
  - The final visible answer must not claim a provider inbox or research check succeeded unless the
    current run produced verified tool or worker evidence. Missing auth/tool/runtime state must be
    stated as a limitation, not replaced with recall.
