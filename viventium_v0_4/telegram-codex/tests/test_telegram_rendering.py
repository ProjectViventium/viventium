from __future__ import annotations

from app.telegram_rendering import render_telegram_chunks, sanitize_telegram_text


def test_sanitize_telegram_text_removes_citations_and_normalizes_em_dash():
    text = "Hello \\ue202turn0search0 world [12] Hi—There"
    cleaned = sanitize_telegram_text(text)
    assert "turn0search0" not in cleaned
    assert "[12]" not in cleaned
    assert "Hi, There" in cleaned


def test_render_telegram_chunks_preserves_basic_markdown():
    chunks = render_telegram_chunks("Hello **bold**.\n- item")
    assert len(chunks) == 1
    assert "<b>bold</b>" in chunks[0].html
    assert "• item" in chunks[0].html
