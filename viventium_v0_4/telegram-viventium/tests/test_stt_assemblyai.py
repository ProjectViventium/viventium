# VIVENTIUM START
# File: test_stt_assemblyai.py
# Purpose: Unit tests for AssemblyAI STT client integration.
# VIVENTIUM END
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TELEGRAM_ROOT = ROOT / "TelegramVivBot"
if str(TELEGRAM_ROOT) not in sys.path:
    sys.path.insert(0, str(TELEGRAM_ROOT))

from TelegramVivBot.aient.aient.models.assemblyai import AssemblyAI, AssemblyAIError


class StubResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class StubSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, headers=None, timeout=None, **kwargs):
        self.calls.append(("POST", url, headers, kwargs))
        return self._responses.pop(0)

    def get(self, url, headers=None, timeout=None):
        self.calls.append(("GET", url, headers, {}))
        return self._responses.pop(0)


def test_assemblyai_transcribe_happy_path():
    responses = [
        StubResponse(200, {"upload_url": "https://upload.local/abc"}),
        StubResponse(200, {"id": "tx-123"}),
        StubResponse(200, {"status": "completed", "text": "hello world"}),
    ]
    session = StubSession(responses)
    client = AssemblyAI(
        api_key="test-key",
        base_url="https://api.assemblyai.com/v2",
        poll_interval_s=0.0,
        poll_timeout_s=1.0,
        session=session,
    )
    text = client.transcribe_bytes(b"audio-bytes")
    assert text == "hello world"
    post_payload = session.calls[1][3]["json"]
    assert post_payload["audio_url"] == "https://upload.local/abc"


def test_assemblyai_transcribe_error_status():
    responses = [
        StubResponse(200, {"upload_url": "https://upload.local/abc"}),
        StubResponse(200, {"id": "tx-123"}),
        StubResponse(200, {"status": "error", "error": "bad request"}),
    ]
    session = StubSession(responses)
    client = AssemblyAI(
        api_key="test-key",
        base_url="https://api.assemblyai.com/v2",
        poll_interval_s=0.0,
        poll_timeout_s=1.0,
        session=session,
    )
    with pytest.raises(AssemblyAIError):
        client.transcribe_bytes(b"audio-bytes")
