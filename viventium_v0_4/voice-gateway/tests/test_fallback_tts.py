"""Viventium voice-gateway TTS fallback tests."""

# === VIVENTIUM START ===
# Feature: Fallback TTS wrapper tests
# Added: 2026-02-06
# === VIVENTIUM END ===

import asyncio
import os
import sys
import unittest
from unittest.mock import patch

from livekit.agents import APIConnectOptions, APIError, APIStatusError, APITimeoutError
from livekit.agents.tts import AudioEmitter, ChunkedStream, SynthesizeStream, TTS, TTSCapabilities

# Ensure voice-gateway root is on sys.path so `import fallback_tts` works
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import fallback_tts as fallback_tts_module  # noqa: E402
from fallback_tts import FallbackTTS, ProviderAttempt  # noqa: E402


def _silence_pcm(*, sample_rate: int, num_channels: int, duration_ms: int) -> bytes:
    samples_per_channel = int(sample_rate * (duration_ms / 1000.0))
    total_samples = samples_per_channel * num_channels
    return b"\x00\x00" * total_samples  # pcm_s16le silence


def test_streaming_control_observer_is_bounded_and_detects_split_markup() -> None:
    observer = fallback_tts_module._StreamingVoiceControlObserver(max_pending_chars=64)

    observer.push_text("Synthetic text " * 10_000)
    assert observer.pending_chars == 0
    assert observer.controls_present is False

    observer.push_text("<emo")
    assert observer.pending_chars == 4
    observer.push_text('tion value="curiosity"/>Hello')

    assert observer.controls_present is True
    assert observer.pending_chars == 0


class _FakeChunkedStream(ChunkedStream):
    def __init__(self, *, tts: TTS, input_text: str, conn_options, should_fail: bool) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._should_fail = should_fail

    async def _run(self, output_emitter: AudioEmitter) -> None:
        if self._should_fail:
            raise APIError("boom", retryable=True)

        output_emitter.initialize(
            request_id="fake",
            sample_rate=self._tts.sample_rate,
            num_channels=self._tts.num_channels,
            mime_type="audio/pcm",
            frame_size_ms=200,
            stream=False,
        )
        output_emitter.push(
            _silence_pcm(
                sample_rate=self._tts.sample_rate,
                num_channels=self._tts.num_channels,
                duration_ms=200,
            )
        )


class FakeTTS(TTS):
    def __init__(self, *, sample_rate: int, should_fail: bool = False) -> None:
        super().__init__(
            capabilities=TTSCapabilities(streaming=False),
            sample_rate=sample_rate,
            num_channels=1,
        )
        self._should_fail = should_fail
        # === VIVENTIUM START ===
        # Feature: Capture synthesized input text for test assertions.
        self.last_synth_text: str = ""
        # === VIVENTIUM END ===

    @property
    def provider(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return "fake"

    def synthesize(self, text: str, *, conn_options) -> ChunkedStream:
        self.last_synth_text = text
        return _FakeChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
            should_fail=self._should_fail,
        )


class _FakeStreamingSynthesizeStream(SynthesizeStream):
    def __init__(self, *, tts: TTS, conn_options, should_fail: bool) -> None:
        super().__init__(tts=tts, conn_options=conn_options)
        self._should_fail = should_fail

    async def _run(self, output_emitter: AudioEmitter) -> None:
        output_emitter.initialize(
            request_id="fake-stream",
            sample_rate=self._tts.sample_rate,
            num_channels=self._tts.num_channels,
            mime_type="audio/pcm",
            frame_size_ms=200,
            stream=True,
        )
        output_emitter.start_segment(segment_id="seg")
        async for data in self._input_ch:
            if isinstance(data, str):
                self._tts.last_stream_chunks.append(data)  # type: ignore[attr-defined]
        if self._should_fail:
            raise APIError("boom", retryable=True)
        output_emitter.push(
            _silence_pcm(
                sample_rate=self._tts.sample_rate,
                num_channels=self._tts.num_channels,
                duration_ms=200,
            )
        )


class FakeStreamingTTS(TTS):
    def __init__(self, *, sample_rate: int, should_fail: bool = False) -> None:
        super().__init__(
            capabilities=TTSCapabilities(streaming=True),
            sample_rate=sample_rate,
            num_channels=1,
        )
        self._should_fail = should_fail
        self.last_stream_chunks: list[str] = []

    @property
    def provider(self) -> str:
        return "fake-streaming"

    @property
    def model(self) -> str:
        return "fake-streaming"

    def synthesize(self, text: str, *, conn_options) -> ChunkedStream:
        return _FakeChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
            should_fail=self._should_fail,
        )

    def stream(self, *, conn_options) -> SynthesizeStream:
        return _FakeStreamingSynthesizeStream(
            tts=self,
            conn_options=conn_options,
            should_fail=self._should_fail,
        )


class TestFallbackTTS(unittest.IsolatedAsyncioTestCase):
    async def test_wrapper_reports_streaming_capability(self) -> None:
        wrapper = FallbackTTS(
            attempts=[
                ProviderAttempt(label="primary", tts=FakeTTS(sample_rate=44100, should_fail=False)),
                ProviderAttempt(label="fallback", tts=FakeStreamingTTS(sample_rate=44100, should_fail=False)),
            ]
        )

        self.assertTrue(wrapper.capabilities.streaming)

    async def test_primary_success_does_not_invoke_fallback(self) -> None:
        selected: list[str] = []
        wrapper = FallbackTTS(
            attempts=[
                ProviderAttempt(label="primary", tts=FakeTTS(sample_rate=44100, should_fail=False)),
                ProviderAttempt(label="fallback", tts=FakeTTS(sample_rate=44100, should_fail=True)),
            ],
            on_provider_selected=lambda provider, _tts: selected.append(provider),
        )

        frame = await wrapper.synthesize("hello").collect()
        self.assertEqual(frame.sample_rate, 44100)
        self.assertGreater(len(frame.data), 0)
        self.assertEqual(selected, ["primary"])

    async def test_primary_failure_uses_fallback(self) -> None:
        selected: list[str] = []
        wrapper = FallbackTTS(
            attempts=[
                ProviderAttempt(label="primary", tts=FakeTTS(sample_rate=44100, should_fail=True)),
                ProviderAttempt(label="fallback", tts=FakeTTS(sample_rate=44100, should_fail=False)),
            ],
            on_provider_selected=lambda provider, _tts: selected.append(provider),
        )

        frame = await wrapper.synthesize("hello").collect()
        self.assertEqual(frame.sample_rate, 44100)
        self.assertGreater(len(frame.data), 0)
        self.assertEqual(selected, ["fallback"])

    async def test_resamples_fallback_to_primary_rate(self) -> None:
        selected: list[str] = []
        wrapper = FallbackTTS(
            attempts=[
                ProviderAttempt(label="primary", tts=FakeTTS(sample_rate=44100, should_fail=True)),
                ProviderAttempt(label="fallback", tts=FakeTTS(sample_rate=24000, should_fail=False)),
            ],
            on_provider_selected=lambda provider, _tts: selected.append(provider),
        )

        frame = await wrapper.synthesize("hello").collect()
        self.assertEqual(frame.sample_rate, 44100)
        self.assertGreater(len(frame.data), 0)
        self.assertEqual(selected, ["fallback"])


    # === VIVENTIUM START ===
    # Feature: Tests for same-turn fallback SSML tag sanitization.
    # Updated 2026-02-22: Both SSML tags AND bracket nonverbal markers are now
    # stripped for non-expressive fallback providers to prevent literal reading
    # of tokens like "[laughter]" or "[sigh]" by ElevenLabs/OpenAI.
    async def test_fallback_strips_ssml_for_elevenlabs(self) -> None:
        """When primary Cartesia fails and fallback is elevenlabs, SSML tags and bracket markers are stripped."""
        primary = FakeTTS(sample_rate=44100, should_fail=True)
        fallback = FakeTTS(sample_rate=44100, should_fail=False)
        selected: list[str] = []
        wrapper = FallbackTTS(
            attempts=[
                ProviderAttempt(label="cartesia", tts=primary),
                ProviderAttempt(label="elevenlabs", tts=fallback, sanitize_voice_markup=True),
            ],
            on_provider_selected=lambda provider, _tts: selected.append(provider),
        )

        tagged_text = '<emotion value="excited"/>Hello! [laughter] How are you?'
        frame = await wrapper.synthesize(tagged_text).collect()
        self.assertGreater(len(frame.data), 0)
        self.assertEqual(selected, ["elevenlabs"])
        # Both SSML tags and bracket nonverbal markers are stripped.
        self.assertNotIn("<emotion", fallback.last_synth_text)
        self.assertNotIn("[laughter]", fallback.last_synth_text)
        self.assertIn("Hello!", fallback.last_synth_text)
        self.assertIn("How are you?", fallback.last_synth_text)

    async def test_fallback_strips_ssml_for_openai(self) -> None:
        """When primary fails and fallback is openai, SSML tags and bracket markers are stripped."""
        primary = FakeTTS(sample_rate=44100, should_fail=True)
        fallback = FakeTTS(sample_rate=44100, should_fail=False)
        selected: list[str] = []
        wrapper = FallbackTTS(
            attempts=[
                ProviderAttempt(label="cartesia", tts=primary),
                ProviderAttempt(label="openai", tts=fallback, sanitize_voice_markup=True),
            ],
            on_provider_selected=lambda provider, _tts: selected.append(provider),
        )

        tagged_text = '<emotion value="sad">Oh no</emotion> [sigh] That is bad.'
        frame = await wrapper.synthesize(tagged_text).collect()
        self.assertGreater(len(frame.data), 0)
        self.assertEqual(selected, ["openai"])
        # Both SSML tags and bracket nonverbal markers are stripped.
        self.assertNotIn("<emotion", fallback.last_synth_text)
        self.assertNotIn("[sigh]", fallback.last_synth_text)
        self.assertIn("Oh no", fallback.last_synth_text)
        self.assertIn("That is bad.", fallback.last_synth_text)

    async def test_primary_cartesia_receives_original_tags(self) -> None:
        """When primary Cartesia succeeds, it receives the original tagged text."""
        primary = FakeTTS(sample_rate=44100, should_fail=False)
        fallback = FakeTTS(sample_rate=44100, should_fail=True)
        selected: list[str] = []
        wrapper = FallbackTTS(
            attempts=[
                ProviderAttempt(label="cartesia", tts=primary),
                ProviderAttempt(label="elevenlabs", tts=fallback),
            ],
            on_provider_selected=lambda provider, _tts: selected.append(provider),
        )

        tagged_text = '<emotion value="excited"/>Hello! [laughter]'
        frame = await wrapper.synthesize(tagged_text).collect()
        self.assertGreater(len(frame.data), 0)
        self.assertEqual(selected, ["cartesia"])
        # Cartesia should receive the original text with tags intact.
        self.assertEqual(primary.last_synth_text, tagged_text)

    async def test_chunked_rendering_observation_reports_preserved_controls_without_payload(self) -> None:
        primary = FakeTTS(sample_rate=44100, should_fail=False)
        wrapper = FallbackTTS(
            attempts=[ProviderAttempt(label="cartesia", tts=primary)],
        )
        private_text = '<emotion value="curiosity"/>Synthetic private sentence.'

        with self.assertLogs("voice-gateway.fallback_tts", level="INFO") as captured:
            frame = await wrapper.synthesize(private_text).collect()

        self.assertGreater(len(frame.data), 0)
        joined = "\n".join(captured.output)
        self.assertIn("[VoiceRendering][voice_gateway]", joined)
        self.assertIn("event=attempt", joined)
        self.assertIn("event=selected", joined)
        self.assertIn("provider=cartesia", joined)
        self.assertIn("model=fake", joined)
        self.assertIn("role=primary", joined)
        self.assertIn("markup_policy=preserve", joined)
        self.assertIn("controls_present=true", joined)
        self.assertNotIn(private_text, joined)
        self.assertNotIn("Synthetic private sentence", joined)

    async def test_chunked_rendering_observation_reports_fallback_sanitization(self) -> None:
        primary = FakeTTS(sample_rate=44100, should_fail=True)
        fallback = FakeTTS(sample_rate=44100, should_fail=False)
        wrapper = FallbackTTS(
            attempts=[
                ProviderAttempt(label="cartesia", tts=primary),
                ProviderAttempt(label="openai", tts=fallback, sanitize_voice_markup=True),
            ],
        )

        with self.assertLogs("voice-gateway.fallback_tts", level="INFO") as captured:
            frame = await wrapper.synthesize("[sigh] Synthetic fallback sentence.").collect()

        self.assertGreater(len(frame.data), 0)
        joined = "\n".join(captured.output)
        self.assertIn("provider=openai", joined)
        self.assertIn("role=fallback", joined)
        self.assertIn("markup_policy=strip", joined)
        self.assertIn("controls_present=true", joined)
        self.assertIn("controls_action=stripped", joined)
        self.assertNotIn("Synthetic fallback sentence", joined)

    async def test_streaming_primary_failure_uses_fallback(self) -> None:
        selected: list[str] = []
        primary = FakeStreamingTTS(sample_rate=44100, should_fail=True)
        fallback = FakeStreamingTTS(sample_rate=44100, should_fail=False)
        wrapper = FallbackTTS(
            attempts=[
                ProviderAttempt(label="primary", tts=primary),
                ProviderAttempt(label="fallback", tts=fallback),
            ],
            on_provider_selected=lambda provider, _tts: selected.append(provider),
        )

        stream = wrapper.stream()
        stream.push_text("hello ")
        stream.push_text("world")
        stream.end_input()

        frames = []
        async with stream:
            async for ev in stream:
                frames.append(ev.frame)

        self.assertGreater(len(frames), 0)
        self.assertEqual(selected, ["fallback"])
        self.assertEqual(fallback.last_stream_chunks, ["hello ", "world"])

    async def test_streaming_provider_input_drops_orphan_period_chunk(self) -> None:
        tts = FakeStreamingTTS(sample_rate=44100, should_fail=False)
        wrapper = FallbackTTS(attempts=[ProviderAttempt(label="xai", tts=tts)])

        stream = wrapper.stream()
        stream.push_text("Good to hear you")
        stream.push_text(".")
        stream.push_text(" Next thought.")
        stream.end_input()

        async with stream:
            async for _ in stream:
                pass

        self.assertEqual(tts.last_stream_chunks, ["Good to hear you", " Next thought."])
        self.assertNotIn(".", tts.last_stream_chunks)

    async def test_streaming_provider_input_logs_forwarded_and_dropped_chunks(self) -> None:
        tts = FakeStreamingTTS(sample_rate=44100, should_fail=False)
        wrapper = FallbackTTS(attempts=[ProviderAttempt(label="xai", tts=tts)])

        stream = wrapper.stream()
        stream.push_text("Good to hear you")
        stream.push_text(".")
        stream.push_text(" Next thought.")
        stream.end_input()

        with patch.dict(os.environ, {"VIVENTIUM_VOICE_LOG_TTS_INPUTS": "1"}, clear=False):
            with self.assertLogs("voice-gateway.fallback_tts", level="INFO") as captured:
                async with stream:
                    async for _ in stream:
                        pass

        joined = "\n".join(captured.output)
        self.assertIn("[VoiceTTSInput]", joined)
        self.assertIn("action=dropped", joined)
        self.assertIn("punctuation_only=True", joined)
        self.assertIn('text_json="."', joined)
        self.assertIn("action=forwarded", joined)
        self.assertIn('text_json=" Next thought."', joined)
        self.assertEqual(tts.last_stream_chunks, ["Good to hear you", " Next thought."])

    async def test_streaming_rendering_observation_is_structural_and_payload_free(self) -> None:
        tts = FakeStreamingTTS(sample_rate=44100, should_fail=False)
        wrapper = FallbackTTS(attempts=[ProviderAttempt(label="xai", tts=tts)])
        private_text = "<soft>Synthetic private sentence.</soft>"

        stream = wrapper.stream()
        stream.push_text(private_text)
        stream.end_input()

        with self.assertLogs("voice-gateway.fallback_tts", level="INFO") as captured:
            async with stream:
                async for _ in stream:
                    pass

        joined = "\n".join(captured.output)
        self.assertIn("[VoiceRendering][voice_gateway]", joined)
        self.assertIn("event=attempt", joined)
        self.assertIn("event=input_complete", joined)
        self.assertIn("event=selected", joined)
        self.assertIn("provider=xai", joined)
        self.assertIn("markup_policy=preserve", joined)
        self.assertIn("controls_present=true", joined)
        self.assertNotIn(private_text, joined)
        self.assertNotIn("Synthetic private sentence", joined)

    async def test_chunked_provider_input_logs_full_synthesize_text(self) -> None:
        tts = FakeTTS(sample_rate=44100, should_fail=False)
        wrapper = FallbackTTS(attempts=[ProviderAttempt(label="openai", tts=tts)])

        with patch.dict(os.environ, {"VIVENTIUM_VOICE_LOG_TTS_INPUTS": "1"}, clear=False):
            with self.assertLogs("voice-gateway.fallback_tts", level="INFO") as captured:
                frame = await wrapper.synthesize("Full response.").collect()

        self.assertGreater(len(frame.data), 0)
        joined = "\n".join(captured.output)
        self.assertIn("[VoiceTTSInput]", joined)
        self.assertIn("mode=synthesize", joined)
        self.assertIn("stage=synthesize", joined)
        self.assertIn("action=forwarded", joined)
        self.assertIn('text_json="Full response."', joined)

    async def test_streaming_provider_input_preserves_trailing_word_boundary(self) -> None:
        tts = FakeStreamingTTS(sample_rate=44100, should_fail=False)
        wrapper = FallbackTTS(attempts=[ProviderAttempt(label="xai", tts=tts)])

        stream = wrapper.stream()
        stream.push_text("Nice, invoice cleared ")
        stream.push_text("is a real milestone.")
        stream.end_input()

        async with stream:
            async for _ in stream:
                pass

        self.assertEqual(
            "".join(tts.last_stream_chunks),
            "Nice, invoice cleared is a real milestone.",
        )
        self.assertEqual(tts.last_stream_chunks[0], "Nice, invoice cleared ")

    async def test_streaming_provider_input_keeps_decimal_split(self) -> None:
        tts = FakeStreamingTTS(sample_rate=44100, should_fail=False)
        wrapper = FallbackTTS(attempts=[ProviderAttempt(label="xai", tts=tts)])

        stream = wrapper.stream()
        stream.push_text("3")
        stream.push_text(".14 is pi.")
        stream.end_input()

        async with stream:
            async for _ in stream:
                pass

        self.assertEqual(tts.last_stream_chunks, ["3", ".14 is pi."])

    async def test_streaming_provider_input_keeps_standalone_decimal_point(self) -> None:
        tts = FakeStreamingTTS(sample_rate=44100, should_fail=False)
        wrapper = FallbackTTS(attempts=[ProviderAttempt(label="xai", tts=tts)])

        stream = wrapper.stream()
        stream.push_text("3")
        stream.push_text(".")
        stream.push_text("14 is pi.")
        stream.end_input()

        async with stream:
            async for _ in stream:
                pass

        self.assertEqual(tts.last_stream_chunks, ["3", ".14 is pi."])

    async def test_streaming_provider_input_preserves_clause_punctuation(self) -> None:
        tts = FakeStreamingTTS(sample_rate=44100, should_fail=False)
        wrapper = FallbackTTS(attempts=[ProviderAttempt(label="xai", tts=tts)])

        stream = wrapper.stream()
        stream.push_text("I get it")
        stream.push_text(",")
        stream.push_text(" however, timing matters.")
        stream.end_input()

        async with stream:
            async for _ in stream:
                pass

        self.assertEqual(tts.last_stream_chunks, ["I get it", ", however, timing matters."])

    async def test_streaming_provider_input_preserves_delayed_question_before_next_phrase(self) -> None:
        tts = FakeStreamingTTS(sample_rate=44100, should_fail=False)
        wrapper = FallbackTTS(attempts=[ProviderAttempt(label="xai", tts=tts)])

        stream = wrapper.stream()
        stream.push_text("Sleep okay")
        stream.push_text("?")
        stream.push_text(" Want to plan today?")
        stream.end_input()

        async with stream:
            async for _ in stream:
                pass

        self.assertEqual(tts.last_stream_chunks, ["Sleep okay", "? Want to plan today?"])

    async def test_streaming_provider_input_preserves_quoted_delayed_question(self) -> None:
        tts = FakeStreamingTTS(sample_rate=44100, should_fail=False)
        wrapper = FallbackTTS(attempts=[ProviderAttempt(label="xai", tts=tts)])

        stream = wrapper.stream()
        stream.push_text("Sleep okay")
        stream.push_text('?"')
        stream.push_text(" she asked.")
        stream.end_input()

        async with stream:
            async for _ in stream:
                pass

        self.assertEqual(tts.last_stream_chunks, ["Sleep okay", '?" she asked.'])

    async def test_streaming_provider_input_preserves_delayed_exclamation_before_next_phrase(self) -> None:
        tts = FakeStreamingTTS(sample_rate=44100, should_fail=False)
        wrapper = FallbackTTS(attempts=[ProviderAttempt(label="xai", tts=tts)])

        stream = wrapper.stream()
        stream.push_text("That landed")
        stream.push_text("!")
        stream.push_text(" Keep going.")
        stream.end_input()

        async with stream:
            async for _ in stream:
                pass

        self.assertEqual(tts.last_stream_chunks, ["That landed", "! Keep going."])

    async def test_streaming_fallback_strips_control_tags_for_openai(self) -> None:
        selected: list[str] = []
        primary = FakeStreamingTTS(sample_rate=44100, should_fail=True)
        fallback = FakeStreamingTTS(sample_rate=44100, should_fail=False)
        wrapper = FallbackTTS(
            attempts=[
                ProviderAttempt(label="cartesia", tts=primary),
                ProviderAttempt(label="openai", tts=fallback, sanitize_voice_markup=True),
            ],
            on_provider_selected=lambda provider, _tts: selected.append(provider),
        )

        stream = wrapper.stream()
        stream.push_text('<emotion value="exc')
        stream.push_text('ited"/>Hello ')
        stream.push_text("[laughter")
        stream.push_text("] world")
        stream.end_input()

        async with stream:
            async for _ in stream:
                pass

        self.assertEqual(selected, ["openai"])
        self.assertEqual("".join(fallback.last_stream_chunks), "Hello  world")
    # === VIVENTIUM END ===



# === VIVENTIUM START ===
# The installed SDK owns replay across retries; fallback owns replay within one run.
class _RetryInputTTS(TTS):
    def __init__(self, modes):
        super().__init__(capabilities=TTSCapabilities(streaming=True), sample_rate=24000, num_channels=1)
        self.modes = modes
        self.inputs = []
        self.opened = []

    @property
    def provider(self):
        return "synthetic"

    @property
    def model(self):
        return "synthetic"

    def synthesize(self, *args, **kwargs):
        raise AssertionError("streaming route required")

    def stream(self, *, conn_options):
        index = len(self.inputs)
        self.inputs.append([])
        self.opened.append(asyncio.Event())
        return _RetryInputStream(tts=self, conn_options=conn_options, index=index)


class _RetryInputStream(SynthesizeStream):
    def __init__(self, *, tts, conn_options, index):
        super().__init__(tts=tts, conn_options=conn_options)
        self.index = index

    async def _run(self, emitter):
        mode = self._tts.modes[min(self.index, len(self._tts.modes) - 1)]
        self._tts.opened[self.index].set()
        if mode == "unauthorized":
            raise APIStatusError("synthetic unauthorized", status_code=401)
        async for item in self._input_ch:
            if isinstance(item, str):
                self._tts.inputs[self.index].append(item)
                if mode == "early_timeout":
                    raise APITimeoutError("synthetic timeout")
        if mode == "timeout":
            raise APITimeoutError("synthetic timeout")
        emitter.initialize(request_id="synthetic", sample_rate=24000, num_channels=1,
                           mime_type="audio/pcm", frame_size_ms=200, stream=True)
        emitter.start_segment(segment_id="synthetic")
        emitter.push(bytes(9600))
        if mode == "partial_error":
            await asyncio.sleep(0)
            raise APITimeoutError("synthetic after audio")


class TestNativeSdkFallbackRetryReplay(unittest.IsolatedAsyncioTestCase):
    async def consume(self, stream):
        async with stream:
            return [event async for event in stream]

    async def test_native_retry_replays_long_markup_once_per_attempt(self):
        primary = _RetryInputTTS(["timeout", "timeout", "success"])
        fallback = _RetryInputTTS(["unauthorized"])
        wrapper = FallbackTTS(attempts=[ProviderAttempt("primary", primary), ProviderAttempt("fallback", fallback)])
        chunks = ['<emotion value="ca', 'lm">Pine moon. ' * 1,
                  'Pine moon. ' * 256, '</emotion>Final words.']
        original = ''.join(chunks)
        stream = wrapper.stream(conn_options=APIConnectOptions(max_retry=2, retry_interval=0, timeout=1))
        for chunk in chunks:
            stream.push_text(chunk)
        stream.end_input()
        frames = await self.consume(stream)
        self.assertTrue(frames)
        self.assertEqual([''.join(parts) for parts in primary.inputs], [original] * 3)
        self.assertEqual(len(fallback.inputs), 2)  # Terminal-provider policy is unchanged.

    async def test_native_retry_captures_future_input_once(self):
        primary = _RetryInputTTS(["early_timeout", "success"])
        fallback = _RetryInputTTS(["unauthorized"])
        wrapper = FallbackTTS(attempts=[ProviderAttempt("primary", primary), ProviderAttempt("fallback", fallback)])
        stream = wrapper.stream(conn_options=APIConnectOptions(max_retry=1, retry_interval=0, timeout=1))
        stream.push_text('<emotion value="calm">First words ')
        consume = asyncio.create_task(self.consume(stream))
        async def second_started():
            while len(primary.opened) < 2:
                await asyncio.sleep(0)
            await primary.opened[1].wait()
        try:
            await asyncio.wait_for(second_started(), 2)
            stream.push_text('and later words.</emotion>')
            stream.end_input()
            self.assertTrue(await asyncio.wait_for(consume, 2))
            self.assertEqual(''.join(primary.inputs[1]), '<emotion value="calm">First words and later words.</emotion>')
        finally:
            await stream.aclose()
            if not consume.done():
                consume.cancel()
            await asyncio.gather(consume, return_exceptions=True)

    async def test_same_run_fallback_keeps_exact_markup_and_tail(self):
        primary = _RetryInputTTS(["timeout"])
        fallback = _RetryInputTTS(["success"])
        wrapper = FallbackTTS(attempts=[ProviderAttempt("primary", primary), ProviderAttempt("fallback", fallback)])
        text = '<emotion value="calm">Pine moon.</emotion> Final words.'
        stream = wrapper.stream(conn_options=APIConnectOptions(max_retry=2, retry_interval=0, timeout=1))
        stream.push_text(text)
        stream.end_input()
        self.assertTrue(await self.consume(stream))
        self.assertEqual([''.join(parts) for parts in primary.inputs], [text])
        self.assertEqual([''.join(parts) for parts in fallback.inputs], [text])

    async def test_partial_audio_does_not_restart_or_invoke_fallback(self):
        primary = _RetryInputTTS(["partial_error", "success"])
        fallback = _RetryInputTTS(["success"])
        wrapper = FallbackTTS(attempts=[ProviderAttempt("primary", primary), ProviderAttempt("fallback", fallback)])
        stream = wrapper.stream(conn_options=APIConnectOptions(max_retry=2, retry_interval=0, timeout=1))
        stream.push_text('Keep the delivered words.')
        stream.end_input()
        self.assertTrue(await self.consume(stream))
        self.assertEqual(len(primary.inputs), 1)
        self.assertEqual(fallback.inputs, [])

    async def test_terminal_unauthorized_alone_keeps_native_no_retry(self):
        primary = _RetryInputTTS(["unauthorized"])
        wrapper = FallbackTTS(attempts=[ProviderAttempt("primary", primary)])
        stream = wrapper.stream(conn_options=APIConnectOptions(max_retry=2, retry_interval=0, timeout=1))
        stream.push_text('Unavailable remains unavailable.')
        stream.end_input()
        with self.assertRaises(APIError) as caught:
            await self.consume(stream)
        self.assertFalse(caught.exception.retryable)
        self.assertEqual(len(primary.inputs), 1)
# === VIVENTIUM END ===



# === VIVENTIUM START ===
# Provider warnings retain typed diagnostics, never provider error payloads.
class TestProviderFailureLoggingPrivacy(unittest.IsolatedAsyncioTestCase):
    def failure(self, api_error):
        if api_error:
            return APIStatusError(
                "Synthetic private provider prose.", status_code=401,
                body={"error": {"message": "Synthetic masked key " + "-".join(("sk", "test...private-fragment"))}},
                request_id="synthetic-private-request",
            )
        return RuntimeError("Synthetic private provider prose.")

    def assert_private_warning(self, captured, exc):
        joined = "\n".join(captured.output)
        self.assertNotIn("-".join(("sk", "test...private-fragment")), joined)
        self.assertNotIn("Synthetic private provider prose", joined)
        self.assertNotIn("synthetic-private-request", joined)
        self.assertNotIn("Traceback", joined)
        warnings = [record for record in captured.records if record.levelname == "WARNING"]
        self.assertEqual(len(warnings), 1)
        self.assertIsNone(warnings[0].exc_info)
        self.assertIn("primary", joined)
        self.assertIn(f"error_class={type(exc).__name__}", joined)
        self.assertIn(f"retryable={bool(getattr(exc, 'retryable', True))}", joined)
        if isinstance(exc, APIStatusError):
            self.assertIn("status_code=401", joined)

    async def chunked_failure(self, api_error):
        primary = FakeTTS(sample_rate=24000)
        fallback = FakeTTS(sample_rate=24000)
        selected = []
        wrapper = FallbackTTS(
            attempts=[ProviderAttempt("primary", primary), ProviderAttempt("fallback", fallback)],
            on_provider_selected=lambda label, _tts: selected.append(label),
        )
        exc = self.failure(api_error)
        original = fallback_tts_module._FallbackChunkedStream._collect_frames

        async def collect(stream, attempt, **kwargs):
            if attempt.tts is primary:
                raise exc
            return await original(stream, attempt, **kwargs)

        text = '<emotion value="calm">Complete words.</emotion> Final tail.'
        with patch.object(fallback_tts_module._FallbackChunkedStream, "_collect_frames", collect):
            with self.assertLogs("voice-gateway.fallback_tts", level="WARNING") as captured:
                frame = await wrapper.synthesize(text).collect()
        self.assertGreater(len(frame.data), 0)
        self.assertEqual(selected, ["fallback"])
        self.assertEqual(fallback.last_synth_text, text)
        self.assert_private_warning(captured, exc)

    async def streaming_failure(self, api_error):
        primary = FakeStreamingTTS(sample_rate=24000)
        fallback = FakeStreamingTTS(sample_rate=24000)
        selected = []
        attempted = []
        wrapper = FallbackTTS(
            attempts=[ProviderAttempt("primary", primary), ProviderAttempt("fallback", fallback)],
            on_provider_selected=lambda label, _tts: selected.append(label),
            on_provider_attempt=attempted.append,
        )
        exc = self.failure(api_error)
        original = fallback_tts_module._FallbackSynthesizeStream._try_synthesize

        async def synthesize(stream, *, attempt, **kwargs):
            if attempt.tts is primary:
                raise exc
            async for audio in original(stream, attempt=attempt, **kwargs):
                yield audio

        text = '<emotion value="calm">Complete words.</emotion> Final tail.'
        stream = wrapper.stream()
        stream.push_text(text)
        stream.end_input()
        with patch.object(fallback_tts_module._FallbackSynthesizeStream, "_try_synthesize", synthesize):
            with self.assertLogs("voice-gateway.fallback_tts", level="WARNING") as captured:
                async with stream:
                    frames = [event.frame async for event in stream]
        self.assertTrue(frames)
        self.assertEqual(selected, ["fallback"])
        self.assertEqual(attempted, [primary, primary, fallback])
        self.assertEqual("".join(fallback.last_stream_chunks), text)
        self.assert_private_warning(captured, exc)

    async def test_chunked_api_status_warning_omits_private_payload(self):
        await self.chunked_failure(True)

    async def test_chunked_generic_warning_omits_private_prose_and_traceback(self):
        await self.chunked_failure(False)

    async def test_streaming_api_status_warning_omits_private_payload(self):
        await self.streaming_failure(True)

    async def test_streaming_generic_warning_omits_private_prose_and_traceback(self):
        await self.streaming_failure(False)

    def test_attempt_description_preserves_structural_status_retryability_and_voice(self):
        from types import SimpleNamespace
        provider = FakeTTS(sample_rate=24000)
        provider._opts = SimpleNamespace(voice_id="synthetic-voice")
        for status, retryable in ((401, False), (429, False), (503, True)):
            with self.subTest(status=status):
                exc = APIStatusError("Synthetic private provider prose.", status_code=status,
                                     body={"key": "-".join(("sk", "test...private-fragment"))})
                with patch.object(fallback_tts_module, "_safe_json") as render_body:
                    description = fallback_tts_module._describe_attempt(ProviderAttempt("primary", provider), exc)
                self.assertNotIn("-".join(("sk", "test...private-fragment")), description)
                render_body.assert_not_called()
                self.assertIn("primary", description)
                self.assertIn("voice_id=synthetic-voice", description)
                self.assertIn("error_class=APIStatusError", description)
                self.assertIn(f"status_code={status}", description)
                self.assertIn(f"retryable={retryable}", description)
# === VIVENTIUM END ===

if __name__ == "__main__":
    unittest.main()
