"""Real buffered media checks; no provider or Telegram network calls."""
from io import BytesIO
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import wave
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from telegram_audio import finalize_wav_chunks, package_telegram_audio, TelegramAudioError

def wav_bytes(seconds=0.25):
    output = BytesIO()
    with wave.open(output, 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000)
        f.writeframes(b''.join(struct.pack('<h', int(5000*math.sin(i*0.07))) for i in range(int(seconds*16000))))
    return output.getvalue()

def streamed(data):
    value=bytearray(data); value[4:8]=struct.pack('<I',0xffffffff); value[40:44]=struct.pack('<I',0xffffffff)
    return bytes(value)

def test_single_streamed_wav_finalizes_exact_pcm_and_duration():
    original=wav_bytes(); result=finalize_wav_chunks([streamed(original)])
    assert result == original
    assert struct.unpack_from('<I', result,4)[0] == len(result)-8
    with wave.open(BytesIO(result),'rb') as f:
        assert f.getnframes()==4000
        assert f.getnframes()/f.getframerate()==0.25

def test_multiple_streamed_wav_keeps_all_pcm():
    result=finalize_wav_chunks([streamed(wav_bytes()),streamed(wav_bytes())])
    with wave.open(BytesIO(result),'rb') as f:
        assert f.getnframes()==8000

def test_empty_and_partial_wav_fail_before_transport():
    with pytest.raises(TelegramAudioError):
        package_telegram_audio(b'')
    with pytest.raises(TelegramAudioError):
        finalize_wav_chunks([streamed(wav_bytes())[:-1]])
    with pytest.raises(TelegramAudioError, match='audio_truncated'):
        finalize_wav_chunks([wav_bytes()[:-2]])

@pytest.fixture
def media_tools():
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('Existing FFmpeg/ffprobe prerequisite unavailable')

def test_streamed_wav_becomes_supported_mp3_with_measured_duration(media_tools):
    media=package_telegram_audio(streamed(wav_bytes()))
    assert media.filename=='Voice.mp3' and media.content_type=='audio/mpeg'
    assert 0.25 <= media.duration_seconds < 0.4
    assert media.duration==1
    assert media.data[:4] != b'RIFF'

def test_compatible_mp3_keeps_native_bytes(media_tools):
    media=package_telegram_audio(wav_bytes())
    again=package_telegram_audio(media.data)
    assert again==media

def test_multiple_native_mp3_chunks_have_complete_duration(media_tools):
    media=package_telegram_audio(wav_bytes())
    combined=package_telegram_audio([media.data,media.data])
    assert combined.duration_seconds == pytest.approx(0.5, abs=0.05)

def test_compatible_m4a_keeps_native_bytes(media_tools,tmp_path):
    source=tmp_path/'input.wav'; target=tmp_path/'input.m4a'; source.write_bytes(wav_bytes())
    subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(source),'-c:a','aac',str(target)],check=True)
    data=target.read_bytes(); media=package_telegram_audio(data)
    assert media.data==data and media.filename=='Voice.m4a' and media.content_type=='audio/mp4'

def test_missing_media_probe_is_classified_before_transport(monkeypatch):
    monkeypatch.setattr(shutil,'which',lambda _name:None)
    with pytest.raises(TelegramAudioError,match='media_probe_unavailable'):
        package_telegram_audio(wav_bytes())
