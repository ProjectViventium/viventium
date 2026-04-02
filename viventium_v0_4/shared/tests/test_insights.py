import sys
from pathlib import Path


# Allow `from insights import ...` by adding `viventium_v0_4/shared` to sys.path.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from insights import format_insights_fallback_text  # noqa: E402


def test_format_insights_fallback_text_text_mode_paragraphs() -> None:
    insights = [
        {"cortex_name": "Online Tool Use", "insight": "First."},
        {"cortex_name": "Pattern Recognition", "insight": "Second."},
    ]
    text = format_insights_fallback_text(insights, voice_mode=False)
    assert text == "First.\n\nSecond."
    assert "Online Tool Use" not in text
    assert "Pattern Recognition" not in text
    assert "Background insights" not in text


def test_format_insights_fallback_text_voice_mode_spaces() -> None:
    insights = [{"insight": "Hello."}, {"insight": "World."}]
    text = format_insights_fallback_text(insights, voice_mode=True)
    assert text == "Hello. World."


def test_format_insights_fallback_text_skips_empty() -> None:
    insights = [{"insight": "  "}, {"insight": "Kept"}]
    text = format_insights_fallback_text(insights, voice_mode=False)
    assert text == "Kept"

