import os
import sys
import unittest
import asyncio
import json
import subprocess
from pathlib import Path

# Ensure voice-gateway root is on sys.path so `import sse` works
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# === VIVENTIUM START ===
from sse import (
    VoiceControlDisplayFilter,
    _XAI_WRAPPING_TAG_NAMES,
    iter_sse_json_events,
    extract_cortex_message_id,
    extract_raw_text_deltas,
    extract_text_deltas,
    sanitize_voice_delta_text,
    sanitize_voice_text,
    sanitize_voice_followup_text,
    sanitize_voice_tts_text,
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

    def test_sanitize_voice_text_preserves_turn_substrings_in_words(self) -> None:
        for text in [
            "Saturn5rocket2 launches today",
            "The return0value1 was set",
            "An overturn3case4 ruling",
            "A nocturne is playing",
            "Take turn 4 now",
        ]:
            with self.subTest(text=text):
                self.assertEqual(sanitize_voice_text(text), text)

    def test_sanitize_voice_text_strips_split_bare_turn_id(self) -> None:
        text = "Persian. turn0search4 If you mean coolest"
        cleaned = sanitize_voice_text(text)
        self.assertNotIn("turn0search4", cleaned)
        self.assertEqual(cleaned, "Persian. If you mean coolest")

    def test_sanitize_voice_text_strips_bracketed_turn_source_shell(self) -> None:
        text = "Answer \u3010turn0search4\u2020source\u3011 continues"
        cleaned = sanitize_voice_text(text)
        self.assertNotIn("turn0search4", cleaned)
        self.assertNotIn("\u2020source", cleaned)
        self.assertEqual(cleaned, "Answer continues")

    def test_sanitize_voice_text_strips_concatenated_split_turn_ids(self) -> None:
        text = "Answer turn0search1turn0news2turn0file3 done"
        cleaned = sanitize_voice_text(text)
        self.assertNotIn("turn0search1", cleaned)
        self.assertNotIn("turn0news2", cleaned)
        self.assertNotIn("turn0file3", cleaned)
        self.assertEqual(cleaned, "Answer done")

    def test_sanitize_voice_text_strips_numeric_citation_before_punctuation(self) -> None:
        text = "Answer [1]. Next [23], done"
        cleaned = sanitize_voice_text(text)
        self.assertNotIn("[1]", cleaned)
        self.assertNotIn("[23]", cleaned)
        self.assertIn("Answer", cleaned)
        self.assertIn("Next", cleaned)

    def test_sanitize_voice_delta_text_strips_split_bare_turn_id(self) -> None:
        cleaned = sanitize_voice_delta_text(" turn0search4 If you mean coolest")
        self.assertNotIn("turn0search4", cleaned)
        self.assertEqual(cleaned, " If you mean coolest")

    def test_sanitize_voice_delta_text_strips_split_citation_tail(self) -> None:
        cleaned = "".join(
            sanitize_voice_delta_text(chunk)
            for chunk in ["Answer turn0search4", "\u2020source\u3011 continues"]
        )
        self.assertNotIn("turn0search4", cleaned)
        self.assertNotIn("\u2020source", cleaned)
        self.assertNotIn("\u3011", cleaned)
        self.assertEqual(" ".join(cleaned.split()), "Answer continues")

    def test_sanitize_voice_delta_text_strips_split_citation_brackets(self) -> None:
        cases = [
            ["Answer \u3010turn0search4", "\u3011 next"],
            ["Answer \u3010", "turn0search4 next"],
        ]
        for chunks in cases:
            with self.subTest(chunks=chunks):
                cleaned = "".join(sanitize_voice_delta_text(chunk) for chunk in chunks)
                self.assertNotIn("turn0search4", cleaned)
                self.assertNotIn("\u3010", cleaned)
                self.assertNotIn("\u3011", cleaned)
                self.assertEqual(" ".join(cleaned.split()), "Answer next")
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

    def test_sanitize_voice_tts_text_strips_malformed_internal_nta_artifacts(self) -> None:
        cases = [
            "{N{NTATA}}",
            "{N{N{NTA}}}",
            "The marker {N{NTATA}} should not leak.",
            "Useful context {NTA",
            "Useful context {N{NTA}",
        ]
        for text in cases:
            with self.subTest(text=text):
                cleaned = sanitize_voice_tts_text(text)
                self.assertNotIn("{N", cleaned)
                self.assertNotIn("NTA", cleaned)

    def test_sanitize_voice_delta_text_strips_malformed_internal_nta_artifacts(self) -> None:
        cleaned = sanitize_voice_delta_text("The marker {N{NTATA}} should not leak.")
        self.assertNotIn("{N", cleaned)
        self.assertNotIn("NTA", cleaned)

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

    def test_sanitize_voice_tts_text_strips_reference_markdown_links_and_code(self) -> None:
        text = (
            "Sources: https://example.com/report\n"
            "Read [the brief](https://example.com/brief). "
            "```json\n{\"ok\": true}\n```"
        )
        cleaned = sanitize_voice_tts_text(text)
        self.assertNotIn("Sources:", cleaned)
        self.assertNotIn("https://", cleaned)
        self.assertNotIn("[the brief]", cleaned)
        self.assertNotIn("```", cleaned)
        self.assertIn("the brief.", cleaned)

    def test_sanitize_voice_tts_text_strips_inline_markdown_emphasis(self) -> None:
        text = "Use **bold** and _italic_ words, then ~~remove~~ this. *** rule ***"
        cleaned = sanitize_voice_tts_text(text)
        self.assertEqual(cleaned, "Use bold and italic words, then remove this. rule")

    def test_sanitize_voice_tts_text_strips_marker_only_markdown_chunk(self) -> None:
        self.assertEqual(sanitize_voice_tts_text("*"), "")
        self.assertEqual(sanitize_voice_tts_text("***"), "")

    def test_sanitize_voice_tts_text_preserves_math_asterisk(self) -> None:
        cleaned = sanitize_voice_tts_text("Five times three is 5 * 3.")
        self.assertIn("5 * 3", cleaned)

    def test_sanitize_voice_tts_text_normalizes_urls_and_email_preserves_bare_domains(self) -> None:
        text = "Go to example.com or www.example.org, then email qa@example.com."
        cleaned = sanitize_voice_tts_text(text)
        self.assertIn("example.com", cleaned)
        self.assertNotIn("www.example.org", cleaned)
        self.assertNotIn("qa@example.com", cleaned)
        self.assertIn("link available", cleaned)
        self.assertIn("address available", cleaned)
        self.assertNotIn("email email", cleaned.lower())

    def test_sanitize_voice_tts_text_keeps_email_replacement_natural(self) -> None:
        self.assertEqual(
            sanitize_voice_tts_text("Email qa@example.com."),
            "Email address available.",
        )

    def test_sanitize_voice_tts_text_preserves_dot_heavy_technical_tokens(self) -> None:
        text = "Use .NET, asp.net, v1.2A, U.S.A., and node.js. Done.Next."
        cleaned = sanitize_voice_tts_text(text)
        self.assertEqual(
            cleaned,
            "Use .NET, asp.net, v1.2A, U.S.A., and node.js. Done. Next.",
        )
        self.assertNotIn("link available", cleaned)

    def test_sanitize_voice_tts_text_does_not_convert_common_filename_domains(self) -> None:
        text = "Open read.me, index.co, node.app, and thing.dev in the project."
        cleaned = sanitize_voice_tts_text(text)
        self.assertEqual(cleaned, text)

    def test_sanitize_voice_tts_text_keeps_reference_label_content_without_link(self) -> None:
        cleaned = sanitize_voice_tts_text("References: I have a few good ones.")
        self.assertEqual(cleaned, "I have a few good ones.")

    def test_sanitize_voice_tts_text_strips_voice_controls_for_plain_tts(self) -> None:
        text = '<emotion value="calm"/>Hello <break time="500ms"/>there [laughter].'
        cleaned = sanitize_voice_tts_text(text, allow_voice_controls=False)
        self.assertEqual(cleaned, "Hello there.")

    def test_sanitize_voice_tts_text_preserves_supported_voice_controls_when_allowed(self) -> None:
        text = '<emotion value="calm"/>Hello <break time="500ms"/>there [laughter].'
        cleaned = sanitize_voice_tts_text(text, allow_voice_controls=True)
        self.assertIn('<emotion value="calm"/>', cleaned)
        self.assertIn('<break time="500ms"/>', cleaned)
        self.assertIn("[laughter]", cleaned)
        self.assertIn("Hello", cleaned)

    def test_sanitize_voice_tts_text_strips_unknown_angle_tags(self) -> None:
        text = "Hello <custom data='x'>there</custom> <soft>quiet</soft>."
        cleaned = sanitize_voice_tts_text(text, allow_voice_controls=True)
        self.assertNotIn("<custom", cleaned)
        self.assertNotIn("</custom>", cleaned)
        self.assertIn("<soft>quiet</soft>", cleaned)

    def test_sanitize_voice_tts_text_can_preserve_trailing_space(self) -> None:
        cleaned = sanitize_voice_tts_text("invoice cleared ", preserve_trailing_space=True)
        self.assertEqual(cleaned, "invoice cleared ")

    def test_sanitize_voice_tts_text_tracks_shared_artifact_contract(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        contract_path = repo_root / "qa/modern-playground-voice/scripts/voice_artifact_contract.cjs"
        script = (
            "const contract = require(process.argv[1]);"
            "process.stdout.write(JSON.stringify({"
            "keys: contract.DEFAULT_TTS_FORBIDDEN_ARTIFACT_KEYS,"
            "cases: contract.SYNTHETIC_FORBIDDEN_ARTIFACT_CASES,"
            "counts: contract.artifactCounts"
            "}));"
        )
        payload = json.loads(
            subprocess.check_output(["node", "-e", script, str(contract_path)], text=True)
        )
        sanitizer_owned_keys = {
            "rawUrl",
            "rawEmail",
            "sourceLabel",
            "markdownLink",
            "markdownEmphasis",
            "codeFence",
            "unknownAngleTag",
            "voiceControlMarker",
            "internalTurnId",
            "numericCitation",
            "privateUseCitationMarker",
            "internalNoResponseMarker",
        }
        self.assertTrue(sanitizer_owned_keys.issubset(set(payload["keys"])))

        for case in payload["cases"]:
            key = case.get("key")
            if key not in sanitizer_owned_keys:
                continue
            with self.subTest(key=key, text=case.get("text")):
                cleaned = sanitize_voice_tts_text(case.get("text") or "")
                check_script = (
                    "const contract = require(process.argv[1]);"
                    "process.stdout.write(JSON.stringify(contract.artifactCounts(process.argv[2])));"
                )
                counts = json.loads(
                    subprocess.check_output(
                        ["node", "-e", check_script, str(contract_path), cleaned],
                        text=True,
                    )
                )
                self.assertEqual(counts.get(key, 0), 0, cleaned)
    # === VIVENTIUM END ===

    # === VIVENTIUM START ===
    def test_sanitize_voice_delta_text_preserves_whitespace(self) -> None:
        self.assertEqual(sanitize_voice_delta_text(" "), " ")
        self.assertEqual(sanitize_voice_delta_text("  "), " ")
        self.assertEqual(sanitize_voice_delta_text(" hello"), " hello")
        self.assertEqual(sanitize_voice_delta_text("hello "), "hello ")

    def test_sanitize_voice_delta_text_strips_inline_nta_tokens(self) -> None:
        self.assertEqual(sanitize_voice_delta_text("{NTA}hello"), "hello")
        self.assertEqual(sanitize_voice_delta_text("first{NTA}second"), "first second")

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

    def test_strip_voice_control_tags_strips_xai_wrapping_tags(self) -> None:
        text = "I need <whisper>this quiet</whisper> and <slow><soft>gentle</soft></slow>."
        cleaned = strip_voice_control_tags(text)
        self.assertEqual(cleaned, "I need this quiet and gentle.")
        self.assertNotIn("<whisper>", cleaned)
        self.assertNotIn("<slow>", cleaned)
        self.assertNotIn("<soft>", cleaned)

    def test_strip_voice_control_tags_strips_malformed_xai_square_wrappers(self) -> None:
        text = "<soft>Morning. You have warmth.[/soft] If needed."
        cleaned = strip_voice_control_tags(text)
        self.assertEqual(cleaned, "Morning. You have warmth. If needed.")
        self.assertNotIn("<soft>", cleaned)
        self.assertNotIn("[/soft]", cleaned)

    def test_strip_voice_control_tags_strips_every_malformed_xai_square_wrapper(self) -> None:
        for tag in _XAI_WRAPPING_TAG_NAMES:
            with self.subTest(tag=tag):
                cleaned = strip_voice_control_tags(f"Lead [{tag}] keep [/{tag}] tail.")
                self.assertEqual(cleaned, "Lead keep tail.")
                self.assertNotIn(f"[{tag}]", cleaned)
                self.assertNotIn(f"[/{tag}]", cleaned)

    def test_sanitize_voice_followup_text_strips_voice_control_tags(self) -> None:
        """Follow-up sanitization now strips voice control tags before speech."""
        text = '<emotion value="excited"/>Great news! [laughter] Check it out.'
        cleaned = sanitize_voice_followup_text(text)
        self.assertNotIn("<emotion", cleaned)
        self.assertNotIn("[laughter]", cleaned)
        self.assertIn("Great news!", cleaned)
        self.assertIn("Check it out.", cleaned)

    def test_voice_control_display_filter_buffers_partial_emotion_tag(self) -> None:
        display = VoiceControlDisplayFilter()
        chunks = ["<em", "otion ", 'value="excited"/>Voice ', "check"]
        cleaned = "".join(display.feed(chunk) for chunk in chunks)
        cleaned += display.feed("", final=True)
        self.assertEqual(cleaned, "Voice check")

    def test_voice_control_display_filter_strips_split_bracket_stage_direction(self) -> None:
        display = VoiceControlDisplayFilter()
        chunks = ["Hello ", "[laugh", "ter] world"]
        cleaned = "".join(display.feed(chunk) for chunk in chunks)
        self.assertEqual(cleaned, "Hello  world")

    def test_voice_control_display_filter_strips_split_xai_wrapping_tag(self) -> None:
        display = VoiceControlDisplayFilter()
        chunks = ["Hello ", "<whis", "per>secret</whisper> world"]
        cleaned = "".join(display.feed(chunk) for chunk in chunks)
        cleaned += display.feed("", final=True)
        self.assertEqual(cleaned, "Hello secret world")

    def test_voice_control_display_filter_strips_malformed_xai_square_wrapper(self) -> None:
        display = VoiceControlDisplayFilter()
        chunks = ["Morning. ", "You have warmth.[/so", "ft] If needed."]
        cleaned = "".join(display.feed(chunk) for chunk in chunks)
        cleaned += display.feed("", final=True)
        self.assertEqual(cleaned, "Morning. You have warmth. If needed.")

    def test_voice_control_display_filter_preserves_non_voice_markup(self) -> None:
        display = VoiceControlDisplayFilter()
        cleaned = display.feed("Use 1 < 2 and [note: important].")
        self.assertEqual(cleaned, "Use 1 < 2 and [note: important].")
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

    def test_extract_raw_text_deltas_preserves_voice_markup_for_debugging(self) -> None:
        payload = {
            "event": "on_message_delta",
            "data": {
                "delta": {
                    "content": [
                        {
                            "type": "text",
                            "text": '<emotion value="calm"/>Hello <break time="200ms"/>there.',
                        }
                    ]
                }
            },
        }
        self.assertEqual(
            extract_raw_text_deltas(payload),
            ['<emotion value="calm"/>Hello <break time="200ms"/>there.'],
        )
    # === VIVENTIUM END ===


if __name__ == "__main__":
    unittest.main()
