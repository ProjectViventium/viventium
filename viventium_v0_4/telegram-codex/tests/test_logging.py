from __future__ import annotations

import logging

from app.main import TelegramTokenRedactionFilter, redact_telegram_bot_tokens


def test_redact_telegram_bot_tokens_redacts_bot_api_urls():
    raw = "POST https://api.telegram.org/bot1234567890:ABCdef_1234567890-SECRET_TOKEN/sendMessage"

    redacted = redact_telegram_bot_tokens(raw)

    assert redacted == "POST https://api.telegram.org/bot[REDACTED]/sendMessage"
    assert "SECRET_TOKEN" not in redacted


def test_telegram_token_redaction_filter_redacts_message_args():
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="HTTP Request: %s",
        args=(
            "POST https://api.telegram.org/bot1234567890:ABCdef_1234567890-SECRET_TOKEN/getUpdates",
        ),
        exc_info=None,
    )

    assert TelegramTokenRedactionFilter().filter(record) is True

    rendered = record.getMessage()
    assert rendered == "HTTP Request: POST https://api.telegram.org/bot[REDACTED]/getUpdates"
    assert "SECRET_TOKEN" not in rendered
