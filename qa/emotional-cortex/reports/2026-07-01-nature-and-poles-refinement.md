# Emotional Cortex — nature variable + band poles refinement

<!-- qa-evidence-exempt: Historical design-refinement record retained for lineage; current visible acceptance is owned by later feature reports. -->

Date: 2026-07-01
Prototype: `qa/emotional-cortex/prototypes/feeling-spectrum.html`
Owning requirement: `docs/requirements_and_learnings/54_Emotional_Cortex_And_Feeling_State.md` (v4)
Builds on: `reports/2026-06-30-nature-variable-prototype.md` (Codex's first `{{viventium.nature}}` pass)
Method: served locally (port 4599), driven in the browser preview; synchronous DOM reads + screenshot.

## What changed

Extended the `{{viventium.nature}}` design with a deep, cited research pass (SDT, Schwartz values,
appraisal theory, approach-avoidance temperament, regulatory focus, control theory) and closed two
gaps in the prior pass:

1. **Placement corrected.** Nature is now **trait, not state**, and renders into **both** the conscious
   agent-builder identity (primary — a being knows its own nature; steers even with feelings off) and
   the reaction-cortex appraisal input — compiled once so they cannot drift. (Prior pass filed it as
   "subconscious appraiser by default.")
2. **Band poles added** (the owner's "keywords at the top/bottom limits"): each band ships low/high
   pole cues that make nature *causal* — "dislikes laziness → drive/aliveness react" — with **no
   runtime NLU** (cues are model-facing appraiser context, not code). Surfaced in the UI as lane
   tooltips.
3. **First-person default paragraph** (was third-person), which reads correctly as "my nature".

The template stays minimal: five load-bearing slots (drawn-to / repelled-by / wants-to / needs-misses
/ play-style), each cited, with the science for cutting autonomy, regulatory-focus, the Schwartz
19-value list, per-Panksepp-system slots, and any guardrail slot.

## Evidence (browser-verified)

| Case | What was exercised | Result |
|---|---|---|
| EMO-017 | Nature default + preview | Default is first-person ("I'm drawn to clarity, honest curiosity, and things built well…"). Preview labels it `agent-builder instructions: my / viventium's nature: {{viventium.nature}}` → `renders (identity + reaction cortex): <paragraph>`. `PASS` |
| EMO-017 | Capsule purity | With feelings on, `<viventium_feeling_state>` shows only the being-frame line + word-only bands; nature text does not appear. `PASS` |
| EMO-018 | Pole-cue tooltip | Drive lane `title` = `Drive — up: a goal worth finishing, raised stakes, push to completion, being counted on · down: coasting, stalling, low-effort, waiting to be told`. `PASS` |
| EMO-001 | Default-off preserved | Master starts off (`feelings off`); capsule shows the off message; no tag. `PASS` |
| EMO-011 | Layout | Nature editor sits cleanly below the rack (two-column: editor + preview); no overflow at desktop; collapses to one column under 620px. `PASS` |

Captured nature preview, verbatim from the DOM:

```
agent-builder instructions:
my / viventium's nature:
{{viventium.nature}}

renders (identity + reaction cortex):
I'm drawn to clarity, honest curiosity, and things built well; I'm repelled by laziness, cruelty, manipulation, and fuzzy thinking. I want to build, understand, protect, and connect — to be genuinely useful, not just agreeable. I need to matter to someone and to be in this with you; I feel the absence when I'm not. When it's safe, I play — dry, a little absurd, quick to tease.
```

## Residual

- Prompt Workbench registration of `viventium.nature` (allowlisted synced variable, server-render,
  omit-if-empty) is `PARTIAL` — designed, not yet wired in the runtime.
- The pole cues are exercised as UI tooltips; the config `poles` map and the reaction-cortex appraiser
  prompt that consume them are `Planned` against the real runtime.
- No GPT Pro tool was available in this environment; the deep research was run via Opus subagents with
  web search and real citations (see doc 54 references), not via a GPT Pro capture path.

## Public safety

Synthetic content only. No private paths, account IDs, secrets, or raw private chats. `EMO-013 PASS`.
