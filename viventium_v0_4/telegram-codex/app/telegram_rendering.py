from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict


MAX_TELEGRAM_TEXT_CHARS = 3500

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

_CITATION_COMPOSITE_RE = re.compile(r"(?:\\ue200|ue200|\ue200).*?(?:\\ue201|ue201|\ue201)", re.IGNORECASE)
_CITATION_STANDALONE_RE = re.compile(r"(?:\\ue202|ue202|\ue202)turn\d+[A-Za-z]+\d+", re.IGNORECASE)
_CITATION_CLEANUP_RE = re.compile(r"(?:\\ue2(?:00|01|02|03|04|06)|ue2(?:00|01|02|03|04|06)|[\ue200-\ue206])", re.IGNORECASE)
_BRACKET_CITATION_RE = re.compile(r"\[(\d{1,3})\](?=\s|$)")
_MARKDOWN_CODE_SPAN_RE = re.compile(r"```[\s\S]*?```|`[^`\n]*`")
_EM_DASH_RE = re.compile("—")
_EM_DASH_OPENERS = "\"'“‘([{"
_MARKDOWN_V2_UNESCAPE_RE = re.compile(r"\\([_*\[\]()~`>#+\-=|{}.!])")


@dataclass(frozen=True)
class RenderedChunk:
    html: str
    plain: str


def sanitize_telegram_text(text: str) -> str:
    if not text:
        return ""
    cleaned = _CITATION_COMPOSITE_RE.sub(" ", text)
    cleaned = _CITATION_STANDALONE_RE.sub(" ", cleaned)
    cleaned = _CITATION_CLEANUP_RE.sub(" ", cleaned)
    cleaned = _BRACKET_CITATION_RE.sub(" ", cleaned)
    cleaned = _apply_outside_markdown_code(cleaned, _normalize_em_dashes_for_telegram)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def _apply_outside_markdown_code(text: str, transform):
    if not text:
        return ""
    parts: list[str] = []
    last_index = 0
    for match in _MARKDOWN_CODE_SPAN_RE.finditer(text):
        parts.append(transform(text[last_index : match.start()]))
        parts.append(match.group(0))
        last_index = match.end()
    parts.append(transform(text[last_index:]))
    return "".join(parts)


def _normalize_em_dashes_for_telegram(text: str) -> str:
    if "—" not in text:
        return text

    parts: list[str] = []
    last_index = 0
    for match in _EM_DASH_RE.finditer(text):
        dash_index = match.start()
        segment = text[last_index:dash_index].rstrip(" \t")
        if segment:
            parts.append(segment)

        next_index = match.end()
        while next_index < len(text) and text[next_index] in " \t":
            next_index += 1

        lookahead_index = next_index
        while lookahead_index < len(text) and text[lookahead_index] in _EM_DASH_OPENERS:
            lookahead_index += 1

        prev_has_space = dash_index > 0 and text[dash_index - 1] in " \t"
        next_has_space = dash_index + 1 < len(text) and text[dash_index + 1] in " \t"
        next_char = text[lookahead_index] if lookahead_index < len(text) else ""
        replacement = ", " if prev_has_space or next_has_space or next_char.isupper() else " "
        parts.append(replacement)
        last_index = next_index

    parts.append(text[last_index:])
    return "".join(parts)


def split_telegram_text(text: str, limit: int = MAX_TELEGRAM_TEXT_CHARS) -> list[str]:
    if not text:
        return []
    cleaned = text.strip()
    if not cleaned:
        return []
    if len(cleaned) <= limit:
        return [cleaned]

    chunks: list[str] = []
    remaining = cleaned
    min_boundary = max(1, limit // 2)

    while len(remaining) > limit:
        split_at = remaining.rfind("\n\n", 0, limit)
        if split_at < min_boundary:
            split_at = remaining.rfind("\n", 0, limit)
        if split_at < min_boundary:
            split_at = remaining.rfind(". ", 0, limit)
            if split_at >= min_boundary:
                split_at += 1
        if split_at < min_boundary:
            split_at = remaining.rfind(" ", 0, limit)
        if split_at < 1:
            split_at = limit

        chunk = remaining[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].strip()

    if remaining:
        chunks.append(remaining)
    return chunks


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_html_attr(text: str) -> str:
    return _escape_html(text).replace('"', "&quot;")


def markdown_to_html(text: str) -> str:
    if not text:
        return ""

    placeholders: Dict[str, str] = {}
    counter = [0]

    def _store(html: str) -> str:
        key = f"\x00PH{counter[0]}\x00"
        counter[0] += 1
        placeholders[key] = html
        return key

    def _replace_fenced_code(match: re.Match) -> str:
        lang = match.group(1) or ""
        code = _escape_html(match.group(2))
        if lang:
            return _store(f'<pre><code class="language-{_escape_html_attr(lang)}">{code}</code></pre>')
        return _store(f"<pre><code>{code}</code></pre>")

    def _replace_inline_code(match: re.Match) -> str:
        return _store(f"<code>{_escape_html(match.group(1))}</code>")

    def _replace_link(match: re.Match) -> str:
        label = _escape_html(match.group(1))
        url = _escape_html_attr(match.group(2))
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

    blockquote_lines: list[str] = []
    out_lines: list[str] = []
    for line in result.split("\n"):
        blockquote = _BLOCKQUOTE_RE.match(line)
        if blockquote:
            blockquote_lines.append(blockquote.group(1))
            continue
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
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", "", text)
    cleaned = cleaned.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return cleaned.strip()


def strip_markdown(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"```[\s\S]*?```", " ", text)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"[\*_~]+", "", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = _MARKDOWN_V2_UNESCAPE_RE.sub(r"\1", cleaned)
    return cleaned.strip()


def render_telegram_chunks(text: str, limit: int = MAX_TELEGRAM_TEXT_CHARS) -> list[RenderedChunk]:
    cleaned = sanitize_telegram_text(text)
    if not cleaned:
        return []
    chunks = split_telegram_text(cleaned, limit=limit)
    return [
        RenderedChunk(
            html=markdown_to_html(chunk),
            plain=strip_markdown(chunk),
        )
        for chunk in chunks
    ]

