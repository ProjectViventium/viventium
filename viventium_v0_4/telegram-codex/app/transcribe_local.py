from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import socket
import sys
import tempfile
import urllib.request
from pathlib import Path

_SHARED_PATH = Path(__file__).resolve().parents[2] / "shared"
if str(_SHARED_PATH) not in sys.path:
    sys.path.insert(0, str(_SHARED_PATH))

from whisper_cpp_models import MODEL_FILENAMES as _MODEL_MAP
from whisper_cpp_models import MODEL_SHA1 as _MODEL_SHA1

from pywhispercpp.model import Model

from app.config import TranscriptionSettings


logger = logging.getLogger(__name__)


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


def _download_model_file(filename: str, model_path: Path, expected_sha1: str) -> None:
    url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{filename}"
    tmp_path = model_path.with_name(f".{model_path.name}.{os.getpid()}.download")
    tmp_path.unlink(missing_ok=True)
    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(_download_timeout_s())
    try:
        logger.info("Downloading whisper.cpp model %s", url)
        urllib.request.urlretrieve(url, tmp_path)
        actual_sha1 = _sha1_file(tmp_path)
        if actual_sha1 != expected_sha1:
            raise RuntimeError(
                f"Downloaded whisper.cpp model {filename} failed checksum: "
                f"expected {expected_sha1}, got {actual_sha1}"
            )
        os.replace(tmp_path, model_path)
    finally:
        socket.setdefaulttimeout(previous_timeout)
        tmp_path.unlink(missing_ok=True)


def _ensure_model_file(model_name: str, cache_dir: Path) -> Path:
    filename = _MODEL_MAP.get(model_name)
    if not filename:
        known = ", ".join(sorted(_MODEL_MAP))
        raise ValueError(f"Unsupported local whisper.cpp model '{model_name}'. Known models: {known}")
    expected_sha1 = _MODEL_SHA1.get(filename)
    if not expected_sha1:
        raise RuntimeError(f"Missing checksum for local whisper.cpp model '{model_name}'")

    cache_dir.mkdir(parents=True, exist_ok=True)
    model_path = cache_dir / filename
    if model_path.exists():
        actual_sha1 = _sha1_file(model_path)
        if actual_sha1 == expected_sha1:
            return model_path.resolve()
        logger.warning(
            "Cached whisper.cpp model %s failed checksum; redownloading exact selected model",
            model_path,
        )

    _download_model_file(filename, model_path, expected_sha1)
    return model_path.resolve()


class LocalWhisperTranscriber:
    def __init__(self, settings: TranscriptionSettings) -> None:
        self._settings = settings
        self._model: Model | None = None

    async def transcribe_bytes(self, file_bytes: bytes, *, suffix: str = ".ogg") -> str:
        return await asyncio.to_thread(self._transcribe_sync, file_bytes, suffix)

    def _transcribe_sync(self, file_bytes: bytes, suffix: str) -> str:
        model = self._ensure_model()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(file_bytes)
        try:
            segments = model.transcribe(
                str(tmp_path),
                language=self._settings.language,
                translate=False,
                print_realtime=False,
            )
            return " ".join(segment.text for segment in segments).strip()
        finally:
            tmp_path.unlink(missing_ok=True)

    def _ensure_model(self) -> Model:
        if self._model is not None:
            return self._model

        model_path = self._resolve_model_path()
        logger.info("Loading local whisper model from %s", model_path)
        self._model = Model(str(model_path), n_threads=self._settings.threads)
        return self._model

    def _resolve_model_path(self) -> Path:
        configured_path = str(self._settings.model_path or "").strip()
        if configured_path:
            logger.warning(
                "Local Whisper model_path is set; Telegram Codex will load this explicit path without managed "
                "checksum self-heal or redownload."
            )
            return Path(configured_path).expanduser().resolve()

        configured_cache_dir = (os.getenv("VIVENTIUM_WHISPER_CACHE_DIR") or "").strip()
        cache_dir = (
            Path(configured_cache_dir).expanduser()
            if configured_cache_dir
            else Path.home() / ".cache" / "whisper"
        )
        return _ensure_model_file(self._settings.model_name, cache_dir)
