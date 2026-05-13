import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pywhispercpp_provider


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


if __name__ == "__main__":
    unittest.main()
