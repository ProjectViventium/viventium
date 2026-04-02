"""
Performance tests for LiveKitBridge to measure actual latency and validate assumptions.

These tests measure:
1. Bridge overhead (time to send message)
2. Transcription processing latency
3. Queue handling performance
4. Overall end-to-end timing
"""
import asyncio
import time
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
async def test_send_message_overhead():
    """
    Test that send_message() completes quickly (should be < 100ms).
    This measures bridge overhead, NOT LLM latency.
    """
    bridge = LiveKitBridge()
    chat_id = 999
    
    # Mock the room connection to avoid actual LiveKit calls
    class MockRoom:
        async def __await__(self):
            return self
        
        def __init__(self):
            self.local_participant = MockParticipant()
            self.remote_participants = {}
    
    class MockParticipant:
        async def send_text(self, text: str, topic: str):
            # Simulate minimal network overhead
            await asyncio.sleep(0.001)  # 1ms
    
    # Replace connect_user to return mock room
    original_connect_user = bridge.connect_user
    async def mock_connect_user(chat_id):
        return MockRoom()
    bridge.connect_user = mock_connect_user
    # Ensure agent presence check is bypassed for the mock room.
    bridge._agent_present = lambda _room: True
    
    start_time = time.time()
    await bridge.send_message(chat_id, "Test message")
    elapsed = time.time() - start_time
    
    # Bridge overhead should be < 350ms (includes a 200ms stability delay when agent is present)
    # In production, actual LiveKit send_text() adds ~10-50ms network latency
    assert elapsed < 0.35, f"send_message took {elapsed*1000:.2f}ms, expected < 350ms"


@pytest.mark.asyncio
async def test_transcription_processing_latency():
    """
    Test that transcription processing (once received) is fast (< 10ms).
    This measures bridge processing overhead, NOT LLM generation time.
    """
    bridge = LiveKitBridge()
    chat_id = 888
    queue = asyncio.Queue()
    bridge.queues[chat_id] = queue
    
    start_time = time.time()
    bridge._handle_transcription_segments(chat_id, [DummySegment("Hello world", final=True)])
    processing_time = time.time() - start_time
    
    # Processing should be nearly instant (< 10ms)
    assert processing_time < 0.01, f"Transcription processing took {processing_time*1000:.2f}ms, expected < 10ms"
    
    # Verify message was enqueued
    result = await asyncio.wait_for(queue.get(), timeout=0.1)
    assert result == "Hello world"


@pytest.mark.asyncio
async def test_queue_throughput():
    """
    Test that the queue can handle multiple rapid transcriptions without blocking.
    Measures queue processing throughput.
    
    Note: We process and collect messages one at a time because _reset_transcription_state
    clears the queue. This is correct behavior - each user turn should start fresh.
    """
    bridge = LiveKitBridge()
    chat_id = 777
    queue = asyncio.Queue()
    bridge.queues[chat_id] = queue
    
    messages = [f"Message {i}" for i in range(10)]
    received = []
    
    start_time = time.time()
    for msg in messages:
        bridge._reset_transcription_state(chat_id)  # Reset for each message (clears queue)
        bridge._handle_transcription_segments(chat_id, [DummySegment(msg, final=True)])
        # Collect immediately before next reset
        received.append(await asyncio.wait_for(queue.get(), timeout=0.2))
    processing_time = time.time() - start_time
    
    # 10 messages should process in < 200ms (including queue.get() waits)
    assert processing_time < 0.2, f"Processing 10 messages took {processing_time*1000:.2f}ms, expected < 200ms"
    
    # Verify all messages were received correctly
    assert len(received) == 10, f"Only received {len(received)}/10 messages"
    assert received == messages


@pytest.mark.asyncio
async def test_chat_stream_response_time():
    """
    Test that chat_stream() yields responses as soon as they're available.
    This measures the bridge's responsiveness, NOT LLM latency.
    """
    bridge = LiveKitBridge()
    chat_id = 666
    queue = asyncio.Queue()
    bridge.queues[chat_id] = queue
    
    # Mock send_message to avoid actual LiveKit calls
    original_send_message = bridge.send_message
    async def mock_send_message(cid, text):
        pass  # No-op for testing
    bridge.send_message = mock_send_message
    
    # Simulate a response arriving after a delay
    async def simulate_delayed_response():
        await asyncio.sleep(0.05)  # 50ms delay (simulating LLM processing)
        bridge._handle_transcription_segments(chat_id, [DummySegment("Response text", final=True)])
    
    # Start the delayed response simulation
    response_task = asyncio.create_task(simulate_delayed_response())
    
    # Start streaming (signature: chat_stream(text, convo_id))
    start_time = time.time()
    responses = []
    async for chunk in bridge.chat_stream("Test prompt", str(chat_id)):
        responses.append(chunk)
        break  # Just get first response
    
    elapsed = time.time() - start_time
    
    # Should yield response within 100ms of it being enqueued
    # (50ms delay + 50ms buffer for async scheduling)
    assert elapsed < 0.15, f"chat_stream took {elapsed*1000:.2f}ms to yield, expected < 150ms"
    assert responses == ["Response text"], f"Expected ['Response text'], got {responses}"
    
    await response_task


@pytest.mark.asyncio
async def test_multiple_turns_performance():
    """
    Test that multiple conversation turns don't degrade performance.
    Measures if state management adds overhead over time.
    """
    bridge = LiveKitBridge()
    chat_id = 555
    queue = asyncio.Queue()
    bridge.queues[chat_id] = queue
    
    turn_times = []
    
    for turn in range(5):
        bridge._reset_transcription_state(chat_id)
        
        start_time = time.time()
        bridge._handle_transcription_segments(chat_id, [DummySegment(f"Turn {turn} response", final=True)])
        elapsed = time.time() - start_time
        turn_times.append(elapsed)
        
        # Verify message was received
        result = await asyncio.wait_for(queue.get(), timeout=0.1)
        assert result == f"Turn {turn} response"
    
    # All turns should be fast (< 10ms each)
    max_time = max(turn_times)
    assert max_time < 0.01, f"Slowest turn took {max_time*1000:.2f}ms, expected < 10ms"
    
    # Performance should not degrade (last turn shouldn't be significantly slower)
    first_turn = turn_times[0]
    last_turn = turn_times[-1]
    degradation = (last_turn - first_turn) / first_turn if first_turn > 0 else 0
    assert degradation < 2.0, f"Performance degraded by {degradation*100:.1f}%, last turn {last_turn*1000:.2f}ms vs first {first_turn*1000:.2f}ms"


@pytest.mark.asyncio
async def test_filtering_overhead():
    """
    Test that internal message filtering doesn't add significant overhead.
    """
    bridge = LiveKitBridge()
    chat_id = 444
    queue = asyncio.Queue()
    bridge.queues[chat_id] = queue
    
    # Test filtering a complex function call (worst case)
    complex_xml = '''<xai:function_call name="delegate_to_subconscious">
<parameter name="topic">blackjack strategy for guaranteed wins based on math and papers</parameter>
<parameter name="instruction">Analyze if repeated blackjack plays can guarantee billionaire status</parameter>
<parameter name="rationale">Need deep truth check</parameter>
</xai:function_call>'''
    
    start_time = time.time()
    bridge._handle_transcription_segments(chat_id, [DummySegment(complex_xml, final=True)])
    filter_time = time.time() - start_time
    
    # Filtering should be fast (< 5ms even for complex XML)
    assert filter_time < 0.005, f"Filtering took {filter_time*1000:.2f}ms, expected < 5ms"
    
    # Verify message was filtered (not enqueued)
    assert queue.empty(), "Complex XML should be filtered"


def test_bridge_initialization_time():
    """
    Test that LiveKitBridge initializes quickly.
    """
    start_time = time.time()
    bridge = LiveKitBridge()
    elapsed = time.time() - start_time
    
    # Initialization should be instant (< 10ms)
    assert elapsed < 0.01, f"Initialization took {elapsed*1000:.2f}ms, expected < 10ms"


@pytest.mark.asyncio
async def test_concurrent_messages_performance():
    """
    Test that handling concurrent messages from different users doesn't cause blocking.
    """
    bridge = LiveKitBridge()
    
    async def simulate_user(chat_id: int, message: str):
        queue = asyncio.Queue()
        bridge.queues[chat_id] = queue
        
        bridge._handle_transcription_segments(chat_id, [DummySegment(message, final=True)])
        return await asyncio.wait_for(queue.get(), timeout=0.1)
    
    # Simulate 5 concurrent users
    start_time = time.time()
    results = await asyncio.gather(*[
        simulate_user(i, f"Message from user {i}")
        for i in range(5)
    ])
    elapsed = time.time() - start_time
    
    # All concurrent messages should process quickly (< 50ms total)
    assert elapsed < 0.05, f"Processing 5 concurrent messages took {elapsed*1000:.2f}ms, expected < 50ms"
    
    # Verify all messages were received correctly
    assert len(results) == 5
    for i, result in enumerate(results):
        assert result == f"Message from user {i}"
