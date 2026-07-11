# Feelings Live Demo QA
<!-- qa-evidence-exempt: Historical local QA format retained without retroactively inventing evidence; current release acceptance is recorded separately. -->

Date: 2026-07-09
Status: `PASS` for the standalone owner-approval demo; product runtime remains `PARTIAL` / not implemented

## Scope

This run validates the standalone interactive frontend candidate at
`qa/emotional-cortex/prototypes/feelings-live-demo.html`. It does not claim that Feelings is wired
into LibreChat, persisted in Mongo, produced by a real Emotional Reaction Cortex, or available on
Web/Voice/Telegram.

## What Ran

- Static server bound to localhost for a real HTTP browser path.
- Playwright CLI real-browser interaction using
  `qa/emotional-cortex/scripts/feelings_live_demo_qa.cjs`.
- Clean first-run, enabled, edited, stimulated, decayed, refreshed, reduced-motion, and responsive
  states.
- Viewports: 1440, 1024, 768, 390, and 320 CSS pixels.
- Manual visual review of desktop, mobile, and Reaction Cortex drawer captures.
- Runtime tokenizer measurement of the demo capsule: 83 tokens for both tested tokenizer families.
- JavaScript syntax checks, targeted diff checks, and public-safety scan.

## Results

| Surface / behavior | Result | Evidence |
|---|---|---|
| Default-off prompt absence | `PASS` | No `<viventium_feeling_state>` on clean first run |
| Seven active bands | `PASS` | Energy, Drive, Curiosity, Vigilance, Care, Connection, Play |
| Current vs Nature separation | `PASS` | Real pointer drags and keyboard edits passed; moving Nature left Current unchanged |
| Word-only embodied capsule | `PASS` | One tag, one being-frame sentence, seven word rows, zero numbers/config/history/policy prose |
| Per-band omission | `PASS` | Care disappeared from the capsule and count changed to `6 of 7 felt` |
| Reaction stimuli | `PASS` | Risk raised Vigilance and lowered Play; other scenarios update their intended bands |
| Decay | `PASS` | Thirty-minute advance moved Vigilance from 38 to 57 toward Nature 68 |
| Trail | `PASS` | Timestamped visible history capped at ten; history never entered the speaking capsule |
| Reaction Cortex editor | `PASS` | Drawer opens, saves wording, persists through refresh, closes, and restores focus |
| Keyboard and dialog access | `PASS` | Fourteen lane sliders + two inspector sliders; arrows work; closed drawer inert; open drawer is a focus-trapped dialog |
| Persistence | `PASS` | Enable state, reaction wording, band state, and ten-entry trail survived refresh |
| Responsive layout | `PASS` | Zero page overflow at all five viewports |
| Reduced motion | `PASS` | Heartbeat animation removed and transitions reduced |
| Persisted-state boundary | `PASS` | Synthetic markup in local storage rendered as inert text, never DOM |
| Browser health | `PASS` | Zero console warnings/errors and zero external requests |

## Visual QA Corrections Made During The Run

1. The first browser pass showed that clicking a lane body did not select it; only the small title
   did. The complete lane now selects the band while leaving its two handles independently draggable.
2. A missing favicon generated the only console error. The self-contained data favicon removed it.
3. Mobile hid the Reaction Cortex action, required horizontal stimulus scrolling, and left the final
   Play band in a half-empty row. The action is now retained, stimuli wrap, and Play spans the final
   row.
4. The closed Reaction Cortex drawer remained in keyboard navigation. It is now inert when closed,
   exposes dialog semantics when open, traps focus, supports Escape, and returns focus to its opener.
5. Persisted trail values were initially interpolated as HTML. A hostile-storage regression now
   proves every persisted trail field is escaped before rendering.
6. When Current and Nature began at the same value, the Nature diamond stole the first current drag,
   and re-rendering invalidated stored track geometry. Current now owns the center hit target and the
   drag stores stable geometry rather than a disposable DOM node.

## Claude Review: Adopted vs Deferred

Adopted in this candidate:

- the embodied being-frame rather than the bare `You are feeling:` line;
- accepting the measured 83-token capsule instead of forcing a 60-token ceiling that weakens the
  intended frame;
- distinct Emotional Resonance (understanding the user) and Emotional Reaction (moving Viv's state)
  concepts;
- hidden numeric state with a word-only speaking capsule;
- primary/conscious-agent dynamic-tail placement as the implementation direction.

Deliberately not added to this v1 candidate:

- a separate five-slot `{{viventium.nature}}` prompt variable; baselines and the editable reaction
  instruction already express the required temperament without another identity subsystem;
- an optional `recent:` row in the speaking capsule; the trail stays in the Reaction Cortex/UI;
- assistant-output-driven appraisal, which can recursively amplify Viv's own emotional wording;
- duplicate policy prose or an additional restrictive runtime layer. Existing provider/base-system
  behavior remains where it is; feature quality is checked through QA and evals instead.

## Remaining Product Gaps

- No React/LibreChat embedding.
- No authenticated API, database state, or multi-surface identity.
- No real LLM appraiser or detached writer.
- No real prompt-frame trace proving the capsule's runtime position.
- No chat/voice/Telegram latency or behavioral eval.
- Demo stimuli are deterministic UI fixtures, not runtime intent classification.

The standalone artifact is ready for owner interaction and visual approval. Runtime implementation
must remain off until the owner approves the behavior and the product-level cases are implemented.
