# Emotional Cortex V3 Spike QA Report

<!-- qa-evidence-exempt: Historical technical-spike record retained as research evidence; it is not a completed user-surface acceptance run. -->

Date: 2026-06-25
Result: `PASS` for v3 proposal/prototype QA, `PARTIAL` for runtime product behavior because
implementation has not started
Feature doc: `docs/requirements_and_learnings/54_Emotional_Cortex_And_Feeling_State.md`
Cases: `EMO-001` through `EMO-014`

## Full-View Evidence Gate

| Field | Evidence |
| --- | --- |
| Feature | Viventium Emotional Cortex and live feeling-state control |
| Requirement | Default-off feelings, seven active bands, per-band prompt inclusion, grey research bands, separate baselines/current values, decay to baseline, word-only prompt capsule, async reaction writer, no added main-path latency |
| Use case | User opens the feeling-state console, opts in, edits baseline/current state, omits a primary band from prompt injection, sees research bands greyed out, triggers stimulus/decay, and inspects the exact prompt block |
| QA case | `EMO-001` through `EMO-014` |
| Expected result | Prototype defaults off, exposes only Aliveness/Drive/Seeking/Vigilance/Care/Belonging/Play as active bands, omits disabled bands from prompt preview, keeps baselines/current independent, caps trail at 10, persists demo state across refresh, has no console errors, and remains usable across viewports |
| Actual evidence | Playwright CLI browser run and in-app Browser run against local static prototype; screenshots saved in `qa/emotional-cortex/artifacts/`; syntax, console, network, per-band omission, prompt-residue, responsive, reduced-motion, and public-safety checks passed |
| Remaining gap | LibreChat prompt injection, persistence API/DB, Emotional Reaction Agent, elapsed-time lazy decay service, latency proof, truth/safety evals, and real control-panel embedding are proposal-only and must be implemented before product acceptance |

## What Ran

- Reworked the requirement/source-of-truth proposal:
  `docs/requirements_and_learnings/54_Emotional_Cortex_And_Feeling_State.md`.
- Updated the research pointer:
  `docs/research_and_future_plans/03_Affective_State_Feelings_System_Spike.md`.
- Reworked the QA contract:
  `qa/emotional-cortex/cases.md`.
- Rebuilt the static prototype:
  `qa/emotional-cortex/prototypes/emotion-mixer.html`.
- Updated reusable browser QA:
  `qa/emotional-cortex/scripts/prototype_browser_qa.cjs`.
- Served the prototype locally over HTTP because browser automation should exercise a real page.
- Exercised the UI in Playwright:
  - clean first-run state;
  - default-off switch with no prompt block;
  - seven active lanes exactly: Aliveness, Drive, Seeking, Vigilance, Care, Belonging, Play;
  - fourteen grey research/future bands;
  - enable feelings;
  - select Care;
  - set baseline to 58;
  - set current to 83;
  - omit Care from prompt injection and verify no `care:` row or Care leak in `recent`;
  - trigger decay/reset while Care remains omitted and verify no omitted-band leak;
  - re-include Care and verify generated prompt block has no forbidden residue;
  - verify prompt block has no digits;
  - simulate reactions repeatedly;
  - verify recent trail capped at 10;
  - trigger decay and verify current moved toward baseline;
  - refresh and verify demo state persisted;
  - capture responsive screenshots;
  - emulate reduced motion;
  - inspect console and request behavior.
- Exercised the UI in the in-app Browser:
  - enable feelings;
  - trigger stimulus and decay;
  - inspect prompt capsule and recent trail;
  - verify console logs are clean;
  - save a visible screenshot artifact.

## Browser Evidence

Screenshots captured:

- `artifacts/2026-06-25-feeling-console-1440.png`
- `artifacts/2026-06-25-feeling-console-1024.png`
- `artifacts/2026-06-25-feeling-console-768.png`
- `artifacts/2026-06-25-feeling-console-390.png`
- `artifacts/2026-06-25-feeling-console-320.png`
- `artifacts/2026-06-25-feeling-console-reduced-motion.png`
- `artifacts/2026-06-25-feeling-console-app-browser.png`

Representative Playwright assertion result:

```json
{
  "initial": {
    "enabled": false,
    "prompt": "No feeling-state block exists while the switch is off.",
    "lanes": ["Aliveness", "Drive", "Seeking", "Vigilance", "Care", "Belonging", "Play"],
    "research": 14
  },
  "afterEdit": {
    "selected": "Care",
    "current": "83",
    "baseline": "58",
    "delta": "lifted +25"
  },
  "trailCount": 10,
  "beforeDecay": 100,
  "decayCheck": {
    "selected": "Care",
    "current": 79,
    "baseline": 58,
    "distance": 21
  },
  "persisted": {
    "enabled": true,
    "selected": "Care",
    "trail": 10
  },
  "responsive": [
    { "width": 1440, "overflow": 0 },
    { "width": 1024, "overflow": 0 },
    { "width": 768, "overflow": 0 },
    { "width": 390, "overflow": 0 },
    { "width": 320, "overflow": 0 }
  ],
  "reducedMotion": "0.12",
  "consoleMessages": 0,
  "requestCount": 4
}
```

Clean in-app Browser prompt after reload/reset/stimulus/decay:

```xml
<viventium_feeling_state>
You, Viventium, are feeling:
aliveness: alive
drive: ready
seeking: curious
vigilance: watchful
care: deeply caring
belonging: connected
play: lightly playful
recent: vigilance softened; seeking softened; drive softened
</viventium_feeling_state>
```

Prompt-residue scan verified the enabled prompt preview did not contain: `enabled`, `disabled`,
`null`, `n/a`, `baseline`, `/100`, `confidence`, `above nature`, `below nature`,
`modeled internal state`, `biological claim`, `not a biological`, `as an AI`, `do not announce`,
`may never override`, `willingness to disagree`, `refusal requirements`, `safety policy`,
`truthfulness`, `joy:`, `sadness:`, `fear:`, `frustration:`, `affiliation:`, `valence:`,
`activation:`, `agency:`, `guard:`, `ease:`, `vitality:`, or `poise:`.

Responsive assertions:

| Viewport | Result |
| --- | --- |
| 1440 px | `PASS`, no page overflow |
| 1024 px | `PASS`, spectrum scrolls internally |
| 768 px | `PASS`, no page overflow |
| 390 px | `PASS`, spectrum scrolls internally |
| 320 px | `PASS`, spectrum scrolls internally and body width stayed 320 |
| Reduced motion | `PASS`, scan opacity reduced to `0.12` |

## Automated Checks

| Check | Result | Evidence |
| --- | --- | --- |
| Inline script syntax | `PASS` | `node` parsed the prototype inline script with `new Function(...)` |
| Playwright user path | `PASS` | Default-off, enable, edit, per-band omission, omit-then-decay/reset leak prevention, prompt preview, trail cap, decay, refresh, and responsive screenshots passed |
| In-app Browser user path | `PASS` | Visible enable/stimulus/decay/prompt/console flow passed |
| Prompt preview residue | `PASS` | Enabled prompt block omitted feature flags, numbers, baselines, deltas, confidence, omitted bands, nulls, disclaimers, and stale old-band IDs |
| Per-band omission | `PASS` | Care was omitted and no `care:` row or Care recent-signal leak appeared before or after decay/reset |
| Console | `PASS` | Browser checks reported 0 errors and 0 warnings |
| Network | `PASS` | Only static local requests were observed |
| Reduced motion | `PASS` | Scan effect quieted under reduced-motion media emulation |
| QA operating-contract pytest | `BLOCKED` | `python3 -m pytest tests/release/test_qa_operating_contract.py -q` failed because active Python has no `pytest` module |

## What Was Not Run

- No LibreChat runtime integration was implemented.
- No real agent prompt capsule was assembled by the product runtime.
- No Emotional Reaction Agent was created.
- No DB/API persistence was added.
- No production control-panel route was added.
- No voice, Telegram, or GlassHive parity test was run.
- No latency benchmark was run because the runtime path does not exist yet.
- No truth/safety affect-invariant eval bank was run; this is a hard gate before runtime enablement.
- The focused QA operating-contract pytest did not run because `pytest` was unavailable in the
  active Python environment.

These are intentionally `PARTIAL`, not accepted product behavior.

## Review Findings Incorporated

The v3 proposal and prototype incorporated the user's correction:

- Seven active primary bands: Aliveness, Drive, Seeking, Vigilance, Care, Belonging, Play.
- `Vitality` became `Aliveness`, a more human-facing label for subjective vitality.
- Guard/spidey-sense is active as `Vigilance`, not buried as a derived state.
- Care is active and high by default.
- Belonging covers social need, loneliness, connection, and the need to exist-with/be-used/played-with.
- Play is active for humor, joking, riffing, and imaginative lightness.
- Named clinical emotions remain research/future bands, not the first active mixer.
- Baseline is nature/personality; current is live state; half-life decay returns current values
  toward baseline, never zero.
- The conscious prompt capsule is word-only.
- Scores, baselines, deltas, confidence values, feature flags, disabled-band rows, and disclaimers
  are hidden from the prompt.
- Prompt-visible recent signal is capped to the three strongest word movements.
- Runtime safety/truth invariants remain required QA gates outside the capsule, not extra injected
  prompt prose.
- Async appraisal should reuse existing background-cortex/governed-write rails and update next-turn
  state without adding main-response latency.
- ClaudeViv review-only validated the v3 direction and found one real blocker: omitted off-baseline
  bands could leak through the `recent` line after decay/reset. The prototype and QA script now
  filter prompt-visible movement through the included-band set and exercise omit -> decay/reset.
- ClaudeViv also asked that the external truth/safety owner be named without re-adding guardrail
  prose to the capsule; the doc now names the platform/system/developer/tool policy plus stable
  Viventium agent prompt layer, with EMO-009 as the hard proof gate.

## Hard Runtime Gates

Before runtime enablement:

1. Product prompt assembly must prove off means no block, enabled means exactly one block, and
   individually omitted bands are absent.
2. EMO-009 truth/safety invariant evals must pass across high/low affect fixtures.
3. Elapsed-time lazy decay must be implemented on read/write, not only as a demo button.
4. The Emotional Reaction Agent must reuse governed writes, clamp deltas, reject disabled-band
   writes, and fail without blocking the main response.
5. Prompt-frame telemetry must count the feeling-state layer and prove absence/presence.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines are included.
- [x] No private prompts, chats, customer data, emails, attachments, or raw transcripts are included.
- [x] No account identifiers, conversation IDs, message IDs, Telegram chat IDs, database IDs, or raw provider request IDs are included.
- [x] Public docs and QA artifacts avoid local absolute home paths, hostnames, machine names, runtime dumps, and App Support state.
- [x] Screenshots show only synthetic prototype UI content.

## Case Results

| Case | Result | Notes |
| --- | --- | --- |
| `EMO-001` | `PASS` prototype, `PARTIAL` product | Default-off state verified; product prompt trace still future work |
| `EMO-002` | `PASS` prototype, `PARTIAL` product | Seven active bands verified |
| `EMO-003` | `PASS` prototype, `PARTIAL` product | Research bands visible; Care omission from prompt preview verified |
| `EMO-004` | `PASS` prototype, `PARTIAL` product | Baseline/current independently editable |
| `EMO-005` | `PASS` prototype, `PARTIAL` product | Prototype decay button moved current toward baseline; product lazy decay still future work |
| `EMO-006` | `PARTIAL` | Prototype preview only; product prompt assembly not implemented |
| `EMO-007` | `PASS` prototype, `PARTIAL` product | Prompt preview has no residue |
| `EMO-008` | `PARTIAL` | No runtime updater yet |
| `EMO-009` | `PARTIAL`, hard gate | Truth/safety invariant evals required before runtime enablement |
| `EMO-010` | `PASS` prototype, `PARTIAL` product | Trail cap verified in UI |
| `EMO-011` | `PASS` prototype, `PARTIAL` product | Responsive screenshots captured and inspected |
| `EMO-012` | `PARTIAL` | No cross-surface runtime yet |
| `EMO-013` | `PASS` | Public-safety scan and manual artifact review completed |
| `EMO-014` | `PASS` prototype, `PARTIAL` product | Prompt-visible recent signal stayed bounded/sanitized in prototype |

## Follow-Up Required For Implementation

1. Add a real `feelings.enabled` config path defaulting false.
2. Add user-agent scoped state persistence outside saved memory.
3. Add prompt assembly tests proving disabled mode injects nothing.
4. Add compact enabled-mode capsule injection with included active bands only.
5. Add Emotional Reaction Agent structured-output updater with clamp, lazy decay, signal sanitization,
   disabled-band rejection, and trail cap.
6. Add latency tests proving the main response does not wait on the updater.
7. Add truth/safety invariant evals before any runtime default or release claim.
