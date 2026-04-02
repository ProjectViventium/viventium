# === VIVENTIUM START ===
# Feature: Markdown → Telegram HTML conversion
#
# Purpose:
# - Convert standard Markdown (from LLM output) to Telegram-supported HTML.
# - HTML parse mode is far more robust than MarkdownV2:
#   only 3 characters need escaping (<, >, &) vs 17 for MarkdownV2.
# - Inspired by OpenClaw's IR-based approach (see research/CognitiveAI_System/cool repos/openclaw).
#
# Supported Telegram HTML tags:
#   <b>, <i>, <u>, <s>, <code>, <pre>, <a>, <blockquote>, <tg-spoiler>
#
# Added: 2026-02-15
# === VIVENTIUM END ===

import re
from typing import Dict

_FENCED_CODE_RE = re.compile(r"```(\w*)\n([\s\S]*?)```", re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+?)`")
_LINK_RE = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")
_BOLD_ASTERISK_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_BOLD_UNDERSCORE_RE = re.compile(r"__(.+?)__", re.DOTALL)
_ITALIC_ASTERISK_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_ITALIC_UNDERSCORE_RE = re.compile(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)")
_STRIKETHROUGH_RE = re.compile(r"~~(.+?)~~")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_BLOCKQUOTE_RE = re.compile(r"^>\s?(.*)$", re.MULTILINE)
_BULLET_RE = re.compile(r"^(\s*)[-*]\s+", re.MULTILINE)
_HR_RE = re.compile(r"^---+$", re.MULTILINE)


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_html_attr(text: str) -> str:
    return _escape_html(text).replace('"', "&quot;")


def markdown_to_html(text: str) -> str:
    """Convert standard Markdown to Telegram-compatible HTML.

    Uses a placeholder system to protect already-converted regions from
    being re-processed by subsequent regex passes.
    """
    if not text:
        return ""

    placeholders: Dict[str, str] = {}
    counter = [0]

    def _store(html: str) -> str:
        key = f"\x00PH{counter[0]}\x00"
        counter[0] += 1
        placeholders[key] = html
        return key

    def _replace_fenced_code(m: re.Match) -> str:
        lang = m.group(1) or ""
        code = _escape_html(m.group(2))
        if lang:
            return _store(f'<pre><code class="language-{_escape_html_attr(lang)}">{code}</code></pre>')
        return _store(f"<pre><code>{code}</code></pre>")

    def _replace_inline_code(m: re.Match) -> str:
        return _store(f"<code>{_escape_html(m.group(1))}</code>")

    def _replace_link(m: re.Match) -> str:
        label = _escape_html(m.group(1))
        url = _escape_html_attr(m.group(2))
        return _store(f'<a href="{url}">{label}</a>')

    result = text

    result = _FENCED_CODE_RE.sub(_replace_fenced_code, result)
    result = _INLINE_CODE_RE.sub(_replace_inline_code, result)
    result = _LINK_RE.sub(_replace_link, result)

    result = _BOLD_ASTERISK_RE.sub(lambda m: _store(f"<b>{_escape_html(m.group(1))}</b>"), result)
    result = _BOLD_UNDERSCORE_RE.sub(lambda m: _store(f"<b>{_escape_html(m.group(1))}</b>"), result)
    result = _STRIKETHROUGH_RE.sub(lambda m: _store(f"<s>{_escape_html(m.group(1))}</s>"), result)
    result = _ITALIC_ASTERISK_RE.sub(lambda m: _store(f"<i>{_escape_html(m.group(1))}</i>"), result)
    result = _ITALIC_UNDERSCORE_RE.sub(lambda m: _store(f"<i>{_escape_html(m.group(1))}</i>"), result)
    result = _HEADING_RE.sub(lambda m: _store(f"\n<b>{_escape_html(m.group(2))}</b>\n"), result)

    result = _BULLET_RE.sub(lambda m: f"{m.group(1)}• ", result)
    result = _HR_RE.sub("─────────────────", result)

    blockquote_lines = []
    out_lines = []
    for line in result.split("\n"):
        bq = _BLOCKQUOTE_RE.match(line)
        if bq:
            blockquote_lines.append(bq.group(1))
        else:
            if blockquote_lines:
                content = "\n".join(blockquote_lines)
                out_lines.append(_store(f"<blockquote>{_escape_html(content)}</blockquote>"))
                blockquote_lines = []
            out_lines.append(line)
    if blockquote_lines:
        content = "\n".join(blockquote_lines)
        out_lines.append(_store(f"<blockquote>{_escape_html(content)}</blockquote>"))
    result = "\n".join(out_lines)

    result = _escape_html(result)

    for key, value in placeholders.items():
        result = result.replace(key, value)

    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


def strip_html_tags(text: str) -> str:
    """Strip all HTML tags for plain-text fallback."""
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", "", text)
    cleaned = cleaned.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return cleaned.strip()
