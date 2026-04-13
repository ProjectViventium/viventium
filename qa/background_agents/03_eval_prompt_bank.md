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
