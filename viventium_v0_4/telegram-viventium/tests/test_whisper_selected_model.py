# === VIVENTIUM START ===
"""An explicit Listening model wins defaults; legacy callers retain their defaults."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'TelegramVivBot'))
from TelegramVivBot.aient.aient.models.whisper import Whisper


@pytest.mark.parametrize('selected,expected', [
    ('whisper-1', 'whisper-1'), ('gpt-4o-transcribe', 'gpt-4o-transcribe'),
    (None, 'environment-model'),
])
def test_explicit_model_wins_environment_without_changing_legacy(monkeypatch, selected, expected):
    monkeypatch.setenv('AUDIO_MODEL_NAME', 'environment-model')
    monkeypatch.delenv('WHISPER_API_URL', raising=False)
    client = Whisper(api_key='synthetic-key')
    calls = []
    monkeypatch.setattr(client.session, 'post', lambda *args, **kwargs:
                        calls.append(kwargs) or SimpleNamespace(status_code=200, text='{"text":"hello"}'))
    arguments = {} if selected is None else {'model': selected}
    assert client.generate(b'audio', **arguments) == 'hello'
    assert calls[0]['data']['model'] == expected
    client.session.close()


def test_selected_url_bypasses_legacy_override_but_legacy_keeps_it(monkeypatch):
    monkeypatch.setenv('WHISPER_API_URL', 'https://legacy.example/audio')
    legacy = Whisper(api_key='synthetic-key', api_url='https://selected.example/v1/')
    selected = Whisper(api_key='synthetic-key', api_url='https://selected.example/v1/', use_environment_url=False)
    assert legacy.api_url == 'https://legacy.example/audio'
    assert selected.api_url == 'https://selected.example/v1/audio/transcriptions'
    legacy.session.close()
    selected.session.close()


def test_invalid_explicit_endpoint_does_not_fall_back():
    with pytest.raises(Exception, match='API_URL is not set'):
        Whisper(api_key='synthetic-key', api_url='invalid', use_environment_url=False)


def test_legacy_http_rejection_preserves_status_without_provider_body(caplog, monkeypatch):
    import requests
    response = requests.Response()
    response.status_code, response.reason = 401, 'Unauthorized'
    response._content = b'{"error":{"message":"private-response-marker synthetic-key-sample"}}'
    response._content_consumed = True
    client = Whisper(api_key='synthetic-key')
    monkeypatch.setattr(client.session, 'post', lambda *args, **kwargs: response)
    try:
        with pytest.raises(requests.HTTPError) as result:
            client.generate(b'audio')
        assert result.value.response is response
        assert result.value.response.status_code == 401
        assert 'private-response-marker' not in caplog.text
        assert 'synthetic-key-sample' not in str(result.value)
    finally:
        client.session.close()


def test_invalid_json_response_does_not_log_provider_body(caplog, monkeypatch):
    client = Whisper(api_key='synthetic-key')
    monkeypatch.setattr(client.session, 'post', lambda *args, **kwargs:
                        SimpleNamespace(status_code=200, text='private-response-marker {invalid'))
    try:
        with pytest.raises(RuntimeError, match='response is invalid JSON') as result:
            client.generate(b'audio')
        assert 'private-response-marker' not in caplog.text
        assert 'private-response-marker' not in str(result.value)
    finally:
        client.session.close()


def test_response_cleanup_failure_cannot_replace_http_status(caplog, monkeypatch):
    import requests
    response = requests.Response()
    response.status_code = 401
    response._content = b'{"error":{"message":"private-response-marker"}}'
    def failed_close():
        raise requests.ConnectionError('private-cleanup-marker')
    response.close = failed_close
    client = Whisper(api_key='synthetic-key')
    monkeypatch.setattr(client.session, 'post', lambda *args, **kwargs: response)
    try:
        with pytest.raises(requests.HTTPError) as result:
            client.generate(b'audio')
        assert result.value.response.status_code == 401
        assert 'private-response-marker' not in caplog.text
        assert 'private-cleanup-marker' not in caplog.text
    finally:
        client.session.close()
# === VIVENTIUM END ===
