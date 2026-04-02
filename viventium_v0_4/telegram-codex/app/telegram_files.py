from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from telegram import InputMediaPhoto


MAX_TELEGRAM_FILE_BYTES = 49_000_000
MAX_TELEGRAM_PHOTO_BYTES = 9_500_000

_ATTACHMENTS_HEADER_RE = re.compile(r"^\s*Attachments\s*:\s*$", re.IGNORECASE)
_BACKTICK_PATH_RE = re.compile(r"`(/[^`]+)`")
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class StagedTelegramAttachment:
    path: Path
    filename: str
    mime_type: str
    kind: str


def sanitize_attachment_name(name: str, *, default_stem: str = "attachment", default_suffix: str = "") -> str:
    raw_name = Path(str(name or "")).name.strip()
    if not raw_name:
        raw_name = default_stem + default_suffix

    stem = Path(raw_name).stem or default_stem
    suffix = Path(raw_name).suffix or default_suffix
    safe_stem = _SAFE_NAME_RE.sub("_", stem).strip("._") or default_stem
    safe_suffix = _SAFE_NAME_RE.sub("", suffix)
    if safe_suffix and not safe_suffix.startswith("."):
        safe_suffix = f".{safe_suffix}"
    return f"{safe_stem}{safe_suffix}"


def build_staged_attachment_path(*, project_root: Path, chat_id: int, message_id: int, filename: str) -> Path:
    attachment_dir = project_root / ".telegram_codex" / "attachments" / str(chat_id) / str(message_id)
    attachment_dir.mkdir(parents=True, exist_ok=True)
    return attachment_dir / filename


def default_extension_for_mime(mime_type: str) -> str:
    guessed = mimetypes.guess_extension((mime_type or "").strip(), strict=False) or ""
    if guessed == ".jpe":
        return ".jpg"
    return guessed


def build_attachment_prompt(*, user_text: str, attachments: list[StagedTelegramAttachment]) -> str:
    prompt = (user_text or "").strip() or "Please review the attached file(s)."
    if not attachments:
        return prompt

    lines = [prompt, "", "Attachment context:"]
    for attachment in attachments:
        mime_type = attachment.mime_type or "unknown"
        lines.append(
            f"- {attachment.kind}: {attachment.filename} ({mime_type}) available at {attachment.path}"
        )
    lines.extend(
        [
            "",
            "Use the local attachment path(s) above directly. Images are also attached to the Codex turn when supported.",
        ]
    )
    return "\n".join(lines).strip()


def summarize_attachments(attachments: list[StagedTelegramAttachment]) -> list[str]:
    return [f"{attachment.kind}: {attachment.filename}" for attachment in attachments]


def split_message_and_attachment_paths(text: str, *, allowed_root: Path) -> tuple[str, list[Path]]:
    if not text:
        return "", []

    lines = text.splitlines()
    kept_lines: list[str] = []
    raw_paths: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if not _ATTACHMENTS_HEADER_RE.match(line.strip()):
            kept_lines.append(line)
            index += 1
            continue

        section_paths: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            candidate = lines[cursor]
            stripped = candidate.strip()
            if not stripped:
                if section_paths:
                    cursor += 1
                    break
                cursor += 1
                continue

            extracted = _extract_absolute_path(candidate)
            if extracted:
                section_paths.append(extracted)
                cursor += 1
                continue
            break

        if section_paths:
            raw_paths.extend(section_paths)
            index = cursor
            continue

        kept_lines.append(line)
        index += 1

    cleaned_text = "\n".join(kept_lines).strip()
    return cleaned_text, _resolve_allowed_files(raw_paths, allowed_root=allowed_root)


def _extract_absolute_path(line: str) -> str | None:
    backtick_match = _BACKTICK_PATH_RE.search(line)
    if backtick_match:
        return backtick_match.group(1).strip()

    stripped = line.strip()
    while stripped.startswith(("-", "•", "*")):
        stripped = stripped[1:].strip()
    if stripped.startswith("/"):
        return stripped
    return None


def _resolve_allowed_files(raw_paths: list[str], *, allowed_root: Path) -> list[Path]:
    root = allowed_root.expanduser().resolve()
    results: list[Path] = []
    seen: set[Path] = set()

    for raw_path in raw_paths:
        try:
            candidate = Path(raw_path).expanduser().resolve()
        except OSError:
            continue
        if not candidate.is_file():
            continue
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        results.append(candidate)

    return results


async def send_local_files(
    *,
    bot: Any,
    chat_id: int,
    paths: list[Path],
    reply_to_message_id: int | None = None,
    max_bytes: int = MAX_TELEGRAM_FILE_BYTES,
    text_fallback: bool = False,
) -> None:
    seen: set[Path] = set()
    images: list[Path] = []
    documents: list[Path] = []

    for path in paths:
        resolved = path.expanduser().resolve()
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)

        size_bytes = resolved.stat().st_size
        if size_bytes > max_bytes:
            if text_fallback:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"Attachment ready locally but too large for Telegram: {resolved.name}",
                    reply_to_message_id=reply_to_message_id,
                )
            continue

        mime_type, _ = mimetypes.guess_type(resolved.name)
        if (mime_type or "").startswith("image/") and size_bytes <= MAX_TELEGRAM_PHOTO_BYTES:
            images.append(resolved)
        else:
            documents.append(resolved)

    for start in range(0, len(images), 10):
        batch = images[start : start + 10]
        if not batch:
            continue
        handles: list[BytesIO] = []
        try:
            media_group = []
            for image_path in batch:
                blob = BytesIO(image_path.read_bytes())
                blob.name = image_path.name
                blob.seek(0)
                handles.append(blob)
                media_group.append(InputMediaPhoto(media=blob))
            await bot.send_media_group(
                chat_id=chat_id,
                media=media_group,
                reply_to_message_id=reply_to_message_id,
            )
        except Exception:
            for image_path in batch:
                try:
                    with image_path.open("rb") as file_handle:
                        await bot.send_photo(
                            chat_id=chat_id,
                            photo=file_handle,
                            caption=image_path.name,
                            reply_to_message_id=reply_to_message_id,
                        )
                except Exception:
                    if text_fallback:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=f"Attachment delivery failed for {image_path.name}. The file still exists locally.",
                            reply_to_message_id=reply_to_message_id,
                        )
        finally:
            for handle in handles:
                handle.close()

    for resolved in documents:
        try:
            with resolved.open("rb") as file_handle:
                await bot.send_document(
                    chat_id=chat_id,
                    document=file_handle,
                    filename=resolved.name,
                    reply_to_message_id=reply_to_message_id,
                )
        except Exception:
            if text_fallback:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"Attachment delivery failed for {resolved.name}. The file still exists locally.",
                    reply_to_message_id=reply_to_message_id,
                )
