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

## xAI TTS

`xai_tts_capabilities.json` is the source of truth for standalone xAI Text-to-Speech, distinct
from the older xAI Grok Voice Agent API adapter:

- documented REST and WebSocket TTS endpoints
- xAI voice IDs and supported language codes
- REST/WebSocket text limits and supported output formats
- supported inline speech tags such as `[pause]`, `[laugh]`, and `[sigh]`
- supported wrapping speech tags such as `<whisper>TEXT</whisper>` and `<slow>TEXT</slow>`

Use **xAI** as the user-facing provider label. In product guidance, Local Chatterbox is still the
first recommendation when available because it is local/covered; xAI Voice is the recommended hosted
general-purpose route after that because, as of 2026-05-07, the official xAI TTS pricing page lists
$4.20 per 1M TTS characters and local QA found the route fast and high quality. Cartesia remains the
expressive Sonic-3 option when its emotion controls or `[laughter]` are required.

xAI speech tags are not SSML and must not be mixed with Cartesia Sonic-3 tags. Runtime and prompt
builders should read this contract instead of maintaining separate xAI tag vocabularies. xAI has no
Cartesia-style `generation_config.emotion`; tone is controlled only by natural wording plus the
documented xAI speech tags.
