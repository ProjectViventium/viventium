"""Viventium voice-gateway TTS fallback tests."""

# === VIVENTIUM START ===
# Feature: Fallback TTS wrapper tests
# Added: 2026-02-06
# === VIVENTIUM END ===

import os
import sys
import unittest
from unittest.mock import patch

from livekit.agents import APIError
from livekit.agents.tts import AudioEmitter, ChunkedStream, SynthesizeStream, TTS, TTSCapabilities

# Ensure voice-gateway root is on sys.path so `import fallback_tts` works
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fallback_tts import FallbackTTS, ProviderAttempt  # noqa: E402


def _silence_pcm(*, sample_rate: int, num_channels: int, duration_ms: int) -> bytes:
    samples_per_channel = int(sample_rate * (duration_ms / 1000.0))
    total_samples = samples_per_channel * num_channels
    return b"\x00\x00" * total_samples  # pcm_s16le silence


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


if __name__ == "__main__":
    unittest.main()
