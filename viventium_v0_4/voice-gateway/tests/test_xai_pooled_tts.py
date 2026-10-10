import asyncio
import base64
import json
import gc
import os
import sys
from types import SimpleNamespace
import unittest
import weakref
from unittest.mock import Mock, patch

import aiohttp
from livekit.agents import APIConnectOptions, tokenize
from livekit.plugins.xai import tts as xai

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from xai_pooled_tts import PooledXaiTTS, create_xai_tts
from voice_p0_timing import VoiceP0Timing
from fallback_tts import FallbackTTS, ProviderAttempt
from test_fallback_tts import FakeStreamingTTS


class Socket:
    def __init__(self, voice="Sal", *, error=False, partial=False, gate=None, never_answer=False):
        self.voice, self.error, self.partial, self.gate = voice, error, partial, gate
        self.never_answer = never_answer
        self.closed = False
        self.close_code = 1000
        self.packets = []
        self.messages = asyncio.Queue()
        self.text_done = asyncio.Event()

    def audio(self):
        self.messages.put_nowait(SimpleNamespace(type=aiohttp.WSMsgType.TEXT,
            data=json.dumps({"type": "audio.delta", "delta": base64.b64encode(b"\x01\x00" * 2400).decode()})))

    async def send_str(self, data, **kwargs):
        packet = json.loads(data)
        self.packets.append(packet)
        if self.partial and packet["type"] == "text.delta":
            self.audio()
            self.partial = False
        if packet["type"] == "text.done":
            self.text_done.set()
            if self.never_answer:
                return
            if self.gate is not None:
                await self.gate.wait()
            if self.error:
                self.messages.put_nowait(SimpleNamespace(type=aiohttp.WSMsgType.TEXT,
                    data=json.dumps({"type": "error", "message": "synthetic provider error"})))
            else:
                self.audio()
                self.messages.put_nowait(SimpleNamespace(type=aiohttp.WSMsgType.TEXT,
                    data=json.dumps({"type": "audio.done"})))

    async def receive(self, **kwargs):
        return await self.messages.get()

    async def close(self):
        self.closed = True


class PoolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tts = PooledXaiTTS(api_key="synthetic-test", voice="Sal", language="en",
            tokenizer=tokenize.basic.WordTokenizer(ignore_punctuation=False, retain_format=True))
        self.sockets = []
        self.next_options = {}

        async def connect(timeout):
            await asyncio.sleep(0)
            ws = Socket(self.tts._opts.voice, **self.next_options)
            self.next_options = {}
            self.sockets.append(ws)
            return ws
        self.tts._connect_ws = connect

    async def asyncTearDown(self):
        await self.tts.aclose()

    async def render(self, text="Take one slow breath. Then choose one small next step.", *, max_retry=0, timeout=1):
        stream = self.tts.stream(conn_options=APIConnectOptions(max_retry=max_retry, retry_interval=0, timeout=timeout))
        try:
            stream.push_text(text)
            stream.end_input()
            return [event async for event in stream]
        finally:
            await stream.aclose()

    async def test_actual_sdk_wire_preserves_full_tail_and_reuses_completed_socket(self):
        text = "Take one slow breath. Then choose one small next step."
        metrics = []
        self.tts.on("metrics_collected", metrics.append)
        for _ in range(2):
            events = await self.render(text)
            self.assertEqual(b"".join(event.frame.data.tobytes() for event in events), b"\x01\x00" * 2400)
        self.assertEqual(len(self.sockets), 1)
        packets = self.sockets[0].packets
        self.assertEqual("".join(p.get("delta", "") for p in packets), text * 2)
        self.assertEqual(sum(p["type"] == "text.done" for p in packets), 2)
        self.assertEqual([m.connection_reused for m in metrics], [False, True])
        self.assertEqual(metrics[-1].acquire_time, 0)

    async def test_concurrent_streams_use_distinct_leases(self):
        first, second = await asyncio.gather(self.render("First complete sentence."), self.render("Second complete sentence."))
        self.assertTrue(first and second)
        self.assertEqual(len(self.sockets), 2)

    async def test_mid_audio_cancellation_evicts_and_recovery_uses_fresh_socket(self):
        self.next_options = {"partial": True}
        stream = self.tts.stream(conn_options=APIConnectOptions(max_retry=0, timeout=1))
        stream.push_text("Hold the abandoned words ")
        await stream.__anext__()
        await stream.aclose()
        self.assertFalse(self.tts._pool._available)
        self.assertFalse(self.tts._pool._connections)
        self.assertTrue(await self.render())
        self.assertEqual(len(self.sockets), 2)
        self.assertTrue(self.sockets[0].closed)
        recovered = "".join(p.get("delta", "") for p in self.sockets[1].packets)
        self.assertNotIn("abandoned", recovered)
        self.assertTrue(recovered.endswith("next step."))

    async def test_provider_error_evicts_without_a_healthy_return(self):
        self.next_options = {"error": True}
        with self.assertRaises(Exception):
            await self.render()
        self.assertFalse(self.tts._pool._available)
        self.assertTrue(await self.render())
        self.assertEqual(len(self.sockets), 2)

    async def test_closed_idle_socket_and_expired_socket_reconnect(self):
        await self.render()
        self.sockets[0].closed = True
        await self.render()
        self.assertEqual(len(self.sockets), 2)
        self.tts._pool._connections[self.sockets[1]] -= 1801
        await self.render()
        self.assertEqual(len(self.sockets), 3)
        self.assertNotIn(self.sockets[1], self.tts._pool._connections)
        await self.tts.aclose()
        self.assertTrue(self.sockets[1].closed)

    async def test_silent_dead_idle_socket_is_bounded_and_native_retry_recovers(self):
        await self.render()
        stale = self.sockets[0]
        stale.never_answer = True
        self.assertFalse(stale.closed)
        recovered = await asyncio.wait_for(self.render(max_retry=1, timeout=.03), 1)
        self.assertTrue(recovered)
        self.assertEqual(len(self.sockets), 2)
        self.assertTrue(stale.closed)
        self.assertNotIn(stale, self.tts._pool._connections)
        self.assertEqual(sum(p["type"] == "text.done" for p in stale.packets), 2)
        self.assertEqual(sum(p["type"] == "text.done" for p in self.sockets[1].packets), 1)

    async def test_never_answer_socket_exits_and_fallback_preserves_complete_text(self):
        self.next_options = {"never_answer": True}
        fallback = FakeStreamingTTS(sample_rate=24000)
        wrapper = FallbackTTS(attempts=[ProviderAttempt("xai", self.tts), ProviderAttempt("fallback", fallback)])
        stream = wrapper.stream(conn_options=APIConnectOptions(max_retry=0, timeout=.03))
        text = "Preserve these complete final words."
        stream.push_text(text)
        stream.end_input()
        try:
            self.assertTrue(await asyncio.wait_for(self.collect(stream), 1))
            self.assertEqual("".join(fallback.last_stream_chunks), text)
            self.assertNotIn(self.sockets[0], self.tts._pool._connections)
        finally:
            await stream.aclose()
        self.tts.prewarm()
        await self.wait_prewarm()
        self.assertTrue(self.sockets[0].closed)
        self.assertTrue(await self.render())
        self.assertEqual(len(self.sockets), 2)

    @staticmethod
    async def collect(stream):
        return [event async for event in stream]

    async def test_first_audio_budget_excludes_long_prewarm_and_pretext_wait(self):
        self.tts.prewarm()
        await self.wait_prewarm()
        await asyncio.sleep(.06)
        stream = self.tts.stream(conn_options=APIConnectOptions(max_retry=0, timeout=.03))
        await asyncio.sleep(.06)
        stream.push_text("A complete response after the model wait.")
        stream.end_input()
        try:
            self.assertTrue(await self.collect(stream))
            self.assertEqual(len(self.sockets), 1)
        finally:
            await stream.aclose()

    async def test_first_audio_budget_preserves_slow_complete_tail_without_replay(self):
        gate = asyncio.Event()
        self.next_options = {"partial": True, "gate": gate}
        render = asyncio.create_task(self.render("Keep the entire final sentence.", max_retry=1, timeout=.03))
        while not self.sockets:
            await asyncio.sleep(0)
        await self.sockets[0].text_done.wait()
        await asyncio.sleep(.06)
        self.assertFalse(render.done())
        gate.set()
        events = await asyncio.wait_for(render, 1)
        self.assertEqual(b"".join(event.frame.data.tobytes() for event in events), b"\x01\x00" * 4800)
        self.assertEqual(len(self.sockets), 1)
        self.assertEqual(sum(p["type"] == "text.done" for p in self.sockets[0].packets), 1)

    async def test_option_change_evicts_idle_but_same_options_keep_socket(self):
        await self.render()
        self.tts.update_options(voice="Sal", language="en")
        await self.render()
        self.assertEqual(len(self.sockets), 1)
        self.tts.update_options(voice="Eve")
        self.assertFalse(self.tts._pool._available)
        await self.render()
        self.assertEqual([s.voice for s in self.sockets], ["Sal", "Eve"])
        self.assertTrue(self.sockets[0].closed)

    async def test_option_change_preserves_active_utterance_and_evicts_it_on_release(self):
        gate = asyncio.Event()
        self.next_options = {"gate": gate}
        first = asyncio.create_task(self.render("Complete the original voice."))
        while not self.sockets:
            await asyncio.sleep(0)
        await self.sockets[0].text_done.wait()
        self.tts.update_options(voice="Eve")
        await self.render("Speak the new voice.")
        self.assertFalse(self.sockets[0].closed)
        gate.set()
        self.assertTrue(await first)
        self.assertNotIn(self.sockets[0], self.tts._pool._available)
        self.assertIn(self.sockets[1], self.tts._pool._available)

    async def test_prewarm_race_connects_once_and_close_cleans_up(self):
        self.tts.prewarm()
        self.tts.prewarm()
        await self.render()
        self.assertEqual(len(self.sockets), 1)
        await self.tts.aclose()
        self.assertTrue(self.sockets[0].closed)
        self.assertFalse(self.tts._pool._connections)

    async def wait_prewarm(self):
        task = self.tts._pool._prewarm_task() if self.tts._pool._prewarm_task else None
        if task is not None:
            await task

    async def test_prewarm_after_cancellation_replaces_evicted_socket(self):
        self.tts.prewarm()
        await self.wait_prewarm()
        self.sockets[0].partial = True
        stream = self.tts.stream(conn_options=APIConnectOptions(max_retry=0, timeout=1))
        stream.push_text("Abandoned partial words ")
        await stream.__anext__()
        await stream.aclose()
        self.tts.prewarm()
        await self.wait_prewarm()
        self.assertEqual(len(self.sockets), 2)
        self.assertTrue(self.sockets[0].closed)
        self.assertTrue(await self.render())
        self.assertEqual(len(self.sockets), 2)
        self.assertTrue(self.sockets[0].closed)
        self.assertNotIn("Abandoned", str(self.sockets[1].packets))

    async def test_prewarm_replaces_dead_and_expired_idle_sockets_before_text(self):
        self.tts.prewarm()
        await self.wait_prewarm()
        self.sockets[0].closed = True
        self.tts.prewarm()
        await self.wait_prewarm()
        self.assertEqual(len(self.sockets), 2)
        self.assertFalse(self.sockets[1].packets)
        self.tts._pool._connections[self.sockets[1]] -= 1801
        self.tts.prewarm()
        await self.wait_prewarm()
        self.assertEqual(len(self.sockets), 3)
        self.assertTrue(await self.render())
        self.assertEqual(len(self.sockets), 3)
        self.assertTrue(self.sockets[1].closed)

    async def test_option_change_during_prewarm_closes_old_recipe_and_warms_current(self):
        started, release = asyncio.Event(), asyncio.Event()
        async def connect(timeout):
            ws = Socket(self.tts._opts.voice)
            self.sockets.append(ws)
            if len(self.sockets) == 1:
                started.set()
                await release.wait()
            return ws
        self.tts._connect_ws = connect
        self.tts.prewarm()
        await started.wait()
        self.tts.update_options(voice="Eve")
        self.tts.prewarm()
        release.set()
        await self.wait_prewarm()
        self.assertEqual([s.voice for s in self.sockets], ["Sal", "Eve"])
        self.assertTrue(self.sockets[0].closed)
        self.assertTrue(await self.render())
        self.assertEqual(len(self.sockets), 2)

    async def test_before_audio_cancel_evicts_and_next_turn_prewarms(self):
        gate = asyncio.Event()
        self.next_options = {"gate": gate}
        stream = self.tts.stream(conn_options=APIConnectOptions(max_retry=0, timeout=1))
        stream.push_text("Do not play these words.")
        stream.end_input()
        while not self.sockets:
            await asyncio.sleep(0)
        await self.sockets[0].text_done.wait()
        await stream.aclose()
        self.assertFalse(self.tts._pool._connections)
        self.tts.prewarm()
        await self.wait_prewarm()
        self.assertTrue(await self.render())
        self.assertEqual(len(self.sockets), 2)
        self.assertNotIn("Do not play", str(self.sockets[1].packets))

    async def test_native_retry_owner_recovers_before_audio_and_never_after_audio(self):
        self.next_options = {"error": True}
        self.assertTrue(await self.render(max_retry=1))
        self.assertEqual(len(self.sockets), 2)
        self.assertTrue(self.sockets[0].closed)
        self.assertEqual(sum(p["type"] == "text.done" for p in self.sockets[1].packets), 1)
        self.sockets[1].partial = self.sockets[1].error = True
        with self.assertRaises(Exception):
            await self.render(max_retry=1)
        self.assertEqual(len(self.sockets), 2)
        self.assertFalse(self.tts._pool._connections)

    async def test_existing_fallback_recovers_before_audio_without_post_audio_replay(self):
        fallback = FakeStreamingTTS(sample_rate=24000)
        wrapper = FallbackTTS(attempts=[ProviderAttempt("xai", self.tts), ProviderAttempt("fallback", fallback)])
        for partial in (False, True):
            self.next_options = {"error": True, "partial": partial}
            fallback.last_stream_chunks.clear()
            stream = wrapper.stream(conn_options=APIConnectOptions(max_retry=0, timeout=1))
            stream.push_text("Preserve the complete final words.")
            stream.end_input()
            try:
                if partial:
                    self.assertTrue([event async for event in stream])
                    self.assertFalse(fallback.last_stream_chunks)
                else:
                    self.assertTrue([event async for event in stream])
                    self.assertEqual("".join(fallback.last_stream_chunks), "Preserve the complete final words.")
            finally:
                await stream.aclose()
        self.assertEqual(len(self.sockets), 2)

    async def test_failed_prewarm_is_consumed_and_demand_retries(self):
        connect = self.tts._connect_ws
        async def fail(timeout):
            raise RuntimeError("private error content must not be logged")
        self.tts._connect_ws = fail
        with patch("xai_pooled_tts.logger") as log:
            self.tts.prewarm()
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            self.assertEqual(log.warning.call_args.args[1], "RuntimeError")
            self.assertNotIn("private", str(log.warning.call_args))
        self.tts._connect_ws = connect
        self.tts.prewarm()
        await self.wait_prewarm()
        self.assertEqual(len(self.sockets), 1)
        self.assertTrue(await self.render())

    async def test_close_cancels_pending_prewarm(self):
        started = asyncio.Event()
        cancelled = asyncio.Event()
        async def pending(timeout):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        self.tts._connect_ws = pending
        self.tts.prewarm()
        await started.wait()
        await self.tts.aclose()
        self.assertTrue(cancelled.is_set())
        self.assertFalse(self.tts._pool._connections)

    async def test_observer_joins_each_reused_lease_to_its_current_request(self):
        log = Mock()
        timing = VoiceP0Timing(log, "synthetic-call", enabled=True)
        self.assertTrue(timing.attach_xai(self.tts))
        await self.render()
        await self.render()
        rows = [json.loads(call.args[1]) for call in log.info.call_args_list]
        acquired = [r for r in rows if r["stage"] == "tts_acquire_end"]
        writes = [r for r in rows if r["stage"] == "tts_first_text_write"]
        audio = [r for r in rows if r["stage"] == "tts_first_audio_receipt"]
        self.assertEqual([r["reused"] for r in acquired], [False, True])
        self.assertEqual(len(writes), 2)
        self.assertEqual(len(audio), 2)
        self.assertNotEqual(writes[0]["streamHash"], writes[1]["streamHash"])
        self.assertNotEqual(writes[0]["requestHash"], writes[1]["requestHash"])
        self.assertEqual([r["requestHash"] for r in writes], [r["requestHash"] for r in audio])
        self.assertEqual(writes[0]["socketHash"], writes[1]["socketHash"])
        self.assertEqual(sum(r["stage"] == "tts_connect_start" for r in rows), 1)
        self.assertNotIn("Take one", str(rows))

    async def test_observer_does_not_retain_closed_sockets_after_call_cleanup(self):
        timing = VoiceP0Timing(Mock(), "synthetic-call", enabled=True)
        self.assertTrue(timing.attach_xai(self.tts))
        await self.render()
        socket_ref = weakref.ref(self.sockets[0])
        await self.tts.aclose()
        self.sockets.clear()
        await asyncio.sleep(0)
        gc.collect()
        self.assertIsNone(socket_ref())

    async def test_observer_proves_active_cancel_eviction_then_clean_fresh_and_reuse(self):
        log = Mock()
        timing = VoiceP0Timing(log, "synthetic-call", enabled=True)
        self.assertTrue(timing.attach_xai(self.tts))
        self.next_options = {"partial": True}
        stream = self.tts.stream(conn_options=APIConnectOptions(max_retry=0, timeout=1))
        stream.push_text("Abandoned partial words ")
        await stream.__anext__()
        await stream.aclose()
        await self.render()
        await self.render()
        rows = [json.loads(call.args[1]) for call in log.info.call_args_list]
        acquired = [r for r in rows if r["stage"] == "tts_acquire_end"]
        dispositions = [r for r in rows if r["stage"] == "tts_pool_disposition"]
        ended = [r for r in rows if r["stage"] == "tts_stream_end"]
        decoded = [r for r in rows if r["stage"] == "tts_first_decoded_pcm"]
        self.assertEqual([r["operation"] for r in dispositions], ["evicted", "returned", "returned"])
        self.assertEqual([r["status"] for r in ended], ["cancelled", "completed", "completed"])
        self.assertEqual([r["leaseHash"] for r in acquired], [r["leaseHash"] for r in dispositions])
        self.assertEqual([r["leaseHash"] for r in acquired], [r["leaseHash"] for r in decoded])
        self.assertEqual([r["requestHash"] for r in acquired], [r["requestHash"] for r in dispositions])
        self.assertEqual(dispositions[0]["bindingStatus"], "active_lease")
        self.assertFalse(dispositions[0]["trackedAfter"])
        self.assertFalse(dispositions[0]["availableAfter"])
        self.assertTrue(dispositions[0]["closeQueuedAfter"])
        self.assertTrue(dispositions[1]["trackedAfter"])
        self.assertTrue(dispositions[1]["availableAfter"])
        self.assertFalse(dispositions[1]["closeQueuedAfter"])
        self.assertNotEqual(acquired[0]["socketHash"], acquired[1]["socketHash"])
        self.assertEqual(acquired[1]["socketHash"], acquired[2]["socketHash"])
        self.assertNotEqual(acquired[1]["leaseHash"], acquired[2]["leaseHash"])
        self.assertTrue(self.sockets[0].closed)
        self.assertNotIn("Abandoned", str(rows))

    async def test_observer_concurrent_leases_do_not_cross_bind(self):
        log = Mock()
        self.assertTrue(VoiceP0Timing(log, "synthetic-call", enabled=True).attach_xai(self.tts))
        await asyncio.gather(self.render("First complete sentence."), self.render("Second complete sentence."))
        rows = [json.loads(call.args[1]) for call in log.info.call_args_list]
        acquired = {r["leaseHash"]: r for r in rows if r["stage"] == "tts_acquire_end"}
        returned = [r for r in rows if r["stage"] == "tts_pool_disposition"]
        self.assertEqual(len(acquired), 2)
        self.assertEqual(len({r["socketHash"] for r in acquired.values()}), 2)
        for row in returned:
            self.assertEqual(row["operation"], "returned")
            for key in ("socketHash", "streamHash", "requestHash"):
                self.assertEqual(row[key], acquired[row["leaseHash"]][key])

    async def test_observer_preserves_pinned_deprecated_segment_outcome(self):
        async def render_segments():
            stream = self.tts.stream(conn_options=APIConnectOptions(max_retry=0, timeout=1))
            stream.push_text("First complete sentence.")
            stream.flush()
            stream.push_text("Second complete sentence.")
            stream.end_input()
            try:
                frames = [event.frame.data.tobytes() async for event in stream]
                return b"".join(frames)
            finally:
                await stream.aclose()
        baseline = await render_segments()
        log = Mock()
        self.assertTrue(VoiceP0Timing(log, "synthetic-call", enabled=True).attach_xai(self.tts))
        self.assertEqual(await render_segments(), baseline)
        self.assertTrue(baseline)
        rows = [json.loads(call.args[1]) for call in log.info.call_args_list]
        acquired = [r for r in rows if r["stage"] == "tts_acquire_end"]
        returned = [r for r in rows if r["stage"] == "tts_pool_disposition"]
        self.assertEqual(len(acquired), 1)
        self.assertEqual(len(returned), 1)
        for key in ("socketHash", "streamHash", "requestHash"):
            self.assertEqual(acquired[0][key], returned[0][key])
        self.assertEqual([r["leaseHash"] for r in acquired], [r["leaseHash"] for r in returned])

    async def test_observer_native_retry_keeps_each_attempt_lease_and_outcome(self):
        log = Mock()
        self.assertTrue(VoiceP0Timing(log, "synthetic-call", enabled=True).attach_xai(self.tts))
        self.next_options = {"error": True}
        self.assertTrue(await self.render(max_retry=1))
        rows = [json.loads(call.args[1]) for call in log.info.call_args_list]
        acquired = [r for r in rows if r["stage"] == "tts_acquire_end"]
        dispositions = [r for r in rows if r["stage"] == "tts_pool_disposition"]
        ended = [r for r in rows if r["stage"] == "tts_stream_end"]
        self.assertEqual([r["operation"] for r in dispositions], ["evicted", "returned"])
        self.assertEqual([r["status"] for r in ended], ["failed", "completed"])
        self.assertEqual(acquired[0]["streamHash"], acquired[1]["streamHash"])
        self.assertNotEqual(acquired[0]["requestHash"], acquired[1]["requestHash"])
        self.assertNotEqual(acquired[0]["leaseHash"], acquired[1]["leaseHash"])
        self.assertNotEqual(acquired[0]["socketHash"], acquired[1]["socketHash"])
        self.assertEqual([r["leaseHash"] for r in acquired], [r["leaseHash"] for r in dispositions])

    async def test_observer_active_option_eviction_does_not_guess_cancellation(self):
        log = Mock()
        self.assertTrue(VoiceP0Timing(log, "synthetic-call", enabled=True).attach_xai(self.tts))
        gate = asyncio.Event()
        self.next_options = {"gate": gate}
        render = asyncio.create_task(self.render())
        while not self.sockets:
            await asyncio.sleep(0)
        await self.sockets[0].text_done.wait()
        self.tts.update_options(voice="Eve")
        gate.set()
        self.assertTrue(await render)
        rows = [json.loads(call.args[1]) for call in log.info.call_args_list]
        removed = [r for r in rows if r["stage"] == "tts_pool_disposition"]
        ended = [r for r in rows if r["stage"] == "tts_stream_end"]
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]["operation"], "evicted")
        self.assertEqual(removed[0]["bindingStatus"], "active_lease")
        self.assertEqual(ended[0]["status"], "completed")
        self.assertEqual(removed[0]["leaseHash"], ended[0]["leaseHash"])

    async def test_observer_idle_option_eviction_does_not_reuse_old_speech_binding(self):
        log = Mock()
        self.assertTrue(VoiceP0Timing(log, "synthetic-call", enabled=True).attach_xai(self.tts))
        await self.render()
        self.tts.update_options(voice="Eve")
        rows = [json.loads(call.args[1]) for call in log.info.call_args_list]
        removed = [r for r in rows if r["stage"] == "tts_pool_disposition" and r["operation"] == "evicted"]
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]["bindingStatus"], "unbound")
        self.assertNotIn("leaseHash", removed[0])
        self.assertNotIn("streamHash", removed[0])
        self.assertNotIn("requestHash", removed[0])
        self.assertFalse(removed[0]["trackedAfter"])

    async def test_observer_disabled_or_logger_failure_keeps_native_pool_outcome(self):
        log = Mock()
        put, remove = self.tts._pool.put, self.tts._pool.remove
        self.assertFalse(VoiceP0Timing(log, "synthetic-call", enabled=False).attach_xai(self.tts))
        self.assertEqual(self.tts._pool.put, put)
        self.assertEqual(self.tts._pool.remove, remove)
        log.info.side_effect = RuntimeError("private diagnostic")
        self.assertTrue(VoiceP0Timing(log, "synthetic-call", enabled=True).attach_xai(self.tts))
        self.assertTrue(await self.render())
        self.assertTrue(await self.render())
        self.assertEqual(len(self.sockets), 1)
        self.assertEqual(len(self.tts._pool._available), 1)


class SupportTests(unittest.IsolatedAsyncioTestCase):
    def test_unsupported_version_retains_original_renderer(self):
        with patch("xai_pooled_tts.version", return_value="1.6.9"):
            tts = create_xai_tts(api_key="synthetic-test")
        self.assertIs(type(tts), xai.TTS)

    async def test_worker_turn_start_prewarms_primary_and_preserves_default_stream_chunks(self):
        import worker
        prewarm = Mock()
        mode = worker.AuthoritativeCallModeState()
        agent = worker.ViventiumVoiceAgent(instructions="Synthetic", prewarm_tts=prewarm,
                                           authoritative_mode_state=mode)
        chat_ctx, tools, settings, output = object(), object(), object(), object()
        async def source():
            yield output

        with patch.object(worker.Agent.default, "llm_node", side_effect=lambda *_args: source()) as node:
            for value in ("call", "wing", "listen_only", "uncertain"):
                mode.apply(value)
                self.assertEqual([chunk async for chunk in agent.llm_node(chat_ctx, tools, settings)], [output])
                node.assert_called_with(agent, chat_ctx, tools, settings)
        self.assertEqual(prewarm.call_count, 2)

    async def test_worker_prewarm_error_does_not_fail_model_node_or_log_private_content(self):
        import worker
        agent = worker.ViventiumVoiceAgent(instructions="Synthetic", prewarm_tts=Mock(
            side_effect=RuntimeError("private content must not be logged")))
        async def source():
            yield "output"

        with patch.object(worker.Agent.default, "llm_node", side_effect=lambda *_args: source()), patch.object(worker, "logger") as log:
            self.assertEqual([chunk async for chunk in agent.llm_node(None, [], None)], ["output"])
        self.assertEqual(log.warning.call_args.args[1], "RuntimeError")
        self.assertNotIn("private", str(log.warning.call_args))
