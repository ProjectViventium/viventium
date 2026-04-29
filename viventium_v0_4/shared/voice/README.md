# Shared Voice Provider Contracts

This directory holds provider/model capability contracts that must stay shared across prompts,
runtime TTS adapters, UI route labels, and tests.

## Cartesia Sonic-3

`cartesia_sonic3_capabilities.json` is the source of truth for the Viventium Cartesia Sonic-3
surface:

- Cartesia API version and model id
- named Cartesia voice presets used by Viventium
- `generation_config` ranges/defaults for speed, volume, and emotion
- complete documented Sonic-3 emotion values
- supported SSML-like tags: `emotion`, `speed`, `volume`, `break`, and `spell`
- supported nonverbal marker: `[laughter]`

When Cartesia changes Sonic-3 or when Viventium adds another Cartesia model/provider, update or add
a capability contract here first. Prompt builders and TTS adapters should read this data instead of
maintaining separate hardcoded lists.

Runtime adapters may validate, clamp, segment, log structural counts, or strip unsupported markup
for display/fallback. They must not author emotional content on behalf of the model; for example,
`[laughter]` is preserved as the documented marker, but it does not imply an automatic emotion.
