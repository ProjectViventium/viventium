import os
import subprocess
import logging
import time

# CRITICAL: Load .env BEFORE any imports that read environment variables!
from dotenv import load_dotenv
load_dotenv()

# REMOVED: i18n - Using hardcoded English strings for simplicity
from utils.tts import prepare_tts_text
from utils.livekit_bridge import LiveKitBridge
from utils.stt_env import (
    resolve_api_whisper_config,
    resolve_tts_model,
    resolve_tts_provider,
    resolve_tts_provider_fallback,
    resolve_whisper_mode,
)
from datetime import datetime
# REMOVED: model_display_names import - Model selection removed, display names not needed

# We expose variables for access from other modules

# REMOVED: prompt.system_prompt - System prompts handled by Viventium
# REMOVED: update_initial_model - Model fetching removed
from aient.aient.core.utils import BaseAPI  # Still needed for URL formatting
from aient.aient.models import whisper  # Still needed for Whisper (voice transcription)
# REMOVED: chatgpt import - ChatGPTbot uses LiveKitBridge(), not chatgpt class
# REMOVED: PLUGINS - Plugin selection removed

def _get_float_env(name, default=None):
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default

def _get_bool_env(name, default=None):
    value = os.environ.get(name)
    if value is None:
        return default
    lower = value.lower()
    if lower in ("1", "true", "yes", "on"):
        return True
    if lower in ("0", "false", "no", "off"):
        return False
    return default

# === VIVENTIUM START ===
# Feature: Coerce stored preference values into real booleans.
def _coerce_bool(value, default=None):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("1", "true", "yes", "on"):
            return True
        if normalized in ("0", "false", "no", "off", ""):
            return False
        return default
    return bool(value)
# === VIVENTIUM END ===

# Optional local whisper integration
# Align Telegram STT with the canonical runtime env when the legacy knob is unset.
WHISPER_MODE = resolve_whisper_mode(os.environ)
LOCAL_WHISPER_MODEL_PATH = os.environ.get("LOCAL_WHISPER_MODEL_PATH")
LOCAL_WHISPER_THREADS = int(os.environ.get("LOCAL_WHISPER_THREADS", "4"))
LOCAL_WHISPER_LANG = os.environ.get("LOCAL_WHISPER_LANG", "auto")
LOCAL_WHISPER_VERBOSE = os.environ.get("LOCAL_WHISPER_VERBOSE", "false").lower() == "true"

from telegram import InlineKeyboardButton

NICK = os.environ.get('NICK', None)
PORT = int(os.environ.get('PORT', '8080'))
BOT_TOKEN = os.environ.get('BOT_TOKEN', None)
# === VIVENTIUM START ===
# Telegram backend selection (librechat default, livekit legacy).
VIVENTIUM_TELEGRAM_BACKEND = os.environ.get('VIVENTIUM_TELEGRAM_BACKEND', 'librechat').strip().lower()
# Telegram file upload controls (LibreChat bridge).
VIVENTIUM_TELEGRAM_FILE_UPLOAD_ENABLED = _get_bool_env(
    'VIVENTIUM_TELEGRAM_FILE_UPLOAD_ENABLED', True
)
VIVENTIUM_TELEGRAM_MAX_FILE_SIZE = int(
    os.environ.get('VIVENTIUM_TELEGRAM_MAX_FILE_SIZE', '10485760')
)
VIVENTIUM_TELEGRAM_FILE_TEXT_FALLBACK = _get_bool_env(
    'VIVENTIUM_TELEGRAM_FILE_TEXT_FALLBACK', False
)
# === VIVENTIUM END ===
RESET_TIME = int(os.environ.get('RESET_TIME', '3600'))
if RESET_TIME < 60:
    RESET_TIME = 60

# ============================================================================
# RESOURCE OPTIMIZATION SETTINGS
# ============================================================================
# These settings control CPU and memory usage of the Telegram bot.
# 
# WHERE TO SET: Add these variables to your config.env file in the 
#               interfaces/telegram-viventium/ directory
#
# DEFAULT VALUES: Optimized for small deployments (1-10 users)
# PREVIOUS VALUES: Optimized for large-scale deployments (1000+ users)
#
# ============================================================================

# ----------------------------------------------------------------------------
# CONNECTION_POOL_SIZE
# ----------------------------------------------------------------------------
# What it does: Controls the maximum number of HTTP connections the bot can
#               maintain simultaneously for sending messages to Telegram API.
#
# Where to set: config.env file: CONNECTION_POOL_SIZE=8
#
# When to adjust:
#   - Keep default (8) for: 1-10 users, low memory systems
#   - Increase to 16-32 for: 10-50 concurrent users
#   - Increase to 64-128 for: 50-200 concurrent users
#   - Increase to 256+ for: 200+ concurrent users
#
# Impact:
#   - Lower values = Less memory usage, but may limit concurrent operations
#   - Higher values = More memory usage, but supports more concurrent users
#   - Each connection uses ~1-2KB of memory
#
# Previous default: 65536 (excessive for small deployments)
# Current default: 8 (optimized for small deployments)
CONNECTION_POOL_SIZE = int(os.environ.get('CONNECTION_POOL_SIZE', '8'))

# ----------------------------------------------------------------------------
# GET_UPDATES_CONNECTION_POOL_SIZE
# ----------------------------------------------------------------------------
# What it does: Controls the maximum number of HTTP connections for receiving
#               updates from Telegram API (polling mode).
#
# Where to set: config.env file: GET_UPDATES_CONNECTION_POOL_SIZE=8
#
# When to adjust:
#   - Keep default (8) for: 1-10 users, low memory systems
#   - Increase to 16-32 for: 10-50 concurrent users
#   - Increase to 64-128 for: 50-200 concurrent users
#   - Increase to 256+ for: 200+ concurrent users
#
# Impact:
#   - Lower values = Less memory usage, but may limit update throughput
#   - Higher values = More memory usage, but supports more concurrent updates
#   - Each connection uses ~1-2KB of memory
#
# Previous default: 65536 (excessive for small deployments)
# Current default: 8 (optimized for small deployments)
GET_UPDATES_CONNECTION_POOL_SIZE = int(os.environ.get('GET_UPDATES_CONNECTION_POOL_SIZE', '8'))

# ----------------------------------------------------------------------------
# TIMEOUT
# ----------------------------------------------------------------------------
# What it does: Maximum time (in seconds) to wait for Telegram API responses
#               before timing out. Applies to read, write, connect, and pool
#               operations.
#
# Where to set: config.env file: TIMEOUT=30
#
# When to adjust:
#   - Keep default (30) for: Fast networks, most deployments
#   - Increase to 60-120 for: Slow networks, high latency connections
#   - Decrease to 15-20 for: Very fast networks, want faster error detection
#
# Impact:
#   - Lower values = Faster error detection, less resource usage, but may
#                    timeout on slow networks
#   - Higher values = More tolerant of slow networks, but keeps connections
#                    open longer (more memory/CPU)
#
# Previous default: 600 seconds (10 minutes - excessive)
# Current default: 30 seconds (optimized for small deployments)
TIMEOUT = int(os.environ.get('TIMEOUT', '30'))
if TIMEOUT < 10:
    TIMEOUT = 10  # Minimum 10 seconds to prevent too-aggressive timeouts

# ----------------------------------------------------------------------------
# CONCURRENT_UPDATES
# ----------------------------------------------------------------------------
# What it does: Enables/disables processing multiple Telegram updates
#               simultaneously. When enabled, the bot can handle multiple
#               users' messages concurrently.
#
# Where to set: config.env file: CONCURRENT_UPDATES=false
#               Use: true/false, True/False, 1/0, yes/no, on/off
#
# When to adjust:
#   - Keep default (false) for: 1-10 users, want lower CPU usage
#   - Set to true for: 10+ concurrent users, need higher throughput
#
# Impact:
#   - false = Lower CPU usage, sequential processing, sufficient for small
#            deployments
#   - true = Higher CPU usage, parallel processing, better for many users
#
# Previous default: true (unnecessary for small deployments)
# Current default: false (optimized for small deployments)
CONCURRENT_UPDATES = _get_bool_env('CONCURRENT_UPDATES', False)

# ----------------------------------------------------------------------------
# POLLING_TIMEOUT
# ----------------------------------------------------------------------------
# What it does: Maximum time (in seconds) to wait when polling Telegram API
#               for new updates. Lower values mean more frequent polling
#               checks but less resource usage.
#
# Where to set: config.env file: POLLING_TIMEOUT=30
#
# When to adjust:
#   - Keep default (30) for: Most deployments, balanced performance
#   - Increase to 60-120 for: Want to reduce polling frequency (saves CPU)
#   - Decrease to 10-20 for: Want faster update detection (uses more CPU)
#
# Impact:
#   - Lower values = More frequent polling, faster update detection, but
#                    higher CPU usage
#   - Higher values = Less frequent polling, lower CPU usage, but slower
#                    update detection
#
# Note: This only applies when using polling mode (not webhook mode)
#
# Previous default: 600 seconds (excessive, caused high resource usage)
# Current default: 30 seconds (optimized for small deployments)
POLLING_TIMEOUT = int(os.environ.get('POLLING_TIMEOUT', '30'))
if POLLING_TIMEOUT < 10:
    POLLING_TIMEOUT = 10  # Minimum 10 seconds to prevent excessive polling


# BASE_URL = os.environ.get('BASE_URL', 'https://api.openai.com/v1/chat/completions')
# API_KEY = os.environ.get('API_KEY', None)
# MODEL = os.environ.get('MODEL', 'gpt-5')
BASE_URL = os.environ.get('BASE_URL', 'https://api.x.ai/v1/chat/completions')
API_KEY = (
    os.environ.get('API_KEY')
    or os.environ.get('AZURE_OPENAI_API_KEY')
    or os.environ.get('xai_api_key')
)
# === VIVENTIUM START ===
# Feature: AssemblyAI STT option for Telegram voice transcription.
# Purpose: Allow WHISPER_MODE=assemblyai with AssemblyAI credentials via env.
ASSEMBLYAI_API_KEY = os.environ.get('ASSEMBLYAI_API_KEY')
ASSEMBLYAI_BASE_URL = os.environ.get('ASSEMBLYAI_BASE_URL', 'https://api.assemblyai.com/v2')
# === VIVENTIUM END ===
MODEL = os.environ.get('MODEL', 'grok-4-fast-reasoning')
TTS_VOICE = os.environ.get('TTS_VOICE', 'alloy')
TTS_RESPONSE_FORMAT = os.environ.get('TTS_RESPONSE_FORMAT', 'mp3')
TTS_PROVIDER = resolve_tts_provider(os.environ)
# === VIVENTIUM START ===
# Feature: Primary + fallback TTS provider selection (Cartesia primary, ElevenLabs fallback).
# Backward compatible: if TTS_PROVIDER_PRIMARY is unset, TTS_PROVIDER is treated as the primary.
TTS_PROVIDER_PRIMARY = (
    os.environ.get('TTS_PROVIDER_PRIMARY', '').strip().lower() or TTS_PROVIDER
)
TTS_PROVIDER_FALLBACK = resolve_tts_provider_fallback(os.environ, TTS_PROVIDER_PRIMARY)
TTS_MODEL = resolve_tts_model(
    os.environ.get('TTS_MODEL'),
    TTS_PROVIDER_PRIMARY or TTS_PROVIDER,
    MODEL,
    os.environ,
)

# Optional: allow a dedicated ElevenLabs voice id separate from OpenAI voice name.
TTS_VOICE_ELEVENLABS = os.environ.get('TTS_VOICE_ELEVENLABS', '').strip() or TTS_VOICE
# === VIVENTIUM END ===
ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY')
ELEVENLABS_API_URL = os.environ.get('ELEVENLABS_API_URL', 'https://api.elevenlabs.io')
# ElevenLabs Model Options:
# - "eleven_turbo_v2_5" (recommended): Fastest, lowest latency (~75ms), cost-effective, best for real-time
# - "eleven_multilingual_v2": Best quality, multilingual support, slower, higher cost
# - "eleven_monolingual_v1": English only, older model
# - "eleven_v3": Legacy model (not recommended)
ELEVENLABS_MODEL = os.environ.get('ELEVENLABS_MODEL', 'eleven_turbo_v2_5')  # Changed default to turbo for speed/cost
ELEVENLABS_SPEED = _get_float_env('ELEVENLABS_SPEED')
ELEVENLABS_STABILITY = _get_float_env('ELEVENLABS_STABILITY')
ELEVENLABS_SIMILARITY = _get_float_env('ELEVENLABS_SIMILARITY')
ELEVENLABS_STYLE = _get_float_env('ELEVENLABS_STYLE')
ELEVENLABS_USE_SPEAKER_BOOST = _get_bool_env('ELEVENLABS_USE_SPEAKER_BOOST')
# === VIVENTIUM START ===
# Feature: Cartesia TTS configuration for Telegram voice replies.
# Aligns with voice-gateway defaults while remaining fully configurable.
CARTESIA_API_KEY = os.environ.get('CARTESIA_API_KEY')
VIVENTIUM_CARTESIA_API_URL = os.environ.get(
    'VIVENTIUM_CARTESIA_API_URL', 'https://api.cartesia.ai/tts/bytes'
)
VIVENTIUM_CARTESIA_API_VERSION = os.environ.get('VIVENTIUM_CARTESIA_API_VERSION', '2025-04-16')
VIVENTIUM_CARTESIA_MODEL_ID = os.environ.get('VIVENTIUM_CARTESIA_MODEL_ID', 'sonic-3')
VIVENTIUM_CARTESIA_VOICE_ID = os.environ.get(
    'VIVENTIUM_CARTESIA_VOICE_ID', 'e8e5fffb-252c-436d-b842-8879b84445b6'
)
VIVENTIUM_CARTESIA_SAMPLE_RATE = int(float(os.environ.get('VIVENTIUM_CARTESIA_SAMPLE_RATE', '44100')))
VIVENTIUM_CARTESIA_SPEED = _get_float_env('VIVENTIUM_CARTESIA_SPEED', 1.0)
VIVENTIUM_CARTESIA_VOLUME = _get_float_env('VIVENTIUM_CARTESIA_VOLUME', 1.0)
VIVENTIUM_CARTESIA_EMOTION = os.environ.get('VIVENTIUM_CARTESIA_EMOTION', 'neutral')
VIVENTIUM_CARTESIA_LANGUAGE = os.environ.get('VIVENTIUM_CARTESIA_LANGUAGE', 'en')
# === VIVENTIUM END ===

WEB_HOOK = os.environ.get('WEB_HOOK', None)
CHAT_MODE = os.environ.get('CHAT_MODE', "global")
# === VIVENTIUM START ===
# Feature: Optional default timezone for Telegram time context.
VIVENTIUM_TELEGRAM_DEFAULT_TIMEZONE = os.environ.get('VIVENTIUM_TELEGRAM_DEFAULT_TIMEZONE', '').strip()
# Feature: Typing indicator refresh interval (seconds).
VIVENTIUM_TELEGRAM_TYPING_INTERVAL_S = _get_float_env(
    'VIVENTIUM_TELEGRAM_TYPING_INTERVAL_S', 4.0
)
# Feature: Stream preview edit throttle (seconds, OpenClaw-style coalescing).
VIVENTIUM_TELEGRAM_STREAM_EDIT_INTERVAL_S = _get_float_env(
    'VIVENTIUM_TELEGRAM_STREAM_EDIT_INTERVAL_S', 0.35
)
if not isinstance(VIVENTIUM_TELEGRAM_STREAM_EDIT_INTERVAL_S, (int, float)) or VIVENTIUM_TELEGRAM_STREAM_EDIT_INTERVAL_S <= 0:
    VIVENTIUM_TELEGRAM_STREAM_EDIT_INTERVAL_S = 0.35
# Feature: Delay window for LONG_TEXT message merge.
VIVENTIUM_TELEGRAM_LONG_TEXT_WAIT_S = _get_float_env(
    'VIVENTIUM_TELEGRAM_LONG_TEXT_WAIT_S', 0.35
)
if not isinstance(VIVENTIUM_TELEGRAM_LONG_TEXT_WAIT_S, (int, float)) or VIVENTIUM_TELEGRAM_LONG_TEXT_WAIT_S < 0:
    VIVENTIUM_TELEGRAM_LONG_TEXT_WAIT_S = 0.35
# === VIVENTIUM START ===
# Feature: Optional per-request timing logs for Telegram bridge.
VIVENTIUM_TELEGRAM_TIMING_ENABLED = _get_bool_env(
    'VIVENTIUM_TELEGRAM_TIMING_ENABLED', False
)
# Feature: Deep timing logs for microstep analysis.
VIVENTIUM_TELEGRAM_TIMING_DEEP = _get_bool_env(
    'VIVENTIUM_TELEGRAM_TIMING_DEEP', False
)
# === VIVENTIUM END ===
# === VIVENTIUM END ===
# REMOVED: GET_MODELS - Model fetching removed, Viventium handles models

PASS_HISTORY = os.environ.get('PASS_HISTORY', 9999)
if type(PASS_HISTORY) == str:
    if PASS_HISTORY.isdigit():
        PASS_HISTORY = int(PASS_HISTORY)
    elif PASS_HISTORY.lower() == "true":
        PASS_HISTORY = 9999
    elif PASS_HISTORY.lower() == "false":
        PASS_HISTORY = 0
    else:
        PASS_HISTORY = 9999
else:
    PASS_HISTORY = 9999

PREFERENCES = {
    # REMOVED: PASS_HISTORY - Not used by LiveKit Bridge, Viventium handles conversation history
    # REMOVED: IMAGEQA - LiveKit Bridge handles all images through Viventium, no need to block
    # REMOVED: TITLE - Cosmetic feature, not needed
    # REMOVED: REPLY - LiveKit Bridge handles message threading
    "LONG_TEXT"         : (os.environ.get('LONG_TEXT', "True") == "False") == False,
    "LONG_TEXT_SPLIT"   : (os.environ.get('LONG_TEXT_SPLIT', "True") == "False") == False,
    "FILE_UPLOAD_MESS"  : (os.environ.get('FILE_UPLOAD_MESS', "True") == "False") == False,
    # === VIVENTIUM START ===
    # Feature: Allow users to disable/enable voice replies entirely.
    "VOICE_RESPONSES_ENABLED": _get_bool_env('VOICE_RESPONSES_ENABLED', True),
    # === VIVENTIUM END ===
    # Default: False (only voice when user sends voice)
    "ALWAYS_VOICE_RESPONSE": _get_bool_env('ALWAYS_VOICE_RESPONSE', False),
    # === VIVENTIUM START ===
    # LibreChat bridge metadata (stored per chat)
    "LIBRECHAT_CONVERSATION_ID": "",
    "LIBRECHAT_CONVERSATION_STATE_VERSION": "",
    "LIBRECHAT_AGENT_ID": "",
    # Per-chat timezone hint for LibreChat time context injection
    "CLIENT_TIMEZONE": VIVENTIUM_TELEGRAM_DEFAULT_TIMEZONE,
    # === VIVENTIUM END ===
}

# REMOVED: Language selection - Using English-only UI for simplicity

current_date = datetime.now()
Current_Date = current_date.strftime("%Y-%m-%d")
# NOTE: systemprompt is stored but not used - Viventium handles system prompts
# Keeping for backward compatibility with user configs
systemprompt = os.environ.get('SYSTEMPROMPT', 'You are Viventium, a helpful AI assistant.')

import json
import tomllib
import requests
from contextlib import contextmanager
from urllib.parse import urlparse

CONFIG_DIR = os.environ.get('CONFIG_DIR', 'user_configs')

@contextmanager
def file_lock(filename):
    """Advisory file lock for config writes.  Gracefully degrades on
    filesystems that don't support flock (e.g., Azure Files SMB mount)."""
    if os.name == 'nt':  # Windows system
        import msvcrt
        with open(filename, 'a+') as f:
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                yield f
            finally:
                try:
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                except:
                    pass
    else:  # Unix-like system
        import fcntl
        with open(filename, 'a+') as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                yield f
            except OSError:
                # Azure Files SMB mount doesn't support flock; proceed without lock.
                # Single-instance bot so concurrent writes are not a concern.
                yield f
            finally:
                try:
                    fcntl.flock(f, fcntl.LOCK_UN)
                except OSError:
                    pass

def save_user_config(user_id, config):
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR, exist_ok=True)

    filename = os.path.join(CONFIG_DIR, f'{user_id}.json')

    # Write directly without file_lock to avoid Azure Files SMB conflicts.
    # The bot runs as a single process so concurrent writes are not a concern.
    try:
        with open(filename, 'w') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except OSError as e:
        import logging
        logging.getLogger(__name__).warning("Failed to save config %s: %s", filename, e)

def load_user_config(user_id):
    filename = os.path.join(CONFIG_DIR, f'{user_id}.json')

    if not os.path.exists(filename):
        return {}

    # Read directly without file_lock to avoid Azure Files SMB conflicts.
    # The bot runs as a single process so concurrent reads are not a concern.
    try:
        with open(filename, 'r') as f:
            content = f.read()
            if not content.strip():
                return {}
            return json.loads(content)
    except (OSError, json.JSONDecodeError) as e:
        import logging
        logging.getLogger(__name__).warning("Failed to load config %s: %s", filename, e)
        return {}

def update_user_config(user_id, key, value):
    config = load_user_config(user_id)
    config[key] = value
    save_user_config(user_id, config)


# === VIVENTIUM START ===
# Feature: Sync Telegram voice preferences to LibreChat for scheduler voice parity.
_CALL_URL_CACHE = {}


def _should_cache_call_url(call_url):
    parsed = urlparse(str(call_url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return False

    if parsed.scheme == "https":
        return True

    hostname = (parsed.hostname or "").strip().lower()
    return hostname in {"localhost", "127.0.0.1", "::1"}

def sync_voice_preferences(user_id, always_voice, voice_enabled):
    if not user_id or str(user_id) == "global":
        return
    base_url = (
        os.environ.get("VIVENTIUM_LIBRECHAT_ORIGIN")
        or os.environ.get("DOMAIN_SERVER")
        or os.environ.get("DOMAIN_CLIENT")
        or ""
    ).strip().rstrip("/")
    secret = (
        os.environ.get("VIVENTIUM_TELEGRAM_SECRET")
        or os.environ.get("VIVENTIUM_CALL_SESSION_SECRET")
        or ""
    ).strip()
    if not base_url or not secret:
        return

    payload = {
        "telegramUserId": str(user_id),
        "alwaysVoiceResponse": bool(_coerce_bool(always_voice, False)),
        "voiceResponsesEnabled": bool(_coerce_bool(voice_enabled, True)),
    }
    headers = {"X-VIVENTIUM-TELEGRAM-SECRET": secret}
    url = f"{base_url}/api/viventium/telegram/preferences"
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=5)
        if resp.status_code >= 400:
            logging.getLogger(__name__).warning(
                "Voice preference sync failed (%s): %s",
                resp.status_code,
                resp.text[:240],
            )
    except Exception as e:
        logging.getLogger(__name__).warning("Voice preference sync error: %s", e)


def _extract_telegram_user_id(conversation_key):
    raw = str(conversation_key or "").strip()
    if not raw or raw == "global":
        return ""
    if ":" in raw:
        return raw.split(":")[-1].strip()
    return raw


def get_telegram_call_link_result(conversation_key):
    config_lookup_id = str(conversation_key or "").strip()
    normalized_user_id = _extract_telegram_user_id(config_lookup_id)
    if not normalized_user_id:
        return {
            "url": "",
            "status_code": 0,
            "link_required": False,
            "public_url_required": False,
            "error": "telegramUserId is required",
        }

    cache_ttl_s = max(int(os.environ.get("VIVENTIUM_TELEGRAM_CALL_LINK_CACHE_TTL_S", "480")), 0)
    now = time.time()
    cached = _CALL_URL_CACHE.get(normalized_user_id)
    if cached and cached.get("expires_at", 0) > now:
        return {
            "url": cached.get("url", ""),
            "status_code": 200,
            "link_required": False,
            "public_url_required": False,
            "error": "",
        }

    base_url = (
        os.environ.get("VIVENTIUM_LIBRECHAT_ORIGIN")
        or os.environ.get("DOMAIN_SERVER")
        or os.environ.get("DOMAIN_CLIENT")
        or ""
    ).strip().rstrip("/")
    secret = (
        os.environ.get("VIVENTIUM_TELEGRAM_SECRET")
        or os.environ.get("VIVENTIUM_CALL_SESSION_SECRET")
        or ""
    ).strip()
    if not base_url or not secret:
        return {
            "url": "",
            "status_code": 0,
            "link_required": False,
            "public_url_required": False,
            "error": "Telegram call-link base is not configured",
        }

    payload = {"telegramUserId": normalized_user_id}
    try:
        conversation_id = Users.get_config(config_lookup_id, "LIBRECHAT_CONVERSATION_ID") or ""
        agent_id = Users.get_config(config_lookup_id, "LIBRECHAT_AGENT_ID") or ""
        if conversation_id:
            payload["conversationId"] = conversation_id
        if agent_id:
            payload["agentId"] = agent_id
    except Exception:
        pass

    headers = {"X-VIVENTIUM-TELEGRAM-SECRET": secret}
    url = f"{base_url}/api/viventium/telegram/call-link"
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=5)
        if resp.status_code >= 400:
            data = {}
            if resp.content:
                try:
                    data = resp.json()
                except Exception:
                    data = {}
            logging.getLogger(__name__).warning(
                "Telegram call-link fetch failed (%s): %s",
                resp.status_code,
                resp.text[:240],
            )
            return {
                "url": "",
                "status_code": resp.status_code,
                "link_required": bool(data.get("linkRequired")),
                "public_url_required": bool(data.get("publicPlaygroundRequired")),
                "error": str(data.get("error") or "").strip(),
            }
        data = resp.json() if resp.content else {}
        call_url = str(data.get("callUrl") or data.get("playgroundUrl") or "").strip()
        if not call_url:
            return {
                "url": "",
                "status_code": resp.status_code,
                "link_required": False,
                "public_url_required": False,
                "error": "Call link response did not include a URL",
            }
        if cache_ttl_s > 0 and _should_cache_call_url(call_url):
            _CALL_URL_CACHE[normalized_user_id] = {
                "url": call_url,
                "expires_at": now + cache_ttl_s,
            }
        return {
            "url": call_url,
            "status_code": resp.status_code,
            "link_required": False,
            "public_url_required": False,
            "error": "",
        }
    except Exception as e:
        logging.getLogger(__name__).warning("Telegram call-link fetch error: %s", e)
        return {
            "url": "",
            "status_code": 0,
            "link_required": False,
            "public_url_required": False,
            "error": str(e),
        }


def get_telegram_call_url(conversation_key):
    return get_telegram_call_link_result(conversation_key).get("url", "")
# === VIVENTIUM END ===

class NestedDict:
    def __init__(self):
        self.data = {}

    def __getitem__(self, key):
        if key not in self.data:
            self.data[key] = NestedDict()
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __str__(self):
        return str(self.data)

    def keys(self):
        return self.data.keys()
    
    def __contains__(self, key):
        """Check if key exists without auto-creating it."""
        return key in self.data

class UserConfig:
    def __init__(self,
        user_id: str = None,
        language="English",  # NOTE: Kept for backward compatibility, always English
        api_url="https://api.openai.com/v1/chat/completions",
        api_key=None,
        engine="gpt-5",  # NOTE: Only used for document extraction, not model selection
        mode="global",
        preferences=None,
        languages=None,
        systemprompt=None,  # NOTE: Stored for backward compatibility but not used by Viventium
    ):
        self.user_id = user_id
        self.language = language
        self.languages = languages
        # REMOVED: Language selection - No longer setting language flags
        if self.languages is not None:
            self.languages[self.language] = True
        self.api_url = api_url
        self.api_key = api_key
        self.engine = engine  # Only for document extraction
        self.preferences = preferences
        # REMOVED: plugins - Plugins removed, Viventium handles tools
        self.systemprompt = systemprompt  # Stored but not used by Viventium
        self.users = NestedDict()
        # Initialize global config as a proper NestedDict (not a plain dict).
        # get_init_preferences() returns a plain dict; wrap it so .data is available
        # even when load_all_configs() finds no existing JSON files (fresh mount).
        global_config = NestedDict()
        global_config.data.update(self.get_init_preferences())
        global_config.data.update(self.preferences)
        self.users["global"] = global_config
        # REMOVED: plugins update - Plugins removed
        # REMOVED: languages update - Language selection removed
        if self.languages is not None:
            self.users["global"].data.update(self.languages)
        self.mode = mode
        self.load_all_configs()
        
        # CRITICAL: After loading configs from disk, re-ensure ALL required keys exist.
        # load_all_configs may replace self.users["global"] with data from a JSON file
        # that lacks init preferences (api_key, api_url, engine, systemprompt) or new
        # PREFERENCES added after the file was written.  Ensure self.users["global"]
        # is a NestedDict and merge any missing keys from defaults.
        global_changed = False
        if not isinstance(self.users.data.get("global"), NestedDict):
            existing = self.users.data.get("global", {})
            nd = NestedDict()
            if isinstance(existing, dict):
                nd.data.update(existing)
            self.users.data["global"] = nd
            global_changed = True
        for key, value in self.get_init_preferences().items():
            if key not in self.users["global"].data:
                self.users["global"][key] = value
                global_changed = True
        for pref_key, pref_value in self.preferences.items():
            if pref_key not in self.users["global"].data:
                self.users["global"][pref_key] = pref_value
                global_changed = True
        
        # CRITICAL: Use .data.keys() to avoid triggering __getitem__ auto-creation
        self.parameter_name_list = list(self.users["global"].data.keys())
        if global_changed:
            save_user_config("global", self.users["global"].data)


    def load_all_configs(self):
        if not os.path.exists(CONFIG_DIR):
            return

        for filename in os.listdir(CONFIG_DIR):
            if filename.endswith('.json'):
                user_id = filename[:-5]  # Remove '.json' suffix
                user_config = load_user_config(user_id)
                self.users[user_id] = NestedDict()
                user_changed = False

                # REMOVED: Plugin key mapping - Plugins removed, Viventium handles tools

                # Process configuration items normally
                for key, value in user_config.items():
                    self.users[user_id][key] = value
                    # Don't overwrite user-specific api_url and api_key - they may be provider-specific
                    # Only update global systemprompt if needed
                    if user_id == "global" and key == "systemprompt" and value != self.systemprompt:
                        self.users[user_id]["systemprompt"] = self.systemprompt
                        user_changed = True
                
                # CRITICAL: Add missing preferences from PREFERENCES dict (handles new preferences)
                # This ensures backward compatibility when new preferences are added
                # Use __contains__ or .data directly to avoid triggering NestedDict.__getitem__ auto-creation
                for pref_key, pref_value in self.preferences.items():
                    # Check if key exists using .data directly to avoid auto-creation
                    if pref_key not in self.users[user_id].data:
                        self.users[user_id][pref_key] = pref_value
                        user_changed = True

                if user_changed:
                    save_user_config(user_id, self.users[user_id].data)

    def get_init_preferences(self):
        return {
            "language": self.language,
            "engine": self.engine,
            "systemprompt": self.systemprompt,
            "api_key": self.api_key,
            "api_url": self.api_url,
        }

    def _persist_user_config(self, user_id):
        user_entry = self.users.data.get(user_id)
        if isinstance(user_entry, NestedDict):
            save_user_config(user_id, dict(user_entry.data))

    def user_init(self, user_id = None):
        if user_id == None or self.mode == "global":
            user_id = "global"
        self.user_id = user_id
        changed = False
        
        # CRITICAL: Ensure self.users[self.user_id] is always a NestedDict
        # Check .data directly to avoid triggering __getitem__ auto-creation
        if self.user_id in self.users.data:
            existing_config = self.users.data[self.user_id]
            # If it's a regular dict (from old code or corrupted state), convert it to NestedDict
            if not isinstance(existing_config, NestedDict):
                nested_config = NestedDict()
                nested_config.data.update(existing_config)
                self.users.data[self.user_id] = nested_config
                user_config = nested_config
                changed = True
            else:
                user_config = existing_config
        else:
            # Create new NestedDict for this user
            user_config = NestedDict()
            self.users.data[self.user_id] = user_config
            changed = True
        
        # Initialize with default preferences if empty
        if not user_config.data:
            init_prefs = self.get_init_preferences()
            user_config.data.update(init_prefs)
            user_config.data.update(self.preferences)
            # REMOVED: plugins update - Plugins removed
            # REMOVED: languages update - Language selection removed
            if self.languages is not None:
                user_config.data.update(self.languages)
            changed = True
        
        # CRITICAL: Ensure all current preferences exist (backward compatibility)
        # Add any missing preferences from PREFERENCES dict
        for pref_key, pref_value in self.preferences.items():
            if pref_key not in user_config.data:
                user_config.data[pref_key] = pref_value
                changed = True

        # === VIVENTIUM START ===
        # Feature: Normalize empty CLIENT_TIMEZONE to default when available.
        # Purpose: Ensure Telegram time context has a valid timezone without overfitting.
        current_timezone = user_config.data.get("CLIENT_TIMEZONE")
        if isinstance(current_timezone, str):
            current_timezone = current_timezone.strip()
        else:
            current_timezone = ""
        if not current_timezone:
            default_timezone = self.preferences.get("CLIENT_TIMEZONE", "")
            if isinstance(default_timezone, str):
                default_timezone = default_timezone.strip()
            else:
                default_timezone = ""
            if default_timezone:
                user_config.data["CLIENT_TIMEZONE"] = default_timezone
                changed = True
        # === VIVENTIUM END ===
        
        # Persist only when defaults/normalization changed to avoid Azure Files churn
        # on every get_config() hot-path call.
        if changed:
            self._persist_user_config(user_id)

    def get_config(self, user_id = None, parameter_name = None):
        # CRITICAL: Handle new preferences that might not be in parameter_name_list yet
        # This provides backward compatibility when new preferences are added
        if parameter_name not in self.parameter_name_list:
            # Check if it's a valid preference - if so, add it and return default
            if parameter_name in self.preferences:
                # Add to parameter_name_list for future use
                self.parameter_name_list.append(parameter_name)
                # Initialize for this user if needed
                if self.mode == "multiusers":
                    self.user_init(user_id)
                    # Use .data directly to avoid triggering NestedDict.__getitem__ auto-creation
                    if parameter_name not in self.users[self.user_id].data:
                        self.users[self.user_id][parameter_name] = self.preferences[parameter_name]
                        self._persist_user_config(self.user_id)
                    return self.users[self.user_id][parameter_name]
                else:
                    # Use .data directly to avoid triggering NestedDict.__getitem__ auto-creation
                    if parameter_name not in self.users["global"].data:
                        self.users["global"][parameter_name] = self.preferences[parameter_name]
                        self._persist_user_config("global")
                    return self.users["global"][parameter_name]
            else:
                raise ValueError(f"parameter_name {parameter_name} is not in the parameter_name_list: {self.parameter_name_list}")
        if self.mode == "global":
            return self.users["global"][parameter_name]
        if self.mode == "multiusers":
            self.user_init(user_id)
            return self.users[self.user_id][parameter_name]

    def set_config(self, user_id = None, parameter_name = None, value = None):
        # CRITICAL: Handle new preferences that might not be in parameter_name_list yet
        # This provides backward compatibility when new preferences are added
        if parameter_name not in self.parameter_name_list:
            # Check if it's a valid preference - if so, add it
            if parameter_name in self.preferences:
                self.parameter_name_list.append(parameter_name)
            else:
                raise ValueError(f"parameter_name {parameter_name} is not in the parameter_name_list: {self.parameter_name_list}")
        if self.mode == "global":
            current = self.users["global"].data.get(parameter_name)
            if current == value:
                return
            self.users["global"][parameter_name] = value
            self._persist_user_config("global")
        if self.mode == "multiusers":
            self.user_init(user_id)
            current = self.users[self.user_id].data.get(parameter_name)
            if current == value:
                return
            self.users[self.user_id][parameter_name] = value
            self._persist_user_config(self.user_id)
            # === VIVENTIUM START ===
            # Feature: Keep LibreChat scheduler voice preferences in sync with Telegram settings.
            if self.user_id != "global" and parameter_name in (
                "ALWAYS_VOICE_RESPONSE",
                "VOICE_RESPONSES_ENABLED",
            ):
                sync_voice_preferences(
                    self.user_id,
                    self.users[self.user_id].data.get("ALWAYS_VOICE_RESPONSE"),
                    self.users[self.user_id].data.get("VOICE_RESPONSES_ENABLED"),
                )
            # === VIVENTIUM END ===

    def toggle_config(self, user_id = None, parameter_name = None):
        if parameter_name not in self.parameter_name_list:
            if parameter_name in self.preferences:
                self.parameter_name_list.append(parameter_name)
            else:
                raise ValueError(
                    f"parameter_name {parameter_name} is not in the parameter_name_list: {self.parameter_name_list}"
                )
        default = self.preferences.get(parameter_name)
        if self.mode == "global":
            current_raw = self.users["global"].data.get(parameter_name, default)
            if isinstance(default, bool):
                current_bool = _coerce_bool(current_raw, default)
            else:
                current_bool = bool(current_raw)
            new_value = not current_bool
            self.users["global"][parameter_name] = new_value
            self._persist_user_config("global")
            return new_value
        if self.mode == "multiusers":
            self.user_init(user_id)
            current_raw = self.users[self.user_id].data.get(parameter_name, default)
            if isinstance(default, bool):
                current_bool = _coerce_bool(current_raw, default)
            else:
                current_bool = bool(current_raw)
            new_value = not current_bool
            self.users[self.user_id][parameter_name] = new_value
            self._persist_user_config(self.user_id)
            # === VIVENTIUM START ===
            # Feature: Keep LibreChat scheduler voice preferences in sync with Telegram settings.
            if self.user_id != "global" and parameter_name in (
                "ALWAYS_VOICE_RESPONSE",
                "VOICE_RESPONSES_ENABLED",
            ):
                sync_voice_preferences(
                    self.user_id,
                    self.users[self.user_id].data.get("ALWAYS_VOICE_RESPONSE"),
                    self.users[self.user_id].data.get("VOICE_RESPONSES_ENABLED"),
                )
            # === VIVENTIUM END ===
            return new_value
        raise ValueError(f"Unsupported mode: {self.mode}")

    # REMOVED: extract_plugins_config method - Plugins removed, Viventium handles tools

    def to_json(self, user_id=None):
        def nested_dict_to_dict(nd):
            if isinstance(nd, NestedDict):
                return {k: nested_dict_to_dict(v) for k, v in nd.data.items()}
            return nd

        if user_id:
            serializable_config = nested_dict_to_dict(self.users[user_id])
        else:
            serializable_config = nested_dict_to_dict(self.users)

        return json.dumps(serializable_config, ensure_ascii=False, indent=2)

    def __str__(self):
        return str(self.users)

# REMOVED: plugins parameter - Plugin selection removed, Viventium handles tools
Users = UserConfig(mode=CHAT_MODE, api_key=API_KEY, api_url=BASE_URL, engine=MODEL, preferences=PREFERENCES, language="English", languages=None, systemprompt=systemprompt)

# REMOVED: temperature - Not used, Viventium handles temperature settings

ChatGPTbot, whisperBot = None, None
local_whisper = None
# === VIVENTIUM START ===
# Feature: AssemblyAI STT option for Telegram voice transcription.
assemblyai_client = None
# === VIVENTIUM END ===
stt_engine_ready = False
stt_engine_chat_id = None


def InitEngine(chat_id=None, initialize_stt=True):
    global Users, ChatGPTbot, whisperBot
    global stt_engine_ready, stt_engine_chat_id
    # === VIVENTIUM START ===
    # Feature: AssemblyAI STT option for Telegram voice transcription.
    global assemblyai_client
    # === VIVENTIUM END ===
    api_key, api_url = resolve_api_whisper_config(
        Users.get_config(chat_id, "api_key"),
        Users.get_config(chat_id, "api_url"),
        API_KEY,
        BASE_URL,
    )
    whisper_api_url = os.environ.get("WHISPER_API_URL")
    if whisper_api_url:
        api_url = whisper_api_url
        if not api_key:
            api_key = os.environ.get("AZURE_OPENAI_API_KEY") or API_KEY
    
    # === VIVENTIUM START ===
    # Initialize Telegram bridge backend
    if ChatGPTbot is None:
        if VIVENTIUM_TELEGRAM_BACKEND == "librechat":
            from utils.librechat_bridge import LibreChatBridge
            librechat_conversation_state_version = "2"

            def get_conversation_id(convo_id):
                stored_version = str(
                    Users.get_config(convo_id, "LIBRECHAT_CONVERSATION_STATE_VERSION") or ""
                ).strip()
                if stored_version != librechat_conversation_state_version:
                    Users.set_config(convo_id, "LIBRECHAT_CONVERSATION_ID", "")
                    Users.set_config(
                        convo_id,
                        "LIBRECHAT_CONVERSATION_STATE_VERSION",
                        librechat_conversation_state_version,
                    )
                    return ""
                return Users.get_config(convo_id, "LIBRECHAT_CONVERSATION_ID") or ""

            def set_conversation_id(convo_id, value):
                Users.set_config(
                    convo_id,
                    "LIBRECHAT_CONVERSATION_STATE_VERSION",
                    librechat_conversation_state_version,
                )
                Users.set_config(convo_id, "LIBRECHAT_CONVERSATION_ID", value or "")

            def get_agent_id(convo_id):
                return Users.get_config(convo_id, "LIBRECHAT_AGENT_ID") or ""

            def set_agent_id(convo_id, value):
                Users.set_config(convo_id, "LIBRECHAT_AGENT_ID", value or "")

            ChatGPTbot = LibreChatBridge(
                get_conversation_id=get_conversation_id,
                set_conversation_id=set_conversation_id,
                get_agent_id=get_agent_id,
                set_agent_id=set_agent_id,
            )
        else:
            ChatGPTbot = LiveKitBridge()
    # === VIVENTIUM END ===
        # REMOVED: SummaryBot - Not used with LiveKit Bridge architecture

    if not initialize_stt:
        return

    if stt_engine_ready and stt_engine_chat_id == chat_id:
        return

    global local_whisper
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Initializing Whisper engine, mode={WHISPER_MODE}, api_key={'set' if api_key else 'not set'}, api_url={api_url}")
    
    # Match standalone pattern exactly: use "local" mode (accept "pywhispercpp" as alias)
    # Enhanced with auto-download like viventium_v1 for better UX
    if WHISPER_MODE in ("local", "pywhispercpp"):
        try:
            from pywhispercpp.model import Model
            from pathlib import Path

            # Auto-download model if path not specified (like viventium_v1)
            model_path = LOCAL_WHISPER_MODEL_PATH
            if not model_path or model_path == "/path/to/your/ggml-model.bin":
                # Default model name
                model_name = os.environ.get("LOCAL_WHISPER_MODEL_NAME", "large-v3-turbo")
                
                # Map model names to filenames (matches viventium_v1)
                model_map = {
                    "tiny": "ggml-tiny.bin",
                    "base": "ggml-base.bin", 
                    "small": "ggml-small.bin",
                    "medium": "ggml-medium.bin",
                    "large": "ggml-large.bin",
                    "large-v1": "ggml-large-v1.bin",
                    "large-v2": "ggml-large-v2.bin",
                    "large-v3": "ggml-large-v3.bin",
                    "large-v3-turbo": "ggml-large-v3-turbo.bin",
                }
                
                filename = model_map.get(model_name, "ggml-large-v3-turbo.bin")
                model_dir = Path.home() / ".cache" / "whisper"
                model_dir.mkdir(parents=True, exist_ok=True)
                model_path = str(model_dir / filename)
                
                # Download if not exists
                if not Path(model_path).exists():
                    logger.info(f"Downloading Whisper model {model_name} to {model_path}")
                    import urllib.request
                    url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{filename}"
                    urllib.request.urlretrieve(url, model_path)
                    logger.info(f"Downloaded {model_name} successfully")
                else:
                    logger.info(f"Using cached Whisper model: {model_path}")

            logger.info(f"Loading Whisper model from {model_path} with {LOCAL_WHISPER_THREADS} threads")
            local_whisper = Model(model_path, n_threads=LOCAL_WHISPER_THREADS)
            whisperBot = None
            stt_engine_ready = True
            stt_engine_chat_id = chat_id
            logger.info("Local Whisper model initialized successfully")
            # === VIVENTIUM START ===
            # Feature: AssemblyAI STT option for Telegram voice transcription.
            assemblyai_client = None
            # === VIVENTIUM END ===
        except Exception as e:
            logger.exception(f"Failed to initialize local Whisper model: {e}")
            raise RuntimeError(f"Failed to initialize local Whisper model: {e}")
    # === VIVENTIUM START ===
    # Feature: AssemblyAI STT option for Telegram voice transcription.
    elif WHISPER_MODE == "assemblyai":
        try:
            from aient.aient.models.assemblyai import AssemblyAI

            if not ASSEMBLYAI_API_KEY:
                logger.warning("No ASSEMBLYAI_API_KEY provided; AssemblyAI client will not be initialized")
                assemblyai_client = None
            else:
                assemblyai_client = AssemblyAI(api_key=ASSEMBLYAI_API_KEY, base_url=ASSEMBLYAI_BASE_URL)
                logger.info("AssemblyAI client initialized successfully")
            whisperBot = None
            local_whisper = None
            stt_engine_ready = True
            stt_engine_chat_id = chat_id
        except Exception as e:
            logger.exception(f"Failed to initialize AssemblyAI client: {e}")
            raise RuntimeError(f"Failed to initialize AssemblyAI client: {e}")
    # === VIVENTIUM END ===
    else:
        # Keep Whisper for voice note transcription
        logger.info("Initializing API Whisper client")
        if api_key:
            try:
                whisperBot = whisper(api_key=api_key, api_url=api_url)
                logger.info("API Whisper client initialized successfully")
                stt_engine_ready = True
                stt_engine_chat_id = chat_id
            except Exception as e:
                logger.exception(f"Failed to initialize API Whisper client: {e}")
                whisperBot = None
        else:
            logger.warning("No API key provided, Whisper API client will not be initialized")
            whisperBot = None
        local_whisper = None
        # === VIVENTIUM START ===
        # Feature: AssemblyAI STT option for Telegram voice transcription.
        assemblyai_client = None
        # === VIVENTIUM END ===


def ensure_stt_engine(chat_id=None):
    if stt_engine_ready:
        return
    InitEngine(chat_id=chat_id, initialize_stt=True)

# REMOVED: update_language_status() - Language selection removed, using English-only UI

InitEngine(chat_id=None, initialize_stt=False)
# REMOVED: update_language_status() call - Language selection removed

# REMOVED: Version check functions - Checked the wrong upstream GitHub repo
# If version checking is needed, implement with correct repository URL

def replace_with_asterisk(string):
    if string:
        if len(string) <= 4:  # If string length is less than or equal to 4, don't replace
            return string[0] + '*' * 10
        else:
            return string[:10] + '*' * 10 + string[-2:]
    else:
        return None

def update_info_message(user_id = None):
    # REMOVED: api_key and api_url - Not used with LiveKit Bridge, Viventium handles all API calls
    return "".join([
        f"**🧠 Cognitive System:** `Viventium`\n\n",  # Viventium is the cognitive system
        # REMOVED: API_KEY display - Not used with LiveKit Bridge, Viventium handles API keys
        # REMOVED: BASE URL display - Not used with LiveKit Bridge, Viventium handles endpoints
        f"**🛜 WEB HOOK:** `{WEB_HOOK}`\n\n" if WEB_HOOK else "",
        # REMOVED: Tokens usage - LiveKitBridge doesn't track tokens, Viventium handles this
        f"**🃏 NICK:** `{NICK}`\n\n" if NICK else "",
        # REMOVED: Version check - Checks wrong GitHub repo, removed to avoid confusion
    ])

def reset_ENGINE(chat_id, message=None):
    global ChatGPTbot
    # REMOVED: system_prompt parameter - LiveKitBridge.reset() ignores it, Viventium handles system prompts
    # REMOVED: message parameter - System prompts handled by Viventium, not stored locally
    if ChatGPTbot:
        ChatGPTbot.reset(convo_id=str(chat_id))

def get_robot(chat_id = None):
    """
    Get robot instance and API credentials.
    
    NOTE: With LiveKit Bridge architecture, model selection is handled by Viventium agent.
    This function only returns API keys for residual features (voice transcription, image/document processing).
    The main chat flow uses LiveKit Bridge which doesn't need these API keys.
    """
    global ChatGPTbot
    engine = Users.get_config(chat_id, "engine")
    role = "user"
    robot = ChatGPTbot
    api_key = Users.get_config(chat_id, "api_key")
    api_url = Users.get_config(chat_id, "api_url")
    
    # SIMPLIFIED: No longer switch API keys based on model selection.
    # Viventium agent handles model selection and API routing.
    # Only use default API key/URL for residual features (Whisper, image processing).
    # Default to OpenAI-compatible API for Whisper and vision features.
    if not api_url or api_url == "":
        api_url = "https://api.openai.com/v1"
    else:
        # Ensure we have a valid chat URL format
        api_url = BaseAPI(api_url=api_url).chat_url

    return robot, role, api_key, api_url

whitelist = os.environ.get('whitelist', None)
if whitelist == "":
    whitelist = None
if whitelist:
    whitelist = [id for id in whitelist.split(",")]

BLACK_LIST = os.environ.get('BLACK_LIST', None)
if BLACK_LIST == "":
    BLACK_LIST = None
if BLACK_LIST:
    BLACK_LIST = [id for id in BLACK_LIST.split(",")]

ADMIN_LIST = os.environ.get('ADMIN_LIST', None)
if ADMIN_LIST == "":
    ADMIN_LIST = None
if ADMIN_LIST:
    ADMIN_LIST = [id for id in ADMIN_LIST.split(",")]
GROUP_LIST = os.environ.get('GROUP_LIST', None)
if GROUP_LIST == "":
    GROUP_LIST = None
if GROUP_LIST:
    GROUP_LIST = [id for id in GROUP_LIST.split(",")]

# REMOVED: delete_model_digit_tail function - Only used for model display which is removed

def get_status(chatid = None, item = None):
    # Custom labels for better UX
    value = Users.get_config(chatid, item)
    default = PREFERENCES.get(item)
    if isinstance(default, bool):
        enabled = _coerce_bool(value, default)
    else:
        enabled = bool(value)
    return "✅ " if enabled else "☑️ "

# English display names for preferences (removed i18n)
PREFERENCE_DISPLAY_NAMES = {
    "LONG_TEXT": "Long text merge",
    "LONG_TEXT_SPLIT": "Long text split",
    "FILE_UPLOAD_MESS": "File upload message",
    # === VIVENTIUM START ===
    # Feature: Explicit voice reply toggle in Preferences.
    "VOICE_RESPONSES_ENABLED": "Voice replies",
    # === VIVENTIUM END ===
    "ALWAYS_VOICE_RESPONSE": "Always Voice",  # User-friendly label for voice response toggle
}

def create_buttons(strings, plugins_status=False, lang="en", button_text=None, Suffix="", chatid=None, status_map=None):
    # SIMPLIFIED: Removed i18n - Using English-only display names
    strings_array = {kv:kv for kv in strings}

    # Create display name mapping
    if not button_text:
        button_text = {}
        for k in strings_array.keys():
            display_name = PREFERENCE_DISPLAY_NAMES.get(k, k.replace("_", " ").title())
            button_text[k] = display_name
    
    # Filter by length (for button grouping)
    filtered_strings1 = {k:v for k, v in strings_array.items() if k in button_text and len(button_text[k]) <= 14}
    filtered_strings2 = {k:v for k, v in strings_array.items() if k in button_text and len(button_text[k]) > 14}

    buttons = []
    temp = []

    for k, v in filtered_strings1.items():
        if plugins_status:
            if status_map is not None and k in status_map:
                default = PREFERENCES.get(k)
                if isinstance(default, bool):
                    enabled = _coerce_bool(status_map.get(k), default)
                else:
                    enabled = bool(status_map.get(k))
                prefix = "✅ " if enabled else "☑️ "
            else:
                prefix = get_status(chatid, k)
            button = InlineKeyboardButton(f"{prefix}{button_text[k]}", callback_data=k + Suffix)
        else:
            display_text = button_text.get(k, k)  # Use display name or key
            button = InlineKeyboardButton(display_text, callback_data=v + Suffix)
        temp.append(button)

        # Group every two buttons
        if len(temp) == 2:
            buttons.append(temp)
            temp = []

    # If last group has less than two, add it anyway
    if temp:
        buttons.append(temp)

    for k, v in filtered_strings2.items():
        if plugins_status:
            if status_map is not None and k in status_map:
                default = PREFERENCES.get(k)
                if isinstance(default, bool):
                    enabled = _coerce_bool(status_map.get(k), default)
                else:
                    enabled = bool(status_map.get(k))
                prefix = "✅ " if enabled else "☑️ "
            else:
                prefix = get_status(chatid, k)
            button = InlineKeyboardButton(f"{prefix}{button_text[k]}", callback_data=k + Suffix)
        else:
            display_text = button_text.get(k, k)  # Use display name or key
            button = InlineKeyboardButton(display_text, callback_data=v + Suffix)
        buttons.append([button])

    return buttons

# REMOVED: All model-related code - Model selection removed, Viventium handles models
# Removed: initial_model, MODEL_GROUPS, CUSTOM_MODELS_LIST, remove_no_text_model(),
# get_all_available_models(), get_model_groups(), get_models_in_group()
# These were used for model selection UI which is no longer needed

def get_current_lang(chatid=None):
    # REMOVED: Language selection - Always return English
    return "en"

# REMOVED: update_models_buttons() - Model selection UI removed, Viventium handles models
# This function created model selection buttons which are no longer needed

def update_first_buttons_message(chatid=None):
    # REMOVED: Language selection button - Using English-only UI
    first_buttons = []
    call_url = get_telegram_call_url(chatid) if chatid is not None else ""
    if call_url:
        first_buttons.append([InlineKeyboardButton("Call Viventium", url=call_url)])
    first_buttons.append(
        [
            # REMOVED: Model selection button - Models handled by Viventium
            InlineKeyboardButton("Preferences", callback_data="PREFERENCES"),
        ]
    )
    # REMOVED: Language button - Using English-only UI
    return first_buttons

def update_menu_buttons(setting, _strings, chatid):
    # === VIVENTIUM START ===
    # Only show boolean toggle preferences as buttons.  String preferences like
    # LIBRECHAT_CONVERSATION_ID, LIBRECHAT_CONVERSATION_STATE_VERSION,
    # LIBRECHAT_AGENT_ID, CLIENT_TIMEZONE are internal
    # metadata and should not appear in the Preferences UI.
    toggle_keys = [k for k, v in setting.items() if isinstance(v, bool)]
    # === VIVENTIUM END ===
    status_map = None
    if chatid is not None:
        try:
            Users.user_init(chatid)
            user_data = Users.users[Users.user_id].data
            status_map = {k: user_data.get(k, setting.get(k, False)) for k in toggle_keys}
        except Exception:
            status_map = None
    buttons = create_buttons(
        toggle_keys,
        plugins_status=True,
        lang="en",
        button_text=None,
        chatid=chatid,
        Suffix=_strings,
        status_map=status_map,
    )
    buttons.append(
        [
            InlineKeyboardButton("⬅️ Back", callback_data="BACK"),
        ],
    )
    return buttons
