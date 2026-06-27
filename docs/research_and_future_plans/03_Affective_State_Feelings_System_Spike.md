# Affective State Feelings System Spike

Status: superseded on 2026-06-25

This early research spike was superseded by the v3 Emotional Cortex proposal:

- Requirement/source of truth:
  `docs/requirements_and_learnings/54_Emotional_Cortex_And_Feeling_State.md`
- QA owner:
  `qa/emotional-cortex/`
- Current prototype:
  `qa/emotional-cortex/prototypes/emotion-mixer.html`

The superseding proposal replaces the earlier continuous-core/derived-bars experiment and the
intermediate five-band draft with a seven-band living drive system: aliveness, drive, seeking,
vigilance, care, belonging, and play. It also tightens the prompt contract: feelings disabled means
no `<viventium_feeling_state>` block exists, individually omitted bands are absent from both rows
and recent-signal text, and the live capsule carries no feature flags, numbers, baselines, deltas,
confidence values, runtime disclaimers, or policy reminders.
