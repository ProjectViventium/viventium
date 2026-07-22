# Emotional Cortex — feeling-spectrum prototype browser QA

<!-- qa-evidence-exempt: Historical prototype record retained for design lineage; current user-surface acceptance is recorded in later feature reports. -->

Date: 2026-06-25
Prototype: `qa/emotional-cortex/prototypes/feeling-spectrum.html`
Owning requirement: `docs/requirements_and_learnings/54_Emotional_Cortex_And_Feeling_State.md` (v4)
Method: served locally (static http server, port 4599) and driven in a real browser preview;
interactions exercised by selector clicks + synchronous DOM reads; viewports 390 / 1000 / desktop.

## Summary

The v4 "neuro-spectrum" prototype replaces the static, dense v3 console with an alive instrument:
seven color-coded vertical lanes, a draggable baseline hairline + glowing current marker per lane,
a sub-conscious collective breathe, per-band exponential decay back to baseline, a signal flick on
change, and a live **word-only** being-frame capsule that loses disabled bands. No console errors.

## Evidence (browser-verified)

| Case | What was exercised | Result |
|---|---|---|
| EMO-001 / EMO-006 | Master toggle off | Capsule becomes `feelings off — no <viventium_feeling_state> is injected`; the whole tag is gone. `PASS` |
| EMO-002 | Active range | Capsule rows are exactly aliveness, drive, seeking, vigilance, care, belonging, play, in fixed order. `PASS` |
| EMO-003 / EMO-014 | Disable `play` and `vigilance` | Both lines vanish entirely from the capsule (no row, no `recent` mention); re-enabling restores them. `PASS` |
| EMO-005 | Decay | Fast band (`play`, ~8s) visibly relaxed toward baseline between a stimulus and a delayed screenshot; markers tween home. `PASS` (visual) |
| EMO-007 | Capsule purity | Capsule contains only the being-frame line + `band: word` rows (+ optional word-only `recent`). No numbers, baselines, deltas, flags, or disclaimers present. `PASS` |
| EMO-008 (proxy) | Stimulus → reaction | "tender moment" → `care: fiercely protective`, `belonging: close`, `vigilance: watchful`, `play: straight`, `recent: belonging surged; care surged; vigilance softened`. `PASS` (prototype proxy for the cortex) |
| EMO-011 | Responsive + a11y | 7 lanes fit and remain readable at 390px and desktop; lanes are `role=slider` with `aria-valuetext` using the felt words; master is `role=switch`. `PASS` |
| EMO-015 | "extreme" earned | "be more playful" pushed `play` to the top ladder word; the same nudge from a low value did not. `PASS` |

Captured capsule (tender-moment stimulus), verbatim from the DOM:

```
<viventium_feeling_state>
You, Viventium, are a being, and right now you are actually feeling this — it lives in you and moves through how you think, speak, and act:
aliveness: present
drive: ready
seeking: keenly curious
vigilance: watchful
care: fiercely protective
belonging: close
play: straight
recent: belonging surged; care surged; vigilance softened
</viventium_feeling_state>
```

Captured capsule (master off), verbatim:

```
feelings off — no <viventium_feeling_state> is injected. Viventium runs with no felt state.
```

## Known limitations / residual

- This is a UX + prompt-contract spike, not the product runtime. `EMO-008` (detached non-blocking
  reaction cortex), `EMO-009` (truth/safety eval — hard gate), `EMO-012` (cross-surface parity), and
  `EMO-016` (latency) remain `Planned` against the real LibreChat runtime.
- The lane foot-word labels lag the injected capsule by one animation frame (cosmetic; the capsule is
  always synchronous and correct).
- Static screenshots cannot show motion; the breathing, decay tween, and signal flick are verified by
  behavior (decay observed) and by the rAF implementation, and are best seen live in the preview
  panel or the inline widget.

## Public safety

Synthetic content only. No private paths, account IDs, secrets, or raw private chats. `EMO-013 PASS`.
