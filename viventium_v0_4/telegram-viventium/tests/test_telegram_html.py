# === VIVENTIUM START ===
# Feature: Telegram HTML renderer regression tests.
#
# Purpose:
# - Protect tuned Telegram readability/formatting while runtime reliability evolves.
# - Ensure markdown conversion remains stable for headings, lists, code, links, and escaping.
#
# Added: 2026-02-19
# === VIVENTIUM END ===

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from TelegramVivBot.utils.telegram_html import markdown_to_html, strip_html_tags


def test_markdown_to_html_converts_headings_lists_and_bold():
    text = "# Title\n\n- first\n- second\n\n**Bold** line"
    rendered = markdown_to_html(text)
    assert "<b>Title</b>" in rendered
    assert "• first" in rendered
    assert "• second" in rendered
    assert "<b>Bold</b>" in rendered


def test_markdown_to_html_converts_inline_and_fenced_code():
    text = "Use `pip install`.\n\n```python\nprint('ok')\n```"
    rendered = markdown_to_html(text)
    assert "<code>pip install</code>" in rendered
    assert "<pre><code class=\"language-python\">" in rendered
    assert "print('ok')" in rendered


def test_markdown_to_html_converts_links():
    text = "[Open site](https://chat.viventium.ai)"
    rendered = markdown_to_html(text)
    assert "<a href=\"https://chat.viventium.ai\">Open site</a>" in rendered


def test_markdown_to_html_escapes_html_special_chars():
    text = "5 < 7 & 8 > 3"
    rendered = markdown_to_html(text)
    assert "&lt;" in rendered
    assert "&gt;" in rendered
    assert "&amp;" in rendered


def test_strip_html_tags_returns_plain_text():
    html = "<b>Bold</b> and <code>code</code>"
    assert strip_html_tags(html) == "Bold and code"


def test_double_processing_mangles_html_tags():
    """Documents the double-processing bug: feeding already-rendered HTML back
    through markdown_to_html escapes the tags (e.g. <i> → &lt;i&gt;), causing
    Telegram to display raw tag text instead of formatting.

    This is the root cause of follow-up messages showing literal <i>...</i>.
    The fix is in bot.py on_proactive_message: when parse_mode='HTML', skip
    re-rendering and pass pre-rendered HTML through as-is.
    """
    markdown_input = "*Waitlist Irony*\nSome follow-up text."
    pass1 = markdown_to_html(markdown_input)
    assert "<i>Waitlist Irony</i>" in pass1

    # Second pass mangles the HTML — this proves the bug exists in the renderer
    # and why the callback must NOT re-render pre-rendered HTML.
    pass2 = markdown_to_html(pass1)
    assert "&lt;i&gt;" in pass2, "Double-processing should escape HTML tags"
    assert "<i>" not in pass2, "Double-processing should not preserve raw HTML tags"
