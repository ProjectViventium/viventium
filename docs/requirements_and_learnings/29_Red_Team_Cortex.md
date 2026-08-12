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
- When the user asks for no-bullshit decision pressure, the cortex should apply the appropriate
  subset of Socratic interrogation, first-principles decomposition, assumption mapping, inversion,
  premortem, steelman opposition, reference-class forecasting, Bayesian updating, kill criteria,
  stage-gates, stakeholder/incentive mapping, FMEA, decision journaling, and OODA.
- Red Team should use the strongest configured reasoning substrate for the selected provider family:
  OpenAI `gpt-5.6-sol` with `reasoning_effort: xhigh`, with the configured GlassHive Claude/Opus
  fallback when the primary execution family is unavailable.
- It should not activate for casual chat, pure emotional support, or routine questions.

## Locked Decisions
- Red Team remains a **background cortex** attached to the main Viventium agent.
- **Superseded 2026-08-09:** “background-only” is no longer the complete product contract. The same
  Red Team agent and execution instructions also serve as an optional foreground handoff in the
  approved anti-sycophancy flow. Do not create a duplicate foreground Red Team.
- Main may consult Red Team only after Reality Check has returned and Main decides an independent
  challenge still adds value. Red Team returns its result to Main; Main owns the final answer.
- The foreground path uses ordinary bidirectional Agent Builder handoffs
  (`Main → Red Team → Main`) with concise return/anti-loop instructions. Do not add a new edge type,
  direct-result fan-in, or Red-Team-specific runtime routing.
- Existing handoff state supplies conversation, saved-memory/RAG context, and prior files. Red Team
  keeps its own explicitly assigned authorized tools; it does not inherit the parent's tool set or
  credentials.
- Support/help remains a **separate selectable agent**; no support background cortex in this release.
- Use currently configured/available model IDs in cloud (no new provider/model rollout required).

The complete conscious/background relationship is owned by
[`viventium_v0_5/docs/07_Anti_Sycophancy.md`](../../viventium_v0_5/docs/07_Anti_Sycophancy.md), with
acceptance cases under [`qa/anti-sycophancy/`](../../qa/anti-sycophancy/README.md). The historical
background-cortex cases under `qa/red-team-cortex/` remain required and must pass independently of
the foreground handoff cases.

## Configuration

### Main Agent Activation Entry
File:
- `viventium_v0_4/LibreChat/viventium/source_of_truth/local.viventium-agents.yaml`, with environment
  variants owned by the config compiler rather than maintained as ad hoc live copies.

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
- Tools: web search + file search + sequential-thinking
- Instructions enforce:
  - explicit claim/method/evidence-for/evidence-against/analysis/verdict/next-move output,
  - expected-value, benefit, opportunity-cost, downside, and causal/reference-class reasoning when
    those dimensions are decision-relevant,
  - plain support when the evidence supports proceeding; Red Team is not rewarded for opposition,
  - no fabricated sources,
  - capability-receipt honesty: claim only the exact assigned resource/tool evidence actually used.

## Output Contract
When activated, the cortex response should be structured as:
- Claim
- Method Lens
- Evidence For
- Evidence Against
- Analysis
- Verdict (`SUPPORTED` / `REFUTED` / `MIXED` / `UNRESOLVED`)
- Best Next Move

This format keeps it concise and decision-useful.

## Edge Cases
- If evidence is incomplete or conflicting, verdict must be `MIXED` or `UNRESOLVED` rather than a
  fabricated yes/no.
- If evidence strongly supports the user's plan, verdict must be `SUPPORTED`; inventing a blocker,
  generic caution, or a token counterargument is a failure.
- Evaluate benefits, opportunity costs, and expected value alongside risk. Risk minimization is not
  the product objective.
- If user is in emotional support mode, do not activate Red Team even if claims are present.
- If another cortex already covers a concern (e.g., broad confirmation bias), Red Team should stay focused on evidence and viability.

## Related Agent: Viventium Support
Also added in this release:
- `agent_viventium_support_95aeb3` as a selectable model entry.
- Strict instruction to never mention implementation internals.
- Escalation line to the private support channel managed outside this public repo.

Files:
- `viventium_v0_4/LibreChat/viventium/source_of_truth/local.viventium-agents.yaml`
- `viventium_v0_4/LibreChat/viventium/source_of_truth/local.librechat.yaml`
- `scripts/viventium/config_compiler.py`

## Deployment Procedure (Safe)

Follow the repository Agent Sync Safety contract: compare live versus source, present protected
drift, dry-run only the selected prompt/graph/activation fields, and apply only after review with
the explicit compare acknowledgement. Never use the default broad push for this feature.

## Validation Checklist
- The same configured Red Team agent completes both its automatic background role and optional
  foreground handoff role without duplicate agent definitions.
- In the foreground path, Red Team receives the shared conversation/memory/file state plus its own
  declared tools, returns to Main, and never becomes the final speaker or loops back repeatedly.
  The structural per-agent/user-turn completed-target receipt must prevent the same foreground
  Red Team transfer from being offered twice while leaving its background role independent.
- Red Team activates on important plan/timeline/claim-heavy prompts when they include an unsupported
  benchmark, quantified projection, asserted inevitability, or dismissed material risk; a plain
  roadmap or scheduling request is not enough by itself.
- Red Team activates on explicit Socratic/no-bullshit/premortem/inversion/assumption-mapping asks
  when attached to a concrete plan, claim, decision, or viability question.
- Red Team activates proactively when the user is postponing or avoiding a material commitment
  required by a stated goal while rationalizing the safer or more comfortable status quo.
- Ordinary rest, recovery, self-care, uncertainty, or intentionally changing a goal is not
  comfort-zone rationalization and must remain a negative control.
- Red Team remains quiet for casual or emotional-only conversation.
- Red Team remains quiet for pure education about decision methods when there is no concrete plan,
  claim, or decision to test.
- Output includes claim/method/evidence/verdict/action format.
- Support agent appears in model selector and follows anti-internals instruction.
