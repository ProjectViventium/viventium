# VIVENTIUM START
# File: assemblyai.py
# Purpose: AssemblyAI STT client for Telegram voice transcription.
# Notes:
# - Uses the existing requests dependency.
# - Keeps configuration driven by env vars to avoid hardcoding.
# VIVENTIUM END
import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class AssemblyAIError(RuntimeError):
    pass


class AssemblyAI:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: Optional[str] = None,
        timeout_s: Optional[float] = None,
        poll_interval_s: Optional[float] = None,
        poll_timeout_s: Optional[float] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        if not api_key:
            raise AssemblyAIError("AssemblyAI API key is required")
        self.api_key = api_key
        self.base_url = (base_url or os.environ.get("ASSEMBLYAI_BASE_URL") or "https://api.assemblyai.com/v2").rstrip("/")
        self.timeout_s = timeout_s or float(os.environ.get("ASSEMBLYAI_TIMEOUT_S", "60"))
        self.poll_interval_s = poll_interval_s or float(os.environ.get("ASSEMBLYAI_POLL_INTERVAL_S", "2.0"))
        self.poll_timeout_s = poll_timeout_s or float(os.environ.get("ASSEMBLYAI_POLL_TIMEOUT_S", "120"))
        self.session = session or requests.Session()

    def _headers(self) -> dict:
        return {"authorization": self.api_key}

    def _post(self, path: str, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        response = self.session.post(url, headers=self._headers(), timeout=self.timeout_s, **kwargs)
        if response.status_code not in (200, 201):
            raise AssemblyAIError(f"AssemblyAI POST {url} failed: {response.status_code} {response.text}")
        return response.json()

    def _get(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        response = self.session.get(url, headers=self._headers(), timeout=self.timeout_s)
        if response.status_code != 200:
            raise AssemblyAIError(f"AssemblyAI GET {url} failed: {response.status_code} {response.text}")
        return response.json()

    def transcribe_bytes(self, audio_bytes: bytes) -> str:
        if not audio_bytes:
            raise AssemblyAIError("Audio bytes are empty")

        logger.info("AssemblyAI upload start: bytes=%d", len(audio_bytes))
        upload = self._post("/upload", data=audio_bytes)
        upload_url = upload.get("upload_url")
        if not upload_url:
            raise AssemblyAIError("AssemblyAI upload_url missing in response")

        payload = {"audio_url": upload_url}
        language_code = (os.environ.get("ASSEMBLYAI_LANGUAGE_CODE") or "").strip()
        if language_code:
            payload["language_code"] = language_code

        transcript = self._post("/transcript", json=payload)
        transcript_id = transcript.get("id")
        if not transcript_id:
            raise AssemblyAIError("AssemblyAI transcript id missing in response")

        deadline = time.monotonic() + max(self.poll_timeout_s, 1.0)
        while True:
            data = self._get(f"/transcript/{transcript_id}")
            status = data.get("status")
            if status == "completed":
                return data.get("text", "") or ""
            if status == "error":
                raise AssemblyAIError(data.get("error") or "AssemblyAI transcription error")
            if time.monotonic() >= deadline:
                raise AssemblyAIError(f"AssemblyAI transcription timed out after {self.poll_timeout_s}s")
            time.sleep(max(self.poll_interval_s, 0.5))
