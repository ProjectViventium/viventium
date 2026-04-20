"""Viventium MLX Chatterbox TTS adapter tests (lightweight, no model download)."""

# === VIVENTIUM START ===
# Feature: Local Chatterbox Turbo (MLX) provider tests
# Added: 2026-02-10
# Updated: 2026-02-11 (expanded: PCM conversion, generate params, empty input, config defaults)
#
# Scope:
# - Validate input normalization (strip Cartesia SSML emotion tags) without importing MLX.
# - Validate PCM conversion edge cases.
# - Validate generate() call forwards correct params (no misused sample_rate, correct tuning knobs).
# - Validate empty/whitespace input produces no audio.
# - Validate config defaults match tuned values.
# - Avoid any heavyweight model downloads in unit tests.
# === VIVENTIUM END ===

import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

import numpy as np

# Ensure voice-gateway root is on sys.path so `import mlx_chatterbox_tts` works
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mlx_chatterbox_tts import (
    MlxChatterboxConfig,
    MlxChatterboxTTS,
    _audio_to_pcm_s16le,
    _strip_cartesia_emotion_tags,
)


# ---------------------------------------------------------------------------
# Input normalization
# ---------------------------------------------------------------------------
class TestMlxChatterboxNormalization(unittest.TestCase):
    def test_strips_self_closing_emotion_tag(self) -> None:
        self.assertEqual(_strip_cartesia_emotion_tags('<emotion value="excited"/>Hello'), "Hello")

    def test_keeps_inner_text_for_wrapper_emotion_tag(self) -> None:
        self.assertEqual(
            _strip_cartesia_emotion_tags('<emotion value="sad">Oops</emotion>'),
            "Oops",
        )

    def test_strips_speak_wrapper(self) -> None:
        self.assertEqual(
            _strip_cartesia_emotion_tags("<speak>Hello</speak>"),
            "Hello",
        )

    def test_preserves_bracket_tags(self) -> None:
        text = "[sigh] Hello there."
        self.assertEqual(_strip_cartesia_emotion_tags(text), text)

    def test_empty_string(self) -> None:
        self.assertEqual(_strip_cartesia_emotion_tags(""), "")

    def test_none_returns_empty(self) -> None:
        self.assertEqual(_strip_cartesia_emotion_tags(None), "")

    def test_mixed_tags_and_text(self) -> None:
        text = '<speak><emotion value="happy">Hi!</emotion> [laugh] Bye</speak>'
        result = _strip_cartesia_emotion_tags(text)
        self.assertIn("Hi!", result)
        self.assertIn("[laugh]", result)
        self.assertIn("Bye", result)
        self.assertNotIn("<speak>", result)
        self.assertNotIn("<emotion", result)


# ---------------------------------------------------------------------------
# PCM conversion
# ---------------------------------------------------------------------------
class TestAudioToPcmS16le(unittest.TestCase):
    def test_none_returns_empty(self) -> None:
        self.assertEqual(_audio_to_pcm_s16le(None), b"")

    def test_empty_array_returns_empty(self) -> None:
        self.assertEqual(_audio_to_pcm_s16le(np.array([], dtype=np.float32)), b"")

    def test_single_sample(self) -> None:
        result = _audio_to_pcm_s16le(np.array([0.5], dtype=np.float32))
        expected = np.array([int(0.5 * 32767)], dtype="<i2").tobytes()
        self.assertEqual(result, expected)

    def test_clips_values_outside_range(self) -> None:
        result = _audio_to_pcm_s16le(np.array([2.0, -2.0], dtype=np.float32))
        expected = np.array([32767, -32767], dtype="<i2").tobytes()
        self.assertEqual(result, expected)

    def test_output_is_little_endian_16bit(self) -> None:
        result = _audio_to_pcm_s16le(np.array([0.1, -0.1], dtype=np.float32))
        self.assertEqual(len(result), 4)  # 2 samples * 2 bytes each

    def test_zero_sample(self) -> None:
        result = _audio_to_pcm_s16le(np.array([0.0], dtype=np.float32))
        expected = np.array([0], dtype="<i2").tobytes()
        self.assertEqual(result, expected)

    def test_boundary_values(self) -> None:
        result = _audio_to_pcm_s16le(np.array([1.0, -1.0], dtype=np.float32))
        expected = np.array([32767, -32767], dtype="<i2").tobytes()
        self.assertEqual(result, expected)


# ---------------------------------------------------------------------------
# Config defaults
# ---------------------------------------------------------------------------
class TestMlxChatterboxConfigDefaults(unittest.TestCase):
    def test_default_streaming_interval(self) -> None:
        config = MlxChatterboxConfig()
        self.assertEqual(config.streaming_interval_s, 1.0)

    def test_default_prebuffer(self) -> None:
        config = MlxChatterboxConfig()
        self.assertEqual(config.prebuffer_ms, 500.0)

    def test_default_temperature(self) -> None:
        config = MlxChatterboxConfig()
        self.assertEqual(config.temperature, 0.8)

    def test_default_repetition_penalty(self) -> None:
        config = MlxChatterboxConfig()
        self.assertEqual(config.repetition_penalty, 1.2)

    def test_default_sample_rate(self) -> None:
        config = MlxChatterboxConfig()
        self.assertEqual(config.sample_rate, 24000)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class _DummyEmitter:
    def __init__(self) -> None:
        self.initialize_calls: list[dict] = []
        self.push_calls: list[bytes] = []

    def initialize(self, **kwargs) -> None:
        self.initialize_calls.append(kwargs)

    def push(self, chunk: bytes) -> None:
        self.push_calls.append(chunk)


class _FakeModel:
    def generate(self, **_: object):
        yield SimpleNamespace(sample_rate=24000, audio=np.array([0.2, -0.1, 0.0], dtype=np.float32))


class _RecordingModel:
    """Records the kwargs passed to generate() for assertion."""
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate(self, **kwargs: object):
        self.calls.append(kwargs)
        yield SimpleNamespace(sample_rate=24000, audio=np.array([0.1, -0.1], dtype=np.float32))


class _MultiChunkModel:
    def generate(self, **_: object):
        yield SimpleNamespace(sample_rate=24000, audio=np.array([0.2, -0.1], dtype=np.float32))
        yield SimpleNamespace(sample_rate=24000, audio=np.array([0.4, -0.3], dtype=np.float32))


# ---------------------------------------------------------------------------
# Sample rate handling
# ---------------------------------------------------------------------------
class TestMlxChatterboxSampleRate(unittest.IsolatedAsyncioTestCase):
    async def test_uses_model_output_sample_rate_for_emitter(self) -> None:
        tts = MlxChatterboxTTS(
            config=MlxChatterboxConfig(
                model_id="fake-model",
                sample_rate=16000,
                stream=True,
                streaming_interval_s=0.05,
                prebuffer_ms=0.0,
            )
        )
        stream = tts.synthesize("hello")
        emitter = _DummyEmitter()

        with mock.patch("mlx_chatterbox_tts._load_mlx_model", return_value=_FakeModel()):
            await stream._run(emitter)

        self.assertEqual(len(emitter.initialize_calls), 1)
        self.assertEqual(emitter.initialize_calls[0].get("sample_rate"), 24000)
        self.assertGreater(len(emitter.push_calls), 0)


# ---------------------------------------------------------------------------
# generate() parameter forwarding
# ---------------------------------------------------------------------------
class TestMlxChatterboxGenerateParams(unittest.IsolatedAsyncioTestCase):
    async def test_does_not_pass_sample_rate_to_generate(self) -> None:
        """Upstream sample_rate param is for input ref_audio, not output. We must not send it."""
        recording = _RecordingModel()
        tts = MlxChatterboxTTS(
            config=MlxChatterboxConfig(
                model_id="fake-model",
                sample_rate=16000,
                stream=True,
                streaming_interval_s=0.5,
                prebuffer_ms=0.0,
                temperature=0.9,
                repetition_penalty=1.3,
            )
        )
        stream = tts.synthesize("hello world")
        emitter = _DummyEmitter()

        with mock.patch("mlx_chatterbox_tts._load_mlx_model", return_value=recording):
            await stream._run(emitter)

        # LiveKit SDK may also invoke _run via an internal task, so there can be >1 call.
        # Validate ALL calls forward the correct params and never include sample_rate.
        self.assertGreaterEqual(len(recording.calls), 1)
        for call_kwargs in recording.calls:
            # Must NOT contain sample_rate (it's an input-audio param, not output control)
            self.assertNotIn("sample_rate", call_kwargs)
            # Must contain the correct generation tuning params
            self.assertAlmostEqual(call_kwargs["temperature"], 0.9)
            self.assertAlmostEqual(call_kwargs["repetition_penalty"], 1.3)
            self.assertEqual(call_kwargs["stream"], True)
            self.assertAlmostEqual(call_kwargs["streaming_interval"], 0.5)

    async def test_forwards_ref_audio(self) -> None:
        recording = _RecordingModel()
        tts = MlxChatterboxTTS(
            config=MlxChatterboxConfig(
                model_id="fake-model",
                prebuffer_ms=0.0,
                ref_audio="/tmp/test_ref.wav",
            )
        )
        stream = tts.synthesize("test")
        emitter = _DummyEmitter()

        with mock.patch("mlx_chatterbox_tts._load_mlx_model", return_value=recording):
            await stream._run(emitter)

        self.assertEqual(recording.calls[0]["ref_audio"], "/tmp/test_ref.wav")


# ---------------------------------------------------------------------------
# Empty / whitespace input
# ---------------------------------------------------------------------------
class TestMlxChatterboxEmptyInput(unittest.IsolatedAsyncioTestCase):
    async def test_empty_text_produces_no_audio(self) -> None:
        tts = MlxChatterboxTTS(
            config=MlxChatterboxConfig(model_id="fake-model", prebuffer_ms=0.0)
        )
        stream = tts.synthesize("")
        emitter = _DummyEmitter()

        with mock.patch("mlx_chatterbox_tts._load_mlx_model", return_value=_FakeModel()):
            await stream._run(emitter)

        self.assertEqual(len(emitter.push_calls), 0)
        # Empty inputs should initialize the emitter so LiveKit can safely finalize the stream.
        self.assertEqual(len(emitter.initialize_calls), 1)

    async def test_emits_all_generated_chunks_without_dropping_tail_audio(self) -> None:
        tts = MlxChatterboxTTS(
            config=MlxChatterboxConfig(
                model_id="fake-model",
                stream=True,
                streaming_interval_s=0.05,
                prebuffer_ms=0.0,
            )
        )
        stream = tts.synthesize("hello world")
        emitter = _DummyEmitter()

        with mock.patch("mlx_chatterbox_tts._load_mlx_model", return_value=_MultiChunkModel()):
            await stream._run(emitter)

        self.assertEqual(len(emitter.initialize_calls), 1)
        self.assertEqual(len(emitter.push_calls), 2)
        self.assertEqual(
            b"".join(emitter.push_calls),
            _audio_to_pcm_s16le(np.array([0.2, -0.1, 0.4, -0.3], dtype=np.float32)),
        )

    async def test_whitespace_only_produces_no_audio(self) -> None:
        tts = MlxChatterboxTTS(
            config=MlxChatterboxConfig(model_id="fake-model", prebuffer_ms=0.0)
        )
        stream = tts.synthesize("   \n\t  ")
        emitter = _DummyEmitter()

        with mock.patch("mlx_chatterbox_tts._load_mlx_model", return_value=_FakeModel()):
            await stream._run(emitter)

        self.assertEqual(len(emitter.push_calls), 0)
        self.assertEqual(len(emitter.initialize_calls), 1)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
class TestMlxChatterboxErrorHandling(unittest.IsolatedAsyncioTestCase):
    async def test_model_load_failure_raises_api_error(self) -> None:
        from livekit.agents import APIError

        tts = MlxChatterboxTTS(
            config=MlxChatterboxConfig(model_id="bad-model", prebuffer_ms=0.0)
        )
        stream = tts.synthesize("hello")
        emitter = _DummyEmitter()

        with mock.patch(
            "mlx_chatterbox_tts._load_mlx_model",
            side_effect=RuntimeError("model load failed"),
        ):
            with self.assertRaises(APIError):
                await stream._run(emitter)


if __name__ == "__main__":
    unittest.main()
