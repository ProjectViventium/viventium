# === VIVENTIUM START ===
# Feature: Local whisper.cpp STT provider with VAD stream adapter (v1 parity)
# Added: 2026-01-11
# === VIVENTIUM END ===

"""PyWhisperCpp STT Provider - Fast, reliable C++ Whisper implementation."""

from __future__ import annotations

import audioop
import hashlib
import importlib.metadata
import logging
import os
import platform
import socket
import subprocess
import sys
import tempfile
import urllib.request
import wave
from pathlib import Path
from typing import List, Optional

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
    STT,
    STTCapabilities,
    SpeechData,
    SpeechEvent,
    SpeechEventType,
)
from livekit.agents.stt.stream_adapter import StreamAdapter
from livekit.agents.utils import AudioBuffer
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
_LOCAL_WHISPER_VAD_MIN_SILENCE_S = "1.0"

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

    return cached_model


def prewarm_model(model_name: Optional[str] = None) -> None:
    """Ensure the local whisper.cpp model is downloaded and loaded in-process."""
    _get_model(model_name)


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
        sample_rate = frames[0].sample_rate
        num_channels = frames[0].num_channels
        pcm_chunks: List[bytes] = []

        for frame in frames:
            if frame.sample_rate != sample_rate or frame.num_channels != num_channels:
                raise ValueError("Mismatched audio frame parameters")
            pcm_chunks.append(frame.data.tobytes())

        pcm_bytes = b"".join(pcm_chunks)

        # Convert to mono if needed
        if num_channels > 1:
            pcm_bytes = audioop.tomono(pcm_bytes, 2, 0.5, 0.5)
            num_channels = 1

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

        # Convert to int16 numpy array (PyWhisperCpp expects int16)
        audio_data = np.frombuffer(pcm_bytes, dtype=np.int16)

        # Use memory-mapped temp file for faster I/O
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            tmp_path = tmp_wav.name
            # Write WAV header and data directly
            with wave.open(tmp_path, "wb") as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self._sample_rate)
                wav_file.writeframes(audio_data.tobytes())

        try:
            lang = language or self._language
            segments = self._model.transcribe(
                tmp_path,
                language=lang,
                no_speech_thold=0.7,
                logprob_thold=-0.8,
                suppress_blank=True,
                temperature=0.0,
                entropy_thold=2.2,
            )

            text = " ".join([segment.text for segment in segments]) if segments else ""

            text_clean = text.strip().lower()
            if text_clean in HALLUCINATION_PHRASES:
                _logger.debug("Filtered hallucination: '%s'", text)
                text = ""
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        return SpeechEvent(
            type=SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[SpeechData(text=text, language=lang)]
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

    return StreamAdapter(stt=stt, vad=vad)


__all__ = [
    "get_stt",
    "PyWhisperCppSTT",
    "prewarm_model",
    "ensure_model_file",
    "ensure_model_ready",
]


if __name__ == "__main__":
    _run_cli()
