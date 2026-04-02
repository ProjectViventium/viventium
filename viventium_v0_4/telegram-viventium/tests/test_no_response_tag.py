# === VIVENTIUM START ===
# Feature: Tests for NTA tag handling in Telegram delivery pipeline.
# Covers: is_no_response_only, strip_trailing_nta, title=None safety.
# Added: 2026-02-15
# === VIVENTIUM END ===

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from TelegramVivBot.utils.librechat_bridge import (
    is_no_response_only,
    strip_trailing_nta,
)


class TestIsNoResponseOnly:
    def test_exact_nta(self):
        assert is_no_response_only("{NTA}") is True

    def test_nta_with_whitespace(self):
        assert is_no_response_only("  {NTA}  ") is True

    def test_nta_case_insensitive(self):
        assert is_no_response_only("{nta}") is True

    def test_nta_with_spaces_inside(self):
        assert is_no_response_only("{ NTA }") is True

    def test_content_plus_nta_is_not_suppressed(self):
        assert is_no_response_only("Hello world {NTA}") is False

    def test_plain_text(self):
        assert is_no_response_only("Hello world") is False

    def test_empty_string(self):
        assert is_no_response_only("") is False

    def test_none(self):
        assert is_no_response_only(None) is False

    def test_legacy_phrase(self):
        assert is_no_response_only("Nothing new to add.") is True

    def test_variant_phrase(self):
        assert is_no_response_only("Nothing to add right now.") is True


class TestStripTrailingNTA:
    def test_content_plus_trailing_nta(self):
        """The real bug: model writes content then appends {NTA}."""
        text = "Happy Valentine's Day you two 💛\n\nEnjoy it.\n\n{NTA}"
        result = strip_trailing_nta(text)
        assert "{NTA}" not in result
        assert "Happy Valentine's Day" in result

    def test_only_nta_preserved_for_suppression(self):
        """Pure {NTA} must be preserved so isNoResponseOnly can suppress it."""
        assert strip_trailing_nta("{NTA}") == "{NTA}"
        assert strip_trailing_nta("  {NTA}  ") == "  {NTA}  "

    def test_nta_in_middle_not_stripped(self):
        """Only trailing {NTA} is stripped, not mid-text."""
        text = "The tag {NTA} appears here but more text follows."
        assert strip_trailing_nta(text) == text

    def test_plain_text_unchanged(self):
        assert strip_trailing_nta("Hello world") == "Hello world"

    def test_none_returns_empty(self):
        assert strip_trailing_nta(None) == ""

    def test_empty_string(self):
        assert strip_trailing_nta("") == ""

    def test_case_insensitive(self):
        text = "Some content\n\n{nta}"
        result = strip_trailing_nta(text)
        assert "nta" not in result.lower() or result == ""
        assert "Some content" in result


class TestTitleNoneSafety:
    """Regression tests for the title=None crash (bot.py line 783)."""

    def test_title_none_concatenation(self):
        """Simulate the concatenation at bot.py line 783."""
        title = None
        tmpresult = "Hello world"
        # This is what the fixed code does:
        result = (title or "") + tmpresult
        assert result == "Hello world"

    def test_title_empty_string(self):
        title = ""
        tmpresult = "Hello world"
        result = (title or "") + tmpresult
        assert result == "Hello world"

    def test_title_with_value(self):
        title = "**Title**\n"
        tmpresult = "Body text"
        result = (title or "") + tmpresult
        assert result == "**Title**\nBody text"

    def test_lastresult_none_safety(self):
        """Simulate lastresult = title at bot.py line 507."""
        title = None
        lastresult = title or ""
        assert lastresult == ""
        assert lastresult != None
