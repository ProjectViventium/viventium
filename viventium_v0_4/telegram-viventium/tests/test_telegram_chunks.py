import html
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "TelegramVivBot"
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from utils.librechat_bridge import render_telegram_markdown  # noqa: E402
from utils.telegram_chunks import (  # noqa: E402
    MAX_TELEGRAM_TEXT_UNITS,
    first_telegram_html_chunk,
    split_telegram_html,
    telegram_text_units,
)


def _visible_text(rendered_html: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", rendered_html))


def test_split_telegram_html_preserves_long_fenced_code_formatting() -> None:
    source = "```python\n" + ("print('synthetic')\n" * 420) + "```"
    rendered = render_telegram_markdown(source)

    chunks = split_telegram_html(rendered)

    assert len(chunks) > 1
    assert all(telegram_text_units(chunk) <= MAX_TELEGRAM_TEXT_UNITS for chunk in chunks)
    assert all(chunk.count("<pre>") == chunk.count("</pre>") == 1 for chunk in chunks)
    assert all(chunk.count("<code") == chunk.count("</code>") == 1 for chunk in chunks)
    assert "".join(_visible_text(chunk) for chunk in chunks) == _visible_text(rendered)


def test_split_telegram_html_measures_table_expansion_after_rendering() -> None:
    rows = "\n".join(f"| value {index} | detail {index} |" for index in range(260))
    source = "| Item | Detail |\n| --- | --- |\n" + rows
    rendered = render_telegram_markdown(source)

    chunks = split_telegram_html(rendered)

    assert len(chunks) > 1
    assert all(telegram_text_units(chunk) <= MAX_TELEGRAM_TEXT_UNITS for chunk in chunks)
    assert "".join(_visible_text(chunk) for chunk in chunks) == _visible_text(rendered)


def test_split_telegram_html_counts_astral_characters_as_two_utf16_units() -> None:
    rendered = render_telegram_markdown("😀" * 2400)

    chunks = split_telegram_html(rendered)

    assert len(chunks) == 2
    assert all(telegram_text_units(chunk) <= MAX_TELEGRAM_TEXT_UNITS for chunk in chunks)
    assert "".join(_visible_text(chunk) for chunk in chunks) == "😀" * 2400


def test_first_telegram_html_chunk_stops_at_one_balanced_preview() -> None:
    rendered = render_telegram_markdown("**bold `code`** " * 1200)

    first = first_telegram_html_chunk(rendered)

    assert telegram_text_units(first) <= MAX_TELEGRAM_TEXT_UNITS
    assert first.count("<b>") == first.count("</b>")
    assert first.count("<code>") == first.count("</code>")
    assert _visible_text(first)


def test_first_chunk_is_the_exact_first_full_split_across_entity_boundary() -> None:
    rendered = "<b>" + ("alpha &amp; beta " * 700) + "</b>"

    first = first_telegram_html_chunk(rendered)
    chunks = split_telegram_html(rendered)

    assert first == chunks[0]
    assert all(telegram_text_units(chunk) <= MAX_TELEGRAM_TEXT_UNITS for chunk in chunks)
    assert "".join(_visible_text(chunk) for chunk in chunks) == _visible_text(rendered)


def test_split_telegram_html_normalizes_crossed_tags_without_losing_text() -> None:
    crossed = "<b><i>synthetic</b> example</i>"

    chunks = split_telegram_html(crossed, limit=8)

    assert "".join(_visible_text(chunk) for chunk in chunks) == "synthetic example"
    assert all(chunk.count("<b>") == chunk.count("</b>") for chunk in chunks)
    assert all(chunk.count("<i>") == chunk.count("</i>") for chunk in chunks)
