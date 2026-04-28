import inspect
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worker import (
    _apply_requested_voice_route,
    _build_assemblyai_stt_kwargs,
    _build_voice_capability_catalog,
    _turn_detector_model_is_cached,
    build_stt_selection,
    load_env,
    load_turn_detection,
    optional_module_available,
)


class TestWorkerTurnHandling(unittest.TestCase):
    def test_optional_module_available_handles_missing_parent_package(self) -> None:
        with patch(
            "worker.importlib.util.find_spec",
            side_effect=ModuleNotFoundError("No module named 'livekit.plugins.turn_detector'"),
        ):
            self.assertFalse(optional_module_available("livekit.plugins.turn_detector.multilingual"))

    def test_load_env_defaults_to_stt_for_assemblyai_when_turn_detector_missing(self) -> None:
        with (
            patch.dict(os.environ, {"VIVENTIUM_STT_PROVIDER": "assemblyai"}, clear=True),
            patch("worker.HAS_TURN_DETECTOR", False),
        ):
            env = load_env()

        self.assertEqual(env.voice_turn_detection, "stt")
        self.assertEqual(env.voice_min_endpointing_delay_s, 0.0)
        self.assertEqual(env.voice_max_endpointing_delay_s, 1.8)
        self.assertEqual(env.voice_min_interruption_words, 1)
        self.assertEqual(env.voice_false_interruption_timeout_s, 2.0)
        self.assertTrue(env.voice_resume_false_interruption)
        self.assertEqual(env.voice_min_consecutive_speech_delay_s, 0.2)
        self.assertIsNone(env.assemblyai_min_end_of_turn_silence_when_confident_ms)
        self.assertIsNone(env.assemblyai_max_turn_silence_ms)

    def test_load_env_keeps_stt_default_for_assemblyai_when_turn_detector_is_available(self) -> None:
        with (
            patch.dict(os.environ, {"VIVENTIUM_STT_PROVIDER": "assemblyai"}, clear=True),
            patch("worker.HAS_TURN_DETECTOR", True),
        ):
            env = load_env()

        self.assertEqual(env.voice_turn_detection, "stt")
        self.assertEqual(env.voice_min_endpointing_delay_s, 0.0)
        self.assertEqual(env.voice_max_endpointing_delay_s, 1.8)

    def test_load_env_respects_explicit_turn_detector_override(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIVENTIUM_STT_PROVIDER": "assemblyai",
                "VIVENTIUM_TURN_DETECTION": "turn_detector",
            },
            clear=True,
        ):
            env = load_env()

        self.assertEqual(env.voice_turn_detection, "turn_detector")
        self.assertEqual(env.voice_min_endpointing_delay_s, 0.35)
        self.assertEqual(env.voice_max_endpointing_delay_s, 1.8)

    def test_load_env_respects_turn_handling_overrides(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIVENTIUM_STT_PROVIDER": "assemblyai",
                "VIVENTIUM_TURN_DETECTION": "stt",
                "VIVENTIUM_VOICE_MIN_INTERRUPTION_WORDS": "3",
                "VIVENTIUM_VOICE_FALSE_INTERRUPTION_TIMEOUT_S": "off",
                "VIVENTIUM_VOICE_RESUME_FALSE_INTERRUPTION": "false",
                "VIVENTIUM_VOICE_MIN_CONSECUTIVE_SPEECH_DELAY_S": "0.45",
                "VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD": "0.33",
                "VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS": "220",
                "VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS": "1500",
                "VIVENTIUM_ASSEMBLYAI_FORMAT_TURNS": "true",
            },
            clear=True,
        ):
            env = load_env()

        self.assertEqual(env.voice_turn_detection, "stt")
        self.assertEqual(env.voice_min_interruption_words, 3)
        self.assertIsNone(env.voice_false_interruption_timeout_s)
        self.assertFalse(env.voice_resume_false_interruption)
        self.assertEqual(env.voice_min_consecutive_speech_delay_s, 0.45)
        self.assertEqual(env.assemblyai_end_of_turn_confidence_threshold, 0.33)
        self.assertEqual(env.assemblyai_min_end_of_turn_silence_when_confident_ms, 220)
        self.assertEqual(env.assemblyai_max_turn_silence_ms, 1500)
        self.assertTrue(env.assemblyai_format_turns)

    def test_requested_assemblyai_override_recomputes_turn_profile_from_local_default(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "VIVENTIUM_STT_PROVIDER": "whisper_local",
                    "ASSEMBLYAI_API_KEY": "assemblyai-test",
                },
                clear=True,
            ),
            patch("worker.HAS_ASSEMBLYAI", True),
        ):
            env = load_env()
            capabilities = _build_voice_capability_catalog(env)
            updated = _apply_requested_voice_route(
                env,
                {"stt": {"provider": "assemblyai", "variant": "universal-streaming"}},
                capabilities,
            )

        self.assertEqual(updated.stt_provider, "assemblyai")
        self.assertEqual(updated.voice_turn_detection, "stt")
        self.assertEqual(updated.voice_min_endpointing_delay_s, 0.0)
        self.assertEqual(updated.voice_max_endpointing_delay_s, 1.8)
        self.assertEqual(updated.voice_min_interruption_words, 1)
        self.assertEqual(updated.voice_min_consecutive_speech_delay_s, 0.2)

    def test_requested_local_override_recomputes_turn_profile_from_assemblyai_default(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "VIVENTIUM_STT_PROVIDER": "assemblyai",
                    "ASSEMBLYAI_API_KEY": "assemblyai-test",
                },
                clear=True,
            ),
            patch("worker.HAS_ASSEMBLYAI", True),
        ):
            env = load_env()
            capabilities = _build_voice_capability_catalog(env)
            updated = _apply_requested_voice_route(
                env,
                {"stt": {"provider": "pywhispercpp", "variant": "tiny.en"}},
                capabilities,
            )

        self.assertEqual(updated.stt_provider, "pywhispercpp")
        self.assertEqual(updated.stt_model, "tiny.en")
        self.assertEqual(updated.voice_turn_detection, "vad")
        self.assertEqual(updated.voice_min_endpointing_delay_s, 0.9)
        self.assertEqual(updated.voice_max_endpointing_delay_s, 3.0)
        self.assertEqual(updated.voice_min_interruption_words, 0)
        self.assertEqual(updated.voice_min_consecutive_speech_delay_s, 0.0)

    def test_load_env_raises_memory_warning_threshold_for_local_voice_route(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIVENTIUM_STT_PROVIDER": "whisper_local",
                "VIVENTIUM_TTS_PROVIDER": "local_chatterbox_turbo_mlx_8bit",
            },
            clear=True,
        ):
            env = load_env()

        self.assertEqual(env.voice_job_memory_warn_mb, 1400.0)
        self.assertEqual(env.voice_job_memory_limit_mb, 0.0)

    def test_load_env_respects_memory_warning_overrides(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIVENTIUM_STT_PROVIDER": "whisper_local",
                "VIVENTIUM_TTS_PROVIDER": "local_chatterbox_turbo_mlx_8bit",
                "VIVENTIUM_VOICE_JOB_MEMORY_WARN_MB": "1600",
                "VIVENTIUM_VOICE_JOB_MEMORY_LIMIT_MB": "2200",
            },
            clear=True,
        ):
            env = load_env()

        self.assertEqual(env.voice_job_memory_warn_mb, 1600.0)
        self.assertEqual(env.voice_job_memory_limit_mb, 2200.0)

    def test_build_assemblyai_stt_kwargs_only_includes_configured_values(self) -> None:
        env = SimpleNamespace(
            assemblyai_end_of_turn_confidence_threshold=0.27,
            assemblyai_min_end_of_turn_silence_when_confident_ms=210,
            assemblyai_max_turn_silence_ms=1300,
            assemblyai_format_turns=True,
        )

        self.assertEqual(
            _build_assemblyai_stt_kwargs(env),
            {
                "end_of_turn_confidence_threshold": 0.27,
                "min_turn_silence": 210,
                "max_turn_silence": 1300,
                "format_turns": True,
            },
        )

    def test_build_stt_selection_passes_assemblyai_turn_kwargs(self) -> None:
        env = SimpleNamespace(
            stt_provider="assemblyai",
            assemblyai_end_of_turn_confidence_threshold=0.29,
            assemblyai_min_end_of_turn_silence_when_confident_ms=190,
            assemblyai_max_turn_silence_ms=1250,
            assemblyai_format_turns=False,
        )

        with (
            patch("worker.HAS_ASSEMBLYAI", True),
            patch.dict(os.environ, {"ASSEMBLYAI_API_KEY": "assemblyai-test"}, clear=False),
            patch("worker.assemblyai_stt.STT", return_value="assemblyai-stt") as stt_cls,
        ):
            stt_impl, provider = build_stt_selection(env, vad=object())

        self.assertEqual(stt_impl, "assemblyai-stt")
        self.assertEqual(provider, "assemblyai")
        stt_cls.assert_called_once_with(
            end_of_turn_confidence_threshold=0.29,
            min_turn_silence=190,
            max_turn_silence=1250,
        )

    def test_load_turn_detection_returns_turn_detector_when_available(self) -> None:
        env = SimpleNamespace(voice_turn_detection="turn_detector", stt_provider="assemblyai")

        with (
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=True),
            patch("worker._load_turn_detector_model_class", return_value=lambda: "semantic-detector"),
        ):
            turn_detection, reason = load_turn_detection(env, has_vad=True)

        self.assertEqual(turn_detection, "semantic-detector")
        self.assertEqual(reason, "semantic_turn_detector")

    def test_load_turn_detection_falls_back_to_stt_when_turn_detector_weights_missing(self) -> None:
        env = SimpleNamespace(voice_turn_detection="turn_detector", stt_provider="assemblyai")

        with (
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=False),
            patch("worker._load_turn_detector_model_class") as detector_cls,
        ):
            turn_detection, reason = load_turn_detection(env, has_vad=True)

        detector_cls.assert_not_called()
        self.assertEqual(turn_detection, "stt")
        self.assertEqual(reason, "stt_end_of_turn")

    def test_load_turn_detection_falls_back_to_stt_when_turn_detector_missing(self) -> None:
        env = SimpleNamespace(voice_turn_detection="turn_detector", stt_provider="assemblyai")

        with patch("worker.HAS_TURN_DETECTOR", False):
            turn_detection, reason = load_turn_detection(env, has_vad=True)

        self.assertEqual(turn_detection, "stt")
        self.assertEqual(reason, "stt_end_of_turn")

    def test_installed_agents_sdk_accepts_interruption_kwargs(self) -> None:
        from livekit.agents import AgentSession

        params = inspect.signature(AgentSession.__init__).parameters

        for name in (
            "min_interruption_words",
            "false_interruption_timeout",
            "resume_false_interruption",
            "min_consecutive_speech_delay",
        ):
            self.assertIn(name, params)

    def test_turn_detector_model_cache_check_looks_for_exact_assets(self) -> None:
        manifest = {
            "repo_id": "livekit/turn-detector",
            "revision": "v0.4.1-intl",
            "onnx_filename": "model_q8.onnx",
        }

        with (
            patch("worker._get_turn_detector_cache_manifest", return_value=manifest),
            patch("huggingface_hub.hf_hub_download", side_effect=["/tmp/model_q8.onnx", "/tmp/languages.json"]) as download,
        ):
            self.assertTrue(_turn_detector_model_is_cached())

        self.assertEqual(download.call_count, 2)

    def test_turn_detector_model_cache_check_returns_false_when_exact_assets_missing(self) -> None:
        manifest = {
            "repo_id": "livekit/turn-detector",
            "revision": "v0.4.1-intl",
            "onnx_filename": "model_q8.onnx",
        }

        with (
            patch("worker._get_turn_detector_cache_manifest", return_value=manifest),
            patch("huggingface_hub.hf_hub_download", side_effect=OSError("missing")),
        ):
            self.assertFalse(_turn_detector_model_is_cached())


if __name__ == "__main__":
    unittest.main()
