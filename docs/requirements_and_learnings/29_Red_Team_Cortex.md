# Red Team Cortex (Mistake Detection)

## Purpose
This document is the single source of truth for the Viventium Red Team cortex:
- requirements,
- activation design,
- technical configuration,
- deployment and validation.

## Product Requirement
- Add a background cortex that proactively identifies:
  - unsupported claims,
  - weak assumptions,
  - viability gaps in plans/timelines,
  - comfort-zone rationalization that blocks execution.
- The cortex must be direct, evidence-first, and action-oriented.
- It should not activate for casual chat, pure emotional support, or routine questions.

## Locked Decisions
- Red Team is a **background cortex** attached to the main Viventium agent.
- Support/help remains a **separate selectable agent**; no support background cortex in this release.
- Use currently configured/available model IDs in cloud (no new provider/model rollout required).

## Configuration

### Main Agent Activation Entry
File:
- `viventium_v0_4/LibreChat/viventium/source_of_truth/cloud.viventium-agents.yaml`

Added under `main.background_cortices`:
- `agent_id: agent_viventium_red_team_95aeb3`
- `activation.enabled: true`
- `activation.confidence_threshold: 0.6`
- `activation.cooldown_ms: 45000`
- `activation.max_history: 6`
- Activation prompt that explicitly distinguishes:
  - evidence/viability checks (activate),
  - casual/emotional/simple asks (do not activate).

### Red Team Agent Definition
Same file:
- `id: agent_viventium_red_team_95aeb3`
- Name: `Red Team`
- Description: evidence-first mistake detection
- Tools: web search + sequential-thinking
- Instructions enforce:
  - explicit claim/evidence/verdict/action output,
  - no fabricated sources,
  - no fake capabilities (email/calendar/files access claims).

## Output Contract
When activated, the cortex response should be structured as:
- Claim
- Evidence
- Verdict (`SUPPORTED` / `UNSUPPORTED` / `UNVERIFIABLE`)
- Action Required

This format keeps it concise and decision-useful.

## Edge Cases
- If evidence is incomplete or conflicting, verdict must be `UNVERIFIABLE` (not hallucinated certainty).
- If user is in emotional support mode, do not activate Red Team even if claims are present.
- If another cortex already covers a concern (e.g., broad confirmation bias), Red Team should stay focused on evidence and viability.

## Related Agent: Viventium Support
Also added in this release:
- `agent_viventium_support_95aeb3` as a selectable model entry.
- Strict instruction to never mention implementation internals.
- Escalation line to the private support channel managed outside this public repo.

Files:
- `viventium_v0_4/LibreChat/viventium/source_of_truth/cloud.viventium-agents.yaml`
- `viventium_v0_4/LibreChat/viventium/source_of_truth/cloud.librechat.yaml`

## Deployment Procedure (Safe)
From `viventium_v0_4/LibreChat`:
```bash
node scripts/viventium-sync-agents.js pull --env=cloud
node scripts/viventium-sync-agents.js push --prompts-only --dry-run --env=cloud
node scripts/viventium-sync-agents.js push --prompts-only --env=cloud
```

## Validation Checklist
- Red Team activates on plan/timeline/claim-heavy prompts.
- Red Team remains quiet for casual or emotional-only conversation.
- Output includes claim/evidence/verdict/action format.
- Support agent appears in model selector and follows anti-internals instruction.
