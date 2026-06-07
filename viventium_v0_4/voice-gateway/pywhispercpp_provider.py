# === VIVENTIUM START ===
# Feature: Local whisper.cpp STT provider with VAD stream adapter (v1 parity)
# Added: 2026-01-11
# === VIVENTIUM END ===

"""PyWhisperCpp STT Provider - Fast, reliable C++ Whisper implementation."""

from __future__ import annotations

import audioop
import asyncio
import hashlib
import importlib.metadata
import logging
import os
import platform
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import AsyncIterable
from pathlib import Path
from typing import Any, List, Optional

_SHARED_PATH = Path(__file__).resolve().parent.parent / "shared"
if str(_SHARED_PATH) not in sys.path:
    sys.path.insert(0, str(_SHARED_PATH))

from whisper_cpp_models import (
    MODEL_FILENAMES,
    MODEL_SHA1,
    default_model_name as default_whisper_cpp_model_name,
)

import numpy as np
from livekit.agents.stt import (
    RecognizeStream,
    STT,
    STTCapabilities,
    SpeechData,
    SpeechEvent,
    SpeechEventType,
)
from livekit.agents.stt.stream_adapter import (
    DEFAULT_STREAM_ADAPTER_API_CONNECT_OPTIONS,
    StreamAdapter,
)
from livekit.agents.types import (
    DEFAULT_API_CONNECT_OPTIONS,
    APIConnectOptions,
    NOT_GIVEN,
    NotGivenOr,
)
from livekit.agents import utils as lk_utils
from livekit.agents.utils import AudioBuffer
from livekit.agents.vad import VAD as VADBase, VADEventType
from livekit.rtc.audio_frame import AudioFrame
from silero_vad_config import get_silero_vad_kwargs

try:
    from pywhispercpp.model import Model
except ImportError as exc:
    raise RuntimeError(
        "PyWhisperCpp STT selected but the 'pywhispercpp' package is not installed. "
        "Install it via 'pip install pywhispercpp'."
    ) from exc

_logger = logging.getLogger(__name__)
_MODEL_CACHE: dict[str, Model] = {}
_LOCAL_WHISPER_VAD_MIN_SPEECH_S = "0.35"
_LOCAL_WHISPER_VAD_MIN_SILENCE_S = "0.5"
_MODEL_WARMUP_DONE: set[str] = set()

# Common hallucination phrases Whisper outputs on silence/noise
# Based on research: https://github.com/ggml-org/whisper.cpp/issues/1724
HALLUCINATION_PHRASES = {
    "thank you",
    "thanks",
    "okay",
    "ok",
    "bye",
    "goodbye",
    "you",
    "thank you.",
    "thanks.",
    "okay.",
    "- thank you",
    "- thank you.",
    "- okay",
    "- okay.",
}


def _local_whisper_vad_env() -> dict[str, str]:
    source = dict(os.environ)
    if not (source.get("VIVENTIUM_STT_VAD_MIN_SPEECH") or "").strip():
        source["VIVENTIUM_STT_VAD_MIN_SPEECH"] = _LOCAL_WHISPER_VAD_MIN_SPEECH_S
    if not (source.get("VIVENTIUM_STT_VAD_MIN_SILENCE") or "").strip():
        source["VIVENTIUM_STT_VAD_MIN_SILENCE"] = _LOCAL_WHISPER_VAD_MIN_SILENCE_S
    return source


def _bool_env(name: str, fallback: bool = False) -> bool:
    raw = (os.getenv(name, "") or "").strip().lower()
    if not raw:
        return fallback
    return raw in {"1", "true", "yes", "y", "on"}


def _latency_logging_enabled() -> bool:
    return _bool_env("VIVENTIUM_VOICE_LOG_LATENCY", False)


def _ms_since(start_ns: int, end_ns: Optional[int] = None) -> float:
    return ((end_ns or time.perf_counter_ns()) - start_ns) / 1_000_000.0


def _float_env(name: str, fallback: float) -> float:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return fallback
    try:
        return float(raw)
    except ValueError:
        return fallback


def _int_env(name: str, fallback: int) -> int:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return fallback
    try:
        return int(raw)
    except ValueError:
        return fallback


def _audio_ctx_for_transcribe(
    model_name: str,
    *,
    audio_duration_s: Optional[float] = None,
) -> int:
    configured = (os.getenv("VIVENTIUM_STT_AUDIO_CTX", "") or "").strip()
    if configured:
        try:
            return max(0, int(configured))
        except ValueError:
            return 0

    if model_name != "large-v3-turbo":
        return 0

    reduced_ctx_max_audio_s = max(
        0.0,
        _float_env("VIVENTIUM_STT_REDUCED_AUDIO_CTX_MAX_AUDIO_S", 12.0),
    )
    if audio_duration_s is not None and audio_duration_s > reduced_ctx_max_audio_s:
        return 0
    return 768


def _transcribe_kwargs(
    language: str,
    *,
    model_name: Optional[str] = None,
    audio_duration_s: Optional[float] = None,
) -> dict[str, object]:
    resolved_model = _default_model_name(model_name)
    audio_ctx = _audio_ctx_for_transcribe(
        resolved_model,
        audio_duration_s=audio_duration_s,
    )
    params: dict[str, object] = {
        "language": language,
        "no_speech_thold": 0.7,
        "logprob_thold": -0.8,
        "suppress_blank": True,
        "temperature": 0.0,
        "entropy_thold": 2.2,
        "no_context": _bool_env("VIVENTIUM_STT_NO_CONTEXT", True),
        "single_segment": _bool_env("VIVENTIUM_STT_SINGLE_SEGMENT", True),
    }
    if audio_ctx > 0:
        params["audio_ctx"] = audio_ctx

    # === VIVENTIUM START ===
    # Feature: Bounded temperature-fallback for real-time STT tail latency.
    # Why: whisper.cpp retries the whole decode at higher temperatures (step = temperature_inc,
    #   default 0.2) whenever a segment fails compression/logprob/entropy thresholds. On hard or
    #   noisy audio this re-runs the decoder up to ~5x (0.0,0.2,0.4,0.6,0.8,1.0), which is the main
    #   source of worst-case latency spikes on the voice hot path. Setting temperature_inc to 0
    #   disables the fallback loop (single greedy pass). This is OFF by default: per Key Principles 0
    #   (outcome = Quality + Performance) we only ship a behavior change once the local STT accuracy
    #   harness (tests/stt_local_accuracy_bench.py) proves no WER regression on the degraded-audio
    #   suite that actually triggers the fallback. Tune via VIVENTIUM_STT_TEMPERATURE_INC
    #   (float, e.g. "0" to disable retries, "0.2" = whisper.cpp default); unset = library default.
    # Added: 2026-05-30
    # === VIVENTIUM END ===
    temperature_inc_raw = (os.getenv("VIVENTIUM_STT_TEMPERATURE_INC", "") or "").strip()
    if temperature_inc_raw:
        try:
            params["temperature_inc"] = max(0.0, float(temperature_inc_raw))
        except ValueError:
            pass
    return params


def _default_model_name(configured_model: Optional[str] = None) -> str:
    configured = (configured_model or os.getenv("VIVENTIUM_STT_MODEL", "")).strip()
    if configured:
        return configured
    return default_whisper_cpp_model_name()


def _model_cache_dir() -> Path:
    configured = (os.getenv("VIVENTIUM_WHISPER_CACHE_DIR") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.home() / ".cache" / "whisper"


def _model_filename(model_name: str) -> str:
    filename = MODEL_FILENAMES.get(model_name)
    if not filename:
        known = ", ".join(sorted(MODEL_FILENAMES))
        raise ValueError(f"Unsupported local whisper.cpp model '{model_name}'. Known models: {known}")
    return filename


def _sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_timeout_s() -> float:
    try:
        return max(
            10.0,
            float((os.getenv("VIVENTIUM_LOCAL_WHISPER_DOWNLOAD_TIMEOUT_S") or "").strip()),
        )
    except Exception:
        return 300.0


def _pywhispercpp_runtime_fingerprint() -> str:
    try:
        version = importlib.metadata.version("pywhispercpp")
    except Exception:
        version = "unknown"
    return f"pywhispercpp={version};python={sys.version_info.major}.{sys.version_info.minor};platform={platform.platform()}"


def _validation_stamp_path(model_path: Path) -> Path:
    return model_path.with_name(f"{model_path.name}.viventium-ok")


def _validation_stamp_matches(model_path: Path, expected_sha1: Optional[str]) -> bool:
    stamp_path = _validation_stamp_path(model_path)
    if not expected_sha1 or not stamp_path.exists():
        return False
    try:
        expected = {
            "sha1": expected_sha1,
            "runtime": _pywhispercpp_runtime_fingerprint(),
        }
        current = dict(
            line.split("=", 1)
            for line in stamp_path.read_text(encoding="utf-8").splitlines()
            if "=" in line
        )
        return current == expected
    except Exception:
        return False


def _write_validation_stamp(model_path: Path, expected_sha1: Optional[str]) -> None:
    if not expected_sha1:
        return
    stamp_path = _validation_stamp_path(model_path)
    stamp_path.write_text(
        f"sha1={expected_sha1}\nruntime={_pywhispercpp_runtime_fingerprint()}\n",
        encoding="utf-8",
    )


def _clear_validation_stamp(model_path: Path) -> None:
    _validation_stamp_path(model_path).unlink(missing_ok=True)


def _download_model_file(filename: str, model_path: Path, expected_sha1: Optional[str]) -> None:
    model_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = model_path.with_name(f".{model_path.name}.{os.getpid()}.download")
    tmp_path.unlink(missing_ok=True)
    url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{filename}"
    _logger.info("Downloading whisper.cpp model %s to %s", filename, model_path)
    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(_download_timeout_s())
    try:
        urllib.request.urlretrieve(url, tmp_path)
        if expected_sha1:
            actual_sha1 = _sha1_file(tmp_path)
            if actual_sha1 != expected_sha1:
                raise RuntimeError(
                    f"Downloaded whisper.cpp model {filename} failed checksum: "
                    f"expected {expected_sha1}, got {actual_sha1}"
                )
        tmp_path.replace(model_path)
        _logger.info("Downloaded whisper.cpp model %s successfully", filename)
    finally:
        socket.setdefaulttimeout(previous_timeout)
        tmp_path.unlink(missing_ok=True)


def _resolve_model_path(model_name: str) -> tuple[Path, bool, Optional[str], str]:
    configured_path = (os.getenv("VIVENTIUM_STT_MODEL_PATH") or "").strip()
    if configured_path:
        path = Path(configured_path).expanduser().resolve()
        _logger.warning(
            "VIVENTIUM_STT_MODEL_PATH is set; Viventium will load-validate this explicit model path but cannot "
            "checksum self-heal or redownload it because it is outside the managed whisper.cpp cache."
        )
        return path, False, None, path.name

    filename = _model_filename(model_name)
    return _model_cache_dir() / filename, True, MODEL_SHA1.get(filename), filename


def ensure_model_file(model_name: Optional[str] = None, *, force_download: bool = False) -> Path:
    resolved_model = _default_model_name(model_name)
    model_path, owned_cache_file, expected_sha1, filename = _resolve_model_path(resolved_model)

    if not owned_cache_file:
        if not model_path.exists():
            raise FileNotFoundError(f"Configured local whisper.cpp model path does not exist: {model_path}")
        return model_path

    should_download = force_download or not model_path.exists()
    if model_path.exists() and expected_sha1:
        actual_sha1 = _sha1_file(model_path)
        if actual_sha1 != expected_sha1:
            _logger.warning(
                "Cached whisper.cpp model %s failed checksum: expected %s, got %s; redownloading exact selected model.",
                filename,
                expected_sha1,
                actual_sha1,
            )
            should_download = True
            _clear_validation_stamp(model_path)

    if should_download:
        _download_model_file(filename, model_path, expected_sha1)
        _clear_validation_stamp(model_path)

    return model_path


def _model_load_healthcheck_timeout_s() -> float:
    try:
        return max(
            10.0,
            float((os.getenv("VIVENTIUM_LOCAL_WHISPER_HEALTHCHECK_TIMEOUT_S") or "").strip()),
        )
    except Exception:
        return 120.0


def _validate_model_load_in_subprocess(model_path: Path, n_threads: int) -> tuple[bool, str]:
    code = """
import sys
from pywhispercpp.model import Model
Model(sys.argv[1], n_threads=int(sys.argv[2]), print_realtime=False, print_progress=False)
print("VIVENTIUM_MODEL_LOAD_OK")
"""
    try:
        completed = subprocess.run(
            [sys.executable, "-c", code, str(model_path), str(n_threads)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=_model_load_healthcheck_timeout_s(),
            check=False,
        )
        output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        return completed.returncode == 0, output[-4000:]
    except subprocess.TimeoutExpired as exc:
        output = "\n".join(
            part
            for part in (
                exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout,
                exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr,
            )
            if part
        )
        return False, f"timed out after {_model_load_healthcheck_timeout_s()}s\n{output[-4000:]}"


def _validation_enabled() -> bool:
    return (os.getenv("VIVENTIUM_LOCAL_WHISPER_VALIDATE_LOAD", "1") or "").strip().lower() not in {
        "0",
        "false",
        "off",
        "no",
    }


def ensure_model_ready(model_name: Optional[str] = None, *, validate_load: Optional[bool] = None) -> Path:
    resolved_model = _default_model_name(model_name)
    model_path, owned_cache_file, expected_sha1, filename = _resolve_model_path(resolved_model)
    default_threads = "2" if platform.machine().lower() == "x86_64" else "8"
    n_threads = int(os.getenv("VIVENTIUM_STT_THREADS", default_threads))

    model_path = ensure_model_file(resolved_model)
    should_validate = _validation_enabled() if validate_load is None else validate_load
    if not should_validate:
        _logger.warning(
            "VIVENTIUM_LOCAL_WHISPER_VALIDATE_LOAD is disabled; Viventium will checksum the selected "
            "whisper.cpp model but skip isolated native load validation."
        )
        return model_path

    if _validation_stamp_matches(model_path, expected_sha1):
        return model_path

    ok, output = _validate_model_load_in_subprocess(model_path, n_threads)
    if ok:
        _write_validation_stamp(model_path, expected_sha1)
        return model_path

    _clear_validation_stamp(model_path)
    if owned_cache_file:
        _logger.warning(
            "Cached whisper.cpp model %s failed isolated load validation; redownloading exact selected model once. Error tail: %s",
            filename,
            output,
        )
        model_path = ensure_model_file(resolved_model, force_download=True)
        ok, output = _validate_model_load_in_subprocess(model_path, n_threads)
        if ok:
            _write_validation_stamp(model_path, expected_sha1)
            return model_path

    raise RuntimeError(
        f"Local whisper.cpp model '{resolved_model}' failed isolated load validation after self-heal. "
        f"Last error tail: {output}"
    )


def _get_model(model_name_override: Optional[str] = None) -> Model:
    """Get or create the WhisperCpp model instance."""
    model_name = _default_model_name(model_name_override)
    cached_model = _MODEL_CACHE.get(model_name)
    if cached_model is None:
        default_threads = "2" if platform.machine().lower() == "x86_64" else "8"
        n_threads = int(os.getenv("VIVENTIUM_STT_THREADS", default_threads))
        model_path = ensure_model_ready(model_name)

        _logger.info("Loading PyWhisperCpp model from %s", model_path)
        cached_model = Model(str(model_path), n_threads=n_threads, print_realtime=False, print_progress=False)
        _MODEL_CACHE[model_name] = cached_model
        _logger.info("PyWhisperCpp model loaded successfully with %s threads", n_threads)
        try:
            _logger.info("PyWhisperCpp system_info: %s", cached_model.system_info())
        except Exception as exc:
            _logger.debug("Unable to read PyWhisperCpp system_info: %s", exc)

    return cached_model


def prewarm_model(model_name: Optional[str] = None) -> None:
    """Ensure the local whisper.cpp model is downloaded, loaded, and first-inference warmed."""
    resolved_model = _default_model_name(model_name)
    model = _get_model(resolved_model)
    if resolved_model in _MODEL_WARMUP_DONE:
        return
    if not _bool_env("VIVENTIUM_STT_WARMUP_INFERENCE", True):
        return

    warmup_audio_s = max(
        0.1,
        min(3.0, _float_env("VIVENTIUM_STT_WARMUP_AUDIO_S", 1.0)),
    )
    warmup_samples = max(1, int(16000 * warmup_audio_s))
    warmup_audio = np.zeros(warmup_samples, dtype=np.float32)
    start = time.perf_counter()
    model.transcribe(
        warmup_audio,
        **_transcribe_kwargs(
            os.getenv("VIVENTIUM_STT_LANGUAGE", "en"),
            model_name=resolved_model,
            audio_duration_s=warmup_audio_s,
        ),
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    _MODEL_WARMUP_DONE.add(resolved_model)
    if _latency_logging_enabled():
        _logger.info(
            "[VoiceLatency] pywhispercpp_warmup model=%s audio_s=%.3f total_ms=%.1f",
            resolved_model,
            warmup_audio_s,
            elapsed_ms,
        )


def _run_cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Viventium local whisper.cpp model self-heal")
    parser.add_argument("--ensure-model", default=None, help="Model id to download, checksum, and load-validate")
    parser.add_argument("--no-validate", action="store_true", help="Only ensure the model file exists and passes checksum")
    args = parser.parse_args()

    model_path = ensure_model_ready(args.ensure_model, validate_load=not args.no_validate)
    print(f"VIVENTIUM_WHISPER_MODEL_READY {model_path.name}")


class PyWhisperCppSTT(STT):
    """PyWhisperCpp-based Speech-to-Text implementation."""

    def __init__(
        self,
        *,
        language: str = "en",
        sample_rate: int = 16000,
        model_name: Optional[str] = None,
    ) -> None:
        super().__init__(
            capabilities=STTCapabilities(streaming=False, interim_results=False)
        )
        self._language = language
        self._sample_rate = sample_rate
        self._model_name = _default_model_name(model_name)
        self._model = _get_model(self._model_name)

    @property
    def model(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return "PyWhisperCpp"

    async def _recognize_impl(
        self,
        buffer: AudioBuffer,
        *,
        language: str | None = None,
        conn_options: object = None,
    ) -> SpeechEvent:
        total_start = time.perf_counter()
        timings: dict[str, float] = {}

        def mark(name: str, start: float) -> float:
            now = time.perf_counter()
            timings[name] = (now - start) * 1000.0
            return now

        # Handle AudioBuffer which can be a frame or list of frames
        frames: List[AudioFrame] = []
        if isinstance(buffer, list):
            frames = buffer
        else:
            frames = [buffer]

        if not frames:
            return SpeechEvent(
                type=SpeechEventType.FINAL_TRANSCRIPT,
                alternatives=[SpeechData(text="", language=self._language)]
            )

        # Combine all audio frames into a single PCM buffer
        stage_start = time.perf_counter()
        sample_rate = frames[0].sample_rate
        num_channels = frames[0].num_channels
        input_channels = num_channels
        pcm_chunks: List[bytes] = []

        for frame in frames:
            if frame.sample_rate != sample_rate or frame.num_channels != num_channels:
                raise ValueError("Mismatched audio frame parameters")
            pcm_chunks.append(frame.data.tobytes())

        pcm_bytes = b"".join(pcm_chunks)
        input_audio_duration_s = (
            len(pcm_bytes) / (sample_rate * num_channels * 2)
            if sample_rate > 0 and num_channels > 0
            else 0.0
        )
        stage_start = mark("combine_ms", stage_start)

        # Convert to mono if needed
        if num_channels > 1:
            pcm_bytes = audioop.tomono(pcm_bytes, 2, 0.5, 0.5)
            num_channels = 1
        stage_start = mark("mono_ms", stage_start)

        # Resample to 16kHz if needed
        if sample_rate != self._sample_rate:
            pcm_bytes, _ = audioop.ratecv(
                pcm_bytes,
                2,  # 16-bit audio (2 bytes per sample)
                num_channels,
                sample_rate,
                self._sample_rate,
                None,
            )
        stage_start = mark("resample_ms", stage_start)

        # pywhispercpp accepts raw 16 kHz mono float32 PCM, so avoid a temp WAV roundtrip.
        audio_data = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        audio_data /= 32768.0
        audio_data = np.ascontiguousarray(audio_data)
        output_audio_duration_s = (
            audio_data.size / self._sample_rate if self._sample_rate > 0 else 0.0
        )
        stage_start = mark("float32_ms", stage_start)

        lang = language or self._language
        transcribe_params = _transcribe_kwargs(
            lang,
            model_name=self._model_name,
            audio_duration_s=output_audio_duration_s,
        )
        transcribe_start_ns = time.perf_counter_ns()
        segments = self._model.transcribe(
            audio_data,
            **transcribe_params,
        )
        transcribe_end_ns = time.perf_counter_ns()
        stage_start = mark("transcribe_ms", stage_start)

        text = " ".join([segment.text for segment in segments]) if segments else ""

        text_clean = text.strip().lower()
        if text_clean in HALLUCINATION_PHRASES:
            _logger.debug("Filtered hallucination: '%s'", text)
            text = ""
        mark("filter_ms", stage_start)

        if _latency_logging_enabled():
            total_ms = (time.perf_counter() - total_start) * 1000.0
            _logger.info(
                "[VoiceLatency] pywhispercpp_recognize model=%s frames=%s input_audio_s=%.3f output_audio_s=%.3f input_rate=%s output_rate=%s input_channels=%s text_chars=%s total_ms=%.3f combine_ms=%.3f mono_ms=%.3f resample_ms=%.3f float32_ms=%.3f transcribe_ms=%.3f filter_ms=%.3f",
                self._model_name,
                len(frames),
                input_audio_duration_s,
                output_audio_duration_s,
                sample_rate,
                self._sample_rate,
                input_channels,
                len(text),
                total_ms,
                timings.get("combine_ms", 0.0),
                timings.get("mono_ms", 0.0),
                timings.get("resample_ms", 0.0),
                timings.get("float32_ms", 0.0),
                timings.get("transcribe_ms", 0.0),
                timings.get("filter_ms", 0.0),
            )
            _logger.info(
                "[VoiceLatencyDetail] pywhispercpp_transcribe model=%s audio_s=%.6f audio_ctx=%s no_context=%s single_segment=%s transcribe_perf_ns_start=%s transcribe_perf_ns_end=%s transcribe_wall_ms=%.3f",
                self._model_name,
                output_audio_duration_s,
                transcribe_params.get("audio_ctx", "default"),
                transcribe_params.get("no_context"),
                transcribe_params.get("single_segment"),
                transcribe_start_ns,
                transcribe_end_ns,
                _ms_since(transcribe_start_ns, transcribe_end_ns),
            )

        return SpeechEvent(
            type=SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[SpeechData(text=text, language=lang)]
        )


class ViventiumInstrumentedStreamAdapterWrapper(RecognizeStream):
    """StreamAdapter wrapper with high-resolution local STT stage timing."""

    def __init__(
        self,
        stt: STT,
        *,
        vad: VADBase,
        wrapped_stt: STT,
        language: NotGivenOr[str],
        conn_options: APIConnectOptions,
    ) -> None:
        super().__init__(
            stt=stt,
            conn_options=DEFAULT_STREAM_ADAPTER_API_CONNECT_OPTIONS,
        )
        self._vad = vad
        self._wrapped_stt = wrapped_stt
        self._wrapped_stt_conn_options = conn_options
        self._language = language

    async def _metrics_monitor_task(self, event_aiter: AsyncIterable[SpeechEvent]) -> None:
        async for _ in event_aiter:
            pass

    async def _run(self) -> None:
        vad_stream = self._vad.stream()

        async def _forward_input() -> None:
            async for input in self._input_ch:
                if isinstance(input, self._FlushSentinel):
                    vad_stream.flush()
                    continue
                vad_stream.push_frame(input)

            vad_stream.end_input()

        async def _recognize() -> None:
            async for event in vad_stream:
                if event.type == VADEventType.START_OF_SPEECH:
                    if _latency_logging_enabled():
                        _logger.info(
                            "[VoiceLatencyDetail] stream_adapter_vad event=start_of_speech perf_ns=%s vad_timestamp_s=%.6f speech_s=%.6f silence_s=%.6f raw_speech_s=%.6f raw_silence_s=%.6f frames=%s",
                            time.perf_counter_ns(),
                            event.timestamp,
                            event.speech_duration,
                            event.silence_duration,
                            event.raw_accumulated_speech,
                            event.raw_accumulated_silence,
                            len(event.frames),
                        )
                    self._event_ch.send_nowait(SpeechEvent(SpeechEventType.START_OF_SPEECH))
                elif event.type == VADEventType.END_OF_SPEECH:
                    vad_end_ns = time.perf_counter_ns()
                    self._event_ch.send_nowait(
                        SpeechEvent(
                            type=SpeechEventType.END_OF_SPEECH,
                        )
                    )

                    merge_start_ns = time.perf_counter_ns()
                    merged_frames = lk_utils.merge_frames(event.frames)
                    merge_end_ns = time.perf_counter_ns()

                    sample_rate = int(getattr(merged_frames, "sample_rate", 0) or 0)
                    num_channels = int(getattr(merged_frames, "num_channels", 0) or 0)
                    audio_data = getattr(merged_frames, "data", b"") or b""
                    audio_bytes = int(
                        getattr(audio_data, "nbytes", len(audio_data))
                    )
                    audio_s = (
                        audio_bytes / (sample_rate * num_channels * 2)
                        if sample_rate > 0 and num_channels > 0
                        else 0.0
                    )

                    recognize_start_ns = time.perf_counter_ns()
                    t_event = await self._wrapped_stt.recognize(
                        buffer=merged_frames,
                        language=self._language,
                        conn_options=self._wrapped_stt_conn_options,
                    )
                    recognize_end_ns = time.perf_counter_ns()

                    text_chars = (
                        len(t_event.alternatives[0].text)
                        if len(t_event.alternatives) > 0
                        else 0
                    )
                    sent_final = False
                    final_send_ms = 0.0
                    if len(t_event.alternatives) > 0 and t_event.alternatives[0].text:
                        final_send_start_ns = time.perf_counter_ns()
                        self._event_ch.send_nowait(
                            SpeechEvent(
                                type=SpeechEventType.FINAL_TRANSCRIPT,
                                alternatives=[t_event.alternatives[0]],
                            )
                        )
                        final_send_ms = _ms_since(final_send_start_ns)
                        sent_final = True

                    if _latency_logging_enabled():
                        _logger.info(
                            "[VoiceLatencyDetail] stream_adapter_final model=%s provider=%s sent_final=%s text_chars=%s vad_end_perf_ns=%s vad_timestamp_s=%.6f speech_s=%.6f silence_s=%.6f raw_speech_s=%.6f raw_silence_s=%.6f frames=%s audio_s=%.6f merge_ms=%.3f recognize_wait_ms=%.3f final_send_ms=%.3f total_after_vad_end_ms=%.3f",
                            self._wrapped_stt.model,
                            self._wrapped_stt.provider,
                            sent_final,
                            text_chars,
                            vad_end_ns,
                            event.timestamp,
                            event.speech_duration,
                            event.silence_duration,
                            event.raw_accumulated_speech,
                            event.raw_accumulated_silence,
                            len(event.frames),
                            audio_s,
                            _ms_since(merge_start_ns, merge_end_ns),
                            _ms_since(recognize_start_ns, recognize_end_ns),
                            final_send_ms,
                            _ms_since(vad_end_ns),
                        )

        tasks = [
            asyncio.create_task(_forward_input(), name="forward_input"),
            asyncio.create_task(_recognize(), name="recognize"),
        ]
        try:
            await asyncio.gather(*tasks)
        finally:
            await lk_utils.aio.cancel_and_wait(*tasks)
            await vad_stream.aclose()


class ViventiumInstrumentedStreamAdapter(StreamAdapter):
    def stream(
        self,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> RecognizeStream:
        return ViventiumInstrumentedStreamAdapterWrapper(
            self,
            vad=self._vad,
            wrapped_stt=self._stt,
            language=language,
            conn_options=conn_options,
        )


def get_stt(*, model_name: Optional[str] = None, language: Optional[str] = None) -> StreamAdapter:
    """Get PyWhisperCpp STT wrapped in StreamAdapter with VAD for streaming support."""
    from livekit.plugins.silero import VAD

    stt_kwargs = {
        "language": language or os.getenv("VIVENTIUM_STT_LANGUAGE", "en"),
    }
    if model_name is not None:
        stt_kwargs["model_name"] = model_name

    stt = PyWhisperCppSTT(**stt_kwargs)

    vad_kwargs = get_silero_vad_kwargs(_local_whisper_vad_env())
    _logger.info(
        "Loading PyWhisperCpp StreamAdapter VAD min_speech=%ss min_silence=%ss activation=%s max_buffered_speech=%ss force_cpu=%s",
        vad_kwargs["min_speech_duration"],
        vad_kwargs["min_silence_duration"],
        vad_kwargs["activation_threshold"],
        vad_kwargs["max_buffered_speech"],
        vad_kwargs["force_cpu"],
    )
    vad = VAD.load(**vad_kwargs)

    return ViventiumInstrumentedStreamAdapter(stt=stt, vad=vad)


__all__ = [
    "get_stt",
    "PyWhisperCppSTT",
    "prewarm_model",
    "ensure_model_file",
    "ensure_model_ready",
]


if __name__ == "__main__":
    _run_cli()
