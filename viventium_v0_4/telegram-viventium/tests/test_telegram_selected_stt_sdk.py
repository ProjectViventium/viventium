# === VIVENTIUM START ===
"""Run the pinned public stream API against an owned fake WebSocket, without a provider."""
import asyncio
import importlib.metadata
import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'TelegramVivBot'))
pytest.importorskip('livekit.plugins.assemblyai')
from TelegramVivBot.utils.telegram_stt import TelegramSTTError, transcribe_selected_audio
from TelegramVivBot.utils.telegram_audio import DecodedTelegramAudio


@pytest.mark.parametrize('failure', [False, True])
def test_pinned_assembly_sdk_stream_ownership_without_job_context(monkeypatch, failure):
    import aiohttp
    assert importlib.metadata.version('livekit-plugins-assemblyai') == '1.5.10'
    assert importlib.metadata.version('livekit-agents') == '1.5.10'
    monkeypatch.setenv('ASSEMBLYAI_API_KEY', 'synthetic-key')
    monkeypatch.setenv('VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD', '0.31')
    monkeypatch.setenv('VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS', '240')
    monkeypatch.setenv('VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS', '1500')
    monkeypatch.setenv('VIVENTIUM_ASSEMBLYAI_FORMAT_TURNS', 'true')
    state = types.SimpleNamespace(bytes=[], urls=[], socket_closed=False, session_closed=False)

    class Socket:
        _response = types.SimpleNamespace(status=101)
        close_code = 1006
        def __init__(self):
            self.events = asyncio.Queue()
            self.text({'type': 'Begin', 'id': 'synthetic-session'})
        def text(self, data):
            self.events.put_nowait(types.SimpleNamespace(type=aiohttp.WSMsgType.TEXT, data=json.dumps(data)))
        def final(self, text):
            self.text({'type': 'Turn', 'transcript': text, 'end_of_turn': True,
                       'turn_is_formatted': True, 'words': []})
        async def send_bytes(self, data):
            state.bytes.append(data)
            if failure and len(state.bytes) == 1:
                self.final('partial must not escape')
                self.events.put_nowait(types.SimpleNamespace(type=aiohttp.WSMsgType.CLOSED, data='', extra=''))
        async def send_str(self, value):
            if json.loads(value).get('type') == 'Terminate':
                self.final('first')
                self.final('second')
                self.events.put_nowait(types.SimpleNamespace(type=aiohttp.WSMsgType.CLOSED, data='', extra=''))
        async def receive(self): return await self.events.get()
        async def close(self): state.socket_closed = True

    class Session:
        def __init__(self, trace_configs): self.traces = trace_configs
        async def __aenter__(self): return self
        async def __aexit__(self, *_): state.session_closed = True
        async def ws_connect(self, url, headers):
            state.urls.append((url, headers))
            for trace in self.traces:
                for callback in trace.on_request_end:
                    await callback(self, None, None)
            return Socket()
    monkeypatch.setattr(aiohttp, 'ClientSession', Session)

    async def run():
        pcm = np.linspace(-0.2, 0.2, 3500, dtype=np.float32)
        timings = []
        if failure:
            with pytest.raises(TelegramSTTError, match='transcription_failed'):
                await transcribe_selected_audio(b'bytes', DecodedTelegramAudio(pcm),
                    {'provider': 'assemblyai', 'variant': 'u3-rt-pro'}, 1)
        else:
            result = await transcribe_selected_audio(b'bytes', DecodedTelegramAudio(pcm),
                {'provider': 'assemblyai', 'variant': 'u3-rt-pro',
                 'contextualKeyterms': ['Example Meeting']}, 1, timing=lambda *args: timings.append(args))
            assert result == 'first second'
            received = np.frombuffer(b''.join(state.bytes), dtype='<i2')
            np.testing.assert_array_equal(received, np.rint(pcm * 32767).astype('<i2'))
            assert 'assemblyai_connected' in [t[0] for t in timings]
        assert len(state.urls) == 1  # No SDK retry, even after an emitted FINAL.
        assert 'speech_model=u3-rt-pro' in state.urls[0][0]
        from urllib.parse import parse_qs, urlparse
        query = parse_qs(urlparse(state.urls[0][0]).query)
        assert query['speaker_labels'] == ['true']
        assert query['end_of_turn_confidence_threshold'] == ['0.31']
        assert query['min_turn_silence'] == ['240']
        assert query['max_turn_silence'] == ['1500']
        assert query['format_turns'] == ['true']
        if not failure:
            assert json.loads(query['keyterms_prompt'][0]) == ['Example Meeting']
        assert state.urls[0][1]['Authorization'] == 'synthetic-key'
        assert state.session_closed and state.socket_closed
    asyncio.run(run())
# === VIVENTIUM END ===
