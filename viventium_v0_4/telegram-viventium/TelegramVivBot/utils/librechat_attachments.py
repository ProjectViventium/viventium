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
from telegram.error import BadRequest, Forbidden, RetryAfter
try:
    from utils.librechat_http import async_client_options_for_url
except ModuleNotFoundError:
    from TelegramVivBot.utils.librechat_http import async_client_options_for_url

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
    async with httpx.AsyncClient(
        timeout=timeout,
        **async_client_options_for_url(url),
    ) as client:
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
    before_side_effect: Optional[Callable[[], Awaitable[bool]]] = None,
    on_message_ids: Optional[Callable[[list[str]], None]] = None,
) -> dict[str, Any]:
    message_ids: list[str] = []
    if not attachments:
        return {"message_ids": [], "delivery_unknown": False, "outcomes": {}}

    if fetch_bytes is None:
        fetch_bytes = fetch_librechat_bytes

    seen: set[str] = set()
    images: list[tuple[bytes, str]] = []
    documents: list[tuple[bytes, str]] = []
    unavailable = 0
    retrieval_failed = 0
    oversized = 0
    rejected = 0
    unconfirmed = 0
    sent = 0

    async def authorize() -> None:
        if before_side_effect is None:
            return
        try:
            if await before_side_effect() is False:
                raise RuntimeError("telegram_attachment_authorization_lost")
        except Exception as exc:
            exc.telegram_message_ids = list(message_ids)
            raise

    def remember(result: Any, expected: int = 1) -> None:
        nonlocal unconfirmed, sent
        results = result if isinstance(result, (list, tuple)) else [result]
        confirmed = []
        for item in results:
            message_id = getattr(item, "message_id", None)
            if message_id is not None and str(message_id).strip():
                confirmed.append(str(message_id).strip())
        message_ids.extend(confirmed)
        if confirmed and on_message_ids is not None:
            on_message_ids(list(dict.fromkeys(message_ids)))
        sent += min(expected, len(confirmed))
        unconfirmed += max(0, expected - len(confirmed))

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

        # === VIVENTIUM START === Reuse existing notices for exact typed unavailable selections.
        receipt = att.get("nativeOutputFile")
        if (isinstance(receipt, dict) and receipt.get("version") == 1
                and receipt.get("status") == "unavailable" and isinstance(receipt.get("code"), str)):
            if receipt["code"] == "native_output_file_size_limit":
                oversized += 1
            else:
                unavailable += 1
            continue
        # === VIVENTIUM END ===
        if size_hint is not None and size_hint > max_bytes:
            oversized += 1
            continue

        download_url = _attachment_download_url(
            base_url=base_url,
            file_id=str(file_id),
            filepath=str(filepath),
        )
        if not download_url:
            retrieval_failed += 1
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
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {404, 410}:
                unavailable += 1
            else:
                retrieval_failed += 1
            continue
        except Exception:
            retrieval_failed += 1
            continue

        if len(blob) > max_bytes:
            oversized += 1
            continue

        safe_name = filename or (f"{file_id}.bin" if file_id else "attachment.bin")
        final_mime = (content_type or mime_type or "").split(";")[0].strip().lower()
        if final_mime.startswith("image/"):
            images.append((blob, safe_name))
        else:
            documents.append((blob, safe_name))

    for i in range(0, len(images), 10):
        batch = images[i : i + 10]
        if not batch:
            continue
        await authorize()
        try:
            if len(batch) == 1:
                result = await bot.send_photo(
                    chat_id=telegram_chat_id,
                    photo=batch[0][0],
                    message_thread_id=message_thread_id,
                    reply_to_message_id=reply_to_message_id,
                )
            else:
                result = await bot.send_media_group(
                    chat_id=telegram_chat_id,
                    media=[InputMediaPhoto(media=blob) for blob, _ in batch],
                    message_thread_id=message_thread_id,
                    reply_to_message_id=reply_to_message_id,
                )
            remember(result, len(batch))
        except BadRequest:
            # A rejected photo/album was not sent. Preserve its original bytes as files.
            documents.extend(batch)
        except (Forbidden, RetryAfter):
            rejected += len(batch)
        except Exception:
            unconfirmed += len(batch)
            continue

    for blob, safe_name in documents:
        bio = BytesIO(blob)
        bio.name = safe_name
        bio.seek(0)
        await authorize()
        try:
            result = await bot.send_document(
                chat_id=telegram_chat_id,
                message_thread_id=message_thread_id,
                document=bio,
                filename=safe_name,
                reply_to_message_id=reply_to_message_id,
            )
            remember(result)
        except (BadRequest, Forbidden, RetryAfter):
            rejected += 1
        except Exception:
            unconfirmed += 1
            continue

    notices = []
    for count, detail in (
        (unavailable, "is unavailable" if unavailable == 1 else "are unavailable"),
        (retrieval_failed, "could not be retrieved"),
        (rejected, "could not be sent"),
        (
            oversized,
            ("is too large to send" if oversized == 1 else "are too large to send")
            if text_fallback else "could not be sent",
        ),
    ):
        if count:
            notices.append(f"{count} {'file' if count == 1 else 'files'} {detail}.")
    if unconfirmed:
        notices.append(
            f"Delivery of {unconfirmed} {'file' if unconfirmed == 1 else 'files'} could not be confirmed."
        )
    if notices:
        await authorize()
        try:
            notice = await bot.send_message(
                chat_id=telegram_chat_id,
                message_thread_id=message_thread_id,
                text="\n".join(notices),
                reply_to_message_id=reply_to_message_id,
            )
            notice_id = getattr(notice, "message_id", None)
            if notice_id is not None and str(notice_id).strip():
                message_ids.append(str(notice_id).strip())
                if on_message_ids is not None:
                    on_message_ids(list(dict.fromkeys(message_ids)))
            else:
                unconfirmed += 1
        except Exception as exc:
            exc.telegram_message_ids = list(message_ids)
            raise
    return {
        "message_ids": list(dict.fromkeys(message_ids)),
        "delivery_unknown": bool(unconfirmed),
        "outcomes": {
            "sent": sent,
            "unavailable": unavailable,
            "retrieval_failed": retrieval_failed,
            "oversized": oversized,
            "rejected": rejected,
            "unconfirmed": unconfirmed,
        },
    }
