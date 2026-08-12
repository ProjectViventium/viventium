# Viventium V0.5 Design Review Package

> **Status:** proposed V0.5 architecture, brand, and interaction package under product-owner review.
> No V0.5 runtime is claimed.

The canonical proposal lives in [`viventium_v0_5/docs/`](../../../viventium_v0_5/docs/).

## Review artifacts

1. [Scrollable complete architecture story](artifacts/viventium-v0.5-architecture.html)
2. [Brand and UI/UX Kit](artifacts/viventium-v0.5-brand-ui-kit.html)
3. [Unified V0.5 product prototype](artifacts/viventium-v0.5-sources-wireframe.html)
4. [Public-safe Life folder fixture](test-Life-v0.01/README.md)
5. [Life agent operating rules](test-Life-v0.01/AGENTS.md)

The earlier fixed-frame SVG remains only as superseded review history. It is not the canonical V0.5
architecture presentation.

The first green/card-heavy product UI was explicitly rejected. The first quiet-graphite candidate
improved the visual language but was superseded after specialist review found missing emotional
history, multi-account setup, one-click discovery, and canonical automation editing. That exact R1
state remains under [`artifacts/revisions/quiet-graphite-r1/`](artifacts/revisions/quiet-graphite-r1/).

The current product prototype is the **living-mind R3** candidate. R3 replaces R2's misleading
per-emotion mini charts with the live-product-shaped, fixed 0–100 Feeling Spectrum, and gives MIND
one message-anchored **Behind this reply** receipt for Memory and Cortex visibility. It remains
unapproved until the product owner accepts it; no implementation work should infer approval from
its completeness.

The prototypes simulate local state only. They never request, store, or connect real credentials.
Private user Life data, secrets, exports, logs, and worker context bundles never belong in this
public repository.
