# Background Agent Signoff Manifest

This manifest records the minimum reviewed scenarios that must remain true for the shipped
background-agent roster.

## Roster-wide activation release gate

- `ACT-36` covers every listed cortex through the exact runtime classifier path, including positive,
  sibling-negative, latest-turn, strict-output, injection, multilingual, typo, and combined-intent
  cases.
- Run the full two-pass `background_activation_routing` gate before every release while the primary
  classifier is a preview model, and after any activation prompt, model, provider, fallback, parser,
  or classifier-runtime change.
- A completed-call semantic pass does not erase unavailable evidence. Record completion rate,
  end-to-end required recall, semantic recall, precision, availability flaps, and latency separately.

### 1. Background Analysis

- Activation signoff scenarios: `ACT-01`, `ACT-07`
- Reviewer focus:
  - critical blind-spot analysis activates without relying on runtime heuristics

### 2. Confirmation Bias

- Activation signoff scenarios: `ACT-02`
- Reviewer focus:
  - overconfidence and unsupported certainty activate this cortex specifically

### 3. Red Team

- Activation signoff scenarios: `ACT-01`, `ACT-02`, `ACT-35`
- Reviewer focus:
  - challenge pressure remains available on risky claims and plans
  - Socratic/no-bullshit/premortem decision-method asks activate only when attached to a concrete
    claim, plan, or decision

### 4. Deep Research

- Activation signoff scenarios: `ACT-03`
- Reviewer focus:
  - explicit deep-dive requests still activate the research cortex

### 5. MS365

- Activation signoff scenarios: `ACT-09`, `ACT-11`
- Reviewer focus:
  - provider-only clarification still activates the MS365 cortex
  - mixed-provider inbox requests still allow parallel productivity activation

### 6. Parietal Cortex

- Activation signoff scenarios: `ACT-05`
- Reviewer focus:
  - mathematical/statistical tasks still route cleanly to parietal reasoning

### 7. Pattern Recognition

- Activation signoff scenarios: `ACT-08`
- Reviewer focus:
  - multi-turn recurring-behavior prompts still activate pattern detection

### 8. Emotional Resonance

- Activation signoff scenarios: `ACT-06`
- Reviewer focus:
  - direct emotional disclosure still activates the emotional cortex

### 9. Strategic Planning

- Activation signoff scenarios: `ACT-07`
- Reviewer focus:
  - roadmap and sequencing asks still activate strategic planning

### 10. Viventium User Help

- Activation signoff scenarios: `ACT-04`
- Reviewer focus:
  - in-product help requests still route to the support cortex

### 11. Google

- Activation signoff scenarios: `ACT-10`, `ACT-11`
- Reviewer focus:
  - Gmail / Google Workspace actions still activate the Google cortex
