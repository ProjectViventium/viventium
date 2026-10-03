import asyncio
import json
import os
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from voice_p0_timing import VoiceP0Timing, observe_sdk_commit


class FakeSTT:
    __module__ = "livekit.plugins.assemblyai.stt"

    def _process_stream_event(self, data):
        self.data = data
        return data


class FakeSocket:
    def __init__(self):
        self.sent = []
        self.messages = []

    async def send_str(self, data, **kwargs):
        self.sent.append((data, kwargs))
        return self

    async def receive(self, **kwargs):
        return self.messages.pop(0)


class FakeTTS:
    __module__ = "livekit.plugins.xai.tts"

    def __init__(self, ws):
        self.ws = ws
        self.arguments = []

    async def _connect_ws(self, timeout):
        self.arguments.append(timeout)
        return self.ws

    def stream(self):
        stream = SimpleNamespace()
        stream.texts = []
        stream.push_text = lambda text: stream.texts.append(text)

        async def run(emitter):
            emitter.initialize(request_id="private-request")
            ws = await self._connect_ws(7)
            await ws.send_str(json.dumps({"type": "text.delta", "delta": "private spoken words"}), compress=0)
            return await ws.receive(timeout=3)

        stream._run = run
        return stream


class VoiceP0TimingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.log = Mock()
        self.timing = VoiceP0Timing(self.log, "private-call", enabled=True)
        self.patched = patch("voice_p0_timing.version", return_value="1.5.10")
        self.patched.start()
        self.addCleanup(self.patched.stop)

    def rows(self):
        return [json.loads(call.args[1]) for call in self.log.info.call_args_list]

    def test_disabled_is_noop(self):
        timing = VoiceP0Timing(self.log, "private-call", enabled=False)
        stt = FakeSTT()
        original = stt._process_stream_event
        self.assertFalse(timing.attach_assemblyai(stt))
        self.assertEqual(stt._process_stream_event, original)
        self.assertFalse(timing.attach_xai(FakeTTS(FakeSocket())))
        self.log.info.assert_not_called()

    def test_unsupported_version_does_not_modify_provider(self):
        stt = FakeSTT()
        original = stt._process_stream_event
        with patch("voice_p0_timing.version", return_value="1.6.9"):
            self.assertFalse(self.timing.attach_assemblyai(stt))
        self.assertEqual(stt._process_stream_event, original)
        self.assertEqual(self.rows()[0]["status"], "unsupported")

    def test_eou_final_timestamps_are_receipts_not_backdated_word_end(self):
        stt = FakeSTT()
        self.assertTrue(self.timing.attach_assemblyai(stt))
        payload = {"type": "Turn", "end_of_turn": True, "turn_order": 2,
                   "end_of_turn_confidence": .8, "turn_is_formatted": False,
                   "transcript": "private transcript", "words": [{"end": 120, "text": "private word"}]}
        with patch("voice_p0_timing.time.time_ns", return_value=999_000_000):
            self.assertIs(stt._process_stream_event(payload), payload)
            self.timing.final_stt(SimpleNamespace(type=SimpleNamespace(name="FINAL_TRANSCRIPT")), stt)
        rows = self.rows()[1:]
        self.assertEqual([r["stage"] for r in rows], ["provider_eou_receipt", "stt_final_observed"])
        self.assertEqual(rows[0]["observedAtMs"], 999)
        self.assertEqual(rows[0]["lastWordEndMs"], 120)
        self.assertEqual(rows[0]["endClock"], "provider_relative")
        self.assertEqual(rows[0]["streamHash"], rows[1]["streamHash"])
        self.assertNotIn("private", str(rows))

    def test_interim_and_unknown_do_not_invent_eou(self):
        stt = FakeSTT()
        self.timing.attach_assemblyai(stt)
        payload = {"type": "Turn", "end_of_turn": False}
        self.assertIs(stt._process_stream_event(payload), payload)
        self.assertEqual(len(self.rows()), 1)

    async def test_transport_preserves_socket_message_arguments_and_request_join(self):
        ws = FakeSocket()
        message = SimpleNamespace(data=json.dumps({"type": "audio.delta", "delta": "private bytes"}))
        ws.messages.append(message)
        tts = FakeTTS(ws)
        self.assertTrue(self.timing.attach_xai(tts))
        stream = tts.stream()
        stream.push_text("private text")
        emitter = SimpleNamespace(initialize=Mock())
        self.assertIs(await stream._run(emitter), message)
        self.assertEqual(tts.arguments, [7])
        self.assertEqual(ws.sent[0][1], {"compress": 0})
        self.assertEqual(stream.texts, ["private text"])
        rows = self.rows()
        stages = [r["stage"] for r in rows]
        self.assertIn("tts_first_text_accepted", stages)
        self.assertIn("tts_first_text_write", stages)
        self.assertIn("tts_first_audio_receipt", stages)
        connect = next(r for r in rows if r["stage"] == "tts_connect_end")
        write = next(r for r in rows if r["stage"] == "tts_first_text_write")
        self.assertFalse(connect["reused"])
        self.assertEqual(connect["requestHash"], write["requestHash"])
        self.assertNotIn("private", str(rows))

    async def test_actual_same_socket_reports_reuse_without_new_socket(self):
        ws = FakeSocket()
        tts = FakeTTS(ws)
        self.timing.attach_xai(tts)
        self.assertIs(await tts._connect_ws(1), ws)
        self.assertIs(await tts._connect_ws(2), ws)
        self.assertEqual([r["reused"] for r in self.rows() if r["stage"] == "tts_connect_end"], [False, True])

    async def test_connect_cancellation_preserves_same_exception(self):
        tts = FakeTTS(FakeSocket())
        error = asyncio.CancelledError()
        async def fail(timeout):
            raise error
        tts._connect_ws = fail
        self.timing.attach_xai(tts)
        with self.assertRaises(asyncio.CancelledError) as captured:
            await tts._connect_ws(1)
        self.assertIs(captured.exception, error)
        self.assertEqual(self.rows()[-1]["status"], "cancelled")

    async def test_sdk_commit_preserves_return_and_exception(self):
        obj = SimpleNamespace(_p0_timing=self.timing)
        result = object()
        @observe_sdk_commit
        async def success(self):
            return result
        self.assertIs(await success(obj), result)
        self.assertEqual(self.rows()[-1]["status"], "completed")
        error = RuntimeError("private diagnostic")
        @observe_sdk_commit
        async def fail(self):
            raise error
        with self.assertRaises(RuntimeError) as captured:
            await fail(obj)
        self.assertIs(captured.exception, error)
        self.assertEqual(self.rows()[-1]["status"], "failed")
        self.assertNotIn("private", str(self.rows()))

    async def test_logger_failure_does_not_change_result(self):
        self.log.info.side_effect = RuntimeError("recorder unavailable")
        stt = FakeSTT()
        self.assertTrue(self.timing.attach_assemblyai(stt))
        payload = {"type": "Turn", "end_of_turn": True}
        self.assertIs(stt._process_stream_event(payload), payload)

    async def test_actual_pinned_xai_stream_preserves_pcm_and_close_without_network(self):
        import base64
        import aiohttp
        from livekit.plugins import xai
        from worker import _build_xai_tts_word_tokenizer
        sent_done = asyncio.Event()
        pcm = bytes(2400)

        class SDKSocket(FakeSocket):
            closed_count = 0
            read_count = 0

            async def send_str(self, data, **kwargs):
                result = await super().send_str(data, **kwargs)
                if json.loads(data).get('type') == 'text.done':
                    sent_done.set()
                return result

            async def receive(self, **kwargs):
                await sent_done.wait()
                self.read_count += 1
                packet = ({'type': 'audio.delta', 'delta': base64.b64encode(pcm).decode()}
                          if self.read_count == 1 else {'type': 'audio.done'})
                return SimpleNamespace(type=aiohttp.WSMsgType.TEXT, data=json.dumps(packet))

            async def close(self):
                self.closed_count += 1

        ws = SDKSocket()
        tts = xai.TTS(api_key='synthetic-key', tokenizer=_build_xai_tts_word_tokenizer())
        async def configured_connect(timeout):
            return ws
        tts._connect_ws = configured_connect
        self.assertTrue(self.timing.attach_xai(tts))
        stream = tts.stream()
        stream.push_text('Synthetic speech keeps spaces.')
        stream.end_input()
        output = [event async for event in stream]
        await stream.aclose()
        await tts.aclose()
        self.assertEqual(b''.join(bytes(event.frame.data) for event in output), pcm)
        self.assertEqual(ws.closed_count, 1)
        self.assertEqual(''.join(json.loads(data).get('delta', '') for data, _ in ws.sent), 'Synthetic speech keeps spaces.')
        stages = [row['stage'] for row in self.rows()]
        self.assertIn('tts_request_bound', stages)
        self.assertIn('tts_first_audio_receipt', stages)

    async def test_actual_pinned_assemblyai_event_keeps_final_contract_without_network(self):
        import aiohttp
        from livekit.plugins import assemblyai
        from livekit.plugins.assemblyai.stt import SpeechStream
        from livekit.agents.stt import SpeechEventType
        async def no_network(self):
            await asyncio.Event().wait()
        with patch.object(SpeechStream, '_run', no_network):
            http_session = aiohttp.ClientSession()
            stt = assemblyai.STT(api_key='synthetic-key', http_session=http_session)
            stream = stt.stream()
            try:
                self.assertTrue(self.timing.attach_assemblyai(stream))
                stream._process_stream_event({'type':'Turn','end_of_turn':True,'turn_order':1,
                    'transcript':'Synthetic final transcript.','words':[{'text':'Synthetic','start':100,'end':200}]})
                first = await stream.__anext__()
                final = await stream.__anext__()
                self.assertEqual(first.type, SpeechEventType.INTERIM_TRANSCRIPT)
                self.assertEqual(final.type, SpeechEventType.FINAL_TRANSCRIPT)
                self.assertEqual(final.alternatives[0].text, 'Synthetic final transcript.')
                self.timing.final_stt(final, stream)
            finally:
                await stream.aclose()
                await stt.aclose()
                await http_session.close()
        self.assertEqual([row['stage'] for row in self.rows()],
                         ['stt_receipt_support','provider_eou_receipt','stt_final_observed'])


if __name__ == "__main__":
    unittest.main()
