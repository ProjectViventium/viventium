# === VIVENTIUM START ===
# Feature: Telegram file upload to LibreChat agent
# Purpose: Unit tests for file download and encoding functions.
# Added: 2026-01-31
# === VIVENTIUM END ===

import base64
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'TelegramVivBot'))

from utils.scripts import (
    detect_mime_from_path,
    encode_file_for_agent,
    is_image_mime,
    SUPPORTED_IMAGE_MIMES,
    EXTENSION_TO_MIME,
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
        assert detect_mime_from_path("settings.yml") == "text/yaml"
        assert detect_mime_from_path("settings.yaml") == "text/yaml"

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

    def test_code_extensions(self):
        assert ".py" in EXTENSION_TO_MIME
        assert ".js" in EXTENSION_TO_MIME
        assert ".json" in EXTENSION_TO_MIME


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
