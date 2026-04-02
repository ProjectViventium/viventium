import os
import sys
import unittest

# Ensure voice-gateway root is on sys.path so imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xai_grok_voice_tts import (
    XaiGrokVoiceConfig,
    build_conversation_item_create,
    build_response_create,
    build_session_update,
    extract_output_audio_delta,
    is_response_done,
)


class TestXaiGrokVoiceTTSProtocol(unittest.TestCase):
    def test_build_session_update_contains_voice_and_pcm_rate(self) -> None:
        cfg = XaiGrokVoiceConfig(api_key="xai-key", voice="Eve", sample_rate=24000)
        msg = build_session_update(cfg)
        self.assertEqual(msg["type"], "session.update")
        self.assertEqual(msg["session"]["voice"], "Eve")
        self.assertEqual(msg["session"]["audio"]["output"]["format"]["type"], "audio/pcm")
        self.assertEqual(msg["session"]["audio"]["output"]["format"]["rate"], 24000)

    def test_build_conversation_item_create_wraps_speak_tag(self) -> None:
        msg = build_conversation_item_create("hello")
        self.assertEqual(msg["type"], "conversation.item.create")
        self.assertEqual(msg["item"]["role"], "user")
        self.assertEqual(msg["item"]["content"][0]["type"], "input_text")
        # xAI Grok Voice is conversational; we rely on instructions, not SSML wrappers.
        self.assertEqual(msg["item"]["content"][0]["text"], "hello")

    def test_build_response_create(self) -> None:
        self.assertEqual(build_response_create(), {"type": "response.create"})

    def test_extract_output_audio_delta_decodes_base64(self) -> None:
        # base64 for bytes [0x01, 0x02, 0x03]
        event = {"type": "response.output_audio.delta", "delta": "AQID"}
        audio = extract_output_audio_delta(event)
        self.assertEqual(audio, b"\x01\x02\x03")

    def test_is_response_done(self) -> None:
        self.assertTrue(is_response_done({"type": "response.done"}))
        self.assertTrue(is_response_done({"type": "response.output_audio.done"}))
        self.assertFalse(is_response_done({"type": "response.created"}))


if __name__ == "__main__":
    unittest.main()
