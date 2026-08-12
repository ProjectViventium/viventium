import os
import sys
import unittest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from speaker_segments import CallScopedSegmentSequencer, SpeakerSegmentTracker


class TestSpeakerSegmentTracker(unittest.TestCase):
    def test_call_scoped_sequence_is_unique_across_owner_guests_revisions_and_reconnect(self) -> None:
        sequencer = CallScopedSegmentSequencer()

        def tracker(identity, track_sid, namespace="", owner=False):
            return SpeakerSegmentTracker(
                call_session_id="call_1",
                participant_identity=identity,
                track_sid=track_sid,
                owner_signed=owner,
                participant_authenticated=not owner,
                id_namespace=namespace,
                segment_sequencer=sequencer,
            )

        owner = tracker("owner", "TR_owner", owner=True)
        guest_one = tracker("guest_1", "TR_guest_1", "guest_1")
        guest_two = tracker("guest_2", "TR_guest_2", "guest_2")
        owner_segment = owner.ingest(
            transcript="Owner speaking",
            is_final=True,
            provider_speaker_id="A",
            created_at=1.0,
            start_time=0.0,
            end_time=1.0,
        )[-1]
        guest_one_segment = guest_one.ingest(
            transcript="Guest one",
            is_final=True,
            provider_speaker_id="A",
            created_at=2.0,
            start_time=1.0,
            end_time=2.0,
        )[-1]
        guest_two_segment = guest_two.ingest(
            transcript="Guest two",
            is_final=True,
            provider_speaker_id="A",
            created_at=3.0,
            start_time=2.0,
            end_time=3.0,
        )[-1]
        guest_one_changes = guest_one.ingest(
            transcript="Second device speaker",
            is_final=True,
            provider_speaker_id="B",
            created_at=4.0,
            start_time=3.0,
            end_time=4.0,
        )
        guest_one_revision = next(
            item
            for item in guest_one_changes
            if item["segmentId"] == guest_one_segment["segmentId"]
        )
        new_guest_segment = next(
            item
            for item in guest_one_changes
            if item["segmentId"] != guest_one_segment["segmentId"]
        )
        reconnected = tracker(
            "guest_1", "TR_guest_1_reconnected", "guest_1_reconnected"
        ).ingest(
            transcript="Back again",
            is_final=True,
            provider_speaker_id="A",
            created_at=5.0,
            start_time=4.0,
            end_time=5.0,
        )[-1]

        self.assertEqual(
            [
                owner_segment["sequence"],
                guest_one_segment["sequence"],
                guest_two_segment["sequence"],
                new_guest_segment["sequence"],
                reconnected["sequence"],
            ],
            [1, 2, 3, 4, 5],
        )
        self.assertEqual(guest_one_revision["sequence"], guest_one_segment["sequence"])

    def _tracker(self) -> SpeakerSegmentTracker:
        return SpeakerSegmentTracker(
            call_session_id="call_public_safe",
            participant_identity="owner-participant",
            participant_name="Owner",
            track_sid="TR_audio_owner",
            owner_signed=True,
        )

    def test_single_provider_speaker_on_signed_track_is_verified_owner(self) -> None:
        tracker = self._tracker()

        changes = tracker.ingest(
            transcript="Synthetic hello",
            is_final=True,
            provider_speaker_id="A",
            created_at=100.0,
            start_time=10.0,
            end_time=11.0,
        )
        segments, revisions = tracker.finalize_turn("Synthetic hello")

        self.assertEqual(len(changes), 1)
        self.assertEqual(revisions, [])
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["version"], 1)
        self.assertEqual(segments[0]["turnId"], "turn_000001")
        self.assertEqual(segments[0]["segmentId"], "segment_000001")
        self.assertEqual(segments[0]["sequence"], 1)
        self.assertEqual(segments[0]["revision"], 1)
        self.assertEqual(segments[0]["speaker"]["key"], "participant:owner-participant")
        self.assertEqual(segments[0]["speaker"]["label"], "Owner")
        self.assertEqual(segments[0]["speaker"]["source"], "hybrid")
        self.assertEqual(segments[0]["speaker"]["attribution"], "verified")
        self.assertEqual(segments[0]["speaker"]["actorTrust"], "owner_participant")
        self.assertEqual(segments[0]["speaker"]["providerSpeakerId"], "A")
        self.assertNotIn("confidence", segments[0]["speaker"])

    def test_final_short_utterance_without_stable_timing_abstains_to_unknown(self) -> None:
        tracker = self._tracker()

        tracker.ingest(
            transcript="Yes",
            is_final=True,
            provider_speaker_id="A",
            created_at=100.0,
        )
        segments, _ = tracker.finalize_turn("Yes")

        self.assertEqual(segments[0]["speaker"]["key"], "unknown")
        self.assertEqual(segments[0]["speaker"]["label"], "Unknown")
        self.assertEqual(segments[0]["speaker"]["attribution"], "unknown")
        self.assertEqual(segments[0]["speaker"]["actorTrust"], "unknown")
        self.assertEqual(segments[0]["speaker"]["providerSpeakerId"], "A")
        self.assertTrue(segments[0]["uncertain"])

    def test_interim_abstains_then_stable_final_revision_can_verify(self) -> None:
        tracker = self._tracker()
        interim = tracker.ingest(
            transcript="Synthetic",
            is_final=False,
            provider_speaker_id="A",
            created_at=100.0,
            start_time=10.0,
            end_time=10.4,
        )[0]
        final = tracker.ingest(
            transcript="Synthetic hello",
            is_final=True,
            provider_speaker_id="A",
            created_at=100.5,
            start_time=10.0,
            end_time=11.0,
        )[0]

        self.assertEqual(interim["speaker"]["attribution"], "unknown")
        self.assertEqual(final["speaker"]["attribution"], "verified")
        self.assertEqual(final["revision"], interim["revision"] + 1)

    def test_second_provider_speaker_downgrades_entire_track_deterministically(self) -> None:
        tracker = self._tracker()
        first_changes = tracker.ingest(
            transcript="First speaker",
            is_final=True,
            provider_speaker_id="A",
            created_at=100.0,
            start_time=10.0,
            end_time=11.0,
        )
        first_segment = first_changes[0]
        tracker.finalize_turn("First speaker")

        second_changes = tracker.ingest(
            transcript="Second speaker",
            is_final=True,
            provider_speaker_id="B",
            created_at=101.0,
            start_time=11.0,
            end_time=12.0,
        )
        session_states = tracker.pop_session_state_changes()
        current, revisions = tracker.finalize_turn("Second speaker")

        self.assertEqual(first_segment["speaker"]["attribution"], "verified")
        self.assertEqual(len(revisions), 1)
        self.assertEqual(revisions[0]["segmentId"], first_segment["segmentId"])
        self.assertEqual(revisions[0]["revision"], 2)
        self.assertEqual(revisions[0]["speaker"]["key"], "provider:A")
        self.assertEqual(revisions[0]["speaker"]["label"], "Speaker 1")
        self.assertEqual(revisions[0]["speaker"]["attribution"], "unverified")
        self.assertEqual(revisions[0]["speaker"]["actorTrust"], "shared_mic_unverified")
        self.assertEqual(current[0]["speaker"]["key"], "provider:B")
        self.assertEqual(current[0]["speaker"]["label"], "Speaker 2")
        self.assertEqual(current[0]["speaker"]["attribution"], "unverified")
        self.assertEqual(current[0]["speaker"]["actorTrust"], "shared_mic_unverified")
        self.assertEqual([item["segmentId"] for item in second_changes], [first_segment["segmentId"], current[0]["segmentId"]])
        self.assertEqual(len(session_states), 1)
        self.assertEqual(session_states[0]["version"], 1)
        self.assertEqual(session_states[0]["callSessionId"], "call_public_safe")
        self.assertEqual(
            session_states[0]["attributionState"],
            "shared_mic_unverified",
        )
        self.assertEqual(session_states[0]["sourceTrackSid"], "TR_audio_owner")
        self.assertEqual(tracker.pop_session_state_changes(), [])

    def test_duplicate_final_event_does_not_create_duplicate_or_revision(self) -> None:
        tracker = self._tracker()
        first = tracker.ingest(
            transcript="Same final",
            is_final=True,
            provider_speaker_id="A",
            created_at=100.0,
        )
        duplicate = tracker.ingest(
            transcript="Same final",
            is_final=True,
            provider_speaker_id="A",
            created_at=100.0,
        )
        segments, revisions = tracker.finalize_turn("Same final")

        self.assertEqual(len(first), 1)
        self.assertEqual(duplicate, [])
        self.assertEqual(len(segments), 1)
        self.assertEqual(revisions, [])

    def test_interim_reuses_segment_id_and_increments_revision(self) -> None:
        tracker = self._tracker()
        first = tracker.ingest(
            transcript="Synthe",
            is_final=False,
            provider_speaker_id="A",
            created_at=100.0,
        )[0]
        revised = tracker.ingest(
            transcript="Synthetic hello",
            is_final=True,
            provider_speaker_id="A",
            created_at=100.2,
        )[0]

        self.assertEqual(revised["segmentId"], first["segmentId"])
        self.assertEqual(revised["sequence"], first["sequence"])
        self.assertEqual(revised["revision"], 2)
        self.assertTrue(revised["isFinal"])

    def test_missing_provider_identity_abstains_to_unknown(self) -> None:
        tracker = self._tracker()
        tracker.ingest(
            transcript="Unattributed words",
            is_final=True,
            provider_speaker_id=None,
            created_at=100.0,
        )
        segments, _ = tracker.finalize_turn("Unattributed words")

        self.assertEqual(segments[0]["speaker"]["key"], "unknown")
        self.assertEqual(segments[0]["speaker"]["label"], "Unknown")
        self.assertEqual(segments[0]["speaker"]["source"], "unknown")
        self.assertEqual(segments[0]["speaker"]["attribution"], "unknown")
        self.assertEqual(segments[0]["speaker"]["actorTrust"], "unknown")
        self.assertTrue(segments[0]["uncertain"])

    def test_local_route_never_invents_cloud_speaker_attribution(self) -> None:
        tracker = self._tracker()
        segments, _ = tracker.finalize_turn("Local-only transcript")

        self.assertEqual(segments[0]["speaker"]["source"], "unknown")
        self.assertEqual(segments[0]["speaker"]["label"], "Unknown")
        self.assertNotIn("providerSpeakerId", segments[0]["speaker"])


if __name__ == "__main__":
    unittest.main()
