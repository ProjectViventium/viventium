# === VIVENTIUM START ===
"""Actual incoming Telegram identity reaches the current saved Listening route."""
import asyncio
import sys
import types
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT, ROOT / 'TelegramVivBot'):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
sys.modules.setdefault('config', types.SimpleNamespace(VIVENTIUM_TELEGRAM_BACKEND='librechat'))
from TelegramVivBot.utils import scripts, telegram_audio, telegram_stt, telegram_vad


def message(owner='owner-a', kind='voice', caption=None):
    value = types.SimpleNamespace(
        chat_id='shared-chat', from_user=types.SimpleNamespace(id=owner),
        is_topic_message=True, message_thread_id=9, message_id=17, text=None,
        reply_to_message=None, photo=None, voice=None, audio=None, video_note=None,
        video=None, document=None, caption=caption, chat=types.SimpleNamespace(type='group'),
    )
    setattr(value, kind, types.SimpleNamespace(file_id=owner))
    return value


@pytest.fixture(autouse=True)
def valid_audio_and_config(monkeypatch):
    # This bank isolates identity/status using synthetic PCM, not speech audio.
    async def admitted_speech(_pcm): return True
    monkeypatch.setattr(telegram_vad, 'has_speech', admitted_speech)
    monkeypatch.setattr(telegram_audio, 'decode_audio_bytes', lambda *_:
        telegram_audio.DecodedTelegramAudio(np.full(1600, 0.001, dtype=np.float32)))
    for config in (scripts.config, sys.modules['config']):
        monkeypatch.setattr(config, 'VIVENTIUM_TELEGRAM_BACKEND', 'librechat', raising=False)
        monkeypatch.setattr(config, 'NICK', None, raising=False)
    async def download(_bot, file_id, **_kwargs):
        return scripts.TelegramDownloadResult(file_bytes=file_id.encode(), filename='note.ogg')
    monkeypatch.setattr(scripts, 'download_telegram_file_result', download)


def use_saved_route(monkeypatch, *, variant='whisper-1'):
    calls = []
    async def current(**identity):
        calls.append(identity)
        return {'stt': {'provider': 'openai', 'variant': variant, 'source': 'saved'}}
    monkeypatch.setattr(scripts.config, 'ChatGPTbot', types.SimpleNamespace(get_voice_route=current), raising=False)
    return calls


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['voice', 'video_note'])
async def test_actual_get_message_forwards_incoming_identity_and_keeps_caption(monkeypatch, kind):
    calls = use_saved_route(monkeypatch)
    selected = []
    def inference(data, variant, *_):
        selected.append((data, variant))
        return 'A useful exact transcript.'
    monkeypatch.setattr(telegram_stt, '_transcribe_openai', inference)
    caption = '  Keep this caption.\nSecond line.'
    result = await scripts.GetMesage(message(kind=kind, caption=caption), types.SimpleNamespace(bot=object()))
    assert calls == [{'telegram_user_id': 'owner-a', 'telegram_chat_id': 'shared-chat', 'telegram_message_thread_id': 9}]
    assert selected == [(b'owner-a', 'whisper-1')]
    assert len(result) == 14
    assert result[0:2] == (caption, caption)
    assert result[6:8] == (9, 'shared-chat:9:owner-a')
    assert result[10:12] == ('A useful exact transcript.', None)
    assert result[-2:] == ([], [])


@pytest.mark.asyncio
async def test_concurrent_incoming_group_owners_get_their_own_fresh_selections(monkeypatch):
    identities, inferences = [], []
    both = asyncio.Event()
    async def current(**identity):
        identities.append(identity)
        if len(identities) == 2: both.set()
        await both.wait()
        model = 'whisper-1' if identity['telegram_user_id'] == 'owner-a' else 'gpt-4o-transcribe'
        return {'stt': {'provider': 'openai', 'variant': model, 'source': 'saved'}}
    monkeypatch.setattr(scripts.config, 'ChatGPTbot', types.SimpleNamespace(get_voice_route=current), raising=False)
    def inference(data, variant, *_):
        inferences.append((data, variant))
        return data.decode() + ' transcript'
    monkeypatch.setattr(telegram_stt, '_transcribe_openai', inference)
    first, second = await asyncio.wait_for(asyncio.gather(
        scripts.GetMesage(message('owner-a'), types.SimpleNamespace(bot=object())),
        scripts.GetMesage(message('owner-b', 'video_note'), types.SimpleNamespace(bot=object())),
    ), 1)
    assert {tuple(sorted(i.items())) for i in identities} == {
        (('telegram_chat_id', 'shared-chat'), ('telegram_message_thread_id', 9), ('telegram_user_id', 'owner-a')),
        (('telegram_chat_id', 'shared-chat'), ('telegram_message_thread_id', 9), ('telegram_user_id', 'owner-b')),
    }
    assert sorted(inferences) == [(b'owner-a', 'whisper-1'), (b'owner-b', 'gpt-4o-transcribe')]
    assert first[7] == 'shared-chat:9:owner-a' and second[7] == 'shared-chat:9:owner-b'
    assert first[10] == 'owner-a transcript' and second[10] == 'owner-b transcript'


@pytest.mark.asyncio
async def test_existing_get_message_info_tuple_keeps_current_owner_and_notice_slots(monkeypatch):
    calls = use_saved_route(monkeypatch)
    monkeypatch.setattr(telegram_stt, '_transcribe_openai', lambda *_: 'Spoken message')
    update_message = message()
    result = await scripts.GetMesageInfo(types.SimpleNamespace(edited_message=None, callback_query=None, message=update_message),
                                         types.SimpleNamespace(bot=object()))
    assert len(result) == 15
    assert result[6] is update_message
    assert result[8] == 'shared-chat:9:owner-a'
    assert result[11:13] == ('Spoken message', None)
    assert calls == [{'telegram_user_id': 'owner-a', 'telegram_chat_id': 'shared-chat', 'telegram_message_thread_id': 9}]


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['voice', 'video_note'])
@pytest.mark.parametrize('caption', [None, 'Keep the authored caption.'])
async def test_healthy_empty_provider_has_no_speech_notice_and_preserves_caption(monkeypatch, kind, caption):
    use_saved_route(monkeypatch)
    monkeypatch.setattr(telegram_stt, '_transcribe_openai', lambda *_: '')
    result = await scripts.GetMesage(message(kind=kind, caption=caption), types.SimpleNamespace(bot=object()))
    assert result[0:2] == (caption, caption)
    assert result[10] is None
    if caption:
        assert result[11] is None
    else:
        label = 'voice note' if kind == 'voice' else 'video note'
        assert result[11] == f'No speech was detected in this {label}.'
        assert result[11].error_code == 'no_speech'


@pytest.mark.asyncio
@pytest.mark.parametrize('code', ['provider_unavailable', 'unsupported_configuration', 'timeout', 'transcription_failed'])
@pytest.mark.parametrize('kind', ['voice', 'video_note'])
async def test_provider_error_code_survives_existing_message_tuple(monkeypatch, code, kind):
    use_saved_route(monkeypatch)
    def fail(*_): raise telegram_stt.TelegramSTTError(code)
    monkeypatch.setattr(telegram_stt, '_transcribe_openai', fail)
    result = await scripts.GetMesage(message(kind=kind), types.SimpleNamespace(bot=object()))
    assert result[10] is None
    assert isinstance(result[11], str)
    assert result[11].error_code == code
    assert result[-2:] == ([], [])


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['voice', 'video_note'])
async def test_healthy_transcript_text_is_not_a_provider_error(monkeypatch, kind):
    use_saved_route(monkeypatch)
    authored_speech = 'error: the document is missing.'
    monkeypatch.setattr(telegram_stt, '_transcribe_openai', lambda *_: authored_speech)
    result = await scripts.GetMesage(message(kind=kind), types.SimpleNamespace(bot=object()))
    assert result[10:12] == (authored_speech, None)
# === VIVENTIUM END ===
