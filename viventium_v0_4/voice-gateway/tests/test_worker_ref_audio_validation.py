# === VIVENTIUM START ===
# Feature: Chatterbox ref_audio startup validation tests
# Added: 2026-02-11
# Purpose:
# - Ensure invalid reference audio paths are rejected before runtime synthesis.
# - Verify WAV duration preflight enforces upstream >=5s expectation.
# === VIVENTIUM END ===

import os
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from livekit.agents.worker import WorkerType

from worker import (
    _apply_requested_voice_route,
    _build_voice_capability_catalog,
    _build_configured_voice_route_metadata,
    _build_voice_route_metadata,
    _validate_ref_audio_path,
    load_env,
    prewarm_process,
    run,
)


def _write_wav(path: Path, *, sample_rate: int, duration_s: float) -> None:
    frames = int(sample_rate * duration_s)
    silence = b"\x00\x00" * max(1, frames)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silence)


class TestRefAudioValidation(unittest.TestCase):
    def test_load_env_prefers_looser_intel_threshold_for_local_whisper(self) -> None:
        with (
            patch.dict(os.environ, {"VIVENTIUM_STT_PROVIDER": "whisper_local"}, clear=False),
            patch("worker.platform.machine", return_value="x86_64"),
        ):
            env = load_env()

        self.assertEqual(env.voice_worker_load_threshold, 0.999)

    def test_load_env_keeps_existing_threshold_on_apple_silicon(self) -> None:
        with (
            patch.dict(os.environ, {"VIVENTIUM_STT_PROVIDER": "whisper_local"}, clear=False),
            patch("worker.platform.machine", return_value="arm64"),
        ):
            env = load_env()

        self.assertEqual(env.voice_worker_load_threshold, 0.995)

    def test_load_env_uses_more_human_openai_tts_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            env = load_env()

        self.assertEqual(env.openai_tts_voice, "coral")
        self.assertEqual(env.openai_tts_speed, 1.12)
        self.assertIn("Speak naturally and warmly", env.openai_tts_instructions)

    def test_missing_path_rejected(self) -> None:
        valid, warning = _validate_ref_audio_path("/path/to/does_not_exist_ref_audio.wav")
        self.assertIsNone(valid)
        self.assertIn("does not exist", warning or "")

    def test_tiny_file_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tiny_path = Path(tmp_dir) / "tiny.wav"
            tiny_path.write_bytes(b"abc")
            valid, warning = _validate_ref_audio_path(str(tiny_path))
            self.assertIsNone(valid)
            self.assertIn("suspiciously small", warning or "")

    def test_short_wav_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            short_path = Path(tmp_dir) / "short.wav"
            _write_wav(short_path, sample_rate=24000, duration_s=1.0)
            valid, warning = _validate_ref_audio_path(str(short_path))
            self.assertIsNone(valid)
            self.assertIn("too short", warning or "")

    def test_long_wav_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            long_path = Path(tmp_dir) / "long.wav"
            _write_wav(long_path, sample_rate=24000, duration_s=6.0)
            valid, warning = _validate_ref_audio_path(str(long_path))
            self.assertEqual(valid, str(long_path.resolve()))
            self.assertIsNone(warning)

    def test_run_registers_publisher_worker(self) -> None:
        captured = {}

        def _fake_run_app(opts):
            captured["opts"] = opts

        with (
            patch("worker.start_health_server"),
            patch("worker.load_env", return_value=SimpleNamespace(livekit_agent_name="librechat-voice-gateway")),
            patch("worker.cli.run_app", side_effect=_fake_run_app),
        ):
            run()

        self.assertIn("opts", captured)
        self.assertEqual(captured["opts"].agent_name, "librechat-voice-gateway")
        self.assertEqual(captured["opts"].worker_type, WorkerType.PUBLISHER)

    def test_prewarm_process_prewarms_local_chatterbox_at_startup(self) -> None:
        proc = SimpleNamespace(userdata={})
        fake_tts = Mock()

        with (
            patch(
                "worker.load_env",
                return_value=SimpleNamespace(
                    stt_provider="openai",
                    tts_provider="local_chatterbox_turbo_mlx_8bit",
                    tts_provider_fallback="",
                    mlx_audio_model_id="mlx-community/chatterbox-turbo-8bit",
                ),
            ),
            patch("worker.load_vad", return_value=None),
            patch(
                "worker._build_local_chatterbox_config",
                return_value=(SimpleNamespace(model_id="mlx-community/chatterbox-turbo-8bit"), None),
            ),
            patch("worker.MlxChatterboxTTS", return_value=fake_tts) as tts_cls,
        ):
            prewarm_process(proc)

        tts_cls.assert_called_once()
        fake_tts.prewarm.assert_called_once_with()
        self.assertIs(proc.userdata["prewarmed_local_chatterbox_tts"], fake_tts)

    def test_apply_requested_voice_route_uses_available_requested_variants(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "openai-key",
                "XAI_API_KEY": "xai-key",
                "VIVENTIUM_TTS_PROVIDER": "openai",
                "VIVENTIUM_OPENAI_STT_MODEL": "gpt-4o-mini-transcribe",
            },
            clear=False,
        ):
            env = load_env()
            capabilities = _build_voice_capability_catalog(env)
            requested = {
                "stt": {"provider": "openai", "variant": "gpt-4o-transcribe"},
                "tts": {"provider": "xai", "variant": "Eve"},
            }

            updated = _apply_requested_voice_route(env, requested, capabilities)

        self.assertEqual(updated.stt_provider, "openai")
        self.assertEqual(updated.openai_stt_model, "gpt-4o-transcribe")
        self.assertEqual(updated.tts_provider, "xai")
        self.assertEqual(updated.xai_voice, "Eve")

    def test_apply_requested_voice_route_ignores_unavailable_providers(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "openai-key",
                "VIVENTIUM_TTS_PROVIDER": "openai",
                "VIVENTIUM_XAI_VOICE": "Sal",
            },
            clear=False,
        ):
            env = load_env()
            capabilities = _build_voice_capability_catalog(env)
            requested = {
                "stt": {"provider": "assemblyai", "variant": "universal-streaming"},
                "tts": {"provider": "xai", "variant": "Eve"},
            }

            updated = _apply_requested_voice_route(env, requested, capabilities)

        self.assertEqual(updated.stt_provider, env.stt_provider)
        self.assertEqual(updated.tts_provider, "openai")
        self.assertEqual(updated.xai_voice, "Sal")

    def test_apply_requested_voice_route_keeps_machine_default_when_requested_route_missing(self) -> None:
        with patch.dict(
            os.environ,
            {
                "CARTESIA_API_KEY": "cartesia-key",
                "VIVENTIUM_TTS_PROVIDER": "local_chatterbox_turbo_mlx_8bit",
                "VIVENTIUM_CARTESIA_MODEL_ID": "sonic-2",
            },
            clear=False,
        ):
            env = load_env()
            capabilities = _build_voice_capability_catalog(env)

            updated = _apply_requested_voice_route(env, {"stt": {}, "tts": {}}, capabilities)

        self.assertEqual(updated.tts_provider, "local_chatterbox_turbo_mlx_8bit")
        self.assertEqual(updated.cartesia_model_id, "sonic-2")

    def test_apply_requested_voice_route_switches_from_local_default_to_cartesia_variant(self) -> None:
        with patch.dict(
            os.environ,
            {
                "CARTESIA_API_KEY": "cartesia-key",
                "VIVENTIUM_TTS_PROVIDER": "local_chatterbox_turbo_mlx_8bit",
                "VIVENTIUM_CARTESIA_MODEL_ID": "sonic-2",
            },
            clear=False,
        ):
            env = load_env()
            capabilities = _build_voice_capability_catalog(env)
            requested = {
                "stt": {},
                "tts": {"provider": "cartesia", "variant": "sonic-3"},
            }

            updated = _apply_requested_voice_route(env, requested, capabilities)

        self.assertEqual(updated.tts_provider, "cartesia")
        self.assertEqual(updated.cartesia_model_id, "sonic-3")

    def test_build_voice_capability_catalog_marks_missing_keys_as_unavailable(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "",
                "XAI_API_KEY": "",
                "CARTESIA_API_KEY": "",
                "ELEVEN_API_KEY": "",
            },
            clear=False,
        ):
            env = load_env()
            capabilities = _build_voice_capability_catalog(env)

        by_key = {(entry["modality"], entry["id"]): entry for entry in capabilities}
        self.assertFalse(by_key[("stt", "openai")]["available"])
        self.assertIn("OPENAI_API_KEY", by_key[("stt", "openai")]["unavailableReason"])
        self.assertFalse(by_key[("tts", "xai")]["available"])
        self.assertIn("XAI_API_KEY", by_key[("tts", "xai")]["unavailableReason"])
        self.assertFalse(by_key[("tts", "openai")]["acceptsInlineVoiceControls"])
        self.assertTrue(by_key[("tts", "cartesia")]["acceptsInlineVoiceControls"])

    def test_build_voice_capability_catalog_labels_local_whisper_recommended_model(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIVENTIUM_STT_PROVIDER": "whisper_local",
                "VIVENTIUM_STT_MODEL": "large-v3-turbo",
            },
            clear=False,
        ):
            env = load_env()
            capabilities = _build_voice_capability_catalog(env)

        whisper_capability = next(
            entry
            for entry in capabilities
            if entry["modality"] == "stt" and entry["id"] == "pywhispercpp"
        )

        self.assertEqual(whisper_capability["label"], "Whisper.cpp Local")
        self.assertTrue(
            any(
                variant["id"] == "large-v3-turbo"
                and "(Recommended)" in variant["label"]
                for variant in whisper_capability["variants"]
            )
        )

    def test_build_configured_voice_route_metadata_matches_runtime_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "openai-key",
                "XAI_API_KEY": "xai-key",
                "VIVENTIUM_STT_PROVIDER": "openai",
                "VIVENTIUM_OPENAI_STT_MODEL": "gpt-4o-transcribe",
                "VIVENTIUM_TTS_PROVIDER": "xai",
                "VIVENTIUM_XAI_VOICE": "Eve",
                "VIVENTIUM_TTS_PROVIDER_FALLBACK": "openai",
            },
            clear=False,
        ):
            env = load_env()
            capabilities = _build_voice_capability_catalog(env)
            metadata = _build_configured_voice_route_metadata(env=env, capabilities=capabilities)

        self.assertEqual(metadata["stt"]["provider"], "openai")
        self.assertEqual(metadata["stt"]["variant"], "gpt-4o-transcribe")
        self.assertEqual(metadata["tts"]["provider"], "xai")
        self.assertEqual(metadata["tts"]["variant"], "Eve")
        self.assertEqual(metadata["ttsFallback"]["provider"], "openai")
        self.assertTrue(any(item["id"] == "xai" for item in metadata["capabilities"]))

    def test_build_voice_route_metadata_uses_effective_provider_variant(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "openai-key",
                "ELEVEN_API_KEY": "eleven-key",
                "VIVENTIUM_STT_PROVIDER": "whisper_local",
                "VIVENTIUM_STT_MODEL": "tiny.en",
                "VIVENTIUM_TTS_PROVIDER": "elevenlabs",
                "VIVENTIUM_ELEVENLABS_VOICE_ID_FALLBACK": "voice_fallback",
            },
            clear=False,
        ):
            env = load_env()
            capabilities = _build_voice_capability_catalog(env)

        effective_tts = SimpleNamespace(_opts=SimpleNamespace(voice_id="voice_live"))
        fallback_tts = SimpleNamespace(model="gpt-4o-mini-tts")
        metadata = _build_voice_route_metadata(
            env=env,
            capabilities=capabilities,
            stt_provider="pywhispercpp",
            tts_provider="elevenlabs",
            effective_tts_impl=effective_tts,
            fallback_tts_provider="openai",
            fallback_tts_impl=fallback_tts,
        )

        self.assertEqual(metadata["stt"]["provider"], "pywhispercpp")
        self.assertEqual(metadata["stt"]["variant"], "tiny.en")
        self.assertEqual(metadata["tts"]["provider"], "elevenlabs")
        self.assertEqual(metadata["tts"]["variant"], "voice_live")
        self.assertEqual(metadata["ttsFallback"]["provider"], "openai")


if __name__ == "__main__":
    unittest.main()
