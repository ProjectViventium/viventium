# Viventium v0.5 Absolute Minimalism concept

This is a standalone, interactive user-surface concept for review. It does not change production code or reuse LibreChat, LiveKit, or prior v0.5 mockup code. It uses the existing Viventium mark.

## Open it

From this folder:

```sh
python3 -m http.server 9377
```

Then open `http://127.0.0.1:9377/`.

Useful review scenes:

- `?reset=1&stage=install`
- `?reset=1&stage=connect`
- `?reset=1&stage=chat`
- `?reset=1&stage=conversation`
- `?reset=1&stage=call`
- `?reset=1&stage=feelings`
- `?reset=1&stage=advanced`
- add `&connectError=1` to test setup recovery
- add `&connectSlow=1` only to review the optional connection-loading state

The concept saves chat, connections, Feelings, appearance, and Advanced state in local browser storage. All visible account and conversation data is synthetic.

Interaction logic checks:

```sh
node --test soul.test.mjs top-of-mind.test.mjs
```

## Design category

The direction is a **quiet multimodal command surface**: one app, one connection, always on. The surface keeps one continuous conversation and hides internal product machinery without deleting capability. A living Feelings presence, a contextual paper-note stack before conversation, and a call button that transforms into one slender call island provide its three purposeful motion moments. It borrows the category logic of current realtime-agent interfaces, not their code or components.

Research basis:

- [LiveKit Agent Starter](https://github.com/livekit-examples/agent-starter-react): negative space, realtime presence, and a compact voice dock.
- [LiveKit Components](https://github.com/livekit/components-js): current voice, transcription, and visualizer primitives.
- [Apple onboarding guidance](https://developer.apple.com/design/human-interface-guidelines/onboarding): fast prerequisites and postponed optional setup.
- [Apple menu guidance](https://developer.apple.com/design/human-interface-guidelines/menus): concise, familiar, space-efficient commands.
- [Apple Live Activities](https://developer.apple.com/design/human-interface-guidelines/live-activities): compact live state, stable positions, and direct controls.
- [Apple Motion](https://developer.apple.com/design/human-interface-guidelines/motion): purposeful status motion, brief feedback, and reduced-motion parity.
- [MDN View Transitions](https://developer.mozilla.org/en-US/docs/Web/API/Document/startViewTransition): shared call-button transformation with immediate fallback.
- [MDN Web Animations](https://developer.mozilla.org/en-US/docs/Web/API/Element/animate): cross-browser call morph fallback.
- [W3C reduced-motion guidance](https://www.w3.org/WAI/WCAG21/Techniques/css/C39): a still equivalent for every focal animation.
- [WCAG 2.2 target size guidance](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html): usable controls and clear focus.

## Runtime boundary

This is the proposed v0.5 shell, not a claim about the current shipped runtime. The concept uses no LibreChat or LiveKit code. In the product, LibreChat can remain hidden behind chat and Cortex Editor, GlassHive remains the worker plane, and Prompt Workbench remains internal.

## Artifact location

New concept:

`docs/research_and_future_plans/v0.5/absolute-minimalism-concept/`

Previous artifact locations were found but their contents were not opened:

- `docs/research_and_future_plans/v0.5/artifacts/`
- `qa/v0.5-product-design/`
