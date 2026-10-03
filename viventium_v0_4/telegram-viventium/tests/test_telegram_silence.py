# === VIVENTIUM START ===
# Exact decoded digital silence is no speech; quiet/nonzero audio is not silence.
import asyncio
import struct
import sys
import types
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / 'TelegramVivBot'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
sys.modules.setdefault('config', types.SimpleNamespace(VIVENTIUM_TELEGRAM_BACKEND='librechat'))
from TelegramVivBot.utils import scripts, telegram_vad


@pytest.fixture(autouse=True)
def separate_silence_decode_from_speech_presence(monkeypatch):
    # Exact-zero and float precision belong to this decoder bank. The actual
    # speech-presence bank uses real spoken/noise fixtures through Silero.
    async def admitted_speech(_pcm): return True
    monkeypatch.setattr(telegram_vad, 'has_speech', admitted_speech)


def float_wav(samples, rate=16000, channels=1):
    data = np.asarray(samples, dtype='<f4').tobytes()
    fmt = struct.pack('<HHIIHH', 3, channels, rate, rate * channels * 4, channels * 4, 32)
    payload = b'fmt ' + struct.pack('<I', len(fmt)) + fmt + b'data' + struct.pack('<I', len(data)) + data
    return b'RIFF' + struct.pack('<I', 4 + len(payload)) + b'WAVE' + payload


def configure_voice(monkeypatch, data, transcript='Thank you.'):
    calls = []
    async def download(*_args, **_kwargs):
        return scripts.TelegramDownloadResult(file_bytes=data, filename='note.wav')
    def transcribe(_bytes, **_kwargs):
        calls.append(_bytes)
        return transcript
    async def current_route(**identity):
        assert identity == {'telegram_user_id': 'owner', 'telegram_chat_id': 'chat'}
        return {'stt': {'provider': 'pywhispercpp', 'variant': 'large-v3-turbo', 'source': 'saved'}}
    monkeypatch.setattr(scripts, 'download_telegram_file_result', download)
    monkeypatch.setattr(scripts, '_get_audio_message_sync', transcribe)
    monkeypatch.setattr(scripts.config, 'WHISPER_MODE', 'pywhispercpp', raising=False)
    monkeypatch.setattr(scripts.config, 'ChatGPTbot',
                        types.SimpleNamespace(get_voice_route=current_route), raising=False)
    monkeypatch.setattr(scripts, 'ffmpeg_runtime_ready', lambda: True)
    return calls


def test_exact_silent_voice_note_does_not_call_transcriber(monkeypatch):
    calls = configure_voice(monkeypatch, float_wav(np.zeros(1600)))
    result = asyncio.run(scripts.get_voice('note', types.SimpleNamespace(bot=object())))
    assert result.error_code == 'no_speech'
    assert result.text is None
    assert result.error_text == 'No speech was detected in this voice note.'
    assert calls == []


def test_quiet_nonzero_voice_note_keeps_transcriber(monkeypatch):
    samples = np.zeros(1600, dtype=np.float32)
    samples[123] = 1e-8
    calls = configure_voice(monkeypatch, float_wav(samples), transcript='Thank you.')
    result = asyncio.run(scripts.get_voice('note', types.SimpleNamespace(bot=object())))
    assert result.text == 'Thank you.'
    assert result.error_code is None
    assert len(calls) == 1


def test_exact_silent_video_note_does_not_call_transcriber(monkeypatch):
    calls = configure_voice(monkeypatch, float_wav(np.zeros(1600)))
    result = asyncio.run(scripts.transcribe_video('note', types.SimpleNamespace(bot=object())))
    assert result.error_code == 'no_speech'
    assert result.text is None
    assert calls == []


@pytest.mark.parametrize('rate,channels', [(16000, 1), (48000, 2)])
def test_preserved_source_exact_zero(rate, channels):
    from TelegramVivBot.utils.telegram_audio import decode_audio_bytes
    result = decode_audio_bytes(float_wav(np.zeros(rate // 20 * channels), rate, channels))
    assert result.no_speech is True
    assert result.pcm.size == 0


@pytest.mark.parametrize('level', [1e-3, 1e-8])
def test_single_quiet_nonzero_sample_is_not_silence(level):
    from TelegramVivBot.utils.telegram_audio import decode_audio_bytes
    samples = np.zeros(1600, dtype=np.float32)
    samples[80] = level
    result = decode_audio_bytes(float_wav(samples))
    assert result.no_speech is False
    assert result.pcm.dtype == np.float32
    assert result.pcm[80] == samples[80]


def test_opposite_stereo_channels_are_not_source_silence():
    from TelegramVivBot.utils.telegram_audio import decode_audio_bytes
    samples = np.tile([0.1, -0.1], 1600)
    result = decode_audio_bytes(float_wav(samples, channels=2))
    assert result.no_speech is False
    # ffmpeg's default matrix has tiny rounding residue; source classification is independent.
    assert np.max(np.abs(result.pcm)) < 1e-7


@pytest.mark.parametrize('sample', [np.nan, np.inf, -np.inf])
def test_nonfinite_source_is_an_error_not_no_speech(sample):
    from TelegramVivBot.utils.telegram_audio import decode_audio_bytes, TelegramAudioDecodeError
    with pytest.raises(TelegramAudioDecodeError) as exc:
        decode_audio_bytes(float_wav([0, sample, 0]))
    assert exc.value.code == 'audio_nonfinite'


@pytest.mark.parametrize('data,code', [(b'', 'audio_empty'), (b'corrupt media', 'audio_decode_failed'),
                                     (float_wav([]), 'audio_empty')])
def test_empty_and_corrupt_audio_are_not_no_speech(data, code):
    from TelegramVivBot.utils.telegram_audio import decode_audio_bytes, TelegramAudioDecodeError
    with pytest.raises(TelegramAudioDecodeError) as exc:
        decode_audio_bytes(data)
    assert exc.value.code == code


def test_decoder_unavailable_and_timeout_stay_distinct(monkeypatch):
    from TelegramVivBot.utils import telegram_audio
    monkeypatch.setattr(telegram_audio.shutil, 'which', lambda *_: None)
    with pytest.raises(telegram_audio.TelegramAudioDecodeError) as exc:
        telegram_audio.decode_audio_bytes(b'input')
    assert exc.value.code == 'media_decoder_unavailable'
    monkeypatch.setattr(telegram_audio.shutil, 'which', lambda *_: 'ffmpeg')
    def timeout(*args, **_kwargs):
        raise telegram_audio.subprocess.TimeoutExpired(args[0], 1)
    monkeypatch.setattr(telegram_audio.subprocess, 'run', timeout)
    with pytest.raises(telegram_audio.TelegramAudioDecodeError) as exc:
        telegram_audio.decode_audio_bytes(b'input')
    assert exc.value.code == 'timeout'


def message(kind, caption=None):
    value = types.SimpleNamespace(
        chat_id='chat', from_user=types.SimpleNamespace(id='owner'), is_topic_message=False,
        message_id=17, text=None, reply_to_message=None, photo=None, voice=None,
        audio=None, video_note=None, video=None, document=None, caption=caption,
        chat=types.SimpleNamespace(type='private'),
    )
    setattr(value, kind, types.SimpleNamespace(file_id='note'))
    return value


@pytest.mark.parametrize('kind', ['voice', 'video_note'])
@pytest.mark.parametrize('caption', [None, '  Keep my exact caption.\nSecond line.'])
def test_silent_media_preserves_caption_without_invented_transcript(monkeypatch, kind, caption):
    calls = configure_voice(monkeypatch, float_wav(np.zeros(1600)))
    monkeypatch.setattr(sys.modules['config'], 'NICK', None, raising=False)
    result = asyncio.run(scripts.GetMesage(message(kind, caption), types.SimpleNamespace(bot=object())))
    assert result[0] == caption
    assert result[1] == caption
    assert result[10] is None
    assert result[11] == (None if caption else f'No speech was detected in this {"voice note" if kind == "voice" else "video note"}.')
    assert result[-2] == []
    assert calls == []


def test_silent_note_does_not_block_next_input(monkeypatch):
    calls = []
    async def download(_bot, file_id, **_kwargs):
        pcm = np.zeros(1600) if file_id == 'first' else np.full(1600, 0.001)
        return scripts.TelegramDownloadResult(file_bytes=float_wav(pcm))
    def transcribe(_bytes, **_kwargs):
        calls.append('second')
        return 'OK'
    monkeypatch.setattr(scripts, 'download_telegram_file_result', download)
    monkeypatch.setattr(scripts, '_get_audio_message_sync', transcribe)
    monkeypatch.setattr(scripts, 'ffmpeg_runtime_ready', lambda: True)
    async def pair():
        context = types.SimpleNamespace(bot=object())
        first = await scripts.get_voice('first', context)
        second = await scripts.get_voice('second', context)
        return first, second
    first, second = asyncio.run(pair())
    assert first.error_code == 'no_speech'
    assert second.text == 'OK'
    assert calls == ['second']


def test_reused_decoded_audio_does_not_decode_again(monkeypatch):
    from TelegramVivBot.utils import telegram_audio
    pcm = np.full(1600, 0.001, dtype=np.float32)
    decoded = telegram_audio.DecodedTelegramAudio(pcm)
    def do_not_decode(*_args, **_kwargs):
        raise AssertionError('Already decoded current media must be reused')
    def transcribe(data, **kwargs):
        assert data == b'original bytes'
        assert kwargs['decoded_audio'] is decoded
        return 'Thank you.'
    monkeypatch.setattr(telegram_audio, 'decode_audio_bytes', do_not_decode)
    monkeypatch.setattr(scripts, '_get_audio_message_sync', transcribe)
    result = asyncio.run(scripts._transcribe_audio_bytes(b'original bytes', 1, decoded_audio=decoded))
    assert result == 'Thank you.'


def test_silent_audio_file_skips_model_initialization(monkeypatch):
    from TelegramVivBot.aient.aient.utils.scripts import get_audio_message
    def must_not_initialize():
        raise AssertionError('Silence must not initialize or call an STT model')
    monkeypatch.setitem(sys.modules, 'config', types.SimpleNamespace(
        WHISPER_MODE='pywhispercpp', local_whisper=None, ensure_stt_engine=must_not_initialize,
    ))
    assert get_audio_message(float_wav(np.zeros(1600))) == ''


def test_audio_file_passes_float32_to_existing_local_model(monkeypatch):
    from TelegramVivBot.aient.aient.utils.scripts import get_audio_message
    calls = []
    class Model:
        def transcribe(self, pcm, **kwargs):
            assert isinstance(pcm, np.ndarray)
            assert pcm.dtype == np.float32
            assert pcm[80] == np.float32(1e-8)
            assert kwargs == {'language': '', 'translate': False, 'print_realtime': False}
            calls.append(pcm)
            return [types.SimpleNamespace(text='OK')]
    monkeypatch.setitem(sys.modules, 'config', types.SimpleNamespace(
        WHISPER_MODE='pywhispercpp', local_whisper=Model(),
        LOCAL_WHISPER_LANG='auto', LOCAL_WHISPER_VERBOSE=False,
    ))
    samples = np.zeros(1600, dtype=np.float32)
    samples[80] = 1e-8
    assert get_audio_message(float_wav(samples)) == 'OK'
    assert len(calls) == 1

# === VIVENTIUM END ===
