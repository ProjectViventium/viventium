import asyncio
import os
import sys
import unittest
from types import MethodType
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import worker
from librechat_llm import LibreChatAuth
from worker import CortexFollowupScheduler


class _DummySession:
    def __init__(self) -> None:
        self.say_calls: list[dict[str, object]] = []

    def say(self, text: str, *, allow_interruptions: bool, add_to_chat_ctx: bool):
        self.say_calls.append(
            {
                "text": text,
                "allow_interruptions": allow_interruptions,
                "add_to_chat_ctx": add_to_chat_ctx,
            }
        )
        return _DummySpeechHandle()


class _DummySpeechHandle:
    def __init__(self) -> None:
        self._done = False
        self.interrupt_forces = []
        self._callbacks = []

    def done(self) -> bool:
        return self._done

    def interrupt(self, *, force=False):
        self.interrupt_forces.append(force)
        self._done = True
        for callback in self._callbacks:
            callback(self)

    def add_done_callback(self, callback):
        self._callbacks.append(callback)


class _FakeClientSession:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class TestCortexFollowupScheduler(unittest.IsolatedAsyncioTestCase):
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

    async def test_speaks_glasshive_callback_result(self) -> None:
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

        self.assertEqual(len(session.say_calls), 1)
        self.assertEqual(session.say_calls[0]["text"], "The worker finished the invoice check.")

    async def test_claims_glasshive_delivery_before_speaking_full_text(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session)
        marked: list[tuple[str, str]] = []

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

        async def _fake_mark(self, _http_session, delivery, status, *, error="", reason=""):
            _ = error, reason
            marked.append((delivery["deliveryId"], status))

        scheduler._fetch_cortex = MethodType(_fake_fetch_cortex, scheduler)
        scheduler._fetch_glasshive = MethodType(_fake_fetch_glasshive, scheduler)
        scheduler._claim_glasshive_delivery = MethodType(_fake_claim, scheduler)
        scheduler._mark_glasshive_delivery_status = MethodType(_fake_mark, scheduler)

        with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
            scheduler.schedule("msg_123", [], "", glasshive_expected=True)
            await scheduler._task

        self.assertEqual(session.say_calls[0]["text"], "Full voice callback result.")
        self.assertEqual(marked, [("ghcd_voice", "sent")])

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

        async def _fake_mark(self, _http_session, delivery, status, *, error="", reason=""):
            _ = delivery, status, error, reason

        scheduler._fetch_cortex = MethodType(_fake_fetch_cortex, scheduler)
        scheduler._fetch_glasshive = MethodType(_fake_fetch_glasshive, scheduler)
        scheduler._claim_glasshive_delivery = MethodType(_fake_claim, scheduler)
        scheduler._mark_glasshive_delivery_status = MethodType(_fake_mark, scheduler)

        with mock.patch.dict(os.environ, {"VIVENTIUM_VOICE_FOLLOWUP_TTS_MAX_CHARS": "800"}):
            with mock.patch.object(worker.aiohttp, "ClientSession", _FakeClientSession):
                scheduler.schedule("msg_123", [], "", glasshive_expected=True)
                await scheduler._task

        spoken = str(session.say_calls[0]["text"])
        self.assertLessEqual(len(spoken), 800)
        self.assertIn("full report in the chat", spoken)

    async def test_waits_for_terminal_glasshive_callback_result(self) -> None:
        session = _DummySession()
        scheduler = self._build_scheduler(session=session, timeout_s=0.6, interval_s=0.25)

        async def _fake_fetch_cortex(self, _http_session, _message_id):
            return {"insights": [], "followUp": None}

        states = [
            {"latest": {"event": "run.started", "text": "I’m working on it now."}},
            {"latest": {"event": "run.completed", "text": "The browser task is done."}},
        ]

        async def _fake_fetch_glasshive(self, _http_session, _message_id):
            if states:
                return states.pop(0)
            return {"latest": None}

        scheduler._fetch_cortex = MethodType(_fake_fetch_cortex, scheduler)
        scheduler._fetch_glasshive = MethodType(_fake_fetch_glasshive, scheduler)

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
            {"latest": {"event": "run.completed", "text": "The worker result arrived."}},
        ]
        first_glasshive_poll = asyncio.Event()

        async def _fake_fetch_glasshive(self, _http_session, _message_id):
            first_glasshive_poll.set()
            if states:
                return states.pop(0)
            return {"latest": None}

        scheduler._fetch_cortex = MethodType(_fake_fetch_cortex, scheduler)
        scheduler._fetch_glasshive = MethodType(_fake_fetch_glasshive, scheduler)

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
