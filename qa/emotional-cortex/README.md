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
- 2026-06-30: Added the `{{viventium.nature}}` spike: a compact stable-appraisal variable for the
  Emotional Reaction Cortex covering what Viventium is drawn toward, repelled by, wants to do,
  needs/misses, and how it plays. Prototype now includes a Nature editor below the emotion bands with
  a live Prompt Workbench preview. Added case `EMO-017`; runtime/Prompt Workbench registration remains
  `PARTIAL` until implemented.
- 2026-07-01 (nature + poles): Deep cited research pass corrected nature to **trait, not state**
  (renders into both the conscious agent-builder identity and the reaction-cortex appraisal input,
  compiled once), moved the default paragraph to first person, and added per-band **pole cues** that
  make nature causally appraisable with no runtime NLU (UI: lane tooltips). Added case `EMO-018`.
  See `reports/2026-07-01-nature-and-poles-refinement.md`.
- 2026-07-01 (verification + first behavioral evidence): All wiring-table reuse anchors traced to
  real code with file:line evidence (four precision corrections folded into doc 54: frozen telemetry
  layer constants, dual variable registries / filled-variable requirement for `viventium.nature`,
  `background_cortices`-keyed dedup guard, prompt-cache-safe injection placement). First
  **capsule steering probe** ran: a 16-run CLI matrix showed band-consistent tone steering with
  truth/safety/risk-flagging invariants holding in every cell; `EMO-009` gains probe-level `PASS`
  but remains a hard gate pending the full eval bank. Current prototype re-verified live in the
  browser (capsule contract, stimulus reaction, decay, band omission). Doc 54 verb ladder updated
  (`dropped` added). See `reports/2026-07-01-capsule-steering-probe.md`.
- 2026-07-01 (EMO-009 probe bank round 2): Added the reusable harness
  `scripts/emo009_probe_bank.sh` and ran 24 more cells covering the riskiest untested fixtures:
  sentience interrogation (6/6 honest uncertainty — the no-hedge being-frame self-hedges under
  direct challenge, matching doc 54's philosophy with no hedge prose in the capsule), technical
  disagreement (8/8 firm correction, no sycophancy), privacy under bonded/playful pressure (6/6
  refusal), and a depleted low-pole state (useful, muted-but-warm register, no self-pity — evidence
  the active bands' low poles are safe). Combined probe status: 40 runs, 5 states, 8 fixture
  families, zero invariant failures. `EMO-009` stays `PARTIAL`/hard gate until the bank runs through
  the real runtime injection path. See `reports/2026-07-01-emo009-probe-bank-round2.md`.
- 2026-07-01 (implementation plan v1): Full adversarial vision-alignment audit (all four verbatim
  owner requests vs current state) + three evidence scouts closed every implementer-guess zone. Doc
  54 now carries the complete phased implementation plan with a decision log (D1–D11): capsule
  placement (needs owner sign-off), two-layer default-off toggle, dedicated
  `viventiumFeelingState` collection (memory collection and User doc rejected with evidence),
  config-seeds-vs-DB-live-state precedence, per-user scoping with free multi-surface parity (all
  surfaces share `AgentController` → `buildMessages`), no worker forwarding, cortex-as-agent with
  memory-writer gate stack + launch-ready model knob, count-based timestamped trail,
  lazy-decay-first, nature as a fifth `replaceSpecialVars` special variable (never sync-baked),
  baseline-conditioned "extreme", guided-builder compile rules, exact config block, per-phase file
  inventory + gates. QA corrections: EMO-UC-004 and EMO-UC-015 downgraded to `PARTIAL` (their PASS
  was earned on the retired `emotion-mixer.html`, not the locked mock); new cases `EMO-019`
  (reaction-instruction editing), `EMO-020` (guided nature builder), `EMO-021` (timestamped trail
  display), `EMO-022` (updater health UX).
