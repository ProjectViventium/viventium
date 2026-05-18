# === VIVENTIUM START ===
# Feature: Shared Silero VAD config tests
# Added: 2026-03-10
# Purpose:
# - Keep the Silero VAD env surface single-source-of-truth across worker.py and
#   the local whisper.cpp adapter.
# - Prove long-utterance protection is driven by VIVENTIUM_STT_VAD_MAX_BUFFERED_SPEECH.
# === VIVENTIUM END ===

import os
import sys
import unittest
from unittest import mock


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pywhispercpp_provider
from silero_vad_config import DEFAULT_MAX_BUFFERED_SPEECH, get_silero_vad_kwargs


class TestSileroVadConfig(unittest.TestCase):
    def test_defaults_include_longer_buffer(self) -> None:
        kwargs = get_silero_vad_kwargs({})

        self.assertEqual(kwargs["sample_rate"], 16000)
        self.assertEqual(kwargs["min_speech_duration"], 0.1)
        self.assertEqual(kwargs["min_silence_duration"], 0.5)
        self.assertEqual(kwargs["activation_threshold"], 0.4)
        self.assertEqual(kwargs["max_buffered_speech"], DEFAULT_MAX_BUFFERED_SPEECH)
        self.assertFalse(kwargs["force_cpu"])

    def test_invalid_buffer_uses_default(self) -> None:
        kwargs = get_silero_vad_kwargs(
            {"VIVENTIUM_STT_VAD_MAX_BUFFERED_SPEECH": "-1"}
        )

        self.assertEqual(kwargs["max_buffered_speech"], DEFAULT_MAX_BUFFERED_SPEECH)

    def test_env_override_is_applied(self) -> None:
        kwargs = get_silero_vad_kwargs(
            {
                "VIVENTIUM_STT_VAD_MIN_SPEECH": "0.25",
                "VIVENTIUM_STT_VAD_MIN_SILENCE": "1.2",
                "VIVENTIUM_STT_VAD_ACTIVATION": "0.6",
                "VIVENTIUM_STT_VAD_MAX_BUFFERED_SPEECH": "1800",
                "VIVENTIUM_STT_VAD_FORCE_CPU": "true",
            }
        )

        self.assertEqual(kwargs["min_speech_duration"], 0.25)
        self.assertEqual(kwargs["min_silence_duration"], 1.2)
        self.assertEqual(kwargs["activation_threshold"], 0.6)
        self.assertEqual(kwargs["max_buffered_speech"], 1800.0)
        self.assertTrue(kwargs["force_cpu"])


class TestPyWhisperCppProviderVadWiring(unittest.TestCase):
    def test_intel_defaults_use_smaller_local_model(self) -> None:
        with (
            mock.patch("pywhispercpp_provider.platform.machine", return_value="x86_64"),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            self.assertEqual(pywhispercpp_provider._default_model_name(), "small")

    def test_apple_silicon_defaults_use_best_local_model(self) -> None:
        with (
            mock.patch("pywhispercpp_provider.platform.machine", return_value="arm64"),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            self.assertEqual(pywhispercpp_provider._default_model_name(), "large-v3-turbo")

    def test_get_stt_uses_shared_vad_kwargs(self) -> None:
        expected_kwargs = {
            "sample_rate": 16000,
            "min_speech_duration": 0.35,
            "min_silence_duration": 0.5,
            "max_buffered_speech": 900.0,
            "activation_threshold": 0.4,
            "force_cpu": False,
        }

        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(
                pywhispercpp_provider,
                "PyWhisperCppSTT",
                return_value="fake-stt",
            ) as stt_cls,
            mock.patch.object(
                pywhispercpp_provider,
                "get_silero_vad_kwargs",
                return_value=expected_kwargs,
            ) as get_kwargs,
            mock.patch(
                "livekit.plugins.silero.VAD.load",
                return_value="fake-vad",
            ) as vad_load,
            mock.patch.object(
                pywhispercpp_provider,
                "StreamAdapter",
                return_value="fake-adapter",
            ) as adapter_cls,
        ):
            result = pywhispercpp_provider.get_stt()

        self.assertEqual(result, "fake-adapter")
        stt_cls.assert_called_once_with(language="en")
        get_kwargs.assert_called_once()
        vad_env = get_kwargs.call_args.args[0]
        self.assertEqual(vad_env["VIVENTIUM_STT_VAD_MIN_SPEECH"], "0.35")
        self.assertEqual(vad_env["VIVENTIUM_STT_VAD_MIN_SILENCE"], "0.5")
        vad_load.assert_called_once_with(**expected_kwargs)
        adapter_cls.assert_called_once_with(stt="fake-stt", vad="fake-vad")

    def test_local_whisper_vad_defaults_respect_explicit_overrides(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "VIVENTIUM_STT_VAD_MIN_SPEECH": "0.22",
                "VIVENTIUM_STT_VAD_MIN_SILENCE": "0.9",
            },
            clear=True,
        ):
            vad_env = pywhispercpp_provider._local_whisper_vad_env()

        self.assertEqual(vad_env["VIVENTIUM_STT_VAD_MIN_SPEECH"], "0.22")
        self.assertEqual(vad_env["VIVENTIUM_STT_VAD_MIN_SILENCE"], "0.9")

    def test_intel_default_threads_are_lowered(self) -> None:
        with (
            mock.patch("pywhispercpp_provider.platform.machine", return_value="x86_64"),
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(
                pywhispercpp_provider,
                "ensure_model_ready",
                return_value="/tmp/ggml-small.bin",
            ),
            mock.patch.object(pywhispercpp_provider, "Model", return_value="fake-model") as model_cls,
        ):
            pywhispercpp_provider._MODEL_CACHE.clear()
            pywhispercpp_provider._get_model()

        self.assertEqual(model_cls.call_args.kwargs["n_threads"], 2)
        pywhispercpp_provider._MODEL_CACHE.clear()


if __name__ == "__main__":
    unittest.main()
