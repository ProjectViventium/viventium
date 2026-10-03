# === VIVENTIUM START ===
# Feature: Telegram file upload to LibreChat agent
# Purpose: Unit tests for file download and encoding functions.
# Added: 2026-01-31
# === VIVENTIUM END ===

import base64
import asyncio
import sys
import os

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'TelegramVivBot'))

from utils.scripts import (
    detect_mime_from_path,
    encode_file_for_agent,
    is_image_mime,
    SUPPORTED_IMAGE_MIMES,
    EXTENSION_TO_MIME,
    download_telegram_file_result,
)


class TestDetectMimeFromPath:
    """Tests for MIME type detection from file paths."""

    def test_jpeg_extension(self):
        assert detect_mime_from_path("photo.jpg") == "image/jpeg"
        assert detect_mime_from_path("photo.jpeg") == "image/jpeg"
        assert detect_mime_from_path("photos/vacation/IMG_001.JPG") == "image/jpeg"

    def test_png_extension(self):
        assert detect_mime_from_path("screenshot.png") == "image/png"
        assert detect_mime_from_path("files/screenshot.PNG") == "image/png"

    def test_webp_extension(self):
        assert detect_mime_from_path("sticker.webp") == "image/webp"

    def test_gif_extension(self):
        assert detect_mime_from_path("animation.gif") == "image/gif"

    def test_pdf_extension(self):
        assert detect_mime_from_path("document.pdf") == "application/pdf"

    def test_text_extensions(self):
        assert detect_mime_from_path("readme.txt") == "text/plain"
        assert detect_mime_from_path("README.md") == "text/markdown"
        assert detect_mime_from_path("script.py") == "text/x-python"
        assert detect_mime_from_path("config.json") == "application/json"
        assert detect_mime_from_path("settings.yml") == "application/x-yaml"
        assert detect_mime_from_path("settings.yaml") == "application/x-yaml"

    def test_unknown_extension(self):
        assert detect_mime_from_path("file.xyz") == "application/octet-stream"
        assert detect_mime_from_path("file") == "application/octet-stream"

    def test_empty_path(self):
        assert detect_mime_from_path("") == "application/octet-stream"
        assert detect_mime_from_path(None) == "application/octet-stream"


class TestEncodeFileForAgent:
    """Tests for file encoding for LibreChat agent."""

    def test_encode_image(self):
        test_bytes = b"fake image data"
        result = encode_file_for_agent(test_bytes, "image/jpeg", "photo.jpg")

        assert result["mime_type"] == "image/jpeg"
        assert result["filename"] == "photo.jpg"
        assert result["data"] == base64.b64encode(test_bytes).decode("utf-8")

    def test_encode_pdf(self):
        test_bytes = b"%PDF-1.4 fake pdf"
        result = encode_file_for_agent(test_bytes, "application/pdf", "document.pdf")

        assert result["mime_type"] == "application/pdf"
        assert result["filename"] == "document.pdf"
        assert "data" in result

    def test_roundtrip_encoding(self):
        """Verify base64 roundtrip preserves data."""
        original = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"  # PNG magic bytes
        result = encode_file_for_agent(original, "image/png", "test.png")
        decoded = base64.b64decode(result["data"])
        assert decoded == original


class TestTelegramDownloadMime:
    @staticmethod
    def download(filename, hint, path="documents/file_1", payload=b"synthetic source bytes"):
        class DownloadFile:
            file_path = path
            file_size = len(payload)

            async def download_as_bytearray(self):
                return bytearray(payload)

        class Bot:
            async def get_file(self, file_id, **_kwargs):
                assert file_id == "synthetic-file"
                return DownloadFile()

        return asyncio.run(download_telegram_file_result(
            Bot(), "synthetic-file", max_bytes=1024,
            filename_hint=filename, mime_type_hint=hint,
        ))

    @pytest.mark.parametrize("extension, hint, expected", [
        (".py", "text/x-script.phyton", "text/x-python"),
        (".PY", "application/octet-stream", "text/x-python"),
        (".js", "text/plain", "text/javascript"),
        (".json", "text/plain", "application/json"),
        (".yml", "application/x-yaml", "application/x-yaml"),
        (".yaml", "text/yaml", "application/x-yaml"),
        (".csv", "application/csv", "text/csv"),
        (".pdf", "application/octet-stream", "application/pdf"),
        (".docx", "application/octet-stream",
         "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        (".xlsx", "application/octet-stream",
         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        (".pptx", "application/octet-stream",
         "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    ])
    def test_known_extension_normalizes_hint_without_changing_source(self, extension, hint, expected):
        filename = "source" + extension
        result = self.download(filename, hint)
        assert result.mime_type == expected
        assert result.filename == filename
        assert result.file_path == "documents/file_1"
        assert result.file_bytes == b"synthetic source bytes"
        assert result.error_code is None

    @pytest.mark.parametrize("filename, hint, path, expected", [
        ("unknown.bin", "application/octet-stream", "documents/file_1", "application/octet-stream"),
        ("unknown.xyz", "application/x-unknown", "documents/file_1", "application/x-unknown"),
        ("unknown.bin", None, "documents/file_1", "application/octet-stream"),
        ("source.py", None, "documents/file_1", "text/x-python"),
        (None, None, "documents/source.py", "text/x-python"),
        (None, "text/x-script.phyton", "documents/source.py", "text/x-python"),
        ("unknown.bin", None, "documents/source.pdf", "application/pdf"),
    ])
    def test_unknown_and_missing_hints_preserve_existing_fallback(self, filename, hint, path, expected):
        result = self.download(filename, hint, path=path)
        assert result.mime_type == expected
        assert result.file_bytes == b"synthetic source bytes"
        assert result.error_code is None

    @pytest.mark.parametrize("extension, mime", list(EXTENSION_TO_MIME.items()))
    def test_known_correct_mime_hint_is_preserved(self, extension, mime):
        result = self.download("source" + extension, mime)
        assert result.mime_type == mime


class TestIsImageMime:
    """Tests for image MIME type detection."""

    def test_supported_image_types(self):
        for mime in SUPPORTED_IMAGE_MIMES:
            assert is_image_mime(mime) is True

    def test_jpeg_variations(self):
        assert is_image_mime("image/jpeg") is True
        assert is_image_mime("image/png") is True
        assert is_image_mime("image/gif") is True
        assert is_image_mime("image/webp") is True

    def test_generic_image_prefix(self):
        # Any image/* should return True
        assert is_image_mime("image/tiff") is True
        assert is_image_mime("image/bmp") is True
        assert is_image_mime("image/heic") is True

    def test_non_image_types(self):
        assert is_image_mime("application/pdf") is False
        assert is_image_mime("text/plain") is False
        assert is_image_mime("video/mp4") is False
        assert is_image_mime("audio/mpeg") is False


class TestExtensionToMimeMapping:
    """Tests for extension-to-MIME mapping completeness."""

    def test_common_image_extensions(self):
        image_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".heic"]
        for ext in image_extensions:
            assert ext in EXTENSION_TO_MIME, f"Missing extension: {ext}"
            assert EXTENSION_TO_MIME[ext].startswith("image/"), f"Wrong MIME for {ext}"

    def test_document_extensions(self):
        assert ".pdf" in EXTENSION_TO_MIME
        assert ".txt" in EXTENSION_TO_MIME
        assert ".md" in EXTENSION_TO_MIME
        assert detect_mime_from_path("deck.pptx") == (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
        assert detect_mime_from_path("sheet.xlsx") == (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert detect_mime_from_path("doc.docx") == (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert detect_mime_from_path("slides.odp") == "application/vnd.oasis.opendocument.presentation"

    def test_code_extensions(self):
        assert ".py" in EXTENSION_TO_MIME
        assert ".js" in EXTENSION_TO_MIME
        assert ".json" in EXTENSION_TO_MIME


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
