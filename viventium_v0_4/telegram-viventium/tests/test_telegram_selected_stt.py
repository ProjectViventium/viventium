# === VIVENTIUM START ===
"""Selected Listening execution, model residency and whole-note stream ownership."""
import asyncio
import importlib
import sys
import threading
import time
import types
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'TelegramVivBot'))
from TelegramVivBot.utils import telegram_stt as adapter
from TelegramVivBot.utils.telegram_audio import DecodedTelegramAudio
from TelegramVivBot.aient.aient.utils.scripts import _LOCAL_STT_TRANSCRIBE_LOCK

# Other preference tests install module-level lightweight mocks during collection.
# This owning bank executes the actual canonical selected/legacy consumer modules.
_CANONICAL_SCRIPTS = importlib.import_module('TelegramVivBot.aient.aient.utils.scripts')
_CANONICAL_WHISPER = importlib.import_module('TelegramVivBot.aient.aient.models.whisper')


@pytest.fixture(autouse=True)
def canonical_consumer_modules(monkeypatch):
    monkeypatch.setitem(sys.modules, 'TelegramVivBot.aient.aient.utils.scripts', _CANONICAL_SCRIPTS)
    monkeypatch.setitem(sys.modules, 'TelegramVivBot.aient.aient.models.whisper', _CANONICAL_WHISPER)
    monkeypatch.setattr(sys.modules['TelegramVivBot.aient.aient.utils'], 'scripts', _CANONICAL_SCRIPTS)
    monkeypatch.setattr(sys.modules['TelegramVivBot.aient.aient.models'], 'whisper', _CANONICAL_WHISPER)


def audio(size=1):
    return DecodedTelegramAudio(np.full(size, 0.001, dtype=np.float32))


@pytest.mark.asyncio
@pytest.mark.parametrize('selection', [None, {}, {'provider': 'openai'},
    {'provider': 'unsupported', 'variant': 'some-model'}])
async def test_missing_or_unsupported_selection_never_runs_other_engine(selection):
    with pytest.raises(adapter.TelegramSTTError, match='unsupported_configuration'):
        await adapter.transcribe_selected_audio(b'bytes', audio(), selection, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize('decoded,code', [
    (DecodedTelegramAudio(np.array([], dtype=np.float32), no_speech=True), 'no_speech'),
    (DecodedTelegramAudio(np.array([], dtype=np.float32)), 'audio_empty'),
    (DecodedTelegramAudio(np.array([np.nan], dtype=np.float32)), 'audio_nonfinite'),
])
async def test_no_speech_and_invalid_pcm_do_not_create_provider(monkeypatch, decoded, code):
    monkeypatch.setattr(adapter, '_transcribe_openai', lambda *_: pytest.fail('provider ran'))
    with pytest.raises(adapter.TelegramSTTError, match=code):
        await adapter.transcribe_selected_audio(b'bytes', decoded, {'provider': 'openai', 'variant': 'whisper-1'}, 1)


@pytest.mark.asyncio
async def test_openai_uses_dedicated_credentials_url_and_explicit_variant(monkeypatch):
    from TelegramVivBot.aient.aient.models.whisper import Whisper
    monkeypatch.setenv('OPENAI_API_KEY', 'openai-synthetic')
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://openai-proxy.example/v1/')
    monkeypatch.setenv('API_KEY', 'grok-synthetic')
    monkeypatch.setenv('BASE_URL', 'https://grok.example/v1/')
    monkeypatch.setenv('WHISPER_API_URL', 'https://azure.example/transcriptions')
    monkeypatch.setenv('AUDIO_MODEL_NAME', 'environment-model')
    calls, closed, timings = [], [], []
    session = types.SimpleNamespace(
        post=lambda url, **kwargs: calls.append((url, kwargs)) or
        types.SimpleNamespace(status_code=200, text='{"text":"hello"}'),
        close=lambda: closed.append(True))
    monkeypatch.setattr('requests.Session', lambda: session)
    result = await adapter.transcribe_selected_audio(b'whole-original-note', audio(),
        {'provider': 'openai', 'variant': 'whisper-1'}, 1,
        timing=lambda *args: timings.append(args))
    assert result == 'hello'
    assert calls[0][0] == 'https://openai-proxy.example/v1/audio/transcriptions'
    assert calls[0][1]['headers'] == {'Authorization': 'Bearer openai-synthetic'}
    assert calls[0][1]['data'] == {'model': 'whisper-1'}
    assert calls[0][1]['files']['file'][1] == b'whole-original-note'
    assert closed == [True]
    assert [t[0] for t in timings] == ['openai_inference_started', 'openai_inference_completed']
    assert all(t[2] == {'requested_variant': 'whisper-1', 'effective_variant': 'whisper-1'} for t in timings)


@pytest.mark.asyncio
async def test_missing_openai_key_does_not_use_generic_provider_key(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setenv('API_KEY', 'other-provider-key')
    with pytest.raises(adapter.TelegramSTTError, match='provider_auth_missing'):
        await adapter.transcribe_selected_audio(b'bytes', audio(), {'provider': 'openai', 'variant': 'whisper-1'}, 1)


@pytest.mark.asyncio
async def test_placeholder_openai_key_is_missing_auth_without_request(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'user_provided')
    monkeypatch.setattr('requests.Session', lambda: pytest.fail('placeholder must not create client'))
    with pytest.raises(adapter.TelegramSTTError, match='provider_auth_missing'):
        await adapter.transcribe_selected_audio(b'bytes', audio(),
            {'provider': 'openai', 'variant': 'gpt-4o-transcribe'}, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize('status,code', [
    (401, 'provider_unauthorized'), (403, 'provider_access_denied'),
    (429, 'provider_rate_limited'), (408, 'timeout'), (504, 'timeout'),
    (500, 'provider_temporarily_unavailable'), (503, 'provider_temporarily_unavailable'),
    (400, 'provider_request_rejected'), (404, 'provider_request_rejected'), (422, 'provider_request_rejected'),
])
async def test_openai_status_is_typed_without_body_leak_or_replay(monkeypatch, caplog, status, code):
    import requests
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-key')
    response = requests.Response()
    response.status_code, response.reason = status, 'Synthetic provider rejection'
    secret_body = 'private-response-marker synthetic-credential-sample'
    response._content = ('{"error":{"message":"' + secret_body + '"}}').encode()
    response._content_consumed = True
    calls, closed = [], []
    monkeypatch.setattr('requests.Session', lambda: types.SimpleNamespace(
        post=lambda *args, **kwargs: calls.append(kwargs) or response,
        close=lambda: closed.append(True)))
    with pytest.raises(adapter.TelegramSTTError) as result:
        await adapter.transcribe_selected_audio(b'whole-original-note', audio(),
            {'provider': 'openai', 'variant': 'gpt-4o-transcribe'}, 1)
    assert result.value.code == code
    assert len(calls) == 1 and closed == [True]
    assert calls[0]['data']['model'] == 'gpt-4o-transcribe'
    assert calls[0]['files']['file'][1] == b'whole-original-note'
    assert result.value.__cause__.response.status_code == status
    assert secret_body not in caplog.text and secret_body not in str(result.value.__cause__)


@pytest.mark.parametrize('media', ['voice note', 'video note'])
@pytest.mark.parametrize('code,notice', [
    ('provider_auth_missing', 'no usable authentication'),
    ('provider_unauthorized', 'rejected its authentication'),
    ('provider_access_denied', 'denied access'),
    ('provider_rate_limited', 'rate-limited'),
    ('provider_temporarily_unavailable', 'temporarily unavailable'),
    ('provider_request_rejected', 'provider rejected this'),
    ('unsupported_configuration', 'configuration is unsupported'),
    ('timeout', 'Timed out transcribing'),
])
def test_selected_listening_failure_has_typed_truthful_notice(monkeypatch, code, notice, media):
    monkeypatch.setitem(sys.modules, 'config', types.ModuleType('config'))
    scripts = importlib.import_module('TelegramVivBot.utils.scripts')
    result = scripts._transcription_runtime_error(media, code)
    assert result.text is None and notice in result.error_text
    assert result.error_code == code and result.error_text.error_code == code


@pytest.mark.asyncio
@pytest.mark.parametrize('exception,code', [
    ('ReadTimeout', 'timeout'), ('ConnectTimeout', 'timeout'),
    ('ConnectionError', 'provider_temporarily_unavailable'),
    ('InvalidURL', 'unsupported_configuration'),
])
async def test_openai_transport_type_survives_shared_client(monkeypatch, exception, code):
    import requests
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-key')
    original = getattr(requests.exceptions, exception)('synthetic failure')
    calls, closed = [], []
    def post(*args, **kwargs):
        calls.append(kwargs)
        raise original
    monkeypatch.setattr('requests.Session', lambda: types.SimpleNamespace(
        post=post, close=lambda: closed.append(True)))
    with pytest.raises(adapter.TelegramSTTError) as result:
        await adapter.transcribe_selected_audio(b'whole-original-note', audio(),
            {'provider': 'openai', 'variant': 'gpt-4o-transcribe'}, 1)
    assert result.value.code == code and result.value.__cause__ is original
    assert len(calls) == 1 and closed == [True]


@pytest.mark.asyncio
async def test_provider_failure_is_not_empty_or_fallback(monkeypatch):
    def fail(*_):
        raise RuntimeError('synthetic provider error')
    monkeypatch.setattr(adapter, '_transcribe_openai', fail)
    monkeypatch.setattr(adapter, '_transcribe_local', lambda *_: pytest.fail('fallback ran'))
    with pytest.raises(adapter.TelegramSTTError, match='transcription_failed'):
        await adapter.transcribe_selected_audio(b'bytes', audio(), {'provider': 'openai', 'variant': 'kept-model'}, 1)


@pytest.fixture
def local_model(monkeypatch):
    state = types.SimpleNamespace(paths=[], validations=[], inferences=[], active=0, peak_active=0,
                                  resident=0, peak_resident=0)
    class Model:
        def __init__(self, path, n_threads):
            self.model_path = path
            state.paths.append((path, n_threads))
            state.resident += 1
            state.peak_resident = max(state.peak_resident, state.resident)
        def __del__(self):
            state.resident -= 1
        def transcribe(self, pcm, **kwargs):
            state.active += 1
            state.peak_active = max(state.peak_active, state.active)
            time.sleep(0.015)
            state.inferences.append((self.model_path, pcm.copy(), kwargs))
            state.active -= 1
            return [types.SimpleNamespace(text=self.model_path)]
    def ensure(variant):
        state.validations.append(variant)
        return '/managed/' + variant
    config = types.SimpleNamespace(local_whisper=None, LOCAL_WHISPER_THREADS=3,
        LOCAL_WHISPER_LANG='auto', LOCAL_WHISPER_VERBOSE=False,
        _local_whisper_model_path=lambda variant: '/managed/' + variant,
        _ensure_local_whisper_model_file=ensure)
    monkeypatch.setitem(sys.modules, 'config', config)
    monkeypatch.setitem(sys.modules, 'pywhispercpp.model', types.SimpleNamespace(Model=Model))
    yield state, config
    config.local_whisper = None


@pytest.mark.asyncio
@pytest.mark.parametrize('provider', ['local', 'whisper_local', 'pywhispercpp'])
async def test_local_selected_model_reuses_and_swaps_only_one_resident(local_model, provider):
    state, config = local_model
    for variant in ['small', 'small', 'large-v3-turbo', 'small']:
        assert await adapter.transcribe_selected_audio(b'bytes', audio(),
            {'provider': provider, 'variant': variant}, 1) == '/managed/' + variant
    assert state.paths == [('/managed/small', 3), ('/managed/large-v3-turbo', 3), ('/managed/small', 3)]
    assert state.validations == ['small', 'large-v3-turbo', 'small']
    assert state.peak_resident == 1
    assert all(i[2]['n_threads'] == 3 and i[2]['language'] == '' for i in state.inferences)


@pytest.mark.asyncio
async def test_local_requests_share_native_lock_without_global_env_race(local_model, monkeypatch):
    monkeypatch.setenv('WHISPER_MODE', 'openai')
    state, _ = local_model
    results = await asyncio.gather(*[
        adapter.transcribe_selected_audio(b'bytes', audio(),
            {'provider': 'whisper_local', 'variant': variant}, 1)
        for variant in ['small', 'large-v3-turbo']])
    assert results == ['/managed/small', '/managed/large-v3-turbo']
    assert state.peak_active == state.peak_resident == 1
    assert __import__('os').environ['WHISPER_MODE'] == 'openai'


@pytest.mark.asyncio
async def test_cancelled_queued_local_work_never_loads_or_transcribes(local_model):
    state, _ = local_model
    _LOCAL_STT_TRANSCRIBE_LOCK.acquire()
    try:
        task = asyncio.create_task(adapter.transcribe_selected_audio(b'bytes', audio(),
            {'provider': 'whisper_local', 'variant': 'small'}, 1))
        await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        _LOCAL_STT_TRANSCRIBE_LOCK.release()
    await asyncio.sleep(0.02)
    assert not state.paths and not state.inferences


@pytest.mark.asyncio
async def test_unknown_local_model_fails_without_inference_or_fallback(local_model):
    state, config = local_model
    def unknown(_): raise ValueError('unknown model')
    config._ensure_local_whisper_model_file = unknown
    with pytest.raises(adapter.TelegramSTTError, match='unsupported_configuration'):
        await adapter.transcribe_selected_audio(b'bytes', audio(),
            {'provider': 'pywhispercpp', 'variant': 'unknown'}, 1)
    assert not state.inferences and not state.paths


@pytest.mark.asyncio
async def test_selected_and_legacy_local_paths_share_actual_canonical_lock(local_model, monkeypatch):
    from TelegramVivBot.aient.aient.utils import scripts as legacy
    _, config = local_model
    config.WHISPER_MODE = 'pywhispercpp'
    class Lock:
        entries = 0
        def __enter__(self): self.entries += 1
        def __exit__(self, *_): pass
    lock = Lock()
    monkeypatch.setattr(legacy, '_LOCAL_STT_TRANSCRIBE_LOCK', lock)
    await adapter.transcribe_selected_audio(b'bytes', audio(),
        {'provider': 'pywhispercpp', 'variant': 'small'}, 1)
    assert legacy.get_audio_message(b'bytes', decoded_audio=audio(), raise_errors=True) == '/managed/small'
    assert lock.entries == 2


@pytest.fixture
def assembly(monkeypatch):
    import aiohttp
    state = types.SimpleNamespace(session_closed=False, stream_closed=False, engine_closed=False,
        constructor={}, options=None, frames=[], failure=False, hang=False, completed=False)
    class Session:
        def __init__(self, **_): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_): state.session_closed = True
    monkeypatch.setattr(aiohttp, 'ClientSession', Session)
    FINAL, INTERIM = 'final', 'interim'
    def event(kind, text):
        return types.SimpleNamespace(type=kind, alternatives=[types.SimpleNamespace(text=text)])
    class Stream:
        def __init__(self): self.end = asyncio.Event()
        def push_frame(self, frame): state.frames.append((time.monotonic(), frame))
        def end_input(self): self.end.set()
        async def aclose(self): state.stream_closed = True
        def __aiter__(self):
            async def events():
                yield event(INTERIM, 'not final')
                yield event(FINAL, 'first')
                if state.hang: await asyncio.Event().wait()
                await self.end.wait()
                if state.failure: raise RuntimeError('provider died after partial')
                yield event(FINAL, 'second')
                state.completed = True
            return events()
    class STT:
        def __init__(self, **kwargs):
            state.constructor = kwargs
            self.model = 'u3-rt-pro' if kwargs['model'] == 'u3-pro' else kwargs['model']
        def stream(self, conn_options): state.options = conn_options; return Stream()
        async def aclose(self): state.engine_closed = True
    monkeypatch.setitem(sys.modules, 'livekit.agents', types.SimpleNamespace(
        APIConnectOptions=lambda **kwargs: types.SimpleNamespace(**kwargs),
        stt=types.SimpleNamespace(SpeechEventType=types.SimpleNamespace(FINAL_TRANSCRIPT=FINAL))))
    monkeypatch.setitem(sys.modules, 'livekit.plugins', types.SimpleNamespace(
        assemblyai=types.SimpleNamespace(STT=STT)))
    monkeypatch.setenv('ASSEMBLYAI_API_KEY', 'assembly-synthetic')
    return state


@pytest.mark.asyncio
async def test_assembly_whole_pcm_ordered_finals_pacing_and_owned_session(assembly):
    pcm = np.linspace(-0.5, 0.5, 3500, dtype=np.float32)
    timings = []
    before = time.monotonic()
    result = await adapter.transcribe_selected_audio(b'original', DecodedTelegramAudio(pcm),
        {'provider': 'assemblyai', 'variant': 'u3-rt-pro'}, 1,
        timing=lambda *args: timings.append(args))
    assert result == 'first second' and assembly.completed
    assert assembly.options.max_retry == 0
    assert assembly.constructor['model'] == 'u3-rt-pro'
    assert assembly.constructor['api_key'] == 'assembly-synthetic'
    assert assembly.constructor['http_session'] is not None
    assert assembly.session_closed and assembly.stream_closed and assembly.engine_closed
    assert [frame.samples_per_channel for _, frame in assembly.frames] == [1600, 1600, 300]
    received = np.concatenate([np.frombuffer(frame.data, dtype='<i2') for _, frame in assembly.frames])
    np.testing.assert_array_equal(received, np.rint(pcm * 32767).astype('<i2'))
    assert time.monotonic() - before >= 3500 / 16000 - 0.005
    assert all(assembly.frames[i][0] - assembly.frames[i-1][0] >= 0.08 for i in (1, 2))
    assert all(set(t[2]) == {'requested_variant', 'effective_variant'} for t in timings)


@pytest.mark.asyncio
async def test_assembly_uses_compiled_call_options_and_current_context(assembly, monkeypatch):
    monkeypatch.setenv('VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD', '0.31')
    monkeypatch.setenv('VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS', '240')
    monkeypatch.setenv('VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS', '1500')
    monkeypatch.setenv('VIVENTIUM_ASSEMBLYAI_FORMAT_TURNS', 'true')
    terms = ['Example Planning Notes.pdf', 'Example Meeting']
    assert await adapter.transcribe_selected_audio(b'bytes', audio(), {
        'provider': 'assemblyai', 'variant': 'universal-streaming-multilingual',
        'contextualKeyterms': terms,
    }, 1) == 'first second'
    assert {key: assembly.constructor[key] for key in (
        'model', 'speaker_labels', 'end_of_turn_confidence_threshold',
        'min_turn_silence', 'max_turn_silence', 'format_turns', 'keyterms_prompt',
    )} == {
        'model': 'universal-streaming-multilingual', 'speaker_labels': True,
        'end_of_turn_confidence_threshold': 0.31, 'min_turn_silence': 240,
        'max_turn_silence': 1500, 'format_turns': True, 'keyterms_prompt': terms,
    }
    assert assembly.options.max_retry == 0
    assert assembly.session_closed and assembly.stream_closed and assembly.engine_closed


@pytest.mark.asyncio
async def test_documented_assembly_alias_is_supported_and_observable(assembly):
    timings = []
    assert await adapter.transcribe_selected_audio(b'bytes', audio(),
        {'provider': 'assemblyai', 'variant': 'u3-pro'}, 1,
        timing=lambda *args: timings.append(args)) == 'first second'
    assert assembly.constructor['model'] == 'u3-pro'
    assert all(t[2] == {'requested_variant': 'u3-pro', 'effective_variant': 'u3-rt-pro'} for t in timings)


@pytest.mark.asyncio
@pytest.mark.parametrize('provider,budget', [('assemblyai', 270), ('openai', 120)])
async def test_only_realtime_paced_provider_adds_whole_note_duration(monkeypatch, provider, budget):
    budgets = []
    real_timeout = asyncio.timeout
    monkeypatch.setattr(adapter.asyncio, 'timeout', lambda value: budgets.append(value) or real_timeout(value))
    async def assembly(*_): return 'complete'
    monkeypatch.setattr(adapter, '_transcribe_assemblyai', assembly)
    monkeypatch.setattr(adapter, '_transcribe_openai', lambda *_: 'complete')
    assert await adapter.transcribe_selected_audio(b'whole', audio(150 * 16000),
        {'provider': provider, 'variant': 'selected'}, 120) == 'complete'
    assert budgets == [budget]


@pytest.mark.asyncio
async def test_assembly_failure_after_partial_returns_no_partial_transcript(assembly):
    assembly.failure = True
    with pytest.raises(adapter.TelegramSTTError, match='transcription_failed'):
        await adapter.transcribe_selected_audio(b'bytes', audio(),
            {'provider': 'assemblyai', 'variant': 'kept-model'}, 1)
    assert assembly.session_closed and assembly.stream_closed and assembly.engine_closed
    assert assembly.constructor['model'] == 'kept-model'


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel', [False, True])
async def test_assembly_timeout_or_cancellation_closes_every_owner(assembly, cancel):
    assembly.hang = True
    task = asyncio.create_task(adapter.transcribe_selected_audio(b'bytes', audio(16000),
        {'provider': 'assemblyai', 'variant': 'u3-rt-pro'}, 0.03 if not cancel else 1))
    if cancel:
        await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
    else:
        with pytest.raises(adapter.TelegramSTTError, match='timeout'): await task
    assert assembly.session_closed and assembly.stream_closed and assembly.engine_closed
# === VIVENTIUM END ===

# === VIVENTIUM START ===
@pytest.mark.asyncio
@pytest.mark.parametrize('consumer', ['selected', 'legacy'])
@pytest.mark.parametrize('interval', ['zero', 'quiet', 'unknown'])
async def test_local_zero_backed_segments_preserve_full_input(local_model, consumer, interval):
    _, config = local_model
    pcm = np.zeros(48000, dtype=np.float32)
    pcm[1600] = pcm[33600] = 0.001
    if interval == 'quiet':
        pcm[24000] = np.nextafter(np.float32(0), np.float32(1))
    before = pcm.tobytes()
    calls = []
    segments = [types.SimpleNamespace(t0=0, t1=100, text='Start'),
                types.SimpleNamespace(t0=100, t1=200, text='Thank you.'),
                types.SimpleNamespace(t0=200, t1=300, text='Late')]
    if interval == 'unknown':
        segments[1].t0 = None
    def transcribe(media, **_):
        calls.append(media)
        return segments
    config.local_whisper = types.SimpleNamespace(model_path='/managed/small', transcribe=transcribe)
    config.WHISPER_MODE = 'pywhispercpp'
    decoded = DecodedTelegramAudio(pcm)
    if consumer == 'selected':
        result = await adapter.transcribe_selected_audio(b'whole-original', decoded,
            {'provider': 'pywhispercpp', 'variant': 'small'}, 1)
    else:
        result = _CANONICAL_SCRIPTS.get_audio_message(b'whole-original', decoded_audio=decoded,
                                                   raise_errors=True)
    assert result == ('Start Late' if interval == 'zero' else 'Start Thank you. Late')
    assert len(calls) == 1 and calls[0] is pcm and pcm.tobytes() == before


@pytest.mark.asyncio
@pytest.mark.parametrize('consumer', ['selected', 'legacy'])
async def test_local_all_zero_backed_segments_use_healthy_empty(local_model, consumer):
    _, config = local_model
    pcm = np.zeros(16000, dtype=np.float32)
    config.local_whisper = types.SimpleNamespace(model_path='/managed/small',
        transcribe=lambda *_args, **_kwargs: [types.SimpleNamespace(t0=0, t1=100, text='Thank you.')])
    config.WHISPER_MODE = 'pywhispercpp'
    decoded = DecodedTelegramAudio(pcm)
    if consumer == 'selected':
        with pytest.raises(adapter.TelegramSTTError) as error:
            await adapter.transcribe_selected_audio(b'whole-original', decoded,
                {'provider': 'pywhispercpp', 'variant': 'small'}, 1)
        assert error.value.code == 'no_speech'
    else:
        result = _CANONICAL_SCRIPTS.get_audio_message(b'whole-original', decoded_audio=decoded,
                                                   raise_errors=True)
        assert result == ''
# === VIVENTIUM END ===
