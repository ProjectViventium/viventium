import asyncio
import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from livekit.agents.llm import ChatContext, ChatMessage
from worker import _handle_owner_text_input, _build_room_options
from librechat_llm import TYPED_INPUT_EXTRA_KEY, _extract_last_user_speaker_context, _voice_source_event_id
from speaker_segments import SPEAKER_CONTEXT_EXTRA_KEY


def event(text="Use the existing draft.", participant="owner", stream_id="stream-one"):
    return SimpleNamespace(text=text, participant=SimpleNamespace(identity=participant),
                           info=SimpleNamespace(stream_id=stream_id))


def dispatch(ev):
    session = SimpleNamespace(interrupt=AsyncMock(), generate_reply=MagicMock())
    asyncio.run(_handle_owner_text_input(session, ev, call_session_id="call-one",
                                        owner_participant_identity="owner"))
    return session


def test_typed_owner_message_preserves_real_stream_identity_and_no_speaker_segments():
    session = dispatch(event())
    session.interrupt.assert_awaited_once()
    message = session.generate_reply.call_args.kwargs["user_input"]
    context = ChatContext(items=[message])
    envelope = message.extra[TYPED_INPUT_EXTRA_KEY]
    assert envelope == {"version": 1, "kind": "participant_text", "callSessionId": "call-one",
                        "participantIdentity": "owner", "sourceEventId": _voice_source_event_id(context, "call-one"),
                        "textSha256": hashlib.sha256(b"Use the existing draft.").hexdigest()}
    assert SPEAKER_CONTEXT_EXTRA_KEY not in message.extra
    assert _extract_last_user_speaker_context(context)["typedInput"] == envelope
    repeat = dispatch(event())
    assert repeat.generate_reply.call_args.kwargs["user_input"].id == message.id


@pytest.mark.parametrize("ev", [event(participant="guest"), event(stream_id=None), event(text=" "),
                                    SimpleNamespace(text="hello", participant=None, info=None)])
def test_unbound_input_never_interrupts_or_dispatches(ev):
    session = dispatch(ev)
    session.interrupt.assert_not_awaited()
    session.generate_reply.assert_not_called()


def test_later_audio_does_not_inherit_typed_input_authority():
    session = dispatch(event())
    typed = session.generate_reply.call_args.kwargs["user_input"]
    audio = ChatMessage(role="user", content=["unverified audio"], extra={SPEAKER_CONTEXT_EXTRA_KEY: {
        "speakerSegments": [{"speaker": {"actorTrust": "unknown"}}], "speakerSegmentRevisions": []}})
    result = _extract_last_user_speaker_context(ChatContext(items=[typed, audio]))
    assert "typedInput" not in result
    assert result["speakerSegments"][0]["speaker"]["actorTrust"] == "unknown"


def test_room_options_installs_the_supported_callback():
    callback = AsyncMock()
    options = _build_room_options(sync_transcription=False, participant_identity="owner", text_input_cb=callback)
    assert options.text_input.text_input_cb is callback
    assert options.participant_identity == "owner"


# Feature: Preserve authenticated text readers across returning-participant ordering.
from livekit import rtc
from livekit.agents import utils as livekit_utils
from livekit.agents.types import TOPIC_CHAT
import worker as worker_module


class TextRoom(rtc.EventEmitter):
    register_text_stream_handler = rtc.Room.register_text_stream_handler
    unregister_text_stream_handler = rtc.Room.unregister_text_stream_handler

    def __init__(self):
        super().__init__()
        self._text_stream_handlers = {}
        self.remote_participants = {}
        self.connected = True

    def isconnected(self):
        return self.connected

    def join(self, identity="owner"):
        participant = SimpleNamespace(identity=identity, state=rtc.ParticipantState.PARTICIPANT_STATE_ACTIVE)
        self.remote_participants[identity] = participant
        self.emit("participant_active", participant)
        return participant


class TextSession(rtc.EventEmitter):
    def __init__(self):
        super().__init__()
        self.interrupt = AsyncMock()
        self.generate_reply = MagicMock()


class OwnerTextFixture:
    def __init__(self, *, present=True, ready=True, mode="call", call_id="call-one", owner_wait_s=45.0):
        self.room = TextRoom()
        self.participant = self.room.join() if present else None
        self.session = TextSession()
        self.ready = asyncio.Event()
        if ready:
            self.ready.set()
        self.mode = worker_module.AuthoritativeCallModeState()
        self.mode.apply(mode)
        self.authoritative = True
        self.wait_started = asyncio.Event()
        self.delivered = asyncio.Event()
        self.events = []

        async def wait_owner(*, identity):
            self.wait_started.set()
            return await livekit_utils.wait_for_participant(self.room, identity=identity)

        self.ctx = SimpleNamespace(room=self.room, wait_for_participant=AsyncMock(side_effect=wait_owner))

        async def callback(session, ev):
            self.events.append(ev)
            await _handle_owner_text_input(session, ev, call_session_id=call_id,
                                           owner_participant_identity="owner")
            self.delivered.set()

        self.callback = AsyncMock(side_effect=callback)
        self.stop, self.close = worker_module._register_owner_text_input(
            self.ctx, self.session, call_session_id=call_id, owner_participant_identity="owner", session_ready=self.ready,
            can_dispatch=lambda: self.ready.is_set() and self.room.isconnected(),
            text_input_cb=self.callback, owner_wait_s=owner_wait_s,
        )
        self.handler = self.room._text_stream_handlers[TOPIC_CHAT]

    def send(self, *, stream_id="stream-one", text="Use the existing draft.", sender="owner", read=None):
        reader = SimpleNamespace(info=SimpleNamespace(stream_id=stream_id),
                                 read_all=AsyncMock(side_effect=read) if read else AsyncMock(return_value=text))
        self.handler(reader, sender)
        return reader


async def flush_callbacks():
    # Event-loop turns only; no wall-clock sleep or product polling.
    for _ in range(3):
        await asyncio.sleep(0)


def test_native_delayed_owner_retains_original_reader_info_and_participant_once():
    async def check():
        f = OwnerTextFixture(present=False)
        try:
            reader = f.send()
            await asyncio.wait_for(f.wait_started.wait(), 1)
            reader.read_all.assert_not_awaited()
            f.room.join("guest")
            await flush_callbacks()
            f.callback.assert_not_awaited()
            native = f.room.join()
            await asyncio.wait_for(f.delivered.wait(), 1)
            reader.read_all.assert_awaited_once()
            f.callback.assert_awaited_once()
            assert f.events[0].info is reader.info
            assert f.events[0].participant is native
            f.ctx.wait_for_participant.assert_awaited_once_with(identity="owner")
            f.session.interrupt.assert_awaited_once()
            message = f.session.generate_reply.call_args.kwargs["user_input"]
            assert message.extra[TYPED_INPUT_EXTRA_KEY]["callSessionId"] == "call-one"
            assert SPEAKER_CONTEXT_EXTRA_KEY not in message.extra
        finally:
            await f.close()
    asyncio.run(check())


@pytest.mark.parametrize("mode", ["call", "wing", "listen_only"])
def test_present_owner_has_no_presence_wait_and_preserves_restricted_mode(mode):
    async def check():
        f = OwnerTextFixture(mode=mode)
        try:
            reader = f.send()
            await asyncio.wait_for(f.delivered.wait(), 1)
            f.ctx.wait_for_participant.assert_not_awaited()
            reader.read_all.assert_awaited_once()
            assert f.events[0].participant is f.participant
            f.session.generate_reply.assert_called_once()
        finally:
            await f.close()
    asyncio.run(check())


def test_reader_waits_for_existing_session_readiness_before_dispatch():
    async def check():
        f = OwnerTextFixture(ready=False)
        try:
            reader = f.send()
            await flush_callbacks()
            reader.read_all.assert_not_awaited()
            f.session.generate_reply.assert_not_called()
            f.ready.set()
            await asyncio.wait_for(f.delivered.wait(), 1)
            f.ctx.wait_for_participant.assert_not_awaited()
        finally:
            await f.close()
    asyncio.run(check())


@pytest.mark.parametrize("sender,stream_id", [("guest", "stream-one"), ("", "stream-one"),
                                                 ("owner", None), ("owner", ""), ("owner", "x" * 257)])
def test_unknown_nonowner_or_invalid_stream_never_waits_reads_or_dispatches(sender, stream_id):
    async def check():
        f = OwnerTextFixture(present=False)
        try:
            reader = f.send(sender=sender, stream_id=stream_id)
            await flush_callbacks()
            reader.read_all.assert_not_awaited()
            f.ctx.wait_for_participant.assert_not_awaited()
            f.callback.assert_not_awaited()
        finally:
            await f.close()
    asyncio.run(check())


@pytest.mark.parametrize("terminal", ["end", "session_close", "room_disconnect", "job_cleanup"])
def test_terminal_cancels_native_wait_and_unregisters_only_owned_handler(terminal):
    async def check():
        f = OwnerTextFixture(present=False)
        unrelated = MagicMock()
        f.room.register_text_stream_handler("synthetic.other", unrelated)
        reader = f.send()
        await asyncio.wait_for(f.wait_started.wait(), 1)
        if terminal == "end":
            f.authoritative = False
            f.stop()
        elif terminal == "session_close":
            f.session.emit("close", SimpleNamespace())
        elif terminal == "room_disconnect":
            f.room.connected = False
            f.room.emit("disconnected", None)
        else:
            await f.close()
        f.room.join()
        await f.close()
        await flush_callbacks()
        assert TOPIC_CHAT not in f.room._text_stream_handlers
        assert f.room._text_stream_handlers["synthetic.other"] is unrelated
        assert not f.room._events.get("participant_active")
        reader.read_all.assert_not_awaited()
        f.callback.assert_not_awaited()
        f.session.generate_reply.assert_not_called()
    asyncio.run(check())


def test_transient_task_sse_or_mode_uncertainty_does_not_drop_owner_reader():
    async def check():
        f = OwnerTextFixture(present=False)
        try:
            reader = f.send()
            await asyncio.wait_for(f.wait_started.wait(), 1)
            f.authoritative = False  # Existing task-SSE gap; not terminal call End.
            f.mode.suspend()
            native = f.room.join()
            await asyncio.wait_for(f.delivered.wait(), 1)
            reader.read_all.assert_awaited_once()
            f.callback.assert_awaited_once()
            assert f.events[0].participant is native
            # Existing downstream turn-authority refresh, not a new reader admission gate.
            refresh = AsyncMock(return_value={"version": 1, "callSessionId": "call-one",
                                              "mode": "call", "status": "listening"})
            agent = worker_module.ViventiumVoiceAgent(instructions="", authoritative_mode_state=f.mode,
                                                      refresh_turn_authority=refresh)
            typed = f.session.generate_reply.call_args.kwargs["user_input"]
            await agent.on_user_turn_completed(ChatContext(items=[typed]), typed)
            refresh.assert_awaited_once()
            assert f.mode.mode == "call"
        finally:
            await f.close()
    asyncio.run(check())


@pytest.mark.parametrize("change", ["replace_participant", "owner_disconnect", "end"])
def test_authority_is_rechecked_after_reader_await(change):
    async def check():
        f = OwnerTextFixture()
        read_started, release = asyncio.Event(), asyncio.Event()

        async def read():
            read_started.set()
            await release.wait()
            return "Use the existing draft."

        try:
            f.send(read=read)
            await asyncio.wait_for(read_started.wait(), 1)
            if change == "replace_participant":
                f.room.join()
            elif change == "owner_disconnect":
                old = f.room.remote_participants.pop("owner")
                f.room.emit("participant_disconnected", old)
            else:
                f.authoritative = False
                f.stop()
            release.set()
            await flush_callbacks()
            f.callback.assert_not_awaited()
            f.session.generate_reply.assert_not_called()
        finally:
            await f.close()
    asyncio.run(check())


def test_pending_duplicate_is_read_once_without_blocking_later_complete_reader():
    async def check():
        f = OwnerTextFixture()
        first_started, first_release = asyncio.Event(), asyncio.Event()

        async def first_read():
            first_started.set()
            await first_release.wait()
            return "First synthetic input."

        try:
            first = f.send(stream_id="stream-first", read=first_read)
            duplicate = f.send(stream_id="stream-first")
            second = f.send(stream_id="stream-second", text="Second synthetic input.")
            await asyncio.wait_for(first_started.wait(), 1)
            await asyncio.wait_for(f.delivered.wait(), 1)
            second.read_all.assert_awaited_once()
            duplicate.read_all.assert_not_awaited()
            assert [ev.info.stream_id for ev in f.events] == ["stream-second"]
            f.delivered.clear()
            first_release.set()
            await asyncio.wait_for(f.delivered.wait(), 1)
            assert [ev.info.stream_id for ev in f.events] == ["stream-second", "stream-first"]
            first.read_all.assert_awaited_once()
            second.read_all.assert_awaited_once()
            duplicate.read_all.assert_not_awaited()
            assert f.session.generate_reply.call_count == 2
        finally:
            await f.close()
    asyncio.run(check())


def test_stale_old_disconnect_does_not_cancel_current_native_participant():
    async def check():
        f = OwnerTextFixture()
        old = f.participant
        current = f.room.join()
        try:
            reader = f.send()
            f.room.emit("participant_disconnected", old)
            await asyncio.wait_for(f.delivered.wait(), 1)
            assert f.events[0].participant is current
            reader.read_all.assert_awaited_once()
        finally:
            await f.close()
    asyncio.run(check())


def test_new_call_retains_its_own_participant_and_source_identity():
    async def check():
        f = OwnerTextFixture(call_id="call-one")
        g = OwnerTextFixture(call_id="call-two")
        try:
            f.send()
            g.send()
            await asyncio.wait_for(f.delivered.wait(), 1)
            await asyncio.wait_for(g.delivered.wait(), 1)
            one = f.session.generate_reply.call_args.kwargs["user_input"].extra[TYPED_INPUT_EXTRA_KEY]
            two = g.session.generate_reply.call_args.kwargs["user_input"].extra[TYPED_INPUT_EXTRA_KEY]
            assert one["callSessionId"] == "call-one"
            assert two["callSessionId"] == "call-two"
            assert one["sourceEventId"] != two["sourceEventId"]
            assert f.events[0].participant is f.participant
            assert g.events[0].participant is g.participant
        finally:
            await f.close()
            await g.close()
    asyncio.run(check())


def test_missing_owner_uses_configured_bound_and_logs_only_error_class(caplog):
    async def check():
        f = OwnerTextFixture(present=False, owner_wait_s=0.001)
        try:
            reader = f.send(text="synthetic-private-prose")
            await asyncio.wait_for(f.wait_started.wait(), 1)
            await asyncio.sleep(0.01)  # Test-only expiry of the explicitly supplied owner bound.
            reader.read_all.assert_not_awaited()
            f.callback.assert_not_awaited()
            assert "errorClass=TimeoutError" in caplog.text
            assert "synthetic-private-prose" not in caplog.text
        finally:
            await f.close()
    asyncio.run(check())


def test_room_options_disables_sdk_text_consumer_only_when_native_handler_owns_it():
    callback = AsyncMock()
    owned = _build_room_options(sync_transcription=False, participant_identity="owner",
                                text_input_cb=callback, owns_text_stream=True)
    assert owned.text_input is False
    legacy = _build_room_options(sync_transcription=False, participant_identity="owner", text_input_cb=callback)
    assert legacy.text_input.text_input_cb is callback
    assert owned.participant_identity == legacy.participant_identity == "owner"
    assert owned.close_on_disconnect is False


@pytest.mark.parametrize("mode", ["wing", "listen_only"])
def test_typed_reader_retains_existing_restricted_mode_suppression_and_persistence(mode):
    async def check():
        f = OwnerTextFixture(mode=mode)
        persisted = AsyncMock()
        agent = worker_module.ViventiumVoiceAgent(instructions="", authoritative_mode_state=f.mode,
                                                  persist_suppressed_turn=persisted)
        try:
            f.send()
            await asyncio.wait_for(f.delivered.wait(), 1)
            typed = f.session.generate_reply.call_args.kwargs["user_input"]
            with pytest.raises(worker_module.StopResponse):
                await agent.on_user_turn_completed(ChatContext(items=[typed]), typed)
            persisted.assert_awaited_once()
            assert persisted.call_args.args[1] == mode
        finally:
            await f.close()
    asyncio.run(check())


def test_old_disconnect_with_empty_map_does_not_drop_returning_owner_reader():
    async def check():
        f = OwnerTextFixture(present=False)
        old = SimpleNamespace(identity="owner")
        try:
            reader = f.send()
            await asyncio.wait_for(f.wait_started.wait(), 1)
            f.room.emit("participant_disconnected", old)
            await flush_callbacks()
            reader.read_all.assert_not_awaited()
            f.callback.assert_not_awaited()
            current = f.room.join()
            await asyncio.wait_for(f.delivered.wait(), 1)
            reader.read_all.assert_awaited_once()
            assert f.events[0].participant is current
        finally:
            await f.close()
    asyncio.run(check())


def test_wait_and_callback_logs_bind_call_and_stream_hash_without_text(caplog):
    async def check():
        caplog.set_level("INFO", logger="voice-gateway")
        f = OwnerTextFixture(present=False)
        try:
            f.send(text="synthetic-private-prose")
            await asyncio.wait_for(f.wait_started.wait(), 1)
            f.room.join()
            await asyncio.wait_for(f.delivered.wait(), 1)
            stream_hash = hashlib.sha256(b"stream-one").hexdigest()[:16]
            assert "owner_wait_started callSessionId=call-one streamHash=" + stream_hash in caplog.text
            assert "reader_callback callSessionId=call-one streamHash=" + stream_hash in caplog.text
            assert "ownerWaitMs=" in caplog.text
            assert "synthetic-private-prose" not in caplog.text
            assert "stream-one" not in caplog.text
        finally:
            await f.close()
    asyncio.run(check())
