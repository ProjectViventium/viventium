"""Suspended mode retains exact owner-track evidence without granting authority."""
import asyncio
import socket
from types import SimpleNamespace
from unittest.mock import Mock
import unittest

from aiohttp import web
from librechat_llm import LibreChatAuth, LibreChatLLM
from livekit.agents.llm import ChatContext, ChatMessage
from livekit.agents.stt import SpeechData, SpeechEvent, SpeechEventType
from speaker_segments import SpeakerSegmentTracker, SPEAKER_CONTEXT_EXTRA_KEY
from worker import AuthoritativeCallModeState, ViventiumVoiceAgent
from test_voice_ingress_recovery import TestVoiceIngressRecovery as _IngressFixture


class TestPendingOwnerAttribution(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests, self.streams = [], []
        self.mode, self.status, self.prelaunch_failures = "call", 200, 0
        self.app = web.Application()
        self.app.router.add_post('/api/viventium/voice/chat', self.chat)
        self.app.router.add_get('/api/viventium/voice/stream/{stream}', self.sse)
        self.state_reads = 0
        async def call_state(request):
            self.state_reads += 1
            await self.fresh_ready.wait()
            return web.json_response({"version": 1, "callSessionId": "call_1",
                "mode": self.fresh_mode, "status": self.fresh_status,
                "revision": self.fresh_revision, "updatedAt": "2030-01-01T00:00:00Z"})
        self.app.router.add_get('/api/viventium/voice/call-sessions/call_1/state', call_state)
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        self.origin = f'http://127.0.0.1:{self.port}'
        self.llm = LibreChatLLM(origin=self.origin,
            auth=LibreChatAuth(call_session_id='call_1', call_secret='synthetic'), timeout_s=2)
        self.llm._start_task_continuation = Mock()

    def restore(self, mode="call", *, revision=3, status="listening"):
        self.fresh_mode, self.fresh_revision, self.fresh_status = mode, revision, status
        self.mode = mode
        self.mode_state.apply(mode, revision=revision)
        self.fresh_ready.set()
    async def asyncTearDown(self):
        for stream in self.streams:
            await stream.aclose()
        await self.llm.close_background_continuations()
        await self.llm.aclose()
        await self.runner.cleanup()
    chat = _IngressFixture.chat
    sse = _IngressFixture.sse

    def agent(self, *, owner=True, shared=False, diarization=False, mode="call"):
        self.mode_state = AuthoritativeCallModeState()
        self.mode_state.apply(mode, revision=3)
        self.fresh_ready = asyncio.Event()
        self.fresh_mode, self.fresh_revision, self.fresh_status = mode, 3, "listening"
        self.mode_state.suspend()
        self.tracker = SpeakerSegmentTracker(call_session_id="call_1", participant_identity="owner",
            track_sid="TR_owner", owner_signed=owner, initial_shared_microphone=shared)
        self.provider = SimpleNamespace(capabilities=SimpleNamespace(streaming=True, diarization=diarization))
        activity = SimpleNamespace(stt=self.provider, vad=None, _audio_recognition=None,
            session=SimpleNamespace(conn_options=SimpleNamespace(stt_conn_options=None),
                _recorder_io=None, _started_at=1_790_000_000.0))
        self.agent_impl = ViventiumVoiceAgent(instructions="Synthetic", speaker_tracker=self.tracker,
            authoritative_mode_state=self.mode_state, defer_turn_admission=True,
            refresh_call_state=lambda: self.llm.get_call_state(retry_unavailable=True))
        self.agent_impl._get_activity_or_raise = lambda: activity
        async def prepare(context):
            await self.agent_impl.resolve_pending_owner_track_attribution(context)
            return True
        self.llm.set_turn_admission_handler(prepare)

    async def source(self, identity, text="Open the example page in Chrome."):
        event = SpeechEvent(type=SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[SpeechData(language="en", text=text)])
        class SpeechStream:
            start_time=1_790_000_001.0
            start_time_offset=0.0
            async def __aenter__(self): return self
            async def __aexit__(self,*args): pass
            def push_frame(self, frame): pass
            async def __aiter__(self): yield event
        self.provider.stream=lambda **kwargs: SpeechStream()
        async def audio():
            yield SimpleNamespace(duration=.02)
            await asyncio.Event().wait()
        # Exercise production raw-STT attribution, not an already verified fixture.
        async for _ in self.agent_impl.stt_node(audio(), None): pass
        message=ChatMessage(id=identity,role="user",content=[text])
        await self.agent_impl.on_user_turn_completed(ChatContext.empty(),message)
        stream=self.llm.chat(chat_ctx=ChatContext(items=[message]));self.streams.append(stream)
        return stream,message

    async def test_first_source_waits_for_fresh_snapshot_then_preserves_exact_owner_identity(self):
        self.agent()
        await web.TCPSite(self.runner,"127.0.0.1",self.port).start()
        stream,message=await self.source("first")
        await asyncio.sleep(.02)
        self.assertEqual(self.requests,[])
        self.assertEqual(self.tracker._segments_by_id["segment_000001"]["speaker"]["actorTrust"],"unknown")
        self.restore()
        self.assertEqual([p.delta.content async for p in stream if p.delta and p.delta.content],["Four."])
        body=self.requests[0];segment=body["speakerSegments"][0]
        self.assertEqual(body["sourceEventId"],"voice:call_1:item:first")
        self.assertEqual(segment["segmentId"],"segment_000001")
        self.assertEqual(segment["revision"],2)
        self.assertEqual(segment["text"],message.text_content)
        self.assertEqual(segment["speaker"]["actorTrust"],"owner_participant")
        self.assertEqual(segment["speaker"]["source"],"participant_track")
        self.assertFalse(segment["uncertain"])
        self.assertEqual(body["speakerSegmentRevisions"],[segment])
        self.recovered_body=body

    async def test_a_b_c_interruptions_share_existing_admission_order_during_suspension(self):
        self.agent()
        await web.TCPSite(self.runner,"127.0.0.1",self.port).start()
        for identity in ("A","B"):
            stream,_=await self.source(identity,"Original "+identity)
            await asyncio.sleep(.01);await stream.aclose()
        last,_=await self.source("C","Original C")
        await asyncio.sleep(.01);self.assertEqual(self.requests,[])
        self.restore()
        await asyncio.wait_for(last._presentation.admission_task if last._presentation.admission_task else asyncio.sleep(.1),1)
        _=[p async for p in last]
        self.assertEqual([x["text"] for x in self.requests],["Original A","Original B","Original C"])
        self.assertEqual([x["speakerSegments"][0]["segmentId"] for x in self.requests],
                         ["segment_000001","segment_000002","segment_000003"])
        self.assertTrue(all(x["speakerSegments"][0]["speaker"]["actorTrust"]=="owner_participant" for x in self.requests))

    async def test_end_cancels_pending_attribution_without_late_post(self):
        self.agent()
        stream,_=await self.source("end")
        await asyncio.sleep(.02)
        await self.llm.close_background_continuations()
        self.restore()
        await web.TCPSite(self.runner,"127.0.0.1",self.port).start()
        await asyncio.sleep(.02)
        self.assertEqual(self.requests,[])
        self.assertTrue(stream._presentation.admission_task.done())

    async def test_fresh_mode_and_track_safety_controls_never_promote_unknown(self):
        for restriction in ("wing","listen_only","replaced","shared","overlap","revoked","source_changed"):
            with self.subTest(restriction=restriction):
                self.agent();stream,message=await self.source(restriction)
                await asyncio.sleep(.01)
                if restriction=="replaced":
                    self.tracker.update_participant_track(participant_identity="owner",track_sid="TR_new",owner_signed=True)
                elif restriction=="revoked":
                    self.tracker.update_participant_track(participant_identity="owner",track_sid="TR_owner",owner_signed=False)
                elif restriction=="shared": self.tracker._shared_microphone_tombstone=True
                elif restriction=="source_changed": self.tracker._segments_by_id["segment_000001"]["revision"] += 1
                elif restriction=="overlap":
                    context=message.extra[SPEAKER_CONTEXT_EXTRA_KEY]
                    context["speakerSegments"][0]["overlap"]=True
                    # Stream extracted the same source list before waiting.
                self.mode=restriction if restriction in ("wing","listen_only") else "call"
                self.restore(self.mode)
                if not getattr(self,"site_started",False):
                    await web.TCPSite(self.runner,"127.0.0.1",self.port).start();self.site_started=True
                _=[p async for p in stream]
                self.assertEqual(self.requests[-1]["speakerSegments"][0]["speaker"]["actorTrust"],"unknown")

    async def test_genuine_guest_unknown_or_diarizing_source_is_never_marked_pending(self):
        for options in ({"owner":False},{"shared":True},{"diarization":True},{"mode":"wing"},{"mode":"listen_only"}):
            with self.subTest(options=options):
                self.agent(**options)
                stream,_=await self.source(str(options))
                self.assertFalse(self.tracker._pending_owner_track_attribution)
                await stream.aclose()
                await self.llm.close_background_continuations()
                self.llm._speaker_delivery_closing=False

    async def test_healthy_call_uses_existing_owner_fallback_without_wait_or_refresh(self):
        self.agent();self.restore()
        self.agent_impl._refresh_speaker_track=Mock()
        await web.TCPSite(self.runner,"127.0.0.1",self.port).start()
        stream,_=await self.source("healthy")
        _=[p async for p in stream]
        self.assertEqual(self.state_reads, 0)
        self.agent_impl._refresh_speaker_track.assert_called_once()
        self.assertEqual(self.requests[0]["speakerSegments"][0]["revision"],1)
        self.assertEqual(self.requests[0]["speakerSegments"][0]["speaker"]["actorTrust"],"owner_participant")
        self.assertFalse(self.tracker._pending_owner_track_attribution)

    async def test_unseen_mode_writes_or_missing_revision_never_upgrade_pending_speech(self):
        for revision in (4, 5, None, True, -1):
            with self.subTest(revision=revision):
                self.agent()
                stream,_ = await self.source("changed-" + str(revision))
                await asyncio.sleep(.01)
                if not getattr(self,"site_started",False):
                    await web.TCPSite(self.runner,"127.0.0.1",self.port).start();self.site_started=True
                # Revision 5 represents unseen Call -> Wing -> Call. Current
                # Call alone cannot prove the mode under which this source arose.
                self.restore(revision=revision)
                _ = [p async for p in stream]
                segment = self.requests[-1]["speakerSegments"][0]
                self.assertEqual(segment["speaker"]["actorTrust"], "unknown")
                self.assertEqual(segment["revision"], 1)
                self.assertFalse(self.tracker._pending_owner_track_attribution)

    async def test_core_only_restart_keeps_revision_and_original_action_source(self):
        self.agent()
        stream,_ = await self.source("core-restart")
        await asyncio.sleep(.04)
        self.assertEqual(self.requests, [])
        self.restore()
        await web.TCPSite(self.runner,"127.0.0.1",self.port).start()
        _ = [p async for p in stream]
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.requests[0]["sourceEventId"], "voice:call_1:item:core-restart")
        self.assertEqual(self.requests[0]["speakerSegments"][0]["speaker"]["actorTrust"], "owner_participant")
        self.assertEqual(self.requests[0]["speakerSegments"][0]["revision"], 2)

    async def test_pending_read_does_not_restore_suspended_audio_authority(self):
        self.agent()
        await web.TCPSite(self.runner,"127.0.0.1",self.port).start()
        stream,_ = await self.source("read-only-authority")
        await asyncio.sleep(.01)
        self.fresh_mode, self.fresh_revision, self.fresh_status = "call", 3, "listening"
        self.fresh_ready.set()
        _ = [p async for p in stream]
        self.assertIsNone(self.mode_state.mode)
        self.assertEqual(self.requests[0]["speakerSegments"][0]["speaker"]["actorTrust"], "owner_participant")

    async def test_no_revision_anchor_does_not_mark_unknown_for_upgrade(self):
        self.agent()
        self.mode_state.apply("call")
        self.mode_state.suspend()
        stream,_ = await self.source("unproved-revision")
        self.assertFalse(self.tracker._pending_owner_track_attribution)
        await stream.aclose()
        await self.llm.close_background_continuations()

    def test_mode_revision_survives_suspension_and_tracks_each_new_snapshot(self):
        state = AuthoritativeCallModeState()
        state.apply("call", revision=3)
        state.suspend()
        self.assertIsNone(state.mode)
        self.assertEqual(state.last_observed_revision, 3)
        state.apply("wing", revision=4)
        self.assertEqual(state.last_observed_revision, 4)
        state.apply("call", revision=5)
        self.assertEqual(state.last_observed_revision, 5)

    async def test_recovered_segment_still_receives_later_shared_microphone_downgrade(self):
        self.agent()
        await web.TCPSite(self.runner,"127.0.0.1",self.port).start()
        stream,_ = await self.source("late-shared")
        await asyncio.sleep(.01)
        self.restore()
        _ = [p async for p in stream]
        self.assertEqual(self.tracker._segments_by_id["segment_000001"]["speaker"]["actorTrust"], "owner_participant")
        for index, speaker in enumerate(("first-provider", "second-provider")):
            self.tracker.ingest(transcript="A separate stable speaker.", is_final=True,
                provider_speaker_id=speaker, created_at=1_900_000_000.0 + index,
                start_time=float(index), end_time=float(index) + 1.0)
        downgraded = self.tracker._segments_by_id["segment_000001"]
        self.assertGreater(downgraded["revision"], 2)
        self.assertNotEqual(downgraded["speaker"]["actorTrust"], "owner_participant")
