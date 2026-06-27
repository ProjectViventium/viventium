# Emotional Cortex QA

Status: spike QA owner created 2026-06-25 (v4 rewrite same day)
Feature doc: `docs/requirements_and_learnings/54_Emotional_Cortex_And_Feeling_State.md` (v4)
Current implementation status: proposal and interactive prototype only; runtime product feature not yet implemented.

## Scope

This folder owns QA for Viventium's proposed feelings/emotional-state layer:

- default-off feelings setting;
- per-band prompt inclusion/omission;
- user-editable baselines;
- live current-state bars;
- recent emotional trail;
- Emotional Reaction Agent behavior;
- compact prompt capsule injection;
- no-latency runtime contract;
- control panel UI and later LibreChat embedding;
- public/private evidence safety.

## Surfaces

- Interactive spike prototype (v4, alive neuro-spectrum): `qa/emotional-cortex/prototypes/feeling-spectrum.html`
- Prior reference prototype: `qa/emotional-cortex/prototypes/emotion-mixer.html`
- Future LibreChat/Viventium control panel
- Future agent prompt assembly path
- Future Emotional Reaction Agent background path
- Future web, voice, Telegram, and worker parity checks

## Quality Bar

This feature is not accepted from prompt text alone. Acceptance requires:

- source docs and runtime code traceability;
- prompt assembly tests proving disabled mode has no injection;
- prompt assembly tests proving individually omitted bands leave no row or recent-signal residue;
- state schema tests for clamp, decay, reset, and trail cap;
- truth/safety invariant evals across affect fixtures before runtime enablement;
- latency checks proving no remote model call is added to the main response path;
- browser QA for the control surface;
- refresh/persistence checks once backed by product state;
- cross-surface parity checks before any voice/Telegram claim;
- public-safe QA artifacts.

## Latest Status

- 2026-06-25: V3 spike proposal, seven-band feeling console prototype, per-band omission proof, and
  browser QA completed. Runtime implementation is not shipped, so prompt assembly, persistence,
  updater, latency, truth/safety evals, and cross-surface cases remain `PARTIAL` until implementation
  exists.
- 2026-06-25 (v4): Re-grounded the seven bands in affective neuroscience with per-band citations
  (Panksepp SEEKING/CARE/PLAY/PANIC-GRIEF, BIS/BAS, subjective vitality, need-to-belong, social pain),
  resolved the baseline/current spectrum model, tightened the capsule to a minimal words-only
  being-frame (no numbers, no disclaimers, presence == enabled, disabled == absent), and shipped a new
  alive prototype `feeling-spectrum.html` (breathing lanes, per-band decay, draggable baseline +
  current, signal flick, live capsule preview). Browser-verified: see
  `reports/2026-06-25-feeling-spectrum-prototype.md`. Added cases `EMO-015` (word-ladder/"extreme"
  earned) and `EMO-016` (no added critical-path latency).
