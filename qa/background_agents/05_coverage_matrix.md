# Background Agent Coverage Matrix

## Current Matrix

| Agent | Primary Positive Coverage | Negative / Boundary Coverage | Runtime Notes |
| --- | --- | --- | --- |
| Background Analysis | `ACT-01`, `ACT-07` | `ACT-12` | Known to over-activate on some broad analysis prompts; benchmark tracks spillover explicitly. |
| Confirmation Bias | `ACT-02` | `ACT-12` | Must stay distinct from generic analysis and emotional prompts. |
| Red Team | `ACT-01`, `ACT-02` | `ACT-12` | Challenge pressure should not fire on pure tool/capability requests. |
| Deep Research | `ACT-03` | `ACT-12` | Explicit research asks only; general comparison chat is not enough. |
| MS365 | `ACT-09`, `ACT-11` | `ACT-12` | Provider-only clarification is a required regression case. |
| Parietal Cortex | `ACT-05` | `ACT-12` | Math/statistics only. |
| Pattern Recognition | `ACT-08` | `ACT-12` | Requires multi-turn behavioral span or explicit pattern ask. |
| Emotional Resonance | `ACT-06` | `ACT-12` | Distinguish emotional disclosure from analytical strategy talk. |
| Strategic Planning | `ACT-07` | `ACT-12` | Planning/roadmap scope only. |
| Viventium User Help | `ACT-04` | `ACT-12` | Must not fire on generic factual or research requests. |
| Google | `ACT-10`, `ACT-11` | `ACT-12` | Concrete Google Workspace action required. |

## Interpretation

- Coverage in this matrix is activation coverage, not full execution QA.
- Productivity agents require separate execution and connected-account verification after activation.
- Provider benchmark evidence for the current shipped activation family is recorded in:
  - `qa/background_agents/activation_reliability_2026-04-12.md`
