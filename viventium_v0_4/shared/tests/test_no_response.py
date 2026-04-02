# === VIVENTIUM START ===
# Tests for No Response Tag helper.
# Added: 2026-02-07
# === VIVENTIUM END ===

import sys
from pathlib import Path

# Allow `from no_response import ...` by adding `viventium_v0_4/shared` to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from no_response import (  # noqa: E402
    NO_RESPONSE_TAG,
    is_no_response_only,
    is_no_response_tag,
    normalize_no_response_text,
)


def test_is_no_response_tag_strict_tag() -> None:
    assert is_no_response_tag("{NTA}") is True
    assert is_no_response_tag("{ nta }") is True
    assert is_no_response_tag("  {NTA}\n") is True


def test_is_no_response_tag_rejects_non_tag() -> None:
    assert is_no_response_tag("") is False
    assert is_no_response_tag("hello") is False
    assert is_no_response_tag("{NOTNTA}") is False


def test_is_no_response_only_accepts_legacy_phrases() -> None:
    assert is_no_response_only("Nothing new to add.") is True
    assert is_no_response_only("nothing to add") is True
    assert is_no_response_only("Nothing new to add for now.") is True
    assert is_no_response_only("Nothing to add (yet).") is True
    assert is_no_response_only("Nothing to add, thanks!") is True


def test_is_no_response_only_rejects_prefix_with_content() -> None:
    assert is_no_response_only("Nothing new to add. What next?") is False
    assert is_no_response_only("Nothing to add: Actually, I found something.") is False


def test_normalize_no_response_text() -> None:
    assert normalize_no_response_text("Nothing new to add.") == NO_RESPONSE_TAG
    assert normalize_no_response_text("Nothing new to add for now.") == NO_RESPONSE_TAG
    assert normalize_no_response_text("{NTA}") == NO_RESPONSE_TAG
    assert normalize_no_response_text("hello") == "hello"
