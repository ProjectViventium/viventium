# Affective State Feelings System Spike

Status: superseded on 2026-06-25

This early research spike was superseded by the Emotional Cortex proposal (now v4):

- Requirement/source of truth:
  `docs/requirements_and_learnings/54_Emotional_Cortex_And_Feeling_State.md`
- QA owner:
  `qa/emotional-cortex/`
- Current prototype (browser-verified):
  `qa/emotional-cortex/prototypes/feeling-spectrum.html`
  (`emotion-mixer.html` is retained as a prior reference only)

The superseding proposal replaces the earlier continuous-core/derived-bars experiment and the
intermediate five-band draft with a seven-band living drive system: aliveness, drive, seeking,
vigilance, care, belonging, and play. It also tightens the prompt contract: feelings disabled means
no `<viventium_feeling_state>` block exists, individually omitted bands are absent from both rows
and recent-signal text, and the live capsule carries no feature flags, numbers, baselines, deltas,
confidence values, runtime disclaimers, or policy reminders.
