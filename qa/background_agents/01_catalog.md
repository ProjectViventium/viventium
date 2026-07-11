# Background Agent Catalog

## Quick Matrix

| Agent | Agent ID | Execution Family | Activation Family | Primary Scope |
| --- | --- | --- | --- | --- |
| Background Analysis | `agent_viventium_background_analysis_95aeb3` | `openAI / gpt-5.6-terra / medium` | `groq / qwen/qwen3.6-27b` | blind spots, critical analysis |
| Confirmation Bias | `agent_viventium_confirmation_bias_95aeb3` | `openAI / gpt-5.6-terra / medium` | `groq / qwen/qwen3.6-27b` | overconfidence, unchecked assumptions |
| Red Team | `agent_viventium_red_team_95aeb3` | `openAI / gpt-5.6-sol / xhigh` | `groq / qwen/qwen3.6-27b` | challenge claims, evidence pressure |
| Deep Research | `agent_viventium_deep_research_95aeb3` | `openAI / gpt-5.6-sol / xhigh` | `groq / qwen/qwen3.6-27b` | explicit research and comparison requests |
| MS365 | `agent_viventium_online_tool_use_95aeb3` | `openAI / gpt-5.6-terra / low` | `groq / qwen/qwen3.6-27b` | `productivity_ms365` live Outlook/MS365 actions |
| Parietal Cortex | `agent_viventium_parietal_cortex_95aeb3` | `openAI / gpt-5.6-terra / medium` | `groq / qwen/qwen3.6-27b` | math, statistics, first-principles reasoning |
| Pattern Recognition | `agent_viventium_pattern_recognition_95aeb3` | `openAI / gpt-5.6-terra / medium` | `groq / qwen/qwen3.6-27b` | recurring loops and contradictions |
| Emotional Resonance | `agent_viventium_emotional_resonance_95aeb3` | `openAI / gpt-5.6-terra / low` | `groq / qwen/qwen3.6-27b` | emotional undercurrents and vulnerability |
| Strategic Planning | `agent_viventium_strategic_planning_95aeb3` | `openAI / gpt-5.6-sol / high` | `groq / qwen/qwen3.6-27b` | plans, sequencing, roadmaps |
| Viventium User Help | `agent_viventium_support_95aeb3` | `openAI / gpt-5.6-terra / low` | `groq / qwen/qwen3.6-27b` | in-product support and how-to help |
| Google | `agent_8Y1d7JNhpubtvzYz3hvEv` | `openAI / gpt-5.6-terra / low` | `groq / qwen/qwen3.6-27b` | `productivity_google_workspace` live Gmail/Drive actions |

## Notes

- The execution-family column is the launch-ready shipped baseline from source-of-truth.
- Every row uses Responses API and declares `anthropic / claude-opus-4-8` as its text fallback.
- The activation-family column is the shipped primary activation baseline.
- `Deep Research`, `MS365`, and `Google` remain shipped specialist agents, but the main Viventium
  agent disables their background activation in the GlassHive broker-first local baseline. Live
  web/productivity execution should use the main/direct GlassHive capability path unless this policy
  is explicitly re-enabled.
- Runtime fallbacks and live benchmark evidence are tracked in:
  - `qa/background_agents/activation_reliability_2026-04-12.md`
  - `docs/requirements_and_learnings/02_Background_Agents.md`
