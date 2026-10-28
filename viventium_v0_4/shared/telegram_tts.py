"""Library adapter for the existing Telegram speech engine; no bot/client startup."""

import importlib.util
import re
from pathlib import Path
import sys
from threading import RLock

_LOAD_LOCK = RLock()

# Data-only speech grammar shared by display and the existing lazy TTS engine.
SPEECH_URL_RE = re.compile(r"\bhttps?://\S+|\bwww\.\S+")
CARTESIA_NONVERBAL_ALIASES = {
    "laugh": "laughter",
    "laughter": "laughter",
    "giggle": "laughter",
    "chuckle": "laughter",
    "soft laugh": "laughter",
    "gentle laugh": "laughter",
    "quiet laugh": "laughter",
    "nervous laugh": "laughter",
    "awkward laugh": "laughter",
    "light laugh": "laughter",
}

# Relative to the shared directory's parent in source and installed scheduler trees.
# This is code and public capability data only; no bot, user state or runtime env.
RUNTIME_SUPPORT_FILES = (
    "shared/voice/tts_provider_capabilities.json",
    "shared/voice/cartesia_sonic3_capabilities.json",
    "shared/voice/xai_tts_capabilities.json",
    "telegram-viventium/TelegramVivBot/utils/stt_env.py",
    "telegram-viventium/TelegramVivBot/utils/tts.py",
    "voice-gateway/local_chatterbox_config.py",
    "voice-gateway/mlx_chatterbox_tts.py",
    "voice-gateway/sse.py",
    "voice-gateway/requirements.mlx_audio_darwin.txt",
)


def _load(name: str, filename: str):
    # Scheduler presentations can run concurrently. Expose only a fully loaded engine.
    with _LOAD_LOCK:
        if name in sys.modules:
            return sys.modules[name]
        path = Path(__file__).resolve().parent.parent / "telegram-viventium" / "TelegramVivBot" / "utils" / filename
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError("telegram_speech_library_unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(name, None)
            raise
        return module


def resolve_api_whisper_config(*args):
    return _load("_viventium_telegram_speech_settings", "stt_env.py").resolve_api_whisper_config(*args)


async def synthesize_speech(text, convo_id, *, timeout=60, voice_route=None, environment=None,
                            diagnostics=None, deadline=None):
    settings = _load("_viventium_telegram_speech_settings", "stt_env.py").build_tts_settings(environment)
    engine = _load("_viventium_telegram_speech_engine", "tts.py")
    return await engine.synthesize_speech(text, convo_id, timeout=timeout, voice_route=voice_route,
                                        settings=settings, diagnostics=diagnostics, deadline=deadline)


def audio_speech_endpoint(api_url):
    """Existing BaseAPI speech URL rule, without its unrelated client imports."""
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(api_url or 'https://api.openai.com/v1/chat/completions')
    if not parsed.scheme:
        raise ValueError('API_URL is not set')
    prefix = parsed.path.split('chat/completions')[0] if parsed.path != '/' else ''
    if prefix and not prefix.endswith('/'):
        prefix += '/'
    path = 'v1/t2a_v2' if parsed.hostname == 'api.minimaxi.com' else prefix + 'audio/speech'
    return urlunparse(parsed[:2] + (path,) + ('',) * 3)
