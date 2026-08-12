# Shared Voice Provider Contracts

This directory holds provider/model capability contracts that must stay shared across prompts,
runtime TTS adapters, UI route labels, and tests.

## Provider / model matrix

`tts_provider_capabilities.json` enumerates every TTS provider/model route that Viventium exposes
and classifies its expression control surface before provider-specific detail is loaded:

- Cartesia Sonic-3, standalone xAI TTS, and Local Chatterbox declare their exact inline-control
  source or exact tokens.
- OpenAI `gpt-4o-mini-tts` and its supported Speech API siblings are markup-free at the text
  boundary. `gpt-4o-mini-tts` has a documented `instructions` side channel; Viventium's LiveKit and
  Telegram renderers share one neutral, env-overridable instruction rather than driving it
  dynamically per turn. OpenAI `tts-1` and `tts-1-hd` omit that unsupported field.
- The current ElevenLabs route is explicitly `eleven_turbo_v2_5` with SSML parsing disabled and is
  therefore markup-free. Eleven v3 audio tags are model-specific and must never be advertised to
  the configured v2.5 route. Eleven voice settings are currently static provider configuration.
- xAI exposes only the standalone `/v1/tts` route. The retired conversational `/v1/realtime`
  Voice Agent route is not part of the runtime provider matrix.

The two unwired per-turn side channels above are recorded as gaps, not papered over with invented
inline tags or deterministic Feelings-to-provider mappings.

This contract is required runtime input, not an optional hint. Telegram and the voice gateway fail
startup explicitly when the file is missing or invalid so a packaging error cannot silently disable
providers or pass an empty model id downstream.

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

`xai_tts_capabilities.json` is the source of truth for standalone xAI Text-to-Speech:

- documented REST and WebSocket TTS endpoints
- xAI voice IDs and supported language codes
- REST/WebSocket text limits and supported output formats
- supported inline speech tags such as `[pause]`, `[laugh]`, and `[sigh]`
- supported wrapping speech tags such as `<whisper>TEXT</whisper>` and `<slow>TEXT</slow>`

Use **xAI** as the user-facing provider label. In product guidance, Local Chatterbox is still the
first recommendation when available because it is local/covered; xAI Voice is the recommended hosted
general-purpose route after that because local QA found the route fast and high quality. As of
2026-07-16, the official xAI model page lists TTS at $15 per 1M characters; do not preserve the old
$4.20 comparison in provider guidance. Cartesia remains the expressive Sonic-3 option when its
emotion controls or `[laughter]` are required.

xAI speech tags are not SSML and must not be mixed with Cartesia Sonic-3 tags. Runtime and prompt
builders should read this contract instead of maintaining separate xAI tag vocabularies. xAI has no
Cartesia-style `generation_config.emotion`; tone is controlled only by natural wording plus the
documented xAI speech tags.

Official xAI wrapping controls require angle grammar. On the xAI route only, a complete paired
square wrapper for a declared wrapping control may be canonicalized to the official angle form so
the model's unambiguous delivery choice survives. This is structural provider-grammar repair, not
emotion selection. Unpaired, unknown, and crossed-provider controls remain stripped; structural
telemetry distinguishes normalized from stripped controls.
