#!/usr/bin/env python3
from __future__ import annotations

import re
from typing import Final

TELEGRAM_BOT_TOKEN_HINT: Final[str] = (
    "Telegram bot tokens must use the BotFather format <bot_id>:<secret>."
)
TELEGRAM_BOT_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[0-9]{6,}:[A-Za-z0-9_-]{20,}$"
)
TELEGRAM_BOT_TOKEN_SECRET_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_-]+$")


def normalize_telegram_bot_token(token: object) -> str:
    return str(token or "").strip()


def telegram_bot_token_validation_error(token: object) -> str:
    normalized = normalize_telegram_bot_token(token)
    if not normalized:
        return "Value required."

    if ":" not in normalized:
        return f"{TELEGRAM_BOT_TOKEN_HINT} Re-copy the full token from @BotFather."

    bot_id, _, secret = normalized.partition(":")
    if not bot_id.isdigit():
        return (
            f"{TELEGRAM_BOT_TOKEN_HINT} "
            "The part before ':' must be the numeric bot ID."
        )

    if not secret:
        return (
            f"{TELEGRAM_BOT_TOKEN_HINT} "
            "The secret portion after ':' is missing."
        )

    if not TELEGRAM_BOT_TOKEN_SECRET_PATTERN.fullmatch(secret):
        return (
            f"{TELEGRAM_BOT_TOKEN_HINT} "
            "Only letters, numbers, underscores, and hyphens are allowed after ':'."
        )

    if len(secret) < 20:
        return (
            f"{TELEGRAM_BOT_TOKEN_HINT} "
            "The secret looks incomplete; re-copy it from @BotFather."
        )

    if not TELEGRAM_BOT_TOKEN_PATTERN.fullmatch(normalized):
        return f"{TELEGRAM_BOT_TOKEN_HINT} Re-copy the full token from @BotFather."

    return ""


def telegram_bot_token_looks_valid(token: object) -> bool:
    return telegram_bot_token_validation_error(token) == ""
