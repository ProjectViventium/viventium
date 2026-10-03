# === VIVENTIUM START ===
"""Voice helpers must work in bot.py's direct entry and package-only imports."""
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROBE = textwrap.dedent("""
    import asyncio
    import importlib
    import sys
    import threading
    import time
    import types

    import numpy as np

    entry, case = sys.argv[1:]
    prefix = 'utils' if entry == 'direct' else 'TelegramVivBot.utils'
    legacy_prefix = 'aient.aient' if entry == 'direct' else 'TelegramVivBot.aient.aient'
    # Configuration startup can create a live bot. This probe loads real helpers
    # and dependencies but provides no credentials, config startup or model call.
    sys.modules['config'] = types.SimpleNamespace(WHISPER_MODE='local')
    scripts = (importlib.import_module(prefix + '.scripts')
               if case not in ('assemblyai', 'openai', 'local') else None)
    audio = importlib.import_module(prefix + '.telegram_audio')
    adapter = importlib.import_module(prefix + '.telegram_stt')
    decoded = audio.DecodedTelegramAudio(np.ones(160, dtype=np.float32), no_speech=True)

    def expect_error(function, error_type, code):
        try:
            function()
        except error_type as error:
            assert error.code == code, error
        else:
            raise AssertionError('Expected typed error: ' + code)

    if case == 'handlers':
        async def unavailable(*args, **kwargs):
            return scripts.TelegramDownloadResult(error_code='download_timeout'), None
        scripts._download_transcription_input = unavailable
        scripts.ffmpeg_runtime_ready = lambda: True
        for handler in (scripts.get_voice, scripts.transcribe_video):
            result = asyncio.run(handler('synthetic-file', types.SimpleNamespace()))
            assert result.error_code == 'download_timeout', result
            assert result.text is None
    elif case == 'settings':
        route = {'stt': {'provider': 'assemblyai', 'variant': 'u3-rt-pro', 'source': 'saved'},
                 'contextualKeyterms': ['Example Meeting']}
        assert scripts.resolve_telegram_listening_selection(route, environment={}) == {
            'provider': 'assemblyai', 'variant': 'u3-rt-pro',
            'contextualKeyterms': ['Example Meeting']}
        bridge = importlib.import_module(prefix + '.librechat_bridge')
        assert bridge._normalize_voice_route(route) == route
    elif case == 'silence':
        expect_error(lambda: asyncio.run(scripts._transcribe_audio_bytes(
            b'original', 1, decoded_audio=decoded)), audio.TelegramAudioDecodeError, 'no_speech')
    elif case == 'presence':
        vad = importlib.import_module(prefix + '.telegram_vad')
        async def no_speech(pcm):
            return False
        vad.has_speech = no_speech
        spoken = audio.DecodedTelegramAudio(np.ones(160, dtype=np.float32))
        expect_error(lambda: asyncio.run(scripts._transcribe_audio_bytes(
            b'original', 1, decoded_audio=spoken)), audio.TelegramAudioDecodeError, 'no_speech')
    elif case == 'assemblyai':
        expect_error(lambda: asyncio.run(adapter._transcribe_assemblyai(
            decoded.pcm, 'u3-rt-pro', time.monotonic(), None)),
            adapter.TelegramSTTError, 'provider_unavailable')
    elif case == 'openai':
        expect_error(lambda: adapter._transcribe_openai(
            b'original', 'whisper-1', 1, threading.Event(), time.monotonic(), None),
            adapter.TelegramSTTError, 'provider_auth_missing')
    elif case == 'local':
        cancelled = threading.Event()
        cancelled.set()
        expect_error(lambda: adapter._transcribe_local(
            decoded.pcm, 'small', cancelled, time.monotonic(), None),
            adapter.TelegramSTTError, 'cancelled')
    elif case == 'legacy':
        legacy = importlib.import_module(legacy_prefix + '.utils.scripts')
        expect_error(lambda: legacy.get_audio_message(b'original', decoded_audio=decoded,
            raise_errors=True), audio.TelegramAudioDecodeError, 'no_speech')
    elif case == 'legacy_wrapper':
        expect_error(lambda: scripts._get_audio_message_sync(b'original', decoded_audio=decoded),
            audio.TelegramAudioDecodeError, 'no_speech')
    elif case == 'shared_lock':
        legacy = importlib.import_module(legacy_prefix + '.utils.scripts')
        class Lock:
            entries = 0
            def __enter__(self):
                self.entries += 1
            def __exit__(self, *args):
                pass
        lock = Lock()
        legacy._LOCAL_STT_TRANSCRIBE_LOCK = lock
        cancelled = threading.Event()
        cancelled.set()
        expect_error(lambda: adapter._transcribe_local(
            decoded.pcm, 'small', cancelled, time.monotonic(), None),
            adapter.TelegramSTTError, 'cancelled')
        config = sys.modules['config']
        config.local_whisper = types.SimpleNamespace(
            transcribe=lambda pcm, **kwargs: [types.SimpleNamespace(text='source kept')])
        config.LOCAL_WHISPER_LANG = 'auto'
        config.LOCAL_WHISPER_VERBOSE = False
        spoken = audio.DecodedTelegramAudio(decoded.pcm)
        assert scripts._get_audio_message_sync(b'original', decoded_audio=spoken) == 'source kept'
        assert lock.entries == 2
    else:
        raise AssertionError(case)
    # The probe adds no import roots or aliases. Legacy scripts.py itself adds
    # its bot directory for aient; direct entry still cannot import the parent.
    if entry == 'direct':
        assert 'TelegramVivBot' not in sys.modules
    print('PASS', entry, case)
""")


@pytest.mark.parametrize('entry', ['direct', 'package'])
@pytest.mark.parametrize('case', [
    'handlers', 'settings', 'silence', 'presence', 'assemblyai',
    'openai', 'local', 'legacy', 'legacy_wrapper', 'shared_lock',
])
def test_voice_helpers_in_clean_entry_subprocess(entry, case, tmp_path):
    environment = {name: os.environ[name] for name in ('PATH', 'LANG', 'LC_ALL', 'SYSTEMROOT')
                   if name in os.environ}
    environment.update(PYTHONDONTWRITEBYTECODE='1', PYTHON_DOTENV_DISABLED='1',
                       TMPDIR=str(tmp_path), CONFIG_DIR=str(tmp_path / 'config'))
    result = subprocess.run(
        [sys.executable, '-B', '-c', PROBE, entry, case],
        cwd=ROOT / 'TelegramVivBot' if entry == 'direct' else ROOT,
        env=environment, capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert f'PASS {entry} {case}' in result.stdout
# === VIVENTIUM END ===
