import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
import httpx
from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter, TimedOut

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
        self.photos = []
        self.documents = []
        self.messages = []
        self._message_id = 1000

    def receipt(self):
        self._message_id += 1
        return SimpleNamespace(message_id=self._message_id)

    async def send_media_group(self, **kwargs):
        assert 2 <= len(kwargs["media"]) <= 10
        self.media_groups.append(kwargs)
        return [self.receipt() for _ in kwargs["media"]]

    async def send_photo(self, **kwargs):
        self.photos.append(kwargs)
        return self.receipt()

    async def send_document(self, **kwargs):
        self.documents.append(kwargs)
        return self.receipt()

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)
        return self.receipt()


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
@pytest.mark.parametrize("image_count", [1, 2])
async def test_send_attachments_sends_photo_or_image_album(image_count):
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
        attachments=[{"file_id": f"file-{index}", "filename": f"x-{index}.png", "type": "image/png"}
                     for index in range(1, image_count + 1)],
        message_thread_id=None,
        reply_to_message_id=42,
        fetch_bytes=_fake_fetch_bytes,
    )

    assert captured["url"] == f"http://example.com/api/viventium/telegram/files/download/file-{image_count}"
    if image_count == 1:
        assert not context.bot.media_groups
        assert context.bot.photos[0]["photo"] == b"img-bytes"
        sent = context.bot.photos[0]
    else:
        assert not context.bot.photos
        assert len(context.bot.media_groups) == 1
        assert len(context.bot.media_groups[0]["media"]) == 2
        sent = context.bot.media_groups[0]
    assert sent["reply_to_message_id"] == 42
    assert len(context.bot.documents) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("mime", ["application/pdf", "audio/wav", "application/x-custom"])
async def test_send_attachments_sends_document(mime):
    context = _FakeContext()
    base_url = "http://example.com"
    secret = "s"

    async def _fake_fetch_bytes(**_kwargs):
        return b"synthetic-file-bytes", mime

    await send_librechat_attachments(
        bot=context.bot,
        base_url=base_url,
        secret=secret,
        telegram_user_id="1",
        telegram_username="u",
        telegram_chat_id="123",
        attachments=[{"file_id": "file-2", "filename": "result.bin", "type": mime}],
        message_thread_id=None,
        reply_to_message_id=42,
        fetch_bytes=_fake_fetch_bytes,
    )

    assert len(context.bot.media_groups) == 0
    assert len(context.bot.documents) == 1
    sent = context.bot.documents[0]
    assert sent["filename"] == "result.bin"
    assert isinstance(sent["document"], BytesIO)
    assert sent["document"].getvalue() == b"synthetic-file-bytes"


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
    # 11 unique images -> an album of 10 and a single photo.
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
    assert len(context.bot.media_groups) == 1
    assert len(context.bot.media_groups[0]["media"]) == 10
    assert len(context.bot.photos) == 1
    assert context.bot.photos[0]["photo"] == b"img"


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


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 404, 410, 503])
async def test_unavailable_attachment_reports_one_notice_without_losing_successes(status):
    context = _FakeContext()

    async def fetch(**kwargs):
        if kwargs["url"].endswith("unavailable"):
            raise httpx.HTTPStatusError(
                "synthetic-private-error-detail",
                request=httpx.Request("GET", "https://example.invalid/file"),
                response=httpx.Response(status),
            )
        return b"%PDF-synthetic", "application/pdf"

    await send_librechat_attachments(
        bot=context.bot,
        base_url="https://example.invalid",
        secret="synthetic",
        telegram_user_id="owner",
        telegram_username="",
        telegram_chat_id="chat",
        attachments=[
            {"file_id": "available", "filename": "report.pdf"},
            {"file_id": "unavailable", "filename": "unavailable.pdf"},
            {"file_id": "unavailable", "filename": "duplicate.pdf"},
        ],
        message_thread_id=7,
        reply_to_message_id=42,
        fetch_bytes=fetch,
    )

    assert [item["filename"] for item in context.bot.documents] == ["report.pdf"]
    assert len(context.bot.messages) == 1
    notice = context.bot.messages[0]
    assert notice["chat_id"] == "chat"
    assert notice["message_thread_id"] == 7
    assert notice["reply_to_message_id"] == 42
    assert "1 file" in notice["text"]
    assert "synthetic-private-error-detail" not in notice["text"]
    assert ("unavailable" in notice["text"]) == (status in {404, 410})
    assert "deleted" not in notice["text"]


@pytest.mark.asyncio
async def test_document_and_album_rejections_produce_one_delivery_notice():
    context = _FakeContext()

    async def reject(**_kwargs):
        raise RuntimeError("synthetic-private-error-detail")

    context.bot.send_document = reject
    context.bot.send_media_group = reject
    context.bot.send_photo = reject

    async def fetch(**kwargs):
        return (b"image", "image/png") if kwargs["url"].endswith("image") else (b"pdf", "application/pdf")

    await send_librechat_attachments(
        bot=context.bot,
        base_url="https://example.invalid",
        secret="synthetic",
        telegram_user_id="owner",
        telegram_username="",
        telegram_chat_id="chat",
        attachments=[{"file_id": "image"}, {"file_id": "document"}],
        message_thread_id=None,
        reply_to_message_id=42,
        fetch_bytes=fetch,
    )

    assert len(context.bot.messages) == 1
    assert "2 files" in context.bot.messages[0]["text"]
    assert "could not be confirmed" in context.bot.messages[0]["text"]
    assert "synthetic-private-error-detail" not in context.bot.messages[0]["text"]


@pytest.mark.asyncio
async def test_document_timeout_does_not_claim_the_file_was_not_delivered():
    from telegram.error import TimedOut

    context = _FakeContext()

    async def timeout(**_kwargs):
        raise TimedOut()

    context.bot.send_document = timeout

    async def fetch(**_kwargs):
        return b"pdf", "application/pdf"

    await send_librechat_attachments(
        bot=context.bot,
        base_url="https://example.invalid",
        secret="synthetic",
        telegram_user_id="owner",
        telegram_username="",
        telegram_chat_id="chat",
        attachments=[{"file_id": "document"}],
        message_thread_id=None,
        reply_to_message_id=42,
        fetch_bytes=fetch,
    )

    assert len(context.bot.messages) == 1
    assert "could not be confirmed" in context.bot.messages[0]["text"]
    assert "not delivered" not in context.bot.messages[0]["text"]


# === VIVENTIUM START === Telegram rejects unsupported photos, not arbitrary file bytes.
@pytest.mark.asyncio
@pytest.mark.parametrize("image_count", [1, 2])
async def test_rejected_photo_or_album_sends_original_named_files(image_count):
    bot = _FakeTelegramBot()
    attempts = []

    async def reject(**kwargs):
        if "media" in kwargs:
            assert 2 <= len(kwargs["media"]) <= 10
        attempts.append(kwargs)
        raise BadRequest("Photo_invalid_dimensions")

    bot.send_photo = reject
    bot.send_media_group = reject

    async def fetch(**kwargs):
        return kwargs["url"].rsplit("/", 1)[-1].encode(), "image/svg+xml"

    await send_librechat_attachments(
        bot=bot, base_url="https://example.invalid", secret="synthetic",
        telegram_user_id="owner", telegram_username="", telegram_chat_id="chat",
        attachments=[{"file_id": f"image-{i}", "filename": f"image-{i}.svg"}
                     for i in range(image_count)],
        message_thread_id=7, reply_to_message_id=42, fetch_bytes=fetch,
    )

    assert len(attempts) == 1
    assert [item["filename"] for item in bot.documents] == [f"image-{i}.svg" for i in range(image_count)]
    assert [item["document"].getvalue() for item in bot.documents] == [f"image-{i}".encode() for i in range(image_count)]
    assert all(item["message_thread_id"] == 7 and item["reply_to_message_id"] == 42
               for item in bot.documents)
    assert not bot.messages


@pytest.mark.asyncio
@pytest.mark.parametrize(("error", "detail"), [
    (TimedOut(), "could not be confirmed"),
    (NetworkError("synthetic transport interruption"), "could not be confirmed"),
    (Forbidden("synthetic blocked bot"), "could not be sent"),
    (RetryAfter(1), "could not be sent"),
])
async def test_photo_failure_does_not_retry_ambiguous_or_other_rejections(error, detail):
    bot = _FakeTelegramBot()
    attempts = []

    async def fail(**kwargs):
        attempts.append(kwargs)
        raise error

    bot.send_photo = fail

    async def fetch(**_kwargs):
        return b"image", "image/png"

    receipt = await send_librechat_attachments(
        bot=bot, base_url="https://example.invalid", secret="synthetic",
        telegram_user_id="owner", telegram_username="", telegram_chat_id="chat",
        attachments=[{"file_id": "image", "filename": "image.png"}],
        message_thread_id=None, reply_to_message_id=42, fetch_bytes=fetch,
    )

    assert len(attempts) == 1
    assert not bot.documents and not bot.media_groups
    assert len(bot.messages) == 1
    assert detail in bot.messages[0]["text"]
    assert "1 file" in bot.messages[0]["text"]

    assert receipt["delivery_unknown"] == isinstance(error, (TimedOut, NetworkError))
    assert receipt["outcomes"]["unconfirmed"] == int(isinstance(error, (TimedOut, NetworkError)))
    assert receipt["outcomes"]["rejected"] == int(isinstance(error, (Forbidden, RetryAfter)))
    assert receipt["message_ids"] == ["1001"]


@pytest.mark.asyncio
@pytest.mark.parametrize("document_error", [BadRequest("synthetic rejected file"), Forbidden("synthetic blocked bot")])
async def test_failed_photo_document_fallback_counts_definite_rejection_once(document_error):
    bot = _FakeTelegramBot()
    document_attempts = []

    async def reject_photo(**_kwargs):
        raise BadRequest("Photo_invalid_dimensions")

    async def reject_document(**kwargs):
        document_attempts.append(kwargs)
        raise document_error

    bot.send_photo = reject_photo
    bot.send_document = reject_document

    async def fetch(**_kwargs):
        return b"original image", "image/png"

    await send_librechat_attachments(
        bot=bot, base_url="https://example.invalid", secret="synthetic",
        telegram_user_id="owner", telegram_username="", telegram_chat_id="chat",
        attachments=[{"file_id": "image", "filename": "image.png"}],
        message_thread_id=None, reply_to_message_id=42, fetch_bytes=fetch,
    )

    assert len(document_attempts) == 1
    assert document_attempts[0]["document"].getvalue() == b"original image"
    assert [notice["text"] for notice in bot.messages] == ["1 file could not be sent."]


@pytest.mark.asyncio
@pytest.mark.parametrize("size_hint", [None, 1])
async def test_actual_download_size_enforces_existing_file_bound(size_hint):
    bot = _FakeTelegramBot()
    attachment = {"file_id": "large", "filename": "result.bin"}
    if size_hint is not None:
        attachment["bytes"] = size_hint

    async def fetch(**_kwargs):
        return b"12345678901", "application/x-custom"

    await send_librechat_attachments(
        bot=bot, base_url="https://example.invalid", secret="synthetic",
        telegram_user_id="owner", telegram_username="", telegram_chat_id="chat",
        attachments=[attachment], message_thread_id=None, reply_to_message_id=42,
        fetch_bytes=fetch, max_bytes=10, text_fallback=True,
    )

    assert not bot.documents and not bot.photos and not bot.media_groups
    assert [notice["text"] for notice in bot.messages] == ["1 file is too large to send."]
# === VIVENTIUM END ===


# === VIVENTIUM START === Selected-file failure cannot disappear or invent a download.
@pytest.mark.asyncio
@pytest.mark.parametrize(("code", "notice"), [
    ("native_output_file_unavailable", "1 file is unavailable."),
    ("native_output_file_content_mismatch", "1 file is unavailable."),
    ("native_output_file_size_limit", "1 file is too large to send."),
])
async def test_native_output_failure_reuses_typed_notice_without_fetch(code, notice):
    bot = _FakeTelegramBot()
    async def fetch_bytes(**kwargs):
        raise AssertionError("unavailable receipt cannot fetch")
    receipt = {"filename": "result.csv", "messageId": "answer", "nativeOutputFile": {
        "version": 1, "status": "unavailable", "code": code}}
    await send_librechat_attachments(bot=bot, base_url="http://core.test", secret="synthetic",
        telegram_user_id="1", telegram_username="synthetic", telegram_chat_id="2",
        attachments=[receipt, dict(receipt)], message_thread_id=None, reply_to_message_id=3,
        fetch_bytes=fetch_bytes, text_fallback=True)
    assert not bot.documents and not bot.media_groups
    assert [message["text"] for message in bot.messages] == [notice]

@pytest.mark.asyncio
async def test_native_output_siblings_use_existing_download_document_bytes():
    bot = _FakeTelegramBot()
    calls = []
    async def fetch_bytes(**kwargs):
        calls.append(kwargs["url"])
        return b"item,value\nAster,10\n", "text/csv"
    unavailable = {"filename": "large.csv", "nativeOutputFile": {
        "version": 1, "status": "unavailable", "code": "native_output_file_size_limit"}}
    await send_librechat_attachments(bot=bot, base_url="http://core.test", secret="synthetic",
        telegram_user_id="1", telegram_username="synthetic", telegram_chat_id="2",
        attachments=[unavailable, {"file_id": "native_one", "filename": "result.csv", "type": "text/csv"},
            {"file_id": "native_two", "filename": "copy.csv", "type": "text/csv"}],
        message_thread_id=None, reply_to_message_id=3, fetch_bytes=fetch_bytes, text_fallback=True)
    assert calls == ["http://core.test/api/viventium/telegram/files/download/native_one",
                     "http://core.test/api/viventium/telegram/files/download/native_two"]
    assert [item["filename"] for item in bot.documents] == ["result.csv", "copy.csv"]
    assert [item["document"].getvalue() for item in bot.documents] == [b"item,value\nAster,10\n"] * 2
    assert bot.messages[0]["text"] == "1 file is too large to send."
# === VIVENTIUM END ===


@pytest.mark.asyncio
async def test_attachment_receipt_gates_album_document_and_unavailable_notice():
    bot = _FakeTelegramBot()
    events, progress = [], []

    async def authorize():
        events.append("permit")
        return True

    for name in ("send_media_group", "send_document", "send_message"):
        method = getattr(bot, name)
        async def observed(_name=name, _method=method, **kwargs):
            events.append(_name)
            return await _method(**kwargs)
        setattr(bot, name, observed)

    async def fetch(**kwargs):
        return b"original", "image/png" if "/image" in kwargs["url"] else "application/x-custom"

    receipt = await send_librechat_attachments(
        bot=bot, base_url="http://core.test", secret="synthetic",
        telegram_user_id="1", telegram_username="", telegram_chat_id="2",
        attachments=[{"file_id": "image-1"}, {"file_id": "image-2"},
            {"file_id": "document", "filename": "result.bin"},
            {"filename": "missing.bin", "nativeOutputFile": {
                "version": 1, "status": "unavailable", "code": "native_output_file_unavailable"}}],
        message_thread_id=7, reply_to_message_id=None, fetch_bytes=fetch,
        before_side_effect=authorize, on_message_ids=progress.append,
    )
    assert events == ["permit", "send_media_group", "permit", "send_document", "permit", "send_message"]
    assert receipt["message_ids"] == ["1001", "1002", "1003", "1004"]
    assert receipt["delivery_unknown"] is False
    assert receipt["outcomes"] == {"sent": 3, "unavailable": 1, "retrieval_failed": 0,
        "oversized": 0, "rejected": 0, "unconfirmed": 0}

    assert progress == [["1001", "1002"], ["1001", "1002", "1003"],
        ["1001", "1002", "1003", "1004"]]


@pytest.mark.asyncio
async def test_attachment_lost_authority_retains_first_file_receipt_without_second_send():
    bot = _FakeTelegramBot()
    renewals = 0

    async def authorize():
        nonlocal renewals
        renewals += 1
        if renewals == 2:
            raise RuntimeError("synthetic lease lost")
        return True

    async def fetch(**kwargs):
        return b"original", "application/x-custom"

    with pytest.raises(RuntimeError, match="synthetic lease lost") as failure:
        await send_librechat_attachments(
            bot=bot, base_url="http://core.test", secret="synthetic",
            telegram_user_id="1", telegram_username="", telegram_chat_id="2",
            attachments=[{"file_id": "one"}, {"file_id": "two"}],
            message_thread_id=None, reply_to_message_id=None, fetch_bytes=fetch,
            before_side_effect=authorize,
        )
    assert failure.value.telegram_message_ids == ["1001"]
    assert len(bot.documents) == 1
    assert not bot.messages


@pytest.mark.asyncio
async def test_rejected_photo_fallback_renews_before_original_document():
    bot = _FakeTelegramBot()
    events = []

    async def authorize():
        events.append("permit")
        return True

    async def reject_photo(**kwargs):
        events.append("photo")
        raise BadRequest("Photo_invalid_dimensions")

    original_document = bot.send_document
    async def document(**kwargs):
        events.append("document")
        return await original_document(**kwargs)

    async def fetch(**kwargs):
        return b"original", "image/svg+xml"

    bot.send_photo = reject_photo
    bot.send_document = document
    receipt = await send_librechat_attachments(
        bot=bot, base_url="http://core.test", secret="synthetic",
        telegram_user_id="1", telegram_username="", telegram_chat_id="2",
        attachments=[{"file_id": "image", "filename": "vector.svg"}],
        message_thread_id=None, reply_to_message_id=None, fetch_bytes=fetch,
        before_side_effect=authorize,
    )
    assert events == ["permit", "photo", "permit", "document"]
    assert receipt["message_ids"] == ["1001"]
    assert receipt["outcomes"]["sent"] == 1
    assert receipt["delivery_unknown"] is False


@pytest.mark.asyncio
async def test_attachment_notice_failure_retains_confirmed_file_ids_without_replay():
    bot = _FakeTelegramBot()
    async def fetch(**kwargs):
        return b"original", "application/x-custom"
    async def refuse_notice(**kwargs):
        raise Forbidden("synthetic blocked notice")
    bot.send_message = refuse_notice
    with pytest.raises(Forbidden) as failure:
        await send_librechat_attachments(
            bot=bot, base_url="http://core.test", secret="synthetic",
            telegram_user_id="1", telegram_username="", telegram_chat_id="2",
            attachments=[{"file_id": "ready"}, {"filename": "missing.bin", "nativeOutputFile": {
                "version": 1, "status": "unavailable", "code": "native_output_file_unavailable"}}],
            message_thread_id=None, reply_to_message_id=None, fetch_bytes=fetch,
        )
    assert failure.value.telegram_message_ids == ["1001"]
    assert len(bot.documents) == 1
