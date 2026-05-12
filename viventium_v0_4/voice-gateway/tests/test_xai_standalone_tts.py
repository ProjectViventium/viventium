import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from livekit.plugins import xai

from worker import XAI_TTS_CAPABILITIES


class TestXaiStandaloneTTS(unittest.TestCase):
    def test_livekit_xai_tts_reports_streaming_pcm_contract(self) -> None:
        tts = xai.TTS(api_key="synthetic_xai_test", voice="Eve", language="en")

        self.assertTrue(tts.capabilities.streaming)
        self.assertEqual(tts.sample_rate, 24000)
        self.assertEqual(tts.num_channels, 1)
        self.assertEqual(tts.provider, "xAI")

    def test_xai_capability_contract_lists_documented_tags(self) -> None:
        tags = XAI_TTS_CAPABILITIES["speech_tags"]

        self.assertIn("[long-pause]", tags["inline"])
        self.assertIn("[tongue-click]", tags["inline"])
        self.assertIn("whisper", tags["wrapping"])
        self.assertIn("build-intensity", tags["wrapping"])


if __name__ == "__main__":
    unittest.main()
