import asyncio
import logging
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from livekit.plugins import xai

from worker import XAI_TTS_CAPABILITIES, _build_xai_tts_word_tokenizer


def _xai_ws_text_from_tokenizer(tokenizer, chunks: list[str]) -> str:
    """Reconstruct the text the xAI websocket receives for a given tokenizer.

    Mirrors livekit/plugins/xai/tts.py SynthesizeStream: the plugin streams the
    synthesis input through ``tokenizer.stream()`` and sends each emitted
    ``word.token`` as a separate ``{"type": "text.delta", "delta": word.token}``
    frame, which the xAI server concatenates verbatim. ``chunks`` are the
    LLM-sized text pieces pushed into the stream (they may split mid-word).
    """
    async def _collect() -> str:
        stream = tokenizer.stream()
        for chunk in chunks:
            stream.push_text(chunk)
        stream.end_input()
        tokens: list[str] = []
        async for ev in stream:
            tokens.append(ev.token)
        return "".join(tokens)

    return asyncio.run(_collect())


class TestXaiStandaloneTTS(unittest.TestCase):
    def test_livekit_xai_tts_reports_streaming_pcm_contract(self) -> None:
        tts = xai.TTS(api_key="synthetic_xai_test", voice="Eve", language="en")

        self.assertTrue(tts.capabilities.streaming)
        self.assertEqual(tts.sample_rate, 24000)
        self.assertEqual(tts.num_channels, 1)
        self.assertEqual(tts.provider, "xAI")

    # === VIVENTIUM START ===
    # Regression: the xAI standalone TTS websocket must receive the assistant text with its
    # inter-word spacing intact. The plugin streams word tokens as separate text.delta frames;
    # with the plugin-default WordTokenizer(retain_format=False) every space is dropped and the
    # spoken audio glues words together ("Helloworld") even though the chat transcript looks fine.
    # _build_xai_tts_word_tokenizer injects retain_format=True to fix this.
    def test_injected_tokenizer_preserves_word_spacing_for_xai_deltas(self) -> None:
        tokenizer = _build_xai_tts_word_tokenizer()
        # Streamed in LLM-sized pieces, including a split mid-word and a trailing punctuation chunk.
        chunks = [
            "Nice, invoice cleared ",
            "is a real milestone. ",
            "On the two stake",
            "holders, what's your read",
            "?",
        ]
        expected = "".join(chunks)

        received = _xai_ws_text_from_tokenizer(tokenizer, chunks)

        self.assertEqual(received, expected)
        for glued in ("clearedis", "milestone.On", "stakeholders,what's", "what'syour"):
            self.assertNotIn(glued, received)

    def test_default_plugin_tokenizer_would_drop_spacing(self) -> None:
        # Documents the upstream defect being worked around: the plugin's default tokenizer
        # (retain_format=False) concatenates bare word tokens and loses every space.
        default_tokenizer = xai.TTS(
            api_key="synthetic_xai_test", voice="Eve", language="en"
        )._opts.tokenizer
        received = _xai_ws_text_from_tokenizer(default_tokenizer, ["Hello there, ", "how are you?"])
        self.assertEqual(received, "Hellothere,howareyou?")

    def test_xai_tts_constructed_with_space_preserving_tokenizer(self) -> None:
        tts = xai.TTS(
            api_key="synthetic_xai_test",
            voice="Eve",
            language="en",
            tokenizer=_build_xai_tts_word_tokenizer(),
        )
        received = _xai_ws_text_from_tokenizer(tts._opts.tokenizer, ["Hello there, ", "how are you?"])
        self.assertEqual(received, "Hello there, how are you?")

    def test_debug_delta_logging_is_transparent_and_records_word_payloads(self) -> None:
        # With voice TTS debug logging on, the tokenizer logs each text.delta payload but must not
        # change the tokens the websocket receives.
        with mock.patch.dict(os.environ, {"VIVENTIUM_VOICE_DEBUG_TTS": "1"}, clear=False):
            with self.assertLogs("voice-gateway", level=logging.INFO) as captured:
                received = _xai_ws_text_from_tokenizer(
                    _build_xai_tts_word_tokenizer(), ["Hello there, ", "how are you?"]
                )
        self.assertEqual(received, "Hello there, how are you?")
        delta_lines = [line for line in captured.output if "stage=text.delta" in line]
        self.assertTrue(delta_lines, "expected per-word text.delta debug lines")
        self.assertTrue(any("leading_space=True" in line for line in delta_lines))
    # === VIVENTIUM END ===

    def test_xai_capability_contract_lists_documented_tags(self) -> None:
        tags = XAI_TTS_CAPABILITIES["speech_tags"]

        self.assertIn("[long-pause]", tags["inline"])
        self.assertIn("[tongue-click]", tags["inline"])
        self.assertIn("whisper", tags["wrapping"])
        self.assertIn("build-intensity", tags["wrapping"])


if __name__ == "__main__":
    unittest.main()
