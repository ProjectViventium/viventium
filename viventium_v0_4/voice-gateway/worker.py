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
from typing import Any, NoReturn, Optional
from urllib.parse import quote, urlencode

import aiohttp
from livekit import rtc

from livekit.agents import (
    APIConnectionError,
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    JobProcess,
    TurnHandlingOptions,
    WorkerOptions,
    StopResponse,
    cli,
    tokenize,
)
from livekit.agents.worker import WorkerType
from livekit.agents.stt import SpeechEventType
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
# === VIVENTIUM START ===
# Feature: Shared Silero VAD config parity across voice STT paths.
from silero_vad_config import get_silero_vad_kwargs
# === VIVENTIUM END ===
# === VIVENTIUM START ===
# Feature: Local Chatterbox Turbo (MLX) TTS provider (macOS-only).
from mlx_chatterbox_tts import MlxChatterboxConfig, MlxChatterboxTTS
# === VIVENTIUM END ===
from fallback_tts import FallbackTTS, ProviderAttempt
from speaker_segments import (
    CallScopedSegmentSequencer,
    SPEAKER_CONTEXT_EXTRA_KEY,
    SpeakerSegmentTracker,
    attach_speaker_context_to_message,
    shared_microphone_state_applies_to_track,
)
from multi_track_ingress import MultiTrackIngressCoordinator
from voice_progress import (
    AsyncVoiceProgressController,
    VoiceProgressStateMachine,
    parse_authoritative_call_state_packet,
    parse_voice_call_state_v1,
    run_authoritative_mode_reconciliation,
    sync_authoritative_call_mode_once,
)

logger = logging.getLogger("voice-gateway")

_TTS_PROVIDER_CAPABILITIES_PATH = (
    Path(__file__).resolve().parent.parent / "shared" / "voice" / "tts_provider_capabilities.json"
)
_XAI_TTS_CAPABILITIES_PATH = Path(__file__).resolve().parent.parent / "shared" / "voice" / "xai_tts_capabilities.json"


def _load_tts_provider_capabilities() -> dict[str, Any]:
    try:
        with _TTS_PROVIDER_CAPABILITIES_PATH.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        providers = value.get("providers") if isinstance(value, dict) else None
        if isinstance(providers, dict) and providers:
            return value
        raise ValueError("providers must be a non-empty object")
    except Exception as error:
        raise RuntimeError(
            "Required TTS provider capability contract is missing or invalid at "
            f"{_TTS_PROVIDER_CAPABILITIES_PATH}"
        ) from error


TTS_PROVIDER_CAPABILITIES = _load_tts_provider_capabilities()


def _tts_provider_contract(provider: str) -> dict[str, Any]:
    providers = TTS_PROVIDER_CAPABILITIES.get("providers")
    if not isinstance(providers, dict):
        return {}
    value = providers.get(provider)
    return value if isinstance(value, dict) else {}


def _tts_provider_accepts_inline_controls_from_contract(provider: str) -> bool:
    inline = _tts_provider_contract(provider).get("inline_controls")
    return bool(inline.get("supported")) if isinstance(inline, dict) else False


def _tts_provider_default_model(provider: str) -> str:
    return str(_tts_provider_contract(provider).get("default_model") or "").strip()


DEFAULT_OPENAI_TTS_INSTRUCTIONS = str(
    _tts_provider_contract("openai").get("default_renderer_instruction") or ""
).strip()


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

    # xAI standalone TTS settings.
    xai_tts_api_key: str
    xai_voice: str
    xai_language: str
    xai_tts_ws_url: str
    xai_tts_optimize_streaming_latency: int
    xai_sample_rate: int

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


class VoiceRouteError(RuntimeError):
    """Classified failure for an authoritative saved voice route.

    A selected route is a privacy and product-truth boundary.  Callers may surface the
    classification, but must never recover by silently constructing a different provider.
    """

    def __init__(self, code: str, *, modality: str, provider: str, reason: str) -> None:
        self.code = code
        self.modality = modality
        self.provider = (provider or "").strip().lower()
        self.egress_class = "local" if _is_local_provider(self.provider) else "cloud"
        super().__init__(
            f"{code}: authoritative {modality} route {self.provider or '<missing>'} {reason}"
        )


def _raise_route_error(
    code: str, *, modality: str, provider: str, reason: str
) -> NoReturn:
    raise VoiceRouteError(
        code,
        modality=modality,
        provider=provider,
        reason=reason,
    )


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
    xai_runtime_supported = HAS_XAI_TTS
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
            "acceptsInlineVoiceControls": _tts_provider_accepts_inline_controls_from_contract(
                "openai"
            ),
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
            "acceptsInlineVoiceControls": _tts_provider_accepts_inline_controls_from_contract(
                "elevenlabs"
            ),
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
            "acceptsInlineVoiceControls": _tts_provider_accepts_inline_controls_from_contract(
                "cartesia"
            ),
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
            "acceptsInlineVoiceControls": _tts_provider_accepts_inline_controls_from_contract(
                "xai"
            ),
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
            "acceptsInlineVoiceControls": _tts_provider_accepts_inline_controls_from_contract(
                "local_chatterbox_turbo_mlx_8bit"
            ),
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
    if not stt_selection["provider"]:
        _raise_route_error(
            "no_route", modality="stt", provider="", reason="is missing"
        )
    requested_stt_provider = _normalize_stt_provider(stt_selection["provider"])
    stt_capability = _find_voice_capability(
        capabilities, modality="stt", provider=requested_stt_provider
    )
    if stt_capability is None:
        _raise_route_error(
            "no_route",
            modality="stt",
            provider=requested_stt_provider,
            reason="is not supported",
        )
    if not stt_capability.get("available"):
        _raise_route_error(
            "provider_failure",
            modality="stt",
            provider=requested_stt_provider,
            reason="is unavailable",
        )
    requested_stt_variant = stt_selection["variant"]
    stt_variant_ids = {
        item.get("id")
        for item in stt_capability.get("variants", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if requested_stt_variant and stt_variant_ids and requested_stt_variant not in stt_variant_ids:
        _raise_route_error(
            "no_route",
            modality="stt",
            provider=requested_stt_provider,
            reason="has an unsupported saved variant",
        )
    if requested_stt_provider == "openai":
        runtime_env = replace(
            runtime_env,
            stt_provider="openai",
            openai_stt_model=requested_stt_variant or runtime_env.openai_stt_model,
        )
    elif requested_stt_provider == "assemblyai":
        runtime_env = replace(
            runtime_env,
            stt_provider="assemblyai",
            assemblyai_stt_model=_normalize_assemblyai_stt_model(
                requested_stt_variant or runtime_env.assemblyai_stt_model
            ),
        )
    elif requested_stt_provider == "pywhispercpp":
        runtime_env = replace(
            runtime_env,
            stt_provider="pywhispercpp",
            stt_model=requested_stt_variant or runtime_env.stt_model,
        )
    else:
        _raise_route_error(
            "no_route",
            modality="stt",
            provider=requested_stt_provider,
            reason="is not implemented",
        )

    tts_selection = normalized_route["tts"]
    if not tts_selection["provider"]:
        _raise_route_error(
            "no_route", modality="tts", provider="", reason="is missing"
        )
    requested_tts_provider = _normalize_voice_provider(tts_selection["provider"])
    tts_capability = _find_voice_capability(
        capabilities, modality="tts", provider=requested_tts_provider
    )
    if tts_capability is None:
        _raise_route_error(
            "no_route",
            modality="tts",
            provider=requested_tts_provider,
            reason="is not supported",
        )
    if not tts_capability.get("available"):
        _raise_route_error(
            "provider_failure",
            modality="tts",
            provider=requested_tts_provider,
            reason="is unavailable",
        )
    requested_tts_variant = tts_selection["variant"]
    tts_variant_ids = {
        item.get("id")
        for item in tts_capability.get("variants", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if requested_tts_variant and tts_variant_ids and requested_tts_variant not in tts_variant_ids:
        _raise_route_error(
            "no_route",
            modality="tts",
            provider=requested_tts_provider,
            reason="has an unsupported saved variant",
        )
    if requested_tts_provider == "openai":
        runtime_env = replace(
            runtime_env,
            tts_provider="openai",
            openai_tts_model=requested_tts_variant or runtime_env.openai_tts_model,
        )
    elif requested_tts_provider == "elevenlabs":
        runtime_env = replace(
            runtime_env,
            tts_provider="elevenlabs",
            elevenlabs_voice_id=requested_tts_variant or runtime_env.elevenlabs_voice_id,
        )
    elif requested_tts_provider == "cartesia":
        runtime_env = replace(
            runtime_env,
            tts_provider="cartesia",
            cartesia_voice_id=requested_tts_variant or runtime_env.cartesia_voice_id,
            cartesia_model_id=DEFAULT_CARTESIA_MODEL_ID,
        )
    elif requested_tts_provider == "xai":
        runtime_env = replace(
            runtime_env,
            tts_provider="xai",
            xai_voice=requested_tts_variant or runtime_env.xai_voice,
        )
    elif requested_tts_provider == "local_chatterbox_turbo_mlx_8bit":
        runtime_env = replace(
            runtime_env,
            tts_provider="local_chatterbox_turbo_mlx_8bit",
            mlx_audio_model_id=requested_tts_variant or runtime_env.mlx_audio_model_id,
        )
    else:
        _raise_route_error(
            "no_route",
            modality="tts",
            provider=requested_tts_provider,
            reason="is not implemented",
        )

    # A fallback is opt-in configuration, never inferred from the primary.  Local-only remains
    # absolute: crossing the local/cloud egress boundary is forbidden even when a key exists.
    fallback_provider = _normalize_voice_provider(runtime_env.tts_provider_fallback)
    fallback_capability = (
        _find_voice_capability(capabilities, modality="tts", provider=fallback_provider)
        if runtime_env.tts_provider_fallback
        else None
    )
    fallback_allowed = bool(
        runtime_env.tts_provider_fallback
        and fallback_provider != requested_tts_provider
        and fallback_capability
        and fallback_capability.get("available")
        and _is_local_provider(fallback_provider)
        == _is_local_provider(requested_tts_provider)
    )
    runtime_env = replace(
        runtime_env,
        tts_provider_fallback=fallback_provider if fallback_allowed else "",
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
    configured_xai_tts_api = (
        os.getenv("VIVENTIUM_XAI_TTS_API", "tts").strip().lower() or "tts"
    )
    if configured_xai_tts_api != "tts":
        if configured_xai_tts_api == "voice_agent":
            raise ValueError(
                "The xAI Grok Voice Agent route is retired. "
                "Set VIVENTIUM_XAI_TTS_API=tts to use standalone xAI Text-to-Speech (/v1/tts)."
            )
        raise ValueError(
            f"Unsupported VIVENTIUM_XAI_TTS_API={configured_xai_tts_api!r}. "
            "Set VIVENTIUM_XAI_TTS_API=tts; standalone xAI Text-to-Speech is the only supported route."
        )

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
    # Fallback is explicit configuration only.  In particular, a local Chatterbox route must
    # never acquire a cloud fallback merely because a cloud plugin/key happens to be installed.
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
    # A local route cannot fall back to cloud TTS, so its registered worker must have both local
    # models ready before accepting a call. Process prewarm waits for active jobs before loading;
    # this preserves live-call latency while removing the first-call 5–15 second model load.
    default_prewarm_local_tts = (
        _normalize_voice_provider(tts_provider) == "local_chatterbox_turbo_mlx_8bit"
    )
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
        xai_sample_rate=int(float(os.getenv("VIVENTIUM_XAI_SAMPLE_RATE", str(DEFAULT_XAI_TTS_SAMPLE_RATE)))),
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
        openai_tts_model=os.getenv(
            "VIVENTIUM_OPENAI_TTS_MODEL",
            _tts_provider_default_model("openai"),
        ).strip()
        or _tts_provider_default_model("openai"),
        openai_tts_voice=os.getenv("VIVENTIUM_OPENAI_TTS_VOICE", "coral").strip() or "coral",
        openai_tts_speed=_parse_float_env("VIVENTIUM_OPENAI_TTS_SPEED", 1.12),
        openai_tts_instructions=(
            os.getenv(
                "VIVENTIUM_OPENAI_TTS_INSTRUCTIONS",
                DEFAULT_OPENAI_TTS_INSTRUCTIONS,
            ).strip()
            or DEFAULT_OPENAI_TTS_INSTRUCTIONS
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


def _parse_dispatch_claim_id(metadata: str) -> Optional[str]:
    obj = _parse_metadata_json(metadata)
    claim_id = obj.get("dispatchClaimId") or obj.get("dispatch_claim_id")
    if isinstance(claim_id, str) and claim_id.strip():
        return claim_id.strip()[:160]
    return None


def _parse_call_mode(metadata: str) -> str:
    obj = _parse_metadata_json(metadata)
    mode = str(obj.get("mode") or "").strip().lower()
    if mode in {"call", "wing", "listen_only"}:
        return mode
    if bool(obj.get("listenOnly") or obj.get("listen_only")):
        return "listen_only"
    if bool(obj.get("wingMode") or obj.get("wing_mode")):
        return "wing"
    return "call"


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
def _validate_dispatch_job_bindings(
    job: Any,
    *,
    fallback_room_name: str,
    call_session_id: str,
    registered_agent_name: str,
) -> tuple[str, Optional[str]]:
    if not (call_session_id or "").strip():
        raise RuntimeError("signed dispatch call session is missing")
    room = getattr(job, "room", None)
    room_name = str(
        getattr(room, "name", "") or fallback_room_name or ""
    ).strip()
    registered_agent = (registered_agent_name or "").strip()
    if not room_name or not registered_agent:
        raise RuntimeError("signed voice dispatch binding is incomplete")
    dispatched_agent = str(getattr(job, "agent_name", "") or "").strip()
    if dispatched_agent and dispatched_agent != registered_agent:
        raise RuntimeError("dispatch agent mismatch with registered voice gateway")
    participant = getattr(job, "participant", None)
    participant_identity = str(
        getattr(participant, "identity", "") or ""
    ).strip()
    return room_name, participant_identity or None


def _validate_voice_session_claim(
    payload: Any,
    *,
    expected_call_session_id: str,
    expected_room_name: str,
    expected_gateway_agent_name: str,
    expected_owner_participant_identity: Optional[str],
) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("status") != "claimed":
        raise RuntimeError("invalid canonical voice claim")
    expected_fields = {
        "callSessionId": expected_call_session_id,
        "roomName": expected_room_name,
        "gatewayAgentName": expected_gateway_agent_name,
    }
    for field, expected in expected_fields.items():
        actual = payload.get(field)
        if not isinstance(actual, str) or not actual.strip() or len(actual) > 256:
            raise RuntimeError("invalid canonical voice claim")
        if not isinstance(expected, str) or not expected.strip():
            raise RuntimeError("invalid canonical voice claim")
        if actual.strip() != expected.strip():
            raise RuntimeError(f"canonical voice claim mismatch: {field}")

    claimed_owner = payload.get("ownerParticipantIdentity")
    if (
        not isinstance(claimed_owner, str)
        or not claimed_owner.strip()
        or len(claimed_owner) > 256
    ):
        raise RuntimeError("invalid canonical voice claim")
    expected_owner = (expected_owner_participant_identity or "").strip()
    if expected_owner and claimed_owner.strip() != expected_owner:
        raise RuntimeError("canonical voice claim mismatch: ownerParticipantIdentity")

    route = payload.get("requestedVoiceRoute")
    if not isinstance(route, dict):
        raise RuntimeError("invalid canonical voice claim")
    normalized_route = _normalize_requested_voice_route(route)
    for modality in ("stt", "tts"):
        provider = normalized_route[modality].get("provider")
        if not provider or len(provider) > 80:
            raise RuntimeError("invalid canonical voice claim")
        variant = normalized_route[modality].get("variant")
        if variant is not None and len(variant) > 256:
            raise RuntimeError("invalid canonical voice claim")

    call_state = parse_voice_call_state_v1(
        payload.get("callState"),
        expected_call_session_id=expected_call_session_id,
    )
    if call_state is None:
        raise RuntimeError("invalid canonical voice claim")

    state = payload.get("speakerSessionState")
    normalized_state = None
    if state is not None:
        shared_track_sids = state.get("sharedTrackSids") if isinstance(state, dict) else None
        shared_participant_identities = (
            state.get("sharedParticipantIdentities") if isinstance(state, dict) else None
        )
        if (
            not isinstance(state, dict)
            or state.get("version") != 1
            or state.get("callSessionId") != expected_call_session_id
            or state.get("attributionState")
            not in {"single_speaker", "shared_mic_unverified"}
            or not isinstance(state.get("revision"), int)
            or isinstance(state.get("revision"), bool)
            or state.get("revision") < 0
            or not isinstance(state.get("detectedAt"), str)
            or not state.get("detectedAt").strip()
            or (
                shared_track_sids is not None
                and (
                    not isinstance(shared_track_sids, list)
                    or len(shared_track_sids) > 64
                    or any(
                        not isinstance(value, str)
                        or not value.strip()
                        or len(value.strip()) > 160
                        for value in shared_track_sids
                    )
                )
            )
            or (
                shared_participant_identities is not None
                and (
                    not isinstance(shared_participant_identities, list)
                    or len(shared_participant_identities) > 64
                    or any(
                        not isinstance(value, str)
                        or not value.strip()
                        or len(value.strip()) > 160
                        for value in shared_participant_identities
                    )
                )
            )
        ):
            raise RuntimeError("invalid canonical voice claim")
        normalized_state = dict(state)
        if isinstance(shared_track_sids, list):
            normalized_state["sharedTrackSids"] = sorted(
                {value.strip() for value in shared_track_sids}
            )
        if isinstance(shared_participant_identities, list):
            normalized_state["sharedParticipantIdentities"] = sorted(
                {value.strip() for value in shared_participant_identities}
            )

    return {
        **payload,
        "callSessionId": expected_call_session_id.strip(),
        "roomName": expected_room_name.strip(),
        "gatewayAgentName": expected_gateway_agent_name.strip(),
        "ownerParticipantIdentity": claimed_owner.strip(),
        "requestedVoiceRoute": normalized_route,
        "callState": call_state,
        "speakerSessionState": normalized_state,
    }


async def _claim_voice_session(
    origin: str,
    auth: LibreChatAuth,
    *,
    expected_room_name: str,
    expected_gateway_agent_name: str,
    expected_owner_participant_identity: Optional[str],
    dispatch_claim_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if not auth.call_session_id:
        return None
    if not auth.call_secret:
        return None
    if not auth.job_id:
        logger.error("[voice-gateway] Missing job id for voice lease claim")
        return None
    if not auth.worker_id:
        logger.error("[voice-gateway] Missing worker id for voice lease claim")
        return None

    url = f"{origin.rstrip('/')}/api/viventium/voice/claim"
    headers = {
        "X-VIVENTIUM-CALL-SESSION": auth.call_session_id,
        "X-VIVENTIUM-CALL-SECRET": auth.call_secret,
        "X-VIVENTIUM-JOB-ID": auth.job_id,
    }
    headers["X-VIVENTIUM-WORKER-ID"] = auth.worker_id
    if dispatch_claim_id:
        headers["X-VIVENTIUM-DISPATCH-CLAIM"] = dispatch_claim_id

    timeout = aiohttp.ClientTimeout(total=5)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers) as resp:
                if resp.status == 200:
                    payload = await resp.json()
                    return _validate_voice_session_claim(
                        payload,
                        expected_call_session_id=auth.call_session_id,
                        expected_room_name=expected_room_name,
                        expected_gateway_agent_name=expected_gateway_agent_name,
                        expected_owner_participant_identity=expected_owner_participant_identity,
                    )
                await resp.read()
                logger.warning(
                    "[voice-gateway] Voice lease claim rejected (status=%s)",
                    resp.status,
                )
    except RuntimeError:
        logger.error("[voice-gateway] Canonical voice lease claim rejected")
        raise
    except Exception as exc:
        logger.warning("[voice-gateway] Voice lease claim failed: %s", exc)
    return None
# === VIVENTIUM END ===


async def _mark_voice_session_ready(
    origin: str,
    auth: LibreChatAuth,
) -> Optional[dict[str, Any]]:
    """Atomically clear a retryable failure only for the exact live worker."""
    if (
        not auth.call_session_id
        or not auth.call_secret
        or not auth.job_id
        or not auth.worker_id
    ):
        return None
    url = (
        f"{origin.rstrip('/')}/api/viventium/voice/call-sessions/"
        f"{quote(auth.call_session_id, safe='')}/ready"
    )
    headers = {
        "X-VIVENTIUM-CALL-SESSION": auth.call_session_id,
        "X-VIVENTIUM-CALL-SECRET": auth.call_secret,
        "X-VIVENTIUM-JOB-ID": auth.job_id,
        "X-VIVENTIUM-WORKER-ID": auth.worker_id,
    }
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=2.0)
        ) as session:
            async with session.post(
                url,
                headers=headers,
                json={"version": 1},
            ) as resp:
                if resp.status != 200:
                    await resp.read()
                    logger.warning(
                        "[voice-gateway] Voice readiness rejected status=%s speechEnabled=false",
                        resp.status,
                    )
                    return None
                payload = await resp.json()
    except Exception as exc:
        logger.warning(
            "[voice-gateway] Voice readiness failed error=%s speechEnabled=false",
            type(exc).__name__,
        )
        return None
    state = parse_voice_call_state_v1(
        payload,
        expected_call_session_id=auth.call_session_id,
    )
    if state is None or state["status"] != "listening":
        logger.warning(
            "[voice-gateway] Voice readiness response invalid speechEnabled=false"
        )
        return None
    return state


async def _establish_voice_response_plane(
    *,
    llm_impl: Any,
    mark_ready: Any,
    timeout_s: float,
) -> tuple[Optional[Any], Optional[dict[str, Any]]]:
    """Require task-SSE authentication before mutating backend call readiness."""
    stream_task = llm_impl.start_call_task_event_stream()
    stream_ready = bool(
        stream_task is not None
        and await llm_impl.wait_call_task_event_stream_ready(timeout_s=timeout_s)
    )
    if not stream_ready:
        await llm_impl.stop_call_task_event_stream()
        return None, None
    ready_state = await mark_ready()
    if ready_state is None:
        await llm_impl.stop_call_task_event_stream()
        return None, None
    return stream_task, ready_state


async def _abandon_voice_session_claim(
    origin: str,
    auth: LibreChatAuth,
    *,
    reason: str,
) -> bool:
    allowed_reasons = {
        "owner_timeout",
        "owner_mismatch",
        "gateway_initialization_failed",
    }
    normalized_reason = (reason or "").strip()
    if (
        normalized_reason not in allowed_reasons
        or not auth.call_session_id
        or not auth.call_secret
        or not auth.job_id
        or not auth.worker_id
    ):
        return False
    url = f"{origin.rstrip('/')}/api/viventium/voice/claim/abandon"
    headers = {
        "X-VIVENTIUM-CALL-SESSION": auth.call_session_id,
        "X-VIVENTIUM-CALL-SECRET": auth.call_secret,
        "X-VIVENTIUM-JOB-ID": auth.job_id,
    }
    headers["X-VIVENTIUM-WORKER-ID"] = auth.worker_id
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=1.0)
        ) as session:
            async with session.post(
                url,
                headers=headers,
                json={"reason": normalized_reason},
            ) as resp:
                if resp.status != 200:
                    await resp.read()
                    logger.warning(
                        "[voice-gateway] Voice lease abandon rejected status=%s reason=%s",
                        resp.status,
                        normalized_reason,
                    )
                    return False
                payload = await resp.json()
    except Exception as exc:
        logger.warning(
            "[voice-gateway] Voice lease abandon failed reason=%s error=%s",
            normalized_reason,
            type(exc).__name__,
        )
        return False
    released = bool(
        isinstance(payload, dict)
        and payload.get("version") == 1
        and payload.get("released") is True
    )
    logger.info(
        "[voice-gateway] Voice lease abandon completed reason=%s released=%s",
        normalized_reason,
        released,
    )
    return released


async def _report_voice_gateway_failure(
    origin: str,
    auth: LibreChatAuth,
    *,
    classification: str,
    phase: str,
    fatal: bool,
    modality: Optional[str] = None,
    provider: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if (
        classification not in {"no_route", "provider_failure", "gateway_down"}
        or phase not in {"initialization", "runtime"}
        or modality not in {None, "stt", "tts"}
        or not auth.call_session_id
        or not auth.call_secret
        or not auth.job_id
        or not auth.worker_id
    ):
        return None
    normalized_provider = (provider or "").strip().lower()
    if len(normalized_provider) > 80:
        return None
    url = (
        f"{origin.rstrip('/')}/api/viventium/voice/call-sessions/"
        f"{quote(auth.call_session_id, safe='')}/failure"
    )
    headers = {
        "X-VIVENTIUM-CALL-SESSION": auth.call_session_id,
        "X-VIVENTIUM-CALL-SECRET": auth.call_secret,
        "X-VIVENTIUM-JOB-ID": auth.job_id,
        "X-VIVENTIUM-WORKER-ID": auth.worker_id,
    }
    body: dict[str, Any] = {
        "version": 1,
        "classification": classification,
        "phase": phase,
        "fatal": bool(fatal),
    }
    if modality is not None:
        body["modality"] = modality
    if normalized_provider:
        body["provider"] = normalized_provider
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=1.0)
        ) as session:
            async with session.post(url, headers=headers, json=body) as resp:
                if resp.status != 200:
                    await resp.read()
                    logger.warning(
                        "[VoiceProvider] failure_report_rejected callSessionId=%s classification=%s phase=%s status=%s",
                        auth.call_session_id,
                        classification,
                        phase,
                        resp.status,
                    )
                    return None
                payload = await resp.json()
    except Exception as exc:
        logger.warning(
            "[VoiceProvider] failure_report_failed callSessionId=%s classification=%s phase=%s error=%s",
            auth.call_session_id,
            classification,
            phase,
            type(exc).__name__,
        )
        return None
    if (
        not isinstance(payload, dict)
        or payload.get("version") != 1
        or payload.get("callSessionId") != auth.call_session_id
        or payload.get("status") not in {"failed", "degraded"}
        or not isinstance(payload.get("error"), dict)
    ):
        return None
    logger.info(
        "[VoiceProvider] failure_reported callSessionId=%s classification=%s modality=%s phase=%s fatal=%s status=%s",
        auth.call_session_id,
        classification,
        modality or "none",
        phase,
        bool(fatal),
        payload["status"],
    )
    return payload


async def _report_voice_initialization_failure_and_abandon(
    origin: str,
    auth: LibreChatAuth,
    error: VoiceRouteError,
) -> tuple[Optional[dict[str, Any]], bool]:
    """Surface a safe fatal state before releasing the exact worker lease."""
    reported = await _report_voice_gateway_failure(
        origin,
        auth,
        classification=error.code,
        modality=error.modality,
        provider=error.provider,
        phase="initialization",
        fatal=True,
    )
    released = await _abandon_voice_session_claim(
        origin,
        auth,
        reason="gateway_initialization_failed",
    )
    return reported, released


async def _report_voice_gateway_initialization_failure_and_abandon(
    origin: str,
    auth: LibreChatAuth,
) -> tuple[Optional[dict[str, Any]], bool]:
    """Report a non-provider gateway startup failure before releasing ownership."""
    reported = await _report_voice_gateway_failure(
        origin,
        auth,
        classification="gateway_down",
        phase="initialization",
        fatal=True,
    )
    released = await _abandon_voice_session_claim(
        origin,
        auth,
        reason="gateway_initialization_failed",
    )
    return reported, released


def _classify_runtime_voice_provider_failure(
    event: Any,
    *,
    stt_impl: Any,
    tts_impl: Any,
    stt_provider: str,
    tts_provider: str,
) -> Optional[tuple[str, str]]:
    """Classify only SDK provider errors by their exact source object.

    LiveKit's ``ErrorEvent`` preserves the STT/TTS instance that emitted the
    failure.  Identity comparison avoids converting LLM, room, or microphone
    failures into misleading provider UI states.
    """
    source = getattr(event, "source", None)
    if source is stt_impl:
        provider = (stt_provider or "").strip().lower()
        return ("stt", provider) if provider else None
    if source is tts_impl:
        provider = (tts_provider or "").strip().lower()
        return ("tts", provider) if provider else None
    return None


class CanonicalOwnerBindingError(RuntimeError):
    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(message)


async def _resolve_canonical_owner_participant(
    ctx: Any,
    canonical_owner_identity: str,
    *,
    timeout_s: float,
) -> Any:
    """Connect audio and bind only the backend-owned participant identity."""
    identity = (canonical_owner_identity or "").strip()
    if not identity:
        raise CanonicalOwnerBindingError("owner_timeout", "canonical owner unavailable")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    try:
        participant = await asyncio.wait_for(
            ctx.wait_for_participant(identity=identity),
            timeout=max(float(timeout_s), 0.001),
        )
    except (asyncio.TimeoutError, TimeoutError) as exc:
        raise CanonicalOwnerBindingError(
            "owner_timeout", "canonical owner unavailable before timeout"
        ) from exc
    actual_identity = str(getattr(participant, "identity", "") or "").strip()
    if actual_identity != identity:
        raise CanonicalOwnerBindingError(
            "owner_mismatch", "canonical owner mismatch after room connect"
        )
    return participant


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


def _participant_identity_connected(room: Any, participant_identity: str) -> bool:
    """Match only the canonical backend-claimed owner; observers never receive owner speech."""
    identity = (participant_identity or "").strip()
    if not identity:
        return False
    participants = getattr(room, "remote_participants", None)
    if participants is None:
        return False
    try:
        if identity in participants:
            return True
        values = participants.values()
    except (AttributeError, TypeError):
        values = participants
    try:
        return any(
            str(getattr(participant, "identity", "") or "").strip() == identity
            for participant in values
        )
    except TypeError:
        return False


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
        # The job shutdown callback owns marker cleanup. A transient empty room is the normal
        # browser-refresh/reconnect path and must not trigger duplicate heavy model prewarm.

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
    # Speaker labels use the already-selected AssemblyAI stream. They do not select a provider or
    # create a second/cloud route, so explicit local-only configurations remain local-only.
    kwargs: dict[str, Any] = {"speaker_labels": True}
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
            _raise_route_error(
                "provider_failure",
                modality="stt",
                provider="assemblyai",
                reason="plugin is unavailable",
            )
        elif not (os.getenv("ASSEMBLYAI_API_KEY") or "").strip():
            _raise_route_error(
                "provider_failure",
                modality="stt",
                provider="assemblyai",
                reason="credentials are unavailable",
            )
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
            error = VoiceRouteError(
                "provider_failure",
                modality="stt",
                provider="pywhispercpp",
                reason="could not be made ready; the gateway will not silently switch providers",
            )
            raise error from exc

    if provider != "openai":
        _raise_route_error(
            "no_route",
            modality="stt",
            provider=provider,
            reason="is not implemented",
        )

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
        except Exception as exc:
            logger.error(
                "[voice-gateway] Local Chatterbox TTS prewarm failed; refusing to register an unhealthy local TTS worker",
                exc_info=True,
            )
            raise RuntimeError(
                "Local Chatterbox TTS prewarm failed; worker will not register."
            ) from exc


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


def _build_room_options(
    *, sync_transcription: bool, participant_identity: str = ""
) -> Any:
    options: dict[str, Any] = {
        "text_output": room_io.TextOutputOptions(
            sync_transcription=sync_transcription
        ),
        "close_on_disconnect": False,
    }
    if participant_identity:
        options["participant_identity"] = participant_identity
    return room_io.RoomOptions(**options)


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


def _interrupt_livekit_speech_handles(handles: set[Any]) -> None:
    """Stop only still-active progress handles and forget the completed ones."""
    pending = list(handles)
    handles.clear()
    for handle in pending:
        try:
            if not bool(handle.done()):
                handle.interrupt(force=True)
        except Exception as exc:
            logger.warning(
                "[VoiceTask] progress_interrupt_failed error=%s callContinues=true",
                type(exc).__name__,
            )


def _interrupt_agent_session_speech(session: Any) -> None:
    """Stop current AgentSession playout while preserving its backend task and room."""
    try:
        session.interrupt(force=True)
    except Exception as exc:
        logger.warning(
            "[VoiceMode] main_speech_interrupt_failed error=%s callContinues=true",
            type(exc).__name__,
        )


def _apply_authoritative_call_mode_to_speech_planes(
    mode: str,
    *,
    progress_controller: Any,
    ambient_ingress: Any,
    followup_scheduler: Any,
    session: Any,
) -> None:
    """Apply one validated mode atomically without reconnecting or cancelling backend work."""
    if mode not in {"call", "wing", "listen_only"}:
        return
    progress_controller.set_mode(mode)
    ambient_ingress.set_mode(mode)
    followup_scheduler.set_mode(mode)
    if mode == "listen_only":
        _interrupt_agent_session_speech(session)


def _suspend_all_call_speech_until_authoritative(
    *,
    progress_controller: Any,
    followup_scheduler: Any,
    session: Any,
    authoritative_mode_state: Optional[Any] = None,
) -> None:
    if authoritative_mode_state is not None:
        authoritative_mode_state.suspend()
    progress_controller.suspend_until_authoritative()
    followup_scheduler.suspend_until_authoritative()
    _interrupt_agent_session_speech(session)


def _apply_task_cancel_suppression(
    task_id: str,
    *,
    progress_controller: Any,
    followup_scheduler: Any,
    session: Any,
) -> None:
    """Synchronously silence accepted cancellation while backend settlement continues."""
    progress_controller.suppress_task(task_id)
    followup_scheduler.cancel_pending()
    _interrupt_agent_session_speech(session)


async def _publish_livekit_speaker_segments(
    local_participant: Any,
    segments: list[dict[str, Any]],
    *,
    owner_participant_identity: str,
) -> None:
    """Publish validated gateway-owned segments without logging transcript content."""
    for segment in segments:
        if not isinstance(segment, dict) or segment.get("version") != 1:
            continue
        payload = json.dumps(segment, ensure_ascii=True, separators=(",", ":"))
        if not await _publish_bounded_livekit_data(
            local_participant,
            payload,
            topic="viventium.speaker.v1",
            correlation_id=str(segment.get("segmentId") or ""),
            destination_identity=owner_participant_identity,
        ):
            continue
        speaker = segment.get("speaker") if isinstance(segment.get("speaker"), dict) else {}
        logger.info(
            "[VoiceSpeaker] segment_published callSessionId=%s turnId=%s segmentId=%s sequence=%s revision=%s final=%s attribution=%s source=%s chars=%s",
            segment.get("callSessionId", ""),
            segment.get("turnId", ""),
            segment.get("segmentId", ""),
            segment.get("sequence", ""),
            segment.get("revision", ""),
            bool(segment.get("isFinal")),
            speaker.get("attribution", "unknown"),
            speaker.get("source", "unknown"),
            len(str(segment.get("text") or "")),
        )


async def _publish_livekit_task_event(
    local_participant: Any,
    task_event: dict[str, Any],
    *,
    owner_participant_identity: str,
) -> None:
    if (
        not isinstance(task_event, dict)
        or task_event.get("version") != 1
        or not isinstance(task_event.get("taskId"), str)
        or not isinstance(task_event.get("sequence"), int)
    ):
        return
    payload = json.dumps(task_event, ensure_ascii=True, separators=(",", ":"))
    if not await _publish_bounded_livekit_data(
        local_participant,
        payload,
        topic="viventium.task.v1",
        correlation_id=str(task_event.get("eventId") or task_event.get("taskId") or ""),
        destination_identity=owner_participant_identity,
    ):
        return
    logger.info(
        "[VoiceTask] event_published callSessionId=%s taskId=%s eventId=%s sequence=%s state=%s phase=%s",
        task_event.get("callSessionId", ""),
        task_event.get("taskId", ""),
        task_event.get("eventId", ""),
        task_event.get("sequence", ""),
        task_event.get("state", ""),
        task_event.get("phase", ""),
    )


async def _publish_bounded_livekit_data(
    local_participant: Any,
    payload: str,
    *,
    topic: str,
    correlation_id: str,
    destination_identity: str,
) -> bool:
    destination = (destination_identity or "").strip()
    if not destination:
        logger.warning(
            "[VoiceData] publish_skipped topic=%s correlationId=%s reason=missing_owner_destination",
            topic,
            correlation_id,
        )
        return False
    payload_bytes = payload.encode("utf-8")
    if len(payload_bytes) > 14_000:
        logger.warning(
            "[VoiceData] publish_skipped topic=%s correlationId=%s reason=payload_too_large bytes=%s",
            topic,
            correlation_id,
            len(payload_bytes),
        )
        return False
    try:
        await local_participant.publish_data(
            payload,
            reliable=True,
            topic=topic,
            destination_identities=[destination],
        )
        return True
    except Exception as exc:
        logger.warning(
            "[VoiceData] publish_failed topic=%s correlationId=%s error=%s callContinues=true",
            topic,
            correlation_id,
            type(exc).__name__,
        )
        return False


def _linked_participant_speaker_context(
    room: Any, owner_participant_identity: str
) -> dict[str, Any]:
    owner_identity = (owner_participant_identity or "").strip()
    if not owner_identity:
        return {}
    participant = next(
        (
            item
            for item in getattr(room, "remote_participants", {}).values()
            if str(getattr(item, "identity", "") or "").strip() == owner_identity
        ),
        None,
    )
    if participant is None:
        return {}
    track_sid = ""
    publications = list(getattr(participant, "track_publications", {}).values())
    microphone_publication = next(
        (
            item
            for item in publications
            if str(getattr(item, "source", "")).lower().endswith("microphone")
        ),
        publications[0] if publications else None,
    )
    if microphone_publication is not None:
        track_sid = str(getattr(microphone_publication, "sid", "") or "")
    identity = str(getattr(participant, "identity", "") or "").strip()
    return {
        "participant_identity": identity,
        "participant_name": str(getattr(participant, "name", "") or "").strip(),
        "track_sid": track_sid,
        # LiveKit participant identity is signed by the token minted for the authenticated call
        # session. Provider diarization never upgrades a different physical voice to this trust.
        "owner_signed": identity == owner_identity,
    }


# === VIVENTIUM START ===
# Feature: Cartesia voice-control tags are TTS-only, never user transcript text.
class AuthoritativeCallModeState:
    """Shared fail-closed mode gate for every response-producing call plane."""

    def __init__(self) -> None:
        self._mode: Optional[str] = None
        self._authoritative = False

    @property
    def mode(self) -> Optional[str]:
        return self._mode if self._authoritative else None

    @property
    def allows_agent_dispatch(self) -> bool:
        return self._authoritative and self._mode in {"call", "wing"}

    @property
    def suppressed_mode(self) -> str:
        return "listen_only" if self.mode == "listen_only" else "uncertain"

    def apply(self, mode: str) -> None:
        if mode not in {"call", "wing", "listen_only"}:
            self.suspend()
            return
        self._mode = mode
        self._authoritative = True

    def suspend(self) -> None:
        self._authoritative = False


class CallTaskStreamSpeechAuthority:
    """Fail-close every speech plane around the authoritative task SSE lifecycle."""

    _STREAM_STATES = {
        "connecting",
        "syncing",
        "connected",
        "disconnected",
        "terminal",
        "stopped",
    }
    _CALL_STATUSES = {
        "created",
        "connecting",
        "listening",
        "speaking",
        "working",
        "needs_input",
        "degraded",
        "failed",
        "ended",
    }

    def __init__(
        self,
        *,
        call_session_id: str,
        fetch_call_state: Any,
        suspend: Any,
        apply_state: Any,
    ) -> None:
        self._call_session_id = call_session_id
        self._fetch_call_state = fetch_call_state
        self._suspend = suspend
        self._apply_state = apply_state
        self._session_ready = False
        self._stream_connected = False
        self._authoritative = False

    @property
    def authoritative(self) -> bool:
        return self._authoritative

    @property
    def stream_connected(self) -> bool:
        return self._stream_connected

    def _valid_call_state(
        self,
        state: Any,
        *,
        require_listening: bool = False,
    ) -> bool:
        if not isinstance(state, dict):
            return False
        revision = state.get("revision")
        status = state.get("status")
        return bool(
            state.get("version") == 1
            and state.get("callSessionId") == self._call_session_id
            and state.get("mode") in {"call", "wing", "listen_only"}
            and status in self._CALL_STATUSES
            and status not in {"failed", "ended"}
            and (not require_listening or status == "listening")
            and isinstance(revision, int)
            and not isinstance(revision, bool)
            and revision >= 0
            and isinstance(state.get("updatedAt"), str)
            and bool(state.get("updatedAt"))
        )

    def mark_session_ready(self, state: Any) -> bool:
        """Open speech only after both SSE 2xx and the exact ready transition."""
        self._authoritative = False
        if not self._stream_connected or not self._valid_call_state(
            state,
            require_listening=True,
        ):
            self._session_ready = False
            self._suspend()
            return False
        self._apply_state(state)
        self._session_ready = True
        self._authoritative = True
        return True

    async def reconcile(self) -> bool:
        """Restore only from a fresh call snapshot while the task stream is live."""
        self._authoritative = False
        self._suspend()
        if not self._session_ready or not self._stream_connected:
            return False
        try:
            snapshot = await self._fetch_call_state()
        except Exception as exc:
            logger.warning(
                "[VoiceTask] call_stream_snapshot_failed callSessionId=%s error=%s speechSuspended=true",
                self._call_session_id,
                type(exc).__name__,
            )
            return False
        if not self._valid_call_state(snapshot):
            return False
        self._apply_state(snapshot)
        self._authoritative = True
        return True

    async def on_stream_health(self, health: Any) -> None:
        valid = bool(
            isinstance(health, dict)
            and health.get("version") == 1
            and health.get("callSessionId") == self._call_session_id
            and health.get("state") in self._STREAM_STATES
        )
        state = health.get("state") if valid else "invalid"
        if state != "connected":
            self._stream_connected = False
            self._authoritative = False
            self._suspend()
            return

        status = health.get("status")
        if (
            not isinstance(status, int)
            or isinstance(status, bool)
            or status < 200
            or status >= 300
        ):
            self._stream_connected = False
            self._authoritative = False
            self._suspend()
            return

        self._stream_connected = True
        # A 2xx reconnect proves transport/auth, but not current call state. Keep
        # all speech interrupted until a fresh authoritative state snapshot lands.
        if not self._session_ready:
            self._authoritative = False
            self._suspend()
            return
        await self.reconcile()


def _ingest_raw_stt_speaker_event(
    tracker: SpeakerSegmentTracker,
    event: Any,
    *,
    timeline_offset_s: float,
) -> tuple[list[dict[str, Any]], bool]:
    """Preserve provider timing/diarization before AgentSession strips SpeechData."""
    event_type = getattr(event, "type", None)
    is_interim = event_type == SpeechEventType.INTERIM_TRANSCRIPT
    is_final = event_type == SpeechEventType.FINAL_TRANSCRIPT
    if not (is_interim or is_final):
        return [], False
    alternatives = getattr(event, "alternatives", None)
    if not isinstance(alternatives, list) or not alternatives:
        return [], is_final
    alternative = alternatives[0]
    relative_start = getattr(alternative, "start_time", None)
    relative_end = getattr(alternative, "end_time", None)
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    if (
        isinstance(relative_start, (int, float))
        and not isinstance(relative_start, bool)
        and isinstance(relative_end, (int, float))
        and not isinstance(relative_end, bool)
        and float(relative_end) > float(relative_start)
    ):
        start_time = max(float(timeline_offset_s), 0.0) + float(relative_start)
        end_time = max(float(timeline_offset_s), 0.0) + float(relative_end)
    changes = tracker.ingest(
        transcript=str(getattr(alternative, "text", "") or ""),
        is_final=is_final,
        provider_speaker_id=getattr(alternative, "speaker_id", None),
        created_at=time.time(),
        start_time=start_time,
        end_time=end_time,
    )
    return changes, is_final


class ViventiumVoiceAgent(Agent):
    def __init__(
        self,
        *,
        speaker_tracker: Optional[SpeakerSegmentTracker] = None,
        authoritative_mode_state: Optional[AuthoritativeCallModeState] = None,
        persist_suppressed_turn: Optional[Any] = None,
        on_finalized_speaker_context: Optional[Any] = None,
        on_interim_speaker_changes: Optional[Any] = None,
        speaker_timeline_offset: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._speaker_tracker = speaker_tracker
        self._authoritative_mode_state = authoritative_mode_state
        self._persist_suppressed_turn = persist_suppressed_turn
        self._on_finalized_speaker_context = on_finalized_speaker_context
        self._on_interim_speaker_changes = on_interim_speaker_changes
        self._speaker_timeline_offset = speaker_timeline_offset

    async def on_user_turn_completed(self, turn_ctx: Any, new_message: Any) -> None:
        _ = turn_ctx
        context: dict[str, Any] = {}
        if self._speaker_tracker is not None:
            extra = getattr(new_message, "extra", None)
            existing = (
                extra.get(SPEAKER_CONTEXT_EXTRA_KEY)
                if isinstance(extra, dict)
                else None
            )
            context = (
                existing
                if isinstance(existing, dict)
                else attach_speaker_context_to_message(self._speaker_tracker, new_message)
            )
            if self._on_finalized_speaker_context is not None:
                finalized = self._on_finalized_speaker_context(context)
                if inspect.isawaitable(finalized):
                    await finalized
        mode_state = self._authoritative_mode_state
        if mode_state is None or mode_state.allows_agent_dispatch:
            return
        try:
            if self._persist_suppressed_turn is not None:
                await self._persist_suppressed_turn(
                    context,
                    mode_state.suppressed_mode,
                )
        except Exception as exc:
            logger.warning(
                "[VoiceMode] suppressed_turn_persist_failed error=%s responseSuppressed=true",
                type(exc).__name__,
            )
        raise StopResponse()

    async def stt_node(self, audio: Any, model_settings: Any) -> Any:
        raw_events = super().stt_node(audio, model_settings)
        if inspect.isawaitable(raw_events):
            raw_events = await raw_events
        timeline_offset_s = (
            float(self._speaker_timeline_offset())
            if self._speaker_timeline_offset is not None
            else 0.0
        )
        async for event in raw_events:
            if self._speaker_tracker is not None:
                changes, is_final = _ingest_raw_stt_speaker_event(
                    self._speaker_tracker,
                    event,
                    timeline_offset_s=timeline_offset_s,
                )
                if changes and not is_final and self._on_interim_speaker_changes is not None:
                    result = self._on_interim_speaker_changes(changes)
                    if inspect.isawaitable(result):
                        await result
            yield event

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
        self._mode = "call"
        self._authoritative_mode_available = True
        self._speech_handles: set[Any] = set()

    def set_mode(self, mode: str) -> None:
        if mode not in {"call", "wing", "listen_only"}:
            return
        self._mode = mode
        self._authoritative_mode_available = True
        if mode == "listen_only":
            _interrupt_livekit_speech_handles(self._speech_handles)

    def suspend_until_authoritative(self) -> None:
        self._authoritative_mode_available = False
        _interrupt_livekit_speech_handles(self._speech_handles)

    def cancel_pending(self) -> None:
        for task in (
            self._task,
            self._cortex_task,
            *self._glasshive_tasks,
        ):
            if task is not None and not task.done():
                task.cancel()
        _interrupt_livekit_speech_handles(self._speech_handles)

    async def close(self) -> None:
        tasks = {
            task
            for task in (self._task, self._cortex_task, *self._glasshive_tasks)
            if task is not None and not task.done()
        }
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        _interrupt_livekit_speech_handles(self._speech_handles)

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
                                    if (
                                        self._mode == "listen_only"
                                        or not self._authoritative_mode_available
                                    ):
                                        logger.info(
                                            "[VoiceMode] glasshive_voice_suppressed message_id=%s linkedChatPreserved=true",
                                            message_id,
                                        )
                                        return
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
        if self._mode == "listen_only" or not self._authoritative_mode_available:
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
            handle = self._session.say(
                cleaned,
                allow_interruptions=True,
                add_to_chat_ctx=False,
            )
            if handle is not None:
                self._speech_handles.add(handle)
                add_done_callback = getattr(handle, "add_done_callback", None)
                if callable(add_done_callback):
                    add_done_callback(
                        lambda completed: self._speech_handles.discard(completed)
                    )
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
    call_session_id = _parse_call_session_id(job_metadata)
    dispatch_claim_id = _parse_dispatch_claim_id(job_metadata)

    if not call_session_id:
        logger.error("Missing callSessionId in signed dispatch metadata")
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
    expected_gateway_agent_name = (env.livekit_agent_name or "").strip()
    expected_room_name, expected_owner_participant_identity = (
        _validate_dispatch_job_bindings(
            ctx.job,
            fallback_room_name=str(getattr(ctx.room, "name", "") or ""),
            call_session_id=call_session_id,
            registered_agent_name=expected_gateway_agent_name,
        )
    )
    claimed = await _claim_voice_session(
        env.librechat_origin,
        auth,
        expected_room_name=expected_room_name,
        expected_gateway_agent_name=expected_gateway_agent_name,
        expected_owner_participant_identity=expected_owner_participant_identity,
        dispatch_claim_id=dispatch_claim_id,
    )
    if not claimed:
        logger.warning("[voice-gateway] Voice session already claimed; exiting worker")
        shutdown = getattr(ctx, "shutdown", None)
        if callable(shutdown):
            try:
                await shutdown()
            except Exception:
                logger.debug("[voice-gateway] Duplicate-session shutdown hook failed", exc_info=True)
        return
    claimed_call_state = claimed["callState"]
    call_mode = str(claimed_call_state["mode"])
    authoritative_mode_state = AuthoritativeCallModeState()
    # Claim state describes durable intent, but it is not a readiness grant. A
    # reclaimed call may intentionally still carry a retryable failure tombstone.
    # Keep every response plane closed until the exact job+worker marks ready.
    voice_session_ready = [False]
    unready_claim_active = [True]
    abandon_attempted = [False]

    async def _abandon_unready_claim(
        reason: str = "gateway_initialization_failed",
    ) -> bool:
        if not unready_claim_active[0] or abandon_attempted[0]:
            return False
        abandon_attempted[0] = True
        released = await _abandon_voice_session_claim(
            env.librechat_origin,
            auth,
            reason=reason,
        )
        if released:
            unready_claim_active[0] = False
        else:
            abandon_attempted[0] = False
        return released

    async def _release_unready_claim_on_shutdown(*_args: Any) -> None:
        await _abandon_unready_claim("gateway_initialization_failed")

    ctx.add_shutdown_callback(_release_unready_claim_on_shutdown)

    async def _fail_voice_route_initialization(exc: VoiceRouteError) -> None:
        _reported, released = await _report_voice_initialization_failure_and_abandon(
            env.librechat_origin,
            auth,
            exc,
        )
        if released:
            unready_claim_active[0] = False
            abandon_attempted[0] = True
        else:
            # Keep the shutdown callback armed for a best-effort release retry.
            abandon_attempted[0] = False
        shutdown = getattr(ctx, "shutdown", None)
        if callable(shutdown):
            result = shutdown()
            if inspect.isawaitable(result):
                await result
    owner_participant_identity = claimed["ownerParticipantIdentity"]
    owner_wait_s = min(
        max(_parse_float_env("VIVENTIUM_VOICE_OWNER_WAIT_S", 8.0), 0.25),
        30.0,
    )
    try:
        await _resolve_canonical_owner_participant(
            ctx,
            owner_participant_identity,
            timeout_s=owner_wait_s,
        )
    except CanonicalOwnerBindingError as exc:
        await _abandon_unready_claim(exc.reason)
        shutdown = getattr(ctx, "shutdown", None)
        if callable(shutdown):
            result = shutdown()
            if inspect.isawaitable(result):
                await result
        raise
    # === VIVENTIUM END ===

    # === VIVENTIUM START ===
    _attach_room_diagnostics(
        ctx,
        call_session_id=call_session_id,
        active_job_marker=active_job_marker,
    )
    # === VIVENTIUM END ===

    capabilities = _build_voice_capability_catalog(env)
    requested_voice_route = claimed["requestedVoiceRoute"]
    speaker_session_state = claimed.get("speakerSessionState")
    try:
        env = _apply_requested_voice_route(env, requested_voice_route, capabilities)
    except VoiceRouteError as exc:
        await _fail_voice_route_initialization(exc)
        raise

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
        is_participant_connected=lambda: _participant_identity_connected(
            ctx.room,
            owner_participant_identity,
        ),
        participant_reconnect_grace_s=min(
            max(
                _parse_float_env(
                    "VIVENTIUM_VOICE_PARTICIPANT_RECONNECT_GRACE_S",
                    60.0,
                ),
                0.0,
            ),
            300.0,
        ),
    )

    async def _close_llm_background_continuations(*_args: Any) -> None:
        await llm_impl.close_background_continuations()

    ctx.add_shutdown_callback(_close_llm_background_continuations)

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
    try:
        stt_impl, stt_provider = build_stt_selection(env, vad)
    except VoiceRouteError as exc:
        await _fail_voice_route_initialization(exc)
        raise
    except Exception as exc:
        classified = VoiceRouteError(
            "provider_failure",
            modality="stt",
            provider=_normalize_stt_provider(env.stt_provider),
            reason="initialization failed",
        )
        await _fail_voice_route_initialization(classified)
        raise classified from exc

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
                _raise_route_error(
                    "provider_failure",
                    modality="tts",
                    provider="local_chatterbox_turbo_mlx_8bit",
                    reason=f"is unavailable on platform {sys.platform}",
                )

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
                _raise_route_error(
                    "provider_failure",
                    modality="tts",
                    provider="local_chatterbox_turbo_mlx_8bit",
                    reason=f"runtime is unavailable ({type(exc).__name__})",
                )
            except Exception as exc:
                logger.error(
                    "Local Chatterbox (MLX) initialization failed error=%s",
                    type(exc).__name__,
                    exc_info=True,
                )
                _raise_route_error(
                    "provider_failure",
                    modality="tts",
                    provider="local_chatterbox_turbo_mlx_8bit",
                    reason="initialization failed",
                )
        # === VIVENTIUM END ===

        # TTS (Cartesia, xAI standalone TTS, ElevenLabs, or OpenAI)
        if provider in {"xai", "x_ai", "grok", "xai_grok_voice"}:
            xai_api_key = (env.xai_tts_api_key or os.getenv("XAI_API_KEY", "") or "").strip()
            if not _is_real_api_key(xai_api_key):
                _raise_route_error(
                    "provider_failure",
                    modality="tts",
                    provider="xai",
                    reason="credentials are unavailable",
                )

            if not HAS_XAI_TTS or xai_plugin is None:
                _raise_route_error(
                    "provider_failure",
                    modality="tts",
                    provider="xai",
                    reason="plugin is unavailable",
                )

            _log_selection(
                "Using xAI standalone TTS (voice=%s, language=%s, sample_rate=%s, ws=%s, optimize_streaming_latency=%s)",
                env.xai_voice,
                env.xai_language,
                env.xai_sample_rate,
                env.xai_tts_ws_url,
                env.xai_tts_optimize_streaming_latency,
            )
            logger.info(
                "[VoiceProviderCapability] provider=xai api=tts "
                "capability=xai_speech_tags selected=true legacy_adapter=false"
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
                _raise_route_error(
                    "provider_failure",
                    modality="tts",
                    provider="cartesia",
                    reason="credentials are unavailable",
                )

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
                _raise_route_error(
                    "provider_failure",
                    modality="tts",
                    provider="elevenlabs",
                    reason="credentials are unavailable",
                )

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
                    model=_tts_provider_default_model("elevenlabs"),
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

        if provider == "elevenlabs" and not HAS_ELEVENLABS:
            _raise_route_error(
                "provider_failure",
                modality="tts",
                provider="elevenlabs",
                reason="plugin is unavailable",
            )
        if provider != "openai":
            _raise_route_error(
                "no_route",
                modality="tts",
                provider=provider,
                reason="is not implemented",
            )
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

    try:
        primary_tts_impl, primary_voice_provider = _build_tts(
            env.tts_provider, selection_role="primary"
        )
    except VoiceRouteError as exc:
        await _fail_voice_route_initialization(exc)
        raise
    except Exception as exc:
        classified = VoiceRouteError(
            "provider_failure",
            modality="tts",
            provider=_normalize_voice_provider(env.tts_provider),
            reason="initialization failed",
        )
        await _fail_voice_route_initialization(classified)
        raise classified from exc

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
        try:
            primary_tts_impl.prewarm()
        except Exception as exc:
            classified = VoiceRouteError(
                "provider_failure",
                modality="tts",
                provider=primary_voice_provider,
                reason="prewarm failed",
            )
            await _fail_voice_route_initialization(classified)
            raise classified from exc
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

    async def _maybe_add_elevenlabs_voice_fallback(*, voice_provider: str) -> None:
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

        try:
            fallback_voice_tts, fallback_voice_provider = _build_tts(
                "elevenlabs",
                elevenlabs_voice_id_override=fallback_voice_id,
                selection_role="fallback",
            )
        except Exception:
            await _report_voice_gateway_failure(
                env.librechat_origin,
                auth,
                classification="provider_failure",
                modality="tts",
                provider="elevenlabs",
                phase="initialization",
                fatal=False,
            )
            return
        if fallback_voice_provider != "elevenlabs":
            return
        attempts.append(
            _build_tts_provider_attempt(
                capabilities=capabilities,
                provider=voice_provider,
                tts_impl=fallback_voice_tts,
            )
        )

    await _maybe_add_elevenlabs_voice_fallback(voice_provider=primary_voice_provider)

    if env.tts_provider_fallback and env.tts_provider_fallback != env.tts_provider:
        try:
            fallback_tts_impl, fallback_voice_provider = _build_tts(
                env.tts_provider_fallback,
                selection_role="fallback",
            )
        except Exception:
            await _report_voice_gateway_failure(
                env.librechat_origin,
                auth,
                classification="provider_failure",
                modality="tts",
                provider=_normalize_voice_provider(env.tts_provider_fallback),
                phase="initialization",
                fatal=False,
            )
            fallback_tts_impl = None
            fallback_voice_provider = None
        if (
            fallback_tts_impl is not None
            and fallback_voice_provider
            and fallback_voice_provider != primary_voice_provider
        ):
            attempts.append(
                _build_tts_provider_attempt(
                    capabilities=capabilities,
                    provider=fallback_voice_provider,
                    tts_impl=fallback_tts_impl,
                )
            )
            await _maybe_add_elevenlabs_voice_fallback(voice_provider=fallback_voice_provider)
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
            timestamp = _metric_value(metrics, "timestamp")
            duration = _metric_value(metrics, "duration")
            ttfb = _metric_value(metrics, "ttfb")
            correlation_id = ""
            if timestamp is not None and duration is not None and ttfb is not None:
                correlation_id = llm_impl.record_next_trace_hop(
                    "tts_first_byte",
                    (timestamp - duration + max(ttfb, 0.0)) * 1000.0,
                )
            logger.info(
                "[VoiceLatency] tts_provider_metrics callSessionId=%s correlationId=%s provider=%s label=%s request_id=%s ttfb_ms=%s duration_ms=%s audio_duration_ms=%s streamed=%s cancelled=%s characters=%s",
                call_session_id,
                correlation_id or "unmatched",
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
    runtime_failure_report_tasks: set[asyncio.Task[Any]] = set()
    runtime_failure_reported_at: dict[tuple[str, str], float] = {}

    def _schedule_runtime_provider_failure_report(event: Any) -> None:
        classified = _classify_runtime_voice_provider_failure(
            event,
            stt_impl=stt_impl,
            tts_impl=tts_impl,
            stt_provider=stt_provider,
            tts_provider=current_tts_provider,
        )
        if classified is None:
            return
        modality, provider = classified
        now = time.monotonic()
        report_key = (modality, provider)
        if now - runtime_failure_reported_at.get(report_key, -math.inf) < 5.0:
            return
        runtime_failure_reported_at[report_key] = now
        task = asyncio.create_task(
            _report_voice_gateway_failure(
                env.librechat_origin,
                auth,
                classification="provider_failure",
                modality=modality,
                provider=provider,
                phase="runtime",
                fatal=False,
            )
        )
        runtime_failure_report_tasks.add(task)

        def _consume_report_result(completed: asyncio.Task[Any]) -> None:
            runtime_failure_report_tasks.discard(completed)
            if completed.cancelled():
                return
            try:
                completed.exception()
            except Exception:
                logger.debug(
                    "[VoiceProvider] runtime failure report task cleanup failed",
                    exc_info=True,
                )

        task.add_done_callback(_consume_report_result)
        logger.warning(
            "[VoiceProvider] runtime_failure callSessionId=%s modality=%s provider=%s callContinues=true",
            call_session_id,
            modality,
            provider,
        )

    async def _drain_runtime_failure_reports(*_args: Any) -> None:
        if runtime_failure_report_tasks:
            await asyncio.gather(*tuple(runtime_failure_report_tasks), return_exceptions=True)

    ctx.add_shutdown_callback(_drain_runtime_failure_reports)

    followup_scheduler = CortexFollowupScheduler(
        origin=env.librechat_origin,
        auth=auth,
        session=session,
        timeout_s=env.voice_followup_timeout_s,
        interval_s=env.voice_followup_interval_s,
        grace_s=env.voice_followup_grace_s,
        glasshive_timeout_s=env.voice_glasshive_timeout_s,
    )
    followup_scheduler.set_mode("listen_only")
    llm_impl.set_followup_handler(followup_scheduler.schedule)

    async def _close_followup_scheduler(*_args: Any) -> None:
        await followup_scheduler.close()

    ctx.add_shutdown_callback(_close_followup_scheduler)
    progress_speech_handles: set[Any] = set()

    def _stop_active_progress_speech() -> None:
        _interrupt_livekit_speech_handles(progress_speech_handles)

    def _speak_task_progress(task_id: str, text: str) -> None:
        cleaned = sanitize_voice_followup_text(text)
        if not cleaned:
            return
        try:
            handle = session.say(
                cleaned,
                allow_interruptions=True,
                add_to_chat_ctx=False,
            )
            if handle is not None:
                progress_speech_handles.add(handle)
                add_done_callback = getattr(handle, "add_done_callback", None)
                if callable(add_done_callback):
                    add_done_callback(
                        lambda completed: progress_speech_handles.discard(completed)
                    )
            logger.info(
                "[VoiceTask] progress_spoken callSessionId=%s taskId=%s chars=%s interruptible=true",
                call_session_id,
                task_id,
                len(cleaned),
            )
        except Exception as exc:
            logger.warning(
                "[VoiceTask] progress_speak_failed callSessionId=%s taskId=%s error=%s callContinues=true",
                call_session_id,
                task_id,
                type(exc).__name__,
            )

    progress_controller = AsyncVoiceProgressController(
        machine=VoiceProgressStateMachine(enabled=False),
        speak=_speak_task_progress,
        clock=time.monotonic,
        stop_active_speech=_stop_active_progress_speech,
        initial_mode="listen_only",
    )

    async def _relay_and_track_task_event(task_event: dict[str, Any]) -> None:
        progress_controller.on_task_event(task_event)
        await _publish_livekit_task_event(
            ctx.room.local_participant,
            task_event,
            owner_participant_identity=owner_participant_identity,
        )

    llm_impl.set_task_event_handler(_relay_and_track_task_event)
    llm_impl.set_model_output_handler(progress_controller.on_model_output)

    def _on_task_cancel_accepted(task_id: str, _result: dict[str, Any]) -> None:
        # The backend task remains authoritative; this is the local suppression barrier.
        _apply_task_cancel_suppression(
            task_id,
            progress_controller=progress_controller,
            followup_scheduler=followup_scheduler,
            session=session,
        )

    llm_impl.set_task_cancel_handler(_on_task_cancel_accepted)

    segment_sequencer = CallScopedSegmentSequencer()
    owner_speaker_context = _linked_participant_speaker_context(
        ctx.room, owner_participant_identity
    )
    speaker_tracker = SpeakerSegmentTracker(
        call_session_id=call_session_id,
        segment_sequencer=segment_sequencer,
        initial_shared_microphone=shared_microphone_state_applies_to_track(
            speaker_session_state,
            owner_speaker_context.get("track_sid", ""),
            owner_speaker_context.get("participant_identity", ""),
        ),
        **owner_speaker_context,
    )

    async def _persist_ambient_speaker_session_state(
        state: dict[str, Any]
    ) -> None:
        await llm_impl.post_speaker_segment_revisions([], session_state=state)

    async def _persist_ambient_turn(payload: dict[str, Any]) -> None:
        try:
            await llm_impl.post_ambient_transcript(payload)
        except Exception as exc:
            logger.warning(
                "[VoiceSpeaker] ambient_persist_failed callSessionId=%s segments=%s error=%s",
                call_session_id,
                len(payload.get("segments") or []),
                type(exc).__name__,
            )

    async def _persist_suppressed_owner_turn(
        context: dict[str, Any], mode: str
    ) -> None:
        segments = context.get("speakerSegments")
        revisions = context.get("speakerSegmentRevisions")
        bounded_segments = segments if isinstance(segments, list) else []
        bounded_revisions = revisions if isinstance(revisions, list) else []
        if bounded_revisions:
            await llm_impl.post_speaker_segment_revisions(bounded_revisions)
        if not bounded_segments:
            return
        first_turn_id = str(bounded_segments[0].get("turnId") or "")
        await llm_impl.post_ambient_transcript(
            {
                "version": 1,
                "callSessionId": call_session_id,
                "mode": "listen_only" if mode == "listen_only" else call_mode,
                "ingressKind": (
                    "listen_only_owner"
                    if mode == "listen_only"
                    else "ambient_participant"
                ),
                **({"turnId": first_turn_id} if first_turn_id else {}),
                "segments": bounded_segments,
            }
        )
        logger.info(
            "[VoiceMode] suppressed_owner_turn_persisted callSessionId=%s mode=%s segments=%s revisions=%s llmDispatched=false",
            call_session_id,
            mode,
            len(bounded_segments),
            len(bounded_revisions),
        )

    multi_track_ingress = MultiTrackIngressCoordinator(
        call_session_id=call_session_id,
        owner_participant_identity=owner_participant_identity,
        mode=call_mode,
        stt_impl=stt_impl,
        audio_stream_factory=lambda track: rtc.AudioStream(track),
        on_segment_changes=lambda changes: _publish_livekit_speaker_segments(
            ctx.room.local_participant,
            changes,
            owner_participant_identity=owner_participant_identity,
        ),
        on_ambient_turn=_persist_ambient_turn,
        on_session_state_change=_persist_ambient_speaker_session_state,
        owner_present=lambda: _participant_identity_connected(
            ctx.room, owner_participant_identity
        ),
        initial_speaker_session_state=speaker_session_state,
        segment_sequencer=segment_sequencer,
    )

    async def _poll_spoken_progress() -> None:
        while True:
            await asyncio.sleep(0.1)
            progress_controller.poll()

    latest_pushed_mode_revision = [int(claimed_call_state["revision"])]

    def _suspend_for_task_stream_uncertainty() -> None:
        _suspend_all_call_speech_until_authoritative(
            progress_controller=progress_controller,
            followup_scheduler=followup_scheduler,
            session=session,
            authoritative_mode_state=authoritative_mode_state,
        )

    def _apply_task_stream_call_state(state: dict[str, Any]) -> None:
        nonlocal call_mode
        call_mode = str(state["mode"])
        latest_pushed_mode_revision[0] = max(
            latest_pushed_mode_revision[0],
            int(state["revision"]),
        )
        authoritative_mode_state.apply(call_mode)
        _apply_authoritative_call_mode_to_speech_planes(
            call_mode,
            progress_controller=progress_controller,
            ambient_ingress=multi_track_ingress,
            followup_scheduler=followup_scheduler,
            session=session,
        )

    task_stream_authority = CallTaskStreamSpeechAuthority(
        call_session_id=call_session_id,
        fetch_call_state=llm_impl.get_call_state,
        suspend=_suspend_for_task_stream_uncertainty,
        apply_state=_apply_task_stream_call_state,
    )
    llm_impl.set_call_task_event_stream_health_handler(
        task_stream_authority.on_stream_health
    )

    @ctx.room.on("data_received")
    def _on_authoritative_call_state_packet(packet: Any) -> None:
        if str(getattr(packet, "topic", "") or "") != "viventium.call.state.v1":
            return
        if not voice_session_ready[0] or not task_stream_authority.authoritative:
            _suspend_all_call_speech_until_authoritative(
                progress_controller=progress_controller,
                followup_scheduler=followup_scheduler,
                session=session,
                authoritative_mode_state=authoritative_mode_state,
            )
            logger.warning(
                "[VoiceMode] push_rejected callSessionId=%s reason=response_plane_not_authoritative speechSuspended=true",
                call_session_id,
            )
            return
        participant = getattr(packet, "participant", None)
        source_identity = str(getattr(participant, "identity", "") or "").strip()
        if source_identity != owner_participant_identity:
            logger.warning(
                "[VoiceMode] push_rejected callSessionId=%s reason=non_owner_source",
                call_session_id,
            )
            return
        raw_data = getattr(packet, "data", b"")
        if not isinstance(raw_data, (bytes, bytearray)) or len(raw_data) > 16_000:
            _suspend_all_call_speech_until_authoritative(
                progress_controller=progress_controller,
                followup_scheduler=followup_scheduler,
                session=session,
                authoritative_mode_state=authoritative_mode_state,
            )
            return
        try:
            payload = json.loads(bytes(raw_data).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        packet_revision = payload.get("revision") if isinstance(payload, dict) else None
        if (
            isinstance(packet_revision, int)
            and not isinstance(packet_revision, bool)
            and packet_revision <= latest_pushed_mode_revision[0]
        ):
            logger.info(
                "[VoiceMode] push_ignored callSessionId=%s reason=stale_revision revision=%s latest=%s",
                call_session_id,
                packet_revision,
                latest_pushed_mode_revision[0],
            )
            return
        parsed = parse_authoritative_call_state_packet(
            payload,
            expected_call_session_id=call_session_id,
            expected_owner_identity=owner_participant_identity,
            source_identity=source_identity,
            latest_revision=latest_pushed_mode_revision[0],
        )
        if parsed is None:
            _suspend_all_call_speech_until_authoritative(
                progress_controller=progress_controller,
                followup_scheduler=followup_scheduler,
                session=session,
                authoritative_mode_state=authoritative_mode_state,
            )
            logger.warning(
                "[VoiceMode] push_rejected callSessionId=%s reason=invalid_or_stale_contract speechSuspended=true",
                call_session_id,
            )
            return
        mode, status, revision = parsed
        latest_pushed_mode_revision[0] = revision
        if status in {"failed", "ended"}:
            _suspend_all_call_speech_until_authoritative(
                progress_controller=progress_controller,
                followup_scheduler=followup_scheduler,
                session=session,
                authoritative_mode_state=authoritative_mode_state,
            )
            logger.info(
                "[VoiceMode] push_terminal callSessionId=%s status=%s revision=%s",
                call_session_id,
                status,
                revision,
            )
            return
        authoritative_mode_state.apply(mode)
        previous_mode = progress_controller.mode
        _apply_authoritative_call_mode_to_speech_planes(
            mode,
            progress_controller=progress_controller,
            ambient_ingress=multi_track_ingress,
            followup_scheduler=followup_scheduler,
            session=session,
        )
        logger.info(
            "[VoiceMode] push_applied callSessionId=%s previous=%s current=%s revision=%s reconnect=false",
            call_session_id,
            previous_mode,
            mode,
            revision,
        )

    async def _sync_authoritative_mode() -> None:
        def _on_mode_transition(previous_mode: str, current_mode: str) -> None:
            followup_scheduler.set_mode(current_mode)
            if previous_mode != "listen_only" and current_mode == "listen_only":
                _interrupt_agent_session_speech(session)

        def _on_state_uncertain() -> None:
            _suspend_all_call_speech_until_authoritative(
                progress_controller=progress_controller,
                followup_scheduler=followup_scheduler,
                session=session,
                authoritative_mode_state=authoritative_mode_state,
            )

        def _on_terminal_state(status: str) -> None:
            _suspend_all_call_speech_until_authoritative(
                progress_controller=progress_controller,
                followup_scheduler=followup_scheduler,
                session=session,
                authoritative_mode_state=authoritative_mode_state,
            )
            logger.info(
                "[VoiceMode] terminal_state callSessionId=%s status=%s backendTaskPreserved=true",
                call_session_id,
                status,
            )
            shutdown = getattr(ctx, "shutdown", None)
            if callable(shutdown):
                result = shutdown()
                if inspect.isawaitable(result):
                    shutdown_task = asyncio.create_task(result)
                    terminal_shutdown_tasks.add(shutdown_task)

                    def _consume_terminal_shutdown(completed: asyncio.Task[Any]) -> None:
                        terminal_shutdown_tasks.discard(completed)
                        if completed.cancelled():
                            return
                        try:
                            completed.exception()
                        except Exception:
                            logger.debug(
                                "[VoiceMode] terminal shutdown cleanup failed",
                                exc_info=True,
                            )

                    shutdown_task.add_done_callback(_consume_terminal_shutdown)

        async def _reconcile_once() -> None:
            if not task_stream_authority.authoritative:
                restored = await task_stream_authority.reconcile()
                if restored:
                    logger.info(
                        "[VoiceMode] task_stream_snapshot_restored callSessionId=%s speechAuthoritative=true",
                        call_session_id,
                    )
                else:
                    _on_state_uncertain()
                    logger.warning(
                        "[VoiceMode] progress_suspended callSessionId=%s reason=task_stream_unavailable audioConnected=true",
                        call_session_id,
                    )
                return
            previous_mode = progress_controller.mode
            authoritative_mode = await sync_authoritative_call_mode_once(
                fetch_mode=llm_impl.get_call_state,
                progress_controller=progress_controller,
                set_ambient_mode=multi_track_ingress.set_mode,
                on_mode_transition=_on_mode_transition,
                on_state_uncertain=_on_state_uncertain,
                on_terminal_state=_on_terminal_state,
            )
            if authoritative_mode is None:
                logger.warning(
                    "[VoiceMode] progress_suspended callSessionId=%s reason=authoritative_state_unavailable audioConnected=true",
                    call_session_id,
                )
            else:
                authoritative_mode_state.apply(authoritative_mode)
                # Also clears a prior fail-safe suspension when the mode value is unchanged.
                followup_scheduler.set_mode(authoritative_mode)
                if authoritative_mode != previous_mode:
                    logger.info(
                        "[VoiceMode] mode_changed callSessionId=%s previous=%s current=%s reconnect=false",
                        call_session_id,
                        previous_mode,
                        authoritative_mode,
                    )

        await run_authoritative_mode_reconciliation(
            reconcile_once=_reconcile_once,
            interval_s=_parse_float_env(
                "VIVENTIUM_VOICE_MODE_RECONCILIATION_S",
                5.0,
            ),
            clock=asyncio.get_running_loop().time,
            sleep=asyncio.sleep,
        )

    progress_poll_task: Optional[asyncio.Task[None]] = None
    mode_sync_task: Optional[asyncio.Task[None]] = None
    terminal_shutdown_tasks: set[asyncio.Task[Any]] = set()

    async def _stop_progress_and_mode_sync(*_args: Any) -> None:
        tasks = [
            task
            for task in (progress_poll_task, mode_sync_task)
            if task is not None
        ]
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        _stop_active_progress_speech()

    ctx.add_shutdown_callback(_stop_progress_and_mode_sync)

    def _register_ambient_track(track: Any, publication: Any, participant: Any) -> None:
        if not voice_session_ready[0]:
            return
        if multi_track_ingress.track_joined(participant, track, publication):
            logger.info(
                "[VoiceSpeaker] ambient_track_started callSessionId=%s participantBound=true trackSid=%s authority=soft_evidence",
                call_session_id,
                getattr(publication, "sid", "") or getattr(track, "sid", ""),
            )

    @ctx.room.on("track_subscribed")
    def _on_ambient_track_subscribed(track: Any, publication: Any, participant: Any) -> None:
        _register_ambient_track(track, publication, participant)

    @ctx.room.on("track_unsubscribed")
    def _on_ambient_track_unsubscribed(track: Any, publication: Any, participant: Any) -> None:
        _ = participant
        track_sid = str(
            getattr(publication, "sid", "") or getattr(track, "sid", "") or ""
        )
        if track_sid:
            asyncio.get_running_loop().create_task(
                multi_track_ingress.track_left(track_sid)
            )

    def _register_existing_ambient_tracks() -> None:
        for participant in getattr(ctx.room, "remote_participants", {}).values():
            for publication in getattr(participant, "track_publications", {}).values():
                track = getattr(publication, "track", None)
                if track is not None:
                    _register_ambient_track(track, publication, participant)

    async def _close_multi_track_ingress(*_args: Any) -> None:
        await multi_track_ingress.close()

    ctx.add_shutdown_callback(_close_multi_track_ingress)

    async def _on_owner_interim_speaker_changes(
        changes: list[dict[str, Any]],
    ) -> None:
        late_revisions = [
            item for item in changes if item.get("turnId") != speaker_tracker.turn_id
        ]
        session_states = speaker_tracker.pop_session_state_changes()
        await _publish_livekit_speaker_segments(
            ctx.room.local_participant,
            changes,
            owner_participant_identity=owner_participant_identity,
        )
        if late_revisions or session_states:
            llm_impl.queue_speaker_segment_revisions(
                late_revisions,
                session_state=session_states[-1] if session_states else None,
            )

    async def _on_finalized_owner_speaker_context(
        context: dict[str, Any],
    ) -> None:
        segments = context.get("speakerSegments")
        if not isinstance(segments, list):
            segments = []
        overlap_revisions = multi_track_ingress.apply_call_wide_overlap(segments)
        revisions = context.get("speakerSegmentRevisions")
        if not isinstance(revisions, list):
            revisions = []
        revisions.extend(overlap_revisions)
        context["speakerSegmentRevisions"] = revisions
        session_states = speaker_tracker.pop_session_state_changes()
        if revisions or session_states:
            await llm_impl.post_speaker_segment_revisions(
                revisions,
                session_state=session_states[-1] if session_states else None,
            )
        if segments or overlap_revisions:
            await _publish_livekit_speaker_segments(
                ctx.room.local_participant,
                [*segments, *overlap_revisions],
                owner_participant_identity=owner_participant_identity,
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
        if str(getattr(event, "new_state", "") or "") == "speaking":
            created_at = float(getattr(event, "created_at", 0.0) or 0.0)
            correlation_id = llm_impl.record_next_trace_hop(
                "audio_output",
                (created_at if created_at > 0 else time.time()) * 1000.0,
            )
            task_id = llm_impl.task_id_for_trace(correlation_id)
            if task_id:
                progress_controller.on_audible_ack(task_id)
        logger.info(
            "[voice-gateway] agent_state_changed callSessionId=%s old=%s new=%s",
            call_session_id,
            getattr(event, "old_state", ""),
            getattr(event, "new_state", ""),
        )

    @session.on("error")
    def _on_voice_provider_error(event: Any) -> None:
        _schedule_runtime_provider_failure_report(event)

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
                "[VoiceLatency] assistant_turn_metrics callSessionId=%s correlationId=%s provider=%s llm_node_ttft_ms=%s tts_node_ttfb_ms=%s e2e_latency_ms=%s event_lag_ms=%.3f",
                call_session_id,
                llm_impl.current_trace_id,
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

    agent = ViventiumVoiceAgent(
        instructions=(
            "You are the Viventium Voice Gateway. "
            "You must speak the LibreChat agent's responses naturally and concisely."
        ),
        llm=llm_impl,
        stt=stt_impl,
        tts=tts_impl,
        speaker_tracker=speaker_tracker,
        authoritative_mode_state=authoritative_mode_state,
        persist_suppressed_turn=_persist_suppressed_owner_turn,
        on_finalized_speaker_context=_on_finalized_owner_speaker_context,
        on_interim_speaker_changes=_on_owner_interim_speaker_changes,
        speaker_timeline_offset=multi_track_ingress.call_timeline_offset_s,
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
    try:
        await session.start(
            agent=agent,
            room=ctx.room,
            room_options=_build_room_options(
                sync_transcription=sync_transcription,
                participant_identity=(
                    owner_participant_identity or "__viventium_unbound_owner__"
                ),
            ),
        )
    except Exception:
        _reported, released = (
            await _report_voice_gateway_initialization_failure_and_abandon(
                env.librechat_origin,
                auth,
            )
        )
        if released:
            unready_claim_active[0] = False
            abandon_attempted[0] = True
        else:
            abandon_attempted[0] = False
        raise
    call_task_event_stream, ready_state = await _establish_voice_response_plane(
        llm_impl=llm_impl,
        mark_ready=lambda: _mark_voice_session_ready(env.librechat_origin, auth),
        timeout_s=min(
            max(
                _parse_float_env(
                    "VIVENTIUM_VOICE_TASK_STREAM_READY_TIMEOUT_S",
                    5.0,
                ),
                0.25,
            ),
            15.0,
        ),
    )
    if call_task_event_stream is None:
        _suspend_for_task_stream_uncertainty()
        _reported, released = (
            await _report_voice_gateway_initialization_failure_and_abandon(
                env.librechat_origin,
                auth,
            )
        )
        if released:
            unready_claim_active[0] = False
            abandon_attempted[0] = True
        else:
            abandon_attempted[0] = False
        shutdown = getattr(ctx, "shutdown", None)
        if callable(shutdown):
            result = shutdown()
            if inspect.isawaitable(result):
                await result
        raise RuntimeError("authoritative call task stream handshake failed")
    if ready_state is None:
        _suspend_all_call_speech_until_authoritative(
            progress_controller=progress_controller,
            followup_scheduler=followup_scheduler,
            session=session,
            authoritative_mode_state=authoritative_mode_state,
        )
        await _abandon_unready_claim("gateway_initialization_failed")
        shutdown = getattr(ctx, "shutdown", None)
        if callable(shutdown):
            result = shutdown()
            if inspect.isawaitable(result):
                await result
        raise RuntimeError("voice readiness handshake failed")
    if not task_stream_authority.mark_session_ready(ready_state):
        _suspend_for_task_stream_uncertainty()
        await _abandon_unready_claim("gateway_initialization_failed")
        shutdown = getattr(ctx, "shutdown", None)
        if callable(shutdown):
            result = shutdown()
            if inspect.isawaitable(result):
                await result
        raise RuntimeError("authoritative task stream lost before voice readiness")
    voice_session_ready[0] = True
    progress_poll_task = asyncio.create_task(_poll_spoken_progress())
    mode_sync_task = asyncio.create_task(_sync_authoritative_mode())
    _register_existing_ambient_tracks()
    unready_claim_active[0] = False
    logger.info(
        "[voice-gateway] Voice session ready callSessionId=%s mode=%s status=%s revision=%s",
        call_session_id,
        call_mode,
        ready_state["status"],
        ready_state["revision"],
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
        # Explicit AgentDispatchClient dispatches are room jobs. Owner authority remains bound
        # separately to the canonical participant identity returned by the signed backend claim.
        worker_type=WorkerType.ROOM,
        initialize_process_timeout=initialize_process_timeout_s,
        num_idle_processes=idle_processes,
        load_threshold=load_threshold,
        job_memory_warn_mb=float(getattr(env, "voice_job_memory_warn_mb", 500.0)),
        job_memory_limit_mb=float(getattr(env, "voice_job_memory_limit_mb", 0.0)),
    )
    cli.run_app(worker_opts)


if __name__ == "__main__":
    run()
