import asyncio
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT, ROOT / 'TelegramVivBot'):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
sys.modules.setdefault('config', types.SimpleNamespace(VIVENTIUM_TELEGRAM_BACKEND='librechat'))
from TelegramVivBot.utils import scripts


def route(provider='pywhispercpp', variant='large-v3-turbo', source='saved'):
    return {'stt': {'provider': provider, 'variant': variant, 'source': source}}


@pytest.mark.parametrize('provider,variant', [
    ('pywhispercpp', 'small'), ('openai', 'whisper-1'),
    ('openai', 'gpt-4o-transcribe'), ('assemblyai', 'universal-streaming-multilingual'),
])
def test_saved_choice_wins_over_explicit_telegram_and_global_defaults(provider, variant):
    assert scripts.resolve_telegram_listening_selection(route(provider, variant), environment={
        'VIVENTIUM_TELEGRAM_STT_PROVIDER': 'openai',
        'VIVENTIUM_TELEGRAM_STT_PROVIDER_SOURCE': 'explicit',
        'VIVENTIUM_OPENAI_STT_MODEL': 'gpt-4o-mini-transcribe',
    }) == {'provider': provider, 'variant': variant}


@pytest.mark.parametrize('provider,variant', [
    ('openai', 'gpt-4o-mini-transcribe'), ('assemblyai', 'u3-rt-pro'),
    ('whisper_local', 'large-v3-turbo'), ('pywhispercpp', 'large-v3-turbo'),
])
def test_explicit_telegram_default_is_used_only_without_saved_choice(provider, variant):
    assert scripts.resolve_telegram_listening_selection(route(source='default'), environment={
        'VIVENTIUM_TELEGRAM_STT_PROVIDER': provider,
        'VIVENTIUM_TELEGRAM_STT_PROVIDER_SOURCE': 'explicit',
        'LOCAL_WHISPER_MODEL_NAME': 'large-v3-turbo',
    }) == {'provider': 'pywhispercpp' if provider == 'whisper_local' else provider, 'variant': variant}


def test_inherited_default_preserves_fresh_global_variant():
    assert scripts.resolve_telegram_listening_selection(route(variant='small', source='default'),
        environment={'VIVENTIUM_TELEGRAM_STT_PROVIDER': 'whisper_local',
                     'VIVENTIUM_TELEGRAM_STT_PROVIDER_SOURCE': 'inherited'}) == {
        'provider': 'pywhispercpp', 'variant': 'small',
    }


def test_no_telegram_default_uses_current_global_route():
    assert scripts.resolve_telegram_listening_selection(route('assemblyai', 'u3-rt-pro', 'default'),
        environment={}) == {'provider': 'assemblyai', 'variant': 'u3-rt-pro'}


@pytest.mark.parametrize('value', [{}, {'stt': {}}, route(source='unknown')])
def test_missing_route_provenance_never_falls_back(value):
    with pytest.raises(ValueError):
        scripts.resolve_telegram_listening_selection(value, environment={})


@pytest.mark.parametrize('source', ['saved', 'default'])
@pytest.mark.parametrize('override', ['', 'assemblyai', 'openai'])
def test_current_context_survives_saved_and_default_selection(source, override):
    current = route('assemblyai', 'universal-streaming-multilingual', source)
    current['contextualKeyterms'] = ['Example Meeting']
    selected = scripts.resolve_telegram_listening_selection(current, environment={
        'VIVENTIUM_TELEGRAM_STT_PROVIDER': override,
        'VIVENTIUM_TELEGRAM_STT_PROVIDER_SOURCE': 'explicit',
        'LOCAL_WHISPER_MODEL_NAME': 'small',
    })
    assert selected['contextualKeyterms'] == ['Example Meeting']
    assert current['contextualKeyterms'] == ['Example Meeting']


@pytest.mark.asyncio
async def test_route_and_download_overlap_and_incoming_owner_is_preserved(monkeypatch):
    download_started = asyncio.Event()
    route_started = asyncio.Event()
    captured = []
    async def current(**identity):
        captured.append(identity)
        route_started.set()
        await download_started.wait()
        return route('openai', 'whisper-1')
    async def download(*_args, **_kwargs):
        download_started.set()
        await route_started.wait()
        return scripts.TelegramDownloadResult(file_bytes=b'exact-note')
    monkeypatch.setattr(scripts.config, 'ChatGPTbot', types.SimpleNamespace(get_voice_route=current), raising=False)
    monkeypatch.setattr(scripts, 'download_telegram_file_result', download)
    result, selection = await asyncio.wait_for(scripts._download_transcription_input('note',
        types.SimpleNamespace(bot=object()), filename='note.ogg', mime_type='audio/ogg',
        telegram_user_id='owner-a', telegram_chat_id='chat-a'), timeout=0.5)
    assert captured == [{'telegram_user_id': 'owner-a', 'telegram_chat_id': 'chat-a'}]
    assert result.file_bytes == b'exact-note'
    assert selection == {'provider': 'openai', 'variant': 'whisper-1'}


@pytest.mark.asyncio
async def test_route_failure_stops_transcription_instead_of_using_old_cache(monkeypatch):
    async def current(**_identity):
        raise RuntimeError('unavailable')
    async def download(*_args, **_kwargs):
        return scripts.TelegramDownloadResult(file_bytes=b'exact-note')
    async def never_transcribe(*_args, **_kwargs):
        raise AssertionError('route failure cannot call any transcriber')
    monkeypatch.setattr(scripts.config, 'ChatGPTbot', types.SimpleNamespace(
        get_voice_route=current, get_cached_voice_route=lambda _chat: route()), raising=False)
    monkeypatch.setattr(scripts, 'download_telegram_file_result', download)
    monkeypatch.setattr(scripts, '_transcribe_audio_bytes', never_transcribe)
    result = await scripts.get_voice('note', types.SimpleNamespace(bot=object()),
        telegram_user_id='owner-a', telegram_chat_id='chat-a')
    assert result.text is None
    assert result.error_code == 'voice_route_unavailable'


@pytest.mark.asyncio
async def test_failed_download_cancels_and_drains_independent_route(monkeypatch):
    started = asyncio.Event()
    stopped = asyncio.Event()
    async def current(**_identity):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()
    async def download(*_args, **_kwargs):
        await started.wait()
        return scripts.TelegramDownloadResult(error_code='file_too_large')
    monkeypatch.setattr(scripts.config, 'ChatGPTbot', types.SimpleNamespace(get_voice_route=current), raising=False)
    monkeypatch.setattr(scripts, 'download_telegram_file_result', download)
    result, selection = await scripts._download_transcription_input('note',
        types.SimpleNamespace(bot=object()), filename='note.ogg', mime_type='audio/ogg',
        telegram_user_id='owner-a', telegram_chat_id='chat-a')
    assert result.error_code == 'file_too_large'
    assert selection is None
    assert stopped.is_set()


def test_no_speech_notice_preserves_typed_code_through_string_courier():
    result = scripts.TelegramTranscriptionResult(error_text='No speech was detected.', error_code='no_speech')
    assert isinstance(result.error_text, str)
    assert result.error_text == 'No speech was detected.'
    assert result.error_text.error_code == 'no_speech'
