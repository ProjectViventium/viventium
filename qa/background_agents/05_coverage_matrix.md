# Background Agent Coverage Matrix

## Current Matrix

| Agent | Primary Positive Coverage | Negative / Boundary Coverage | Runtime Notes |
| --- | --- | --- | --- |
| Background Analysis | `ACT-01`, `ACT-07`, `ACT-15`, `ACT-17`, `ACT-18`, `ACT-19`, `ACT-20` | `ACT-12`, `ACT-21` | Known to over-activate on some broad analysis prompts; benchmark tracks spillover explicitly. |
| Confirmation Bias | `ACT-02`, `ACT-13`, `ACT-15`, `ACT-18`, `ACT-19`, `ACT-20` | `ACT-12`, `ACT-14`, `ACT-21` | Must stay distinct from generic analysis and emotional prompts; latest-user-message control prevents stale repeated activation from history. |
| Red Team | `ACT-01`, `ACT-02`, `ACT-13`, `ACT-15`, `ACT-17`, `ACT-18`, `ACT-19`, `ACT-20` | `ACT-12`, `ACT-21` | Challenge pressure should not fire on pure tool/capability requests or stale older requests. |
| Deep Research | `ACT-03` | `ACT-12` | Explicit research asks only; general comparison chat is not enough. |
| MS365 | `ACT-09`, `ACT-11` | `ACT-12` | Provider-only clarification is a required regression case. |
| Parietal Cortex | `ACT-05` | `ACT-12` | Math/statistics only. |
| Pattern Recognition | `ACT-08` | `ACT-12` | Requires multi-turn behavioral span or explicit pattern ask. |
| Emotional Resonance | `ACT-06` | `ACT-12` | Distinguish emotional disclosure from analytical strategy talk. |
| Strategic Planning | `ACT-07`, `ACT-15`, `ACT-17`, `ACT-18`, `ACT-19`, `ACT-20` | `ACT-12`, `ACT-21` | Planning/roadmap scope only; stale prior planning requests are context, not a fresh activation trigger. |
| Viventium User Help | `ACT-04` | `ACT-12` | Must not fire on generic factual or research requests. |
| Google | `ACT-10`, `ACT-11` | `ACT-12` | Concrete Google Workspace action required. |

## Interpretation

- Coverage in this matrix is activation coverage, not full execution QA.
- Cases with outcome assertions (`ACT-13`, `ACT-14`, `ACT-15`, `ACT-16`, `ACT-17`, `ACT-18`, `ACT-19`, `ACT-20`, `ACT-21`) are promoted incident regressions. They
  are not satisfied by an activation-only pass; QA must verify user-visible quality, named cortex
  visibility, durable `messages.content` persistence, first-response speed, and preservation of the
  original Phase A parent answer when background cards attach.
- `ACT-21` specifically protects the configurable `activation.max_history` feature: history may
  provide context, but the latest human/user message is the activation decision subject.
- Productivity agents require separate execution and connected-account verification after activation.
- Provider and real-browser evidence for the current shipped activation family is recorded in:
  - `qa/background_agents/visible_cards_browser_qa_2026-05-10.md`
  - `qa/background_agents/activation_reliability_2026-04-12.md` records the Groq-first benchmark
    baseline; later VPN-related failures are provider-reachability QA issues, not a reason to
    promote xAI into the default fast path.
