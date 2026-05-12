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
