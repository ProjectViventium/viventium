# Interface and brand

## User promise

Viventium looks and reads like one intentional product on every supported surface.

## Identity

- **CORE-017:** Every user-facing surface uses the Viventium name and canonical V mark. Upstream
  LibreChat identity and generic fallback marks do not appear as product identity.

## Requirements

- A changed surface is designed for its real workflow, not from generic component defaults.
- Responsive layouts, light and dark themes, keyboard interaction, accessibility text, loading,
  empty, degraded, error, and recovery states are part of acceptance when applicable.
- Hidden, copied, serialized, and accessibility text are user-facing for privacy and polish.
- Canonical assets have one source and packaging path. Generated and installed bytes must match the
  reviewed source before release.

## Owners and QA

- Assets and product rules: `docs/requirements_and_learnings/16_Branding_and_Assets.md`
- Surface code: the owning client or helper component
- QA: `qa/branding-assets/` and `qa/cognitive-architecture/`

Acceptance uses the real changed surface and checks responsive layout, themes, interaction,
accessibility, product identity, and installed assets. A screenshot review alone does not pass.

## Detailed contracts

- [Branding and Assets](../16_Branding_and_Assets.md)
