import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import TelegramVivBot.utils.livekit_bridge as bridge_module  # noqa: E402
from TelegramVivBot.utils.livekit_bridge import LiveKitBridge  # noqa: E402


def test_livekit_api_url_conversion():
    bridge = LiveKitBridge()
    bridge.url = "ws://localhost:7880"
    assert bridge._livekit_api_url() == "http://localhost:7880"

    bridge.url = "wss://example.com"
    assert bridge._livekit_api_url() == "https://example.com"

    bridge.url = "http://localhost:7880"
    assert bridge._livekit_api_url() == "http://localhost:7880"

    bridge.url = "https://example.com"
    assert bridge._livekit_api_url() == "https://example.com"


def test_is_agent_participant_prefers_kind_with_fallback():
    from livekit import rtc

    bridge = LiveKitBridge()

    class DummyParticipant:
        def __init__(self, kind, identity: str):
            self.kind = kind
            self.identity = identity

    # Kind-based detection (preferred)
    p1 = DummyParticipant(rtc.ParticipantKind.PARTICIPANT_KIND_AGENT, "not-agent-prefix")
    assert bridge._is_agent_participant(p1) is True

    # Identity fallback heuristic
    p2 = DummyParticipant(rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD, "agent-xyz")
    assert bridge._is_agent_participant(p2) is True

    # Non-agent participant
    p3 = DummyParticipant(rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD, "telegram-user-123")
    assert bridge._is_agent_participant(p3) is False


def test_ensure_agent_dispatch_uses_http_url_and_creates_dispatch(monkeypatch):
    """
    Unit test: ensure we call LiveKitAPI with an HTTP base URL and create a dispatch once.
    """
    created = {"url": None, "created_reqs": []}

    class FakeAgentDispatchService:
        async def list_dispatch(self, room_name: str):
            return []

        async def create_dispatch(self, req):
            created["created_reqs"].append(req)
            return object()

    class FakeLiveKitAPI:
        def __init__(self, url: str, api_key: str, api_secret: str, **kwargs):
            created["url"] = url
            self._agent_dispatch = FakeAgentDispatchService()

        @property
        def agent_dispatch(self):
            return self._agent_dispatch

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(bridge_module.api, "LiveKitAPI", FakeLiveKitAPI)

    bridge = LiveKitBridge()
    bridge.url = "ws://localhost:7880"
    bridge.api_key = "devkey"
    bridge.api_secret = "secret"
    bridge.agent_name = "viventium"

    asyncio.run(bridge._ensure_agent_dispatch(room_name="room-123", chat_id=1))

    assert created["url"] == "http://localhost:7880"
    assert len(created["created_reqs"]) == 1
    assert getattr(created["created_reqs"][0], "agent_name") == "viventium"
    assert getattr(created["created_reqs"][0], "room") == "room-123"

    # Second call should be deduped for the same room
    asyncio.run(bridge._ensure_agent_dispatch(room_name="room-123", chat_id=1))
    assert len(created["created_reqs"]) == 1


def test_force_redispatch_deletes_existing_and_creates(monkeypatch):
    """
    Unit test: force=True should delete existing dispatches for the same agent+room, then create a new dispatch.
    """
    calls = {"deleted": [], "created": 0}

    class DummyDispatch:
        def __init__(self, dispatch_id: str, agent_name: str, room: str):
            self.id = dispatch_id
            self.agent_name = agent_name
            self.room = room

    class FakeAgentDispatchService:
        async def list_dispatch(self, room_name: str):
            return [
                DummyDispatch("AD_1", "viventium", room_name),
                DummyDispatch("AD_2", "other-agent", room_name),
            ]

        async def delete_dispatch(self, dispatch_id: str, room_name: str):
            calls["deleted"].append((dispatch_id, room_name))
            return object()

        async def create_dispatch(self, req):
            calls["created"] += 1
            return object()

    class FakeLiveKitAPI:
        def __init__(self, url: str, api_key: str, api_secret: str, **kwargs):
            self._agent_dispatch = FakeAgentDispatchService()

        @property
        def agent_dispatch(self):
            return self._agent_dispatch

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(bridge_module.api, "LiveKitAPI", FakeLiveKitAPI)

    bridge = LiveKitBridge()
    bridge.url = "ws://localhost:7880"
    bridge.api_key = "devkey"
    bridge.api_secret = "secret"
    bridge.agent_name = "viventium"

    asyncio.run(bridge._ensure_agent_dispatch(room_name="room-123", chat_id=1, force=True))

    # Only the matching agent dispatch should be deleted
    assert calls["deleted"] == [("AD_1", "room-123")]
    assert calls["created"] == 1

