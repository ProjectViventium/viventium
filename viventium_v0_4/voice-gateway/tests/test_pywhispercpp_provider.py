import hashlib
import os
import tempfile
import unittest
import asyncio
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pywhispercpp_provider
from livekit.rtc.audio_frame import AudioFrame


class TestPyWhisperCppModelSelfHeal(unittest.TestCase):
    def test_default_models_preserve_best_local_route_on_apple_silicon(self) -> None:
        with (
            patch("pywhispercpp_provider.platform.machine", return_value="arm64"),
            patch.dict(os.environ, {}, clear=True),
        ):
            self.assertEqual(pywhispercpp_provider._default_model_name(), "large-v3-turbo")

    def test_default_models_use_smaller_route_on_x86(self) -> None:
        with (
            patch("pywhispercpp_provider.platform.machine", return_value="x86_64"),
            patch.dict(os.environ, {}, clear=True),
        ):
            self.assertEqual(pywhispercpp_provider._default_model_name(), "small")

    def test_bad_cached_checksum_redownloads_exact_selected_model(self) -> None:
        good_content = b"correct selected model"
        expected_sha1 = hashlib.sha1(good_content).hexdigest()

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            model_path = cache_dir / "ggml-large-v3-turbo.bin"
            model_path.write_bytes(b"corrupt stale model")

            def fake_urlretrieve(_url: str, destination: Path) -> None:
                Path(destination).write_bytes(good_content)

            with (
                patch.dict(os.environ, {"VIVENTIUM_WHISPER_CACHE_DIR": tmpdir}, clear=True),
                patch.dict(
                    pywhispercpp_provider.MODEL_SHA1,
                    {"ggml-large-v3-turbo.bin": expected_sha1},
                    clear=False,
                ),
                patch("pywhispercpp_provider.urllib.request.urlretrieve", side_effect=fake_urlretrieve),
            ):
                resolved = pywhispercpp_provider.ensure_model_file("large-v3-turbo")

            self.assertEqual(resolved, model_path.resolve())
            self.assertEqual(model_path.read_bytes(), good_content)

    def test_download_checksum_mismatch_preserves_existing_cache_and_cleans_temp(self) -> None:
        good_content = b"correct selected model"
        expected_sha1 = hashlib.sha1(good_content).hexdigest()

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            model_path = cache_dir / "ggml-large-v3-turbo.bin"
            existing_content = b"existing corrupt model"
            model_path.write_bytes(existing_content)

            def fake_urlretrieve(_url: str, destination: Path) -> None:
                Path(destination).write_bytes(b"wrong downloaded model")

            with (
                patch.dict(os.environ, {"VIVENTIUM_WHISPER_CACHE_DIR": tmpdir}, clear=True),
                patch.dict(
                    pywhispercpp_provider.MODEL_SHA1,
                    {"ggml-large-v3-turbo.bin": expected_sha1},
                    clear=False,
                ),
                patch("pywhispercpp_provider.urllib.request.urlretrieve", side_effect=fake_urlretrieve),
            ):
                with self.assertRaisesRegex(RuntimeError, "failed checksum"):
                    pywhispercpp_provider.ensure_model_file("large-v3-turbo")

            self.assertEqual(model_path.read_bytes(), existing_content)
            self.assertEqual(list(cache_dir.glob(".ggml-large-v3-turbo.bin.*.download")), [])

    def test_unsupported_model_does_not_silently_fallback(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported local whisper.cpp model"):
            pywhispercpp_provider.ensure_model_file("not-a-real-model")

    def test_legacy_large_alias_is_not_supported_without_checksum(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported local whisper.cpp model"):
            pywhispercpp_provider.ensure_model_file("large")

    def test_every_supported_model_has_checksum(self) -> None:
        missing = [
            filename
            for filename in pywhispercpp_provider.MODEL_FILENAMES.values()
            if filename not in pywhispercpp_provider.MODEL_SHA1
        ]

        self.assertEqual(missing, [])

    def test_failed_isolated_load_redownloads_exact_model_once(self) -> None:
        good_content = b"valid after repair"
        expected_sha1 = hashlib.sha1(good_content).hexdigest()

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            model_path = cache_dir / "ggml-large-v3-turbo.bin"
            model_path.write_bytes(good_content)

            def fake_urlretrieve(_url: str, destination: Path) -> None:
                Path(destination).write_bytes(good_content)

            with (
                patch.dict(os.environ, {"VIVENTIUM_WHISPER_CACHE_DIR": tmpdir}, clear=True),
                patch.dict(
                    pywhispercpp_provider.MODEL_SHA1,
                    {"ggml-large-v3-turbo.bin": expected_sha1},
                    clear=False,
                ),
                patch("pywhispercpp_provider.urllib.request.urlretrieve", side_effect=fake_urlretrieve),
                patch(
                    "pywhispercpp_provider._validate_model_load_in_subprocess",
                    side_effect=[(False, "native load failed"), (True, "ok")],
                ) as validate,
            ):
                resolved = pywhispercpp_provider.ensure_model_ready("large-v3-turbo")

            self.assertEqual(resolved, model_path.resolve())
            self.assertEqual(validate.call_count, 2)

    def test_validation_stamp_runtime_mismatch_revalidates_model(self) -> None:
        good_content = b"valid selected model"
        expected_sha1 = hashlib.sha1(good_content).hexdigest()

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            model_path = cache_dir / "ggml-large-v3-turbo.bin"
            model_path.write_bytes(good_content)
            pywhispercpp_provider._validation_stamp_path(model_path).write_text(
                f"sha1={expected_sha1}\nruntime=old-runtime\n",
                encoding="utf-8",
            )

            with (
                patch.dict(os.environ, {"VIVENTIUM_WHISPER_CACHE_DIR": tmpdir}, clear=True),
                patch.dict(
                    pywhispercpp_provider.MODEL_SHA1,
                    {"ggml-large-v3-turbo.bin": expected_sha1},
                    clear=False,
                ),
                patch(
                    "pywhispercpp_provider._validate_model_load_in_subprocess",
                    return_value=(True, "ok"),
                ) as validate,
            ):
                resolved = pywhispercpp_provider.ensure_model_ready("large-v3-turbo")

            self.assertEqual(resolved, model_path.resolve())
            validate.assert_called_once()


class TestPyWhisperCppRecognition(unittest.TestCase):
    def tearDown(self) -> None:
        pywhispercpp_provider._MODEL_WARMUP_DONE.clear()

    def test_prewarm_runs_one_silent_inference_by_default(self) -> None:
        fake_model = SimpleNamespace()
        calls = []

        def fake_transcribe(media, **kwargs):
            calls.append((media, kwargs))
            return []

        fake_model.transcribe = fake_transcribe

        with (
            patch.object(pywhispercpp_provider, "_get_model", return_value=fake_model),
            patch.dict(os.environ, {"VIVENTIUM_STT_LANGUAGE": "en"}, clear=True),
        ):
            pywhispercpp_provider.prewarm_model("large-v3-turbo")
            pywhispercpp_provider.prewarm_model("large-v3-turbo")

        self.assertEqual(len(calls), 1)
        media, kwargs = calls[0]
        self.assertIsInstance(media, np.ndarray)
        self.assertEqual(media.dtype, np.float32)
        self.assertTrue(media.flags["C_CONTIGUOUS"])
        self.assertEqual(media.size, 16000)
        self.assertEqual(kwargs["language"], "en")
        self.assertEqual(kwargs["temperature"], 0.0)
        self.assertEqual(kwargs["audio_ctx"], 768)
        self.assertEqual(kwargs["no_context"], True)
        self.assertEqual(kwargs["single_segment"], True)

    def test_prewarm_inference_can_be_disabled(self) -> None:
        fake_model = SimpleNamespace(transcribe=lambda _media, **_kwargs: [])

        with (
            patch.object(pywhispercpp_provider, "_get_model", return_value=fake_model),
            patch.dict(
                os.environ,
                {"VIVENTIUM_STT_WARMUP_INFERENCE": "false"},
                clear=True,
            ),
            patch.object(fake_model, "transcribe", wraps=fake_model.transcribe) as transcribe,
        ):
            pywhispercpp_provider.prewarm_model("large-v3-turbo")

        transcribe.assert_not_called()

    def test_recognize_passes_float32_pcm_directly_to_pywhispercpp(self) -> None:
        samples = np.array([0, 16384, -16384, 32767], dtype=np.int16)
        fake_model = SimpleNamespace()

        def fake_transcribe(media, **kwargs):
            fake_model.media = media
            fake_model.kwargs = kwargs
            return [SimpleNamespace(text="Hello there")]

        fake_model.transcribe = fake_transcribe

        with patch.object(pywhispercpp_provider, "_get_model", return_value=fake_model):
            stt = pywhispercpp_provider.PyWhisperCppSTT(language="en")

        frame = AudioFrame(
            data=samples.tobytes(),
            sample_rate=16000,
            num_channels=1,
            samples_per_channel=len(samples),
        )
        event = asyncio.run(stt._recognize_impl(frame))

        self.assertEqual(event.alternatives[0].text, "Hello there")
        self.assertIsInstance(fake_model.media, np.ndarray)
        self.assertEqual(fake_model.media.dtype, np.float32)
        self.assertTrue(fake_model.media.flags["C_CONTIGUOUS"])
        np.testing.assert_allclose(
            fake_model.media,
            samples.astype(np.float32) / 32768.0,
            rtol=0,
            atol=1e-6,
        )
        self.assertEqual(fake_model.kwargs["language"], "en")
        self.assertEqual(fake_model.kwargs["temperature"], 0.0)
        self.assertEqual(fake_model.kwargs["audio_ctx"], 768)
        self.assertEqual(fake_model.kwargs["no_context"], True)
        self.assertEqual(fake_model.kwargs["single_segment"], True)

    def test_large_turbo_audio_ctx_can_be_overridden(self) -> None:
        with patch.dict(os.environ, {"VIVENTIUM_STT_AUDIO_CTX": "0"}, clear=True):
            kwargs = pywhispercpp_provider._transcribe_kwargs(
                "en",
                model_name="large-v3-turbo",
            )

        self.assertNotIn("audio_ctx", kwargs)

    def test_large_turbo_reduced_audio_ctx_is_only_default_for_short_audio(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            short_kwargs = pywhispercpp_provider._transcribe_kwargs(
                "en",
                model_name="large-v3-turbo",
                audio_duration_s=8.0,
            )
            long_kwargs = pywhispercpp_provider._transcribe_kwargs(
                "en",
                model_name="large-v3-turbo",
                audio_duration_s=20.0,
            )

        self.assertEqual(short_kwargs["audio_ctx"], 768)
        self.assertNotIn("audio_ctx", long_kwargs)

    def test_large_turbo_explicit_audio_ctx_applies_to_long_audio(self) -> None:
        with patch.dict(os.environ, {"VIVENTIUM_STT_AUDIO_CTX": "512"}, clear=True):
            kwargs = pywhispercpp_provider._transcribe_kwargs(
                "en",
                model_name="large-v3-turbo",
                audio_duration_s=20.0,
            )

        self.assertEqual(kwargs["audio_ctx"], 512)

    def test_smaller_models_do_not_default_to_reduced_audio_ctx(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            kwargs = pywhispercpp_provider._transcribe_kwargs(
                "en",
                model_name="small",
            )

        self.assertNotIn("audio_ctx", kwargs)

    def test_latency_log_reports_sanitized_stage_timings(self) -> None:
        samples = np.array([0, 8192, -8192, 0], dtype=np.int16)
        fake_model = SimpleNamespace(
            transcribe=lambda _media, **_kwargs: [SimpleNamespace(text="Secret words")]
        )

        with (
            patch.object(pywhispercpp_provider, "_get_model", return_value=fake_model),
            patch.dict(os.environ, {"VIVENTIUM_VOICE_LOG_LATENCY": "1"}, clear=True),
        ):
            stt = pywhispercpp_provider.PyWhisperCppSTT(language="en")
            frame = AudioFrame(
                data=samples.tobytes(),
                sample_rate=16000,
                num_channels=1,
                samples_per_channel=len(samples),
            )
            with self.assertLogs("pywhispercpp_provider", level="INFO") as logs:
                asyncio.run(stt._recognize_impl(frame))

        joined = "\n".join(logs.output)
        self.assertIn("pywhispercpp_recognize", joined)
        self.assertIn("transcribe_ms=", joined)
        self.assertIn("text_chars=12", joined)
        self.assertNotIn("Secret words", joined)


if __name__ == "__main__":
    unittest.main()
