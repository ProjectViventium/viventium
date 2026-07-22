# 2026-06-25 Heart Prompt Live Sync

<!-- qa-evidence-exempt: Historical prompt-sync record retained for lineage; it is not a complete browser and persistence acceptance report. -->

## Scope

Surgically update the main Viventium prompt so warmth/playfulness is less compressed while preserving
truthfulness, brevity, and factual grounding. This report covers public-safe source/live sync evidence
only; private account identifiers, raw conversations, and raw memory values are omitted.

## Requirement Links

- `docs/requirements_and_learnings/01_Key_Principles.md`
- `docs/requirements_and_learnings/49_Prompt_Architecture_and_Token_Efficiency.md`
- `qa/prompt-architecture/cases.md` (`PROMPT-001`, `PROMPT-002`)

## Changes Verified

- `viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/main/voice_style.md`
  - Removed the pressure line that framed lower-value acknowledgement as wasted reader energy.
  - Replaced the one-breath cap with moment-sensitive brevity.
- `viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/main/core_behaviors.md`
  - Narrowed anti-sycophancy from "Don't play along" to "Don't fake agreement."
- `viventium_v0_4/LibreChat/viventium/source_of_truth/prompts/main/memory_policy.md`
  - Added time gaps to the "do not guess" grounding rule while preserving grounded timestamp/memory
    awareness.
- `viventium_v0_4/LibreChat/viventium/source_of_truth/local.viventium-agents.yaml`
  - Updated the resolved local main-agent instructions with the same three text changes.

## Live Sync Evidence

- Pulled the current live local agent bundle before pushing.
- Compared live vs tracked source and observed pre-existing live/source drift across several agents.
- Built a live-derived prompt bundle so existing live tools, model/provider fields, conversation
  starters, background cortices, and handoff agents were preserved.
- Dry-run used `--prompts-only` and `--agent-ids` scoped to the main agent.
- Non-dry-run push used `--prompts-only --compare-reviewed --agent-ids` scoped to the main agent.
- Post-pull comparison of live vs the live-derived source showed zero diffs for the reviewed sync
  fields.

## Local Checks Run

- Prompt registry parse smoke for the three edited prompt markdown files: `PASS`.
- Resolved local main prompt string guard: `PASS`.
- Source/live string guard for removed/new wording: `PASS`.
- Live-derived bundle comparison after post-pull: `PASS`.
- Git whitespace check for the four edited files: `PASS`.
- Runtime restart/reload: `PASS`; the stack was restarted after prompt sync and returned to ready
  state.
- Post-restart live prompt string check: `PASS`; the live bundle still contained the refined
  wording and none of the removed pressure strings.
- ClaudeViv review-only second opinion: `PASS`; confirmed the live-derived sync and cleanup
  no-delete stance, challenged the time-gap wording, and prompted the grounded timestamp/memory
  refinement.

## Cleanup Inventory

Read-only sanitized DB inventory was run to scope possible QA/test/probe cleanup:

- Conversations, messages, saved memories, and cleanup candidates were counted.
- Exact aggregate counts were intentionally redacted from the public report because they describe a
  private local instance rather than public product behavior.

No conversation, message, recall, or saved-memory rows were mutated. The inventory is evidence for a
future classified cleanup proposal, not deletion approval.

## Not Run / Gaps

- `pytest` release tests were not run because pytest is not installed in the available local Python
  runtimes.
- No live browser chat/model-turn eval was run, intentionally: sending synthetic prompts through the
  main account would add more production chat junk before the snapshot harness exists.
- Full old-vs-new exact-model evals remain pending. They should run from a private snapshot harness
  plus public synthetic cases before further prompt tuning or cleanup mutation.

## Verdict

`PARTIAL/PASS-SAFETY`.

The source and live prompt sync behaved correctly and preserved live settings. Full behavioral
acceptance remains gated on the snapshot/eval harness and a non-destructive cleanup plan.
