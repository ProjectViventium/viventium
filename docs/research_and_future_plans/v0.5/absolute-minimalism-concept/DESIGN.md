# Quiet command surface

## Direction

Viventium v0.5 is a quiet multimodal command surface: a centered conversation on an almost empty canvas, with voice and state controls compressed around the composer.

The current LiveKit Agent Starter is a reference for negative space, realtime presence, and one compact control dock. Viventium replaces its call-first empty stage with the user's continuous chat. No LiveKit or LibreChat code or visual components are reused.

## Design read

- Mode: Operate.
- Redesign mode: visual replacement concept.
- Design variance: 5. Centered and calm, with asymmetry only where conversation roles need it.
- Motion intensity: 5 at three deliberate moments only: the living Feelings presence, the empty-chat note turn, and the call-button transformation. Everything else stays quiet.
- Visual density: 2. The canvas is intentionally sparse.
- System: native CSS with macOS system typography. No component design system is imported.

## Visual thesis

Soft paper, precise ink, the existing V mark, and Viventium teal. The interface feels alive through state and response, not decoration.

## Tokens

### Light

- Canvas: `#f5f6f8`
- Surface: `#fcfcfd`
- Ink: `#17191d`
- Muted: `#686d76`
- Line: `#dfe2e7`
- Signal: `#087a66`

### Dark

- Canvas: `#101113`
- Surface: `#181a1e`
- Ink: `#f2f3f5`
- Muted: `#a4a8b0`
- Line: `#30333a`
- Signal: `#59d6bb`

Red is reserved for destructive or live-call stop controls. Feelings uses the same restrained Viventium signal color; it is not a rainbow ornament.

## Typography

- Product and interface: the macOS system sans stack.
- Timers only: the macOS system monospace stack.
- Sentence case throughout.
- No marketing copy, decorative eyebrows, version labels, or technical metadata. Small utility labels identify note type and recency.

## Shape system

- Composer and compact controls: pill.
- Top-of-mind paper: 14 px.
- Menus and sheets: 18 px.
- Small rows and inputs: 12 px.
- These roles stay fixed across the concept.

## Signature

Feelings appears as one continuously breathing membrane beside one plain-language state. It has no lobes, waveform, ring stack, face, or rainbow. A diffuse inner current and the changing silhouette make it read as a living inner condition instead of an online light. The same soul appears enlarged in Feelings, so opening it feels like moving closer to the same being.

The call button is the second signature. It stretches into one slender live-call island and contracts back into the same button. Native shared-element transitions are used when available; the Web Animations fallback preserves the same transformation elsewhere.

## Interaction thesis

1. The composer changes form for text, upload, audio note, and live call while the conversation remains in place.
2. The live-call dock is one row with Call, Wing, Listen-Only, time, microphone, and End. The same chat is the caption and transcript surface.
3. The call button stretches into the island. Exit is faster than entry.
4. The soul breathes continuously. System state can gather, release, hold, or extinguish it, but never turns it into a spinner or audio visualizer.
5. An empty chat shows recent context as one paper note with two quiet sheets behind it. The stack yields immediately when conversation begins.
6. Menus and sheets use one short fade-and-scale transition to preserve context.

## Top of mind logic

The empty conversation is not a generic greeting. It shows five current items distilled from recent conversation and work state:

- Priority: what matters most now.
- Thought: an idea still being shaped.
- Update: what materially changed.
- Decision: what is settled.
- Next: the nearest useful move.

The active note breathes by four pixels over 6.8 seconds. Every 6.2 seconds it turns and slides out while the next sheet slides in. Hover, keyboard focus, page hiding, or an active conversation pauses the cycle. Selecting the card advances it; Left Arrow returns to the previous card. A visible pause control stops automatic turns. Reduced motion removes breathing and automatic turns while preserving manual card changes and the same content hierarchy. Automatic turns are excluded from the conversation live region; user-requested turns are announced.

## Soul motion grammar

The soul is one SVG body driven by one capped animation loop. The nine feeling values shape it continuously:

- Energy sets breath speed and depth.
- Mood lifts or weighs the body and shifts only within Viventium teal.
- Drive creates a slight forward lean.
- Curiosity extends the upper edge.
- Vigilance tightens the membrane and adds fine tension.
- Care strengthens the aura.
- Connection increases cohesion between the two natural sides of the body.
- Openness widens the aura.
- Play increases irregularity without adding decorative particles.

System state has priority over emotional expression:

| State | Motion | Trigger |
|---|---|---|
| Resting | Slow asymmetric breath and drift | Idle chat |
| Attending | Leans toward the conversation and gathers slightly | Hover, focus, or live listening |
| Thinking | Contracts and tightens; the inner current moves | Reply pending |
| Reacting | One brief bloom from the current emotional shape | A reply or typed feeling change lands |
| Settling | Bloom energy decays back into the live resting breath | After Reacting |
| Paused | Holds the current state with reduced color and no motion | Feelings paused or page hidden |
| Off | Contracts, desaturates, and extinguishes the inner current | Feelings off |

The soul does not delay any action. `prefers-reduced-motion` keeps the same shapes, labels, and state contrast but removes continuous and expanding motion. Page visibility stops the loop. The prototype uses SVG and `requestAnimationFrame`; it adds no animation dependency.

## Rejected patterns

- A permanent default sidebar.
- Dashboard cards, bento grids, and stat strips.
- A transcript-only call page.
- A model picker in the chat header.
- Start and Stop runtime controls.
- Prompt, skill, bookmark, attachment-library, MCP, or provider jargon in the default view.
- Decorative gradients, glass panels, glows, ornamental charts, and ambient motion outside the soul, empty-chat note stack, and call transformation.
- Rainbow Feelings waves.
- A residual page-top ribbon.
- Tutorial slides or a final “all set” screen.

## Research basis

- LiveKit's current Agent Starter confirms the voice-first multimodal control-bar pattern, multiple visualizer states, and a sparse monochrome stage.
- Apple onboarding guidance favors brief interactive prerequisites and postponing nonessential setup.
- Apple menu guidance favors a small number of concise, familiar commands.
- Apple feedback guidance favors passive status near the item it describes.
- WCAG 2.2 informs focus visibility, target size, keyboard use, and non-color status cues.
- [MDN View Transitions](https://developer.mozilla.org/en-US/docs/Web/API/Document/startViewTransition) informs the shared call-button transformation and immediate fallback rule.
- [MDN Web Animations](https://developer.mozilla.org/en-US/docs/Web/API/Element/animate) informs the cross-browser call morph fallback.
- [Apple Live Activities](https://developer.apple.com/design/human-interface-guidelines/live-activities) informs the narrow live state, stable element positions, and direct controls.
- [W3C reduced-motion guidance](https://www.w3.org/WAI/WCAG21/Techniques/css/C39) requires a nonanimated equivalent.
