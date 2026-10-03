import asyncio
import hashlib
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import MethodType, SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import worker
from librechat_llm import LibreChatAuth, LibreChatLLM
from worker import CortexFollowupScheduler


class _DummySession:
    def __init__(self) -> None:
        self.say_calls: list[dict[str, object]] = []
        self.speech_handles: list[_DummySpeechHandle] = []
        self.options = SimpleNamespace(tts_text_transforms=["filter_markdown", "filter_emoji"])
        self.current_agent = object()

    def say(self, text: str, *, audio=None, allow_interruptions: bool, add_to_chat_ctx: bool):
        self.say_calls.append(
            {
                "text": text,
                "audio": audio,
                "allow_interruptions": allow_interruptions,
                "add_to_chat_ctx": add_to_chat_ctx,
            }
        )
        handle = _DummySpeechHandle()
        self.speech_handles.append(handle)
        return handle


class _DummySpeechHandle:
    def __init__(self) -> None:
        self._done = False
        self.interrupt_forces = []
        self._callbacks = []

    def done(self) -> bool:
        return self._done

    def interrupt(self, *, force=False):
        self.interrupt_forces.append(force)
        self.complete()

    def complete(self):
        if self._done:
            return
        self._done = True
        for callback in tuple(self._callbacks):
            callback(self)

    def add_done_callback(self, callback):
        if self._done:
            callback(self)
            return
        self._callbacks.append(callback)


def _dispatch_permit(
    *,
    delivery_id: str,
    claim_id: str,
    generation: int = 1,
    expires_in_s: float = 60.0,
) -> dict[str, object]:
    return {
        "deliveryId": delivery_id,
        "claimId": claim_id,
        "surface": "voice",
        "permitId": "permit_" + "a" * 32,
        "permitGeneration": generation,
        "expiresAt": (
            datetime.now(timezone.utc) + timedelta(seconds=expires_in_s)
        ).isoformat(),
        "resultRevision": 1,
        "resultDigest": "sha256:" + "b" * 64,
    }


def _worker_completion_presentation(
    text: str,
    *,
    call_session_id: str = "call_123",
    message_id: str = "message-coalesced",
) -> dict[str, object]:
    digest = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
    return {
        "version": 1,
        "presentationRef": "voice_worker_completion_" + "c" * 64,
        "callSessionId": call_session_id,
        "turnId": "voice_worker_completion_turn_" + "c" * 64,
        "revision": 1,
        "responseMessageId": message_id,
        "responseDigest": "sha256:" + digest,
        "bindings": [
            {
                "originRef": "origin-a",
                "workRef": "work-a",
                "workerId": "worker-a",
                "runId": "run-a",
                "callbackRef": "callback_sha256:" + "a" * 64,
                "attemptNumber": 1,
                "resultKey": "ghtr_" + "a" * 64,
                "acceptedOperationId": "a" * 32,
                "terminalCallbackId": "cb_terminal_" + "a" * 64,
                "resultDigest": "sha256:" + "a" * 64,
                "resultRevision": 1,
                "effectGeneration": 1,
            }
        ],
    }


async def _renew_dispatch_permit_for_test(_self, _http_session, delivery, _permit):
    return _dispatch_permit(
        delivery_id=str(delivery["deliveryId"]),
        claim_id=str(delivery["claimId"]),
        expires_in_s=120,
    )


def _install_claimed_terminal_delivery(
    scheduler: CortexFollowupScheduler,
    *,
    callback_id: str,
    text: str,
) -> None:
    async def _claim(self, _http_session, latest):
        assert latest["callbackId"] == callback_id
        return {
            "deliveryId": f"ghcd_{callback_id}",
            "claimId": f"claim_{callback_id}",
            "callbackId": callback_id,
            "text": text,
        }

    async def _authorize(self, _http_session, delivery):
        return _dispatch_permit(
            delivery_id=str(delivery["deliveryId"]),
            claim_id=str(delivery["claimId"]),
        )

    async def _maintain(
        self,
        _http_session,
        _delivery,
        _permit,
        _speech_handle,
        **_kwargs,
    ):
        return True

    scheduler._claim_glasshive_delivery = MethodType(_claim, scheduler)
    scheduler._authorize_glasshive_delivery = MethodType(_authorize, scheduler)
    scheduler._renew_glasshive_delivery_permit = MethodType(
        _renew_dispatch_permit_for_test, scheduler
    )
    scheduler._maintain_glasshive_speech_permit = MethodType(_maintain, scheduler)


class _FakeClientSession:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeResponse:
    def __init__(self, status: int, payload: object) -> None:
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def json(self):
        return self._payload


class _RecordingPostSession:
    def __init__(self, responses: list[tuple[int, object]]) -> None:
        self.responses = list(responses)
        self.posts: list[dict[str, object]] = []

    def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]):
        self.posts.append({"url": url, "headers": headers, "json": json})
        status, payload = self.responses.pop(0)
        return _FakeResponse(status, payload)


class TestCortexFollowupScheduler(unittest.IsolatedAsyncioTestCase):
    def _callwide_event(self, *, child=False, **changes):
        event = {
            "version": 1,
            "eventId": "child_completed" if child else "parent_completed",
            "taskId": "child_task" if child else "parent_task",
            "callSessionId": "call_123",
            "conversationId": "conversation_123",
            "parentTaskId": "parent_task" if child else "",
            "streamId": "worker_stream" if child else "main_stream",
            "owner": {"kind": "glasshive_run" if child else "remote_generation",
                      "id": "worker_run" if child else "main_stream"},
            "state": "completed", "phase": "completed", "type": "result",
            "sequence": 4, "emittedAt": "2026-01-01T00:00:00Z",
            "cancellable": False, "retryable": False,
            "resultMessageId": "mission_callback_not_anchor" if child else "main_anchor",
        }
        return {**event, **changes}

    def _callwide_llm(self, scheduler):
        llm = LibreChatLLM(
            origin="http://example.test", auth=scheduler._auth,
            task_event_handler=lambda event: scheduler.on_task_event(
                event, is_task_suppressed=llm.is_task_output_suppressed,
            ),
        )
        return llm

    async def test_callwide_worker_join_converges_in_both_orders_and_replay(self):
        for child_first in (False, True):
            with self.subTest(child_first=child_first):
                scheduler = self._build_scheduler(session=_DummySession())
                scheduler._run = mock.AsyncMock()
                llm = self._callwide_llm(scheduler)
                parent, child = self._callwide_event(), self._callwide_event(child=True)
                events = [child, parent] if child_first else [parent, child]
                for event in events + events + [
                    {**child, "eventId": "newer_terminal", "sequence": 5},
                    {**child, "eventId": "older_terminal", "sequence": 3},
                ]:
                    await llm._relay_task_event_once(event)
                await asyncio.gather(*scheduler._glasshive_tasks)
                scheduler._run.assert_awaited_once()
                args, kwargs = scheduler._run.await_args
                self.assertEqual(args[1], "main_anchor")
                self.assertFalse(kwargs["should_poll_cortex"])
                self.assertTrue(kwargs["should_poll_glasshive"])
                self.assertTrue(kwargs["wait_for_delivery"])
                self.assertIsNone(kwargs["presentation_is_current"])
                self.assertEqual(scheduler._seq, 0)
                self.assertIsNone(scheduler._task)
                self.assertIsNone(scheduler._cortex_task)
                await scheduler.close()
                self.assertEqual(scheduler._task_refs, {})
                self.assertEqual(scheduler._worker_followup_pairs, {})

    async def test_callwide_workers_keep_distinct_parent_and_child_pairs(self):
        scheduler = self._build_scheduler(session=_DummySession())
        scheduler._run = mock.AsyncMock()
        llm = self._callwide_llm(scheduler)
        parent, child = self._callwide_event(), self._callwide_event(child=True)
        for event in [parent, child,
                      self._callwide_event(child=True, taskId="other_child", eventId="other_child"),
                      self._callwide_event(taskId="other_parent", eventId="other_parent",
                                           streamId="other_stream", resultMessageId="other_anchor",
                                           owner={"kind": "remote_generation", "id": "other_stream"}),
                      self._callwide_event(child=True, taskId="third_child", eventId="third_child",
                                           parentTaskId="other_parent")]:
            await llm._relay_task_event_once(event)
        await asyncio.gather(*scheduler._glasshive_tasks)
        self.assertEqual([call.args[1] for call in scheduler._run.await_args_list],
                         ["main_anchor", "main_anchor", "other_anchor"])
        self.assertEqual(len(scheduler._worker_followup_pairs), 3)
        scheduler.cancel_pending()
        self.assertEqual(len(scheduler._task_refs), 5)
        self.assertEqual(scheduler._worker_followup_pairs, {})
        await scheduler.close()
        self.assertEqual(scheduler._task_refs, {})

    async def test_callwide_cancel_keeps_unrelated_running_worker_parent(self):
        scheduler = self._build_scheduler(session=_DummySession())
        scheduler._run = mock.AsyncMock()
        llm = self._callwide_llm(scheduler)
        parent = self._callwide_event()
        child = self._callwide_event(child=True, state="running")
        await llm._relay_task_event_once(parent)
        await llm._relay_task_event_once(child)
        progress = mock.Mock()
        worker._apply_task_cancel_suppression(
            "unrelated_task", progress_controller=progress,
            followup_scheduler=scheduler, session=_DummySession(),
        )
        progress.suppress_task.assert_called_once_with("unrelated_task")
        terminal = {**child, "state": "completed", "sequence": 5,
                    "eventId": "worker_after_unrelated_cancel"}
        await llm._relay_task_event_once(terminal)
        await llm._relay_task_event_once(terminal)
        await asyncio.gather(*scheduler._glasshive_tasks)
        scheduler._run.assert_awaited_once()
        self.assertEqual(scheduler._run.await_args.args[1], "main_anchor")
        await scheduler.close()

    async def test_callwide_worker_join_refuses_foreign_missing_and_cancelled_sources(self):
        variants = [
            ("wrong_call", {}, {"callSessionId": "another_call"}),
            ("wrong_conversation", {}, {"conversationId": "another_conversation"}),
            ("missing_parent", {}, {"parentTaskId": "missing"}),
            ("missing_main_result", {"resultMessageId": ""}, {}),
            ("wrong_parent_owner", {"owner": {"kind": "glasshive_run", "id": "main_stream"}}, {}),
            ("wrong_parent_stream", {"streamId": "different_stream"}, {}),
            ("cancelled_parent", {"state": "cancelled"}, {}),
            ("cancelled_child", {}, {"state": "cancelled"}),
            ("running_child", {}, {"state": "running"}),
        ]
        for name, parent_change, child_change in variants:
            with self.subTest(case=name):
                scheduler = self._build_scheduler(session=_DummySession())
                scheduler._run = mock.AsyncMock()
                llm = self._callwide_llm(scheduler)
                await llm._relay_task_event_once(self._callwide_event(**parent_change))
                await llm._relay_task_event_once(self._callwide_event(child=True, **child_change))
                self.assertEqual(scheduler._glasshive_tasks, set())
                scheduler._run.assert_not_called()
                await scheduler.close()
        scheduler = self._build_scheduler(session=_DummySession())
        scheduler._run = mock.AsyncMock()
        llm = self._callwide_llm(scheduler)
        await llm._relay_task_event_once(self._callwide_event())
        llm._task_event_gate.mark_cancel_accepted("child_task")
        await llm._relay_task_event_once(self._callwide_event(child=True))
        scheduler._run.assert_not_called()
        await scheduler.close()

    async def test_callwide_worker_arm_preserves_concurrent_cortex_delivery(self):
        session = _DummySession()
        scheduler = self._build_scheduler(session=session, timeout_s=2)
        llm = self._callwide_llm(scheduler)
        cortex_entered, release_cortex = asyncio.Event(), asyncio.Event()

        async def fetch_cortex(_self, _http, _message):
            cortex_entered.set()
            await release_cortex.wait()
            return {"followUp": {"messageId": "cortex_answer", "text": "Current Cortex answer."}}

        async def fetch_worker(_self, _http, _message):
            await asyncio.Future()

        scheduler._fetch_cortex = MethodType(fetch_cortex, scheduler)
        scheduler._fetch_glasshive = MethodType(fetch_worker, scheduler)
        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule("newer_main", [], "", cortex_expected=True)
            cortex_task, seq = scheduler._cortex_task, scheduler._seq
            await cortex_entered.wait()
            await llm._relay_task_event_once(self._callwide_event())
            await llm._relay_task_event_once(self._callwide_event(child=True))
            self.assertEqual(scheduler._seq, seq)
            self.assertIs(scheduler._cortex_task, cortex_task)
            self.assertIs(scheduler._task, cortex_task)
            release_cortex.set()
            await cortex_task
            self.assertEqual([call["text"] for call in session.say_calls], ["Current Cortex answer."])
            self.assertEqual(len(scheduler._glasshive_tasks), 1)
            await scheduler.close()

    async def test_callwide_worker_waits_zero_to_ten_seconds_for_core_enqueue(self):
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        scheduler._glasshive_timeout_s = 20
        llm = self._callwide_llm(scheduler)
        scheduler._fetch_cortex = mock.AsyncMock(return_value={
            "followUpDecision": {"result": "suppressed", "llmResult": "nta",
                                 "selectedStrategy": "no_response_suppressed",
                                 "suppressionReason": "no_response_tag"},
        })
        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule("main_anchor", [], "", cortex_expected=True)
            await scheduler._cortex_task
        self.assertEqual(session.say_calls, [])
        self.assertEqual(scheduler._fetch_cortex.await_count, 1)
        cortex_seq = scheduler._seq
        claim = scheduler._claim_glasshive_delivery
        _install_claimed_terminal_delivery(scheduler, callback_id="callback_ready",
                                           text="Main-authored completed report.")
        scheduler._claim_glasshive_delivery = claim
        elapsed, claims, anchors = [0.0], [], []

        class DelayedSession(_FakeClientSession):
            def get(self, url, *, headers):
                anchors.append(url)
                return _FakeResponse(200, {"latest": {"callbackId": "callback_ready",
                    "event": "run.completed", "text": "Early mission callback."}})

            def post(self, url, *, headers, json):
                claims.append(elapsed[0])
                deliveries = [] if elapsed[0] < 10 else [{
                    "deliveryId": "delivery_ready", "claimId": "claim_ready",
                    "callbackId": "callback_sha256:" + hashlib.sha256(b"callback_ready").hexdigest(), "userId": "synthetic_owner",
                    "voiceCallSessionId": "call_123", "text": "Main-authored completed report.",
                }]
                elapsed[0] += 2
                return _FakeResponse(200, {"deliveries": deliveries})

        with mock.patch.object(worker.aiohttp, "ClientSession", DelayedSession), \
             mock.patch.object(worker, "time", SimpleNamespace(monotonic=lambda: elapsed[0])):
            await llm._relay_task_event_once(self._callwide_event())
            await llm._relay_task_event_once(self._callwide_event(child=True))
            await asyncio.gather(*scheduler._glasshive_tasks)
        self.assertEqual(claims, [0, 2, 4, 6, 8, 10])
        self.assertEqual(scheduler._seq, cortex_seq)
        self.assertEqual(scheduler._fetch_cortex.await_count, 1)
        self.assertTrue(all(url.endswith("/glasshive/main_anchor") for url in anchors))
        self.assertEqual([call["text"] for call in session.say_calls],
                         ["Main-authored completed report."])
        await scheduler.close()

    async def test_file_followup_keeps_display_link_and_exact_capped_speech(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        text = "[sigh] Your report is ready 🙂. " + "Useful detail. " * 250
        text += " [Download report](https://example.invalid/files/report.pdf?revision=2&view=owner)"
        rendered = []

        async def tts_node(agent, source, settings):
            self.assertIs(agent, session.current_agent)
            async for value in source:
                rendered.append(value)
            yield object()

        with mock.patch.object(worker.Agent.default, "tts_node", tts_node):
            queued, handle, reason = scheduler._start_speech(text, scheduler._seq)
            self.assertTrue(queued)
            self.assertEqual(reason, "queued")
            self.assertEqual(rendered, [])  # No synthesis before SDK consumes audio.
            call = session.say_calls[-1]
            self.assertIn("https://example.invalid/files/report.pdf?revision=2&view=owner", call["text"])
            self.assertGreater(len(call["text"]), worker._voice_followup_tts_max_chars())
            async for _ in call["audio"]:
                pass
        expected = worker.cap_voice_followup_for_tts(worker.sanitize_voice_followup_text(text))
        self.assertEqual("".join(rendered), expected.replace("🙂", ""))
        self.assertNotIn("https://", "".join(rendered))
        self.assertNotIn("[sigh]", "".join(rendered))
        self.assertIn("I have the full report in the chat.", "".join(rendered))
        self.assertIn(handle, scheduler._speech_handles)
        handle.complete()
        self.assertNotIn(handle, scheduler._speech_handles)
        await scheduler.close()

    async def test_supplied_followup_audio_closes_selected_node_on_interruption(self) -> None:
        session = _DummySession()
        closed = []

        async def tts_node(agent, source, settings):
            try:
                async for value in source:
                    yield value
                await asyncio.Future()
            finally:
                closed.append(True)

        with mock.patch.object(worker.Agent.default, "tts_node", tts_node):
            audio = worker._voice_followup_audio(session, "Safe complete speech.")
            self.assertEqual(closed, [])
            await anext(audio)
            await audio.aclose()
        self.assertEqual(closed, [True])

    async def test_intentional_followup_silence_is_skipped_not_failed(self) -> None:
        for reason in ("listen_only", "not_authoritative", "empty", "no_response"):
            session = _DummySession()
            scheduler = self._build_scheduler(session=session)
            scheduler._trace_handler = mock.AsyncMock(return_value=True)
            text = "Synthetic follow-up."
            if reason == "listen_only": scheduler._mode = "listen_only"
            if reason == "not_authoritative": scheduler._authoritative_mode_available = False
            if reason == "empty": text = ""
            if reason == "no_response": text = "{NTA}"
            self.assertFalse(scheduler._speak_cortex_followup(text, scheduler._seq,
                trace_id="trace-one", presentation_ref="followup-one"))
            await asyncio.sleep(0)
            await scheduler.close()
            self.assertEqual([c.args[2] for c in scheduler._trace_handler.await_args_list], ["audio.superseded"])

    async def test_followup_trace_requires_playout_and_reports_interruption_and_stale(self) -> None:
        for outcome in ("audible", "failed", "interrupted", "stale"):
            session = _DummySession()
            scheduler = self._build_scheduler(session=session)
            scheduler._trace_handler = mock.AsyncMock(return_value=True)
            current = {"value": True}
            scheduler._speak_cortex_followup("Synthetic follow-up.", scheduler._seq,
                trace_id="trace-one", presentation_ref="followup-one",
                presentation_is_current=lambda: current["value"])
            self.assertEqual(scheduler._trace_handler.await_count, 0)
            handle = session.speech_handles[-1]
            handle.interrupted = outcome == "interrupted"
            handle.chat_items = []  # LiveKit say(add_to_chat_ctx=False) has no chat-item metrics.
            if outcome == "audible": scheduler.note_started_playout(handle)
            if outcome == "stale": current["value"] = False
            handle.complete()
            await asyncio.sleep(0)
            await scheduler.close()
            stages = [call.args[2] for call in scheduler._trace_handler.await_args_list]
            expected = {"audible": ["tts.completed", "audio.completed"], "failed": ["audio.failed"],
                "interrupted": ["audio.interrupted"], "stale": ["audio.superseded"]}
            self.assertEqual(stages, expected[outcome])

    def _build_scheduler(
        self,
        *,
        session: _DummySession,
        timeout_s: float = 0.03,
        interval_s: float = 0.001,
        grace_s: float = 0.005,
    ) -> CortexFollowupScheduler:
        return CortexFollowupScheduler(
            origin="http://example.test",
            auth=LibreChatAuth(call_session_id="call_123", call_secret="secret_123"),
            session=session,
            timeout_s=timeout_s,
            interval_s=interval_s,
            grace_s=grace_s,
        )

    async def test_speaks_only_persisted_followup(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)

        async def _fake_fetch(self, _http_session, _message_id):
            return {
                "insights": [{"cortex_id": "pattern", "insight": "Background thought."}],
                "followUp": {"messageId": "follow_123", "text": "Here is the real follow-up."},
            }

        scheduler._fetch_cortex = MethodType(_fake_fetch, scheduler)

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule("msg_123", [], "", cortex_expected=True)
            await scheduler._task

        self.assertEqual(len(session.say_calls), 1)
        self.assertEqual(session.say_calls[0]["text"], "Here is the real follow-up.")
        self.assertEqual(session.say_calls[0]["allow_interruptions"], True)
        self.assertEqual(session.say_calls[0]["add_to_chat_ctx"], False)

    async def test_stable_supersession_stops_stale_followup_without_claiming_durable_result(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        fetch_calls = []

        async def _fake_fetch(self, _http_session, message_id):
            fetch_calls.append(message_id)
            return {
                "latest": {
                    "callbackId": "callback-1",
                    "text": "Late durable result must not speak as the stale response.",
                    "status": "completed",
                }
            }

        scheduler._fetch_glasshive = MethodType(_fake_fetch, scheduler)

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule(
                "msg_123",
                [],
                "",
                cortex_expected=False,
                glasshive_expected=True,
                presentation_is_current=lambda: False,
            )
            await scheduler._task

        self.assertEqual(fetch_calls, [])
        self.assertEqual(session.say_calls, [])

    async def test_listen_only_suppresses_callback_and_call_mode_resumes(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)

        async def _fake_fetch(self, _http_session, message_id):
            return {
                "insights": [{"cortex_id": "pattern", "insight": "Background thought."}],
                "followUp": {"messageId": message_id, "text": f"Follow-up {message_id}"},
            }

        scheduler._fetch_cortex = MethodType(_fake_fetch, scheduler)

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.set_mode("listen_only")
            scheduler.schedule("silent", [], "", cortex_expected=True)
            await scheduler._task
            scheduler.set_mode("call")
            scheduler.schedule("audible", [], "", cortex_expected=True)
            await scheduler._task

        self.assertEqual(
            [call["text"] for call in session.say_calls],
            ["Follow-up audible"],
        )

    async def test_switch_to_listen_only_interrupts_active_followup_handle(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        self.assertTrue(scheduler._speak("Current follow-up", 0))
        handle = next(iter(scheduler._speech_handles))

        scheduler.set_mode("listen_only")

        self.assertEqual(handle.interrupt_forces, [True])
        self.assertEqual(scheduler._speech_handles, set())

    async def test_close_cancels_pollers_and_active_followup_audio(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        self.assertTrue(scheduler._speak("Current follow-up", 0))
        handle = next(iter(scheduler._speech_handles))
        poller = asyncio.create_task(asyncio.sleep(60))
        scheduler._task = poller
        scheduler._cortex_task = poller

        await scheduler.close()

        self.assertTrue(poller.cancelled())
        self.assertEqual(handle.interrupt_forces, [True])

    async def test_keeps_background_insights_silent_without_followup(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session, timeout_s=0.02, grace_s=0.003)

        async def _fake_fetch(self, _http_session, _message_id):
            return {
                "insights": [{"cortex_id": "pattern", "insight": "Internal background realization."}],
                "followUp": None,
            }

        scheduler._fetch_cortex = MethodType(_fake_fetch, scheduler)

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule("msg_123", [], "", cortex_expected=True)
            await scheduler._task

        self.assertEqual(session.say_calls, [])

    async def test_suppresses_no_response_followup(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)

        async def _fake_fetch(self, _http_session, _message_id):
            return {
                "insights": [{"cortex_id": "pattern", "insight": "Background thought."}],
                "followUp": {"messageId": "follow_123", "text": "{NTA}"},
            }

        scheduler._fetch_cortex = MethodType(_fake_fetch, scheduler)

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule("msg_123", [], "", cortex_expected=True)
            await scheduler._task

        self.assertEqual(session.say_calls, [])

    async def test_stops_polling_when_server_reports_silent_followup_decision(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session, timeout_s=0.2, grace_s=0.05)
        calls = 0

        async def _fake_fetch(self, _http_session, _message_id):
            nonlocal calls
            calls += 1
            return {
                "insights": [{"cortex_id": "pattern", "insight": "Internal background realization."}],
                "followUp": None,
                "followUpDecision": {
                    "result": "suppressed",
                    "llmResult": "nta",
                    "selectedStrategy": "no_response_suppressed",
                    "suppressionReason": "no_response_tag",
                },
            }

        scheduler._fetch_cortex = MethodType(_fake_fetch, scheduler)

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule("msg_123", [], "", cortex_expected=True)
            await scheduler._task

        self.assertEqual(session.say_calls, [])
        self.assertEqual(calls, 1)

    async def test_does_not_treat_persisted_decision_with_reason_as_silent_terminal(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session, timeout_s=0.7, grace_s=0.01)
        calls = 0

        async def _fake_fetch(self, _http_session, _message_id):
            nonlocal calls
            calls += 1
            if calls == 1:
                return {
                    "insights": [],
                    "followUp": None,
                    "followUpDecision": {
                        "result": "persisted",
                        "selectedStrategy": "deferred",
                        "suppressionReason": "older_user_message",
                    },
                }
            return {
                "insights": [{"cortex_id": "pattern", "insight": "Background thought."}],
                "followUp": {"messageId": "follow_123", "text": "Follow-up after persistence."},
            }

        scheduler._fetch_cortex = MethodType(_fake_fetch, scheduler)

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule("msg_123", [], "", cortex_expected=True)
            await scheduler._task

        self.assertEqual(len(session.say_calls), 1)
        self.assertEqual(session.say_calls[0]["text"], "Follow-up after persistence.")
        self.assertEqual(calls, 2)

    async def test_terminal_glasshive_result_without_callback_identity_is_silent(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)

        async def _fake_fetch_cortex(self, _http_session, _message_id):
            return {"insights": [], "followUp": None}

        async def _fake_fetch_glasshive(self, _http_session, _message_id):
            return {"latest": {"event": "run.completed", "text": "The worker finished the invoice check."}}

        scheduler._fetch_cortex = MethodType(_fake_fetch_cortex, scheduler)
        scheduler._fetch_glasshive = MethodType(_fake_fetch_glasshive, scheduler)

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule("msg_123", [], "", glasshive_expected=True)
            await scheduler._task

        self.assertEqual(session.say_calls, [])

    async def test_claims_glasshive_delivery_before_speaking_full_text(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        marked: list[tuple[str, str, int]] = []

        async def _fake_fetch_cortex(self, _http_session, _message_id):
            return {"insights": [], "followUp": None}

        async def _fake_fetch_glasshive(self, _http_session, _message_id):
            return {
                "latest": {
                    "event": "run.completed",
                    "text": "Short preview.",
                    "callbackId": "cb_voice",
                }
            }

        async def _fake_claim(self, _http_session, latest):
            assert latest["callbackId"] == "cb_voice"
            return {
                "deliveryId": "ghcd_voice",
                "claimId": "claim_voice",
                "text": "Short preview.",
                "fullText": "Full voice callback result.",
            }

        async def _fake_authorize(self, _http_session, delivery):
            return _dispatch_permit(
                delivery_id=str(delivery["deliveryId"]),
                claim_id=str(delivery["claimId"]),
            )

        async def _fake_mark(
            self,
            _http_session,
            delivery,
            status,
            *,
            dispatch_permit=None,
            error="",
            reason="",
        ):
            _ = error, reason
            marked.append(
                (
                    delivery["deliveryId"],
                    status,
                    int((dispatch_permit or {}).get("permitGeneration") or 0),
                )
            )
            return True

        scheduler._fetch_cortex = MethodType(_fake_fetch_cortex, scheduler)
        scheduler._fetch_glasshive = MethodType(_fake_fetch_glasshive, scheduler)
        scheduler._claim_glasshive_delivery = MethodType(_fake_claim, scheduler)
        scheduler._authorize_glasshive_delivery = MethodType(_fake_authorize, scheduler)
        scheduler._renew_glasshive_delivery_permit = MethodType(
            _renew_dispatch_permit_for_test, scheduler
        )
        scheduler._mark_glasshive_delivery_status = MethodType(_fake_mark, scheduler)

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule("msg_123", [], "", glasshive_expected=True)
            while not session.speech_handles:
                await asyncio.sleep(0)
            session.speech_handles[0].complete()
            await scheduler._task

        self.assertEqual(session.say_calls[0]["text"], "Full voice callback result.")
        self.assertEqual(marked, [("ghcd_voice", "sent", 1)])

    async def test_final_pre_speech_renewal_suppresses_a_after_b_wins(
        self,
    ) -> None:
        session_a = _DummySession()
        session_b = _DummySession()
        scheduler_a = self._build_scheduler(session=session_a)
        scheduler_b = self._build_scheduler(session=session_b)
        renewal_entered = asyncio.Event()
        release_a_renewal = asyncio.Event()
        winner = {"callback_id": "cb_voice_race_a"}

        async def _fake_fetch_a(self, _http_session, _message_id):
            return {
                "latest": {
                    "event": "run.completed",
                    "text": "Revision A must be fenced.",
                    "callbackId": "cb_voice_race_a",
                }
            }

        async def _fake_fetch_b(self, _http_session, _message_id):
            return {
                "latest": {
                    "event": "run.completed",
                    "text": "Revision B is current.",
                    "callbackId": "cb_voice_race_b",
                }
            }

        async def _fake_claim_a(self, _http_session, _latest):
            return {
                "deliveryId": "ghcd_voice_race_a",
                "claimId": "claim_voice_race_a",
                "callbackId": "cb_voice_race_a",
                "text": "Revision A must be fenced.",
            }

        async def _fake_claim_b(self, _http_session, _latest):
            return {
                "deliveryId": "ghcd_voice_race_b",
                "claimId": "claim_voice_race_b",
                "callbackId": "cb_voice_race_b",
                "text": "Revision B is current.",
            }

        async def _fake_authorize(self, _http_session, delivery):
            return _dispatch_permit(
                delivery_id=str(delivery["deliveryId"]),
                claim_id=str(delivery["claimId"]),
            )

        async def _fake_renew_a(self, _http_session, _delivery, _permit):
            renewal_entered.set()
            await release_a_renewal.wait()
            return None

        async def _fake_renew_b(self, _http_session, delivery, _permit):
            assert winner["callback_id"] == "cb_voice_race_b"
            return _dispatch_permit(
                delivery_id=str(delivery["deliveryId"]),
                claim_id=str(delivery["claimId"]),
                expires_in_s=120,
            )

        async def _fake_mark(
            self,
            _http_session,
            _delivery,
            _status,
            *,
            dispatch_permit=None,
            error="",
            reason="",
        ):
            _ = dispatch_permit, error, reason
            return True

        scheduler_a._fetch_glasshive = MethodType(_fake_fetch_a, scheduler_a)
        scheduler_a._claim_glasshive_delivery = MethodType(_fake_claim_a, scheduler_a)
        scheduler_a._authorize_glasshive_delivery = MethodType(
            _fake_authorize, scheduler_a
        )
        scheduler_a._renew_glasshive_delivery_permit = MethodType(
            _fake_renew_a, scheduler_a
        )
        scheduler_a._mark_glasshive_delivery_status = MethodType(
            _fake_mark, scheduler_a
        )
        scheduler_b._fetch_glasshive = MethodType(_fake_fetch_b, scheduler_b)
        scheduler_b._claim_glasshive_delivery = MethodType(_fake_claim_b, scheduler_b)
        scheduler_b._authorize_glasshive_delivery = MethodType(
            _fake_authorize, scheduler_b
        )
        scheduler_b._renew_glasshive_delivery_permit = MethodType(
            _fake_renew_b, scheduler_b
        )
        scheduler_b._mark_glasshive_delivery_status = MethodType(
            _fake_mark, scheduler_b
        )

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler_a.schedule("msg_voice_race_a", [], "", glasshive_expected=True)
            try:
                await asyncio.wait_for(renewal_entered.wait(), timeout=1.0)
                winner["callback_id"] = "cb_voice_race_b"
                scheduler_b.schedule(
                    "msg_voice_race_b", [], "", glasshive_expected=True
                )
                while not session_b.speech_handles:
                    await asyncio.sleep(0)
                session_b.speech_handles[0].complete()
                await asyncio.wait_for(scheduler_b._task, timeout=1.0)
                release_a_renewal.set()
                await asyncio.wait_for(scheduler_a._task, timeout=1.0)
            finally:
                release_a_renewal.set()
                for task in (scheduler_a._task, scheduler_b._task):
                    if task is not None and not task.done():
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)

        self.assertEqual(session_a.say_calls, [])
        self.assertEqual(
            [call["text"] for call in session_b.say_calls],
            ["Revision B is current."],
        )

    async def test_terminal_callback_without_a_claim_never_speaks_or_marks(
        self,
    ) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        side_effects: list[str] = []

        async def _fake_fetch(self, _http_session, _message_id):
            return {
                "latest": {
                    "event": "run.completed",
                    "text": "Unclaimed terminal callback.",
                    "callbackId": "cb_voice_unclaimed",
                }
            }

        async def _fake_claim(self, _http_session, _latest):
            return None

        async def _unexpected(*_args, **_kwargs):
            side_effects.append("ledger")
            return True

        scheduler._fetch_glasshive = MethodType(_fake_fetch, scheduler)
        scheduler._claim_glasshive_delivery = MethodType(_fake_claim, scheduler)
        scheduler._mark_glasshive_delivery_status = MethodType(_unexpected, scheduler)

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule("msg_voice_unclaimed", [], "", glasshive_expected=True)
            await asyncio.wait_for(scheduler._task, timeout=1.0)

        self.assertEqual(session.say_calls, [])
        self.assertEqual(side_effects, [])

    async def test_two_dispatchers_claim_once_and_only_the_winner_speaks(
        self,
    ) -> None:
        sessions = [_DummySession(), _DummySession()]
        schedulers = [self._build_scheduler(session=session) for session in sessions]
        claim_lock = asyncio.Lock()
        claim_won = False
        marked: list[str] = []

        async def _fake_fetch(self, _http_session, _message_id):
            return {
                "latest": {
                    "event": "run.completed",
                    "text": "One terminal utterance.",
                    "callbackId": "cb_voice_claim_once",
                }
            }

        async def _claim_once(self, _http_session, _latest):
            nonlocal claim_won
            async with claim_lock:
                if claim_won:
                    return None
                claim_won = True
                return {
                    "deliveryId": "ghcd_voice_claim_once",
                    "claimId": "claim_voice_claim_once",
                    "callbackId": "cb_voice_claim_once",
                    "text": "One terminal utterance.",
                }

        async def _fake_authorize(self, _http_session, delivery):
            return _dispatch_permit(
                delivery_id=str(delivery["deliveryId"]),
                claim_id=str(delivery["claimId"]),
            )

        async def _fake_mark(
            self,
            _http_session,
            _delivery,
            status,
            *,
            dispatch_permit=None,
            error="",
            reason="",
        ):
            _ = dispatch_permit, error, reason
            marked.append(status)
            return True

        for scheduler in schedulers:
            scheduler._fetch_glasshive = MethodType(_fake_fetch, scheduler)
            scheduler._claim_glasshive_delivery = MethodType(_claim_once, scheduler)
            scheduler._authorize_glasshive_delivery = MethodType(
                _fake_authorize, scheduler
            )
            scheduler._renew_glasshive_delivery_permit = MethodType(
                _renew_dispatch_permit_for_test, scheduler
            )
            scheduler._mark_glasshive_delivery_status = MethodType(
                _fake_mark, scheduler
            )

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            for index, scheduler in enumerate(schedulers):
                scheduler.schedule(
                    f"msg_voice_claim_once_{index}",
                    [],
                    "",
                    glasshive_expected=True,
                )
            while not any(session.speech_handles for session in sessions):
                await asyncio.sleep(0)
            for session in sessions:
                for handle in session.speech_handles:
                    handle.complete()
            await asyncio.gather(*(scheduler._task for scheduler in schedulers))

        utterances = [
            call["text"] for session in sessions for call in session.say_calls
        ]
        self.assertEqual(utterances, ["One terminal utterance."])
        self.assertEqual(marked, ["sent"])

    async def test_claim_conflict_non_200_and_exception_return_no_delivery(
        self,
    ) -> None:
        scheduler = self._build_scheduler(session=_DummySession())
        latest = {"callbackId": "cb_voice_claim_failure"}

        for label, http in (
            ("conflict", _RecordingPostSession([(409, {})])),
            ("non_200", _RecordingPostSession([(503, {})])),
        ):
            with self.subTest(label=label):
                claimed = await scheduler._claim_glasshive_delivery(http, latest)
                self.assertIsNone(claimed)

        class _RaisingPostSession:
            def post(self, *_args, **_kwargs):
                raise RuntimeError("synthetic claim failure")

        claimed = await scheduler._claim_glasshive_delivery(
            _RaisingPostSession(), latest
        )
        self.assertIsNone(claimed)

    async def test_claim_rejects_substituted_callback_or_call_and_requires_owner_scope(
        self,
    ) -> None:
        scheduler = self._build_scheduler(session=_DummySession())
        raw_callback = "cb_terminal_" + "a" * 64
        canonical_callback = "callback_sha256:" + hashlib.sha256(raw_callback.encode()).hexdigest()
        latest = {"callbackId": raw_callback, "userId": "owner_expected"}
        valid = {
            "deliveryId": "delivery_expected",
            "claimId": "claim_expected",
            "callbackId": canonical_callback,
            "terminalCallbackId": raw_callback,
            "voiceCallSessionId": "call_123",
            "userId": "owner_expected",
        }

        for label, changes in (
            ("substituted_callback", {"callbackId": "callback_sha256:" + "b" * 64}),
            ("uncanonical_response", {"callbackId": raw_callback}),
            ("different_call", {"voiceCallSessionId": "call_other"}),
            ("different_owner", {"userId": "owner_other"}),
            ("missing_owner", {"userId": ""}),
            ("missing_claim", {"claimId": ""}),
            ("missing_delivery", {"deliveryId": ""}),
        ):
            with self.subTest(label=label):
                claimed = await scheduler._claim_glasshive_delivery(
                    _RecordingPostSession(
                        [(200, {"deliveries": [{**valid, **changes}]})]
                    ),
                    latest,
                )
                self.assertIsNone(claimed)

        for requested_callback in (raw_callback, canonical_callback):
            with self.subTest(requested_form=requested_callback[:16]):
                http = _RecordingPostSession([(200, {"deliveries": [valid]})])
                claimed = await scheduler._claim_glasshive_delivery(
                    http, {**latest, "callbackId": requested_callback}
                )
                self.assertEqual(claimed, valid)
                self.assertEqual(http.posts[0]["json"]["callbackId"], requested_callback)
                self.assertEqual(claimed["terminalCallbackId"], raw_callback)

    async def test_followup_http_errors_never_read_or_log_private_response_bodies(
        self,
    ) -> None:
        scheduler = self._build_scheduler(session=_DummySession())
        sensitive = "SYNTHETIC_PRIVATE_FOLLOWUP_PROVIDER_CREDENTIAL"

        class _PrivateErrorResponse(_FakeResponse):
            def __init__(self):
                super().__init__(503, {})
                self.body_reads = 0

            async def text(self):
                self.body_reads += 1
                return sensitive

        class _PrivateErrorSession:
            def __init__(self):
                self.response = _PrivateErrorResponse()

            def get(self, *_args, **_kwargs):
                return self.response

        for name in ("_fetch_cortex", "_fetch_glasshive"):
            with self.subTest(poller=name):
                http = _PrivateErrorSession()
                with mock.patch.object(worker.logger, "warning") as warning:
                    result = await getattr(scheduler, name)(http, "message_synthetic")

                self.assertIsNone(result)
                self.assertEqual(http.response.body_reads, 0)
                self.assertNotIn(sensitive, str(warning.call_args_list))

    async def test_completed_speech_settles_after_presentation_authority_changes(
        self,
    ) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        delivery = {
            "deliveryId": "ghcd_voice_completed_before_mode_change",
            "claimId": "claim_voice_completed_before_mode_change",
        }
        permit = _dispatch_permit(
            delivery_id=str(delivery["deliveryId"]),
            claim_id=str(delivery["claimId"]),
        )
        speech_handle = session.say(
            "Already spoken terminal result.",
            allow_interruptions=True,
            add_to_chat_ctx=False,
        )
        speech_handle.complete()
        marked: list[tuple[str, str]] = []
        released: list[str] = []

        async def _fake_mark(
            self,
            _http_session,
            _delivery,
            status,
            *,
            dispatch_permit=None,
            error="",
            reason="",
        ):
            _ = error, reason
            marked.append((status, str(dispatch_permit["permitId"])))
            return True

        async def _fake_release(self, _http_session, _delivery, _permit):
            released.append(str(_delivery["deliveryId"]))
            return True

        scheduler._mark_glasshive_delivery_status = MethodType(_fake_mark, scheduler)
        scheduler._release_glasshive_delivery_permit = MethodType(
            _fake_release, scheduler
        )
        scheduler._mode = "listen_only"

        settled = await scheduler._maintain_glasshive_speech_permit(
            _FakeClientSession(),
            delivery,
            permit,
            speech_handle,
            seq=scheduler._seq,
            allow_stale_delivery=False,
            presentation_is_current=lambda: False,
        )

        self.assertTrue(settled)
        self.assertEqual(marked, [("sent", str(permit["permitId"]))])
        self.assertEqual(released, [])

    async def test_cancellation_during_completed_speech_settlement_never_releases(
        self,
    ) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        delivery = {
            "deliveryId": "ghcd_voice_cancelled_settlement",
            "claimId": "claim_voice_cancelled_settlement",
        }
        permit = _dispatch_permit(
            delivery_id=str(delivery["deliveryId"]),
            claim_id=str(delivery["claimId"]),
        )
        speech_handle = session.say(
            "Spoken before settlement cancellation.",
            allow_interruptions=True,
            add_to_chat_ctx=False,
        )
        speech_handle.complete()
        first_mark_entered = asyncio.Event()
        marked: list[str] = []
        released: list[str] = []

        async def _fake_mark(
            self,
            _http_session,
            _delivery,
            status,
            *,
            dispatch_permit=None,
            error="",
            reason="",
        ):
            _ = dispatch_permit, error, reason
            marked.append(status)
            if len(marked) == 1:
                first_mark_entered.set()
                await asyncio.Event().wait()
            return True

        async def _fake_release(self, _http_session, _delivery, _permit):
            released.append(str(_delivery["deliveryId"]))
            return True

        scheduler._mark_glasshive_delivery_status = MethodType(_fake_mark, scheduler)
        scheduler._release_glasshive_delivery_permit = MethodType(
            _fake_release, scheduler
        )

        lifecycle = asyncio.create_task(
            scheduler._maintain_glasshive_speech_permit(
                _FakeClientSession(),
                delivery,
                permit,
                speech_handle,
                seq=scheduler._seq,
                allow_stale_delivery=False,
                presentation_is_current=lambda: True,
            )
        )
        await asyncio.wait_for(first_mark_entered.wait(), timeout=1.0)
        lifecycle.cancel()
        outcome = (await asyncio.gather(lifecycle, return_exceptions=True))[0]

        self.assertIsInstance(outcome, asyncio.CancelledError)
        self.assertEqual(marked, ["sent", "sent"])
        self.assertEqual(released, [])

    async def test_invalid_active_speech_permit_records_unknown_without_release(
        self,
    ) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        delivery = {
            "deliveryId": "ghcd_voice_invalid_active_permit",
            "claimId": "claim_voice_invalid_active_permit",
        }
        permit = _dispatch_permit(
            delivery_id=str(delivery["deliveryId"]),
            claim_id=str(delivery["claimId"]),
        )
        permit["expiresAt"] = "invalid-expiry"
        speech_handle = session.say(
            "Speech with invalid active permit.",
            allow_interruptions=True,
            add_to_chat_ctx=False,
        )
        marked: list[tuple[str, str]] = []
        released: list[str] = []

        async def _fake_mark(
            self,
            _http_session,
            _delivery,
            status,
            *,
            dispatch_permit=None,
            error="",
            reason="",
        ):
            _ = dispatch_permit, error
            marked.append((status, reason))
            return True

        async def _fake_release(self, _http_session, _delivery, _permit):
            released.append(str(_delivery["deliveryId"]))
            return True

        scheduler._mark_glasshive_delivery_status = MethodType(_fake_mark, scheduler)
        scheduler._release_glasshive_delivery_permit = MethodType(
            _fake_release, scheduler
        )

        settled = await scheduler._maintain_glasshive_speech_permit(
            _FakeClientSession(),
            delivery,
            permit,
            speech_handle,
            seq=scheduler._seq,
            allow_stale_delivery=False,
            presentation_is_current=lambda: True,
        )

        self.assertFalse(settled)
        self.assertEqual(speech_handle.interrupt_forces, [True])
        self.assertEqual(
            marked,
            [("delivery_unknown", "voice_speech_permit_invalid_after_transport")],
        )
        self.assertEqual(released, [])

    async def test_renewal_loss_after_handle_completion_settles_sent(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        delivery = {
            "deliveryId": "ghcd_voice_completed_during_renewal",
            "claimId": "claim_voice_completed_during_renewal",
        }
        permit = _dispatch_permit(
            delivery_id=str(delivery["deliveryId"]),
            claim_id=str(delivery["claimId"]),
            expires_in_s=0.02,
        )
        speech_handle = session.say(
            "Completes while renewal is pending.",
            allow_interruptions=True,
            add_to_chat_ctx=False,
        )
        marked: list[tuple[str, str]] = []

        async def _lose_after_completion(self, _http_session, _delivery, _permit):
            speech_handle.complete()
            return None

        async def _fake_mark(
            self,
            _http_session,
            _delivery,
            status,
            *,
            dispatch_permit=None,
            error="",
            reason="",
        ):
            _ = dispatch_permit, error
            marked.append((status, reason))
            return True

        scheduler._renew_glasshive_delivery_permit = MethodType(
            _lose_after_completion, scheduler
        )
        scheduler._mark_glasshive_delivery_status = MethodType(_fake_mark, scheduler)

        settled = await scheduler._maintain_glasshive_speech_permit(
            _FakeClientSession(),
            delivery,
            permit,
            speech_handle,
            seq=scheduler._seq,
            allow_stale_delivery=False,
            presentation_is_current=lambda: True,
        )

        self.assertTrue(settled)
        self.assertEqual(marked, [("sent", "")])

    async def test_completion_callback_registration_exception_records_unknown(
        self,
    ) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        delivery = {
            "deliveryId": "ghcd_voice_callback_registration_failure",
            "claimId": "claim_voice_callback_registration_failure",
        }
        permit = _dispatch_permit(
            delivery_id=str(delivery["deliveryId"]),
            claim_id=str(delivery["claimId"]),
        )
        speech_handle = session.say(
            "Speech whose completion callback cannot register.",
            allow_interruptions=True,
            add_to_chat_ctx=False,
        )
        marked: list[tuple[str, str]] = []

        def _raise_registration(_callback):
            raise RuntimeError("synthetic callback registration failure")

        async def _fake_mark(
            self,
            _http_session,
            _delivery,
            status,
            *,
            dispatch_permit=None,
            error="",
            reason="",
        ):
            _ = dispatch_permit, error
            marked.append((status, reason))
            return True

        speech_handle.add_done_callback = _raise_registration
        scheduler._mark_glasshive_delivery_status = MethodType(_fake_mark, scheduler)

        settled = await scheduler._maintain_glasshive_speech_permit(
            _FakeClientSession(),
            delivery,
            permit,
            speech_handle,
            seq=scheduler._seq,
            allow_stale_delivery=False,
            presentation_is_current=lambda: True,
        )

        self.assertFalse(settled)
        self.assertEqual(speech_handle.interrupt_forces, [True])
        self.assertEqual(
            marked,
            [("delivery_unknown", "voice_speech_outcome_unknown:RuntimeError")],
        )

    async def test_failed_sent_settlement_falls_back_to_unknown(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        delivery = {
            "deliveryId": "ghcd_voice_sent_settlement_failure",
            "claimId": "claim_voice_sent_settlement_failure",
        }
        permit = _dispatch_permit(
            delivery_id=str(delivery["deliveryId"]),
            claim_id=str(delivery["claimId"]),
        )
        speech_handle = session.say(
            "Completed speech with uncertain settlement.",
            allow_interruptions=True,
            add_to_chat_ctx=False,
        )
        speech_handle.complete()
        marked: list[tuple[str, str]] = []

        async def _fake_mark(
            self,
            _http_session,
            _delivery,
            status,
            *,
            dispatch_permit=None,
            error="",
            reason="",
        ):
            _ = dispatch_permit, error
            marked.append((status, reason))
            return status == "delivery_unknown"

        scheduler._mark_glasshive_delivery_status = MethodType(_fake_mark, scheduler)

        settled = await scheduler._maintain_glasshive_speech_permit(
            _FakeClientSession(),
            delivery,
            permit,
            speech_handle,
            seq=scheduler._seq,
            allow_stale_delivery=False,
            presentation_is_current=lambda: True,
        )

        self.assertFalse(settled)
        self.assertEqual(
            marked,
            [
                ("sent", ""),
                ("delivery_unknown", "voice_speech_settlement_unknown"),
            ],
        )

    async def test_cancellation_during_active_speech_records_unknown_without_release(
        self,
    ) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        delivery = {
            "deliveryId": "ghcd_voice_cancelled_active_speech",
            "claimId": "claim_voice_cancelled_active_speech",
        }
        permit = _dispatch_permit(
            delivery_id=str(delivery["deliveryId"]),
            claim_id=str(delivery["claimId"]),
        )
        speech_handle = session.say(
            "Interrupted active speech.",
            allow_interruptions=True,
            add_to_chat_ctx=False,
        )
        marked: list[tuple[str, str]] = []
        released: list[str] = []

        async def _fake_mark(
            self,
            _http_session,
            _delivery,
            status,
            *,
            dispatch_permit=None,
            error="",
            reason="",
        ):
            _ = dispatch_permit, error
            marked.append((status, reason))
            return True

        async def _fake_release(self, _http_session, _delivery, _permit):
            released.append(str(_delivery["deliveryId"]))
            return True

        scheduler._mark_glasshive_delivery_status = MethodType(_fake_mark, scheduler)
        scheduler._release_glasshive_delivery_permit = MethodType(
            _fake_release, scheduler
        )
        lifecycle = asyncio.create_task(
            scheduler._maintain_glasshive_speech_permit(
                _FakeClientSession(),
                delivery,
                permit,
                speech_handle,
                seq=scheduler._seq,
                allow_stale_delivery=False,
                presentation_is_current=lambda: True,
            )
        )
        await asyncio.sleep(0)
        lifecycle.cancel()
        outcome = (await asyncio.gather(lifecycle, return_exceptions=True))[0]

        self.assertIsInstance(outcome, asyncio.CancelledError)
        self.assertEqual(speech_handle.interrupt_forces, [True])
        self.assertEqual(
            marked,
            [("delivery_unknown", "voice_speech_cancelled_after_transport")],
        )
        self.assertEqual(released, [])

    async def test_unexpected_lifecycle_exception_records_unknown(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        delivery = {
            "deliveryId": "ghcd_voice_lifecycle_exception",
            "claimId": "claim_voice_lifecycle_exception",
        }
        permit = _dispatch_permit(
            delivery_id=str(delivery["deliveryId"]),
            claim_id=str(delivery["claimId"]),
            expires_in_s=0.02,
        )
        speech_handle = session.say(
            "Speech with lifecycle exception.",
            allow_interruptions=True,
            add_to_chat_ctx=False,
        )
        marked: list[tuple[str, str]] = []

        async def _raise_renewal(self, _http_session, _delivery, _permit):
            raise RuntimeError("synthetic renewal exception")

        async def _fake_mark(
            self,
            _http_session,
            _delivery,
            status,
            *,
            dispatch_permit=None,
            error="",
            reason="",
        ):
            _ = dispatch_permit, error
            marked.append((status, reason))
            return True

        scheduler._renew_glasshive_delivery_permit = MethodType(
            _raise_renewal, scheduler
        )
        scheduler._mark_glasshive_delivery_status = MethodType(_fake_mark, scheduler)

        settled = await scheduler._maintain_glasshive_speech_permit(
            _FakeClientSession(),
            delivery,
            permit,
            speech_handle,
            seq=scheduler._seq,
            allow_stale_delivery=False,
            presentation_is_current=lambda: True,
        )

        self.assertFalse(settled)
        self.assertEqual(speech_handle.interrupt_forces, [True])
        self.assertEqual(
            marked,
            [("delivery_unknown", "voice_speech_outcome_unknown:RuntimeError")],
        )

    async def test_active_glasshive_speech_renews_permit_and_settles_with_latest_generation(
        self,
    ) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        renewals: list[int] = []
        marked: list[tuple[str, int]] = []

        async def _fake_fetch(self, _http_session, _message_id):
            return {
                "latest": {
                    "event": "run.completed",
                    "text": "A long terminal result.",
                    "callbackId": "cb_voice_renew",
                }
            }

        async def _fake_claim(self, _http_session, _latest):
            return {
                "deliveryId": "ghcd_voice_renew",
                "claimId": "claim_voice_renew",
                "text": "A long terminal result.",
            }

        async def _fake_authorize(self, _http_session, delivery):
            return _dispatch_permit(
                delivery_id=str(delivery["deliveryId"]),
                claim_id=str(delivery["claimId"]),
                expires_in_s=0.03,
            )

        async def _fake_renew(self, _http_session, delivery, permit):
            renewals.append(int(permit["permitGeneration"]))
            renewed = _dispatch_permit(
                delivery_id=str(delivery["deliveryId"]),
                claim_id=str(delivery["claimId"]),
                generation=1,
                expires_in_s=0.03 if len(renewals) == 1 else 60,
            )
            if len(renewals) > 1:
                session.speech_handles[0].complete()
            return renewed

        async def _fake_mark(
            self,
            _http_session,
            _delivery,
            status,
            *,
            dispatch_permit=None,
            error="",
            reason="",
        ):
            _ = error, reason
            marked.append((status, int(dispatch_permit["permitGeneration"])))
            return True

        scheduler._fetch_glasshive = MethodType(_fake_fetch, scheduler)
        scheduler._claim_glasshive_delivery = MethodType(_fake_claim, scheduler)
        scheduler._authorize_glasshive_delivery = MethodType(_fake_authorize, scheduler)
        scheduler._renew_glasshive_delivery_permit = MethodType(_fake_renew, scheduler)
        scheduler._mark_glasshive_delivery_status = MethodType(_fake_mark, scheduler)

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule("msg_voice_renew", [], "", glasshive_expected=True)
            await asyncio.wait_for(scheduler._task, timeout=1.0)

        self.assertEqual(len(session.say_calls), 1)
        self.assertEqual(renewals, [1, 1])
        self.assertEqual(marked, [("sent", 1)])

    async def test_denied_active_speech_renewal_cancels_and_records_unknown_without_retry(
        self,
    ) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        released: list[int] = []
        marked: list[str] = []
        renewal_calls = 0

        async def _fake_fetch(self, _http_session, _message_id):
            return {
                "latest": {
                    "event": "run.completed",
                    "text": "This speech loses its permit.",
                    "callbackId": "cb_voice_renew_denied",
                }
            }

        async def _fake_claim(self, _http_session, _latest):
            return {
                "deliveryId": "ghcd_voice_renew_denied",
                "claimId": "claim_voice_renew_denied",
                "text": "This speech loses its permit.",
            }

        async def _fake_authorize(self, _http_session, delivery):
            return _dispatch_permit(
                delivery_id=str(delivery["deliveryId"]),
                claim_id=str(delivery["claimId"]),
                expires_in_s=0.03,
            )

        async def _fake_renew(self, _http_session, delivery, _permit):
            nonlocal renewal_calls
            renewal_calls += 1
            if renewal_calls == 1:
                return _dispatch_permit(
                    delivery_id=str(delivery["deliveryId"]),
                    claim_id=str(delivery["claimId"]),
                    expires_in_s=0.03,
                )
            return None

        async def _fake_release(self, _http_session, _delivery, permit):
            released.append(int(permit["permitGeneration"]))
            return True

        async def _fake_mark(
            self,
            _http_session,
            _delivery,
            status,
            *,
            dispatch_permit=None,
            error="",
            reason="",
        ):
            _ = dispatch_permit, error, reason
            marked.append(status)
            return True

        scheduler._fetch_glasshive = MethodType(_fake_fetch, scheduler)
        scheduler._claim_glasshive_delivery = MethodType(_fake_claim, scheduler)
        scheduler._authorize_glasshive_delivery = MethodType(_fake_authorize, scheduler)
        scheduler._renew_glasshive_delivery_permit = MethodType(_fake_renew, scheduler)
        scheduler._release_glasshive_delivery_permit = MethodType(_fake_release, scheduler)
        scheduler._mark_glasshive_delivery_status = MethodType(_fake_mark, scheduler)

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule("msg_voice_renew_denied", [], "", glasshive_expected=True)
            await asyncio.wait_for(scheduler._task, timeout=1.0)

        self.assertEqual(len(session.say_calls), 1)
        self.assertEqual(session.speech_handles[0].interrupt_forces, [True])
        self.assertEqual(released, [])
        self.assertEqual(marked, ["delivery_unknown"])

    async def test_unavailable_active_speech_renewal_cancels_before_permit_expiry(
        self,
    ) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        permit_expiry: datetime | None = None
        renewal_cancelled = False
        renewal_calls = 0
        released_at: datetime | None = None
        unknown_at: datetime | None = None

        async def _fake_fetch(self, _http_session, _message_id):
            return {
                "latest": {
                    "event": "run.completed",
                    "text": "This speech cannot renew its permit.",
                    "callbackId": "cb_voice_renew_unavailable",
                }
            }

        async def _fake_claim(self, _http_session, _latest):
            return {
                "deliveryId": "ghcd_voice_renew_unavailable",
                "claimId": "claim_voice_renew_unavailable",
                "text": "This speech cannot renew its permit.",
            }

        async def _fake_authorize(self, _http_session, delivery):
            nonlocal permit_expiry
            permit = _dispatch_permit(
                delivery_id=str(delivery["deliveryId"]),
                claim_id=str(delivery["claimId"]),
                expires_in_s=0.5,
            )
            permit_expiry = datetime.fromisoformat(str(permit["expiresAt"]))
            return permit

        async def _fake_renew(self, _http_session, delivery, _permit):
            nonlocal renewal_cancelled, renewal_calls
            renewal_calls += 1
            if renewal_calls == 1:
                return _dispatch_permit(
                    delivery_id=str(delivery["deliveryId"]),
                    claim_id=str(delivery["claimId"]),
                    expires_in_s=0.5,
                )
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                renewal_cancelled = True
                raise

        async def _fake_release(self, _http_session, _delivery, _permit):
            nonlocal released_at
            released_at = datetime.now(timezone.utc)
            return True

        async def _fake_mark(
            self,
            _http_session,
            _delivery,
            status,
            *,
            dispatch_permit=None,
            error="",
            reason="",
        ):
            nonlocal unknown_at
            _ = dispatch_permit, error, reason
            assert status == "delivery_unknown"
            unknown_at = datetime.now(timezone.utc)
            return True

        scheduler._fetch_glasshive = MethodType(_fake_fetch, scheduler)
        scheduler._claim_glasshive_delivery = MethodType(_fake_claim, scheduler)
        scheduler._authorize_glasshive_delivery = MethodType(_fake_authorize, scheduler)
        scheduler._renew_glasshive_delivery_permit = MethodType(_fake_renew, scheduler)
        scheduler._release_glasshive_delivery_permit = MethodType(_fake_release, scheduler)
        scheduler._mark_glasshive_delivery_status = MethodType(_fake_mark, scheduler)

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule("msg_voice_renew_unavailable", [], "", glasshive_expected=True)
            await asyncio.wait_for(scheduler._task, timeout=1.0)

        self.assertTrue(renewal_cancelled)
        self.assertEqual(session.speech_handles[0].interrupt_forces, [True])
        self.assertIsNotNone(permit_expiry)
        self.assertIsNone(released_at)
        self.assertIsNotNone(unknown_at)
        self.assertLess(unknown_at, permit_expiry)

    async def test_dispatch_permit_http_contract_is_exact_and_lease_bound(self) -> None:
        scheduler = self._build_scheduler(session=_DummySession())
        delivery = {"deliveryId": "ghcd_voice_http", "claimId": "claim_voice_http"}
        initial = _dispatch_permit(
            delivery_id="ghcd_voice_http",
            claim_id="claim_voice_http",
            expires_in_s=60,
        )
        renewed = _dispatch_permit(
            delivery_id="ghcd_voice_http",
            claim_id="claim_voice_http",
            generation=1,
            expires_in_s=120,
        )
        http = _RecordingPostSession(
            [
                (200, {"permit": initial}),
                (200, {"permit": renewed}),
                (200, {"released": True}),
                (200, {"delivery": {"status": "sent"}}),
            ]
        )

        authorized = await scheduler._authorize_glasshive_delivery(http, delivery)
        refreshed = await scheduler._renew_glasshive_delivery_permit(
            http, delivery, authorized
        )
        released = await scheduler._release_glasshive_delivery_permit(
            http, delivery, refreshed
        )
        settled = await scheduler._mark_glasshive_delivery_status(
            http,
            delivery,
            "sent",
            dispatch_permit=refreshed,
        )

        base = "http://example.test/api/viventium/voice/glasshive/deliveries/ghcd_voice_http"
        self.assertEqual(
            [post["url"] for post in http.posts],
            [f"{base}/authorize", f"{base}/renew", f"{base}/release", f"{base}/status"],
        )
        self.assertEqual(
            http.posts[0]["json"],
            {"claimId": "claim_voice_http", "leaseMs": 60_000},
        )
        self.assertEqual(
            http.posts[1]["json"],
            {
                "claimId": "claim_voice_http",
                "dispatchPermit": initial,
                "leaseMs": 60_000,
            },
        )
        self.assertEqual(
            http.posts[2]["json"],
            {"claimId": "claim_voice_http", "dispatchPermit": renewed},
        )
        self.assertEqual(
            http.posts[3]["json"],
            {
                "claimId": "claim_voice_http",
                "status": "sent",
                "dispatchPermit": renewed,
            },
        )
        self.assertEqual(authorized, initial)
        self.assertEqual(refreshed, renewed)
        self.assertTrue(released)
        self.assertTrue(settled)

    async def test_coalesced_worker_completion_calls_exact_settlement_only_after_audio(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        text = "Both Workers completed."
        delivery = {
            "deliveryId": "ghcd_voice_coalesced",
            "claimId": "claim_voice_coalesced",
            "callbackMessageId": "message-coalesced",
            "voiceCallSessionId": "call_123",
            "voiceRequestId": "voice_worker_completion_turn_" + "c" * 64,
            "text": text,
            "workerCompletionPresentation": _worker_completion_presentation(text),
        }
        permit = _dispatch_permit(
            delivery_id=str(delivery["deliveryId"]),
            claim_id=str(delivery["claimId"]),
        )
        completed: list[str] = []
        marked: list[str] = []

        async def _complete(_scheduler, _http_session, observed, _permit):
            self.assertEqual(observed, delivery)
            self.assertTrue(session.speech_handles[0].done())
            completed.append(str(observed["deliveryId"]))
            return True

        async def _mark(_scheduler, _http_session, _delivery, status, **_kwargs):
            marked.append(status)
            return True

        scheduler._complete_glasshive_worker_presentation = MethodType(_complete, scheduler)
        scheduler._mark_glasshive_delivery_status = MethodType(_mark, scheduler)
        speech_handle = session.say(
            text,
            allow_interruptions=True,
            add_to_chat_ctx=True,
        )
        speech_handle.complete()

        settled = await scheduler._maintain_glasshive_speech_permit(
            object(),
            delivery,
            permit,
            speech_handle,
            seq=scheduler._seq,
            allow_stale_delivery=True,
            presentation_is_current=lambda: True,
        )

        self.assertTrue(settled)
        self.assertEqual(completed, ["ghcd_voice_coalesced"])
        self.assertEqual(marked, [])

    async def test_substituted_coalesced_response_digest_blocks_speech(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        authorized = False
        marked: list[str] = []

        async def _fetch(self, _http_session, _message_id):
            return {
                "latest": {
                    "event": "run.completed",
                    "text": "Original response.",
                    "callbackId": "cb_voice_digest",
                }
            }

        async def _claim(self, _http_session, _latest):
            return {
                "deliveryId": "ghcd_voice_digest",
                "claimId": "claim_voice_digest",
                "callbackId": "cb_voice_digest",
                "callbackMessageId": "message-coalesced",
                "voiceCallSessionId": "call_123",
                "voiceRequestId": "voice_worker_completion_turn_" + "c" * 64,
                "text": "Substituted response.",
                "workerCompletionPresentation": _worker_completion_presentation(
                    "Original response."
                ),
            }

        async def _authorize(self, _http_session, _delivery):
            nonlocal authorized
            authorized = True
            return None

        async def _mark(self, _http_session, _delivery, status, **_kwargs):
            marked.append(status)
            return True

        scheduler._fetch_glasshive = MethodType(_fetch, scheduler)
        scheduler._claim_glasshive_delivery = MethodType(_claim, scheduler)
        scheduler._authorize_glasshive_delivery = MethodType(_authorize, scheduler)
        scheduler._mark_glasshive_delivery_status = MethodType(_mark, scheduler)

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule("msg_voice_digest", [], "", glasshive_expected=True)
            await asyncio.wait_for(scheduler._task, timeout=1.0)

        self.assertFalse(authorized)
        self.assertEqual(session.say_calls, [])
        self.assertEqual(marked, ["failed"])

    async def test_worker_completion_http_contract_is_exact(self) -> None:
        scheduler = self._build_scheduler(session=_DummySession())
        text = "Both Workers completed."
        delivery = {
            "deliveryId": "ghcd_voice_complete",
            "claimId": "claim_voice_complete",
            "callbackMessageId": "message-coalesced",
            "voiceCallSessionId": "call_123",
            "voiceRequestId": "voice_worker_completion_turn_" + "c" * 64,
            "text": text,
            "workerCompletionPresentation": _worker_completion_presentation(text),
        }
        permit = _dispatch_permit(
            delivery_id=str(delivery["deliveryId"]),
            claim_id=str(delivery["claimId"]),
        )
        http = _RecordingPostSession(
            [
                (
                    200,
                    {
                        "delivery": {
                            "deliveryId": delivery["deliveryId"],
                            "status": "sent",
                            "voiceCallSessionId": "call_123",
                            "workerCompletionPresentation": delivery[
                                "workerCompletionPresentation"
                            ],
                        }
                    },
                )
            ]
        )

        settled = await scheduler._complete_glasshive_worker_presentation(
            http, delivery, permit
        )

        self.assertTrue(settled)
        self.assertEqual(len(http.posts), 1)
        self.assertTrue(http.posts[0]["url"].endswith("/presentation-complete"))
        self.assertEqual(
            http.posts[0]["json"],
            {
                "claimId": "claim_voice_complete",
                "dispatchPermit": permit,
                "presentationRef": "voice_worker_completion_" + "c" * 64,
            },
        )

    async def test_authorize_rejects_unknown_or_mismatched_permit_fields(self) -> None:
        scheduler = self._build_scheduler(session=_DummySession())
        delivery = {"deliveryId": "ghcd_voice_http", "claimId": "claim_voice_http"}
        malformed = _dispatch_permit(
            delivery_id="another_delivery",
            claim_id="claim_voice_http",
        )
        malformed["privatePath"] = "/private/result"
        http = _RecordingPostSession([(200, {"permit": malformed})])

        authorized = await scheduler._authorize_glasshive_delivery(http, delivery)

        self.assertIsNone(authorized)

    async def test_caps_long_glasshive_delivery_before_voice_tts(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)

        async def _fake_fetch_cortex(self, _http_session, _message_id):
            return {"insights": [], "followUp": None}

        async def _fake_fetch_glasshive(self, _http_session, _message_id):
            return {
                "latest": {
                    "event": "run.completed",
                    "text": "Short preview.",
                    "callbackId": "cb_voice_long",
                }
            }

        async def _fake_claim(self, _http_session, latest):
            assert latest["callbackId"] == "cb_voice_long"
            return {
                "deliveryId": "ghcd_voice_long",
                "claimId": "claim_voice_long",
                "text": "Short preview.",
                "fullText": "A" * 5000,
            }

        async def _fake_authorize(self, _http_session, delivery):
            return _dispatch_permit(
                delivery_id=str(delivery["deliveryId"]),
                claim_id=str(delivery["claimId"]),
            )

        async def _fake_mark(
            self,
            _http_session,
            delivery,
            status,
            *,
            dispatch_permit=None,
            error="",
            reason="",
        ):
            _ = delivery, status, dispatch_permit, error, reason
            return True

        scheduler._fetch_cortex = MethodType(_fake_fetch_cortex, scheduler)
        scheduler._fetch_glasshive = MethodType(_fake_fetch_glasshive, scheduler)
        scheduler._claim_glasshive_delivery = MethodType(_fake_claim, scheduler)
        scheduler._authorize_glasshive_delivery = MethodType(_fake_authorize, scheduler)
        scheduler._renew_glasshive_delivery_permit = MethodType(
            _renew_dispatch_permit_for_test, scheduler
        )
        scheduler._mark_glasshive_delivery_status = MethodType(_fake_mark, scheduler)

        with mock.patch.dict(os.environ, {"VIVENTIUM_VOICE_FOLLOWUP_TTS_MAX_CHARS": "800"}):
            with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
                scheduler.schedule("msg_123", [], "", glasshive_expected=True)
                while not session.speech_handles:
                    await asyncio.sleep(0)
                session.speech_handles[0].complete()
                await scheduler._task

        rendered = []

        async def selected_node(agent, source, settings):
            async for value in source:
                rendered.append(value)
            yield object()

        with mock.patch.object(worker.Agent.default, "tts_node", selected_node):
            async for _ in session.say_calls[0]["audio"]:
                pass
        self.assertEqual(session.say_calls[0]["text"], "A" * 5000)
        spoken = "".join(rendered)
        self.assertLessEqual(len(spoken), 800)
        self.assertIn("full report in the chat", spoken)

    async def test_waits_for_terminal_glasshive_callback_result(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session, timeout_s=0.6, interval_s=0.25)

        async def _fake_fetch_cortex(self, _http_session, _message_id):
            return {"insights": [], "followUp": None}

        states = [
            {"latest": {"event": "run.started", "text": "I’m working on it now."}},
            {
                "latest": {
                    "event": "run.completed",
                    "text": "The browser task is done.",
                    "callbackId": "cb_voice_wait_terminal",
                }
            },
        ]

        async def _fake_fetch_glasshive(self, _http_session, _message_id):
            if states:
                return states.pop(0)
            return {"latest": None}

        scheduler._fetch_cortex = MethodType(_fake_fetch_cortex, scheduler)
        scheduler._fetch_glasshive = MethodType(_fake_fetch_glasshive, scheduler)
        _install_claimed_terminal_delivery(
            scheduler,
            callback_id="cb_voice_wait_terminal",
            text="The browser task is done.",
        )

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule("msg_123", [], "", glasshive_expected=True)
            await scheduler._task

        self.assertEqual(len(session.say_calls), 1)
        self.assertEqual(session.say_calls[0]["text"], "The browser task is done.")

    async def test_new_turn_does_not_cancel_pending_glasshive_result(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session, timeout_s=0.5, interval_s=0.01)

        async def _fake_fetch_cortex(self, _http_session, _message_id):
            return {"insights": [], "followUp": None}

        states = [
            {"latest": {"event": "run.started", "text": "Still working."}},
            {
                "latest": {
                    "event": "run.completed",
                    "text": "The worker result arrived.",
                    "callbackId": "cb_voice_new_turn",
                }
            },
        ]
        first_glasshive_poll = asyncio.Event()

        async def _fake_fetch_glasshive(self, _http_session, _message_id):
            first_glasshive_poll.set()
            if states:
                return states.pop(0)
            return {"latest": None}

        scheduler._fetch_cortex = MethodType(_fake_fetch_cortex, scheduler)
        scheduler._fetch_glasshive = MethodType(_fake_fetch_glasshive, scheduler)
        _install_claimed_terminal_delivery(
            scheduler,
            callback_id="cb_voice_new_turn",
            text="The worker result arrived.",
        )

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule("msg_glasshive", [], "", glasshive_expected=True)
            glasshive_task = scheduler._task
            await first_glasshive_poll.wait()
            scheduler.schedule("msg_new", [], "", cortex_expected=True)
            self.assertIsNotNone(glasshive_task)
            await glasshive_task

        self.assertEqual(len(session.say_calls), 1)
        self.assertEqual(session.say_calls[0]["text"], "The worker result arrived.")

    async def test_does_not_schedule_poll_for_ordinary_turn(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)

        scheduler.schedule("msg_123", [], "")

        self.assertIsNone(scheduler._task)
        self.assertEqual(session.say_calls, [])

    async def test_stable_supersession_stops_stale_followup_without_claiming_durable_result(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        fetch_calls = []

        async def _fake_fetch(self, _http_session, message_id):
            fetch_calls.append(message_id)
            return {
                "latest": {
                    "callbackId": "callback-1",
                    "text": "Late durable result must not speak as the stale response.",
                    "status": "completed",
                }
            }

        scheduler._fetch_glasshive = MethodType(_fake_fetch, scheduler)

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule(
                "msg_123",
                [],
                "",
                cortex_expected=False,
                glasshive_expected=True,
                presentation_is_current=lambda: False,
            )
            await scheduler._task

        self.assertEqual(fetch_calls, [])
        self.assertEqual(session.say_calls, [])


if __name__ == "__main__":
    unittest.main()
