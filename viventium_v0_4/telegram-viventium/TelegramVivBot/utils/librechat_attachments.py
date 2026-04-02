# === VIVENTIUM START ===
# Feature: LibreChat attachment delivery helpers (Telegram bridge)
#
# Purpose:
# - Telegram bot streams text deltas from LibreChat via SSE.
# - LibreChat-generated files/images are emitted as "attachment" events and persisted as message
#   attachments; Telegram must download and send them explicitly.
#
# Notes:
# - Keep this module import-safe for unit tests (do not import Telegram bot config or start-up code).
# - The caller provides base_url/secret/limits and the Telegram bot instance.
#
# Added: 2026-02-10
# === VIVENTIUM END ===

from __future__ import annotations

import re
import urllib.parse
from io import BytesIO
from typing import Any, Awaitable, Callable, Optional

import httpx
from telegram import InputMediaPhoto

_LC_CODE_DOWNLOAD_PATH_RE = re.compile(
    r"^/?(?:.*?)(/api/files/code/download/([A-Za-z0-9_-]{21})/([A-Za-z0-9_-]{21}))"
)


def build_librechat_url(base_url: str, path: str) -> str:
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return ""
    if not path:
        return ""
    if not path.startswith("/"):
        path = "/" + path
    return f"{base}{path}"


async def fetch_librechat_bytes(
    *,
    base_url: str,
    secret: str,
    url: str,
    telegram_user_id: str,
    telegram_username: str,
    telegram_chat_id: str,
    timeout_s: float = 60.0,
) -> tuple[bytes, str]:
    secret = (secret or "").strip()
    if not secret:
        raise RuntimeError("LibreChat secret missing")
    if not url:
        raise RuntimeError("Missing download url")

    headers = {"X-VIVENTIUM-TELEGRAM-SECRET": secret}
    params = {"telegramUserId": str(telegram_user_id)}
    if telegram_username:
        params["telegramUsername"] = str(telegram_username)
    if telegram_chat_id:
        params["telegramChatId"] = str(telegram_chat_id)

    timeout = httpx.Timeout(connect=10.0, read=timeout_s, write=10.0, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.content, resp.headers.get("content-type") or ""


def _attachment_download_url(
    *,
    base_url: str,
    file_id: str,
    filepath: str,
) -> str:
    if file_id:
        quoted = urllib.parse.quote(str(file_id), safe="")
        return build_librechat_url(base_url, f"/api/viventium/telegram/files/download/{quoted}")

    if filepath:
        match = _LC_CODE_DOWNLOAD_PATH_RE.match(filepath)
        if match:
            session_id = match.group(2)
            code_file_id = match.group(3)
            return build_librechat_url(
                base_url,
                f"/api/viventium/telegram/files/code/download/{session_id}/{code_file_id}",
            )
        return build_librechat_url(base_url, filepath)

    return ""


async def send_librechat_attachments(
    *,
    bot: Any,
    base_url: str,
    secret: str,
    telegram_user_id: str,
    telegram_username: str,
    telegram_chat_id: str,
    attachments: list[dict[str, Any]],
    message_thread_id: Optional[int],
    reply_to_message_id: Optional[int],
    max_bytes: int = 10_485_760,
    text_fallback: bool = False,
    fetch_bytes: Optional[
        Callable[..., Awaitable[tuple[bytes, str]]]
    ] = None,
) -> None:
    if not attachments:
        return

    if fetch_bytes is None:
        fetch_bytes = fetch_librechat_bytes

    seen: set[str] = set()
    images: list[bytes] = []
    documents: list[tuple[bytes, str]] = []

    for att in attachments:
        if not isinstance(att, dict):
            continue

        file_id = att.get("file_id") or att.get("fileId") or ""
        filename = att.get("filename") or att.get("name") or ""
        filepath = att.get("filepath") or att.get("path") or ""
        mime_type = att.get("type") or att.get("mime_type") or ""
        size_hint = att.get("bytes") if isinstance(att.get("bytes"), int) else None

        dedupe_key = str(file_id or filepath or filename)
        if not dedupe_key or dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        if size_hint is not None and size_hint > max_bytes:
            if text_fallback:
                await bot.send_message(
                    chat_id=telegram_chat_id,
                    message_thread_id=message_thread_id,
                    text=f"File too large to send via Telegram ({size_hint} bytes): {filename or file_id or filepath}",
                    reply_to_message_id=reply_to_message_id,
                )
            continue

        download_url = _attachment_download_url(
            base_url=base_url,
            file_id=str(file_id),
            filepath=str(filepath),
        )
        if not download_url:
            continue

        try:
            blob, content_type = await fetch_bytes(
                base_url=base_url,
                secret=secret,
                url=download_url,
                telegram_user_id=telegram_user_id,
                telegram_username=telegram_username,
                telegram_chat_id=telegram_chat_id,
            )
        except Exception:
            # Caller logs (bot.py) should capture failures; skip delivery here.
            continue

        final_mime = (content_type or mime_type or "").split(";")[0].strip().lower()
        if final_mime.startswith("image/"):
            images.append(blob)
        else:
            safe_name = filename or (f"{file_id}.bin" if file_id else "attachment.bin")
            documents.append((blob, safe_name))

    for i in range(0, len(images), 10):
        batch = images[i : i + 10]
        if not batch:
            continue
        media_group = [InputMediaPhoto(media=b) for b in batch]
        try:
            await bot.send_media_group(
                chat_id=telegram_chat_id,
                media=media_group,
                message_thread_id=message_thread_id,
                reply_to_message_id=reply_to_message_id,
            )
        except Exception:
            # Best-effort: don't fail the whole response if Telegram rejects media.
            continue

    for blob, safe_name in documents:
        bio = BytesIO(blob)
        bio.name = safe_name
        bio.seek(0)
        try:
            await bot.send_document(
                chat_id=telegram_chat_id,
                message_thread_id=message_thread_id,
                document=bio,
                filename=safe_name,
                reply_to_message_id=reply_to_message_id,
            )
        except Exception:
            continue
