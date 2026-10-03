"""STT UTC comes from the owned provider stream, not node creation time."""
import asyncio
import ast
import hashlib
import inspect
import textwrap
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from livekit.agents import Agent
from livekit.agents import APIConnectionError
from livekit.agents.stt import SpeechData, SpeechEvent, SpeechEventType
from livekit.agents.stt import RecognizeStream
from livekit.agents.types import APIConnectOptions
from livekit.agents.types import TimedString
from speaker_segments import SpeakerSegmentTracker, SPEAKER_CONTEXT_EXTRA_KEY
from worker import ViventiumVoiceAgent, _ingest_raw_stt_speaker_event
from multi_track_ingress import AudioSampleTimeline, MultiTrackIngressCoordinator, speech_stream_call_timeline_offset_s


@pytest.mark.parametrize('first_frame_s, retry, streaming, has_origin', [
    (1.0, False, True, True),
    (118.0, False, True, True),
    (118.0, True, True, True),
    (118.0, False, False, True),
    (118.0, False, True, False),
])
def test_owned_stream_clock_handles_warm_idle_rejoin_retry_and_vad_adapter(
    first_frame_s, retry, streaming, has_origin,
):
    origin = 1_790_000_000.0
    clock = [origin + 1.0]
    forwarded = []
    lifecycle = []
    context = {}
    frame = SimpleNamespace(duration=0.02)
    tracker = SpeakerSegmentTracker(call_session_id='synthetic-clock')

    class SpeechStream:
        start_time = origin + 1.0
        start_time_offset = 0.0

        async def __aenter__(self):
            self.ready = asyncio.Event()
            lifecycle.append('open')
            return self

        async def __aexit__(self, *args):
            lifecycle.append('close')

        def push_frame(self, received):
            forwarded.append(received)
            # A provider may publish its more exact first-send anchor through the SDK field.
            self.start_time = clock[0]
            self.ready.set()

        async def __aiter__(self):
            await self.ready.wait()
            offset = self.start_time_offset
            first = SpeechEvent(type=SpeechEventType.FINAL_TRANSCRIPT, alternatives=[SpeechData(
                language='en', text='The first stable timing sentence.',
                start_time=3.0 + offset, end_time=7.7 + offset,
            )])
            yield first
            if retry:
                self.start_time = origin + 240.0
                self.start_time_offset = 121.0
                yield SpeechEvent(type=SpeechEventType.FINAL_TRANSCRIPT, alternatives=[SpeechData(
                    language='en', text='The second stable timing sentence.',
                    start_time=122.0, end_time=123.0,
                )])

    speech_stream = SpeechStream()
    provider = SimpleNamespace(capabilities=SimpleNamespace(streaming=streaming),
                               stream=lambda **kwargs: speech_stream)
    adapted = SimpleNamespace(stream=lambda **kwargs: speech_stream)
    session = SimpleNamespace(conn_options=SimpleNamespace(stt_conn_options='synthetic-options'),
                              _recorder_io=None, _started_at=origin)
    activity = SimpleNamespace(stt=provider, vad=object(), session=session,
                               _audio_recognition=SimpleNamespace(_input_started_at=None))
    agent = ViventiumVoiceAgent(instructions='Synthetic timing test.', speaker_tracker=tracker,
        speaker_timeline_offset=lambda: clock[0] - origin,
        speaker_timeline_origin=(lambda: origin * 1000.0) if has_origin else None)
    agent._get_activity_or_raise = lambda: activity

    async def audio():
        try:
            clock[0] = origin + first_frame_s
            yield frame
            await asyncio.Event().wait()
        finally:
            lifecycle.append('input-cancelled')

    async def run():
        async for event in agent.stt_node(audio(), None):
            assert event.type == SpeechEventType.FINAL_TRANSCRIPT
        message = SimpleNamespace(text_content='A stable timing test sentence.', extra={})
        await agent.on_user_turn_completed(None, message)
        context.update(message.extra[SPEAKER_CONTEXT_EXTRA_KEY])

    with patch('worker.time.time', side_effect=lambda: clock[0]), \
         patch('livekit.agents.stt.StreamAdapter', return_value=adapted) as adapter:
        asyncio.run(run())
    assert forwarded == [frame]
    assert lifecycle == ['open', 'input-cancelled', 'close']
    assert adapter.call_count == (0 if streaming else 1)
    if has_origin and not retry:
        expected_end_s = first_frame_s + 7.7
        assert context['utteranceEndClock'] == 'utc'
        assert context['utteranceEndAtMs'] == pytest.approx((origin + expected_end_s) * 1000.0, rel=0, abs=0.001)
    else:
        assert context['utteranceEndClock'] == 'call_audio_relative'
        assert 'utteranceEndAtMs' not in context


@pytest.mark.parametrize('origin, start, offset', [
    (None, 1_790_000_001.0, 1.0),
    (1_790_000_000_000.0, None, 1.0),
    (1_790_000_000_000.0, float('nan'), 1.0),
    (1_790_000_000_000.0, 1_790_000_001.0, True),
])
def test_incomplete_clock_pair_cannot_invent_a_utc_offset(origin, start, offset):
    stream = SimpleNamespace(start_time=start, start_time_offset=offset)
    assert speech_stream_call_timeline_offset_s(stream, origin) is None


def test_stt_node_cancellation_closes_owned_stream_and_audio_input():
    operations = []
    class SpeechStream:
        start_time = 1_790_000_001.0
        start_time_offset = 0.0
        async def __aenter__(self):
            operations.append('open')
            return self
        async def __aexit__(self, *args):
            operations.append('close')
        def push_frame(self, frame):
            operations.append('frame')
        async def __aiter__(self):
            await asyncio.Event().wait()
            yield
    stream = SpeechStream()
    activity = SimpleNamespace(
        stt=SimpleNamespace(capabilities=SimpleNamespace(streaming=True), stream=lambda **kwargs: stream),
        session=SimpleNamespace(conn_options=SimpleNamespace(stt_conn_options='synthetic-options'),
                                _recorder_io=None, _started_at=1_790_000_000.0),
        _audio_recognition=None,
    )
    agent = ViventiumVoiceAgent(instructions='Synthetic cancellation check.')
    agent._get_activity_or_raise = lambda: activity
    async def audio():
        try:
            yield SimpleNamespace(duration=0.02)
            await asyncio.Event().wait()
        finally:
            operations.append('input-cancelled')
    async def run():
        generator = agent.stt_node(audio(), None)
        task = asyncio.create_task(anext(generator))
        while 'frame' not in operations:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await generator.aclose()
    asyncio.run(run())
    assert operations == ['open', 'frame', 'input-cancelled', 'close']


@pytest.mark.parametrize('has_origin', [True, False])
def test_speech_after_twenty_seconds_without_frames_keeps_its_measured_audio_clock(has_origin):
    origin = 1_790_000_000.0
    clock = [origin + 1.0]
    tracker = SpeakerSegmentTracker(call_session_id='synthetic-gap')
    contexts = []
    class SpeechStream:
        start_time = origin + 1.0
        start_time_offset = 0.0
        async def __aenter__(self):
            self.turns = asyncio.Queue()
            self.next_turn = asyncio.Event()
            self.count = 0
            return self
        async def __aexit__(self, *args):
            pass
        def push_frame(self, frame):
            self.count += 1
            if self.count % 50 == 0:
                self.turns.put_nowait(self.count // 50)
        async def __aiter__(self):
            for _ in range(2):
                turn = await self.turns.get()
                yield SpeechEvent(type=SpeechEventType.FINAL_TRANSCRIPT, alternatives=[SpeechData(
                    language='en', text=f'A stable timing sentence for turn {turn}.',
                    start_time=(turn - 1) + 0.1 + self.start_time_offset,
                    end_time=turn + self.start_time_offset,
                )])
                self.next_turn.set()
    stream = SpeechStream()
    activity = SimpleNamespace(
        stt=SimpleNamespace(capabilities=SimpleNamespace(streaming=True), stream=lambda **kwargs: stream),
        session=SimpleNamespace(conn_options=SimpleNamespace(stt_conn_options='synthetic-options'),
                                _recorder_io=None, _started_at=origin), _audio_recognition=None,
    )
    agent = ViventiumVoiceAgent(instructions='Synthetic gap test.', speaker_tracker=tracker,
        speaker_timeline_offset=lambda: clock[0] - origin,
        speaker_timeline_origin=(lambda: origin * 1000.0) if has_origin else None)
    agent._get_activity_or_raise = lambda: activity
    async def audio():
        for turn in range(2):
            base = 1.0 if turn == 0 else 22.0
            for index in range(50):
                clock[0] = origin + base + (index + 1) * 0.02
                yield SimpleNamespace(duration=0.02)
            if turn == 0:
                await stream.next_turn.wait()
            else:
                await asyncio.Event().wait()
    async def run():
        async for event in agent.stt_node(audio(), None):
            message = SimpleNamespace(text_content=event.alternatives[0].text, extra={})
            await agent.on_user_turn_completed(None, message)
            contexts.append(message.extra[SPEAKER_CONTEXT_EXTRA_KEY])
    with patch('worker.time.time', side_effect=lambda: clock[0]):
        asyncio.run(run())
    assert contexts[0]['utteranceEndOffsetMs'] == pytest.approx(2000, rel=0, abs=0.001)
    assert contexts[1]['utteranceEndOffsetMs'] == pytest.approx(23000, rel=0, abs=0.001)
    for index, end_s in enumerate((2.0, 23.0)):
        if has_origin:
            assert contexts[index]['utteranceEndAtMs'] == pytest.approx((origin + end_s) * 1000, rel=0, abs=0.001)
        else:
            assert contexts[index]['utteranceEndClock'] == 'call_audio_relative'
            assert 'utteranceEndAtMs' not in contexts[index]


def test_audio_sample_boundary_keeps_both_sides_of_a_gap_and_sdk_retry_ownership():
    clock = AudioSampleTimeline()
    stream = SimpleNamespace(start_time_offset=1.0)
    clock.push_frame(SimpleNamespace(duration=1.0), stream, 2.0)
    clock.push_frame(SimpleNamespace(duration=1.0), stream, 23.0)
    boundary = SpeechData(language='en', text='Boundary', start_time=2.0, end_time=2.0)
    assert clock.time_for(boundary, stream, end=False) == 22.0
    assert clock.time_for(boundary, stream, end=True) == 2.0
    stream.start_time_offset = 31.0
    clock.push_frame(SimpleNamespace(duration=1.0), stream, 33.0)
    retry = SpeechData(language='en', text='Retry', start_time=31.0, end_time=32.0)
    assert clock.time_for(retry, stream, end=False) is None
    assert clock.time_for(retry, stream, end=True) is None
    assert not clock.physical_utc_available(stream)
    previous_words = [TimedString('Old', start_time_offset=1.0)]
    old = SpeechData(language='en', text='Old', start_time=1.0, end_time=2.0, words=previous_words)
    assert clock.time_for(old, stream, end=True) is None


def test_sample_receipts_are_bounded_and_unmatched_provider_time_uses_the_sdk_pair():
    clock = AudioSampleTimeline()
    stream = SimpleNamespace(start_time_offset=0.0)
    for index in range(5000):
        clock.push_frame(SimpleNamespace(duration=0.02), stream, (index + 1) * 0.02)
    assert len(clock._frames) == 4096
    assert clock.time_for(SpeechData(language='en', text='Old', end_time=1.0), stream, end=True) is None
    assert clock.time_for(SpeechData(language='en', text='Future', end_time=101.0), stream, end=True) is None
    assert clock.time_for(SpeechData(language='en', text='Recent', end_time=100.0), stream, end=True) == pytest.approx(100.0)


def test_pinned_sdk_default_stt_node_contract_requires_explicit_compatibility_review():
    # The owned node needs the default's private activity attributes because its public
    # delegate hides SpeechStream. Detect upstream configuration/lifecycle/default changes
    # before updating this narrow adapter and the owning dependency pin together.
    installed = version('livekit-agents')
    requirements = (Path(__file__).resolve().parents[1] / 'requirements.txt').read_text()
    assert f'livekit-agents=={installed}' in requirements
    assert installed == '1.5.10'
    source = textwrap.dedent(inspect.getsource(Agent.default.stt_node))
    digest = hashlib.sha256(ast.dump(ast.parse(source), include_attributes=False).encode()).hexdigest()
    assert digest == '87fab5c4f4d11806f8656b178a7f6c778b8bdaa63d104cb25a44857d61f25f1e'


def test_ambient_stream_keeps_the_same_measured_sample_clock_after_an_audio_gap():
    origin = 1_790_000_000.0
    clock, turns = [0.0], []
    class SpeechStream:
        start_time = origin
        start_time_offset = 0.0
        def __init__(self):
            self.ready = asyncio.Queue()
            self.next_turn = asyncio.Event()
            self.count = 0
        def push_frame(self, frame):
            self.count += 1
            if self.count % 50 == 0:
                self.ready.put_nowait(self.count // 50)
        def end_input(self):
            pass
        async def __aiter__(self):
            for _ in range(2):
                turn = await self.ready.get()
                yield SpeechEvent(type=SpeechEventType.FINAL_TRANSCRIPT, alternatives=[SpeechData(
                    language='en', text='A stable ambient sentence.', speaker_id='A',
                    start_time=turn - 0.9, end_time=float(turn))])
                self.next_turn.set()
    stream = SpeechStream()
    async def audio():
        for turn in range(2):
            base = 1.0 if turn == 0 else 22.0
            for index in range(50):
                clock[0] = base + (index + 1) * 0.02
                yield SimpleNamespace(frame=SimpleNamespace(duration=0.02))
            if turn == 0:
                await stream.next_turn.wait()
            else:
                await asyncio.Event().wait()
    async def append(target, value):
        target.append(value)
    coordinator = MultiTrackIngressCoordinator(call_session_id='synthetic-ambient-gap',
        owner_participant_identity='synthetic-owner',
        stt_impl=SimpleNamespace(stream=lambda: stream, capabilities=SimpleNamespace(streaming=True)),
        audio_stream_factory=lambda _track: audio(), clock=lambda: clock[0], wall_clock=lambda: origin,
        on_segment_changes=lambda _value: append([], _value),
        on_ambient_turn=lambda value: append(turns, value))
    tracker = SpeakerSegmentTracker(call_session_id='synthetic-ambient-gap',
        participant_authenticated=True, participant_identity='synthetic-guest')
    with patch('multi_track_ingress.time.time', side_effect=lambda: origin + clock[0]):
        asyncio.run(coordinator._run_track_once(participant=None, track=None,
                                                track_sid='synthetic-track', tracker=tracker))
    assert [turn['segments'][0]['endTimeMs'] for turn in turns] == [2000, 23000]
    assert all(turn['segments'][0]['speaker']['actorTrust'] == 'authenticated_participant' for turn in turns)


def test_partial_receipt_window_does_not_mix_measured_and_sdk_endpoint_clocks():
    clock = AudioSampleTimeline()
    stream = SimpleNamespace(start_time_offset=0.0)
    for index in range(5000):
        clock.push_frame(SimpleNamespace(duration=0.02), stream, (index + 1) * 0.02)
    event = SpeechEvent(type=SpeechEventType.FINAL_TRANSCRIPT, alternatives=[SpeechData(
        language='en', text='A long synthetic utterance.', start_time=1.0, end_time=100.0)])
    tracker = SpeakerSegmentTracker(call_session_id='synthetic-partial-clock')
    [segment], _ = _ingest_raw_stt_speaker_event(tracker, event, timeline_offset_s=30.0,
                                               sample_timeline=clock, speech_stream=stream)
    assert segment['startTimeMs'] == 31000
    assert segment['endTimeMs'] == 130000
    assert not clock.physical_utc_available(stream, event.alternatives[0])
    # The completion adapter must not convert the fallback end to physical UTC.
    agent = ViventiumVoiceAgent(instructions='Synthetic partial clock test.', speaker_tracker=tracker,
        speaker_timeline_origin=lambda: 1_790_000_000_000.0)
    agent._speaker_timeline_utc_available = clock.physical_utc_available(stream, event.alternatives[0])
    message = SimpleNamespace(text_content=event.alternatives[0].text, extra={})
    asyncio.run(agent.on_user_turn_completed(None, message))
    context = message.extra[SPEAKER_CONTEXT_EXTRA_KEY]
    assert context['utteranceEndClock'] == 'call_audio_relative'
    assert context['utteranceEndTimingSource'] == 'stt_call_audio_timeline_unproved'
    assert 'utteranceEndAtMs' not in context


def test_real_sdk_backoff_replays_queued_audio_without_claiming_unproved_physical_utc():
    origin = 1_790_000_000.0
    clock = [origin + 1.0]
    receipt, diagnostic = {}, {}
    original_sleep = asyncio.sleep
    async def run():
        backoff = asyncio.Event()
        queued = asyncio.Event()
        new_generation = asyncio.Event()
        stt = SimpleNamespace(_label='synthetic', capabilities=SimpleNamespace(streaming=True),
                              emit=lambda *args: None)
        class RetryingStream(RecognizeStream):
            async def _metrics_monitor_task(self, event_aiter):
                async for _ in event_aiter:
                    pass
            async def _run(self):
                if self._num_retries == 0:
                    raise APIConnectionError('Synthetic first retry')
                if self._num_retries == 1:
                    await anext(self._input_ch.__aiter__())
                    raise APIConnectionError('Synthetic one-second backoff')
                for _ in range(50):
                    await anext(self._input_ch.__aiter__())
                new_generation.set()
                await anext(self._input_ch.__aiter__())
                alternative = SpeechData(language='en', text='A stable queued speaker sentence.',
                    speaker_id='A', start_time=0.01 + self.start_time_offset,
                    end_time=0.7 + self.start_time_offset)
                diagnostic['sdkEndAtMs'] = (self.start_time + 0.7) * 1000
                diagnostic['physicalEndAtMs'] = (origin + 1.9) * 1000
                self._event_ch.send_nowait(SpeechEvent(type=SpeechEventType.FINAL_TRANSCRIPT,
                                                       alternatives=[alternative]))
        stream = RetryingStream(stt=stt, conn_options=APIConnectOptions(max_retry=2, retry_interval=1.0))
        stt.stream = lambda **kwargs: stream
        tracker = SpeakerSegmentTracker(call_session_id='synthetic-queued-retry',
            owner_signed=True, participant_authenticated=True, participant_identity='synthetic-owner')
        activity = SimpleNamespace(stt=stt, _audio_recognition=None,
            session=SimpleNamespace(conn_options=SimpleNamespace(stt_conn_options=stream._conn_options),
                                    _recorder_io=None, _started_at=origin))
        agent = ViventiumVoiceAgent(instructions='Synthetic SDK queue test.', speaker_tracker=tracker,
            speaker_timeline_offset=lambda: clock[0] - origin,
            speaker_timeline_origin=lambda: origin * 1000.0)
        agent._get_activity_or_raise = lambda: activity
        async def audio():
            clock[0] = origin + 1.2
            yield SimpleNamespace(duration=0.02, sample_rate=16000)
            await backoff.wait()
            for index in range(50):
                clock[0] = origin + 1.2 + (index + 1) * 0.02
                yield SimpleNamespace(duration=0.02, sample_rate=16000)
            queued.set()
            await new_generation.wait()
            clock[0] = origin + 3.3
            yield SimpleNamespace(duration=0.8, sample_rate=16000)
            await asyncio.Event().wait()
        async def sdk_sleep(delay):
            if delay >= 1.0:
                backoff.set()
                await queued.wait()
                assert delay == 1.0
            else:
                clock[0] += delay
                await original_sleep(0)
        with patch('livekit.agents.stt.stt.asyncio.sleep', new=sdk_sleep):
            async for event in agent.stt_node(audio(), None):
                message = SimpleNamespace(text_content=event.alternatives[0].text, extra={})
                await agent.on_user_turn_completed(None, message)
                receipt.update(message.extra[SPEAKER_CONTEXT_EXTRA_KEY])
    with patch('worker.time.time', side_effect=lambda: clock[0]):
        asyncio.run(run())
    assert diagnostic['sdkEndAtMs'] - diagnostic['physicalEndAtMs'] == pytest.approx(1000, rel=0, abs=0.001)
    assert receipt['speakerSegments'][0]['speaker']['actorTrust'] == 'owner_participant'
    assert receipt['utteranceEndClock'] == 'call_audio_relative'
    assert 'utteranceEndAtMs' not in receipt
