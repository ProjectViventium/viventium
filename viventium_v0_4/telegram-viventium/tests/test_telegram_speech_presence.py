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


@pytest.mark.asyncio
async def test_presence_acceptance_preserves_whole_original_bytes_and_pcm(monkeypatch):
    pcm = np.linspace(-0.001, 0.001, 80000, dtype=np.float32)
    decoded = telegram_audio.DecodedTelegramAudio(pcm)
    seen = []
    async def presence(value):
        assert value is pcm
        return True
    async def recognize(data, audio, selection, timeout, **_):
        seen.append((data, audio, selection))
        assert audio.pcm is pcm
        np.testing.assert_array_equal(audio.pcm, pcm)
        return 'Beginning and paused tail.'
    monkeypatch.setattr(telegram_vad, 'has_speech', presence)
    monkeypatch.setattr(telegram_stt, 'transcribe_selected_audio', recognize)
    selection = {'provider': 'openai', 'variant': 'whisper-1'}
    assert await scripts._transcribe_audio_bytes(b'whole original', 1,
        decoded_audio=decoded, selection=selection) == 'Beginning and paused tail.'
    assert seen == [(b'whole original', decoded, selection)]


@pytest.mark.asyncio
async def test_nonzero_no_speech_stops_every_selected_engine(monkeypatch):
    async def absent(_): return False
    async def never(*_, **__): pytest.fail('No speech cannot call provider')
    monkeypatch.setattr(telegram_vad, 'has_speech', absent)
    monkeypatch.setattr(telegram_stt, 'transcribe_selected_audio', never)
    for provider in ('pywhispercpp', 'openai', 'assemblyai'):
        with pytest.raises(telegram_audio.TelegramAudioDecodeError, match='no_speech'):
            await scripts._transcribe_audio_bytes(b'original', 1,
                decoded_audio=telegram_audio.DecodedTelegramAudio(np.full(16000, 0.01, dtype=np.float32)),
                selection={'provider': provider, 'variant': 'selected'})


@pytest.mark.asyncio
async def test_exact_zero_bypasses_presence_and_provider(monkeypatch):
    async def never(*_, **__): pytest.fail('Exact zero cannot call VAD/provider')
    monkeypatch.setattr(telegram_vad, 'has_speech', never)
    monkeypatch.setattr(telegram_stt, 'transcribe_selected_audio', never)
    with pytest.raises(telegram_audio.TelegramAudioDecodeError, match='no_speech'):
        await scripts._transcribe_audio_bytes(b'original', 1,
            decoded_audio=telegram_audio.DecodedTelegramAudio(np.array([], dtype=np.float32), no_speech=True),
            selection={'provider': 'openai', 'variant': 'whisper-1'})


@pytest.mark.asyncio
async def test_missing_presence_dependency_is_unavailable_not_no_speech(monkeypatch):
    async def missing(_): raise ImportError('fixture missing SDK')
    monkeypatch.setattr(telegram_vad, 'has_speech', missing)
    with pytest.raises(telegram_stt.TelegramSTTError, match='speech_presence_unavailable'):
        await scripts._transcribe_audio_bytes(b'original', 1,
            decoded_audio=telegram_audio.DecodedTelegramAudio(np.full(16000, 0.01, dtype=np.float32)),
            selection={'provider': 'openai', 'variant': 'whisper-1'})
