import inspect
import os
import sys
import tempfile
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worker import (
    _apply_requested_voice_route,
    _attach_room_diagnostics,
    _build_assemblyai_stt_kwargs,
    _build_voice_capability_catalog,
    _ensure_turn_detector_runner_registered,
    _semantic_turn_detector_status,
    _silero_vad_kwargs_for_env,
    _supports_semantic_turn_detector,
    _turn_detector_model_is_cached,
    _turn_detector_runner_registered,
    _vad_kwargs_cache_key,
    _active_voice_job_markers,
    _clear_active_voice_job_marker,
    _mark_active_voice_job,
    _voice_sync_transcription_enabled,
    build_stt_selection,
    load_env,
    load_turn_detection,
    optional_module_available,
)


class TestWorkerTurnHandling(unittest.TestCase):
    def test_active_voice_job_markers_are_process_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(
                os.environ,
                {
                    "TMPDIR": tmp_dir,
                    "VIVENTIUM_VOICE_WORKER_RUN_ID": "test-run",
                },
                clear=False,
            ):
                marker = _mark_active_voice_job("job-1")
                self.assertIn(marker, _active_voice_job_markers())
                _clear_active_voice_job_marker(marker)
                self.assertEqual(_active_voice_job_markers(), [])

    def test_room_participant_disconnect_does_not_clear_active_marker(self) -> None:
        class FakeRoom:
            name = "room"

            def __init__(self) -> None:
                self.handlers = {}
                self.remote_participants = {"owner": object()}

            def on(self, event_name):
                def _register(handler):
                    self.handlers[event_name] = handler
                    return handler

                return _register

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(
                os.environ,
                {
                    "TMPDIR": tmp_dir,
                    "VIVENTIUM_VOICE_WORKER_RUN_ID": "test-run",
                },
                clear=False,
            ):
                marker = _mark_active_voice_job("job-1")
                room = FakeRoom()
                ctx = SimpleNamespace(room=room)
                participant = SimpleNamespace(identity="observer")

                _attach_room_diagnostics(
                    ctx,
                    call_session_id="test-call",
                    active_job_marker=marker,
                )
                room.handlers["participant_disconnected"](participant)

                self.assertIn(marker, _active_voice_job_markers())
                _clear_active_voice_job_marker(marker)

    def test_room_empty_participant_disconnect_clears_active_marker(self) -> None:
        class FakeRoom:
            name = "room"

            def __init__(self) -> None:
                self.handlers = {}
                self.remote_participants = {}

            def on(self, event_name):
                def _register(handler):
                    self.handlers[event_name] = handler
                    return handler

                return _register

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(
                os.environ,
                {
                    "TMPDIR": tmp_dir,
                    "VIVENTIUM_VOICE_WORKER_RUN_ID": "test-run",
                },
                clear=False,
            ):
                marker = _mark_active_voice_job("job-1")
                room = FakeRoom()
                ctx = SimpleNamespace(room=room)
                participant = SimpleNamespace(identity="owner")

                _attach_room_diagnostics(
                    ctx,
                    call_session_id="test-call",
                    active_job_marker=marker,
                )
                room.handlers["participant_disconnected"](participant)

                self.assertNotIn(marker, _active_voice_job_markers())

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
        self.assertEqual(env.voice_aec_warmup_duration_s, 3.0)
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
        with (
            patch.dict(
                os.environ,
                {
                    "VIVENTIUM_STT_PROVIDER": "assemblyai",
                    "VIVENTIUM_TURN_DETECTION": "turn_detector",
                },
                clear=True,
            ),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=True),
            patch("worker._ensure_turn_detector_runner_registered", return_value=True),
        ):
            env = load_env()

        self.assertEqual(env.voice_turn_detection, "turn_detector")
        self.assertEqual(env.voice_min_endpointing_delay_s, 0.35)
        self.assertEqual(env.voice_max_endpointing_delay_s, 1.8)
        self.assertEqual(env.voice_min_interruption_words, 1)

    def test_explicit_turn_detector_falls_back_to_aligned_profile_when_uncached(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "VIVENTIUM_STT_PROVIDER": "assemblyai",
                    "VIVENTIUM_TURN_DETECTION": "turn_detector",
                },
                clear=True,
            ),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=False),
            patch("worker._ensure_turn_detector_runner_registered", return_value=False),
        ):
            env = load_env()

        self.assertEqual(env.voice_turn_detection, "stt")
        self.assertEqual(env.voice_min_endpointing_delay_s, 0.0)
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
                "VIVENTIUM_VOICE_AEC_WARMUP_DURATION_S": "0.75",
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
        self.assertEqual(env.voice_aec_warmup_duration_s, 0.75)
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
                {"stt": {"provider": "assemblyai", "variant": "u3-rt-pro"}},
                capabilities,
            )

        self.assertEqual(updated.stt_provider, "assemblyai")
        self.assertEqual(updated.voice_turn_detection, "stt")
        self.assertEqual(updated.voice_min_endpointing_delay_s, 0.0)
        self.assertEqual(updated.voice_max_endpointing_delay_s, 1.8)
        self.assertEqual(updated.voice_min_interruption_words, 1)
        self.assertEqual(updated.voice_min_consecutive_speech_delay_s, 0.2)
        self.assertEqual(_silero_vad_kwargs_for_env(updated)["min_silence_duration"], 0.5)

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
            patch("worker._turn_detector_model_is_cached", return_value=False),
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
        self.assertEqual(updated.voice_min_endpointing_delay_s, 0.5)
        self.assertEqual(updated.voice_max_endpointing_delay_s, 3.0)
        self.assertEqual(updated.voice_min_interruption_words, 0)
        self.assertEqual(updated.voice_min_consecutive_speech_delay_s, 0.0)

    def test_local_whisper_uses_semantic_turn_detector_when_cached(self) -> None:
        with (
            patch.dict(os.environ, {"VIVENTIUM_STT_PROVIDER": "whisper_local"}, clear=True),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=True),
            patch("worker._ensure_turn_detector_runner_registered", return_value=True),
        ):
            env = load_env()

        self.assertTrue(_supports_semantic_turn_detector("whisper_local"))
        self.assertTrue(_supports_semantic_turn_detector("pywhispercpp"))
        self.assertEqual(env.voice_turn_detection, "turn_detector")
        self.assertEqual(env.voice_min_endpointing_delay_s, 0.35)
        self.assertEqual(env.voice_max_endpointing_delay_s, 1.8)
        self.assertEqual(env.voice_min_interruption_words, 0)
        self.assertEqual(env.voice_min_consecutive_speech_delay_s, 0.2)
        self.assertEqual(env.voice_aec_warmup_duration_s, 1.0)

    def test_local_whisper_semantic_turn_detector_respects_explicit_min_words_override(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "VIVENTIUM_STT_PROVIDER": "whisper_local",
                    "VIVENTIUM_VOICE_MIN_INTERRUPTION_WORDS": "2",
                },
                clear=True,
            ),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=True),
            patch("worker._ensure_turn_detector_runner_registered", return_value=True),
        ):
            env = load_env()

        self.assertEqual(env.voice_turn_detection, "turn_detector")
        self.assertEqual(env.voice_min_interruption_words, 2)

    def test_local_whisper_falls_back_to_vad_when_runner_is_not_registered(self) -> None:
        with (
            patch.dict(os.environ, {"VIVENTIUM_STT_PROVIDER": "whisper_local"}, clear=True),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=True),
            patch("worker._ensure_turn_detector_runner_registered", return_value=False),
        ):
            env = load_env()

        self.assertEqual(env.voice_turn_detection, "vad")
        self.assertEqual(env.voice_min_endpointing_delay_s, 0.5)
        self.assertEqual(env.voice_max_endpointing_delay_s, 3.0)
        self.assertEqual(env.voice_min_interruption_words, 0)
        self.assertEqual(env.voice_aec_warmup_duration_s, 1.0)

    def test_local_whisper_uncached_fallback_uses_less_eager_vad(self) -> None:
        with (
            patch.dict(os.environ, {"VIVENTIUM_STT_PROVIDER": "whisper_local"}, clear=True),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=False),
            patch("worker._ensure_turn_detector_runner_registered", return_value=False),
        ):
            env = load_env()

        self.assertEqual(env.voice_turn_detection, "vad")
        self.assertEqual(env.voice_min_endpointing_delay_s, 0.5)
        self.assertEqual(env.voice_max_endpointing_delay_s, 3.0)
        self.assertEqual(_silero_vad_kwargs_for_env(env)["min_speech_duration"], 0.35)
        self.assertEqual(_silero_vad_kwargs_for_env(env)["min_silence_duration"], 0.5)

    def test_local_whisper_respects_explicit_vad_min_speech_override(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "VIVENTIUM_STT_PROVIDER": "whisper_local",
                    "VIVENTIUM_STT_VAD_MIN_SPEECH": "0.22",
                },
                clear=True,
            ),
            patch("worker._turn_detector_model_is_cached", return_value=False),
        ):
            env = load_env()
            vad_kwargs = _silero_vad_kwargs_for_env(env)

        self.assertEqual(vad_kwargs["min_speech_duration"], 0.22)

    def test_local_whisper_respects_explicit_vad_min_silence_override(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "VIVENTIUM_STT_PROVIDER": "whisper_local",
                    "VIVENTIUM_STT_VAD_MIN_SILENCE": "0.72",
                },
                clear=True,
            ),
            patch("worker._turn_detector_model_is_cached", return_value=False),
        ):
            env = load_env()
            vad_kwargs = _silero_vad_kwargs_for_env(env)

        self.assertEqual(vad_kwargs["min_silence_duration"], 0.72)

    def test_vad_kwargs_cache_key_changes_when_requested_route_changes_vad_timing(self) -> None:
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
            patch("worker._turn_detector_model_is_cached", return_value=False),
        ):
            env = load_env()
            local_key = _vad_kwargs_cache_key(_silero_vad_kwargs_for_env(env))
            capabilities = _build_voice_capability_catalog(env)
            updated = _apply_requested_voice_route(
                env,
                {"stt": {"provider": "assemblyai", "variant": "u3-rt-pro"}},
                capabilities,
            )
            assemblyai_key = _vad_kwargs_cache_key(_silero_vad_kwargs_for_env(updated))

        self.assertEqual(env.voice_turn_detection, "vad")
        self.assertEqual(_silero_vad_kwargs_for_env(env)["min_speech_duration"], 0.35)
        self.assertEqual(_silero_vad_kwargs_for_env(env)["min_silence_duration"], 0.5)
        self.assertEqual(updated.voice_turn_detection, "stt")
        self.assertEqual(_silero_vad_kwargs_for_env(updated)["min_speech_duration"], 0.1)
        self.assertEqual(_silero_vad_kwargs_for_env(updated)["min_silence_duration"], 0.5)
        self.assertNotEqual(local_key, assemblyai_key)

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

        self.assertEqual(env.voice_job_memory_warn_mb, 2200.0)
        self.assertEqual(env.voice_job_memory_limit_mb, 0.0)

    def test_load_env_keeps_chatterbox_only_memory_warning_threshold(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIVENTIUM_STT_PROVIDER": "assemblyai",
                "VIVENTIUM_TTS_PROVIDER": "local_chatterbox_turbo_mlx_8bit",
            },
            clear=True,
        ):
            env = load_env()

        self.assertEqual(env.voice_job_memory_warn_mb, 1400.0)

    def test_load_env_keeps_hosted_voice_memory_warning_threshold(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIVENTIUM_STT_PROVIDER": "assemblyai",
                "VIVENTIUM_TTS_PROVIDER": "openai",
            },
            clear=True,
        ):
            env = load_env()

        self.assertEqual(env.voice_job_memory_warn_mb, 500.0)

    def test_local_whisper_defaults_tts_prewarm_off_to_protect_stt_latency(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIVENTIUM_STT_PROVIDER": "whisper_local",
                "VIVENTIUM_TTS_PROVIDER": "local_chatterbox_turbo_mlx_8bit",
            },
            clear=True,
        ):
            env = load_env()

        self.assertFalse(env.voice_prewarm_local_tts)

    def test_local_whisper_respects_explicit_tts_prewarm_override(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIVENTIUM_STT_PROVIDER": "whisper_local",
                "VIVENTIUM_TTS_PROVIDER": "local_chatterbox_turbo_mlx_8bit",
                "VIVENTIUM_VOICE_PREWARM_LOCAL_TTS": "true",
            },
            clear=True,
        ):
            env = load_env()

        self.assertTrue(env.voice_prewarm_local_tts)

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

    def test_build_assemblyai_stt_kwargs_includes_model_and_configured_values(self) -> None:
        # The engine model is always passed (the selectable Listening picker depends on it); the
        # optional endpointing knobs are still only included when configured.
        env = SimpleNamespace(
            assemblyai_stt_model="universal-streaming-multilingual",
            assemblyai_end_of_turn_confidence_threshold=0.27,
            assemblyai_min_end_of_turn_silence_when_confident_ms=210,
            assemblyai_max_turn_silence_ms=1300,
            assemblyai_format_turns=True,
        )

        self.assertEqual(
            _build_assemblyai_stt_kwargs(env),
            {
                "model": "universal-streaming-multilingual",
                "end_of_turn_confidence_threshold": 0.27,
                "min_turn_silence": 210,
                "max_turn_silence": 1300,
                "format_turns": True,
            },
        )

    def test_build_stt_selection_passes_assemblyai_turn_kwargs(self) -> None:
        env = SimpleNamespace(
            stt_provider="assemblyai",
            assemblyai_stt_model="u3-rt-pro",
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
            model="u3-rt-pro",
            end_of_turn_confidence_threshold=0.29,
            min_turn_silence=190,
            max_turn_silence=1250,
        )

    def test_local_whisper_selection_fails_honestly_without_openai_fallback(self) -> None:
        fake_pywhispercpp_provider = types.ModuleType("pywhispercpp_provider")

        def _fail_get_stt(*_args, **_kwargs):
            raise RuntimeError("selected model is corrupt")

        fake_pywhispercpp_provider.get_stt = _fail_get_stt
        env = SimpleNamespace(
            stt_provider="whisper_local",
            stt_model="large-v3-turbo",
            stt_language="en",
        )

        with (
            patch.dict(sys.modules, {"pywhispercpp_provider": fake_pywhispercpp_provider}),
            patch("worker.openai.STT", side_effect=AssertionError("OpenAI fallback must not run")),
        ):
            with self.assertRaisesRegex(RuntimeError, "will not silently switch"):
                build_stt_selection(env, vad=object())

    def test_load_turn_detection_returns_turn_detector_when_available(self) -> None:
        env = SimpleNamespace(voice_turn_detection="turn_detector", stt_provider="assemblyai")

        with (
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=True),
            patch("worker._ensure_turn_detector_runner_registered", return_value=True),
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
            patch("worker._ensure_turn_detector_runner_registered", return_value=False),
            patch("worker._load_turn_detector_model_class") as detector_cls,
        ):
            turn_detection, reason = load_turn_detection(env, has_vad=True)

        detector_cls.assert_not_called()
        self.assertEqual(turn_detection, "stt")
        self.assertEqual(reason, "stt_end_of_turn")

    def test_load_turn_detection_falls_back_to_vad_for_local_stt_when_runner_missing(self) -> None:
        env = SimpleNamespace(voice_turn_detection="turn_detector", stt_provider="pywhispercpp")

        with (
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=True),
            patch("worker._ensure_turn_detector_runner_registered", return_value=False),
            patch("worker._load_turn_detector_model_class") as detector_cls,
        ):
            turn_detection, reason = load_turn_detection(env, has_vad=True)

        detector_cls.assert_not_called()
        self.assertEqual(turn_detection, "vad")
        self.assertEqual(reason, "vad_silence")

    def test_semantic_turn_detector_status_requires_registered_local_runner(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=True),
            patch("worker._ensure_turn_detector_runner_registered", return_value=False),
        ):
            self.assertEqual(
                _semantic_turn_detector_status("pywhispercpp"),
                (False, "local_inference_runner_unregistered"),
            )

    def test_semantic_turn_detector_status_allows_remote_inference(self) -> None:
        with (
            patch.dict(os.environ, {"LIVEKIT_REMOTE_EOT_URL": "https://example.invalid/eot"}, clear=True),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=False),
        ):
            self.assertEqual(
                _semantic_turn_detector_status("pywhispercpp"),
                (True, "remote_inference"),
            )

    def test_turn_detector_runner_registration_does_not_import_when_assets_missing(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=False),
            patch("builtins.__import__") as import_fn,
        ):
            self.assertFalse(_ensure_turn_detector_runner_registered())

        import_fn.assert_not_called()

    def test_turn_detector_runner_registration_imports_multilingual_plugin(self) -> None:
        registered_runners = {}
        FakeInferenceRunner = type(
            "FakeInferenceRunner",
            (),
            {"registered_runners": registered_runners},
        )

        def fake_import(name: str, *args, **kwargs):
            if name == "livekit.agents.inference_runner":
                return SimpleNamespace(_InferenceRunner=FakeInferenceRunner)
            if name == "livekit.plugins.turn_detector.multilingual":
                registered_runners["lk_end_of_utterance_multilingual"] = object()
                return SimpleNamespace()
            raise ImportError(name)

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=True),
            patch("builtins.__import__", side_effect=fake_import),
        ):
            self.assertFalse(_turn_detector_runner_registered())
            self.assertTrue(_ensure_turn_detector_runner_registered())
            self.assertTrue(_turn_detector_runner_registered())

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
            "aec_warmup_duration",
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
            patch(
                "huggingface_hub.hf_hub_download",
                side_effect=[
                    "/tmp/model_q8.onnx",
                    "/tmp/config.json",
                    "/tmp/languages.json",
                    "/tmp/special_tokens_map.json",
                    "/tmp/tokenizer.json",
                    "/tmp/tokenizer_config.json",
                ],
            ) as download,
        ):
            self.assertTrue(_turn_detector_model_is_cached())

        self.assertEqual(download.call_count, 6)

    def test_turn_detector_model_cache_check_rejects_partial_snapshot(self) -> None:
        manifest = {
            "repo_id": "livekit/turn-detector",
            "revision": "v0.4.1-intl",
            "onnx_filename": "model_q8.onnx",
        }

        with (
            patch("worker._get_turn_detector_cache_manifest", return_value=manifest),
            patch(
                "huggingface_hub.hf_hub_download",
                side_effect=[
                    "/tmp/model_q8.onnx",
                    OSError("missing tokenizer config"),
                ],
            ),
        ):
            self.assertFalse(_turn_detector_model_is_cached())

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

    def test_voice_sync_transcription_defaults_to_fast_async_display(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(_voice_sync_transcription_enabled())

        with patch.dict(os.environ, {"VIVENTIUM_VOICE_SYNC_TRANSCRIPTION": "1"}, clear=True):
            self.assertTrue(_voice_sync_transcription_enabled())

    def test_pinned_livekit_word_tokenizer_preserves_spacing_for_synced_transcripts(self) -> None:
        from livekit.agents import tokenize

        tokenizer = tokenize.basic.WordTokenizer(
            retain_format=True,
            ignore_punctuation=False,
            split_character=True,
        )

        text = "Night, friend. Ha. Which one?"
        self.assertEqual("".join(tokenizer.tokenize(text)), text)

    def test_pinned_livekit_synchronizer_uses_display_safe_word_tokenizer_for_opt_in_sync(self) -> None:
        from livekit.agents.voice.transcription import synchronizer

        source = inspect.getsource(synchronizer.TranscriptSynchronizer)

        self.assertIn("WordTokenizer", source)
        self.assertIn("retain_format=True", source)
        self.assertIn("ignore_punctuation=False", source)
        self.assertIn("split_character=True", source)


if __name__ == "__main__":
    unittest.main()
