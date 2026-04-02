from __future__ import annotations

import asyncio
import logging
import tempfile
import urllib.request
from pathlib import Path

from pywhispercpp.model import Model

from app.config import TranscriptionSettings


logger = logging.getLogger(__name__)

_MODEL_MAP = {
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
            return Path(configured_path).expanduser().resolve()

        filename = _MODEL_MAP.get(self._settings.model_name, "ggml-large-v3-turbo.bin")
        cache_dir = Path.home() / ".cache" / "whisper"
        cache_dir.mkdir(parents=True, exist_ok=True)
        model_path = cache_dir / filename
        if model_path.exists():
            return model_path

        url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{filename}"
        logger.info("Downloading whisper.cpp model %s", url)
        urllib.request.urlretrieve(url, model_path)
        return model_path

