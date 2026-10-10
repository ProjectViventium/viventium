import asyncio
import json
import os
import sys
import struct
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

    def test_local_stt_final_has_a_generic_stream_binding(self):
        stream = SimpleNamespace()
        self.timing.bind_stt(stream)
        self.timing.final_stt(SimpleNamespace(type=SimpleNamespace(name="FINAL_TRANSCRIPT")), stream)
        self.assertEqual(self.rows()[0]["streamHash"], self.rows()[1]["streamHash"])
        self.assertEqual(self.rows()[1]["bindingStatus"], "bound")

    async def test_vad_receipt_preserves_event_and_clock_without_audio_or_text(self):
        class Recognition:
            __module__ = "livekit.agents.voice.audio_recognition"
            async def _on_vad_event(self, event):
                return event
        recognition = Recognition()
        event = SimpleNamespace(type=SimpleNamespace(name="END_OF_SPEECH"),
            samples_index=16000, speech_duration=1.0, silence_duration=.5,
            frames=["private audio"], text="private transcript")
        self.assertTrue(self.timing.attach_audio_recognition(recognition))
        self.assertFalse(self.timing.attach_audio_recognition(recognition))
        with patch("voice_p0_timing.time.time_ns", return_value=999_000_000):
            self.assertIs(await recognition._on_vad_event(event), event)
        row = self.rows()[-1]
        self.assertEqual(row["observedAtMs"], 999)
        self.assertEqual(row["samplesIndex"], 16000)
        self.assertEqual(row["endClock"], "sdk_vad_sample_relative")
        self.assertNotIn("private", str(row))

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
        self.assertEqual(stages.count('tts_first_decoded_pcm'), 1)
        self.assertLess(stages.index('tts_first_audio_receipt'), stages.index('tts_first_decoded_pcm'))
        decoded = next(row for row in self.rows() if row['stage'] == 'tts_first_decoded_pcm')
        self.assertEqual(decoded['byteCount'], len(pcm))
        self.assertNotIn('private', str(decoded))

    async def test_decoded_pcm_observation_preserves_push_and_restores_after_failure(self):
        ws = FakeSocket()
        tts = FakeTTS(ws)
        error = RuntimeError('synthetic failure')
        async def run(emitter):
            emitter.initialize(request_id='synthetic-request', mime_type='audio/pcm')
            emitter.push(b'')
            emitter.push(b'\0\1')
            emitter.push(b'\2\3')
            raise error
        original_stream = tts.stream
        def stream():
            result = original_stream()
            result._run = run
            return result
        tts.stream = stream
        self.assertTrue(self.timing.attach_xai(tts))
        emitter = SimpleNamespace(initialize=Mock(), push=Mock())
        initialize, push = emitter.initialize, emitter.push
        with self.assertRaises(RuntimeError) as captured:
            await tts.stream()._run(emitter)
        self.assertIs(captured.exception, error)
        self.assertIs(emitter.initialize, initialize)
        self.assertIs(emitter.push, push)
        self.assertEqual([call.args[0] for call in push.call_args_list], [b'', b'\0\1', b'\2\3'])
        decoded = [row for row in self.rows() if row['stage'] == 'tts_first_decoded_pcm']
        self.assertEqual(len(decoded), 1)
        self.assertEqual(decoded[0]['byteCount'], 2)
        ended = [row for row in self.rows() if row['stage'] == 'tts_stream_end']
        self.assertEqual(len(ended), 1)
        self.assertEqual(ended[0]['status'], 'failed')
        self.assertNotIn('synthetic failure', str(ended))

    async def test_stream_cancellation_preserves_emitter_and_reports_actual_outcome(self):
        tts = FakeTTS(FakeSocket())
        ready = asyncio.Event()
        original_stream = tts.stream
        async def run(emitter):
            emitter.initialize(request_id='synthetic-request', mime_type='audio/pcm')
            ready.set()
            await asyncio.Event().wait()
        def stream():
            result = original_stream()
            result._run = run
            return result
        tts.stream = stream
        self.assertTrue(self.timing.attach_xai(tts))
        emitter = SimpleNamespace(initialize=Mock(), push=Mock())
        initialize, push = emitter.initialize, emitter.push
        task = asyncio.create_task(tts.stream()._run(emitter))
        await ready.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertIs(emitter.initialize, initialize)
        self.assertIs(emitter.push, push)
        ended = [row for row in self.rows() if row['stage'] == 'tts_stream_end']
        self.assertEqual(len(ended), 1)
        self.assertEqual(ended[0]['status'], 'cancelled')
        self.assertNotIn('leaseHash', ended[0])


    async def _render_native_pcm_chunks(self, chunks, *, enabled=True):
        import base64
        import aiohttp
        from worker import _build_xai_tts_word_tokenizer
        from xai_pooled_tts import PooledXaiTTS
        sent_done = asyncio.Event()

        class SDKSocket(FakeSocket):
            closed = False
            read_count = 0

            async def send_str(self, data, **kwargs):
                result = await super().send_str(data, **kwargs)
                if json.loads(data).get('type') == 'text.done':
                    sent_done.set()
                return result

            async def receive(self, **kwargs):
                await sent_done.wait()
                index = self.read_count
                self.read_count += 1
                packet = ({'type': 'audio.delta', 'delta': base64.b64encode(chunks[index]).decode()}
                          if index < len(chunks) else {'type': 'audio.done'})
                return SimpleNamespace(type=aiohttp.WSMsgType.TEXT, data=json.dumps(packet))

            async def close(self):
                self.closed = True

        ws = SDKSocket()
        tts = PooledXaiTTS(api_key='synthetic-key', tokenizer=_build_xai_tts_word_tokenizer())
        async def connect(timeout):
            return ws
        tts._connect_ws = connect
        observer = self.timing if enabled else VoiceP0Timing(self.log, 'synthetic-call', enabled=False)
        self.assertEqual(observer.attach_xai(tts), enabled)
        stream = tts.stream()
        try:
            stream.push_text('Synthetic speech keeps spaces.')
            stream.end_input()
            output = [event async for event in stream]
            self.assertEqual(b''.join(bytes(event.frame.data) for event in output), b''.join(chunks))
            if enabled:
                returned = [r for r in self.rows() if r['stage'] == 'tts_pool_disposition']
                self.assertEqual(returned[-1]['operation'], 'returned')
        finally:
            await stream.aclose()
            await tts.aclose()
        return self.rows()

    async def test_actual_pinned_decoder_binds_first_activity_after_quiet_and_only_once(self):
        chunks = [bytes(48000), struct.pack('<hhhh', 0, 263, 0, -500), bytes(2392)]
        rows = await self._render_native_pcm_chunks(chunks)
        active = [r for r in rows if r['stage'] == 'tts_first_active_produced_pcm']
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]['leadingQuietSamples'], 24001)
        self.assertEqual(active[0]['sampleRate'], 24000)
        self.assertEqual(active[0]['thresholdNormalized'], .008)
        decoded = next(r for r in rows if r['stage'] == 'tts_first_decoded_pcm')
        self.assertLess(decoded['observedAtMs'], active[0]['observedAtMs'])
        for key in ('callHash', 'streamHash', 'requestHash', 'leaseHash'):
            self.assertEqual(decoded[key], active[0][key])
        self.assertEqual(set(active[0]), {'event', 'stage', 'callHash', 'observedAtMs', 'monotonicMs',
                                        'streamHash', 'requestHash', 'leaseHash',
                                        'leadingQuietSamples', 'sampleRate', 'thresholdNormalized'})
        self.assertNotIn('synthetic', str(active))

    async def test_actual_pinned_decoder_handles_sample_split_across_odd_payloads(self):
        chunks = [bytes(3), b'\0\x07', b'\x01' + bytes(2394)]
        rows = await self._render_native_pcm_chunks(chunks)
        active = [r for r in rows if r['stage'] == 'tts_first_active_produced_pcm']
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]['leadingQuietSamples'], 2)
        self.assertNotIn('tts_active_pcm_support', [r['stage'] for r in rows])

    async def test_actual_pinned_decoder_all_quiet_leaves_activity_clock_absent(self):
        rows = await self._render_native_pcm_chunks([struct.pack('<hh', 262, -262) * 600])
        self.assertNotIn('tts_first_active_produced_pcm', [r['stage'] for r in rows])
        self.assertEqual([r['stage'] for r in rows].count('tts_first_decoded_pcm'), 1)

    async def test_activity_scan_stops_after_first_active_sample(self):
        import voice_p0_timing
        scan = getattr(voice_p0_timing, '_first_active_pcm16le_index', lambda data: None)
        with patch('voice_p0_timing._first_active_pcm16le_index', wraps=scan, create=True) as observed:
            await self._render_native_pcm_chunks([bytes(1200), struct.pack('<h', -263) + bytes(1198), bytes(1200)])
        self.assertEqual(observed.call_count, 2)

    async def test_disabled_native_pcm_path_never_scans_or_logs(self):
        with patch('voice_p0_timing._first_active_pcm16le_index', create=True) as scan:
            await self._render_native_pcm_chunks([struct.pack('<h', 500) + bytes(2398)], enabled=False)
        scan.assert_not_called()
        self.log.info.assert_not_called()

    async def _observe_fake_pcm_format(self, **settings):
        tts = FakeTTS(FakeSocket())
        sentinel = object()
        original_stream = tts.stream
        async def run(emitter):
            emitter.initialize(request_id='synthetic-request', **settings)
            emitter.push(struct.pack('<h', 500))
            return sentinel
        def stream():
            result = original_stream()
            result._run = run
            return result
        tts.stream = stream
        self.assertTrue(self.timing.attach_xai(tts))
        emitter = SimpleNamespace(initialize=Mock(), push=Mock())
        initialize, push = emitter.initialize, emitter.push
        self.assertIs(await tts.stream()._run(emitter), sentinel)
        self.assertIs(emitter.initialize, initialize)
        self.assertIs(emitter.push, push)
        push.assert_called_once_with(struct.pack('<h', 500))
        return self.rows()

    async def test_unknown_raw_format_leaves_clock_absent_without_changing_push(self):
        for settings in ({'mime_type':'audio/pcm'},
                         {'mime_type':'audio/raw', 'sample_rate':True, 'num_channels':1},
                         {'mime_type':'audio/pcm', 'sample_rate':24000, 'num_channels':2}):
            self.log.reset_mock()
            rows = await self._observe_fake_pcm_format(**settings)
            self.assertNotIn('tts_first_active_produced_pcm', [r['stage'] for r in rows])
            unsupported = [r for r in rows if r['stage'] == 'tts_active_pcm_support']
            self.assertEqual(len(unsupported), 1)
            self.assertEqual(unsupported[0]['reason'], 'format')
            self.assertNotIn('synthetic', str(unsupported))

    async def test_explicit_or_unproven_pcm_formats_abstain_without_changing_audio(self):
        for mime_type in ('audio/pcm;format=f32', 'audio/pcm;bits=24',
                          'audio/pcm;endianness=big', 'audio/pcm-f32', 'audio/raw'):
            self.log.reset_mock()
            rows = await self._observe_fake_pcm_format(mime_type=mime_type, sample_rate=24000,
                                                       num_channels=1)
            self.assertNotIn('tts_first_active_produced_pcm', [r['stage'] for r in rows])
            unsupported = [r for r in rows if r['stage'] == 'tts_active_pcm_support']
            self.assertEqual(len(unsupported), 1)
            self.assertEqual(unsupported[0]['reason'], 'format')
            self.assertNotIn(mime_type, str(unsupported))

    async def test_compressed_format_does_not_invent_activity(self):
        rows = await self._observe_fake_pcm_format(mime_type='audio/mpeg', sample_rate=24000, num_channels=1)
        self.assertNotIn('tts_first_active_produced_pcm', [r['stage'] for r in rows])
        self.assertNotIn('tts_first_decoded_pcm', [r['stage'] for r in rows])

    async def test_activity_observer_error_preserves_native_audio_and_outcome(self):
        with patch('voice_p0_timing._first_active_pcm16le_index', side_effect=RuntimeError('private diagnostic'), create=True):
            rows = await self._render_native_pcm_chunks([struct.pack('<h', 500) + bytes(2398)])
        unsupported = [r for r in rows if r['stage'] == 'tts_active_pcm_support']
        self.assertEqual(len(unsupported), 1)
        self.assertEqual(unsupported[0]['reason'], 'observation')
        self.assertNotIn('private diagnostic', str(rows))
        self.assertEqual([r for r in rows if r['stage'] == 'tts_stream_end'][-1]['status'], 'completed')

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


class TextDoneTimingTests(unittest.IsolatedAsyncioTestCase):
    async def test_done_write_after_delta_is_once_bound_and_exactly_forwarded(self):
        log = Mock(); timing = VoiceP0Timing(log, 'synthetic-call', enabled=True)
        ws = FakeSocket(); ws.messages.append(SimpleNamespace(data=json.dumps({'type':'audio.delta'})))
        tts = FakeTTS(ws); self.assertTrue(timing.attach_xai(tts))
        stream = tts.stream(); stream.push_text('Synthetic public text')
        await stream._run(SimpleNamespace(initialize=Mock()))
        done = json.dumps({'type':'text.done'})
        await ws.send_str(done, compress=0); await ws.send_str(done, compress=0)
        rows = [json.loads(call.args[1]) for call in log.info.call_args_list]
        writes = [r for r in rows if r['stage']=='tts_first_text_write']
        ends = [r for r in rows if r['stage']=='tts_text_done_write']
        self.assertEqual(len(ends),1)
        self.assertEqual(ends[0]['requestHash'],writes[0]['requestHash'])
        self.assertEqual(ends[0]['socketHash'],writes[0]['socketHash'])
        self.assertEqual(ws.sent[-2:], [(done, {'compress':0}), (done, {'compress':0})])
        self.assertNotIn('Synthetic public text',str(rows))
