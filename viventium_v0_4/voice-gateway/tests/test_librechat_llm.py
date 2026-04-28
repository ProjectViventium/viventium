import os
import sys
import unittest

from livekit.agents.llm.chat_context import ChatContext, ChatMessage

# Ensure voice-gateway root is on sys.path so `import librechat_llm` works
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from librechat_llm import (
    _extract_final_response_text,
    _extract_final_response_message_id,
    _extract_last_user_text,
    _extract_stream_error,
    _select_stream_error_message,
    _summarize_error_for_log,
    _NoResponseStreamGuard,
    is_no_response_only,
    format_insights_for_direct_speech,
)


class TestExtractLastUserText(unittest.TestCase):
    def test_extracts_single_user_message(self) -> None:
        ctx = ChatContext(items=[ChatMessage(role="user", content=["hello"])])
        self.assertEqual(_extract_last_user_text(ctx), "hello")

    def test_extracts_last_user_message(self) -> None:
        ctx = ChatContext(
            items=[
                ChatMessage(role="user", content=["first"]),
                ChatMessage(role="assistant", content=["ignore"]),
                ChatMessage(role="user", content=["second"]),
            ]
        )
        self.assertEqual(_extract_last_user_text(ctx), "second")

    def test_joins_multiple_text_chunks(self) -> None:
        ctx = ChatContext(items=[ChatMessage(role="user", content=["hel", "lo"])])
        self.assertEqual(_extract_last_user_text(ctx), "hello")

    def test_ignores_empty_and_whitespace(self) -> None:
        ctx = ChatContext(items=[ChatMessage(role="user", content=[" ", "\n", "\t"])])
        self.assertEqual(_extract_last_user_text(ctx), "")


class TestFinalEventHelpers(unittest.TestCase):
    def test_extracts_final_response_message_id(self) -> None:
        final_event = {"final": True, "responseMessage": {"messageId": "msg_123"}}
        self.assertEqual(_extract_final_response_message_id(final_event), "msg_123")

    def test_extracts_final_response_message_id_missing(self) -> None:
        self.assertEqual(_extract_final_response_message_id({"final": True}), "")

    def test_extracts_error_content_part_as_fallback_message(self) -> None:
        os.environ["VIVENTIUM_VOICE_STREAM_ERROR_MESSAGE"] = "Stream down."
        try:
            final_event = {
                "final": True,
                "responseMessage": {"content": [{"type": "error", "error": "Access denied"}]},
            }
            self.assertEqual(_extract_final_response_text(final_event), "Stream down.")
        finally:
            os.environ.pop("VIVENTIUM_VOICE_STREAM_ERROR_MESSAGE", None)

    def test_summarizes_error_content_without_raw_message(self) -> None:
        raw = (
            'An error occurred while processing the request: 401 '
            '{"type":"error","error":{"type":"authentication_error",'
            '"message":"Invalid authentication credentials"}}'
        )
        summary = _summarize_error_for_log(raw)
        self.assertIn("status=401", summary)
        self.assertIn("type=error", summary)
        self.assertIn("error_type=authentication_error", summary)
        self.assertNotIn("Invalid authentication credentials", summary)

    def test_extracts_final_response_text_preserves_word_boundaries(self) -> None:
        final_event = {
            "final": True,
            "responseMessage": {
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "text", "text": " world"},
                ]
            },
        }
        self.assertEqual(_extract_final_response_text(final_event), "Hello world")

    def test_formats_insights_for_direct_speech(self) -> None:
        speech = format_insights_for_direct_speech(
            [{"cortex_name": "Background Analysis", "insight": "Secret code: 27."}]
        )
        self.assertIn("Secret code: 27.", speech)
        self.assertNotIn("Background insights update.", speech)

    # === VIVENTIUM START ===
    def test_formats_insights_for_direct_speech_strips_links(self) -> None:
        speech = format_insights_for_direct_speech(
            [
                {
                    "cortex_name": "Online Tool Use",
                    "insight": "Plan: 1) Check. Zoom: https://example.com",
                }
            ]
        )
        self.assertNotIn("Plan:", speech)
        self.assertNotIn("https://", speech)
        self.assertIn("Check.", speech)
    # === VIVENTIUM END ===

    def test_formats_insights_for_direct_speech_with_preamble(self) -> None:
        os.environ["VIVENTIUM_VOICE_INSIGHT_PREAMBLE"] = "Quick note."
        try:
            speech = format_insights_for_direct_speech(
                [{"cortex_name": "Background Analysis", "insight": "Secret code: 27."}]
            )
            self.assertTrue(speech.startswith("Quick note."))
        finally:
            os.environ.pop("VIVENTIUM_VOICE_INSIGHT_PREAMBLE", None)


class TestStreamErrorHelpers(unittest.TestCase):
    def test_extracts_stream_error(self) -> None:
        payload = {"_sse_event": "error", "error": "boom"}
        self.assertEqual(_extract_stream_error(payload), "boom")

    def test_selects_tool_error_message(self) -> None:
        os.environ["VIVENTIUM_VOICE_STREAM_ERROR_MESSAGE"] = "Stream down."
        os.environ["VIVENTIUM_VOICE_TOOL_ERROR_MESSAGE"] = "Tool down."
        os.environ["VIVENTIUM_VOICE_AUTH_ERROR_MESSAGE"] = "Auth down."
        try:
            self.assertEqual(_select_stream_error_message("MCP connection failed"), "Tool down.")
            self.assertEqual(
                _select_stream_error_message("401 authentication_error"),
                "Auth down.",
            )
            self.assertEqual(_select_stream_error_message("other error"), "Stream down.")
        finally:
            os.environ.pop("VIVENTIUM_VOICE_STREAM_ERROR_MESSAGE", None)
            os.environ.pop("VIVENTIUM_VOICE_TOOL_ERROR_MESSAGE", None)
            os.environ.pop("VIVENTIUM_VOICE_AUTH_ERROR_MESSAGE", None)

class TestNoResponseStreamingGuard(unittest.TestCase):
    def test_buffers_and_suppresses_braced_tag(self) -> None:
        guard = _NoResponseStreamGuard()
        emitted: list[str] = []
        for delta in ["{", "NTA", "}"]:
            emitted.extend(guard.feed(delta))

        self.assertEqual(emitted, [])
        suppressed, pending = guard.finalize("{NTA}")
        self.assertTrue(suppressed)
        self.assertEqual(pending, [])
        self.assertTrue(is_no_response_only("{NTA}"))

    def test_emits_normal_text_immediately(self) -> None:
        guard = _NoResponseStreamGuard()
        emitted = guard.feed("Hello")
        self.assertEqual(emitted, ["Hello"])
        suppressed, pending = guard.finalize("Hello")
        self.assertFalse(suppressed)
        self.assertEqual(pending, [])

    def test_preserves_leading_space_on_following_streamed_delta(self) -> None:
        guard = _NoResponseStreamGuard()
        emitted: list[str] = []
        emitted.extend(guard.feed("Hello"))
        emitted.extend(guard.feed(" world"))
        self.assertEqual(emitted, ["Hello", " world"])
        suppressed, pending = guard.finalize("Hello world")
        self.assertFalse(suppressed)
        self.assertEqual(pending, [])

    def test_suppresses_nothing_to_add_variants(self) -> None:
        guard = _NoResponseStreamGuard()
        emitted = guard.feed("Nothing new to add for now.")
        self.assertEqual(emitted, [])
        suppressed, pending = guard.finalize("Nothing new to add for now.")
        self.assertTrue(suppressed)
        self.assertEqual(pending, [])

    def test_does_not_suppress_meaningful_nothing_statement(self) -> None:
        guard = _NoResponseStreamGuard()
        emitted = guard.feed("Nothing beats a clean implementation.")
        self.assertEqual(emitted, ["Nothing beats a clean implementation."])
        suppressed, pending = guard.finalize("Nothing beats a clean implementation.")
        self.assertFalse(suppressed)
        self.assertEqual(pending, [])

    def test_flushes_when_nothing_to_add_becomes_meaningful(self) -> None:
        guard = _NoResponseStreamGuard()
        emitted: list[str] = []
        emitted.extend(guard.feed("Nothing"))
        self.assertEqual(emitted, [])
        emitted.extend(guard.feed(" to add except this: keep the space."))
        self.assertNotEqual(emitted, [])
        suppressed, pending = guard.finalize("".join(["Nothing", " to add except this: keep the space."]))
        self.assertFalse(suppressed)
        self.assertEqual(pending, [])

    def test_strips_inline_nta_when_meaningful_content_follows(self) -> None:
        guard = _NoResponseStreamGuard()
        emitted: list[str] = []
        emitted.extend(guard.feed("{"))
        emitted.extend(guard.feed("NTA"))
        emitted.extend(guard.feed("} Useful follow-up"))
        self.assertEqual("".join(emitted), "Useful follow-up")
        suppressed, pending = guard.finalize("{NTA} Useful follow-up")
        self.assertFalse(suppressed)
        self.assertEqual(pending, [])


if __name__ == "__main__":
    unittest.main()
