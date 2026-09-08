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
