def resolve_whisper_mode(env) -> str:
    explicit_mode = str(env.get("WHISPER_MODE") or "").strip().lower()
    if explicit_mode:
        return explicit_mode

    stt_provider = str(
        env.get("VIVENTIUM_TELEGRAM_STT_PROVIDER")
        or env.get("VIVENTIUM_STT_PROVIDER")
        or env.get("STT_PROVIDER")
        or ""
    ).strip().lower()

    if stt_provider in {"whisper_local", "pywhispercpp", "local"}:
        return "pywhispercpp"
    if stt_provider in {"assemblyai", "openai"}:
        return stt_provider
    return "openai"


# === VIVENTIUM START === Use the call's compiled AssemblyAI options for notes.
def normalize_voice_context_keyterms(value):
    if value is None:
        return []
    if (not isinstance(value, list) or len(value) > 32
            or any(not isinstance(term, str) or not term.strip() or len(term) > 96
                   or '/' in term or '\\' in term
                   or any(ord(character) < 0x20 for character in term) for term in value)):
        raise ValueError('Invalid canonical voice context keyterms')
    return list(value)


def build_assemblyai_stt_options(environment, contextual_keyterms=None):
    import math

    options = {'speaker_labels': True}
    for source, target, integer in (
        ('VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD',
         'end_of_turn_confidence_threshold', False),
        ('VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS',
         'min_turn_silence', True),
        ('VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS', 'max_turn_silence', True),
    ):
        raw = str(environment.get(source) or '').strip()
        if not raw:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        if math.isfinite(value) and value >= 0:
            options[target] = int(value) if integer else value
    if str(environment.get('VIVENTIUM_ASSEMBLYAI_FORMAT_TURNS') or '').strip().lower() in {
        '1', 'true', 'yes', 'on',
    }:
        options['format_turns'] = True
    keyterms = normalize_voice_context_keyterms(contextual_keyterms)
    if keyterms:
        options['keyterms_prompt'] = keyterms
    return options
# === VIVENTIUM END ===


def resolve_api_whisper_config(
    user_api_key,
    user_api_url,
    default_api_key,
    default_api_url,
) -> tuple[str | None, str | None]:
    normalized_user_api_key = str(user_api_key or "").strip() or None
    normalized_user_api_url = str(user_api_url or "").strip() or None
    normalized_default_api_key = str(default_api_key or "").strip() or None
    normalized_default_api_url = str(default_api_url or "").strip() or None

    # Treat saved API URL overrides as valid only when they come with an
    # explicit saved API key. This avoids stale Telegram state pairing a new
    # runtime key with an old incompatible provider base URL.
    if normalized_user_api_key:
        return normalized_user_api_key, normalized_user_api_url or normalized_default_api_url

    return normalized_default_api_key, normalized_default_api_url


def resolve_tts_provider(env) -> str:
    explicit_provider = str(env.get("TTS_PROVIDER") or "").strip().lower()
    if explicit_provider in {"x_ai", "grok", "xai_grok_voice"}:
        return "xai"
    if explicit_provider:
        return explicit_provider

    canonical_provider = str(env.get("VIVENTIUM_TTS_PROVIDER") or "").strip().lower()
    if canonical_provider in {"browser", "automatic", "auto", "local_automatic"}:
        return "openai"
    if canonical_provider in {"x_ai", "grok", "xai_grok_voice"}:
        return "xai"
    if canonical_provider:
        return canonical_provider

    return "openai"


def resolve_tts_provider_fallback(env, primary_provider) -> str:
    explicit_fallback = str(
        env.get("TTS_PROVIDER_FALLBACK")
        or env.get("VIVENTIUM_TTS_PROVIDER_FALLBACK")
        or ""
    ).strip().lower()
    if explicit_fallback in {"0", "false", "off", "none"}:
        return ""
    if explicit_fallback in {"x_ai", "grok", "xai_grok_voice"}:
        return "xai"
    if explicit_fallback:
        return explicit_fallback

    if str(primary_provider or "").strip().lower() == "cartesia":
        return "elevenlabs"

    return ""


def resolve_tts_model(explicit_model, provider, fallback_model, env=None) -> str:
    normalized_explicit_model = str(explicit_model or "").strip()
    if normalized_explicit_model:
        return normalized_explicit_model

    normalized_provider = str(provider or "").strip().lower()
    normalized_env = env or {}
    if normalized_provider in {"grok", "x_ai", "xai_grok_voice"}:
        normalized_provider = "xai"
    if normalized_provider in {"local_chatterbox", "chatterbox"}:
        normalized_provider = "local_chatterbox_turbo_mlx_8bit"
    if normalized_provider == "openai":
        shared_model = str(normalized_env.get("VIVENTIUM_OPENAI_TTS_MODEL") or "").strip()
        if shared_model:
            return shared_model
        return "gpt-4o-mini-tts"
    if normalized_provider == "cartesia":
        shared_model = str(normalized_env.get("VIVENTIUM_CARTESIA_MODEL_ID") or "").strip()
        if shared_model:
            return shared_model
        return "sonic-3"
    if normalized_provider == "elevenlabs":
        shared_model = str(normalized_env.get("ELEVENLABS_MODEL") or "").strip()
        if shared_model:
            return shared_model
        return "eleven_turbo_v2_5"
    if normalized_provider == "local_chatterbox_turbo_mlx_8bit":
        shared_model = str(normalized_env.get("VIVENTIUM_MLX_AUDIO_MODEL_ID") or "").strip()
        if shared_model:
            return shared_model
        return "mlx-community/chatterbox-turbo-8bit"
    if normalized_provider == "xai":
        shared_voice = str(normalized_env.get("VIVENTIUM_XAI_VOICE") or "").strip()
        if shared_voice:
            return shared_voice
        return "Sal"

    return str(fallback_model or "").strip()


# === VIVENTIUM START ===
def build_tts_settings(environment=None):
    """Pure shared speech settings; does not load Telegram users or runtime clients."""
    import os
    from types import SimpleNamespace
    env = os.environ if environment is None else environment
    def number(name, default=None, integer=False):
        raw = env.get(name)
        if raw is None:
            return default
        try:
            return int(float(str(raw).strip())) if integer else float(str(raw).strip())
        except (TypeError, ValueError, OverflowError):
            return default
    primary = str(env.get('TTS_PROVIDER_PRIMARY') or '').strip().lower() or resolve_tts_provider(env)
    values = {
        'API_KEY': env.get('API_KEY') or env.get('AZURE_OPENAI_API_KEY') or env.get('xai_api_key'),
        'BASE_URL': env.get('BASE_URL', 'https://api.x.ai/v1/chat/completions'),
        'TTS_VOICE': env.get('TTS_VOICE', 'alloy'),
        'TTS_RESPONSE_FORMAT': env.get('TTS_RESPONSE_FORMAT', 'mp3'),
        'TTS_PROVIDER': resolve_tts_provider(env),
        'TTS_PROVIDER_PRIMARY': primary,
        'TTS_PROVIDER_FALLBACK': resolve_tts_provider_fallback(env, primary),
        'TTS_MODEL': resolve_tts_model(env.get('TTS_MODEL'), primary, env.get('MODEL', 'grok-4.5'), env),
        'TTS_VOICE_ELEVENLABS': str(env.get('TTS_VOICE_ELEVENLABS') or '').strip() or env.get('TTS_VOICE', 'alloy'),
        'ELEVENLABS_API_KEY': env.get('ELEVENLABS_API_KEY'),
        'ELEVENLABS_API_URL': env.get('ELEVENLABS_API_URL', 'https://api.elevenlabs.io'),
        'ELEVENLABS_MODEL': env.get('ELEVENLABS_MODEL', 'eleven_turbo_v2_5'),
        'CARTESIA_API_KEY': env.get('CARTESIA_API_KEY'),
        'VIVENTIUM_CARTESIA_API_URL': env.get('VIVENTIUM_CARTESIA_API_URL', 'https://api.cartesia.ai/tts/bytes'),
        'VIVENTIUM_CARTESIA_API_VERSION': env.get('VIVENTIUM_CARTESIA_API_VERSION', ''),
        'VIVENTIUM_CARTESIA_MODEL_ID': env.get('VIVENTIUM_CARTESIA_MODEL_ID', 'sonic-3'),
        'VIVENTIUM_CARTESIA_VOICE_ID': env.get('VIVENTIUM_CARTESIA_VOICE_ID', 'e8e5fffb-252c-436d-b842-8879b84445b6'),
        'VIVENTIUM_CARTESIA_SAMPLE_RATE': number('VIVENTIUM_CARTESIA_SAMPLE_RATE', 44100, True),
        'VIVENTIUM_CARTESIA_SPEED': number('VIVENTIUM_CARTESIA_SPEED', 1.0),
        'VIVENTIUM_CARTESIA_VOLUME': number('VIVENTIUM_CARTESIA_VOLUME', 1.0),
        'VIVENTIUM_CARTESIA_EMOTION': env.get('VIVENTIUM_CARTESIA_EMOTION', 'neutral'),
        'VIVENTIUM_CARTESIA_LANGUAGE': env.get('VIVENTIUM_CARTESIA_LANGUAGE', 'en'),
        'VIVENTIUM_XAI_TTS_API_KEY': str(env.get('VIVENTIUM_XAI_TTS_API_KEY') or '').strip(),
        'VIVENTIUM_XAI_TTS_API_URL': env.get('VIVENTIUM_XAI_TTS_API_URL', 'https://api.x.ai/v1/tts'),
        'VIVENTIUM_XAI_VOICE': env.get('VIVENTIUM_XAI_VOICE', 'Sal'),
        'VIVENTIUM_XAI_LANGUAGE': env.get('VIVENTIUM_XAI_LANGUAGE', 'en'),
        'VIVENTIUM_XAI_TTS_CODEC': env.get('VIVENTIUM_XAI_TTS_CODEC', 'mp3'),
        'VIVENTIUM_XAI_TTS_SAMPLE_RATE': number('VIVENTIUM_XAI_TTS_SAMPLE_RATE', number('VIVENTIUM_XAI_SAMPLE_RATE', 24000, True), True),
        'VIVENTIUM_XAI_TTS_BIT_RATE': number('VIVENTIUM_XAI_TTS_BIT_RATE', 128000, True),
    }
    values['XAI_API_KEY'] = values['VIVENTIUM_XAI_TTS_API_KEY'] or env.get('XAI_API_KEY', '')
    for name in ('SPEED', 'STABILITY', 'SIMILARITY', 'STYLE'):
        values['ELEVENLABS_' + name] = number('ELEVENLABS_' + name)
    raw_boost = env.get('ELEVENLABS_USE_SPEAKER_BOOST')
    boost = str(raw_boost).strip().lower() if raw_boost is not None else ''
    values['ELEVENLABS_USE_SPEAKER_BOOST'] = (True if boost in ('1', 'true', 'yes', 'on') else
        False if boost in ('0', 'false', 'no', 'off') else None)
    return SimpleNamespace(**values)
# === VIVENTIUM END ===
