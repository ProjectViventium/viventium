import sys
from pathlib import Path


VIVENTIUM_ROOT = Path(__file__).resolve().parents[2]
SHARED_ROOT = VIVENTIUM_ROOT / "shared"
if str(SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_ROOT))

from delivery_controls import (  # noqa: E402
    DELIVERY_CONTROL_VERSION,
    MESSAGE_BREAK_TOKEN,
    SKIP_VOICE_TOKEN,
    parse_delivery_controls,
    strip_delivery_controls_for_preview,
)


def test_parse_delivery_controls_builds_one_clean_logical_turn():
    parsed = parse_delivery_controls(
        "\n".join(["First thought.", "{MSG_BREAK}", "Second thought.", "{SKIP_VOICE}"])
    )

    assert parsed.contract_version == DELIVERY_CONTROL_VERSION
    assert parsed.skip_voice is True
    assert parsed.message_break_count == 1
    assert parsed.merged_break_count == 0
    assert parsed.clean_text == "First thought.\n\nSecond thought."
    assert list(parsed.segments) == ["First thought.", "Second thought."]
    assert SKIP_VOICE_TOKEN == "{SKIP_VOICE}"
    assert MESSAGE_BREAK_TOKEN == "{MSG_BREAK}"


def test_parse_delivery_controls_protects_code_quotes_and_prose():
    source = "\n".join(
        [
            "Use `{SKIP_VOICE}` in this example.",
            "```text",
            "{MSG_BREAK}",
            "```",
            "> {SKIP_VOICE}",
            "A literal {MSG_BREAK} inside a sentence stays.",
        ]
    )

    parsed = parse_delivery_controls(source)

    assert parsed.skip_voice is False
    assert parsed.message_break_count == 0
    assert parsed.clean_text == source


def test_parse_delivery_controls_caps_at_three_messages():
    parsed = parse_delivery_controls(
        "\n".join(
            [
                "One.",
                "{MSG_BREAK}",
                "Two.",
                "{MSG_BREAK}",
                "Three.",
                "{MSG_BREAK}",
                "Four.",
            ]
        )
    )

    assert list(parsed.segments) == ["One.", "Two.", "Three.\n\nFour."]
    assert parsed.message_break_count == 2
    assert parsed.merged_break_count == 1


def test_strip_delivery_controls_for_preview_hides_incomplete_reserved_suffix():
    assert strip_delivery_controls_for_preview("Draft ready.\n{") == "Draft ready."
    assert strip_delivery_controls_for_preview("Draft ready.\n{SKIP_") == "Draft ready."
    assert (
        strip_delivery_controls_for_preview("First.\n{MSG_BREAK}\nSec")
        == "First.\n\nSec"
    )
    assert strip_delivery_controls_for_preview("~~~text\n{MSG_\n~~~") == "~~~text\n{MSG_\n~~~"
    assert strip_delivery_controls_for_preview("> {SKIP_") == "> {SKIP_"
    assert strip_delivery_controls_for_preview("Literal {MSG_ in prose") == "Literal {MSG_ in prose"
