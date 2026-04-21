import os
import sys
import unittest
import asyncio

# Ensure voice-gateway root is on sys.path so `import sse` works
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# === VIVENTIUM START ===
from sse import (
    iter_sse_json_events,
    extract_cortex_message_id,
    extract_text_deltas,
    sanitize_voice_delta_text,
    sanitize_voice_text,
    sanitize_voice_followup_text,
    strip_voice_control_tags,
)
# === VIVENTIUM END ===


class _FakeContent:
    def __init__(self, chunks):
        self._chunks = chunks

    async def iter_any(self):
        for chunk in self._chunks:
            yield chunk


class TestSSEParser(unittest.IsolatedAsyncioTestCase):
    async def test_parses_error_event(self) -> None:
        payload = (
            "event: message\n"
            "data: {\"event\":\"on_message_delta\",\"data\":{\"delta\":{\"content\":[{\"type\":\"text\",\"text\":\"hi\"}]}}}\n\n"
            "event: error\n"
            "data: {\"error\":\"boom\"}\n\n"
        )
        content = _FakeContent([payload.encode("utf-8")])
        events = []
        async for event in iter_sse_json_events(content=content):
            events.append(event)

        self.assertEqual(events[0].get("event"), "on_message_delta")
        self.assertEqual(events[1].get("_sse_event"), "error")
        self.assertEqual(events[1].get("error"), "boom")

    # === VIVENTIUM START ===
    def test_extracts_cortex_canonical_message_id(self) -> None:
        payload = {
            "event": "on_cortex_update",
            "data": {"canonicalMessageId": "msg_456"},
        }
        self.assertEqual(extract_cortex_message_id(payload), "msg_456")

    def test_extracts_cortex_canonical_message_id_missing(self) -> None:
        payload = {"event": "on_cortex_update", "data": {}}
        self.assertIsNone(extract_cortex_message_id(payload))
    # === VIVENTIUM END ===

    # === VIVENTIUM START ===
    def test_sanitize_voice_text_strips_literal_citations(self) -> None:
        text = "Hello \\ue202turn0search0 world"
        cleaned = sanitize_voice_text(text)
        self.assertNotIn("\\ue202", cleaned)
        self.assertNotIn("turn0search0", cleaned)
        self.assertEqual(cleaned, "Hello world")

    def test_sanitize_voice_text_strips_unicode_citations(self) -> None:
        text = "Hello \ue202turn0search0 world"
        cleaned = sanitize_voice_text(text)
        self.assertNotIn("\ue202", cleaned)
        self.assertNotIn("turn0search0", cleaned)
        self.assertEqual(cleaned, "Hello world")

    def test_sanitize_voice_text_strips_bare_citations(self) -> None:
        text = "Hello ue202turn0search0 world"
        cleaned = sanitize_voice_text(text)
        self.assertNotIn("ue202", cleaned.lower())
        self.assertNotIn("turn0search0", cleaned)
        self.assertEqual(cleaned, "Hello world")

    def test_sanitize_voice_text_strips_consecutive_bare_citations(self) -> None:
        text = "ArriveCan.ue202turn1search2ue202turn1news1 Done"
        cleaned = sanitize_voice_text(text)
        self.assertNotIn("ue202", cleaned.lower())
        self.assertNotIn("turn1search2", cleaned)
        self.assertNotIn("turn1news1", cleaned)
        self.assertIn("ArriveCan.", cleaned)

    def test_sanitize_voice_text_strips_unknown_citation_type(self) -> None:
        text = "Hello ue202turn9custom7 world"
        cleaned = sanitize_voice_text(text)
        self.assertNotIn("ue202", cleaned.lower())
        self.assertNotIn("turn9custom7", cleaned)
        self.assertEqual(cleaned, "Hello world")
    # === VIVENTIUM END ===

    # === VIVENTIUM START ===
    def test_sanitize_voice_followup_text_strips_plans_and_links(self) -> None:
        text = (
            "Plan: 1) Check calendar.\\n"
            "2) Summarize events.\\n"
            "Zoom: https://example.com/meet\\n"
            "Email: test@example.com"
        )
        cleaned = sanitize_voice_followup_text(text)
        self.assertNotIn("Plan:", cleaned)
        self.assertNotIn("1)", cleaned)
        self.assertNotIn("2)", cleaned)
        self.assertNotIn("https://", cleaned)
        self.assertNotIn("test@example.com", cleaned)
        self.assertNotIn("Check calendar.", cleaned)
        self.assertNotIn("Summarize events.", cleaned)

    def test_sanitize_voice_followup_text_strips_tool_directives(self) -> None:
        text = (
            "Use MS365 to locate your Inbox folder ID. "
            "Pull the 3 most recent messages from Inbox, selecting subject, from, receivedDateTime, and body preview."
        )
        cleaned = sanitize_voice_followup_text(text)
        self.assertNotIn("MS365", cleaned)
        self.assertNotIn("folder ID", cleaned)
        self.assertEqual(cleaned, "")

    def test_sanitize_voice_followup_text_preserves_leading_space_for_deltas(self) -> None:
        text = " hello there"
        cleaned = sanitize_voice_followup_text(text, preserve_leading_space=True)
        self.assertEqual(cleaned, " hello there")

    def test_sanitize_voice_followup_text_strips_inline_nta_tokens(self) -> None:
        cleaned = sanitize_voice_followup_text("{NTA} Useful follow-up {NTA}")
        self.assertEqual(cleaned, "Useful follow-up")

    def test_sanitize_voice_followup_text_adds_space_after_sentence_punctuation(self) -> None:
        # Test that missing spaces after sentence-ending punctuation are added
        text = "First sentence.Second sentence"
        cleaned = sanitize_voice_followup_text(text)
        self.assertIn(". S", cleaned)  # Space should be added after period before uppercase

        text2 = "Question?Answer"
        cleaned2 = sanitize_voice_followup_text(text2)
        self.assertIn("? A", cleaned2)

        text3 = "Wow!Amazing"
        cleaned3 = sanitize_voice_followup_text(text3)
        self.assertIn("! A", cleaned3)

        # Should NOT add space if followed by lowercase (e.g., abbreviations)
        text4 = "Dr.smith went home"
        cleaned4 = sanitize_voice_followup_text(text4)
        self.assertIn("Dr.s", cleaned4)
    # === VIVENTIUM END ===

    # === VIVENTIUM START ===
    def test_sanitize_voice_delta_text_preserves_whitespace(self) -> None:
        self.assertEqual(sanitize_voice_delta_text(" "), " ")
        self.assertEqual(sanitize_voice_delta_text("  "), " ")
        self.assertEqual(sanitize_voice_delta_text(" hello"), " hello")
        self.assertEqual(sanitize_voice_delta_text("hello "), "hello ")

    def test_sanitize_voice_delta_text_strips_inline_nta_tokens(self) -> None:
        self.assertEqual(sanitize_voice_delta_text("{NTA}hello"), " hello")

    # === VIVENTIUM START ===
    # Feature: Tests for strip_voice_control_tags (SSML + structural stage-direction stripping).
    # Updated 2026-04-20: Lowercase bracket stage directions are stripped generically instead of
    # matching a hardcoded token vocabulary.
    def test_strip_voice_control_tags_self_closing_emotion(self) -> None:
        text = '<emotion value="excited"/>Hello there.'
        self.assertEqual(strip_voice_control_tags(text), "Hello there.")

    def test_strip_voice_control_tags_wrapper_preserves_inner(self) -> None:
        text = '<emotion value="sad">Oh no</emotion> that is bad.'
        self.assertEqual(strip_voice_control_tags(text), "Oh no that is bad.")

    def test_strip_voice_control_tags_speak_wrapper(self) -> None:
        self.assertEqual(strip_voice_control_tags("<speak>Hello world</speak>"), "Hello world")

    def test_strip_voice_control_tags_strips_bracket_nonverbals(self) -> None:
        """Bracket nonverbal tokens are stripped for non-expressive providers."""
        text = "[laughter] Hello [sigh] world [gasp]"
        cleaned = strip_voice_control_tags(text)
        self.assertNotIn("[laughter]", cleaned)
        self.assertNotIn("[sigh]", cleaned)
        self.assertNotIn("[gasp]", cleaned)
        self.assertIn("Hello", cleaned)
        self.assertIn("world", cleaned)

    def test_strip_voice_control_tags_strips_structural_stage_directions(self) -> None:
        """Lowercase bracket stage directions are stripped generically."""
        text = "[laugh] [giggle] [chuckle] [soft laugh] [breath] [inhale] [exhale] [hmm] [whisper] [smiles]"
        cleaned = strip_voice_control_tags(text)
        self.assertNotIn("[", cleaned)
        self.assertNotIn("]", cleaned)

    def test_strip_voice_control_tags_preserves_non_nonverbal_brackets(self) -> None:
        """Legitimate bracket usage must never be broken."""
        text = "See [note: important] for details."
        self.assertEqual(strip_voice_control_tags(text), "See [note: important] for details.")

    def test_strip_voice_control_tags_preserves_short_or_non_lowercase_brackets(self) -> None:
        text = "Choose [A] or [ok] depending on context."
        self.assertEqual(strip_voice_control_tags(text), text)

    def test_strip_voice_control_tags_mixed_ssml_and_brackets(self) -> None:
        """Both SSML tags and bracket nonverbals are stripped."""
        text = '<emotion value="excited"/>Hello! [laughter] How are you?'
        cleaned = strip_voice_control_tags(text)
        self.assertIn("Hello!", cleaned)
        self.assertIn("How are you?", cleaned)
        self.assertNotIn("<emotion", cleaned)
        self.assertNotIn("[laughter]", cleaned)

    def test_strip_voice_control_tags_strips_break_tags(self) -> None:
        text = 'Hello <break time="1s"/> world'
        cleaned = strip_voice_control_tags(text)
        self.assertNotIn("<break", cleaned)
        self.assertIn("Hello", cleaned)
        self.assertIn("world", cleaned)

    def test_strip_voice_control_tags_strips_speed_volume_tags(self) -> None:
        text = '<speed ratio="1.2"/>Fast <volume ratio="0.5"/>Quiet'
        cleaned = strip_voice_control_tags(text)
        self.assertNotIn("<speed", cleaned)
        self.assertNotIn("<volume", cleaned)
        self.assertIn("Fast", cleaned)
        self.assertIn("Quiet", cleaned)

    def test_strip_voice_control_tags_strips_spell_preserves_inner(self) -> None:
        text = "The code is <spell>ABC123</spell> for reference."
        cleaned = strip_voice_control_tags(text)
        self.assertNotIn("<spell>", cleaned)
        self.assertNotIn("</spell>", cleaned)
        self.assertIn("ABC123", cleaned)
        self.assertIn("The code is", cleaned)

    def test_strip_voice_control_tags_empty(self) -> None:
        self.assertEqual(strip_voice_control_tags(""), "")

    def test_strip_voice_control_tags_plain_text_unchanged(self) -> None:
        text = "Just a normal sentence with no tags."
        self.assertEqual(strip_voice_control_tags(text), text)

    def test_strip_voice_control_tags_multiple_ssml_tags(self) -> None:
        text = '<speak><emotion value="angry"/>Stop it!</speak> <emotion value="calm">Okay fine.</emotion>'
        cleaned = strip_voice_control_tags(text)
        self.assertIn("Stop it!", cleaned)
        self.assertIn("Okay fine.", cleaned)
        self.assertNotIn("<speak>", cleaned)
        self.assertNotIn("<emotion", cleaned)
        self.assertNotIn("</emotion>", cleaned)

    def test_strip_voice_control_tags_strips_whisper(self) -> None:
        """[whisper] is stripped (xAI marker vocabulary parity)."""
        text = "Hello [whisper] secrets"
        cleaned = strip_voice_control_tags(text)
        self.assertNotIn("[whisper]", cleaned)
        self.assertIn("Hello", cleaned)
        self.assertIn("secrets", cleaned)

    def test_sanitize_voice_followup_text_strips_voice_control_tags(self) -> None:
        """Follow-up sanitization now strips voice control tags before speech."""
        text = '<emotion value="excited"/>Great news! [laughter] Check it out.'
        cleaned = sanitize_voice_followup_text(text)
        self.assertNotIn("<emotion", cleaned)
        self.assertNotIn("[laughter]", cleaned)
        self.assertIn("Great news!", cleaned)
        self.assertIn("Check it out.", cleaned)
    # === VIVENTIUM END ===

    def test_extract_text_deltas_preserves_space_only_chunks(self) -> None:
        payload = {
            "event": "on_message_delta",
            "data": {
                "delta": {
                    "content": [
                        {"type": "text", "text": "quiet"},
                        {"type": "text", "text": " "},
                        {"type": "text", "text": "and"},
                    ]
                }
            },
        }
        deltas = extract_text_deltas(payload)
        self.assertEqual("".join(deltas), "quiet and")
    # === VIVENTIUM END ===


if __name__ == "__main__":
    unittest.main()
