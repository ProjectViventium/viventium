import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load():
    path = Path(__file__).parents[2] / 'scripts/viventium/transcribe_audio.py'
    spec = importlib.util.spec_from_file_location('transcription_adapter', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_readiness_uses_exact_configured_model_without_loading_or_downloading(tmp_path, monkeypatch):
    adapter = _load()
    monkeypatch.setattr(adapter.importlib.util, 'find_spec', lambda _: object())
    monkeypatch.setattr(adapter.shutil, 'which', lambda _: '/bin/ffmpeg')
    model = tmp_path / 'configured.bin'
    model.write_bytes(b'existing model')
    config = SimpleNamespace(WHISPER_MODE='pywhispercpp', LOCAL_WHISPER_MODEL_PATH=str(model))
    assert adapter.engine_readiness(config) == {'status': 'ready'}
    assert config.LOCAL_WHISPER_MODEL_PATH == str(model)
    model.unlink()
    assert adapter.engine_readiness(config) == {'status': 'unavailable', 'code': 'transcription_model_unavailable'}


def test_missing_dependency_does_not_fall_back_to_a_different_provider(monkeypatch):
    adapter = _load()
    monkeypatch.setattr(adapter.importlib.util, 'find_spec', lambda _: None)
    config = SimpleNamespace(WHISPER_MODE='pywhispercpp')
    assert adapter.engine_readiness(config)['code'] == 'transcription_dependencies_unavailable'
    config.WHISPER_MODE = 'unconfigured'
    assert adapter.engine_readiness(config)['code'] == 'transcription_provider_unsupported'


def test_managed_model_requires_its_current_checksum(tmp_path, monkeypatch):
    adapter = _load()
    monkeypatch.setattr(adapter.importlib.util, 'find_spec', lambda _: object())
    monkeypatch.setattr(adapter.shutil, 'which', lambda _: '/bin/ffmpeg')
    monkeypatch.setenv('VIVENTIUM_WHISPER_CACHE_DIR', str(tmp_path))
    (tmp_path / 'chosen.bin').write_bytes(b'existing model')
    config = SimpleNamespace(WHISPER_MODE='pywhispercpp', LOCAL_WHISPER_MODEL_PATH='',
        _normalize_local_whisper_model_name=lambda _: 'chosen', _LOCAL_WHISPER_MODEL_FILES={'chosen': 'chosen.bin'},
        _LOCAL_WHISPER_MODEL_SHA1={'chosen.bin': 'expected'}, _sha1_file=lambda _: 'wrong')
    assert adapter.engine_readiness(config)['code'] == 'transcription_model_invalid'


def test_transcription_failures_keep_typed_auth_quota_network_and_timeout(monkeypatch):
    # The HTTP dependency belongs to the selected optional speech runtime, not root tests.
    import sys
    class ReadTimeout(Exception):
        pass
    class NetworkError(Exception):
        pass
    class HttpError(Exception):
        def __init__(self, response):
            self.response = response
    requests = SimpleNamespace(HTTPError=HttpError, ReadTimeout=ReadTimeout, ConnectionError=NetworkError,
        exceptions=SimpleNamespace(Timeout=ReadTimeout, ConnectionError=NetworkError))
    monkeypatch.setitem(sys.modules, 'requests', requests)
    adapter = _load()
    for status, body, expected in [
        (401, {}, 'transcription_auth_rejected'),
        (429, {'error': {'code': 'insufficient_quota'}}, 'transcription_quota_exhausted'),
        (429, {}, 'transcription_rate_limited'),
        (503, {}, 'transcription_provider_rejected'),
    ]:
        response = SimpleNamespace(status_code=status, json=lambda: body)
        assert adapter.transcription_failure_code(requests.HTTPError(response=response)) == expected
    cause = requests.ReadTimeout()
    error = RuntimeError('opaque wrapper')
    error.__cause__ = cause
    assert adapter.transcription_failure_code(error) == 'transcription_timeout'
    assert adapter.transcription_failure_code(requests.ConnectionError()) == 'transcription_network_unavailable'
    assert adapter.transcription_failure_code(RuntimeError('401 timeout quota')) == 'transcription_failed'


def test_engine_invocation_does_not_mutate_sealed_code(tmp_path):
    import json
    import subprocess
    import sys
    engine = tmp_path / 'engine'
    engine.mkdir()
    (engine / 'config.py').write_text("WHISPER_MODE = 'unconfigured'\n")
    adapter = Path(__file__).parents[2] / 'scripts/viventium/transcribe_audio.py'
    for _ in range(2):
        run = subprocess.run([sys.executable, str(adapter), '--app-support-dir', str(tmp_path),
                              '--engine', str(engine), '--check'], capture_output=True, text=True, check=True)
        assert json.loads(run.stdout)['code'] == 'transcription_provider_unsupported'
        assert sorted(p.name for p in engine.iterdir()) == ['config.py']
