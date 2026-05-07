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

    def say(self, text: str, *, allow_interruptions: bool, add_to_chat_ctx: bool) -> None:
        self.say_calls.append(
            {
                "text": text,
                "allow_interruptions": allow_interruptions,
                "add_to_chat_ctx": add_to_chat_ctx,
            }
        )


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


if __name__ == "__main__":
    unittest.main()
