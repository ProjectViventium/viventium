import asyncio
import importlib.util
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

import httpx

from aient.aient.core.utils import BaseAPI
from utils.stt_env import resolve_api_whisper_config

logger = logging.getLogger(__name__)

_DEFAULT_LOCAL_CHATTERBOX_MODEL_ID = "mlx-community/chatterbox-turbo-8bit"
_CARTESIA_SONIC3_MODEL_ID = "sonic-3"
_SUPPORTED_TTS_PROVIDERS = {
    "openai",
    "elevenlabs",
    "cartesia",
    "local_chatterbox_turbo_mlx_8bit",
}


# === VIVENTIUM START ===
# Feature: Strip LibreChat citation markers before TTS.
_CITATION_COMPOSITE_RE = re.compile(
    r"(?:\\ue200|ue200|\ue200).*?(?:\\ue201|ue201|\ue201)",
    re.IGNORECASE,
)
_CITATION_STANDALONE_RE = re.compile(
    r"(?:\\ue202|ue202|\ue202)turn\d+[A-Za-z]+\d+",
    re.IGNORECASE,
)
_CITATION_CLEANUP_RE = re.compile(
    r"(?:\\ue2(?:00|01|02|03|04|06)|ue2(?:00|01|02|03|04|06)|[\ue200-\ue206])",
    re.IGNORECASE,
)
_BRACKET_CITATION_RE = re.compile(r"\[(\d{1,3})\](?=\s|$)")
# === VIVENTIUM START ===
# Feature: Voice-safe cleanup (URLs, emails, plans, tool directives).
_URL_RE = re.compile(r"\bhttps?://\S+|\bwww\.\S+")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_PLAN_PREFIX_RE = re.compile(r"(?im)^\s*(?:structured\s+)?(?:plan|steps?)\s*:\s*")
_LIST_PREFIX_RE = re.compile(r"(?m)^\s*(?:[-*+]|\d+[.)]|\u2022)\s+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_TOOL_DIRECTIVE_PREFIX_RE = re.compile(
    r"(?i)^(use|list|fetch|pull|query|find|locate|get|retrieve|search|open|check|"
    r"identify|summarize|return|provide|select|collect)\b"
)
_TOOL_DIRECTIVE_KEYWORDS_RE = re.compile(
    r"(?i)\b("
    r"ms365|microsoft 365|folder id|receiveddatetime|body preview|bodypreview|"
    r"subject|from|message id|messageid|conversation id|conversationid|"
    r"calendar|inbox|email|messages?|events?"
    r")\b"
)
# === VIVENTIUM END ===
# === VIVENTIUM END ===

# === VIVENTIUM START ===
# Feature: Strip voice control tags for non-Cartesia TTS providers.
# Purpose: When Cartesia is primary but falls back to ElevenLabs/OpenAI, the
# response text may contain Cartesia SSML/bracket markers that would be spoken
# literally. Strip them before sending to non-expressive providers.
# Keep aligned with voice-gateway/sse.py strip_voice_control_tags().
# Added: 2026-02-22
_VCT_SPEAK_RE = re.compile(r"</?speak[^>]*>", re.IGNORECASE)
_VCT_EMOTION_SC_RE = re.compile(r'<emotion\s+value=["\']?[^"\'>]+["\']?\s*/>', re.IGNORECASE)
_VCT_EMOTION_WRAP_RE = re.compile(
    r'<emotion\s+value=["\']?[^"\'>]+["\']?\s*>([\s\S]*?)</emotion>', re.IGNORECASE
)
_VCT_BREAK_RE = re.compile(r'<break\s+time=["\']?[^"\'>]+["\']?\s*/>', re.IGNORECASE)
_VCT_SPEED_RE = re.compile(r'<speed\s+ratio=["\']?[^"\'>]+["\']?\s*/>', re.IGNORECASE)
_VCT_VOLUME_RE = re.compile(r'<volume\s+ratio=["\']?[^"\'>]+["\']?\s*/>', re.IGNORECASE)
_VCT_SPELL_RE = re.compile(r"<spell>([\s\S]*?)</spell>", re.IGNORECASE)
_VCT_BRACKET_RE = re.compile(
    r"\["
    r"(?:laugh(?:ter)?|giggle|chuckle|soft laugh|gentle laugh|quiet laugh|nervous laugh|"
    r"awkward laugh|light laugh|"
    r"sigh|gentle sigh|soft sigh|"
    r"breath|breath in|breath out|inhale|exhale|"
    r"gasp|whisper|hmm|hm)"
    r"\]",
    re.IGNORECASE,
)


def _strip_voice_control_tags(text: str) -> str:
    """Remove Cartesia SSML and bracket nonverbal markers from text."""
    if not text:
        return ""
    cleaned = _VCT_SPEAK_RE.sub("", text)
    cleaned = _VCT_EMOTION_SC_RE.sub("", cleaned)
    cleaned = _VCT_EMOTION_WRAP_RE.sub(r"\1", cleaned)
    cleaned = _VCT_BREAK_RE.sub("", cleaned)
    cleaned = _VCT_SPEED_RE.sub("", cleaned)
    cleaned = _VCT_VOLUME_RE.sub("", cleaned)
    cleaned = _VCT_SPELL_RE.sub(r"\1", cleaned)
    cleaned = _VCT_BRACKET_RE.sub("", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()
# === VIVENTIUM END ===


def prepare_tts_text(text: str) -> str:
    if not text:
        return ""

    cleaned = text
    # === VIVENTIUM START ===
    # Remove citations early so TTS never speaks them.
    cleaned = _CITATION_COMPOSITE_RE.sub(" ", cleaned)
    cleaned = _CITATION_STANDALONE_RE.sub(" ", cleaned)
    cleaned = _CITATION_CLEANUP_RE.sub(" ", cleaned)
    cleaned = _BRACKET_CITATION_RE.sub(" ", cleaned)
    # === VIVENTIUM END ===
    cleaned = cleaned.replace("\\n", "\n").replace("\\r", "\r")
    cleaned = re.sub(r"```[\s\S]*?```", " ", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
    cleaned = _URL_RE.sub(" link available ", cleaned)
    cleaned = _EMAIL_RE.sub(" email available ", cleaned)
    cleaned = re.sub(r"[\*_~]+", "", cleaned)
    cleaned = _PLAN_PREFIX_RE.sub("", cleaned)
    cleaned = _LIST_PREFIX_RE.sub("", cleaned)
    cleaned = re.sub(r"\s*[\r\n]+\s*", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(cleaned) if s.strip()]
    if sentences:
        filtered: list[str] = []
        for sentence in sentences:
            if _TOOL_DIRECTIVE_PREFIX_RE.match(sentence) and _TOOL_DIRECTIVE_KEYWORDS_RE.search(sentence):
                continue
            filtered.append(sentence)
        cleaned = " ".join(filtered).strip()
    return cleaned.strip()


def _normalize_tts_provider(provider: Optional[str]) -> str:
    value = (provider or "").strip().lower()
    if not value:
        return ""
    if value in {"grok", "xai_grok_voice", "x_ai"}:
        return "xai"
    if "chatterbox" in value:
        return "local_chatterbox_turbo_mlx_8bit"
    if value in {"browser", "automatic", "auto", "local_automatic"}:
        return "openai"
    return value


def _extract_voice_route_tts(voice_route: Optional[dict[str, Any]]) -> dict[str, Optional[str]]:
    route = voice_route if isinstance(voice_route, dict) else {}
    nested_tts = route.get("tts") if isinstance(route.get("tts"), dict) else route
    provider = _normalize_tts_provider(nested_tts.get("provider")) if isinstance(nested_tts, dict) else ""
    variant = nested_tts.get("variant") if isinstance(nested_tts, dict) else None
    return {
        "provider": provider or None,
        "variant": variant.strip() if isinstance(variant, str) and variant.strip() else None,
    }


def _cartesia_voice_id_from_variant(variant: Optional[str], default_voice_id: str) -> str:
    """Cartesia variants are voice IDs; legacy model variants fall back to the configured voice."""
    candidate = (variant or "").strip()
    if candidate and candidate not in {"sonic-2", _CARTESIA_SONIC3_MODEL_ID}:
        return candidate
    return (default_voice_id or "").strip()


def _is_local_chatterbox_supported() -> tuple[bool, Optional[str]]:
    if sys.platform != "darwin":
        return False, "local Chatterbox requires macOS"
    missing_modules = [
        module_name
        for module_name in ("mlx_audio", "mlx_lm")
        if importlib.util.find_spec(module_name) is None
    ]
    if missing_modules:
        return False, f"{', '.join(missing_modules)} is not installed"
    try:
        _import_local_chatterbox()
    except Exception as exc:
        return False, f"local Chatterbox runtime import failed: {exc}"
    return True, None


def _import_local_chatterbox():
    voice_gateway_root = Path(__file__).resolve().parents[3] / "voice-gateway"
    if str(voice_gateway_root) not in sys.path:
        sys.path.insert(0, str(voice_gateway_root))
    from local_chatterbox_config import build_local_chatterbox_config  # type: ignore[import-not-found]
    from mlx_chatterbox_tts import synthesize_wav_bytes  # type: ignore[import-not-found]

    return build_local_chatterbox_config, synthesize_wav_bytes


def _build_local_chatterbox_config(*, model_id_override: Optional[str] = None):
    build_local_chatterbox_config, synthesize_wav_bytes = _import_local_chatterbox()
    config, ref_audio_warning = build_local_chatterbox_config(model_id_override)
    if ref_audio_warning:
        logger.warning("%s; using default local Chatterbox voice", ref_audio_warning)
    return config, synthesize_wav_bytes


def resolve_tts_selection(voice_route: Optional[dict[str, Any]] = None) -> dict[str, Optional[str]]:
    import config  # local import to avoid circular dependency

    requested = _extract_voice_route_tts(voice_route)
    default_provider = _normalize_tts_provider(
        config.TTS_PROVIDER_PRIMARY or config.TTS_PROVIDER or "openai"
    )
    fallback_provider = _normalize_tts_provider(config.TTS_PROVIDER_FALLBACK or "")

    def _default_variant(provider: str) -> Optional[str]:
        if provider == "cartesia":
            return (
                (config.VIVENTIUM_CARTESIA_VOICE_ID or "").strip()
                or None
            )
        if provider == "elevenlabs":
            return (config.TTS_VOICE_ELEVENLABS or config.TTS_VOICE or "").strip() or None
        if provider == "local_chatterbox_turbo_mlx_8bit":
            return (
                (os.getenv("VIVENTIUM_MLX_AUDIO_MODEL_ID", "") or "").strip()
                or _DEFAULT_LOCAL_CHATTERBOX_MODEL_ID
            )
        return (config.TTS_MODEL or "").strip() or None

    def _provider_supported(provider: str) -> tuple[bool, Optional[str]]:
        if provider not in _SUPPORTED_TTS_PROVIDERS:
            return False, f"provider '{provider}' is not supported by Telegram TTS"
        if provider == "cartesia" and not config.CARTESIA_API_KEY:
            return False, "CARTESIA_API_KEY is missing"
        if provider == "elevenlabs" and not config.ELEVENLABS_API_KEY:
            return False, "ELEVENLABS_API_KEY is missing"
        if provider == "local_chatterbox_turbo_mlx_8bit":
            return _is_local_chatterbox_supported()
        return True, None

    requested_provider = _normalize_tts_provider(requested.get("provider"))
    requested_variant = requested.get("variant")
    if requested_provider:
        supported, reason = _provider_supported(requested_provider)
        if supported:
            return {
                "provider": requested_provider,
                "variant": requested_variant or _default_variant(requested_provider),
                "fallback_provider": fallback_provider or None,
                "source": "saved",
            }
        logger.warning(
            "Telegram TTS cannot use saved provider %s; falling back (%s)",
            requested_provider,
            reason or "unsupported",
        )

    for provider in (default_provider, fallback_provider, "openai"):
        normalized = _normalize_tts_provider(provider)
        if not normalized:
            continue
        supported, reason = _provider_supported(normalized)
        if supported:
            effective_fallback = fallback_provider if normalized != fallback_provider else ""
            return {
                "provider": normalized,
                "variant": _default_variant(normalized),
                "fallback_provider": effective_fallback or None,
                "source": "default",
            }
        logger.warning(
            "Telegram TTS skipping provider %s while resolving fallback route (%s)",
            normalized,
            reason or "unsupported",
        )

    return {
        "provider": "openai",
        "variant": None,
        "fallback_provider": None,
        "source": "default",
    }


async def synthesize_speech(
    text: str,
    convo_id: str,
    *,
    timeout: float = 60.0,
    voice_route: Optional[dict[str, Any]] = None,
) -> Optional[bytes]:
    if not text:
        return None

    api_key = None
    api_url = None

    try:
        import config  # local import to avoid circular dependency
        api_key = config.Users.get_config(convo_id, "api_key")
        api_url = config.Users.get_config(convo_id, "api_url")
    except Exception:
        logger.debug("Falling back to global API credentials for TTS", exc_info=True)

    from config import (
        API_KEY as GLOBAL_API_KEY,
        BASE_URL as GLOBAL_BASE_URL,
        CARTESIA_API_KEY,
        TTS_MODEL,
        TTS_VOICE,
        TTS_RESPONSE_FORMAT,
        TTS_PROVIDER,
        TTS_PROVIDER_PRIMARY,
        TTS_PROVIDER_FALLBACK,
        TTS_VOICE_ELEVENLABS,
        ELEVENLABS_API_KEY,
        ELEVENLABS_API_URL,
        ELEVENLABS_MODEL,
        VIVENTIUM_CARTESIA_API_URL,
        VIVENTIUM_CARTESIA_API_VERSION,
        VIVENTIUM_CARTESIA_EMOTION,
        VIVENTIUM_CARTESIA_LANGUAGE,
        VIVENTIUM_CARTESIA_MODEL_ID,
        VIVENTIUM_CARTESIA_SAMPLE_RATE,
        VIVENTIUM_CARTESIA_SPEED,
        VIVENTIUM_CARTESIA_VOICE_ID,
        VIVENTIUM_CARTESIA_VOLUME,
    )

    api_key, api_url = resolve_api_whisper_config(
        api_key,
        api_url,
        GLOBAL_API_KEY,
        GLOBAL_BASE_URL,
    )

    resolved_selection = resolve_tts_selection(voice_route=voice_route)
    provider_primary = _normalize_tts_provider(resolved_selection.get("provider"))
    provider_fallback = _normalize_tts_provider(resolved_selection.get("fallback_provider"))
    provider_chain = [provider_primary]
    if provider_fallback and provider_fallback != provider_primary:
        provider_chain.append(provider_fallback)

    timeout_config = httpx.Timeout(timeout)

    async def _try_provider(provider: str) -> Optional[bytes]:
        provider = (provider or "").strip().lower()
        variant_override = resolved_selection.get("variant") if provider == provider_primary else None

        # === VIVENTIUM START ===
        # Feature: Strip voice control tags for non-Cartesia providers.
        # When Cartesia is primary and the response contains SSML/bracket markers,
        # non-expressive fallback providers would speak them literally.
        # Added: 2026-02-22
        synth_text = text
        if provider != "cartesia" and "chatterbox" not in provider:
            synth_text = _strip_voice_control_tags(text)
            if not synth_text:
                logger.warning("Skipping %s TTS: text empty after voice tag stripping", provider)
                return None
        # === VIVENTIUM END ===

        # === VIVENTIUM START ===
        # Feature: Cartesia -> fallback provider for Telegram TTS.
        if provider == "local_chatterbox_turbo_mlx_8bit":
            supported, reason = _is_local_chatterbox_supported()
            if not supported:
                logger.warning("Skipping local Chatterbox TTS because %s", reason or "it is unavailable")
                return None

            try:
                config_obj, synthesize_wav_bytes = _build_local_chatterbox_config(
                    model_id_override=variant_override,
                )
                return await asyncio.to_thread(
                    synthesize_wav_bytes,
                    synth_text,
                    config=config_obj,
                )
            except Exception:
                logger.exception("Unexpected local Chatterbox TTS error")
                return None

        if provider == "cartesia":
            if not CARTESIA_API_KEY:
                logger.warning("Skipping Cartesia TTS because CARTESIA_API_KEY is missing")
                return None

            cartesia_voice_id = _cartesia_voice_id_from_variant(
                variant_override,
                VIVENTIUM_CARTESIA_VOICE_ID,
            )
            if not cartesia_voice_id:
                logger.warning("Skipping Cartesia TTS because VIVENTIUM_CARTESIA_VOICE_ID is not configured")
                return None

            cartesia_model_id = (VIVENTIUM_CARTESIA_MODEL_ID or _CARTESIA_SONIC3_MODEL_ID).strip()
            if cartesia_model_id != _CARTESIA_SONIC3_MODEL_ID:
                logger.warning(
                    "Telegram Cartesia TTS only supports %s; ignoring configured model_id=%s",
                    _CARTESIA_SONIC3_MODEL_ID,
                    cartesia_model_id,
                )
                cartesia_model_id = _CARTESIA_SONIC3_MODEL_ID

            # Updated 2026-02-22: Removed deprecated Sonic-2 top-level "speed": "normal"
            # (conflicts with generation_config.speed). Made language configurable.
            payload = {
                "model_id": cartesia_model_id,
                "transcript": synth_text,
                "voice": {"mode": "id", "id": cartesia_voice_id},
                "output_format": {
                    "container": "wav",
                    "encoding": "pcm_s16le",
                    "sample_rate": int(VIVENTIUM_CARTESIA_SAMPLE_RATE),
                },
                "language": VIVENTIUM_CARTESIA_LANGUAGE or "en",
                "generation_config": {
                    "speed": float(VIVENTIUM_CARTESIA_SPEED),
                    "volume": float(VIVENTIUM_CARTESIA_VOLUME),
                    "emotion": VIVENTIUM_CARTESIA_EMOTION or "neutral",
                },
            }

            headers = {
                "Cartesia-Version": VIVENTIUM_CARTESIA_API_VERSION,
                "X-API-Key": CARTESIA_API_KEY,
                "Authorization": f"Bearer {CARTESIA_API_KEY}",
                "Content-Type": "application/json",
            }

            try:
                async with httpx.AsyncClient(timeout=timeout_config) as client:
                    response = await client.post(
                        VIVENTIUM_CARTESIA_API_URL, headers=headers, content=json.dumps(payload)
                    )
                    response.raise_for_status()
                    return response.content
            except asyncio.TimeoutError:
                logger.warning("Cartesia TTS timed out for conversation %s", convo_id)
            except httpx.HTTPStatusError as err:
                logger.warning("Cartesia TTS HTTP error (%s): %s", err.response.status_code, err.response.text)
            except Exception:
                logger.exception("Unexpected Cartesia TTS error")

            return None
        # === VIVENTIUM END ===

        if provider == "elevenlabs":
            if not ELEVENLABS_API_KEY:
                logger.warning("Skipping ElevenLabs TTS because ELEVENLABS_API_KEY is missing")
                return None

            voice_id = (variant_override or TTS_VOICE_ELEVENLABS or TTS_VOICE or "").strip()
            if not voice_id:
                logger.warning("Skipping ElevenLabs TTS because ElevenLabs voice id is not configured")
                return None

            api_base = (ELEVENLABS_API_URL or "https://api.elevenlabs.io").rstrip("/")
            endpoint = f"{api_base}/v1/text-to-speech/{voice_id}"

            format_map = {
                "mp3": "mp3_44100_128",
                "wav": "wav",
                "ogg": "ogg_44100_64",
                "pcm": "pcm_16000",
            }
            output_format = format_map.get((TTS_RESPONSE_FORMAT or "mp3").lower(), "mp3_44100_128")

            voice_settings = {}
            if config.ELEVENLABS_STABILITY is not None:
                stability = config.ELEVENLABS_STABILITY
                allowed_stability = {0.0, 0.5, 1.0}
                if stability not in allowed_stability:
                    closest_stability = min(allowed_stability, key=lambda value: abs(value - stability))
                    logger.warning(
                        "Adjusting ElevenLabs stability from %s to %s (allowed values: %s)",
                        stability,
                        closest_stability,
                        sorted(allowed_stability),
                    )
                    stability = closest_stability
                voice_settings["stability"] = stability

            if config.ELEVENLABS_SIMILARITY is not None:
                similarity = max(0.0, min(1.0, config.ELEVENLABS_SIMILARITY))
                if similarity != config.ELEVENLABS_SIMILARITY:
                    logger.warning(
                        "Clamped ElevenLabs similarity_boost from %s to %s (allowed range: 0.0-1.0)",
                        config.ELEVENLABS_SIMILARITY,
                        similarity,
                    )
                voice_settings["similarity_boost"] = similarity

            if config.ELEVENLABS_STYLE is not None:
                style = max(0.0, min(1.0, config.ELEVENLABS_STYLE))
                if style != config.ELEVENLABS_STYLE:
                    logger.warning(
                        "Clamped ElevenLabs style from %s to %s (allowed range: 0.0-1.0)",
                        config.ELEVENLABS_STYLE,
                        style,
                    )
                voice_settings["style"] = style

            if config.ELEVENLABS_USE_SPEAKER_BOOST is not None:
                voice_settings["use_speaker_boost"] = bool(config.ELEVENLABS_USE_SPEAKER_BOOST)

            if config.ELEVENLABS_SPEED is not None:
                # ElevenLabs accepts approximately 0.7x to 1.3x playback speed for flagship voices.
                speed = max(0.7, min(1.3, config.ELEVENLABS_SPEED))
                if speed != config.ELEVENLABS_SPEED:
                    logger.warning(
                        "Clamped ElevenLabs speed from %s to %s (allowed range: 0.7-1.3)",
                        config.ELEVENLABS_SPEED,
                        speed,
                    )
                voice_settings["speed"] = speed

            # Use turbo_v2_5 as default for speed/cost, fallback to multilingual_v2 for quality
            default_model = ELEVENLABS_MODEL or "eleven_turbo_v2_5"
            payload = {
                "text": synth_text,
                "model_id": default_model,
                "output_format": output_format,
            }
            if voice_settings:
                payload["voice_settings"] = voice_settings

            headers = {
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
            }

            try:
                async with httpx.AsyncClient(timeout=timeout_config) as client:
                    response = await client.post(endpoint, headers=headers, json=payload)
                    response.raise_for_status()

                    # CRITICAL FIX: Ensure complete audio is received
                    # Read all content and verify we got the full response
                    audio_content = response.content

                    # Check Content-Length header to ensure we received complete audio
                    content_length = response.headers.get("Content-Length")
                    if content_length:
                        expected_length = int(content_length)
                        actual_length = len(audio_content)
                        if actual_length < expected_length:
                            logger.warning(
                                "ElevenLabs TTS incomplete audio: received %d bytes, expected %d bytes",
                                actual_length,
                                expected_length
                            )
                            # Try to read remaining content
                            remaining = await response.aread()
                            if remaining:
                                audio_content += remaining
                                logger.info("Recovered remaining audio: %d bytes", len(remaining))

                    # Small delay to ensure audio buffer is fully flushed (prevents cutoff)
                    await asyncio.sleep(0.1)

                    return audio_content
            except asyncio.TimeoutError:
                logger.warning("ElevenLabs TTS timed out for conversation %s", convo_id)
            except httpx.HTTPStatusError as err:
                logger.warning(
                    "ElevenLabs TTS HTTP error (%s): %s",
                    err.response.status_code,
                    err.response.text,
                )
            except Exception:
                logger.exception("Unexpected ElevenLabs TTS error")

            return None

        if provider != "openai":
            logger.warning("Skipping unsupported Telegram TTS provider '%s'", provider)
            return None

        api_key_final = api_key or GLOBAL_API_KEY
        api_url_final = api_url or GLOBAL_BASE_URL

        if not api_key_final or not api_url_final:
            logger.warning("Skipping TTS synthesis because OpenAI API credentials are missing")
            return None

        try:
            endpoint = BaseAPI(api_url_final).audio_speech
        except Exception as err:
            logger.warning("Failed to derive audio endpoint for TTS: %s", err)
            return None

        payload = {
            "model": (variant_override or TTS_MODEL or "").strip() or TTS_MODEL,
            "input": synth_text,
            "voice": TTS_VOICE,
            "response_format": TTS_RESPONSE_FORMAT,
        }

        headers = {
            "Authorization": f"Bearer {api_key_final}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                return response.content
        except asyncio.TimeoutError:
            logger.warning("OpenAI TTS request timed out for conversation %s", convo_id)
        except httpx.HTTPStatusError as err:
            logger.warning("OpenAI TTS HTTP error (%s): %s", err.response.status_code, err.response.text)
        except Exception:
            logger.exception("Unexpected OpenAI TTS error")

        return None

    for provider in provider_chain:
        voice_bytes = await _try_provider(provider)
        if voice_bytes:
            return voice_bytes

    return None
