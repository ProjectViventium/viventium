import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch
from livekit.agents.llm import ChatContext, ChatMessage
from librechat_llm import LibreChatLLM, LibreChatAuth, VoiceHopTrace
from test_librechat_llm import _CompletableSpeechHandle, _FakeLogicalStreamingSseSession, _voice_task_event


class TestAudibleProvisionalDeliveryLifecycle(unittest.IsolatedAsyncioTestCase):
    def _bound(self):
        llm = LibreChatLLM(origin="http://librechat.test",
            auth=LibreChatAuth(call_session_id="call_1", call_secret="synthetic"))
        llm.ack_delivery = AsyncMock(return_value=True)
        llm.schedule_trace_terminal = Mock()
        llm.record_completed_trace_stage = Mock(return_value=True)
        old = llm._presentation_coordinator.begin_stable(
            source_event_id="voice:call_1:item:old", presentation_ref="old")
        llm.register_trace(VoiceHopTrace(correlation_id=old.trace_id, call_session_id="call_1"))
        llm._presentation_coordinator.bind_core_context(old,
            {"logical_turn_id": "logical-1", "revision": 1})
        llm.bind_trace_core_context(old.trace_id, stream_id="old-stream", task_id="old-task",
            presentation=old)
        handle = _CompletableSpeechHandle("old-speech")
        handle.mark_audible_playout()
        old.output_offered = True
        llm.register_speech_handle(handle)
        llm._bind_next_speech_handle(old)
        return llm, old, handle

    async def _interrupt_first(self, llm, old, handle):
        llm.note_provisional_interruption()
        handle.complete(interrupted=True)
        await asyncio.sleep(0)
        llm.ack_delivery.assert_not_awaited()
        self.assertFalse(old.delivery_ack_task.done())

    async def test_audible_handle_done_precedes_distinct_stable_source(self):
        llm, old, handle = self._bound()
        await self._interrupt_first(llm, old, handle)
        successor = llm._presentation_coordinator.begin_stable(
            source_event_id="voice:call_1:item:new", presentation_ref="new")
        self.assertTrue(llm._presentation_coordinator.is_current(successor))
        await asyncio.wait_for(old.delivery_ack_task, 0.25)
        llm.ack_delivery.assert_awaited_once_with(logical_turn_id="logical-1", revision=1,
            state="partial_removed", presentation_ref="old-speech")
        await llm.close_background_continuations()

    async def test_same_source_does_not_claim_stable_supersession(self):
        llm, old, handle = self._bound()
        await self._interrupt_first(llm, old, handle)
        llm._presentation_coordinator.begin_stable(
            source_event_id=old.source_event_id, presentation_ref="retry")
        await asyncio.wait_for(old.delivery_ack_task, 0.25)
        self.assertEqual(llm.ack_delivery.await_args.kwargs["state"], "failed")
        await llm.close_background_continuations()

    async def test_end_resolves_pending_audible_interruption_and_drains_tasks(self):
        llm, old, handle = self._bound()
        await self._interrupt_first(llm, old, handle)
        await asyncio.wait_for(llm.close_background_continuations(), 0.25)
        self.assertEqual(llm.ack_delivery.await_args.kwargs["state"], "failed")
        self.assertTrue(old.delivery_ack_task.done())
        self.assertEqual(llm._delivery_ack_tasks, set())

    async def test_false_interruption_resumes_live_handle_without_terminal_ack(self):
        llm, old, handle = self._bound()
        llm.note_provisional_interruption()
        llm.resolve_false_interruption(handle, resumed=True)
        llm.ack_delivery.assert_not_awaited()
        self.assertFalse(handle.done())
        handle.complete(interrupted=False)
        await old.delivery_ack_task
        self.assertEqual(llm.ack_delivery.await_args.kwargs["state"], "committed")
        await llm.close_background_continuations()

    async def test_false_nonresumed_interruption_resolves_failed_after_handle_done(self):
        llm, old, handle = self._bound()
        await self._interrupt_first(llm, old, handle)
        llm.resolve_false_interruption(handle, resumed=False)
        await asyncio.wait_for(old.delivery_ack_task, 0.25)
        self.assertEqual(llm.ack_delivery.await_args.kwargs["state"], "failed")
        await llm.close_background_continuations()

    async def test_foreign_false_interruption_cannot_release_owned_waiter(self):
        llm, old, handle = self._bound()
        await self._interrupt_first(llm, old, handle)
        llm.resolve_false_interruption(_CompletableSpeechHandle("foreign"), resumed=False)
        await asyncio.sleep(0)
        llm.ack_delivery.assert_not_awaited()
        await llm.close_background_continuations()
        self.assertEqual(llm.ack_delivery.await_args.kwargs["state"], "failed")

    async def test_changed_call_or_revision_cannot_ack_old_binding(self):
        for changed in ("call", "revision"):
            with self.subTest(changed=changed):
                llm, old, handle = self._bound()
                await self._interrupt_first(llm, old, handle)
                if changed == "call":
                    llm._auth = LibreChatAuth(call_session_id="foreign", call_secret="synthetic")
                else:
                    old.revision = 2
                llm._presentation_coordinator.begin_stable(
                    source_event_id="voice:call_1:item:new", presentation_ref="new")
                self.assertFalse(await asyncio.wait_for(old.delivery_ack_task, 0.25))
                llm.ack_delivery.assert_not_awaited()
                await llm.close_background_continuations()

    async def test_pending_partial_ack_does_not_delay_successor_ready_receipt(self):
        llm, old, handle = self._bound()
        await self._interrupt_first(llm, old, handle)
        release = asyncio.Event()
        async def ack(**_kwargs):
            await release.wait()
            return True
        llm.ack_delivery = AsyncMock(side_effect=ack)
        fake = _FakeLogicalStreamingSseSession([{
            "final": True, "responseMessage": {"messageId": "new-answer",
                "content": [{"type": "text", "text": "Ordinary response."}]}}])
        with patch("librechat_llm.aiohttp.ClientSession", return_value=fake):
            stream = llm.chat(chat_ctx=ChatContext(items=[
                ChatMessage(role="user", content=["new ordinary input"])]))
            await asyncio.wait_for(stream._run(), 0.25)
            self.assertEqual(stream._presentation.logical_turn_id, "logical-1")
            self.assertFalse(old.delivery_ack_task.done())
            self.assertTrue(any("/voice/chat" in call[0] for call in fake.post_calls))
            release.set()
            await old.delivery_ack_task
        await llm.close_background_continuations()

    async def test_exact_owner_stop_resolves_pending_and_foreign_task_does_not(self):
        llm, old, handle = self._bound()
        await self._interrupt_first(llm, old, handle)
        foreign = _voice_task_event("foreign-stop", 1, taskId="foreign-task",
            state="cancelling", phase="cancelling", event_type="state",
            owner={"kind": "generation_job", "id": "foreign-stream"}, streamId="foreign-stream")
        self.assertTrue(await llm._relay_task_event_once(foreign))
        llm.ack_delivery.assert_not_awaited()
        owned = _voice_task_event("owned-stop", 1, taskId="old-task",
            state="cancelling", phase="cancelling", event_type="state",
            owner={"kind": "generation_job", "id": "old-stream"}, streamId="old-stream")
        self.assertTrue(await llm._relay_task_event_once(owned))
        await asyncio.wait_for(old.delivery_ack_task, 0.25)
        self.assertEqual(llm.ack_delivery.await_args.kwargs["state"], "failed")
        await llm.close_background_continuations()

    async def test_nonresumed_false_event_before_completion_does_not_hold_claim(self):
        llm, old, handle = self._bound()
        llm.note_provisional_interruption()
        llm.resolve_false_interruption(handle, resumed=False)
        handle.complete(interrupted=True)
        await asyncio.wait_for(old.delivery_ack_task, 0.25)
        self.assertEqual(llm.ack_delivery.await_args.kwargs["state"], "failed")
        await llm.close_background_continuations()

    async def test_completed_presentation_stop_keeps_exact_ref_boundary(self):
        for ref in ("foreign-speech", "old-speech"):
            with self.subTest(ref=ref):
                llm, old, handle = self._bound()
                await self._interrupt_first(llm, old, handle)
                event = _voice_task_event("completed-stop", 1, taskId="old-task",
                    state="completed", phase="completed", event_type="state",
                    owner={"kind": "generation_job", "id": "old-stream"}, streamId="old-stream",
                    presentation={"ref": ref, "state": "stop_requested", "startedAtMs": 1000})
                self.assertTrue(await llm._relay_task_event_once(event))
                if ref == "foreign-speech":
                    await asyncio.sleep(0)
                    llm.ack_delivery.assert_not_awaited()
                    await llm.close_background_continuations()
                else:
                    await asyncio.wait_for(old.delivery_ack_task, 0.25)
                    await llm.close_background_continuations()
                self.assertEqual(llm.ack_delivery.await_args.kwargs["state"], "failed")

    async def test_saved_vad_and_stt_events_mark_only_current_generated_handle_before_done(self):
        from types import SimpleNamespace
        from worker import _register_presentation_lifecycle_handlers
        events = (
            ("user_state_changed", SimpleNamespace(new_state="speaking")),
            ("user_input_transcribed", SimpleNamespace(transcript="ordinary interim input", is_final=False)),
            ("user_input_transcribed", SimpleNamespace(transcript="ordinary final input", is_final=True)),
        )
        for name, event in events:
            with self.subTest(event=name, final=getattr(event, "is_final", None)):
                llm, old, handle = self._bound()
                class Session:
                    current_speech = handle
                    handlers = {}
                    def on(self, name):
                        def register(handler):
                            self.handlers[name] = handler
                            return handler
                        return register
                session = Session()
                _register_presentation_lifecycle_handlers(session, llm)
                session.handlers[name](event)
                handle.complete(interrupted=True)
                await asyncio.sleep(0)
                llm.ack_delivery.assert_not_awaited()
                self.assertFalse(old.delivery_ack_task.done())
                llm._presentation_coordinator.begin_stable(
                    source_event_id="voice:call_1:item:new", presentation_ref="new")
                await asyncio.wait_for(old.delivery_ack_task, 0.25)
                self.assertEqual(llm.ack_delivery.await_args.kwargs["state"], "partial_removed")
                await llm.close_background_continuations()

    async def test_ordinary_events_do_not_hold_foreign_nongenerated_or_terminal_handles(self):
        from types import SimpleNamespace
        from worker import _register_presentation_lifecycle_handlers
        for mode in ("foreign", "absent", "done", "not_speaking", "blank"):
            with self.subTest(mode=mode):
                llm, old, handle = self._bound()
                selected = _CompletableSpeechHandle("not-a-generated-main") if mode == "foreign" else handle
                if mode == "absent":
                    selected = None
                if mode == "done":
                    selected._done = True
                class Session:
                    current_speech = selected
                    handlers = {}
                    def on(self, name):
                        def register(handler):
                            self.handlers[name] = handler
                            return handler
                        return register
                session = Session()
                _register_presentation_lifecycle_handlers(session, llm)
                name = "user_input_transcribed" if mode == "blank" else "user_state_changed"
                event = SimpleNamespace(transcript="" if mode == "blank" else "ordinary input",
                    new_state="listening" if mode == "not_speaking" else "speaking")
                session.handlers[name](event)
                self.assertEqual(old.provisional_interruptions, 0)
                handle.complete(interrupted=True)
                await asyncio.wait_for(old.delivery_ack_task, 0.25)
                self.assertEqual(llm.ack_delivery.await_args.kwargs["state"], "failed")
                await llm.close_background_continuations()

    async def test_typed_owner_interrupt_done_precedes_generate_reply_stable_source(self):
        from types import SimpleNamespace
        from worker import _handle_owner_text_input
        llm, old, handle = self._bound()
        stream = None
        async def interrupt():
            handle.complete(interrupted=True)
            await asyncio.sleep(0)
            llm.ack_delivery.assert_not_awaited()
        def generate_reply(*, user_input, input_modality):
            nonlocal stream
            self.assertEqual(input_modality, "text")
            stream = llm.chat(chat_ctx=ChatContext(items=[user_input]))
        session = SimpleNamespace(llm=llm, current_speech=handle,
            interrupt=interrupt, generate_reply=generate_reply)
        event = SimpleNamespace(participant=SimpleNamespace(identity="owner"),
            info=SimpleNamespace(stream_id="typed-source"), text="Ordinary typed continuation.")
        await _handle_owner_text_input(session, event, call_session_id="call_1",
            owner_participant_identity="owner")
        self.assertIsNotNone(stream)
        self.assertNotEqual(stream._presentation.source_event_id, old.source_event_id)
        await asyncio.wait_for(old.delivery_ack_task, 0.25)
        self.assertEqual(llm.ack_delivery.await_args.kwargs["state"], "partial_removed")
        await llm.close_background_continuations()

    async def test_foreign_typed_input_cannot_mark_or_interrupt_generated_main(self):
        from types import SimpleNamespace
        from worker import _handle_owner_text_input
        llm, old, handle = self._bound()
        session = SimpleNamespace(llm=llm, current_speech=handle,
            interrupt=AsyncMock(), generate_reply=Mock())
        event = SimpleNamespace(participant=SimpleNamespace(identity="foreign"),
            info=SimpleNamespace(stream_id="typed-source"), text="Ordinary typed input.")
        await _handle_owner_text_input(session, event, call_session_id="call_1",
            owner_participant_identity="owner")
        self.assertEqual(old.provisional_interruptions, 0)
        session.interrupt.assert_not_awaited()
        session.generate_reply.assert_not_called()
        handle.complete(interrupted=True)
        await asyncio.wait_for(old.delivery_ack_task, 0.25)
        self.assertEqual(llm.ack_delivery.await_args.kwargs["state"], "failed")
        await llm.close_background_continuations()

    async def test_progress_and_callback_forced_interrupts_do_not_mark_owner_supersession(self):
        from types import SimpleNamespace
        from worker import _interrupt_agent_session_speech, _interrupt_livekit_speech_handles
        llm, old, handle = self._bound()
        session = SimpleNamespace(interrupt=Mock(side_effect=lambda **_kwargs: handle.complete(interrupted=True)))
        _interrupt_agent_session_speech(session)
        await asyncio.wait_for(old.delivery_ack_task, 0.25)
        self.assertEqual(old.provisional_interruptions, 0)
        self.assertEqual(llm.ack_delivery.await_args.kwargs["state"], "failed")
        progress = SimpleNamespace(done=lambda: False, interrupt=Mock())
        pending = [progress]
        _interrupt_livekit_speech_handles(pending)
        progress.interrupt.assert_called_once_with(force=True)
        self.assertEqual(pending, [])
        self.assertEqual(old.provisional_interruptions, 0)
        await llm.close_background_continuations()
