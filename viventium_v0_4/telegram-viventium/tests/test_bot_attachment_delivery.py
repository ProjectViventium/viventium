import sys
from io import BytesIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "TelegramVivBot"

# Mirror prod import semantics (`cd TelegramVivBot && python bot.py`) so `utils.*` resolves.
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from utils import librechat_attachments as attachments_module  # noqa: E402
from utils.librechat_attachments import (  # noqa: E402
    fetch_librechat_bytes,
    send_librechat_attachments,
)


class _FakeTelegramBot:
    def __init__(self) -> None:
        self.media_groups = []
        self.documents = []
        self.messages = []

    async def send_media_group(self, **kwargs):
        self.media_groups.append(kwargs)

    async def send_document(self, **kwargs):
        self.documents.append(kwargs)

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)


class _FakeContext:
    def __init__(self) -> None:
        self.bot = _FakeTelegramBot()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("url", "expected_options"),
    [
        (
            "http://127.0.0.1:3180/api/viventium/telegram/files/download/file-1",
            {"trust_env": False, "verify": False},
        ),
        ("https://example.com/download/file-1", {}),
    ],
)
async def test_attachment_download_applies_loopback_http_client_policy(
    monkeypatch,
    url,
    expected_options,
):
    captured = {}

    class _FakeResponse:
        content = b"fixture"
        headers = {"content-type": "application/octet-stream"}

        @staticmethod
        def raise_for_status():
            return None

    class _FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            return _FakeResponse()

    monkeypatch.setattr(attachments_module.httpx, "AsyncClient", _FakeClient)

    content, content_type = await fetch_librechat_bytes(
        base_url=url.split("/api", 1)[0],
        secret="synthetic-secret",
        url=url,
        telegram_user_id="1",
        telegram_username="synthetic",
        telegram_chat_id="2",
    )

    assert content == b"fixture"
    assert content_type == "application/octet-stream"
    observed_options = {
        key: captured[key]
        for key in ("trust_env", "verify")
        if key in captured
    }
    assert observed_options == expected_options


@pytest.mark.asyncio
async def test_send_attachments_sends_image_album(monkeypatch):
    context = _FakeContext()
    base_url = "http://example.com"
    secret = "s"

    captured = {}

    async def _fake_fetch_bytes(**kwargs):
        captured["url"] = kwargs["url"]
        return b"img-bytes", "image/png"

    await send_librechat_attachments(
        bot=context.bot,
        base_url=base_url,
        secret=secret,
        telegram_user_id="1",
        telegram_username="u",
        telegram_chat_id="123",
        attachments=[{"file_id": "file-1", "filename": "x.png", "type": "image/png"}],
        message_thread_id=None,
        reply_to_message_id=42,
        fetch_bytes=_fake_fetch_bytes,
    )

    assert captured["url"] == "http://example.com/api/viventium/telegram/files/download/file-1"
    assert len(context.bot.media_groups) == 1
    assert len(context.bot.media_groups[0]["media"]) == 1
    assert len(context.bot.documents) == 0


@pytest.mark.asyncio
async def test_send_attachments_sends_document(monkeypatch):
    context = _FakeContext()
    base_url = "http://example.com"
    secret = "s"

    async def _fake_fetch_bytes(**_kwargs):
        return b"%PDF-1.4", "application/pdf"

    await send_librechat_attachments(
        bot=context.bot,
        base_url=base_url,
        secret=secret,
        telegram_user_id="1",
        telegram_username="u",
        telegram_chat_id="123",
        attachments=[{"file_id": "file-2", "filename": "doc.pdf", "type": "application/pdf"}],
        message_thread_id=None,
        reply_to_message_id=42,
        fetch_bytes=_fake_fetch_bytes,
    )

    assert len(context.bot.media_groups) == 0
    assert len(context.bot.documents) == 1
    sent = context.bot.documents[0]
    assert sent["filename"] == "doc.pdf"
    assert isinstance(sent["document"], BytesIO)


@pytest.mark.asyncio
async def test_send_attachments_dedupes_and_batches(monkeypatch):
    context = _FakeContext()
    base_url = "http://example.com"
    secret = "s"

    calls = {"n": 0}

    async def _fake_fetch_bytes(**_kwargs):
        calls["n"] += 1
        return b"img", "image/png"

    attachments = []
    # 11 unique images -> 2 albums (10 + 1)
    for i in range(11):
        attachments.append({"file_id": f"img-{i}", "filename": f"{i}.png", "type": "image/png"})
    # duplicate should be skipped (no extra download)
    attachments.append({"file_id": "img-0", "filename": "dup.png", "type": "image/png"})

    await send_librechat_attachments(
        bot=context.bot,
        base_url=base_url,
        secret=secret,
        telegram_user_id="1",
        telegram_username="u",
        telegram_chat_id="123",
        attachments=attachments,
        message_thread_id=None,
        reply_to_message_id=42,
        fetch_bytes=_fake_fetch_bytes,
    )

    assert calls["n"] == 11
    assert len(context.bot.media_groups) == 2
    assert len(context.bot.media_groups[0]["media"]) == 10
    assert len(context.bot.media_groups[1]["media"]) == 1


@pytest.mark.asyncio
async def test_send_attachments_skips_large_files_and_optional_text_fallback(monkeypatch):
    context = _FakeContext()
    base_url = "http://example.com"
    secret = "s"

    calls = {"n": 0}

    async def _fake_fetch_bytes(**_kwargs):
        calls["n"] += 1
        return b"img", "image/png"

    await send_librechat_attachments(
        bot=context.bot,
        base_url=base_url,
        secret=secret,
        telegram_user_id="1",
        telegram_username="u",
        telegram_chat_id="123",
        attachments=[{"file_id": "big", "filename": "big.png", "bytes": 99999, "type": "image/png"}],
        message_thread_id=None,
        reply_to_message_id=42,
        max_bytes=10,
        text_fallback=True,
        fetch_bytes=_fake_fetch_bytes,
    )

    # Should not attempt download; should emit text fallback notice.
    assert calls["n"] == 0
    assert len(context.bot.messages) == 1


@pytest.mark.asyncio
async def test_send_attachments_rewrites_code_download_path_when_missing_file_id(monkeypatch):
    context = _FakeContext()
    base_url = "http://example.com"
    secret = "s"

    captured = {}

    async def _fake_fetch_bytes(**kwargs):
        captured["url"] = kwargs["url"]
        return b"csv", "text/plain"

    session_id = "a" * 21
    file_id = "b" * 21
    filepath = f"/api/files/code/download/{session_id}/{file_id}"

    await send_librechat_attachments(
        bot=context.bot,
        base_url=base_url,
        secret=secret,
        telegram_user_id="1",
        telegram_username="u",
        telegram_chat_id="123",
        attachments=[{"filepath": filepath, "filename": "out.csv"}],
        message_thread_id=None,
        reply_to_message_id=42,
        fetch_bytes=_fake_fetch_bytes,
    )

    assert (
        captured["url"]
        == f"http://example.com/api/viventium/telegram/files/code/download/{session_id}/{file_id}"
    )
    assert len(context.bot.documents) == 1
    assert context.bot.documents[0]["filename"] == "out.csv"
