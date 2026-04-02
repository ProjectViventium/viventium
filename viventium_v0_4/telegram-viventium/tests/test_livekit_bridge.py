import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from TelegramVivBot.utils.livekit_bridge import LiveKitBridge  # noqa: E402


class DummySegment:
    def __init__(self, text: str, final: bool):
        self.text = text
        self.final = final


@pytest.mark.asyncio
async def test_transcription_only_sends_once_for_final_segment():
    bridge = LiveKitBridge()
    chat_id = 123
    queue = asyncio.Queue()
    bridge.queues[chat_id] = queue

    # partial update should not enqueue
    bridge._handle_transcription_segments(chat_id, [DummySegment("Morning.", final=False)])
    assert queue.empty()

    # final update delivers the full text
    bridge._handle_transcription_segments(chat_id, [DummySegment("Morning. Booked that call?", final=True)])
    assert await queue.get() == "Morning. Booked that call?"

    # duplicate final update should be ignored
    bridge._handle_transcription_segments(chat_id, [DummySegment("Morning. Booked that call?", final=True)])
    assert queue.empty()


@pytest.mark.asyncio
async def test_duplicate_final_allowed_after_new_prompt():
    bridge = LiveKitBridge()
    chat_id = 42
    queue = asyncio.Queue()
    bridge.queues[chat_id] = queue

    # First response arrives and is forwarded
    bridge._handle_transcription_segments(chat_id, [DummySegment("Same reply", final=True)])
    assert await queue.get() == "Same reply"

    # Identical duplicate during same turn should be filtered
    bridge._handle_transcription_segments(chat_id, [DummySegment("Same reply", final=True)])
    assert queue.empty()

    # Simulate sending a new prompt (reset dedupe state)
    bridge._reset_transcription_state(chat_id)

    # Now an identical transcript should go through again
    bridge._handle_transcription_segments(chat_id, [DummySegment("Same reply", final=True)])
    assert await queue.get() == "Same reply"


@pytest.mark.asyncio
async def test_internal_function_calls_are_filtered():
    """
    Test that internal LLM function calls (like xAI's XML format) are NOT sent to users.
    This prevents raw XML like <xai:function_call> from appearing in Telegram.
    """
    bridge = LiveKitBridge()
    chat_id = 789
    queue = asyncio.Queue()
    bridge.queues[chat_id] = queue

    # xAI function call XML should be filtered
    xai_function_call = '''<xai:function_call name="delegate_to_subconscious">
<parameter name="topic">blackjack strategy</parameter>
<parameter name="instruction">Analyze gambling odds</parameter>
<parameter name="rationale">Need fact check</parameter>'''
    
    bridge._handle_transcription_segments(chat_id, [DummySegment(xai_function_call, final=True)])
    assert queue.empty(), "xAI function call XML should be filtered"

    # Normal text should pass through
    bridge._handle_transcription_segments(chat_id, [DummySegment("Hello, how are you?", final=True)])
    assert await queue.get() == "Hello, how are you?"

    # {no-response} marker should be filtered
    bridge._reset_transcription_state(chat_id)
    bridge._handle_transcription_segments(chat_id, [DummySegment("{no-response}", final=True)])
    assert queue.empty(), "{no-response} marker should be filtered"

    # <!--viv_internal:brew_begin--> should be filtered
    bridge._reset_transcription_state(chat_id)
    bridge._handle_transcription_segments(chat_id, [DummySegment("<!--viv_internal:brew_begin-->", final=True)])
    assert queue.empty(), "brew_begin marker should be filtered"
    
    # Legacy {{DEEP_THINKING_ACTIVATED}} should also be filtered (backward compatibility)
    bridge._reset_transcription_state(chat_id)
    bridge._handle_transcription_segments(chat_id, [DummySegment("{{DEEP_THINKING_ACTIVATED}}", final=True)])
    assert queue.empty(), "Legacy DEEP_THINKING_ACTIVATED marker should be filtered"


def test_is_internal_message_detection():
    """
    Unit test for the _is_internal_message helper method.
    """
    bridge = LiveKitBridge()
    
    # Should be detected as internal (filtered)
    assert bridge._is_internal_message("") is True
    assert bridge._is_internal_message("   ") is True
    assert bridge._is_internal_message("<xai:function_call name='test'>") is True
    assert bridge._is_internal_message("Some text <xai:function_call> more") is True
    assert bridge._is_internal_message("<function_call>test</function_call>") is True
    assert bridge._is_internal_message("{no-response}") is True
    assert bridge._is_internal_message("{{no-response}}") is True
    assert bridge._is_internal_message("<!--viv_internal:brew_begin-->") is True
    assert bridge._is_internal_message("<!--viv_internal:brew_end-->") is True
    # Legacy markers (backward compatibility)
    assert bridge._is_internal_message("{DEEP_THINKING_ACTIVATED}") is True
    assert bridge._is_internal_message("{{DEEP_THINKING_ACTIVATED}}") is True
    assert bridge._is_internal_message("<some_tag>") is True
    
    # Should NOT be detected as internal (allowed through)
    assert bridge._is_internal_message("Hello, how are you?") is False
    assert bridge._is_internal_message("That's a gambler's fallacy.") is False
    assert bridge._is_internal_message("I think we should discuss this.") is False
    assert bridge._is_internal_message("The weather is nice today.") is False


def test_holding_message_detection():
    bridge = LiveKitBridge()
    assert bridge._is_holding_message("Hang on...") is True
    assert bridge._is_holding_message("Let me get the full details:") is True
    assert bridge._is_holding_message("Here's the latest email from David.") is False


def test_disconnect_notice_enqueue_for_active_chat():
    bridge = LiveKitBridge()
    chat_id = 555
    queue = asyncio.Queue()
    bridge.queues[chat_id] = queue
    bridge.active_chats.add(chat_id)

    bridge._notify_disconnect(chat_id)
    notice = queue.get_nowait()
    assert "Connection lost" in notice
