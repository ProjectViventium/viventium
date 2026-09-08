import importlib.util
import json
import unittest
from pathlib import Path

from telegram import Update


SOURCE = Path(__file__).resolve().parents[1] / "TelegramVivBot/utils/telegram_preparation.py"
spec = importlib.util.spec_from_file_location("telegram_preparation", SOURCE)
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)


class TelegramPreparationTests(unittest.TestCase):
    def message(self, **values):
        return {
            "message_id": 42, "date": 1700000000,
            "chat": {"id": -100, "type": "supergroup", "title": "Unneeded title"},
            "from": {"id": 7, "is_bot": False, "first_name": "Example", "username": "example"},
            "message_thread_id": 8, "is_topic_message": True,
            **values,
        }

    def identity(self, **values):
        return {"telegramUserId": "7", "telegramChatId": "-100",
                "telegramMessageThreadId": "8", "sourceSequence": 42, **values}

    def test_voice_caption_and_reply_survive_json_roundtrip_without_extra_context(self):
        reply = self.message(message_id=40, text="Earlier exact words", document={
            "file_id": "reply-file", "file_unique_id": "reply-unique",
            "file_name": "reference.pdf", "mime_type": "application/pdf",
        }, reply_to_message=self.message(message_id=39, text="Do not retain this ancestor"))
        value = self.message(caption="Original caption", voice={
            "file_id": "voice-file", "file_unique_id": "voice-unique", "duration": 25,
        }, reply_to_message=reply, forward_origin={"type": "hidden_user", "date": 100,
                                                 "sender_user_name": "Unneeded name"})
        original = Update.de_json({"update_id": 20, "edited_message": value}, None)
        retained = owner.capture_telegram_preparation(original, args=["original", "args"], has_command=True)
        retained = json.loads(json.dumps(retained))
        recovered = owner.restore_telegram_preparation(retained, None, self.identity())
        self.assertEqual(recovered.update_id, original.update_id)
        self.assertEqual(recovered.edited_message.caption, original.edited_message.caption)
        self.assertEqual(recovered.edited_message.voice.file_id, "voice-file")
        self.assertEqual(recovered.edited_message.reply_to_message.document.file_id, "reply-file")
        self.assertEqual(recovered.edited_message.reply_to_message.text, "Earlier exact words")
        self.assertIsNone(recovered.edited_message.reply_to_message.reply_to_message)
        self.assertNotIn("forward_origin", retained["message"])
        self.assertNotIn("title", retained["message"]["chat"])
        self.assertEqual(retained["command"], {"title": "", "args": ["original", "args"], "hasCommand": True})

    def test_supported_media_preserves_references_used_by_existing_preparation(self):
        for kind, extra in (("photo", {"width": 20, "height": 30}),
                            ("video_note", {"length": 20, "duration": 5}),
                            ("document", {"file_name": "report.txt", "mime_type": "text/plain"}),
                            ("audio", {"duration": 20, "file_name": "recording.mp3"}),
                            ("video", {"width": 20, "height": 30, "duration": 5})):
            with self.subTest(kind=kind):
                media = {"file_id": "exact-id", "file_unique_id": "exact-unique", **extra}
                original = Update.de_json({"update_id": 21, "message": self.message(
                    media_group_id="album", **{kind: [media] if kind == "photo" else media})}, None)
                retained = owner.capture_telegram_preparation(original)
                recovered = owner.restore_telegram_preparation(retained, None, self.identity())
                actual = getattr(recovered.message, kind)
                actual = actual[-1] if kind == "photo" else actual
                self.assertEqual(actual.file_id, "exact-id")
                self.assertEqual(recovered.message.media_group_id, "album")

    def test_recovery_rejects_changed_owner_chat_thread_or_sequence(self):
        original = Update.de_json({"update_id": 22, "message": self.message(text="Original")}, None)
        retained = owner.capture_telegram_preparation(original)
        for key, wrong in (("telegramUserId", "9"), ("telegramChatId", "-200"),
                           ("telegramMessageThreadId", "10"), ("sourceSequence", 43)):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "scope mismatch"):
                owner.restore_telegram_preparation(retained, None, self.identity(**{key: wrong}))

    def test_callback_is_not_captured_as_an_original_user_source(self):
        update = Update.de_json({"update_id": 23, "callback_query": {
            "id": "callback", "chat_instance": "chat", "data": "button",
            "from": {"id": 7, "is_bot": False, "first_name": "Example"},
            "message": self.message(text="Assistant button"),
        }}, None)
        with self.assertRaisesRegex(ValueError, "original Telegram message"):
            owner.capture_telegram_preparation(update)


if __name__ == "__main__":
    unittest.main()
