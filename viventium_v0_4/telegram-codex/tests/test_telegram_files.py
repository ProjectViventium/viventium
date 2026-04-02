from __future__ import annotations

from pathlib import Path

import pytest

from app.telegram_files import (
    StagedTelegramAttachment,
    build_attachment_prompt,
    send_local_files,
    split_message_and_attachment_paths,
)


class _FakeBot:
    def __init__(self) -> None:
        self.photos = []
        self.media_groups = []
        self.documents = []
        self.messages = []

    async def send_photo(self, **kwargs):
        photo = kwargs["photo"]
        self.photos.append({"name": Path(photo.name).name, **kwargs})

    async def send_document(self, **kwargs):
        document = kwargs["document"]
        self.documents.append({"name": Path(document.name).name, **kwargs})

    async def send_media_group(self, **kwargs):
        names = [Path(getattr(item.media, "name", "")).name for item in kwargs["media"]]
        self.media_groups.append({"names": names, **kwargs})

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)


def test_build_attachment_prompt_includes_attachment_context(tmp_path):
    path = tmp_path / "report.pdf"
    path.write_text("pdf", encoding="utf-8")
    attachments = [
        StagedTelegramAttachment(
            path=path,
            filename=path.name,
            mime_type="application/pdf",
            kind="file",
        )
    ]

    prompt = build_attachment_prompt(user_text="Summarize this", attachments=attachments)

    assert "Summarize this" in prompt
    assert "Attachment context:" in prompt
    assert str(path) in prompt
    assert "report.pdf" in prompt


def test_split_message_and_attachment_paths_removes_footer_and_filters_root(tmp_path):
    allowed = tmp_path / "workspace"
    allowed.mkdir()
    exported = allowed / "summary.txt"
    exported.write_text("done", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("nope", encoding="utf-8")

    message = (
        "Finished the task.\n\n"
        "Attachments:\n"
        f"- `{exported}`\n"
        f"- `{outside}`\n"
    )

    display_text, paths = split_message_and_attachment_paths(message, allowed_root=allowed)

    assert display_text == "Finished the task."
    assert paths == [exported.resolve()]


@pytest.mark.asyncio
async def test_send_local_files_sends_images_and_documents(tmp_path):
    bot = _FakeBot()
    image = tmp_path / "preview.png"
    image.write_bytes(b"png")
    document = tmp_path / "notes.pdf"
    document.write_bytes(b"pdf")

    await send_local_files(bot=bot, chat_id=123, paths=[image, document], reply_to_message_id=77)

    assert len(bot.media_groups) == 1
    assert len(bot.media_groups[0]["media"]) == 1
    assert len(bot.documents) == 1
    assert bot.documents[0]["name"] == "notes.pdf"


@pytest.mark.asyncio
async def test_send_local_files_reports_large_payloads(tmp_path):
    bot = _FakeBot()
    document = tmp_path / "huge.bin"
    document.write_bytes(b"123456")

    await send_local_files(
        bot=bot,
        chat_id=123,
        paths=[document],
        max_bytes=3,
        text_fallback=True,
    )

    assert len(bot.documents) == 0
    assert len(bot.messages) == 1
    assert "too large" in bot.messages[0]["text"]
