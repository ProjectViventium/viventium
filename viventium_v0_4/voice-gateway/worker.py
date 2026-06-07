# === VIVENTIUM START ===
# Feature: LibreChat Voice Calls - LiveKit Voice Gateway worker
# Added: 2026-01-08
#
# Purpose:
# - Register a LiveKit agent worker under `LIVEKIT_AGENT_NAME` (explicit dispatch).
# - On dispatch, extract `callSessionId` from `ctx.job.metadata`.
# - Use LiveKit STT + TTS, but use LibreChat as the LLM via `LibreChatLLM`.
# === VIVENTIUM END ===

from __future__ import annotations

import asyncio
import inspect
import importlib.util
import json
import logging
import math
import os
import platform
import sys
import time
import threading
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer
from dataclasses import dataclass, replace
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

import aiohttp

from livekit.agents import (
    APIConnectionError,
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    JobProcess,
    TurnHandlingOptions,
    WorkerOptions,
    cli,
    tokenize,
)
from livekit.agents.worker import WorkerType
from livekit.plugins import openai

try:
    from livekit.plugins import xai as xai_plugin
    HAS_XAI_TTS = True
except ImportError:
    HAS_XAI_TTS = False
    xai_plugin = None

# === VIVENTIUM START ===
# Feature: Text transcripts must still surface when TTS fails.
# Purpose: LiveKit RoomIO defaults to syncing transcript output to audio playout. If TTS fails
# (no audio frames), the modern playground can appear "stuck" with no visible assistant text.
# We allow disabling transcript sync so text is published as soon as LLM deltas arrive.
from livekit.agents.voice import room_io
from livekit.agents.voice.io import TimedString
# === VIVENTIUM END ===

# === VIVENTIUM START ===
# Feature: AssemblyAI STT support (v1 parity)
# Added: 2026-01-11
# === VIVENTIUM END ===
try:
    from livekit.plugins.assemblyai import stt as assemblyai_stt
    HAS_ASSEMBLYAI = True
except ImportError:
    HAS_ASSEMBLYAI = False
    assemblyai_stt = None

try:
    from livekit.plugins import silero as silero_vad
    HAS_SILERO = True
except ImportError:
    HAS_SILERO = False
    silero_vad = None


def optional_module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


HAS_TURN_DETECTOR = optional_module_available("livekit.plugins.turn_detector.multilingual")
_TURN_DETECTOR_RUNNER_NAME = "lk_end_of_utterance_multilingual"
_LOCAL_WHISPER_STT_PROVIDERS = {"pywhispercpp", "whisper_local"}
_LOCAL_WHISPER_VAD_MIN_SPEECH_S = "0.35"
_LOCAL_WHISPER_VAD_MIN_SILENCE_S = "0.5"
_DEFAULT_AEC_WARMUP_DURATION_S = 3.0
_LOCAL_WHISPER_AEC_WARMUP_DURATION_S = 1.0
_LOCAL_WHISPER_MODELS = (
    "tiny.en",
    "base.en",
    "small",
    "small.en",
    "medium",
    "medium.en",
    "large-v3",
    "large-v3-q5_0",
    "large-v3-turbo",
    "large-v3-turbo-q5_0",
)
_TURN_DETECTOR_REQUIRED_ROOT_FILES = (
    "config.json",
    "languages.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
)

# Optional import - handle gracefully if elevenlabs is not available
try:
    from livekit.plugins import elevenlabs
    HAS_ELEVENLABS = True
except ImportError:
    HAS_ELEVENLABS = False
    elevenlabs = None

from librechat_llm import LibreChatAuth, LibreChatLLM
from sse import VoiceControlDisplayFilter, sanitize_voice_followup_text
from cartesia_tts import (
    CARTESIA_VOICE_PRESETS,
    DEFAULT_MODEL_ID as DEFAULT_CARTESIA_MODEL_ID,
    DEFAULT_VERSION as DEFAULT_CARTESIA_API_VERSION,
    DEFAULT_VOICE_ID as DEFAULT_CARTESIA_VOICE_ID,
    CartesiaConfig,
    CartesiaTTS,
)
from local_chatterbox_config import (
    build_local_chatterbox_config as shared_build_local_chatterbox_config,
    validate_ref_audio_path as shared_validate_ref_audio_path,
)
from xai_grok_voice_tts import XaiGrokVoiceConfig, XaiGrokVoiceTTS
# === VIVENTIUM START ===
# Feature: Shared Silero VAD config parity across voice STT paths.
from silero_vad_config import get_silero_vad_kwargs
# === VIVENTIUM END ===
# === VIVENTIUM START ===
# Feature: Local Chatterbox Turbo (MLX) TTS provider (macOS-only).
from mlx_chatterbox_tts import MlxChatterboxConfig, MlxChatterboxTTS
# === VIVENTIUM END ===
from fallback_tts import FallbackTTS, ProviderAttempt

logger = logging.getLogger("voice-gateway")

_XAI_TTS_CAPABILITIES_PATH = Path(__file__).resolve().parent.parent / "shared" / "voice" / "xai_tts_capabilities.json"


def _load_xai_tts_capabilities() -> dict[str, Any]:
    try:
        with _XAI_TTS_CAPABILITIES_PATH.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        if isinstance(value, dict):
            return value
    except Exception:
        logger.exception("Failed to load xAI TTS capability contract from %s", _XAI_TTS_CAPABILITIES_PATH)
    return {
        "defaults": {"voice_id": "Sal", "language": "en", "livekit_sample_rate": 24000},
        "voices": [{"id": "Sal", "label": "Sal"}],
        "endpoints": {"websocket": "wss://api.x.ai/v1/tts"},
    }


XAI_TTS_CAPABILITIES = _load_xai_tts_capabilities()
XAI_TTS_DEFAULTS = XAI_TTS_CAPABILITIES.get("defaults", {}) if isinstance(XAI_TTS_CAPABILITIES.get("defaults"), dict) else {}
XAI_TTS_ENDPOINTS = XAI_TTS_CAPABILITIES.get("endpoints", {}) if isinstance(XAI_TTS_CAPABILITIES.get("endpoints"), dict) else {}
XAI_TTS_DISPLAY_LABEL = str(XAI_TTS_CAPABILITIES.get("display_label") or "xAI").strip() or "xAI"
XAI_TTS_VOICE_PRESETS = [
    (
        str(voice.get("id") or "").strip(),
        str(voice.get("label") or voice.get("id") or "").strip(),
    )
    for voice in (XAI_TTS_CAPABILITIES.get("voices") or [])
    if isinstance(voice, dict) and str(voice.get("id") or "").strip()
]
DEFAULT_XAI_TTS_VOICE = str(XAI_TTS_DEFAULTS.get("voice_id") or "Sal").strip() or "Sal"
DEFAULT_XAI_TTS_LANGUAGE = str(XAI_TTS_DEFAULTS.get("language") or "en").strip() or "en"
DEFAULT_XAI_TTS_WS_URL = str(XAI_TTS_ENDPOINTS.get("websocket") or "wss://api.x.ai/v1/tts").strip() or "wss://api.x.ai/v1/tts"
DEFAULT_XAI_TTS_SAMPLE_RATE = int(float(XAI_TTS_DEFAULTS.get("livekit_sample_rate") or 24000))
_DEFAULT_XAI_TTS_OPTIMIZE_STREAMING_LATENCY_RAW = XAI_TTS_DEFAULTS.get(
    "optimize_streaming_latency"
)
DEFAULT_XAI_TTS_OPTIMIZE_STREAMING_LATENCY = int(
    float(
        _DEFAULT_XAI_TTS_OPTIMIZE_STREAMING_LATENCY_RAW
        if _DEFAULT_XAI_TTS_OPTIMIZE_STREAMING_LATENCY_RAW not in (None, "")
        else 1
    )
)

_TERMINAL_GLASSHIVE_CALLBACK_EVENTS = {
    "run.completed",
    "run.failed",
    "run.cancelled",
    "run.interrupted",
    "checkpoint.ready",
    "takeover.requested",
}


def _glasshive_callback_is_terminal(latest: dict[str, Any]) -> bool:
    event = str(latest.get("event") or "").strip()
    return not event or event in _TERMINAL_GLASSHIVE_CALLBACK_EVENTS


def _voice_followup_tts_max_chars() -> int:
    try:
        configured = int((os.getenv("VIVENTIUM_VOICE_FOLLOWUP_TTS_MAX_CHARS") or "").strip())
    except Exception:
        configured = 2400
    return max(500, min(configured or 2400, 8000))


def cap_voice_followup_for_tts(text: str) -> str:
    value = str(text or "").strip()
    limit = _voice_followup_tts_max_chars()
    if len(value) <= limit:
        return value
    tail = "\n\nI have the full report in the chat."
    budget = max(100, limit - len(tail) - 3)
    return f"{value[:budget].rstrip()}...{tail}"

# === VIVENTIUM START ===
# Feature: No-response tag ({NTA}) suppression for passive/background follow-ups.
_SHARED_PATH = Path(__file__).resolve().parent.parent / "shared"  # .../viventium_v0_4/shared
if str(_SHARED_PATH) not in sys.path:
    sys.path.insert(0, str(_SHARED_PATH))

try:
    from no_response import contains_no_response_tag, is_no_response_only, strip_inline_nta
except Exception:
    import re

    _NO_RESPONSE_TAG_RE = re.compile(r"^\s*\{\s*NTA\s*\}\s*$", re.IGNORECASE)
    _NO_RESPONSE_PHRASES = {
        "nothing new to add.",
        "nothing new to add",
        "nothing to add.",
        "nothing to add",
    }
    _NO_RESPONSE_VARIANT_MAX_LEN = 200
    _NO_RESPONSE_VARIANT_RE = re.compile(
        r"^\s*nothing\s+(?:new\s+)?to\s+add"
        r"(?:\s*(?:\(\s*)?(?:right\s+now|for\s+now|at\s+this\s+time|at\s+the\s+moment|currently|so\s+far|yet|today)(?:\s*\))?)?"
        r"(?:\s*,?\s*(?:sorry|thanks|thank\s+you))?"
        r"\s*[.!?]*\s*$",
        re.IGNORECASE,
    )

    def is_no_response_only(text: Optional[str]) -> bool:
        if not isinstance(text, str):
            return False
        trimmed = text.strip()
        if not trimmed:
            return False
        if _NO_RESPONSE_TAG_RE.match(trimmed):
            return True
        lowered = trimmed.lower()
        if lowered in _NO_RESPONSE_PHRASES:
            return True
        if len(trimmed) <= _NO_RESPONSE_VARIANT_MAX_LEN and _NO_RESPONSE_VARIANT_RE.match(trimmed):
            return True
        return False

    def contains_no_response_tag(text: Optional[str]) -> bool:
        if not isinstance(text, str):
            return False
        return bool(re.search(r"\{\s*NTA\s*\}", text, flags=re.IGNORECASE))

    def strip_inline_nta(text: Optional[str]) -> str:
        if not isinstance(text, str):
            return text or ""
        cleaned = re.sub(r"\{\s*NTA\s*\}", " ", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        cleaned = re.sub(r"\s+\n", "\n", cleaned)
        cleaned = re.sub(r"\n\s+", "\n", cleaned)
        return cleaned.strip()

# === VIVENTIUM END ===


_TERMINAL_CORTEX_FOLLOWUP_DECISION_RESULTS = {"suppressed", "empty", "skipped"}


def _terminal_cortex_followup_decision(decision: Any) -> Optional[dict[str, Any]]:
    if not isinstance(decision, dict):
        return None
    result = str(decision.get("result") or "").strip().lower()
    if result in _TERMINAL_CORTEX_FOLLOWUP_DECISION_RESULTS:
        return decision
    return None


@dataclass(frozen=True)
class Env:
    livekit_agent_name: str
    librechat_origin: str
    call_session_secret: str

    # STT/TTS provider knobs
    stt_provider: str
    stt_model: str
    stt_language: str
    openai_stt_model: str
    tts_provider: str  # "elevenlabs" | "openai" | "xai" | "cartesia" | "local_chatterbox_turbo_mlx_8bit"
    # Optional runtime fallback provider if the primary provider errors.
    # Example: primary=cartesia, fallback=elevenlabs
    tts_provider_fallback: str  # "" | "elevenlabs" | "openai" | "xai" | "cartesia" | "local_chatterbox_turbo_mlx_8bit"

    # xAI standalone TTS settings, with an explicit legacy Voice Agent mode.
    xai_tts_api: str
    xai_tts_api_key: str
    xai_voice: str
    xai_language: str
    xai_tts_ws_url: str
    xai_tts_optimize_streaming_latency: int
    xai_wss_url: str
    xai_sample_rate: int
    xai_instructions: str

    # ElevenLabs settings
    elevenlabs_voice_id: str
    # Optional fallback voice id used when the primary voice_id is not permitted / errors.
    # This is especially useful when the default v1 voice is an IVC/cloned voice that may be blocked
    # by the current ElevenLabs subscription tier.
    elevenlabs_voice_id_fallback: str
    elevenlabs_voice_stability: float
    elevenlabs_voice_similarity_boost: float
    elevenlabs_voice_style: float
    elevenlabs_voice_speed: float
    # OpenAI TTS settings (fallback)
    openai_tts_model: str
    openai_tts_voice: str
    openai_tts_speed: float
    openai_tts_instructions: str
    # Cartesia TTS settings
    cartesia_api_url: str
    cartesia_ws_url: str
    cartesia_api_version: str
    cartesia_model_id: str
    cartesia_voice_id: str
    cartesia_sample_rate: int
    cartesia_speed: float
    cartesia_volume: float
    cartesia_emotion: str
    cartesia_max_buffer_delay_ms: int
    # === VIVENTIUM START ===
    # Feature: per-emotion segment silence (Cartesia)
    cartesia_segment_silence_ms: int
    cartesia_language: str
    # === VIVENTIUM END ===

    # Local Chatterbox (MLX) model settings
    mlx_audio_model_id: str

    # === VIVENTIUM START ===
    # Feature: non-blocking voice follow-up polling
    voice_followup_timeout_s: float
    voice_followup_interval_s: float
    voice_followup_grace_s: float
    voice_glasshive_timeout_s: float
    voice_initialize_process_timeout_s: float
    voice_idle_processes: int
    voice_worker_load_threshold: float
    voice_job_memory_warn_mb: float
    voice_job_memory_limit_mb: float
    voice_prewarm_local_tts: bool
    voice_requested_turn_detection: str
    voice_turn_detection: str
    voice_configured_min_interruption_words: Optional[int]
    voice_configured_min_endpointing_delay_s: Optional[float]
    voice_configured_max_endpointing_delay_s: Optional[float]
    voice_configured_min_consecutive_speech_delay_s: Optional[float]
    voice_min_interruption_duration_s: float
    voice_min_interruption_words: int
    voice_min_endpointing_delay_s: float
    voice_max_endpointing_delay_s: float
    voice_false_interruption_timeout_s: Optional[float]
    voice_resume_false_interruption: bool
    voice_min_consecutive_speech_delay_s: float
    voice_aec_warmup_duration_s: Optional[float]
    assemblyai_stt_model: str
    assemblyai_end_of_turn_confidence_threshold: Optional[float]
    assemblyai_min_end_of_turn_silence_when_confident_ms: Optional[int]
    assemblyai_max_turn_silence_ms: Optional[int]
    assemblyai_format_turns: bool
    # === VIVENTIUM END ===


# === VIVENTIUM START ===
# Feature: Shared float env parsing for voice follow-ups
def _parse_float_env(name: str, fallback: float) -> float:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return fallback
    try:
        value = float(raw)
    except ValueError:
        return fallback
    if value < 0 or value == float("inf"):
        return fallback
    return value
# === VIVENTIUM END ===


def _parse_worker_load_threshold_env(name: str, fallback: float) -> float:
    raw = (os.getenv(name, "") or "").strip().lower()
    if not raw:
        return fallback
    if raw in {"inf", "infinity", "unlimited", "off", "none", "disabled"}:
        return math.inf
    try:
        value = float(raw)
    except ValueError:
        return fallback
    if value < 0:
        return fallback
    return value


def _parse_int_env(name: str, fallback: int) -> int:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return fallback
    try:
        value = int(float(raw))
    except ValueError:
        return fallback
    return value


def _parse_optional_float_env(name: str) -> Optional[float]:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if value < 0 or value == float("inf"):
        return None
    return value


def _parse_optional_int_env(name: str) -> Optional[int]:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return None
    try:
        value = int(float(raw))
    except ValueError:
        return None
    if value < 0:
        return None
    return value


def _parse_optional_timeout_env(name: str, fallback: Optional[float]) -> Optional[float]:
    raw = (os.getenv(name, "") or "").strip().lower()
    if not raw:
        return fallback
    if raw in {"off", "none", "false", "disabled"}:
        return None
    try:
        value = float(raw)
    except ValueError:
        return fallback
    if value < 0 or value == float("inf"):
        return fallback
    return value


def _cartesia_model_id_from_env() -> str:
    configured = (os.getenv("VIVENTIUM_CARTESIA_MODEL_ID", "") or "").strip()
    if configured and configured != DEFAULT_CARTESIA_MODEL_ID:
        logger.warning(
            "Ignoring unsupported Cartesia model_id=%s; voice calls always use %s",
            configured,
            DEFAULT_CARTESIA_MODEL_ID,
        )
    return DEFAULT_CARTESIA_MODEL_ID


# === VIVENTIUM START ===
# Feature: Shared bool env parsing for VAD/STT controls
def _parse_bool_env(name: str, fallback: bool) -> bool:
    raw = (os.getenv(name, "") or "").strip().lower()
    if not raw:
        return fallback
    return raw in {"1", "true", "yes", "y", "on"}
# === VIVENTIUM END ===


def _voice_latency_log_enabled() -> bool:
    return _parse_bool_env("VIVENTIUM_VOICE_LOG_LATENCY", False)


def _voice_worker_run_id() -> str:
    return (os.getenv("VIVENTIUM_VOICE_WORKER_RUN_ID", "") or "default").strip()


def _voice_coordination_dir() -> Path:
    run_id = _voice_worker_run_id()
    safe_run_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in run_id)
    return Path(os.getenv("TMPDIR", "/tmp")) / "viventium-voice-gateway" / safe_run_id


def _voice_active_jobs_dir() -> Path:
    path = _voice_coordination_dir() / "active-jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _mark_active_voice_job(job_id: str) -> Path:
    safe_job_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in job_id)
    marker = _voice_active_jobs_dir() / f"{os.getpid()}-{safe_job_id or 'job'}.active"
    try:
        marker.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        logger.debug("[voice-gateway] Unable to write active voice job marker", exc_info=True)
    return marker


def _clear_active_voice_job_marker(marker: Path) -> None:
    try:
        marker.unlink(missing_ok=True)
    except OSError:
        logger.debug("[voice-gateway] Unable to remove active voice job marker", exc_info=True)


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _active_voice_job_markers() -> list[Path]:
    active_dir = _voice_active_jobs_dir()
    stale_after_s = _parse_float_env("VIVENTIUM_VOICE_ACTIVE_JOB_MARKER_TTL_S", 3600.0)
    now = time.time()
    active: list[Path] = []
    for marker in active_dir.glob("*.active"):
        try:
            pid = int(marker.name.split("-", 1)[0])
        except (ValueError, IndexError):
            marker.unlink(missing_ok=True)
            continue
        age_s = now - marker.stat().st_mtime
        if age_s > stale_after_s or not _pid_is_alive(pid):
            marker.unlink(missing_ok=True)
            continue
        active.append(marker)
    return active


def _wait_for_active_voice_jobs_before_prewarm() -> None:
    max_wait_s = _parse_float_env(
        "VIVENTIUM_VOICE_REPLACEMENT_PREWARM_MAX_WAIT_S",
        20.0,
    )
    if max_wait_s <= 0:
        return

    started = time.monotonic()
    logged = False
    while _active_voice_job_markers():
        elapsed = time.monotonic() - started
        if elapsed >= max_wait_s:
            logger.info(
                "[voice-gateway] Replacement prewarm waited %.1fs for active calls; continuing so the worker keeps a spare process.",
                elapsed,
            )
            return
        if not logged:
            logger.info(
                "[voice-gateway] Delaying replacement local-model prewarm while an active voice call is running."
            )
            logged = True
        time.sleep(0.25)


def _normalize_turn_detection(mode: str) -> str:
    normalized = (mode or "").strip().lower()
    if normalized in {"turn_detector", "semantic", "semantic_turn_detector", "multilingual"}:
        return "turn_detector"
    if normalized in {"stt", "vad", "realtime_llm", "manual"}:
        return normalized
    return ""


def _supports_stt_endpointing(provider: str) -> bool:
    return _normalize_stt_provider(provider) == "assemblyai"


def _is_local_whisper_stt(provider: str) -> bool:
    return _normalize_stt_provider(provider) in _LOCAL_WHISPER_STT_PROVIDERS


def _supports_semantic_turn_detector(provider: str) -> bool:
    normalized_provider = _normalize_stt_provider(provider)
    return _supports_stt_endpointing(normalized_provider) or _is_local_whisper_stt(
        normalized_provider
    )


def _turn_detector_uses_remote_inference() -> bool:
    return bool((os.getenv("LIVEKIT_REMOTE_EOT_URL", "") or "").strip())


def _turn_detector_runner_registered() -> bool:
    if _turn_detector_uses_remote_inference():
        return True
    try:
        from livekit.agents.inference_runner import _InferenceRunner

        return _TURN_DETECTOR_RUNNER_NAME in _InferenceRunner.registered_runners
    except Exception:
        return False


def _ensure_turn_detector_runner_registered() -> bool:
    if not HAS_TURN_DETECTOR:
        return False
    if _turn_detector_uses_remote_inference():
        return True
    if not _turn_detector_model_is_cached():
        return False
    if _turn_detector_runner_registered():
        return True
    try:
        import livekit.plugins.turn_detector.multilingual  # noqa: F401
    except Exception as exc:
        logger.warning(
            "Unable to import LiveKit multilingual turn detector before worker start: %s",
            exc,
        )
        return False
    return _turn_detector_runner_registered()


def _semantic_turn_detector_status(provider: str) -> tuple[bool, str]:
    normalized_provider = _normalize_stt_provider(provider)
    if not HAS_TURN_DETECTOR:
        return False, "plugin_missing"
    if not _supports_semantic_turn_detector(normalized_provider):
        return False, "unsupported_stt_provider"
    if _turn_detector_uses_remote_inference():
        return True, "remote_inference"
    if not _turn_detector_model_is_cached():
        return False, "model_weights_missing"
    if _ensure_turn_detector_runner_registered():
        return True, "local_inference_runner_ready"
    return False, "local_inference_runner_unregistered"


def _semantic_turn_detector_ready(provider: str) -> bool:
    ready, _status = _semantic_turn_detector_status(provider)
    return ready


def _turn_end_reason_for_mode(mode: str) -> str:
    if mode == "stt":
        return "stt_end_of_turn"
    if mode == "vad":
        return "vad_silence"
    return mode


def _fallback_turn_detection_for_missing_semantic(provider: str) -> str:
    return "stt" if _supports_stt_endpointing(provider) else "vad"


def _default_turn_detection(stt_provider: str) -> str:
    normalized_provider = _normalize_stt_provider(stt_provider)
    if _supports_stt_endpointing(normalized_provider):
        return "stt"
    if _is_local_whisper_stt(normalized_provider) and _semantic_turn_detector_ready(
        normalized_provider
    ):
        return "turn_detector"
    return "vad"


def _resolve_turn_detection_for_profile(
    *,
    stt_provider: str,
    requested_turn_detection: str,
) -> str:
    normalized_provider = _normalize_stt_provider(stt_provider)
    requested = _normalize_turn_detection(requested_turn_detection)
    mode = requested or _default_turn_detection(normalized_provider)
    if mode != "turn_detector":
        return mode

    ready, status = _semantic_turn_detector_status(normalized_provider)
    if ready:
        return "turn_detector"

    fallback_mode = _fallback_turn_detection_for_missing_semantic(normalized_provider)
    if requested:
        logger.warning(
            "VIVENTIUM_TURN_DETECTION=turn_detector requested but semantic detector is unavailable "
            "for provider=%s status=%s; using %s turn detection.",
            normalized_provider,
            status,
            fallback_mode,
        )
    return fallback_mode


def _default_min_endpointing_delay(turn_detection: str, stt_provider: str = "") -> float:
    if turn_detection == "stt":
        return 0.0
    if turn_detection == "turn_detector":
        return 0.35
    if turn_detection == "vad" and _is_local_whisper_stt(stt_provider):
        return 0.5
    return 0.9


def _default_max_endpointing_delay(turn_detection: str) -> float:
    if turn_detection in {"stt", "turn_detector"}:
        return 1.8
    return 3.0


def _default_aec_warmup_duration(stt_provider: str) -> float:
    if _is_local_whisper_stt(stt_provider):
        return _LOCAL_WHISPER_AEC_WARMUP_DURATION_S
    return _DEFAULT_AEC_WARMUP_DURATION_S


def _default_job_memory_warn_mb(stt_provider: str, tts_provider: str) -> float:
    normalized_stt = _normalize_stt_provider(stt_provider)
    normalized_tts = _normalize_voice_provider(tts_provider)
    if normalized_stt in {"pywhispercpp", "whisper_local"}:
        return 2200.0
    if normalized_tts == "local_chatterbox_turbo_mlx_8bit":
        return 1400.0
    return 500.0


def _resolve_turn_handling_profile(
    *,
    stt_provider: str,
    requested_turn_detection: str,
    configured_min_interruption_words: Optional[int],
    configured_min_endpointing_delay_s: Optional[float],
    configured_max_endpointing_delay_s: Optional[float],
    configured_min_consecutive_speech_delay_s: Optional[float],
) -> dict[str, float | int | str]:
    voice_turn_detection = _resolve_turn_detection_for_profile(
        stt_provider=stt_provider,
        requested_turn_detection=requested_turn_detection,
    )
    default_min_endpointing_delay = _default_min_endpointing_delay(
        voice_turn_detection,
        stt_provider,
    )
    default_max_endpointing_delay = _default_max_endpointing_delay(voice_turn_detection)
    default_min_interruption_words = (
        0
        if _is_local_whisper_stt(stt_provider)
        else 1
        if voice_turn_detection in {"stt", "turn_detector"}
        else 0
    )
    default_min_consecutive_speech_delay = 0.2 if voice_turn_detection in {"stt", "turn_detector"} else 0.0
    return {
        "voice_turn_detection": voice_turn_detection,
        "voice_min_interruption_words": configured_min_interruption_words
        if configured_min_interruption_words is not None
        else default_min_interruption_words,
        "voice_min_endpointing_delay_s": configured_min_endpointing_delay_s
        if configured_min_endpointing_delay_s is not None
        else default_min_endpointing_delay,
        "voice_max_endpointing_delay_s": configured_max_endpointing_delay_s
        if configured_max_endpointing_delay_s is not None
        else default_max_endpointing_delay,
        "voice_min_consecutive_speech_delay_s": configured_min_consecutive_speech_delay_s
        if configured_min_consecutive_speech_delay_s is not None
        else default_min_consecutive_speech_delay,
    }


def _apply_effective_turn_handling_profile(env: Env) -> Env:
    profile = _resolve_turn_handling_profile(
        stt_provider=env.stt_provider,
        requested_turn_detection=env.voice_requested_turn_detection,
        configured_min_interruption_words=env.voice_configured_min_interruption_words,
        configured_min_endpointing_delay_s=env.voice_configured_min_endpointing_delay_s,
        configured_max_endpointing_delay_s=env.voice_configured_max_endpointing_delay_s,
        configured_min_consecutive_speech_delay_s=env.voice_configured_min_consecutive_speech_delay_s,
    )
    return replace(
        env,
        voice_turn_detection=str(profile["voice_turn_detection"]),
        voice_min_interruption_words=int(profile["voice_min_interruption_words"]),
        voice_min_endpointing_delay_s=float(profile["voice_min_endpointing_delay_s"]),
        voice_max_endpointing_delay_s=float(profile["voice_max_endpointing_delay_s"]),
        voice_min_consecutive_speech_delay_s=float(profile["voice_min_consecutive_speech_delay_s"]),
    )


def _turn_detector_model_is_cached() -> bool:
    manifest = _get_turn_detector_cache_manifest()
    if not manifest:
        return False
    try:
        from huggingface_hub import hf_hub_download

        hf_hub_download(
            manifest["repo_id"],
            manifest["onnx_filename"],
            subfolder="onnx",
            revision=manifest["revision"],
            local_files_only=True,
        )
        for filename in _TURN_DETECTOR_REQUIRED_ROOT_FILES:
            hf_hub_download(
                manifest["repo_id"],
                filename,
                revision=manifest["revision"],
                local_files_only=True,
            )
        return True
    except Exception:
        return False


def _get_turn_detector_cache_manifest() -> Optional[dict[str, str]]:
    if not HAS_TURN_DETECTOR:
        return None
    try:
        from livekit.plugins.turn_detector.models import HG_MODEL, MODEL_REVISIONS, ONNX_FILENAME

        return {
            "repo_id": HG_MODEL,
            "revision": MODEL_REVISIONS["multilingual"],
            "onnx_filename": ONNX_FILENAME,
        }
    except Exception:
        return None


def _load_turn_detector_model_class() -> Any:
    if not HAS_TURN_DETECTOR:
        return None
    try:
        from livekit.plugins.turn_detector.multilingual import MultilingualModel

        return MultilingualModel
    except Exception:
        return None


# === VIVENTIUM START ===
# Feature: Normalize voice provider labels for downstream prompt injection
def _normalize_voice_provider(provider: str) -> str:
    value = (provider or "").strip().lower()
    if value in {"grok", "xai_grok_voice", "x_ai"}:
        return "xai"
    if not value:
        return "openai"
    return value
# === VIVENTIUM END ===


def _is_real_api_key(value: str) -> bool:
    normalized = (value or "").strip()
    return bool(normalized and normalized.lower() not in {"user_provided", "placeholder"})


# === VIVENTIUM START ===
# Feature: STT provider normalization (v1 alias support)
# Added: 2026-01-11
# === VIVENTIUM END ===
def _normalize_stt_provider(provider: str) -> str:
    value = (provider or "").strip().lower()
    if not value:
        return "whisper_local"
    if value == "whisper_local":
        return "pywhispercpp"
    return value


def _default_local_stt_model() -> str:
    if platform.machine().lower() == "x86_64":
        return "small"
    return "large-v3-turbo"


def _normalize_local_stt_model(model_name: str) -> str:
    return (model_name or "").strip() or _default_local_stt_model()


# === VIVENTIUM START ===
# Feature: Selectable AssemblyAI streaming STT model in the modern playground "Listening" picker
# Added: 2026-05-29
# Why: AssemblyAI was already wired as a Listening provider, but its engine variant was cosmetic.
# The capability catalog advertised a single id "universal-streaming" (which is not even a valid
# plugin model string) and the selected variant was dropped in _apply_requested_voice_route, so the
# model was never passed to assemblyai.STT(). Every AssemblyAI call therefore silently ran the
# plugin default ("universal-streaming-english") and the picker had no effect. R&D
# (private/rnd/livekit_performance) proved "u3-rt-pro" (Universal-3 Pro streaming) as the higher
# quality low-latency engine, so we expose the real, plugin-valid model set, make selection work
# end-to-end, and default to the proven u3-rt-pro. Ids must stay aligned with the
# livekit-plugins-assemblyai STT(model=...) Literal; unknown/empty ids normalize to the default so
# we never hand the provider an invalid model string.
ASSEMBLYAI_DEFAULT_STT_MODEL = "u3-rt-pro"
# (model_id, human-facing label). Order defines the picker order; the first entry is the default.
ASSEMBLYAI_STT_MODELS: tuple[tuple[str, str], ...] = (
    ("u3-rt-pro", "Universal-3 Pro streaming (u3-rt-pro)"),
    ("universal-streaming-english", "Universal Streaming (English)"),
    ("universal-streaming-multilingual", "Universal Streaming (Multilingual)"),
)
_ASSEMBLYAI_STT_MODEL_IDS = {model_id for model_id, _label in ASSEMBLYAI_STT_MODELS}


def _normalize_assemblyai_stt_model(model_name: str) -> str:
    value = (model_name or "").strip()
    if value == "u3-pro":
        # Provider-deprecated alias; the plugin itself remaps u3-pro -> u3-rt-pro.
        return "u3-rt-pro"
    if value in _ASSEMBLYAI_STT_MODEL_IDS:
        return value
    return ASSEMBLYAI_DEFAULT_STT_MODEL


def _assemblyai_model_label(model_id: str) -> str:
    for candidate_id, label in ASSEMBLYAI_STT_MODELS:
        if candidate_id == model_id:
            return label
    return model_id


def _assemblyai_stt_model_variants(selected_model: str) -> list[tuple[str, str]]:
    # Selected model first (mirrors the OpenAI/local-whisper variant ordering), then the full set.
    # _dedupe_variants collapses the duplicate when the selected model is already in the catalog.
    normalized = _normalize_assemblyai_stt_model(selected_model)
    ordered = [normalized, *[model_id for model_id, _label in ASSEMBLYAI_STT_MODELS]]
    return [(model_id, _assemblyai_model_label(model_id)) for model_id in ordered]
# === VIVENTIUM END ===


def _local_whisper_model_variants(recommended_model: str) -> list[tuple[str, str]]:
    ordered_models = [recommended_model, *_LOCAL_WHISPER_MODELS]
    return [
        (
            model_id,
            _local_whisper_variant_label(model_id, recommended_model=recommended_model),
        )
        for model_id in ordered_models
    ]


def _dedupe_variants(*values: Any) -> list[dict[str, str]]:
    seen: set[str] = set()
    variants: list[dict[str, str]] = []
    for value in values:
        if isinstance(value, tuple):
            raw_id, raw_label = value
            text = (raw_id or "").strip()
            label = (raw_label or raw_id or "").strip()
        else:
            text = (value or "").strip()
            label = text
        if not text or text in seen:
            continue
        seen.add(text)
        variants.append({"id": text, "label": label or text})
    return variants


def _cartesia_voice_label(voice_id: str) -> str:
    normalized = (voice_id or "").strip()
    for preset_id, preset_label in CARTESIA_VOICE_PRESETS:
        if normalized == preset_id:
            return preset_label
    return normalized


def _local_whisper_variant_label(model_id: str, *, recommended_model: str) -> str:
    model_key = (model_id or "").strip()
    labels = {
        "tiny.en": "Fastest",
        "base.en": "Light",
        "small": "Balanced",
        "small.en": "Balanced",
        "medium": "More accurate",
        "medium.en": "More accurate",
        "large-v3": "Highest accuracy",
        "large-v3-q5_0": "Highest accuracy quantized",
        "large-v3-turbo": "Best quality",
        "large-v3-turbo-q5_0": "Best quality quantized",
    }
    descriptor = labels.get(model_key)
    if descriptor:
        label = f"{descriptor} - {model_key}"
    else:
        label = model_key
    if model_key == recommended_model:
        return f"{label} (Recommended)"
    return label


def _parse_metadata_json(metadata: str) -> dict[str, Any]:
    if not metadata:
        return {}
    try:
        obj = json.loads(metadata)
    except json.JSONDecodeError:
        return {}
    if not isinstance(obj, dict):
        return {}
    return obj


def _normalize_requested_voice_selection(selection: Any) -> dict[str, Optional[str]]:
    if not isinstance(selection, dict):
        return {"provider": None, "variant": None}

    provider_raw = selection.get("provider")
    variant_raw = selection.get("variant")
    provider = provider_raw.strip() if isinstance(provider_raw, str) and provider_raw.strip() else None
    variant = variant_raw.strip() if isinstance(variant_raw, str) and variant_raw.strip() else None
    return {
        "provider": provider,
        "variant": variant,
    }


def _normalize_requested_voice_route(route: Any) -> dict[str, dict[str, Optional[str]]]:
    if not isinstance(route, dict):
        return {
            "stt": {"provider": None, "variant": None},
            "tts": {"provider": None, "variant": None},
        }

    return {
        "stt": _normalize_requested_voice_selection(route.get("stt")),
        "tts": _normalize_requested_voice_selection(route.get("tts")),
    }


def _provider_display_label(provider: str, *, modality: str) -> str:
    provider_key = (provider or "").strip().lower()
    labels = {
        "assemblyai": "AssemblyAI",
        "cartesia": "Cartesia",
        "elevenlabs": "ElevenLabs",
        "local_chatterbox_turbo_mlx_8bit": "Local Chatterbox",
        "openai": "OpenAI",
        "pywhispercpp": "Whisper.cpp Local",
        "xai": XAI_TTS_DISPLAY_LABEL,
    }
    label = labels.get(provider_key)
    if label:
        return label
    return "Speech Provider" if modality == "stt" else "Voice Provider"


def _provider_variant_type(provider: str, *, modality: str) -> str:
    provider_key = (provider or "").strip().lower()
    if modality == "stt":
        if provider_key == "assemblyai":
            return "Engine"
        return "Model"
    if provider_key in {"xai", "elevenlabs", "cartesia"}:
        return "Voice"
    return "Model"


def _is_local_provider(provider: str) -> bool:
    return (provider or "").strip().lower() in {
        "local_chatterbox_turbo_mlx_8bit",
        "pywhispercpp",
        "whisper_local",
    }


def _build_voice_capability_catalog(env: Env) -> list[dict[str, Any]]:
    openai_api_key = (os.getenv("OPENAI_API_KEY", "") or "").strip()
    assemblyai_api_key = (os.getenv("ASSEMBLYAI_API_KEY", "") or "").strip()
    cartesia_api_key = (os.getenv("CARTESIA_API_KEY", "") or "").strip()
    eleven_api_key = ((os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY")) or "").strip()
    xai_api_key = (env.xai_tts_api_key or os.getenv("XAI_API_KEY", "") or "").strip()
    xai_runtime_supported = env.xai_tts_api == "voice_agent" or HAS_XAI_TTS
    has_pywhispercpp = importlib.util.find_spec("pywhispercpp") is not None
    has_mlx_audio = importlib.util.find_spec("mlx_audio") is not None
    apple_silicon = sys.platform == "darwin" and platform.machine().lower() == "arm64"
    recommended_local_stt_model = _normalize_local_stt_model(env.stt_model)

    capabilities: list[dict[str, Any]] = [
        {
            "id": "openai",
            "modality": "stt",
            "label": _provider_display_label("openai", modality="stt"),
            "isLocal": False,
            "available": bool(openai_api_key),
            "unavailableReason": None if openai_api_key else "OPENAI_API_KEY not set",
            "variantLabel": _provider_variant_type("openai", modality="stt"),
            "variants": _dedupe_variants(
                env.openai_stt_model,
                "gpt-4o-mini-transcribe",
                "gpt-4o-transcribe",
                "whisper-1",
            ),
        },
        {
            "id": "assemblyai",
            "modality": "stt",
            "label": _provider_display_label("assemblyai", modality="stt"),
            "isLocal": False,
            "available": bool(HAS_ASSEMBLYAI and assemblyai_api_key),
            "unavailableReason": None
            if HAS_ASSEMBLYAI and assemblyai_api_key
            else "AssemblyAI plugin or ASSEMBLYAI_API_KEY missing",
            "variantLabel": _provider_variant_type("assemblyai", modality="stt"),
            "variants": _dedupe_variants(*_assemblyai_stt_model_variants(env.assemblyai_stt_model)),
        },
        {
            "id": "pywhispercpp",
            "modality": "stt",
            "label": _provider_display_label("pywhispercpp", modality="stt"),
            "isLocal": True,
            "available": has_pywhispercpp,
            "unavailableReason": None if has_pywhispercpp else "pywhispercpp package not installed",
            "variantLabel": _provider_variant_type("pywhispercpp", modality="stt"),
            "variants": _dedupe_variants(*_local_whisper_model_variants(recommended_local_stt_model)),
        },
        {
            "id": "openai",
            "modality": "tts",
            "label": _provider_display_label("openai", modality="tts"),
            "isLocal": False,
            "available": bool(openai_api_key),
            "unavailableReason": None if openai_api_key else "OPENAI_API_KEY not set",
            "acceptsInlineVoiceControls": False,
            "variantLabel": _provider_variant_type("openai", modality="tts"),
            "variants": _dedupe_variants(env.openai_tts_model, "gpt-4o-mini-tts"),
        },
        {
            "id": "elevenlabs",
            "modality": "tts",
            "label": _provider_display_label("elevenlabs", modality="tts"),
            "isLocal": False,
            "available": bool(HAS_ELEVENLABS and eleven_api_key),
            "unavailableReason": None
            if HAS_ELEVENLABS and eleven_api_key
            else "ElevenLabs plugin or ELEVEN_API_KEY missing",
            "acceptsInlineVoiceControls": False,
            "variantLabel": _provider_variant_type("elevenlabs", modality="tts"),
            "variants": _dedupe_variants(env.elevenlabs_voice_id, env.elevenlabs_voice_id_fallback),
        },
        {
            "id": "cartesia",
            "modality": "tts",
            "label": _provider_display_label("cartesia", modality="tts"),
            "isLocal": False,
            "available": bool(cartesia_api_key),
            "unavailableReason": None if cartesia_api_key else "CARTESIA_API_KEY not set",
            "acceptsInlineVoiceControls": True,
            "variantLabel": _provider_variant_type("cartesia", modality="tts"),
            "variants": _dedupe_variants(
                *CARTESIA_VOICE_PRESETS,
                (env.cartesia_voice_id, _cartesia_voice_label(env.cartesia_voice_id)),
            ),
        },
        {
            "id": "xai",
            "modality": "tts",
            "label": _provider_display_label("xai", modality="tts"),
            "isLocal": False,
            "available": bool(xai_runtime_supported and _is_real_api_key(xai_api_key)),
            "unavailableReason": None
            if xai_runtime_supported and _is_real_api_key(xai_api_key)
            else "xAI plugin or VIVENTIUM_XAI_TTS_API_KEY/XAI_API_KEY missing",
            "acceptsInlineVoiceControls": True,
            "variantLabel": _provider_variant_type("xai", modality="tts"),
            "variants": _dedupe_variants(*XAI_TTS_VOICE_PRESETS, env.xai_voice),
        },
        {
            "id": "local_chatterbox_turbo_mlx_8bit",
            "modality": "tts",
            "label": _provider_display_label("local_chatterbox_turbo_mlx_8bit", modality="tts"),
            "isLocal": True,
            "available": bool(apple_silicon and has_mlx_audio),
            "unavailableReason": None
            if apple_silicon and has_mlx_audio
            else "Apple Silicon + mlx-audio required",
            "acceptsInlineVoiceControls": True,
            "variantLabel": _provider_variant_type("local_chatterbox_turbo_mlx_8bit", modality="tts"),
            "variants": _dedupe_variants(env.mlx_audio_model_id),
        },
    ]
    return capabilities


def _find_voice_capability(
    capabilities: list[dict[str, Any]], *, modality: str, provider: str
) -> Optional[dict[str, Any]]:
    normalized_provider = _normalize_stt_provider(provider) if modality == "stt" else _normalize_voice_provider(provider)
    for capability in capabilities:
        if capability.get("modality") != modality:
            continue
        if capability.get("id") == normalized_provider:
            return capability
    return None


def _resolve_requested_variant(
    capability: Optional[dict[str, Any]],
    requested_variant: Optional[str],
    fallback_variant: Optional[str],
) -> Optional[str]:
    variant_ids = {
        variant.get("id")
        for variant in (capability or {}).get("variants", [])
        if isinstance(variant, dict) and isinstance(variant.get("id"), str)
    }
    if requested_variant and requested_variant in variant_ids:
        return requested_variant
    if fallback_variant and (not variant_ids or fallback_variant in variant_ids):
        return fallback_variant
    for variant in (capability or {}).get("variants", []):
        if isinstance(variant, dict) and isinstance(variant.get("id"), str):
            return variant["id"]
    return fallback_variant


def _build_tts_provider_attempt(
    *,
    capabilities: list[dict[str, Any]],
    provider: str,
    tts_impl: Any,
) -> ProviderAttempt:
    capability = _find_voice_capability(capabilities, modality="tts", provider=provider)
    accepts_inline_voice_controls = bool((capability or {}).get("acceptsInlineVoiceControls"))
    return ProviderAttempt(
        label=provider,
        tts=tts_impl,
        sanitize_voice_markup=not accepts_inline_voice_controls,
    )


def _tts_provider_accepts_inline_voice_controls(
    capabilities: list[dict[str, Any]],
    provider: str,
) -> bool:
    capability = _find_voice_capability(capabilities, modality="tts", provider=provider)
    return bool((capability or {}).get("acceptsInlineVoiceControls"))


# === VIVENTIUM START ===
# Feature: Preserve inter-word spacing in xAI standalone TTS websocket input.
# Added: 2026-05-30
#
# Why:
# - The LiveKit xAI plugin (livekit/plugins/xai/tts.py) tokenizes synthesis input with
#   `tokenize.basic.WordTokenizer(ignore_punctuation=False)` and sends EACH word token as a
#   separate `{"type": "text.delta", "delta": word.token}` frame over wss://api.x.ai/v1/tts.
#   The xAI server concatenates those deltas verbatim.
# - That WordTokenizer defaults to `retain_format=False`, which DROPS the whitespace between
#   words (it advances `word_start = pos + 1` past the space). So "Hello world" is emitted as the
#   bare tokens "Hello","world" and the server speaks "Helloworld". Every inter-word space is lost.
# - The on-screen chat transcript is unaffected: LiveKit's TranscriptSynchronizer already uses a
#   `retain_format=True` WordTokenizer (see test_worker_turn_handling.py), so the displayed text
#   keeps its spacing while only the spoken audio runs words together. This is why the symptom
#   looks like a sanitization bug but is not — our sse.py/fallback_tts.py sanitizers preserve
#   spacing; the loss happens downstream inside the plugin's word-delta streaming.
#
# Fix:
# - Inject a `retain_format=True` WordTokenizer so each emitted token keeps its leading whitespace
#   (" world"), making the reconstructed websocket text match the original spacing exactly.
# - Keep `ignore_punctuation=False` (xAI relies on punctuation for prosody) and the plugin default
#   `split_character=False` so non-spaced scripts (CJK) keep the same delta granularity.
def _xai_tts_delta_logging_enabled() -> bool:
    return (
        (os.getenv("VIVENTIUM_VOICE_DEBUG_TTS", "") or "").strip() == "1"
        or (os.getenv("VIVENTIUM_VOICE_LOG_TTS_INPUTS", "") or "").strip() == "1"
    )


class _LoggingWordStream:
    """Diagnostic proxy around a LiveKit `WordStream`.

    The xAI plugin streams each emitted word token to `wss://api.x.ai/v1/tts` as a separate
    `{"type": "text.delta", "delta": word.token}` frame. When voice TTS debug logging is enabled
    this proxy records the exact per-word payloads (with safe JSON escaping) so the websocket-level
    spacing can be verified without leaking secrets. It never alters the tokens or the stream.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self._index = 0

    def push_text(self, text: str) -> None:
        self._inner.push_text(text)

    def flush(self) -> None:
        self._inner.flush()

    def end_input(self) -> None:
        self._inner.end_input()

    async def aclose(self) -> None:
        await self._inner.aclose()

    def __aiter__(self) -> Any:
        return self

    async def __anext__(self) -> Any:
        token = await self._inner.__anext__()
        try:
            value = getattr(token, "token", "") or ""
            logger.info(
                "[VoiceTTSInput] action=word_delta provider=xai transport=ws stage=text.delta index=%s leading_space=%s token_json=%s",
                self._index,
                bool(value[:1].isspace()),
                json.dumps(value, ensure_ascii=False),
            )
            self._index += 1
        except Exception:
            pass
        return token


class _SpacePreservingWordTokenizer(tokenize.basic.WordTokenizer):
    """xAI synthesis word tokenizer that preserves inter-word spacing.

    Identical to the plugin's tokenizer except `retain_format=True` (set by the factory below). When
    voice TTS debug logging is enabled it wraps the word stream so the exact `text.delta` payloads
    sent to the xAI websocket are logged; otherwise it returns the plain stream so the production
    path is unchanged.
    """

    def stream(self, *, language: Optional[str] = None) -> Any:
        inner = super().stream(language=language)
        if _xai_tts_delta_logging_enabled():
            return _LoggingWordStream(inner)
        return inner


def _build_xai_tts_word_tokenizer() -> tokenize.WordTokenizer:
    return _SpacePreservingWordTokenizer(ignore_punctuation=False, retain_format=True)
# === VIVENTIUM END ===


def _configure_xai_standalone_tts_plugin(*, ws_url: str, sample_rate: int) -> None:
    """Align LiveKit's xAI plugin module constants with our compiled runtime config."""
    if xai_plugin is None:
        return
    tts_module = getattr(xai_plugin, "tts", None)
    if tts_module is None:
        raise RuntimeError("xAI TTS plugin module does not expose live endpoint controls.")
    missing = [
        attr
        for attr in ("XAI_WEBSOCKET_URL", "SAMPLE_RATE")
        if not hasattr(tts_module, attr)
    ]
    if missing:
        raise RuntimeError(
            "xAI TTS plugin endpoint controls are unavailable: "
            + ", ".join(missing)
        )
    setattr(tts_module, "XAI_WEBSOCKET_URL", ws_url)
    setattr(tts_module, "SAMPLE_RATE", int(sample_rate))


def _apply_xai_tts_streaming_latency_options(
    tts_impl: Any,
    *,
    ws_url: str,
    sample_rate: int,
    optimize_streaming_latency: int,
) -> None:
    """Attach Viventium's xAI streaming query parameters until the plugin exposes them."""
    if optimize_streaming_latency <= 0:
        return
    if not hasattr(tts_impl, "_opts") or not hasattr(tts_impl, "_ensure_session"):
        logger.warning(
            "xAI TTS streaming latency optimization requested, but the plugin instance does not expose endpoint controls."
        )
        return
    existing_connect_ws = getattr(tts_impl, "_connect_ws", None)
    if not callable(existing_connect_ws):
        try:
            plugin_version = importlib_metadata.version("livekit-plugins-xai")
        except importlib_metadata.PackageNotFoundError:
            plugin_version = "unknown"
        logger.warning(
            "xAI TTS streaming latency optimization requested, but livekit-plugins-xai version=%s does not expose the expected _connect_ws hook; continuing without optimize_streaming_latency.",
            plugin_version,
        )
        return
    try:
        inspect.signature(existing_connect_ws).bind(1.0)
    except (TypeError, ValueError) as exc:
        try:
            plugin_version = importlib_metadata.version("livekit-plugins-xai")
        except importlib_metadata.PackageNotFoundError:
            plugin_version = "unknown"
        logger.warning(
            "xAI TTS streaming latency optimization requested, but livekit-plugins-xai version=%s exposes an incompatible _connect_ws hook (%s); continuing without optimize_streaming_latency.",
            plugin_version,
            exc,
        )
        return

    async def _connect_ws(timeout: float) -> aiohttp.ClientWebSocketResponse:
        opts = getattr(tts_impl, "_opts", None)
        api_key = getattr(tts_impl, "_api_key", "")
        params = {
            "voice": getattr(opts, "voice", DEFAULT_XAI_TTS_VOICE),
            "language": getattr(opts, "language", DEFAULT_XAI_TTS_LANGUAGE),
            "codec": "pcm",
            "sample_rate": int(sample_rate),
            "optimize_streaming_latency": int(optimize_streaming_latency),
        }
        url = f"{ws_url}?{urlencode(params)}"
        try:
            return await asyncio.wait_for(
                tts_impl._ensure_session().ws_connect(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                ),
                timeout,
            )
        except (
            aiohttp.ClientConnectorError,
            aiohttp.ClientConnectionResetError,
            asyncio.TimeoutError,
        ) as exc:
            raise APIConnectionError("failed to connect to xAI") from exc

    setattr(tts_impl, "_connect_ws", _connect_ws)
    setattr(
        tts_impl,
        "_viventium_xai_tts_optimize_streaming_latency",
        int(optimize_streaming_latency),
    )


def _apply_requested_voice_route(
    env: Env,
    requested_voice_route: Any,
    capabilities: list[dict[str, Any]],
) -> Env:
    normalized_route = _normalize_requested_voice_route(requested_voice_route)
    runtime_env = env

    stt_selection = normalized_route["stt"]
    requested_stt_provider = (
        _normalize_stt_provider(stt_selection["provider"]) if stt_selection["provider"] else None
    )
    if requested_stt_provider:
        capability = _find_voice_capability(capabilities, modality="stt", provider=requested_stt_provider)
        if capability and capability.get("available"):
            if requested_stt_provider == "openai":
                runtime_env = replace(
                    runtime_env,
                    stt_provider="openai",
                    openai_stt_model=_resolve_requested_variant(
                        capability,
                        stt_selection["variant"],
                        runtime_env.openai_stt_model,
                    )
                    or runtime_env.openai_stt_model,
                )
            elif requested_stt_provider == "assemblyai":
                runtime_env = replace(
                    runtime_env,
                    stt_provider="assemblyai",
                    assemblyai_stt_model=_normalize_assemblyai_stt_model(
                        _resolve_requested_variant(
                            capability,
                            stt_selection["variant"],
                            runtime_env.assemblyai_stt_model,
                        )
                        or runtime_env.assemblyai_stt_model
                    ),
                )
            elif requested_stt_provider == "pywhispercpp":
                runtime_env = replace(
                    runtime_env,
                    stt_provider="pywhispercpp",
                    stt_model=_resolve_requested_variant(
                        capability,
                        stt_selection["variant"],
                        runtime_env.stt_model,
                    )
                    or runtime_env.stt_model,
                )
        else:
            logger.warning(
                "[voice-gateway] Ignoring unavailable requested listening provider: %s",
                requested_stt_provider,
            )

    tts_selection = normalized_route["tts"]
    requested_tts_provider = (
        _normalize_voice_provider(tts_selection["provider"]) if tts_selection["provider"] else None
    )
    if requested_tts_provider:
        capability = _find_voice_capability(capabilities, modality="tts", provider=requested_tts_provider)
        if capability and capability.get("available"):
            if requested_tts_provider == "openai":
                runtime_env = replace(
                    runtime_env,
                    tts_provider="openai",
                    openai_tts_model=_resolve_requested_variant(
                        capability,
                        tts_selection["variant"],
                        runtime_env.openai_tts_model,
                    )
                    or runtime_env.openai_tts_model,
                )
            elif requested_tts_provider == "elevenlabs":
                runtime_env = replace(
                    runtime_env,
                    tts_provider="elevenlabs",
                    elevenlabs_voice_id=_resolve_requested_variant(
                        capability,
                        tts_selection["variant"],
                        runtime_env.elevenlabs_voice_id,
                    )
                    or runtime_env.elevenlabs_voice_id,
                )
            elif requested_tts_provider == "cartesia":
                runtime_env = replace(
                    runtime_env,
                    tts_provider="cartesia",
                    cartesia_voice_id=_resolve_requested_variant(
                        capability,
                        tts_selection["variant"],
                        runtime_env.cartesia_voice_id,
                    )
                    or runtime_env.cartesia_voice_id,
                    cartesia_model_id=DEFAULT_CARTESIA_MODEL_ID,
                )
            elif requested_tts_provider == "xai":
                runtime_env = replace(
                    runtime_env,
                    tts_provider="xai",
                    xai_voice=_resolve_requested_variant(
                        capability,
                        tts_selection["variant"],
                        runtime_env.xai_voice,
                    )
                    or runtime_env.xai_voice,
                )
            elif requested_tts_provider == "local_chatterbox_turbo_mlx_8bit":
                runtime_env = replace(
                    runtime_env,
                    tts_provider="local_chatterbox_turbo_mlx_8bit",
                    mlx_audio_model_id=_resolve_requested_variant(
                        capability,
                        tts_selection["variant"],
                        runtime_env.mlx_audio_model_id,
                    )
                    or runtime_env.mlx_audio_model_id,
                )
        else:
            logger.warning(
                "[voice-gateway] Ignoring unavailable requested speaking provider: %s",
                requested_tts_provider,
            )

    return _apply_effective_turn_handling_profile(runtime_env)


def _current_stt_variant(env: Env, provider: str) -> Optional[str]:
    normalized_provider = _normalize_stt_provider(provider)
    if normalized_provider == "openai":
        return env.openai_stt_model
    if normalized_provider == "pywhispercpp":
        return env.stt_model
    if normalized_provider == "assemblyai":
        return "universal-streaming"
    return None


def _current_tts_variant(env: Env, provider: str, tts_impl: Optional[Any] = None) -> Optional[str]:
    normalized_provider = _normalize_voice_provider(provider)
    if normalized_provider == "openai":
        return getattr(tts_impl, "model", None) or env.openai_tts_model
    if normalized_provider == "cartesia":
        cfg = getattr(tts_impl, "_config", None)
        voice_id = getattr(cfg, "voice_id", None)
        return voice_id or env.cartesia_voice_id
    if normalized_provider == "xai":
        cfg = getattr(tts_impl, "_config", None)
        voice = getattr(cfg, "voice", None)
        return voice or env.xai_voice
    if normalized_provider == "elevenlabs":
        opts = getattr(tts_impl, "_opts", None)
        voice_id = getattr(opts, "voice_id", None)
        return voice_id or env.elevenlabs_voice_id
    if normalized_provider == "local_chatterbox_turbo_mlx_8bit":
        cfg = getattr(tts_impl, "_config", None)
        model_id = getattr(cfg, "model_id", None)
        return model_id or env.mlx_audio_model_id
    return None


def _build_route_entry(
    *,
    modality: str,
    provider: str,
    variant: Optional[str],
) -> dict[str, Any]:
    normalized_provider = _normalize_stt_provider(provider) if modality == "stt" else _normalize_voice_provider(provider)
    variant_type = _provider_variant_type(normalized_provider, modality=modality)
    provider_label = _provider_display_label(normalized_provider, modality=modality)
    variant_text = variant.strip() if isinstance(variant, str) and variant.strip() else None
    variant_display = (
        _cartesia_voice_label(variant_text)
        if modality == "tts" and normalized_provider == "cartesia" and variant_text
        else variant_text
    )
    display_label = provider_label if not variant_display else f"{provider_label} • {variant_display}"
    return {
        "provider": normalized_provider,
        "label": provider_label,
        "displayLabel": display_label,
        "isLocal": _is_local_provider(normalized_provider),
        "variant": variant_text,
        "variantLabel": variant_display,
        "variantType": variant_type,
    }


def _build_voice_route_metadata(
    *,
    env: Env,
    capabilities: list[dict[str, Any]],
    stt_provider: str,
    tts_provider: str,
    effective_tts_impl: Any,
    fallback_tts_provider: Optional[str],
    fallback_tts_impl: Optional[Any],
) -> dict[str, Any]:
    tts_fallback = None
    if fallback_tts_provider:
        tts_fallback = _build_route_entry(
            modality="tts",
            provider=fallback_tts_provider,
            variant=_current_tts_variant(env, fallback_tts_provider, fallback_tts_impl),
        )

    return {
        "stt": _build_route_entry(
            modality="stt",
            provider=stt_provider,
            variant=_current_stt_variant(env, stt_provider),
        ),
        "tts": _build_route_entry(
            modality="tts",
            provider=tts_provider,
            variant=_current_tts_variant(env, tts_provider, effective_tts_impl),
        ),
        "ttsFallback": tts_fallback,
        "capabilities": capabilities,
    }


def _build_configured_voice_route_metadata(
    *,
    env: Env,
    capabilities: list[dict[str, Any]],
) -> dict[str, Any]:
    fallback_provider = _normalize_voice_provider(env.tts_provider_fallback)
    fallback_route = None
    if fallback_provider:
        fallback_route = _build_route_entry(
            modality="tts",
            provider=fallback_provider,
            variant=_current_tts_variant(env, fallback_provider),
        )

    return {
        "stt": _build_route_entry(
            modality="stt",
            provider=env.stt_provider,
            variant=_current_stt_variant(env, env.stt_provider),
        ),
        "tts": _build_route_entry(
            modality="tts",
            provider=env.tts_provider,
            variant=_current_tts_variant(env, env.tts_provider),
        ),
        "ttsFallback": fallback_route,
        "capabilities": capabilities,
    }


# === VIVENTIUM START ===
# Feature: Lightweight health endpoint for Container Apps probes.
def start_health_server() -> None:
    host = (os.getenv("VOICE_GATEWAY_HOST", "0.0.0.0") or "0.0.0.0").strip()
    port_raw = (
        os.getenv("VIVENTIUM_VOICE_GATEWAY_HEALTH_PORT")
        or os.getenv("VOICE_GATEWAY_PORT")
        or "8000"
    ).strip() or "8000"
    try:
        port = int(float(port_raw))
    except ValueError:
        port = 8000

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/capabilities":
                try:
                    env = load_env()
                    payload = _build_configured_voice_route_metadata(
                        env=env,
                        capabilities=_build_voice_capability_catalog(env),
                    )
                    body = json.dumps(payload).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                except Exception as exc:
                    logger.warning("[voice-gateway] Failed to build capability payload: %s", exc)
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(b'{"error":"capabilities unavailable"}')
                    return
            if self.path in ("/", "/health"):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    try:
        server = HTTPServer((host, port), HealthHandler)
    except OSError as exc:
        logger.warning("Health endpoint unavailable on %s:%s (%s)", host, port, exc)
        return

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health endpoint listening on %s:%s", host, port)
# === VIVENTIUM END ===

def load_env() -> Env:
    # Determine TTS provider (default to elevenlabs if available, otherwise openai)
    default_tts_provider = "elevenlabs" if HAS_ELEVENLABS else "openai"
    tts_provider = _normalize_voice_provider(
        os.getenv("VIVENTIUM_TTS_PROVIDER", default_tts_provider).strip() or default_tts_provider
    )
    raw_tts_provider_fallback = os.getenv("VIVENTIUM_TTS_PROVIDER_FALLBACK", "").strip() or ""
    tts_provider_fallback = (
        _normalize_voice_provider(raw_tts_provider_fallback) if raw_tts_provider_fallback else ""
    )
    if tts_provider_fallback in {"0", "false", "off", "none"}:
        tts_provider_fallback = ""
    # If the primary provider can fail at runtime (Cartesia credit exhaustion, MLX model OOM, etc.),
    # default fallback to ElevenLabs (or OpenAI) so voice calls remain functional.
    if not tts_provider_fallback and (tts_provider == "cartesia" or "chatterbox" in tts_provider):
        tts_provider_fallback = "elevenlabs" if HAS_ELEVENLABS else "openai"
    # === VIVENTIUM START ===
    # Feature: v1 STT env parity (voice override + legacy STT_PROVIDER)
    stt_provider = (
        os.getenv("VIVENTIUM_VOICE_STT_PROVIDER")
        or os.getenv("VIVENTIUM_STT_PROVIDER")
        or os.getenv("STT_PROVIDER")
        or "whisper_local"
    )
    normalized_stt_provider = _normalize_stt_provider(stt_provider)
    requested_turn_detection = _normalize_turn_detection(
        os.getenv("VIVENTIUM_TURN_DETECTION", "")
    )
    default_initialize_process_timeout_s = (
        120.0 if normalized_stt_provider in {"pywhispercpp", "whisper_local"} else 20.0
    )
    default_idle_processes = 1 if normalized_stt_provider in {"pywhispercpp", "whisper_local"} else 0
    # === VIVENTIUM START ===
    # Feature: Local-whisper dispatch must not race transient machine load.
    # Purpose: local first-run builds and model warmup can briefly push host load to ~100% after
    # the worker has already registered. Refusing the first explicit user call in that window is
    # worse than accepting it with potentially higher latency, so local STT defaults to no CPU gate.
    if normalized_stt_provider in {"pywhispercpp", "whisper_local"}:
        default_load_threshold = math.inf
    else:
        default_load_threshold = 0.7
    # Local Whisper and local Chatterbox both use accelerator-heavy runtimes. Keeping a warm STT
    # job process protects call startup, but prewarming Chatterbox in the replacement idle process
    # can contend with the active Whisper turn and make final transcripts visibly late.
    default_prewarm_local_tts = normalized_stt_provider not in {
        "pywhispercpp",
        "whisper_local",
    }
    configured_min_interruption_words = _parse_optional_int_env(
        "VIVENTIUM_VOICE_MIN_INTERRUPTION_WORDS",
    )
    configured_min_endpointing_delay_s = _parse_optional_float_env(
        "VIVENTIUM_VOICE_MIN_ENDPOINTING_DELAY_S",
    )
    configured_max_endpointing_delay_s = _parse_optional_float_env(
        "VIVENTIUM_VOICE_MAX_ENDPOINTING_DELAY_S",
    )
    configured_min_consecutive_speech_delay_s = _parse_optional_float_env(
        "VIVENTIUM_VOICE_MIN_CONSECUTIVE_SPEECH_DELAY_S",
    )
    turn_handling_profile = _resolve_turn_handling_profile(
        stt_provider=normalized_stt_provider,
        requested_turn_detection=requested_turn_detection,
        configured_min_interruption_words=configured_min_interruption_words,
        configured_min_endpointing_delay_s=configured_min_endpointing_delay_s,
        configured_max_endpointing_delay_s=configured_max_endpointing_delay_s,
        configured_min_consecutive_speech_delay_s=configured_min_consecutive_speech_delay_s,
    )
    default_job_memory_warn_mb = _default_job_memory_warn_mb(
        normalized_stt_provider,
        tts_provider,
    )
    # === VIVENTIUM END ===
    # === VIVENTIUM END ===
    
    return Env(
        livekit_agent_name=os.getenv("LIVEKIT_AGENT_NAME", "librechat-voice-gateway").strip()
        or "librechat-voice-gateway",
        librechat_origin=os.getenv("VIVENTIUM_LIBRECHAT_ORIGIN", "http://localhost:3180").strip()
        or "http://localhost:3180",
        call_session_secret=os.getenv("VIVENTIUM_CALL_SESSION_SECRET", "").strip(),
        stt_provider=stt_provider.strip() or "whisper_local",
        stt_model=_normalize_local_stt_model(os.getenv("VIVENTIUM_STT_MODEL", "")),
        stt_language=(os.getenv("VIVENTIUM_STT_LANGUAGE", "en").strip() or "en"),
        openai_stt_model=os.getenv("VIVENTIUM_OPENAI_STT_MODEL", "gpt-4o-mini-transcribe").strip()
        or "gpt-4o-mini-transcribe",
        tts_provider=tts_provider,
        tts_provider_fallback=tts_provider_fallback,
        # xAI standalone TTS settings (Available: Ara, Eve, Leo, Rex, Sal).
        # Set VIVENTIUM_XAI_TTS_API=voice_agent only to use the older Grok Voice Agent adapter.
        xai_tts_api=(os.getenv("VIVENTIUM_XAI_TTS_API", "tts").strip().lower() or "tts"),
        xai_tts_api_key=(os.getenv("VIVENTIUM_XAI_TTS_API_KEY", "").strip() or ""),
        xai_voice=(os.getenv("VIVENTIUM_XAI_VOICE", DEFAULT_XAI_TTS_VOICE).strip() or DEFAULT_XAI_TTS_VOICE),
        xai_language=(os.getenv("VIVENTIUM_XAI_LANGUAGE", DEFAULT_XAI_TTS_LANGUAGE).strip() or DEFAULT_XAI_TTS_LANGUAGE),
        xai_tts_ws_url=(
            os.getenv("VIVENTIUM_XAI_TTS_WS_URL", DEFAULT_XAI_TTS_WS_URL).strip()
            or DEFAULT_XAI_TTS_WS_URL
        ),
        xai_tts_optimize_streaming_latency=max(
            0,
            min(
                1,
                _parse_int_env(
                    "VIVENTIUM_XAI_TTS_OPTIMIZE_STREAMING_LATENCY",
                    DEFAULT_XAI_TTS_OPTIMIZE_STREAMING_LATENCY,
                ),
            ),
        ),
        xai_wss_url=(
            os.getenv(
                "VIVENTIUM_XAI_VOICE_AGENT_WSS_URL",
                os.getenv("VIVENTIUM_XAI_WSS_URL", "wss://api.x.ai/v1/realtime"),
            ).strip()
            or "wss://api.x.ai/v1/realtime"
        ),
        xai_sample_rate=int(float(os.getenv("VIVENTIUM_XAI_SAMPLE_RATE", str(DEFAULT_XAI_TTS_SAMPLE_RATE)))),
        xai_instructions=(os.getenv("VIVENTIUM_XAI_INSTRUCTIONS", "").strip() or ""),
        # ElevenLabs settings (matching old viventium_v1 config)
        elevenlabs_voice_id=os.getenv("VIVENTIUM_FC_CONSCIOUS_VOICE_ID", "CrmDm7REHG6iBx8uySLf").strip()
        or "CrmDm7REHG6iBx8uySLf",
        # If the primary voice_id is blocked (e.g., instantly cloned voice on lower tiers),
        # retry with a premade voice id so voice calls still work.
        elevenlabs_voice_id_fallback=os.getenv(
            "VIVENTIUM_ELEVENLABS_VOICE_ID_FALLBACK", "cgSgspJ2msm6clMCkdW9"
        ).strip()
        or "cgSgspJ2msm6clMCkdW9",
        elevenlabs_voice_stability=float(os.getenv("VIVENTIUM_ELEVENLABS_VOICE_STABILITY", "0.45")),
        elevenlabs_voice_similarity_boost=float(os.getenv("VIVENTIUM_ELEVENLABS_VOICE_SIMILARITY_BOOST", "0.85")),
        elevenlabs_voice_style=float(os.getenv("VIVENTIUM_ELEVENLABS_VOICE_STYLE", "0.35")),
        elevenlabs_voice_speed=float(os.getenv("VIVENTIUM_ELEVENLABS_VOICE_SPEED", "0.90")),
        # OpenAI TTS settings (fallback)
        openai_tts_model=os.getenv("VIVENTIUM_OPENAI_TTS_MODEL", "gpt-4o-mini-tts").strip()
        or "gpt-4o-mini-tts",
        openai_tts_voice=os.getenv("VIVENTIUM_OPENAI_TTS_VOICE", "coral").strip() or "coral",
        openai_tts_speed=_parse_float_env("VIVENTIUM_OPENAI_TTS_SPEED", 1.12),
        openai_tts_instructions=(
            os.getenv(
                "VIVENTIUM_OPENAI_TTS_INSTRUCTIONS",
                "Speak naturally and warmly with clear pacing. Keep the delivery conversational, grounded, and human. Avoid robotic emphasis or exaggerated pauses.",
            ).strip()
            or "Speak naturally and warmly with clear pacing. Keep the delivery conversational, grounded, and human. Avoid robotic emphasis or exaggerated pauses."
        ),
        # Cartesia TTS settings
        cartesia_api_url=os.getenv("VIVENTIUM_CARTESIA_API_URL", "https://api.cartesia.ai/tts/bytes").strip()
        or "https://api.cartesia.ai/tts/bytes",
        cartesia_ws_url=os.getenv("VIVENTIUM_CARTESIA_WS_URL", "wss://api.cartesia.ai/tts/websocket").strip()
        or "wss://api.cartesia.ai/tts/websocket",
        cartesia_api_version=os.getenv(
            "VIVENTIUM_CARTESIA_API_VERSION",
            DEFAULT_CARTESIA_API_VERSION,
        ).strip()
        or DEFAULT_CARTESIA_API_VERSION,
        cartesia_model_id=_cartesia_model_id_from_env(),
        cartesia_voice_id=os.getenv(
            "VIVENTIUM_CARTESIA_VOICE_ID",
            DEFAULT_CARTESIA_VOICE_ID,
        ).strip()
        or DEFAULT_CARTESIA_VOICE_ID,
        cartesia_sample_rate=int(float(os.getenv("VIVENTIUM_CARTESIA_SAMPLE_RATE", "44100"))),
        cartesia_speed=float(os.getenv("VIVENTIUM_CARTESIA_SPEED", "1.0")),
        cartesia_volume=float(os.getenv("VIVENTIUM_CARTESIA_VOLUME", "1.0")),
        cartesia_emotion=os.getenv("VIVENTIUM_CARTESIA_EMOTION", "neutral").strip() or "neutral",
        cartesia_max_buffer_delay_ms=_parse_int_env("VIVENTIUM_CARTESIA_MAX_BUFFER_DELAY_MS", 120),
        # === VIVENTIUM START ===
        # Feature: Cartesia emotion segment spacing
        cartesia_segment_silence_ms=int(float(os.getenv("VIVENTIUM_CARTESIA_SEGMENT_SILENCE_MS", "80"))),
        cartesia_language=os.getenv("VIVENTIUM_CARTESIA_LANGUAGE", "en").strip() or "en",
        # === VIVENTIUM END ===
        mlx_audio_model_id=(
            os.getenv("VIVENTIUM_MLX_AUDIO_MODEL_ID", "").strip()
            or "mlx-community/chatterbox-turbo-8bit"
        ),
        # === VIVENTIUM START ===
        # Feature: non-blocking background follow-up window
        voice_followup_timeout_s=_parse_float_env("VIVENTIUM_VOICE_FOLLOWUP_TIMEOUT_S", 60.0),
        voice_followup_interval_s=_parse_float_env("VIVENTIUM_VOICE_FOLLOWUP_INTERVAL_S", 1.0),
        voice_followup_grace_s=_parse_float_env("VIVENTIUM_VOICE_FOLLOWUP_GRACE_S", 30.0),
        voice_glasshive_timeout_s=_parse_float_env("VIVENTIUM_VOICE_GLASSHIVE_TIMEOUT_S", 600.0),
        voice_initialize_process_timeout_s=_parse_float_env(
            "VIVENTIUM_VOICE_INITIALIZE_PROCESS_TIMEOUT_S",
            default_initialize_process_timeout_s,
        ),
        voice_idle_processes=max(
            0,
            _parse_int_env("VIVENTIUM_VOICE_IDLE_PROCESSES", default_idle_processes),
        ),
        voice_worker_load_threshold=max(
            0.1,
            _parse_worker_load_threshold_env(
                "VIVENTIUM_VOICE_WORKER_LOAD_THRESHOLD",
                default_load_threshold,
            ),
        ),
        voice_job_memory_warn_mb=_parse_float_env(
            "VIVENTIUM_VOICE_JOB_MEMORY_WARN_MB",
            default_job_memory_warn_mb,
        ),
        voice_job_memory_limit_mb=_parse_float_env(
            "VIVENTIUM_VOICE_JOB_MEMORY_LIMIT_MB",
            0.0,
        ),
        voice_prewarm_local_tts=_parse_bool_env(
            "VIVENTIUM_VOICE_PREWARM_LOCAL_TTS",
            default_prewarm_local_tts,
        ),
        voice_requested_turn_detection=requested_turn_detection,
        voice_turn_detection=str(turn_handling_profile["voice_turn_detection"]),
        voice_configured_min_interruption_words=configured_min_interruption_words,
        voice_configured_min_endpointing_delay_s=configured_min_endpointing_delay_s,
        voice_configured_max_endpointing_delay_s=configured_max_endpointing_delay_s,
        voice_configured_min_consecutive_speech_delay_s=configured_min_consecutive_speech_delay_s,
        voice_min_interruption_duration_s=_parse_float_env(
            "VIVENTIUM_VOICE_MIN_INTERRUPTION_DURATION_S",
            0.5,
        ),
        voice_min_interruption_words=int(turn_handling_profile["voice_min_interruption_words"]),
        voice_min_endpointing_delay_s=float(turn_handling_profile["voice_min_endpointing_delay_s"]),
        voice_max_endpointing_delay_s=float(turn_handling_profile["voice_max_endpointing_delay_s"]),
        voice_false_interruption_timeout_s=_parse_optional_timeout_env(
            "VIVENTIUM_VOICE_FALSE_INTERRUPTION_TIMEOUT_S",
            2.0,
        ),
        voice_resume_false_interruption=_parse_bool_env(
            "VIVENTIUM_VOICE_RESUME_FALSE_INTERRUPTION",
            True,
        ),
        voice_min_consecutive_speech_delay_s=float(
            turn_handling_profile["voice_min_consecutive_speech_delay_s"]
        ),
        voice_aec_warmup_duration_s=_parse_optional_timeout_env(
            "VIVENTIUM_VOICE_AEC_WARMUP_DURATION_S",
            _default_aec_warmup_duration(normalized_stt_provider),
        ),
        assemblyai_stt_model=_normalize_assemblyai_stt_model(
            os.getenv("VIVENTIUM_ASSEMBLYAI_STT_MODEL", "")
        ),
        assemblyai_end_of_turn_confidence_threshold=_parse_optional_float_env(
            "VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD",
        ),
        assemblyai_min_end_of_turn_silence_when_confident_ms=_parse_optional_int_env(
            "VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS"
        ),
        assemblyai_max_turn_silence_ms=_parse_optional_int_env(
            "VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS"
        ),
        assemblyai_format_turns=_parse_bool_env(
            "VIVENTIUM_ASSEMBLYAI_FORMAT_TURNS",
            False,
        ),
        # === VIVENTIUM END ===
    )

def load_turn_detection(env: Env, has_vad: bool) -> tuple[Any, str]:
    """
    LiveKit Agents `AgentSession(turn_detection=...)` accepts string modes:
      - "stt" | "vad" | "realtime_llm" | "manual"

    Viventium defaults to context-aware paths when the configured STT/runtime supports them:
      - semantic turn detector when installed for supported STT providers
      - STT endpointing next
      - VAD fallback otherwise
    """
    mode = env.voice_turn_detection
    if mode == "turn_detector":
        ready, status = _semantic_turn_detector_status(env.stt_provider)
        if ready:
            detector_model_cls = _load_turn_detector_model_class()
            if detector_model_cls is not None:
                return detector_model_cls(), "semantic_turn_detector"

        logger.warning(
            "VIVENTIUM_TURN_DETECTION=%s requested but turn detector is unavailable for provider=%s status=%s; falling back.",
            mode,
            env.stt_provider,
            status,
        )
        mode = "stt" if _supports_stt_endpointing(env.stt_provider) else "vad"

    if mode in {"stt", "vad", "realtime_llm", "manual"}:
        if mode == "vad" and not has_vad:
            logger.warning(
                "VIVENTIUM_TURN_DETECTION=vad but silero VAD is unavailable; falling back to 'stt'."
            )
            return "stt", "stt_end_of_turn"
        return mode, _turn_end_reason_for_mode(mode)

    fallback_mode = "vad" if has_vad else "stt"
    fallback_reason = "vad_silence" if fallback_mode == "vad" else "stt_end_of_turn"
    return fallback_mode, fallback_reason


def _parse_call_session_id(metadata: str) -> Optional[str]:
    obj = _parse_metadata_json(metadata)
    call_session_id = obj.get("callSessionId") or obj.get("call_session_id")
    if isinstance(call_session_id, str) and call_session_id.strip():
        return call_session_id.strip()
    return None


def _parse_requested_voice_route(metadata: str) -> dict[str, dict[str, Optional[str]]]:
    obj = _parse_metadata_json(metadata)
    return _normalize_requested_voice_route(obj.get("requestedVoiceRoute"))


async def _await_participant_call_session_id(
    ctx: JobContext,
    *,
    timeout_s: float = 3.0,
    interval_s: float = 0.25,
) -> Optional[str]:
    if timeout_s <= 0:
        return None
    deadline = time.monotonic() + max(0.0, float(timeout_s))
    interval = max(0.05, float(interval_s))
    while time.monotonic() < deadline:
        try:
            for participant in ctx.room.remote_participants.values():
                meta = getattr(participant, "metadata", "") or ""
                call_session_id = _parse_call_session_id(meta)
                if call_session_id:
                    return call_session_id
        except Exception:
            pass
        await asyncio.sleep(interval)
    return None


def _validate_ref_audio_path(ref_audio_raw: Optional[str], *, min_duration_s: float = 5.0) -> tuple[Optional[str], Optional[str]]:
    return shared_validate_ref_audio_path(ref_audio_raw, min_duration_s=min_duration_s)


def _build_local_chatterbox_config(model_id_override: Optional[str] = None) -> tuple[MlxChatterboxConfig, Optional[str]]:
    return shared_build_local_chatterbox_config(model_id_override)


# === VIVENTIUM START ===
# Feature: Voice session lease claim
async def _claim_voice_session(origin: str, auth: LibreChatAuth) -> bool:
    if not auth.call_session_id:
        return False
    if not auth.call_secret:
        return False
    if not auth.job_id:
        logger.error("[voice-gateway] Missing job id for voice lease claim")
        return False

    url = f"{origin.rstrip('/')}/api/viventium/voice/claim"
    headers = {
        "X-VIVENTIUM-CALL-SESSION": auth.call_session_id,
        "X-VIVENTIUM-CALL-SECRET": auth.call_secret,
        "X-VIVENTIUM-JOB-ID": auth.job_id,
    }
    if auth.worker_id:
        headers["X-VIVENTIUM-WORKER-ID"] = auth.worker_id

    timeout = aiohttp.ClientTimeout(total=5)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers) as resp:
                if resp.status == 200:
                    return True
                body = await resp.text()
                logger.warning(
                    "[voice-gateway] Voice lease claim rejected (status=%s, body=%s)",
                    resp.status,
                    body,
                )
    except Exception as exc:
        logger.warning("[voice-gateway] Voice lease claim failed: %s", exc)
    return False
# === VIVENTIUM END ===


# === VIVENTIUM START ===
# Feature: Room-level diagnostics for silent input failures.
# Purpose:
# - Log participant and track mute transitions with callSessionId so future RCAs can
#   prove whether browser input stopped while the worker and room stayed healthy.
def _track_source_label(publication: Any) -> str:
    source = getattr(publication, "source", None)
    if source is None:
        info = getattr(publication, "_info", None)
        source = getattr(info, "source", None)
    if source is None:
        return "unknown"
    return str(source).split(".")[-1].lower()


def _remote_participant_count(room: Any) -> int:
    participants = getattr(room, "remote_participants", None)
    if participants is None:
        return 0
    try:
        return len(participants)
    except TypeError:
        return 0


def _attach_room_diagnostics(
    ctx: JobContext,
    *,
    call_session_id: str,
    active_job_marker: Path | None = None,
) -> None:
    room = ctx.room
    room_name = getattr(room, "name", "") or "<unknown>"

    @room.on("participant_connected")
    def _on_participant_connected(participant: Any) -> None:
        logger.info(
            "[voice-gateway] participant connected room=%s callSessionId=%s identity=%s",
            room_name,
            call_session_id,
            getattr(participant, "identity", "<unknown>"),
        )

    @room.on("participant_disconnected")
    def _on_participant_disconnected(participant: Any) -> None:
        logger.info(
            "[voice-gateway] participant disconnected room=%s callSessionId=%s identity=%s",
            room_name,
            call_session_id,
            getattr(participant, "identity", "<unknown>"),
        )
        if active_job_marker is not None:
            def _clear_marker_if_room_empty() -> None:
                if _remote_participant_count(room) == 0:
                    _clear_active_voice_job_marker(active_job_marker)

            try:
                asyncio.get_running_loop().call_later(0.25, _clear_marker_if_room_empty)
            except RuntimeError:
                _clear_marker_if_room_empty()

    @room.on("track_muted")
    def _on_track_muted(participant: Any, publication: Any) -> None:
        source = _track_source_label(publication)
        log_method = logger.warning if source == "source_microphone" else logger.info
        log_method(
            "[voice-gateway] track muted room=%s callSessionId=%s identity=%s source=%s sid=%s",
            room_name,
            call_session_id,
            getattr(participant, "identity", "<unknown>"),
            source,
            getattr(publication, "sid", "<unknown>"),
        )

    @room.on("track_unmuted")
    def _on_track_unmuted(participant: Any, publication: Any) -> None:
        logger.info(
            "[voice-gateway] track unmuted room=%s callSessionId=%s identity=%s source=%s sid=%s",
            room_name,
            call_session_id,
            getattr(participant, "identity", "<unknown>"),
            _track_source_label(publication),
            getattr(publication, "sid", "<unknown>"),
        )
# === VIVENTIUM END ===


def _silero_vad_kwargs_for_env(env: Optional[Env] = None) -> dict[str, Any]:
    source = os.environ
    if env is not None and _is_local_whisper_stt(env.stt_provider):
        source = dict(os.environ)
        if not (os.getenv("VIVENTIUM_STT_VAD_MIN_SPEECH") or "").strip():
            source["VIVENTIUM_STT_VAD_MIN_SPEECH"] = _LOCAL_WHISPER_VAD_MIN_SPEECH_S
        if not (os.getenv("VIVENTIUM_STT_VAD_MIN_SILENCE") or "").strip():
            source["VIVENTIUM_STT_VAD_MIN_SILENCE"] = _LOCAL_WHISPER_VAD_MIN_SILENCE_S
    return get_silero_vad_kwargs(source)


def _vad_kwargs_cache_key(vad_kwargs: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((key, str(value)) for key, value in vad_kwargs.items()))


def load_vad(env: Optional[Env] = None) -> Optional[Any]:
    if not HAS_SILERO:
        logger.warning("Silero VAD not available; turn detection will fall back to STT.")
        return None
    # === VIVENTIUM START ===
    # Feature: VAD tuning parity with v1
    # === VIVENTIUM END ===
    try:
        vad_kwargs = _silero_vad_kwargs_for_env(env)
        logger.info(
            "Loading shared Silero VAD min_speech=%ss min_silence=%ss activation=%s max_buffered_speech=%ss force_cpu=%s",
            vad_kwargs["min_speech_duration"],
            vad_kwargs["min_silence_duration"],
            vad_kwargs["activation_threshold"],
            vad_kwargs["max_buffered_speech"],
            vad_kwargs["force_cpu"],
        )
        return silero_vad.VAD.load(**vad_kwargs)
    except Exception as exc:
        logger.warning("Failed to load Silero VAD (%s); falling back to STT.", exc)
        return None


# === VIVENTIUM START ===
# Feature: STT provider selection (AssemblyAI + local whisper.cpp)
# Added: 2026-01-11
# === VIVENTIUM END ===
def _build_assemblyai_stt_kwargs(env: Env) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    # Pass the selected/configured engine through to the plugin. Without this the variant chosen in
    # the Listening picker (or VIVENTIUM_ASSEMBLYAI_STT_MODEL) is ignored and AssemblyAI falls back
    # to its own plugin default. Normalized so an unknown value can never reach the provider.
    kwargs["model"] = _normalize_assemblyai_stt_model(env.assemblyai_stt_model)
    if env.assemblyai_end_of_turn_confidence_threshold is not None:
        kwargs["end_of_turn_confidence_threshold"] = env.assemblyai_end_of_turn_confidence_threshold
    if env.assemblyai_min_end_of_turn_silence_when_confident_ms is not None:
        # Keep the existing env/config surface for backward compatibility, but map it onto the
        # current provider knob name so we do not rely on AssemblyAI's deprecated alias.
        kwargs["min_turn_silence"] = env.assemblyai_min_end_of_turn_silence_when_confident_ms
    if env.assemblyai_max_turn_silence_ms is not None:
        kwargs["max_turn_silence"] = env.assemblyai_max_turn_silence_ms
    if env.assemblyai_format_turns:
        kwargs["format_turns"] = True
    return kwargs


def build_stt_selection(env: Env, vad: Optional[Any]) -> tuple[Any, str]:
    provider = _normalize_stt_provider(env.stt_provider)

    if provider == "assemblyai":
        if not HAS_ASSEMBLYAI:
            logger.warning(
                "AssemblyAI STT requested but plugin not installed. "
                "Install with: pip install livekit-plugins-assemblyai"
            )
        elif not (os.getenv("ASSEMBLYAI_API_KEY") or "").strip():
            logger.warning("ASSEMBLYAI_API_KEY not set; falling back to local/openai STT.")
        else:
            assemblyai_kwargs = _build_assemblyai_stt_kwargs(env)
            logger.info(
                "Using AssemblyAI STT%s",
                ""
                if not assemblyai_kwargs
                else " with " + ", ".join(f"{key}={value}" for key, value in assemblyai_kwargs.items()),
            )
            return assemblyai_stt.STT(**assemblyai_kwargs), "assemblyai"

    if provider in {"pywhispercpp", "whisper_local"}:
        try:
            from pywhispercpp_provider import get_stt as get_pywhispercpp_stt
            logger.info("Using PyWhisperCpp STT (whisper.cpp local)")
            return (
                get_pywhispercpp_stt(model_name=env.stt_model, language=env.stt_language),
                "pywhispercpp",
            )
        except Exception as exc:
            raise RuntimeError(
                "Local Whisper.cpp STT was selected but could not be made ready. "
                "The voice gateway will not silently switch to another STT provider."
            ) from exc

    if provider == "whisperlivekit":
        logger.warning("whisperlivekit STT not bundled in voice-gateway; falling back.")

    if provider not in {"openai", "assemblyai", "pywhispercpp", "whisper_local", "whisperlivekit"}:
        logger.warning("Unknown STT provider '%s'; falling back to OpenAI STT.", provider)

    stt_impl = openai.STT(model=env.openai_stt_model)
    if vad is not None:
        try:
            from livekit.agents.stt.stream_adapter import StreamAdapter
            stt_impl = StreamAdapter(stt=stt_impl, vad=vad)
            logger.info("OpenAI STT wrapped with StreamAdapter+VAD for streaming support")
        except Exception as exc:
            logger.warning("Failed to wrap OpenAI STT with StreamAdapter: %s", exc)
    else:
        logger.warning(
            "OpenAI STT selected without VAD; streaming may fail. "
            "Install livekit-plugins-silero or use assemblyai/whisper_local."
        )
    return stt_impl, "openai"


def build_stt(env: Env, vad: Optional[Any]) -> Any:
    stt_impl, _provider = build_stt_selection(env, vad)
    return stt_impl


def prewarm_process(proc: JobProcess) -> None:
    env = load_env()
    proc.userdata["voice_env"] = env

    prewarmed_vad_kwargs = _silero_vad_kwargs_for_env(env)
    prewarmed_vad = load_vad(env)
    if prewarmed_vad is not None:
        proc.userdata["prewarmed_vad"] = prewarmed_vad
        proc.userdata["prewarmed_vad_kwargs_key"] = _vad_kwargs_cache_key(prewarmed_vad_kwargs)

    provider = _normalize_stt_provider(env.stt_provider)
    if provider in {"pywhispercpp", "whisper_local"}:
        from pywhispercpp_provider import prewarm_model

        _wait_for_active_voice_jobs_before_prewarm()
        logger.info(
            "[voice-gateway] Prewarming local whisper.cpp STT model (%s)",
            env.stt_model,
        )
        try:
            prewarm_model(env.stt_model)
        except Exception as exc:
            logger.error(
                "[voice-gateway] Local whisper.cpp STT prewarm failed for %s; refusing to register an unhealthy local STT worker: %s",
                env.stt_model,
                exc,
            )
            raise RuntimeError(
                f"Local Whisper.cpp STT prewarm failed for {env.stt_model}; worker will not register."
            ) from exc

    tts_providers = {
        _normalize_voice_provider(env.tts_provider),
        _normalize_voice_provider(env.tts_provider_fallback),
    }
    if "local_chatterbox_turbo_mlx_8bit" in tts_providers and env.voice_prewarm_local_tts:
        try:
            config, ref_audio_warning = _build_local_chatterbox_config(env.mlx_audio_model_id)
            if ref_audio_warning:
                logger.warning("%s; using default voice.", ref_audio_warning)
            prewarmed_tts = MlxChatterboxTTS(config=config)
            logger.info(
                "[voice-gateway] Prewarming local Chatterbox TTS at process startup (model=%s)",
                config.model_id,
            )
            prewarmed_tts.prewarm()
            proc.userdata["prewarmed_local_chatterbox_tts"] = prewarmed_tts
        except Exception:
            logger.warning(
                "[voice-gateway] Failed to prewarm local Chatterbox TTS at process startup; first call may be slow",
                exc_info=True,
            )


def _merge_insights(
    base: list[dict[str, Any]], extra: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not extra:
        return base
    seen: set[tuple[Optional[str], Optional[str]]] = set()
    for item in base:
        if not isinstance(item, dict):
            continue
        seen.add((item.get("cortex_id"), item.get("insight")))
    for item in extra:
        if not isinstance(item, dict):
            continue
        key = (item.get("cortex_id"), item.get("insight"))
        if key in seen:
            continue
        seen.add(key)
        base.append(item)
    return base


def _turn_detection_label(turn_detection: Any) -> str:
    if isinstance(turn_detection, str):
        return turn_detection
    if turn_detection is not None:
        return "turn_detector"
    return "unknown"


def _turn_end_reason_label(turn_detection: Any) -> str:
    if isinstance(turn_detection, str):
        if turn_detection == "stt":
            return "stt_end_of_turn"
        if turn_detection == "vad":
            return "vad_silence"
        return turn_detection
    if turn_detection is not None:
        return "semantic_turn_detector"
    return "unknown"


def _voice_sync_transcription_enabled() -> bool:
    return _parse_bool_env("VIVENTIUM_VOICE_SYNC_TRANSCRIPTION", False)


def _build_room_options(*, sync_transcription: bool) -> Any:
    return room_io.RoomOptions(
        text_output=room_io.TextOutputOptions(sync_transcription=sync_transcription)
    )


def _metric_value(metrics: Any, key: str) -> Optional[float]:
    if metrics is None:
        return None
    raw = metrics.get(key) if isinstance(metrics, dict) else getattr(metrics, key, None)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _metric_ms(metrics: Any, key: str) -> str:
    value = _metric_value(metrics, key)
    return "n/a" if value is None else f"{value * 1000.0:.3f}"


def _metric_seconds(metrics: Any, key: str) -> float:
    value = _metric_value(metrics, key)
    return 0.0 if value is None else value


# === VIVENTIUM START ===
# Feature: Cartesia voice-control tags are TTS-only, never user transcript text.
class ViventiumVoiceAgent(Agent):
    async def transcription_node(self, text: Any, model_settings: Any) -> Any:
        display_filter = VoiceControlDisplayFilter()
        async for delta in text:
            cleaned = display_filter.feed(str(delta))
            if not cleaned:
                continue
            if isinstance(delta, TimedString):
                yield TimedString(
                    cleaned,
                    start_time=delta.start_time,
                    end_time=delta.end_time,
                    confidence=delta.confidence,
                    start_time_offset=delta.start_time_offset,
                    speaker_id=delta.speaker_id,
                )
            else:
                yield cleaned

        trailing = display_filter.feed("", final=True)
        if trailing:
            yield trailing


# === VIVENTIUM END ===


# === VIVENTIUM START ===
# Feature: Non-blocking background insight follow-ups for voice calls
class CortexFollowupScheduler:
    def __init__(
        self,
        *,
        origin: str,
        auth: LibreChatAuth,
        session: AgentSession,
        timeout_s: float,
        interval_s: float,
        grace_s: float,
        glasshive_timeout_s: Optional[float] = None,
    ) -> None:
        self._origin = origin.rstrip("/")
        self._auth = auth
        self._session = session
        self._timeout_s = max(0.0, float(timeout_s))
        self._interval_s = max(0.25, float(interval_s))
        self._grace_s = max(0.0, float(grace_s))
        self._glasshive_timeout_s = max(
            0.0,
            float(self._timeout_s if glasshive_timeout_s is None else glasshive_timeout_s),
        )
        self._seq = 0
        self._task: Optional[asyncio.Task[None]] = None
        self._cortex_task: Optional[asyncio.Task[None]] = None
        self._glasshive_tasks: set[asyncio.Task[None]] = set()
        self._glasshive_task_warning_threshold = 4

    def schedule(
        self,
        message_id: str,
        pending_insights: list[dict[str, Any]],
        recent_response: str,
        *,
        cortex_expected: Optional[bool] = None,
        glasshive_expected: bool = False,
    ) -> None:
        _ = recent_response
        should_poll_cortex = bool(pending_insights) if cortex_expected is None else bool(cortex_expected)
        should_poll_glasshive = bool(glasshive_expected)
        if not message_id or not (should_poll_cortex or should_poll_glasshive):
            return
        self._seq += 1
        seq = self._seq
        allow_stale_delivery = should_poll_glasshive
        if _voice_latency_log_enabled():
            logger.info(
                "[VoiceLatency][Followup] scheduled seq=%s message_id=%s cortex_expected=%s pending_insights=%s glasshive_expected=%s timeout_s=%.3f grace_s=%.3f interval_s=%.3f",
                seq,
                message_id,
                should_poll_cortex,
                len(pending_insights or []),
                should_poll_glasshive,
                self._timeout_s,
                self._grace_s,
                self._interval_s,
            )
        if not should_poll_glasshive and self._cortex_task and not self._cortex_task.done():
            self._cortex_task.cancel()
        task = asyncio.create_task(
            self._run(
                seq,
                message_id,
                pending_insights,
                should_poll_cortex=should_poll_cortex,
                should_poll_glasshive=should_poll_glasshive,
                allow_stale_delivery=allow_stale_delivery,
            )
        )
        self._task = task
        if should_poll_glasshive:
            self._glasshive_tasks.add(task)
            task.add_done_callback(self._glasshive_tasks.discard)
            if len(self._glasshive_tasks) > self._glasshive_task_warning_threshold:
                logger.warning(
                    "voice GlassHive follow-up polling has %s concurrent tasks",
                    len(self._glasshive_tasks),
                )
        else:
            self._cortex_task = task

    async def _run(
        self,
        seq: int,
        message_id: str,
        pending_insights: list[dict[str, Any]],
        *,
        should_poll_cortex: bool,
        should_poll_glasshive: bool,
        allow_stale_delivery: bool,
    ) -> None:
        try:
            started_at = time.monotonic()
            log_latency = _voice_latency_log_enabled()
            deadline_window = max(
                self._timeout_s if should_poll_cortex else 0.0,
                self._glasshive_timeout_s if should_poll_glasshive else 0.0,
            )
            if deadline_window <= 0:
                return
            if log_latency:
                logger.info(
                    "[VoiceLatency][Followup] poll_start seq=%s message_id=%s cortex=%s glasshive=%s timeout_s=%.3f",
                    seq,
                    message_id,
                    should_poll_cortex,
                    should_poll_glasshive,
                    deadline_window,
                )
            deadline = started_at + deadline_window
            cortex_deadline = started_at + self._timeout_s
            merged_insights: list[dict[str, Any]] = list(pending_insights or [])
            # === VIVENTIUM START ===
            # Feature: Speak only main-agent Phase B follow-ups in live voice.
            # Updated: 2026-04-21
            #
            # Why:
            # - SSE captures cortex completion during the main stream, so pending_insights
            #   is often already non-empty when the poller starts.
            # - Those insight rows are internal background cognition, not user-facing speech.
            # - Modern playground/TTS should only hear the main agent's conscious outputs:
            #   (1) the immediate Phase A response and (2) a persisted main-agent Phase B
            #   follow-up message when one is actually generated.
            #
            # Contract:
            # - start the grace timer only when the poller first sees persisted insights
            # - if a real follow-up arrives, speak it
            # - if no follow-up arrives by grace/timeout, stay silent
            first_insight_at: Optional[float] = None
            # === VIVENTIUM END ===

            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                while time.monotonic() < deadline:
                    if not allow_stale_delivery and seq != self._seq:
                        if log_latency:
                            logger.info(
                                "[VoiceLatency][Followup] stale_cancel_ms=%s seq=%s message_id=%s latest_seq=%s",
                                int((time.monotonic() - started_at) * 1000),
                                seq,
                                message_id,
                                self._seq,
                            )
                        return

                    if should_poll_glasshive:
                        glasshive_data = await self._fetch_glasshive(session, message_id)
                        if isinstance(glasshive_data, dict):
                            latest = glasshive_data.get("latest")
                            if isinstance(latest, dict):
                                text = latest.get("text")
                                if (
                                    isinstance(text, str)
                                    and text.strip()
                                    and _glasshive_callback_is_terminal(latest)
                                ):
                                    delivery = await self._claim_glasshive_delivery(session, latest)
                                    if delivery:
                                        text = str(
                                            delivery.get("fullText")
                                            or delivery.get("text")
                                            or text
                                        ).strip()
                                    else:
                                        text = text.strip()
                                    if is_no_response_only(text):
                                        if log_latency:
                                            logger.info(
                                                "[VoiceLatency][Followup] glasshive_no_response_ms=%s seq=%s message_id=%s",
                                                int((time.monotonic() - started_at) * 1000),
                                                seq,
                                                message_id,
                                            )
                                        if delivery:
                                            await self._mark_glasshive_delivery_status(
                                                session,
                                                delivery,
                                                "suppressed",
                                                reason="{NTA}",
                                            )
                                        return
                                    if log_latency:
                                        logger.info(
                                            "[VoiceLatency][Followup] glasshive_found_ms=%s seq=%s message_id=%s text_chars=%s",
                                            int((time.monotonic() - started_at) * 1000),
                                            seq,
                                            message_id,
                                            len(text),
                                        )
                                    spoken = self._speak(
                                        text,
                                        seq,
                                        allow_stale_delivery=allow_stale_delivery,
                                    )
                                    if log_latency:
                                        logger.info(
                                            "[VoiceLatency][Followup] glasshive_speak_result_ms=%s seq=%s message_id=%s spoken=%s",
                                            int((time.monotonic() - started_at) * 1000),
                                            seq,
                                            message_id,
                                            spoken,
                                        )
                                    if delivery:
                                        await self._mark_glasshive_delivery_status(
                                            session,
                                            delivery,
                                            "sent" if spoken else "failed",
                                            error="" if spoken else "voice follow-up was not spoken",
                                        )
                                    return

                    data = None
                    if should_poll_cortex and time.monotonic() < cortex_deadline:
                        data = await self._fetch_cortex(session, message_id)
                    if isinstance(data, dict):
                        follow_up = data.get("followUp")
                        if isinstance(follow_up, dict):
                            text = follow_up.get("text")
                            if isinstance(text, str) and text.strip():
                                text = text.strip()
                                if is_no_response_only(text):
                                    if log_latency:
                                        logger.info(
                                            "[VoiceLatency][Followup] cortex_no_response_ms=%s seq=%s message_id=%s",
                                            int((time.monotonic() - started_at) * 1000),
                                            seq,
                                            message_id,
                                        )
                                    logger.info(
                                        "[voice-gateway] Suppressing follow-up speech (no-response): message_id=%s",
                                        message_id,
                                    )
                                    return
                                if log_latency:
                                    logger.info(
                                        "[VoiceLatency][Followup] cortex_followup_found_ms=%s seq=%s message_id=%s text_chars=%s",
                                        int((time.monotonic() - started_at) * 1000),
                                        seq,
                                        message_id,
                                        len(text),
                                    )
                                spoken = self._speak(text, seq, allow_stale_delivery=allow_stale_delivery)
                                if log_latency:
                                    logger.info(
                                        "[VoiceLatency][Followup] cortex_speak_result_ms=%s seq=%s message_id=%s spoken=%s",
                                        int((time.monotonic() - started_at) * 1000),
                                        seq,
                                        message_id,
                                        spoken,
                                    )
                                return

                        followup_decision = _terminal_cortex_followup_decision(
                            data.get("followUpDecision")
                        )
                        if followup_decision is not None:
                            if log_latency:
                                logger.info(
                                    "[VoiceLatency][Followup] cortex_decision_terminal_ms=%s seq=%s message_id=%s result=%s reason=%s llm_result=%s strategy=%s",
                                    int((time.monotonic() - started_at) * 1000),
                                    seq,
                                    message_id,
                                    followup_decision.get("result") or "",
                                    followup_decision.get("suppressionReason") or "none",
                                    followup_decision.get("llmResult") or "",
                                    followup_decision.get("selectedStrategy") or "",
                                )
                            logger.info(
                                "[voice-gateway] Cortex follow-up decision is terminal and silent: message_id=%s result=%s reason=%s",
                                message_id,
                                followup_decision.get("result") or "",
                                followup_decision.get("suppressionReason") or "none",
                            )
                            return

                        insights = data.get("insights")
                        if isinstance(insights, list):
                            merged_insights = _merge_insights(merged_insights, insights)
                            if merged_insights and first_insight_at is None:
                                first_insight_at = time.monotonic()
                                if log_latency:
                                    logger.info(
                                        "[VoiceLatency][Followup] insights_seen_ms=%s seq=%s message_id=%s count=%s",
                                        int((first_insight_at - started_at) * 1000),
                                        seq,
                                        message_id,
                                        len(merged_insights),
                                    )

                    if merged_insights and first_insight_at is not None:
                        grace_deadline = first_insight_at + self._grace_s
                        if time.monotonic() >= grace_deadline:
                            if log_latency:
                                logger.info(
                                    "[VoiceLatency][Followup] insight_grace_expired_ms=%s seq=%s message_id=%s",
                                    int((time.monotonic() - started_at) * 1000),
                                    seq,
                                    message_id,
                                )
                            logger.info(
                                "[voice-gateway] No persisted follow-up before insight grace window expired; keeping background insights silent: message_id=%s",
                                message_id,
                            )
                            return

                    await asyncio.sleep(self._interval_s)

            if not allow_stale_delivery and seq != self._seq:
                return
            if merged_insights:
                if log_latency:
                    logger.info(
                        "[VoiceLatency][Followup] timed_out_after_insights_ms=%s seq=%s message_id=%s count=%s",
                        int((time.monotonic() - started_at) * 1000),
                        seq,
                        message_id,
                        len(merged_insights),
                    )
                logger.info(
                    "[voice-gateway] Follow-up polling timed out after insights with no persisted follow-up; keeping background insights silent: message_id=%s",
                    message_id,
                )
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.warning("[voice-gateway] Follow-up polling failed: %s", exc)

    async def _fetch_cortex(
        self, session: aiohttp.ClientSession, message_id: str
    ) -> Optional[dict[str, Any]]:
        url = f"{self._origin}/api/viventium/voice/cortex/{message_id}"
        headers = {
            "X-VIVENTIUM-CALL-SESSION": self._auth.call_session_id,
            "X-VIVENTIUM-CALL-SECRET": self._auth.call_secret,
        }
        if self._auth.job_id:
            headers["X-VIVENTIUM-JOB-ID"] = self._auth.job_id
        if self._auth.worker_id:
            headers["X-VIVENTIUM-WORKER-ID"] = self._auth.worker_id
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    payload = await resp.json()
                    if isinstance(payload, dict):
                        return payload
                    return None
                if resp.status in {401, 403}:
                    logger.warning(
                        "[voice-gateway] Follow-up poll unauthorized (status=%s)", resp.status
                    )
                    return None
                if resp.status != 404:
                    body = await resp.text()
                    logger.warning(
                        "[voice-gateway] Follow-up poll failed (status=%s, body=%s)",
                        resp.status,
                        body,
                    )
        except Exception:
            return None

    async def _fetch_glasshive(
        self, session: aiohttp.ClientSession, message_id: str
    ) -> Optional[dict[str, Any]]:
        if self._glasshive_timeout_s <= 0:
            return None
        url = f"{self._origin}/api/viventium/voice/glasshive/{message_id}"
        headers = {
            "X-VIVENTIUM-CALL-SESSION": self._auth.call_session_id,
            "X-VIVENTIUM-CALL-SECRET": self._auth.call_secret,
        }
        if self._auth.job_id:
            headers["X-VIVENTIUM-JOB-ID"] = self._auth.job_id
        if self._auth.worker_id:
            headers["X-VIVENTIUM-WORKER-ID"] = self._auth.worker_id
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    payload = await resp.json()
                    if isinstance(payload, dict):
                        return payload
                    return None
                if resp.status in {401, 403}:
                    logger.warning(
                        "[voice-gateway] GlassHive poll unauthorized (status=%s)", resp.status
                    )
                    return None
                if resp.status != 404:
                    body = await resp.text()
                    logger.warning(
                        "[voice-gateway] GlassHive poll failed (status=%s, body=%s)",
                        resp.status,
                        body,
                    )
        except Exception:
            return None
        return None

    async def _claim_glasshive_delivery(
        self, session: aiohttp.ClientSession, latest: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        callback_id = str(latest.get("callbackId") or latest.get("callback_id") or "").strip()
        if not callback_id:
            return None
        url = f"{self._origin}/api/viventium/voice/glasshive/deliveries/claim"
        headers = {
            "X-VIVENTIUM-CALL-SESSION": self._auth.call_session_id,
            "X-VIVENTIUM-CALL-SECRET": self._auth.call_secret,
        }
        if self._auth.job_id:
            headers["X-VIVENTIUM-JOB-ID"] = self._auth.job_id
        if self._auth.worker_id:
            headers["X-VIVENTIUM-WORKER-ID"] = self._auth.worker_id
        try:
            async with session.post(
                url,
                headers=headers,
                json={
                    "callbackId": callback_id,
                    "leaseMs": 600_000,
                    "dispatcherId": f"voice-{self._auth.call_session_id}",
                },
            ) as resp:
                if resp.status != 200:
                    return None
                payload = await resp.json()
                deliveries = payload.get("deliveries") if isinstance(payload, dict) else None
                if isinstance(deliveries, list) and deliveries:
                    first = deliveries[0]
                    return first if isinstance(first, dict) else None
        except Exception:
            return None
        return None

    async def _mark_glasshive_delivery_status(
        self,
        session: aiohttp.ClientSession,
        delivery: dict[str, Any],
        status: str,
        *,
        error: str = "",
        reason: str = "",
    ) -> None:
        delivery_id = str(delivery.get("deliveryId") or "").strip()
        claim_id = str(delivery.get("claimId") or "").strip()
        if not delivery_id or not claim_id:
            return
        url = f"{self._origin}/api/viventium/voice/glasshive/deliveries/{delivery_id}/status"
        headers = {
            "X-VIVENTIUM-CALL-SESSION": self._auth.call_session_id,
            "X-VIVENTIUM-CALL-SECRET": self._auth.call_secret,
        }
        if self._auth.job_id:
            headers["X-VIVENTIUM-JOB-ID"] = self._auth.job_id
        if self._auth.worker_id:
            headers["X-VIVENTIUM-WORKER-ID"] = self._auth.worker_id
        payload: dict[str, Any] = {"claimId": claim_id, "status": status}
        if error:
            payload["error"] = error[:1000]
        if reason:
            payload["reason"] = reason[:1000]
        try:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 409:
                    logger.warning(
                        "[voice-gateway] GlassHive delivery claim was lost before status=%s",
                        status,
                    )
                    return
                if resp.status != 200:
                    logger.warning(
                        "[voice-gateway] GlassHive delivery status update failed (status=%s)",
                        resp.status,
                    )
        except Exception as exc:
            logger.warning("[voice-gateway] GlassHive delivery status update failed: %s", exc)

    def _speak(self, text: str, seq: int, *, allow_stale_delivery: bool = False) -> bool:
        if not allow_stale_delivery and seq != self._seq:
            return False
        try:
            # No-response is an intentional "say nothing" signal.
            if is_no_response_only(text):
                return False
            cleaned = sanitize_voice_followup_text(text)
            if contains_no_response_tag(text):
                cleaned = strip_inline_nta(cleaned)
            if not cleaned:
                return False
            cleaned = cap_voice_followup_for_tts(cleaned)
            self._session.say(cleaned, allow_interruptions=True, add_to_chat_ctx=False)
            return True
        except Exception as exc:
            logger.warning("[voice-gateway] Failed to speak follow-up: %s", exc)
            return False
# === VIVENTIUM END ===


async def entrypoint(ctx: JobContext) -> None:
    env = ctx.proc.userdata.get("voice_env") or load_env()
    active_job_marker = _mark_active_voice_job(getattr(ctx.job, "id", "") or "")

    async def _clear_active_job_marker(*_args: Any) -> None:
        _clear_active_voice_job_marker(active_job_marker)

    ctx.add_shutdown_callback(_clear_active_job_marker)

    if not env.call_session_secret:
        raise RuntimeError("VIVENTIUM_CALL_SESSION_SECRET is required for the voice gateway worker")

    job_metadata = getattr(ctx.job, "metadata", "") or ""
    requested_voice_route = _parse_requested_voice_route(job_metadata)
    call_session_id = _parse_call_session_id(job_metadata)
    connected = False

    if not call_session_id:
        # === VIVENTIUM START ===
        # Feature: Delay room connect until needed for metadata fallback.
        # Purpose: Prevent duplicate-dispatch jobs from joining/publishing before lease claim.
        await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
        connected = True
        # === VIVENTIUM END ===

        # Fallback: read first remote participant metadata (Agents Playground sets participant_metadata too).
        try:
            for p in ctx.room.remote_participants.values():
                meta = getattr(p, "metadata", "") or ""
                if (
                    not requested_voice_route["stt"]["provider"]
                    and not requested_voice_route["tts"]["provider"]
                ):
                    requested_voice_route = _parse_requested_voice_route(meta)
                call_session_id = _parse_call_session_id(meta)
                if call_session_id:
                    break
        except Exception:
            call_session_id = None

    if not call_session_id:
        wait_s = _parse_float_env("VIVENTIUM_CALL_SESSION_WAIT_S", 3.0)
        if wait_s > 0:
            logger.warning(
                "callSessionId missing in job metadata; waiting up to %.1fs for participant metadata",
                wait_s,
            )
            call_session_id = await _await_participant_call_session_id(ctx, timeout_s=wait_s)

    if not call_session_id:
        raw_meta = (getattr(ctx.job, "metadata", "") or "").strip()
        snippet = raw_meta[:200] if raw_meta else "<empty>"
        logger.error("Missing callSessionId after wait; job metadata=%s", snippet)
        raise RuntimeError(
            "Missing callSessionId (expected dispatch job metadata JSON: {\"callSessionId\": \"...\"})"
        )

    # === VIVENTIUM START ===
    # Feature: Lease claim to prevent duplicate workers
    job_id = getattr(ctx.job, "id", "") or ""
    worker_id = getattr(ctx, "worker_id", "") or ""
    auth = LibreChatAuth(
        call_session_id=call_session_id,
        call_secret=env.call_session_secret,
        job_id=job_id,
        worker_id=worker_id,
    )
    if not job_id:
        logger.error("[voice-gateway] Missing LiveKit job id; refusing to start voice session")
        return
    claimed = await _claim_voice_session(env.librechat_origin, auth)
    if not claimed:
        logger.warning("[voice-gateway] Voice session already claimed; exiting worker")
        shutdown = getattr(ctx, "shutdown", None)
        if callable(shutdown):
            try:
                await shutdown()
            except Exception:
                logger.debug("[voice-gateway] Duplicate-session shutdown hook failed", exc_info=True)
        return
    # Connect only after successful claim when metadata already came from dispatch job.
    if not connected:
        await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
        connected = True
    # === VIVENTIUM END ===

    # === VIVENTIUM START ===
    _attach_room_diagnostics(
        ctx,
        call_session_id=call_session_id,
        active_job_marker=active_job_marker,
    )
    # === VIVENTIUM END ===

    capabilities = _build_voice_capability_catalog(env)
    env = _apply_requested_voice_route(env, requested_voice_route, capabilities)

    # Build LibreChat-backed LLM
    # === VIVENTIUM START ===
    # Feature: Voice-mode LLM hints (provider-aware prompt injection)
    llm_impl = LibreChatLLM(
        origin=env.librechat_origin,
        auth=auth,
        voice_mode=True,
        voice_provider=_normalize_voice_provider(env.tts_provider),
        voice_accepts_inline_controls=_tts_provider_accepts_inline_voice_controls(
            capabilities,
            env.tts_provider,
        ),
    )
    # === VIVENTIUM END ===

    # VAD (turn detection)
    desired_vad_kwargs = _silero_vad_kwargs_for_env(env)
    vad = ctx.proc.userdata.get("prewarmed_vad")
    if (
        vad is not None
        and ctx.proc.userdata.get("prewarmed_vad_kwargs_key")
        != _vad_kwargs_cache_key(desired_vad_kwargs)
    ):
        logger.info(
            "[voice-gateway] Discarding prewarmed VAD because the requested voice route needs different VAD timing."
        )
        vad = None
    if vad is None:
        vad = load_vad(env)

    # STT (provider selection)
    stt_impl, stt_provider = build_stt_selection(env, vad)

    def _build_tts(
        provider: str,
        *,
        elevenlabs_voice_id_override: Optional[str] = None,
        selection_role: str = "primary",
    ) -> tuple[Any, str]:
        provider = (provider or "").strip().lower()
        actual_voice_provider = _normalize_voice_provider(provider)

        def _log_selection(message: str, *args: Any) -> None:
            if selection_role == "primary":
                logger.info(message, *args)
                return
            logger.info("Prepared fallback provider: " + message, *args)

        def _build_openai_tts() -> Any:
            return openai.TTS(
                model=env.openai_tts_model,
                voice=env.openai_tts_voice,
                speed=env.openai_tts_speed,
                instructions=env.openai_tts_instructions,
            )

        # === VIVENTIUM START ===
        # Feature: Local Chatterbox Turbo (MLX) provider selection.
        #
        # Provider string:
        # - local_chatterbox_turbo_mlx_8bit
        #
        # Config:
        # - VIVENTIUM_MLX_AUDIO_MODEL_ID (default: mlx-community/chatterbox-turbo-8bit)
        # - VIVENTIUM_MLX_AUDIO_STREAM (default: true)
        # - VIVENTIUM_MLX_AUDIO_STREAMING_INTERVAL_S (default: 1.0)
        # - VIVENTIUM_MLX_AUDIO_SAMPLE_RATE (default: 24000)
        # - VIVENTIUM_MLX_AUDIO_PREBUFFER_MS (default: 500)
        if provider in {"local_chatterbox_turbo_mlx_8bit"} or "chatterbox" in provider:
            if sys.platform != "darwin":
                logger.warning(
                    "Local Chatterbox (MLX) requested on non-macOS platform (%s). Falling back to OpenAI TTS.",
                    sys.platform,
                )
                actual_voice_provider = "openai"
                return (_build_openai_tts(), actual_voice_provider)

            config, ref_audio_warning = _build_local_chatterbox_config(env.mlx_audio_model_id)
            if ref_audio_warning:
                logger.warning("%s; using default voice.", ref_audio_warning)

            try:
                import importlib.util
                if importlib.util.find_spec("mlx_audio") is None:
                    raise ImportError("mlx_audio is not installed")

                _log_selection(
                    "Using local Chatterbox Turbo (MLX-Audio) TTS (model=%s, stream=%s, interval=%.2fs, sample_rate=%s, prebuffer_ms=%s, temp=%.2f, rep_pen=%.2f)",
                    config.model_id,
                    config.stream,
                    config.streaming_interval_s,
                    config.sample_rate,
                    int(config.prebuffer_ms),
                    config.temperature,
                    config.repetition_penalty,
                )
                cached_tts = ctx.proc.userdata.get("prewarmed_local_chatterbox_tts")
                if isinstance(cached_tts, MlxChatterboxTTS) and getattr(cached_tts, "_config", None) == config:
                    return (cached_tts, actual_voice_provider)
                return (
                    MlxChatterboxTTS(config=config),
                    actual_voice_provider,
                )
            except ImportError as exc:
                logger.warning(
                    "Local Chatterbox (MLX) requested but mlx-audio is not installed (%s). Falling back to OpenAI TTS.",
                    exc,
                )
                actual_voice_provider = "openai"
                return (_build_openai_tts(), actual_voice_provider)
            except Exception as exc:
                logger.error(
                    "Local Chatterbox (MLX) initialization failed (%s). Falling back to OpenAI TTS.",
                    exc,
                    exc_info=True,
                )
                actual_voice_provider = "openai"
                return (_build_openai_tts(), actual_voice_provider)
        # === VIVENTIUM END ===

        # TTS (Cartesia, xAI standalone TTS, legacy xAI Grok Voice Agent, ElevenLabs, or OpenAI)
        if provider in {"xai", "x_ai", "grok", "xai_grok_voice"}:
            xai_api_key = (env.xai_tts_api_key or os.getenv("XAI_API_KEY", "") or "").strip()
            if not _is_real_api_key(xai_api_key):
                logger.warning(
                    "xAI TTS requested but a real VIVENTIUM_XAI_TTS_API_KEY or XAI_API_KEY is not set. Falling back to OpenAI TTS."
                )
                actual_voice_provider = "openai"
                return (_build_openai_tts(), actual_voice_provider)

            if env.xai_tts_api == "voice_agent":
                _log_selection(
                    "Using legacy xAI Grok Voice Agent TTS (voice=%s, sample_rate=%s, wss=%s)",
                    env.xai_voice,
                    env.xai_sample_rate,
                    env.xai_wss_url,
                )
                return (
                    XaiGrokVoiceTTS(
                        config=XaiGrokVoiceConfig(
                            api_key=xai_api_key,
                            voice=env.xai_voice,
                            wss_url=env.xai_wss_url,
                            sample_rate=env.xai_sample_rate,
                            num_channels=1,
                            instructions=env.xai_instructions,
                        )
                    ),
                    actual_voice_provider,
                )

            if env.xai_tts_api not in {"", "tts"}:
                logger.warning(
                    "Unsupported VIVENTIUM_XAI_TTS_API=%s; falling back to OpenAI TTS.",
                    env.xai_tts_api,
                )
                actual_voice_provider = "openai"
                return (_build_openai_tts(), actual_voice_provider)

            if not HAS_XAI_TTS or xai_plugin is None:
                logger.warning(
                    "xAI TTS requested but livekit-plugins-xai is not installed. Falling back to OpenAI TTS."
                )
                actual_voice_provider = "openai"
                return (_build_openai_tts(), actual_voice_provider)

            _log_selection(
                "Using xAI standalone TTS (voice=%s, language=%s, sample_rate=%s, ws=%s, optimize_streaming_latency=%s)",
                env.xai_voice,
                env.xai_language,
                env.xai_sample_rate,
                env.xai_tts_ws_url,
                env.xai_tts_optimize_streaming_latency,
            )
            _configure_xai_standalone_tts_plugin(
                ws_url=env.xai_tts_ws_url,
                sample_rate=env.xai_sample_rate,
            )
            tts_instance = xai_plugin.TTS(
                api_key=xai_api_key,
                voice=env.xai_voice,
                language=env.xai_language,
                # === VIVENTIUM START ===
                # Preserve inter-word spacing in the xAI websocket text deltas. Without this the
                # plugin's default WordTokenizer (retain_format=False) strips spaces and the spoken
                # audio glues words together while the chat transcript stays correct. See
                # _build_xai_tts_word_tokenizer for the full root-cause note.
                tokenizer=_build_xai_tts_word_tokenizer(),
                # === VIVENTIUM END ===
            )
            _apply_xai_tts_streaming_latency_options(
                tts_instance,
                ws_url=env.xai_tts_ws_url,
                sample_rate=env.xai_sample_rate,
                optimize_streaming_latency=env.xai_tts_optimize_streaming_latency,
            )
            return (tts_instance, actual_voice_provider)

        if provider == "cartesia":
            cartesia_api_key = (os.getenv("CARTESIA_API_KEY", "") or "").strip()
            if not cartesia_api_key:
                logger.warning(
                    "Cartesia TTS requested but CARTESIA_API_KEY not set. Falling back to OpenAI TTS."
                )
                actual_voice_provider = "openai"
                return (_build_openai_tts(), actual_voice_provider)

            _log_selection(
                "Using Cartesia TTS (model=%s, voice=%s, sample_rate=%s, speed=%s, volume=%s, emotion=%s, language=%s, ws=%s, buffer_ms=%s)",
                env.cartesia_model_id,
                env.cartesia_voice_id,
                env.cartesia_sample_rate,
                env.cartesia_speed,
                env.cartesia_volume,
                env.cartesia_emotion,
                env.cartesia_language or "auto",
                env.cartesia_ws_url,
                env.cartesia_max_buffer_delay_ms,
            )
            return (
                CartesiaTTS(
                    config=CartesiaConfig(
                        api_key=cartesia_api_key,
                        api_url=env.cartesia_api_url,
                        ws_url=env.cartesia_ws_url,
                        api_version=env.cartesia_api_version,
                        model_id=env.cartesia_model_id,
                        voice_id=env.cartesia_voice_id,
                        sample_rate=env.cartesia_sample_rate,
                        num_channels=1,
                        speed=env.cartesia_speed,
                        volume=env.cartesia_volume,
                        emotion=env.cartesia_emotion,
                        max_buffer_delay_ms=env.cartesia_max_buffer_delay_ms,
                        segment_silence_ms=env.cartesia_segment_silence_ms,
                        language=env.cartesia_language,
                    )
                ),
                actual_voice_provider,
            )

        # Check for ElevenLabs API key (LiveKit plugin uses ELEVEN_API_KEY)
        eleven_api_key = os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY")

        if provider == "elevenlabs" and HAS_ELEVENLABS:
            if not eleven_api_key:
                logger.warning(
                    "ElevenLabs TTS requested but ELEVEN_API_KEY/ELEVENLABS_API_KEY not set. "
                    "Falling back to OpenAI TTS."
                )
                actual_voice_provider = "openai"
                return _build_openai_tts(), actual_voice_provider

            voice_id = (elevenlabs_voice_id_override or env.elevenlabs_voice_id).strip() or env.elevenlabs_voice_id

            # ElevenLabs accepts approximately 0.7x to 1.3x playback speed for flagship voices.
            speed = float(env.elevenlabs_voice_speed)
            clamped_speed = max(0.7, min(1.3, speed))
            if clamped_speed != speed:
                logger.warning(
                    "Clamped ElevenLabs speed from %s to %s (allowed range: 0.7-1.3)",
                    speed,
                    clamped_speed,
                )
            speed = clamped_speed

            # Use ElevenLabs TTS (matching old viventium_v1 voice)
            _log_selection(
                "Using ElevenLabs TTS with voice_id=%s (stability=%s, similarity_boost=%s, style=%s, speed=%s)",
                voice_id,
                env.elevenlabs_voice_stability,
                env.elevenlabs_voice_similarity_boost,
                env.elevenlabs_voice_style,
                speed,
            )
            return (
                elevenlabs.TTS(
                    voice_id=voice_id,
                    voice_settings=elevenlabs.VoiceSettings(
                        stability=env.elevenlabs_voice_stability,
                        similarity_boost=env.elevenlabs_voice_similarity_boost,
                        style=env.elevenlabs_voice_style,
                        speed=speed,
                        use_speaker_boost=True,
                    ),
                    api_key=eleven_api_key,
                    # Keep voice-gateway sample rate consistent with Cartesia defaults.
                    encoding="mp3_44100_128",
                ),
                actual_voice_provider,
            )

        # Fallback to OpenAI TTS
        if provider == "elevenlabs" and not HAS_ELEVENLABS:
            logger.warning(
                "ElevenLabs TTS requested but plugin not available. "
                "Falling back to OpenAI TTS. Install with: pip install livekit-plugins-elevenlabs"
            )
        elif provider and provider not in {"openai", "elevenlabs"}:
            logger.warning("Unknown TTS provider '%s'; falling back to OpenAI TTS.", provider)
        else:
            _log_selection(
                "Using OpenAI TTS with model=%s, voice=%s, speed=%.2f",
                env.openai_tts_model,
                env.openai_tts_voice,
                env.openai_tts_speed,
            )
        actual_voice_provider = "openai"
        return (
            _build_openai_tts(),
            actual_voice_provider,
        )

    primary_tts_impl, primary_voice_provider = _build_tts(env.tts_provider, selection_role="primary")

    # === VIVENTIUM START ===
    # Feature: Prewarm local TTS models to eliminate cold-start latency on first voice call.
    # Purpose: MLX Chatterbox must load ~2-4 GB of weights from disk on first use. Without
    # prewarming, the first call has 5-15s extra TTFA. The launcher prefetch warms the HF
    # disk cache but the worker process still needs an in-process load.
    local_tts_providers = {"local_chatterbox_turbo_mlx_8bit"}
    prewarmed_local_tts = ctx.proc.userdata.get("prewarmed_local_chatterbox_tts")
    if (
        primary_voice_provider in local_tts_providers
        and primary_tts_impl is not prewarmed_local_tts
        and env.voice_prewarm_local_tts
        and hasattr(primary_tts_impl, "prewarm")
    ):
        logger.info("[voice-gateway] Prewarming TTS model (%s)...", primary_voice_provider)
        primary_tts_impl.prewarm()
    # === VIVENTIUM END ===

    attempts: list[ProviderAttempt] = [
        _build_tts_provider_attempt(
            capabilities=capabilities,
            provider=primary_voice_provider,
            tts_impl=primary_tts_impl,
        )
    ]
    configured_fallback_tts_impl: Optional[Any] = None
    configured_fallback_voice_provider: Optional[str] = None

    def _maybe_add_elevenlabs_voice_fallback(*, voice_provider: str) -> None:
        # If a chosen ElevenLabs voice id is blocked (IVC voice on lower tiers), fall back to a
        # premade voice id for reliability. We keep the provider label as "elevenlabs" so downstream
        # prompt injection stays stable; logs include the actual voice_id via `fallback_tts.py`.
        if voice_provider != "elevenlabs":
            return

        fallback_voice_id = (env.elevenlabs_voice_id_fallback or "").strip()
        primary_voice_id = (env.elevenlabs_voice_id or "").strip()
        if not fallback_voice_id or not primary_voice_id:
            return
        if fallback_voice_id == primary_voice_id:
            return

        fallback_voice_tts, fallback_voice_provider = _build_tts(
            "elevenlabs",
            elevenlabs_voice_id_override=fallback_voice_id,
            selection_role="fallback",
        )
        if fallback_voice_provider != "elevenlabs":
            return
        attempts.append(
            _build_tts_provider_attempt(
                capabilities=capabilities,
                provider=voice_provider,
                tts_impl=fallback_voice_tts,
            )
        )

    _maybe_add_elevenlabs_voice_fallback(voice_provider=primary_voice_provider)

    if env.tts_provider_fallback and env.tts_provider_fallback != env.tts_provider:
        fallback_tts_impl, fallback_voice_provider = _build_tts(
            env.tts_provider_fallback,
            selection_role="fallback",
        )
        if fallback_voice_provider != primary_voice_provider:
            attempts.append(
                _build_tts_provider_attempt(
                    capabilities=capabilities,
                    provider=fallback_voice_provider,
                    tts_impl=fallback_tts_impl,
                )
            )
            _maybe_add_elevenlabs_voice_fallback(voice_provider=fallback_voice_provider)
            configured_fallback_tts_impl = fallback_tts_impl
            configured_fallback_voice_provider = fallback_voice_provider

    current_tts_provider = primary_voice_provider
    current_tts_impl = primary_tts_impl

    async def _publish_voice_route_metadata(
        selected_tts_provider: str,
        selected_tts_impl: Any,
    ) -> None:
        try:
            route_payload = _build_voice_route_metadata(
                env=env,
                capabilities=capabilities,
                stt_provider=stt_provider,
                tts_provider=selected_tts_provider,
                effective_tts_impl=selected_tts_impl,
                fallback_tts_provider=configured_fallback_voice_provider,
                fallback_tts_impl=configured_fallback_tts_impl,
            )
            existing_metadata = _parse_metadata_json(
                getattr(ctx.room.local_participant, "metadata", "") or ""
            )
            existing_metadata["voiceRoute"] = route_payload
            await ctx.room.local_participant.set_metadata(
                json.dumps(existing_metadata, ensure_ascii=True)
            )
        except Exception as exc:
            logger.warning("[voice-gateway] Failed to publish voice route metadata: %s", exc)

    def _handle_provider_selected(provider: str, tts_impl: Any) -> None:
        nonlocal current_tts_provider, current_tts_impl
        current_tts_provider = provider
        current_tts_impl = tts_impl
        llm_impl.set_voice_provider(
            provider,
            accepts_inline_voice_controls=_tts_provider_accepts_inline_voice_controls(
                capabilities,
                provider,
            ),
        )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(_publish_voice_route_metadata(provider, tts_impl))

    attached_tts_metric_sources: set[int] = set()

    def _attach_tts_latency_logger(provider: str, tts_impl: Any) -> None:
        source_id = id(tts_impl)
        if source_id in attached_tts_metric_sources:
            return
        on_event = getattr(tts_impl, "on", None)
        if not callable(on_event):
            return

        def _on_tts_metrics(metrics: Any) -> None:
            if getattr(metrics, "type", "") != "tts_metrics":
                return
            logger.info(
                "[VoiceLatency] tts_provider_metrics callSessionId=%s provider=%s label=%s request_id=%s ttfb_ms=%s duration_ms=%s audio_duration_ms=%s streamed=%s cancelled=%s characters=%s",
                call_session_id,
                provider,
                getattr(metrics, "label", ""),
                getattr(metrics, "request_id", ""),
                _metric_ms(metrics, "ttfb"),
                _metric_ms(metrics, "duration"),
                _metric_ms(metrics, "audio_duration"),
                bool(getattr(metrics, "streamed", False)),
                bool(getattr(metrics, "cancelled", False)),
                getattr(metrics, "characters_count", 0),
            )

        try:
            on_event("metrics_collected", _on_tts_metrics)
            attached_tts_metric_sources.add(source_id)
        except Exception:
            logger.debug(
                "[voice-gateway] Unable to attach TTS metrics logger for provider=%s",
                provider,
                exc_info=True,
            )

    for attempt in attempts:
        _attach_tts_latency_logger(attempt.label, attempt.tts)

    if len(attempts) > 1:
        tts_impl = FallbackTTS(
            attempts=attempts,
            on_provider_selected=_handle_provider_selected,
        )
    else:
        tts_impl = primary_tts_impl

    # Build session
    # === VIVENTIUM START ===
    # Feature: Sync final provider back into LibreChat voiceMode payloads.
    llm_impl.set_voice_provider(
        primary_voice_provider,
        accepts_inline_voice_controls=_tts_provider_accepts_inline_voice_controls(
            capabilities,
            primary_voice_provider,
        ),
    )
    # === VIVENTIUM END ===

    turn_detection, turn_end_reason = load_turn_detection(env, vad is not None)

    turn_handling: TurnHandlingOptions = {
        "turn_detection": turn_detection,
        "endpointing": {
            "min_delay": env.voice_min_endpointing_delay_s,
            "max_delay": env.voice_max_endpointing_delay_s,
        },
        "interruption": {
            "enabled": True,
            "min_duration": env.voice_min_interruption_duration_s,
            "min_words": env.voice_min_interruption_words,
            "false_interruption_timeout": env.voice_false_interruption_timeout_s,
            "resume_false_interruption": env.voice_resume_false_interruption,
        },
        "preemptive_generation": {
            "enabled": False,
        },
    }

    session = AgentSession(
        vad=vad,
        stt=stt_impl,
        llm=llm_impl,
        tts=tts_impl,
        turn_handling=turn_handling,
        min_consecutive_speech_delay=env.voice_min_consecutive_speech_delay_s,
        aec_warmup_duration=env.voice_aec_warmup_duration_s,
    )
    logger.info(
        "[voice-gateway] AgentSession callSessionId=%s turn_detection=%s turn_end_reason=%s min_interrupt=%ss min_interrupt_words=%s min_endpoint=%ss max_endpoint=%ss false_interrupt_timeout=%s resume_false_interrupt=%s min_consecutive_speech_delay=%ss aec_warmup_duration=%s",
        call_session_id,
        _turn_detection_label(turn_detection),
        turn_end_reason,
        env.voice_min_interruption_duration_s,
        env.voice_min_interruption_words,
        env.voice_min_endpointing_delay_s,
        env.voice_max_endpointing_delay_s,
        env.voice_false_interruption_timeout_s,
        env.voice_resume_false_interruption,
        env.voice_min_consecutive_speech_delay_s,
        env.voice_aec_warmup_duration_s,
    )

    @session.on("agent_state_changed")
    def _on_agent_state_changed(event: Any) -> None:
        logger.info(
            "[voice-gateway] agent_state_changed callSessionId=%s old=%s new=%s",
            call_session_id,
            getattr(event, "old_state", ""),
            getattr(event, "new_state", ""),
        )

    @session.on("user_state_changed")
    def _on_user_state_changed(event: Any) -> None:
        logger.info(
            "[voice-gateway] user_state_changed callSessionId=%s old=%s new=%s",
            call_session_id,
            getattr(event, "old_state", ""),
            getattr(event, "new_state", ""),
        )

    @session.on("overlapping_speech")
    def _on_overlapping_speech(event: Any) -> None:
        logger.info(
            "[voice-gateway] overlapping_speech callSessionId=%s is_interruption=%s probability=%.3f detection_delay=%.3fs total_duration=%.3fs",
            call_session_id,
            bool(getattr(event, "is_interruption", False)),
            float(getattr(event, "probability", 0.0) or 0.0),
            float(getattr(event, "detection_delay", 0.0) or 0.0),
            float(getattr(event, "total_duration", 0.0) or 0.0),
        )

    @session.on("conversation_item_added")
    def _on_conversation_item_added(event: Any) -> None:
        item = getattr(event, "item", None)
        role = getattr(item, "role", "")
        metrics = getattr(item, "metrics", None) or {}
        created_at = float(getattr(event, "created_at", 0.0) or 0.0)
        event_lag_ms = (
            max((time.time() - created_at) * 1000.0, 0.0)
            if created_at > 0
            else 0.0
        )
        if role == "user":
            eou_delay = _metric_seconds(metrics, "end_of_turn_delay")
            transcription_delay = _metric_seconds(metrics, "transcription_delay")
            on_turn_completed_delay = _metric_seconds(
                metrics,
                "on_user_turn_completed_delay",
            )
            logger.info(
                "[voice-gateway] user_turn_completed source=conversation_item_metrics callSessionId=%s reason=%s detection=%s eou_delay=%.6fs transcription_delay=%.6fs",
                call_session_id,
                turn_end_reason,
                _turn_detection_label(turn_detection),
                eou_delay,
                transcription_delay,
            )
            logger.info(
                "[VoiceLatencyDetail] conversation_item_user_metrics callSessionId=%s reason=%s detection=%s eou_delay_s=%.6f transcription_delay_s=%.6f on_user_turn_completed_delay_s=%.6f event_lag_ms=%.3f",
                call_session_id,
                turn_end_reason,
                _turn_detection_label(turn_detection),
                eou_delay,
                transcription_delay,
                on_turn_completed_delay,
                event_lag_ms,
            )
            return
        if role == "assistant":
            logger.info(
                "[VoiceLatency] assistant_turn_metrics callSessionId=%s provider=%s llm_node_ttft_ms=%s tts_node_ttfb_ms=%s e2e_latency_ms=%s event_lag_ms=%.3f",
                call_session_id,
                current_tts_provider,
                _metric_ms(metrics, "llm_node_ttft"),
                _metric_ms(metrics, "tts_node_ttfb"),
                _metric_ms(metrics, "e2e_latency"),
                event_lag_ms,
            )

    @session.on("agent_false_interruption")
    def _on_agent_false_interruption(event: Any) -> None:
        logger.info(
            "[voice-gateway] agent_false_interruption callSessionId=%s resumed=%s timeout=%s",
            call_session_id,
            bool(getattr(event, "resumed", False)),
            env.voice_false_interruption_timeout_s,
        )

    # === VIVENTIUM START ===
    # Feature: Async insight follow-up scheduling (non-blocking).
    followup_scheduler = CortexFollowupScheduler(
        origin=env.librechat_origin,
        auth=auth,
        session=session,
        timeout_s=env.voice_followup_timeout_s,
        interval_s=env.voice_followup_interval_s,
        grace_s=env.voice_followup_grace_s,
        glasshive_timeout_s=env.voice_glasshive_timeout_s,
    )
    llm_impl.set_followup_handler(followup_scheduler.schedule)
    # === VIVENTIUM END ===

    agent = ViventiumVoiceAgent(
        instructions=(
            "You are the Viventium Voice Gateway. "
            "You must speak the LibreChat agent's responses naturally and concisely."
        ),
        llm=llm_impl,
        stt=stt_impl,
        tts=tts_impl,
    )

    # === VIVENTIUM START ===
    # Feature: Transcript display correctness and TTS-failure resilience.
    #
    # Viventium defaults to async transcript output so the modern playground shows
    # each assistant answer as soon as the LLM completes it instead of pacing text
    # word-by-word with TTS playout. Operators can opt into audio-paced captions
    # with VIVENTIUM_VOICE_SYNC_TRANSCRIPTION=1 for provider-specific QA.
    sync_transcription = _voice_sync_transcription_enabled()
    logger.info(
        "[voice-gateway] RoomOptions callSessionId=%s text_output.sync_transcription=%s",
        call_session_id,
        sync_transcription,
    )
    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=_build_room_options(sync_transcription=sync_transcription),
    )
    await _publish_voice_route_metadata(current_tts_provider, current_tts_impl)
    # === VIVENTIUM END ===


def run() -> None:
    start_health_server()
    os.environ["VIVENTIUM_VOICE_WORKER_RUN_ID"] = f"{os.getpid()}-{int(time.time() * 1000)}"
    env = load_env()
    stt_provider = getattr(env, "stt_provider", "")
    if (
        getattr(env, "voice_turn_detection", "") == "turn_detector"
        or _normalize_turn_detection(getattr(env, "voice_requested_turn_detection", ""))
        == "turn_detector"
        or (bool(stt_provider) and _is_local_whisper_stt(stt_provider))
    ):
        turn_detector_ready, turn_detector_status = _semantic_turn_detector_status(stt_provider)
        logger.info(
            "[voice-gateway] turn_detector_readiness stt_provider=%s requested=%s effective=%s ready=%s status=%s",
            stt_provider,
            getattr(env, "voice_requested_turn_detection", "") or "default",
            getattr(env, "voice_turn_detection", ""),
            turn_detector_ready,
            turn_detector_status,
        )
    initialize_process_timeout_s = max(
        10.0,
        float(getattr(env, "voice_initialize_process_timeout_s", 45.0)),
    )
    idle_processes = max(0, int(getattr(env, "voice_idle_processes", 0)))
    load_threshold = float(getattr(env, "voice_worker_load_threshold", 0.7))
    worker_opts = WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm_process,
        agent_name=env.livekit_agent_name,
        worker_type=WorkerType.PUBLISHER,
        initialize_process_timeout=initialize_process_timeout_s,
        num_idle_processes=idle_processes,
        load_threshold=load_threshold,
        job_memory_warn_mb=float(getattr(env, "voice_job_memory_warn_mb", 500.0)),
        job_memory_limit_mb=float(getattr(env, "voice_job_memory_limit_mb", 0.0)),
    )
    cli.run_app(worker_opts)


if __name__ == "__main__":
    run()
