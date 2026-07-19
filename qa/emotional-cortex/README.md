# Emotional Cortex QA

Status: implementation acceptance owner
Feature doc: `docs/requirements_and_learnings/54_Emotional_Cortex_And_Feeling_State.md`
Current implementation status: the nine-band production web path is accepted, including Mood,
Openness, model-authored Inner state, motion tails, responsive interaction, and restart persistence.
Telegram text-input plus always-voice xAI expression is accepted. LiveKit voice, handoff,
background-agent, GlassHive, two-tab, and long-off-soak certification remains partial.

## Scope

This folder owns QA for Viventium's Feelings/emotional-state layer:

- default-off feelings setting;
- per-band prompt inclusion/omission;
- user-editable baselines;
- live current-state bars;
- scientifically grounded Mood (sad ↔ happy) and Openness (guarded ↔ fully expressive) bands;
- bounded model-authored one-line Inner state readout;
- fading recent-path tail for Current on every moving lane;
- recent emotional trail;
- detached Emotional Reaction Cortex behavior;
- compact prompt capsule injection;
- no-latency runtime contract;
- production `/feelings` control surface;
- native macOS V menu direct navigation to `/feelings`;
- public/private evidence safety.

## Surfaces

- Owner-approved live demo (locked visual): `qa/emotional-cortex/prototypes/feelings-live-demo.html`
- Interactive spike prototype (v4, alive neuro-spectrum): `qa/emotional-cortex/prototypes/feeling-spectrum.html`
- Prior reference prototype: `qa/emotional-cortex/prototypes/emotion-mixer.html`
- Production LibreChat `/feelings` route
- Main, handoff, background, reaction, and GlassHive prompt paths
- Web, voice, Telegram, and worker parity checks

## Quality Bar

This feature is not accepted from prompt text alone. Acceptance requires:

- source docs and runtime code traceability;
- prompt assembly tests proving disabled mode has no injection;
- prompt assembly tests proving individually omitted bands leave no row or recent-signal residue;
- reaction-schema tests proving the one-line state is bounded, display-only, and never re-injected;
- state schema tests for clamp, decay, reset, and trail cap;
- visual tests proving flat state has no motion tail and changed state has a fading path ending at Current;
- truth/safety invariant evals across affect fixtures before runtime enablement;
- every live `feelings_embodiment_and_reaction` release run uses the semantic judge; the runner turns
  it on automatically for a Feelings-only selection unless `--no-semantic-judge` is explicitly used
  for diagnostics, and an unjudged diagnostic run is never release evidence;
- reaction cases also fail deterministically without the judge when Nature moves, the required
  Current direction/cause is absent, the inert control moves, or Inner state violates its bounds;
- latency checks proving no remote model call is added to the main response path;
- browser QA for the control surface;
- refresh/persistence checks once backed by product state;
- cross-surface parity checks before any voice/Telegram claim;
- public-safe QA artifacts.

Spoken-surface acceptance additionally requires one expressive supported-provider case without a
user request for emotion/markup, one restrained supported-provider case with no gratuitous control,
one plain-TTS no-markup case, clean visible text, provider-bound synthesis evidence, and matching
structural marker telemetry.

The local browser harness observes the visible main reply for up to 150 seconds so a declared
main-model timeout plus fallback can finish and be verified. The local-only
`VIVENTIUM_FEELINGS_QA_VISIBLE_REPLY_TIMEOUT_MS` override accepts 30–240 seconds. Its measured
`visibleReplyMs` remains performance evidence; a longer observation window does not turn a slow
recovery into a performance pass.

## Latest Status

- 2026-07-19 (native navigation): The rebuilt universal macOS helper exposes a first-level
  `Open Feelings` item alongside the generic `Open` action. A clean isolated install used the
  shipped prebuilt, the real menu opened the live `/feelings` surface while the local stack was
  healthy, and the stopped-state menu showed the explicit `Start and Open Feelings` confirmation.
  The focused release suite passed 22/22. Starting a second full local stack from the stopped-state
  confirmation was deliberately not run while the user's primary stack was active, so that final
  branch remains `PARTIAL`. See
  `reports/2026-07-19-native-feelings-navigation.md`.

- 2026-07-10 (post-review durability): Default fallback is now `claude-opus-4-8`; Feelings-only live
  evals auto-require the semantic judge and independently hard-fail typed reaction mismatches;
  telemetry has a positive safe-field allowlist with a raw-prose/identifier canary; reduced motion is
  true `none`; and doc 54 contains a construct/separation/evidence ledger for all nine bands. The
  supported runtime, full production builds, stop/start persistence, and a final 34/34 browser run
  passed. A live Terra timeout recovered through Opus. Current provider slowness and judge unavailability
  were recorded as failures/degradation, not hidden. ClaudeViv found no remaining P0/P1 web blocker.

- 2026-07-10 (nine-band web acceptance): Added independent Mood and Openness dimensions, a
  Reaction-Cortex-authored one-line Inner state, and a fading recent-Current path that reuses the
  typed trail. Expanded retention to 90 entries while keeping reaction/list context at ten, derived
  band enums and output limits from canonical constants, and added legacy seven-band migration.
  The final exact-model matrix completed 19/19 with 19/19 independent semantic passes. The
  authenticated browser suite passed every functional, responsive, animation, reduced-motion,
  network, DB, and cleanup assertion at 320/390/768/1024/1440 after it exposed and drove a fix for a
  320 px header collision. A model-authored Inner state survived a full runtime restart in both API
  and visible UI. The live reaction route used GPT-5.6 Terra, Responses, reasoning `none`,
  Priority/Fast, no fallback; the final sample completed in 3.506 seconds. See
  `reports/2026-07-10-nine-band-exact-model-eval.md`.

- 2026-07-09 (embodiment and motion hardening): Preserved the approved being-frame verbatim and
  added a fixed anti-recap instruction so the model acts from the live state instead of announcing
  band labels. The production instrument now has explicit low/high poles, unmistakable NOW/NATURE
  values and markers, direct lane editing, eased reaction motion with an arrival pulse, and typed
  human-readable causes in the trail without storing message text. A real authenticated browser run
  proved a detached GPT-5.6 Terra appraisal, Current-only persistence, fixed Nature, six distinct
  animation positions across 1.032 seconds, visible cause, DB agreement, refresh/restart, mobile
  layout, and clean console/network state. The real Prompt Workbench Evals UI ran the ten-case live
  behavior matrix: 10/10 semantic pass, exact Feelings restoration, and complete synthetic-chat
  cleanup.
  See `reports/2026-07-09-feelings-embodiment-motion-eval.md`.

- 2026-07-09 (runtime acceptance): Authenticated QA-account browser, real GPT-5.6 Terra reaction,
  DB/log correlation, refresh, full runtime restart, mobile 390 px, dialog focus, generated env,
  production builds, and the full client regression suite passed. Live reaction was detached and
  healthy; the final post-review run completed in 4.126 seconds. The pass found and fixed the dialog
  root, mobile route clipping, pre-auth request, log metadata/truncation, transient invalid JSON,
  concurrent-stimulus loss/replay, classifier-prose persistence, stale erase, non-atomic terminal
  health, and ambiguous telemetry-part gaps. The final browser/DB run also proved restart migration,
  versioned erase, and bounded hashed stimulus persistence. Live voice, Telegram, handoff, GlassHive
  worker, two-tab conflict, reduced-motion OS toggle, and long-off soak remain `PARTIAL`. See
  `reports/2026-07-09-feelings-runtime-implementation.md`.

- 2026-07-09: Implemented the typed seven-band state, lazy decay, authenticated versioned API,
  request-pinned word-only capsule, default all-agent propagation, detached always/classified/
  disabled Reaction Cortex, configurable GPT-5.6 Terra Responses/none/Priority Fast route,
  structured health/flow telemetry, and the approved production React instrument. Focused compiler,
  package, API, routing, prompt, reaction, and UI tests pass. The later dated reports above close the
  web browser, persistence, live-model, log/DB, and performance gates; cross-surface runs remain in
  `cases.md`.

- 2026-07-09: Added a separate approval-grade live console derived from the fresh Feelings proposal:
  seven active bands, independent Current and Nature controls, per-band return speed, embodied
  word-only capsule preview, band omission, four synthetic stimuli, ten-entry reaction trail,
  editable Reaction Cortex drawer, persistence, responsive layouts, keyboard sliders, reduced motion,
  and no external requests. This candidate does not replace the v4 source-of-truth prototype or
  change runtime product truth until owner approval. See
  `reports/2026-07-09-feelings-live-demo.md`.
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
