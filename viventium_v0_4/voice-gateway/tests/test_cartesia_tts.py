"""Viventium Cartesia TTS normalization tests."""

# === VIVENTIUM START ===
# Feature: Cartesia emotion + nonverbal normalization tests
# Added: 2026-01-10
# Updated: 2026-02-22 - Added SSML preservation tests, break tag tests
# === VIVENTIUM END ===

import os
import sys
import unittest

# Ensure voice-gateway root is on sys.path so `import cartesia_tts` works
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cartesia_tts import (
    CartesiaConfig,
    CartesiaTTS,
    _STAGE_PROMPTS,
    _build_ws_generation_request,
    _consume_streaming_emotion_chunk,
    _extract_ws_audio_chunk,
    _is_ws_done,
    _normalize_nonverbal_tokens,
    _split_emotion_segments,
    StreamingEmotionState,
)


class TestCartesiaNormalization(unittest.TestCase):
    def test_cartesia_reports_streaming_capability(self) -> None:
        tts = CartesiaTTS(config=CartesiaConfig(api_key="cartesia-key"))
        self.assertTrue(tts.capabilities.streaming)

    def test_laughter_stage_prompt_uses_cartesia_token(self) -> None:
        # Cartesia docs: the token `[laughter]` triggers actual laughter. We should not
        # approximate it as spoken "ha ha ha" text.
        prompt, _emotion = _STAGE_PROMPTS.get("laughter", ("", None))
        self.assertEqual(prompt, "[laughter]")

    def test_normalizes_laughter_variants(self) -> None:
        text = "Hi [laugh] there [gentle laugh] wow [giggle]!"
        normalized = _normalize_nonverbal_tokens(text)
        self.assertIn("[laughter]", normalized)
        self.assertNotIn("[laugh]", normalized)
        self.assertNotIn("[gentle laugh]", normalized)
        self.assertNotIn("[giggle]", normalized)

    def test_normalizes_sigh_variants(self) -> None:
        text = "Hmm [sigh] okay [gentle sigh] noted"
        normalized = _normalize_nonverbal_tokens(text)
        self.assertIn("[sigh]", normalized)
        self.assertNotIn("[gentle sigh]", normalized)

    def test_removes_unknown_tokens(self) -> None:
        text = "[whisper] hello [snort] world"
        normalized = _normalize_nonverbal_tokens(text)
        self.assertNotIn("[whisper]", normalized)
        self.assertNotIn("[snort]", normalized)
        self.assertIn("hello", normalized)

    # === VIVENTIUM START ===
    # Feature: Verify Cartesia SSML tags are preserved through normalization.
    # Added: 2026-02-22
    def test_preserves_break_tags(self) -> None:
        text = 'Hello <break time="1s"/> world'
        normalized = _normalize_nonverbal_tokens(text)
        self.assertIn('<break time="1s"/>', normalized)
        self.assertIn("Hello", normalized)
        self.assertIn("world", normalized)

    def test_preserves_speed_tags(self) -> None:
        text = 'Hello <speed ratio="1.2"/> world'
        normalized = _normalize_nonverbal_tokens(text)
        self.assertIn('<speed ratio="1.2"/>', normalized)

    def test_preserves_volume_tags(self) -> None:
        text = 'Hello <volume ratio="0.8"/> world'
        normalized = _normalize_nonverbal_tokens(text)
        self.assertIn('<volume ratio="0.8"/>', normalized)

    def test_strips_non_cartesia_html_tags(self) -> None:
        text = "Hello <b>bold</b> <div>block</div> world"
        normalized = _normalize_nonverbal_tokens(text)
        self.assertNotIn("<b>", normalized)
        self.assertNotIn("<div>", normalized)
        self.assertIn("Hello", normalized)
        self.assertIn("bold", normalized)
        self.assertIn("world", normalized)

    def test_build_ws_generation_request_sets_context_and_buffer(self) -> None:
        cfg = CartesiaConfig(
            api_key="cartesia-key",
            voice_id="voice-123",
            sample_rate=44100,
            max_buffer_delay_ms=120,
        )
        payload = _build_ws_generation_request(
            cfg=cfg,
            context_id="ctx-123",
            transcript="Hello there. ",
            continue_generation=True,
        )
        self.assertEqual(payload["context_id"], "ctx-123")
        self.assertEqual(payload["transcript"], "Hello there. ")
        self.assertEqual(payload["continue"], True)
        self.assertEqual(payload["max_buffer_delay_ms"], 120)
        self.assertEqual(payload["output_format"]["container"], "raw")
        self.assertEqual(payload["output_format"]["encoding"], "pcm_s16le")

    def test_build_ws_generation_request_supports_emotion_override(self) -> None:
        cfg = CartesiaConfig(api_key="cartesia-key", emotion="neutral")
        payload = _build_ws_generation_request(
            cfg=cfg,
            context_id="ctx-123",
            transcript="Hello there.",
            continue_generation=True,
            emotion="calm",
        )
        self.assertEqual(payload["generation_config"]["emotion"], "calm")

    def test_extract_ws_audio_chunk_decodes_base64(self) -> None:
        chunk = _extract_ws_audio_chunk({"type": "chunk", "data": "AQID"})
        self.assertEqual(chunk, b"\x01\x02\x03")

    def test_is_ws_done_matches_context(self) -> None:
        self.assertTrue(_is_ws_done({"type": "done", "context_id": "ctx-123"}, context_id="ctx-123"))
        self.assertFalse(_is_ws_done({"type": "done", "context_id": "ctx-999"}, context_id="ctx-123"))
    # === VIVENTIUM END ===


class TestCartesiaEmotionSegments(unittest.TestCase):
    def test_splits_emotion_segments(self) -> None:
        text = "Hi <emotion value=\"happy\">Great</emotion> there"
        segments = _split_emotion_segments(text)
        data = [(seg.text.strip(), seg.emotion, seg.stage) for seg in segments]
        self.assertEqual(data[0], ("Hi", None, None))
        self.assertEqual(data[1], ("Great", "happy", None))
        self.assertEqual(data[2], ("there", None, None))

    def test_self_closing_emotion_applies_to_following_text(self) -> None:
        text = "<emotion value=\"excited\"/>Hello there. <emotion value=\"sad\"/>Oops."
        segments = _split_emotion_segments(text)
        data = [(seg.text.strip(), seg.emotion, seg.stage) for seg in segments]
        self.assertEqual(data[0], ("Hello there.", "excited", None))
        self.assertEqual(data[1], ("Oops.", "sad", None))

    def test_self_closing_state_persists_across_wrapper_emotion(self) -> None:
        text = "<emotion value=\"excited\"/>Hello <emotion value=\"sad\">inner</emotion> world"
        segments = _split_emotion_segments(text)
        data = [(seg.text.strip(), seg.emotion, seg.stage) for seg in segments]
        self.assertEqual(data[0], ("Hello", "excited", None))
        self.assertEqual(data[1], ("inner", "sad", None))
        self.assertEqual(data[2], ("world", "excited", None))

    def test_ignores_speak_wrapper(self) -> None:
        text = "<speak>Hello <emotion value='sad'>oops</emotion></speak>"
        segments = _split_emotion_segments(text)
        data = [(seg.text.strip(), seg.emotion, seg.stage) for seg in segments]
        self.assertEqual(data[0], ("Hello", None, None))
        self.assertEqual(data[1], ("oops", "sad", None))

    def test_splits_stage_segments(self) -> None:
        text = "Hi [gentle laugh] there"
        segments = _split_emotion_segments(text)
        data = [(seg.text.strip(), seg.emotion, seg.stage) for seg in segments]
        self.assertEqual(data[0], ("Hi", None, None))
        self.assertEqual(data[1], ("", None, "laughter"))
        self.assertEqual(data[2], ("there", None, None))

    def test_streaming_emotion_state_handles_partial_self_closing_tag(self) -> None:
        state = StreamingEmotionState()
        self.assertEqual(
            _consume_streaming_emotion_chunk(state, '<emotion value="con', final=False),
            [],
        )

        segments = _consume_streaming_emotion_chunk(
            state,
            'tent"/>Yeah, feels smoother.',
            final=False,
        )
        data = [(seg.text.strip(), seg.emotion, seg.stage) for seg in segments]
        self.assertEqual(data, [("Yeah, feels smoother.", "content", None)])

    def test_streaming_emotion_state_preserves_emotion_across_chunks(self) -> None:
        state = StreamingEmotionState()
        _consume_streaming_emotion_chunk(state, '<emotion value="calm"/>', final=False)
        segments = _consume_streaming_emotion_chunk(state, 'Go rest.', final=False)
        data = [(seg.text.strip(), seg.emotion, seg.stage) for seg in segments]
        self.assertEqual(data, [("Go rest.", "calm", None)])

    def test_streaming_emotion_state_flushes_unclosed_wrapper_on_final(self) -> None:
        state = StreamingEmotionState()
        self.assertEqual(
            _consume_streaming_emotion_chunk(
                state,
                '<emotion value="curious">Anything else',
                final=False,
            ),
            [],
        )
        segments = _consume_streaming_emotion_chunk(state, '', final=True)
        data = [(seg.text.strip(), seg.emotion, seg.stage) for seg in segments]
        self.assertEqual(data, [("Anything else", "curious", None)])


if __name__ == "__main__":
    unittest.main()
