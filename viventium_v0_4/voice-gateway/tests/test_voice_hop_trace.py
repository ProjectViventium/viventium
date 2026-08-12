import json
import os
import sys
import unittest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from voice_hop_trace import VoiceHopTrace


class TestVoiceHopTrace(unittest.TestCase):
    def test_terminal_summary_proves_all_eight_hops(self) -> None:
        trace = VoiceHopTrace(correlation_id="lc_1", call_session_id="call_1")
        for index, hop in enumerate(
            (
                "utterance_end",
                "gateway_dispatch",
                "agent_start",
                "tool_start",
                "tool_end",
                "first_model_token",
                "tts_first_byte",
                "audio_output",
            )
        ):
            trace.record(hop, 1_000 + index * 100)

        summary = trace.terminal_summary({"tool_start->tool_end": 500})

        self.assertEqual(summary["status"], "complete")
        self.assertEqual(summary["missingHops"], [])
        self.assertIsNone(summary["firstBreach"])

    def test_terminal_summary_truthfully_classifies_missing_hops(self) -> None:
        trace = VoiceHopTrace(correlation_id="lc_1", call_session_id="call_1")
        trace.record("utterance_end", 1_000)
        trace.record("gateway_dispatch", 1_100)

        summary = trace.terminal_summary({})

        self.assertEqual(summary["status"], "incomplete")
        self.assertIn("first_model_token", summary["missingHops"])
        self.assertNotIn("tool_start", summary["missingHops"])
        self.assertIn("audio_output", summary["missingHops"])

    def test_tool_hops_are_optional_when_no_tool_was_observed(self) -> None:
        trace = VoiceHopTrace(correlation_id="corr-no-tool", call_session_id="call-1")
        for index, hop in enumerate(
            (
                "utterance_end",
                "gateway_dispatch",
                "agent_start",
                "first_model_token",
                "tts_first_byte",
                "audio_output",
            )
        ):
            trace.record(hop, 1_000 + index * 100)

        summary = trace.terminal_summary({})

        self.assertEqual(summary["status"], "complete")
        self.assertNotIn("tool_start", summary["missingHops"])
        self.assertNotIn("tool_end", summary["missingHops"])

    def test_identifies_first_configured_breaching_hop(self) -> None:
        trace = VoiceHopTrace(correlation_id="lc_1", call_session_id="call_1")
        trace.record("utterance_end", 1_000)
        trace.record("gateway_dispatch", 1_100)
        trace.record("agent_start", 2_500)
        trace.record("first_model_token", 3_000)

        breach = trace.first_breach(
            {
                "utterance_end->gateway_dispatch": 250,
                "gateway_dispatch->agent_start": 1_000,
            }
        )

        self.assertEqual(
            breach,
            {
                "hop": "gateway_dispatch->agent_start",
                "elapsedMs": 1_400.0,
                "gateMs": 1_000.0,
            },
        )

    def test_log_payload_is_structured_and_contains_no_transcript(self) -> None:
        trace = VoiceHopTrace(correlation_id="lc_1", call_session_id="call_1")
        trace.record("first_model_token", 2_000)

        payload = json.loads(trace.log_payload("first_model_token"))

        self.assertEqual(payload["event"], "voice_hop")
        self.assertEqual(payload["correlationId"], "lc_1")
        self.assertNotIn("text", payload)
        self.assertNotIn("transcript", payload)


if __name__ == "__main__":
    unittest.main()
