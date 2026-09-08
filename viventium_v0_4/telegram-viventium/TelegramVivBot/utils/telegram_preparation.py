# === VIVENTIUM START ===
def capture_telegram_preparation(update, *, title="", args=None, has_command=False):
    """Keep only the Telegram references consumed by input preparation and reply provenance."""
    kind = "edited_message" if getattr(update, "edited_message", None) else "message"
    message = getattr(update, kind, None)
    if message is None or getattr(update, "callback_query", None) is not None:
        raise ValueError("Input preparation requires an original Telegram message")

    def select(value, fields):
        return {key: value[key] for key in fields if key in value}

    def message_reference(value, *, include_reply):
        result = select(value, (
            "message_id", "date", "text", "caption", "message_thread_id",
            "is_topic_message", "media_group_id",
        ))
        result["chat"] = select(value.get("chat", {}), ("id", "type"))
        if value.get("from"):
            result["from"] = select(value["from"], ("id", "is_bot", "first_name", "username"))
        if value.get("sender_chat"):
            result["sender_chat"] = select(value["sender_chat"], ("id", "type"))
        media_fields = (
            "file_id", "file_unique_id", "file_name", "mime_type", "file_size",
            "width", "height", "duration", "length", "type", "is_animated", "is_video",
        )
        for media_kind in ("voice", "video_note", "document", "audio", "video", "animation", "sticker"):
            if value.get(media_kind):
                result[media_kind] = select(value[media_kind], media_fields)
        if value.get("photo"):
            result["photo"] = [select(value["photo"][-1], media_fields)]
        if include_reply and value.get("reply_to_message"):
            result["reply_to_message"] = message_reference(value["reply_to_message"], include_reply=False)
        return result

    return {
        "version": 1,
        "updateId": update.update_id,
        "messageKind": kind,
        "message": message_reference(message.to_dict(), include_reply=True),
        "command": {"title": title, "args": list(args or []), "hasCommand": bool(has_command)},
    }


def restore_telegram_preparation(preparation, bot, identity):
    """Reconstruct the existing parser input only within Core's authenticated source scope."""
    from telegram import Update

    if not isinstance(preparation, dict) or preparation.get("version") != 1:
        raise ValueError("Unsupported Telegram preparation reference")
    kind = preparation.get("messageKind")
    if kind not in {"message", "edited_message"} or not isinstance(preparation.get("message"), dict):
        raise ValueError("Invalid Telegram preparation message")
    value = preparation["message"]
    expected = (
        str(identity.get("telegramUserId") or ""),
        str(identity.get("telegramChatId") or ""),
        str(identity.get("telegramMessageThreadId") or ""),
        str(identity.get("sourceSequence") or ""),
    )
    actual = (
        str((value.get("from") or {}).get("id") or ""),
        str((value.get("chat") or {}).get("id") or ""),
        str(value.get("message_thread_id") or ""),
        str(value.get("message_id") or ""),
    )
    if actual != expected or not all((expected[0], expected[1], expected[3])):
        raise ValueError("Telegram preparation source scope mismatch")
    return Update.de_json({"update_id": preparation["updateId"], kind: value}, bot)
# === VIVENTIUM END ===
