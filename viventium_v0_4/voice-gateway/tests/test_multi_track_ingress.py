import asyncio
import os
import sys
import unittest
from types import SimpleNamespace


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from multi_track_ingress import MultiTrackIngressCoordinator
from speaker_segments import shared_microphone_state_applies_to_track


class _AudioStream:
    def __init__(self, frames):
        self._frames = frames

    async def __aiter__(self):
        for frame in self._frames:
            yield SimpleNamespace(frame=frame)


class _SpeechStream:
    def __init__(self, events):
        self._events = events
        self.frames = []
        self.ended = False

    def push_frame(self, frame):
        self.frames.append(frame)

    def end_input(self):
        self.ended = True

    async def __aiter__(self):
        await asyncio.sleep(0)
        for event in self._events:
            yield event


class _STT:
    def __init__(self, event_batches):
        self._event_batches = list(event_batches)

    def stream(self):
        return _SpeechStream(self._event_batches.pop(0))


def _final(text, speaker_id, created_at, start_time=0.0, end_time=0.0):
    return SimpleNamespace(
        type="SpeechEventType.FINAL_TRANSCRIPT",
        created_at=created_at,
        alternatives=[
            SimpleNamespace(
                text=text,
                speaker_id=speaker_id,
                start_time=start_time,
                end_time=end_time,
            )
        ],
    )


def _segment(segment_id, track_sid, sequence, start_ms, end_ms, actor_trust):
    return {
        "version": 1,
        "segmentId": segment_id,
        "callSessionId": "call_1",
        "turnId": f"turn-{segment_id}",
        "sequence": sequence,
        "revision": 1,
        "startTimeMs": start_ms,
        "endTimeMs": end_ms,
        "text": "Synthetic stable sentence",
        "isFinal": True,
        "speaker": {
            "key": f"participant:{track_sid}",
            "label": track_sid,
            "source": "hybrid",
            "attribution": "verified",
            "actorTrust": actor_trust,
            "trackSid": track_sid,
        },
        "overlap": False,
        "uncertain": False,
    }


class TestMultiTrackIngressCoordinator(unittest.TestCase):
    def test_guest_shared_mic_state_persists_before_revisions_and_restores_per_track(self) -> None:
        async def first_connection():
            observed = []
            turns = []
            coordinator = MultiTrackIngressCoordinator(
                call_session_id="call_1",
                owner_participant_identity="owner",
                stt_impl=_STT(
                    [[
                        _final("Guest speaker A sentence", "A", 100.0, 0.0, 1.0),
                        _final("Guest speaker B sentence", "B", 101.0, 2.0, 3.0),
                    ]]
                ),
                audio_stream_factory=lambda _track: _AudioStream([]),
                on_segment_changes=lambda value: _append_async(
                    observed, ("segments", value)
                ),
                on_session_state_change=lambda value: _append_async(
                    observed, ("state", value)
                ),
                on_ambient_turn=lambda value: _append_async(turns, value),
                clock=lambda: 0.0,
            )
            coordinator.track_joined(
                SimpleNamespace(identity="guest", name="Guest"),
                SimpleNamespace(sid="TR_guest", kind="audio"),
                SimpleNamespace(sid="TR_guest", kind="audio"),
            )
            await coordinator.wait_until_idle()
            return observed, turns

        observed, turns = asyncio.run(first_connection())
        state_index = next(index for index, item in enumerate(observed) if item[0] == "state")
        shared_segment_index = next(
            index
            for index, item in enumerate(observed)
            if item[0] == "segments"
            and any(
                segment["speaker"]["actorTrust"] == "shared_mic_unverified"
                for segment in item[1]
            )
        )
        state = observed[state_index][1]
        self.assertLess(state_index, shared_segment_index)
        self.assertEqual(state["sourceTrackSid"], "TR_guest")
        self.assertEqual(state["sharedTrackSids"], ["TR_guest"])
        self.assertEqual(state["sourceParticipantIdentity"], "guest")
        self.assertEqual(state["sharedParticipantIdentities"], ["guest"])
        self.assertEqual(
            turns[-1]["segments"][0]["speaker"]["actorTrust"],
            "shared_mic_unverified",
        )

        async def recreated_connection():
            turns = []
            coordinator = MultiTrackIngressCoordinator(
                call_session_id="call_1",
                owner_participant_identity="owner",
                stt_impl=_STT(
                    [[_final("Guest remains unverified", "A", 102.0, 0.0, 1.0)]]
                ),
                audio_stream_factory=lambda _track: _AudioStream([]),
                on_segment_changes=lambda _value: _append_async([], _value),
                on_session_state_change=lambda _value: _append_async([], _value),
                on_ambient_turn=lambda value: _append_async(turns, value),
                initial_speaker_session_state=state,
                clock=lambda: 0.0,
            )
            coordinator.track_joined(
                SimpleNamespace(identity="guest", name="Guest"),
                SimpleNamespace(sid="TR_guest_reconnected", kind="audio"),
                SimpleNamespace(sid="TR_guest_reconnected", kind="audio"),
            )
            await coordinator.wait_until_idle()
            return turns

        recreated_turns = asyncio.run(recreated_connection())
        self.assertEqual(
            recreated_turns[0]["segments"][0]["speaker"]["actorTrust"],
            "shared_mic_unverified",
        )

    def test_shared_mic_restore_is_identity_scoped_across_track_replacement(self) -> None:
        scoped = {
            "version": 1,
            "attributionState": "shared_mic_unverified",
            "sharedTrackSids": ["TR_guest"],
            "sharedParticipantIdentities": ["guest"],
        }
        legacy = {
            "version": 1,
            "attributionState": "shared_mic_unverified",
            "sourceTrackSid": "TR_guest",
        }

        self.assertTrue(
            shared_microphone_state_applies_to_track(scoped, "TR_guest_reconnected", "guest")
        )
        self.assertFalse(
            shared_microphone_state_applies_to_track(scoped, "TR_owner", "owner")
        )
        self.assertTrue(shared_microphone_state_applies_to_track(scoped, "", ""))
        self.assertTrue(
            shared_microphone_state_applies_to_track(legacy, "TR_owner", "owner")
        )

    def test_owner_absence_stops_ambient_transcript_and_segment_persistence(self) -> None:
        async def run():
            observed = []
            coordinator = MultiTrackIngressCoordinator(
                call_session_id="call_1",
                owner_participant_identity="owner",
                stt_impl=_STT([[_final("Guest after owner left", "A", 100.0, 0.0, 1.0)]]),
                audio_stream_factory=lambda _track: _AudioStream([object()]),
                on_segment_changes=lambda value: _append_async(observed, ("segments", value)),
                on_session_state_change=lambda value: _append_async(observed, ("state", value)),
                on_ambient_turn=lambda value: _append_async(observed, ("turn", value)),
                owner_present=lambda: False,
                clock=lambda: 0.0,
            )
            coordinator.track_joined(
                SimpleNamespace(identity="guest", name="Guest"),
                SimpleNamespace(sid="TR_guest", kind="audio"),
                SimpleNamespace(sid="TR_guest", kind="audio"),
            )
            await asyncio.sleep(0.1)
            await coordinator.close()
            return observed

        self.assertEqual(asyncio.run(run()), [])

    def test_same_guest_track_resumes_after_owner_disconnect_and_reconnect(self) -> None:
        async def run():
            owner_present = [True]
            now = [100.0]
            release_first_stream = asyncio.Event()
            turns = []

            class FirstSpeechStream(_SpeechStream):
                async def __aiter__(self):
                    await release_first_stream.wait()
                    if False:
                        yield None

            class ReconnectSTT:
                streams = 0

                def stream(self):
                    self.streams += 1
                    if self.streams == 1:
                        return FirstSpeechStream([])
                    return _SpeechStream(
                        [_final("Guest after owner reconnect", "A", 102.0, 0.0, 1.0)]
                    )

            coordinator = MultiTrackIngressCoordinator(
                call_session_id="call_1",
                owner_participant_identity="owner",
                stt_impl=ReconnectSTT(),
                audio_stream_factory=lambda _track: _AudioStream([]),
                on_segment_changes=lambda value: _append_async([], value),
                on_session_state_change=lambda value: _append_async([], value),
                on_ambient_turn=lambda value: _append_async(turns, value),
                owner_present=lambda: owner_present[0],
                clock=lambda: now[0],
            )
            self.assertTrue(
                coordinator.track_joined(
                    SimpleNamespace(identity="guest", name="Guest"),
                    SimpleNamespace(sid="TR_guest", kind="audio"),
                    SimpleNamespace(sid="TR_guest", kind="audio"),
                )
            )
            await asyncio.sleep(0)
            owner_present[0] = False
            release_first_stream.set()
            await asyncio.sleep(0.1)
            self.assertEqual(coordinator.active_track_sids, ("TR_guest",))
            now[0] = 160.0
            owner_present[0] = True
            for _ in range(20):
                if turns:
                    break
                await asyncio.sleep(0.05)
            await coordinator.close()
            return turns

        turns = asyncio.run(run())
        self.assertEqual(turns[0]["segments"][0]["text"], "Guest after owner reconnect")
        self.assertEqual(turns[0]["segments"][0]["startTimeMs"], 60_000)
        self.assertEqual(turns[0]["segments"][0]["endTimeMs"], 61_000)

    def test_failed_state_persistence_retries_before_any_shared_segment_delivery(self) -> None:
        async def run():
            observed = []
            state_attempts = 0

            async def persist_state(value):
                nonlocal state_attempts
                state_attempts += 1
                observed.append(("state_attempt", value["sourceTrackSid"]))
                if state_attempts == 1:
                    raise RuntimeError("synthetic transient persistence failure")

            coordinator = MultiTrackIngressCoordinator(
                call_session_id="call_1",
                owner_participant_identity="owner",
                stt_impl=_STT(
                    [
                        [
                            _final("First guest voice", "A", 100.0, 0.0, 1.0),
                            _final("Second guest voice", "B", 101.0, 2.0, 3.0),
                        ],
                        [],
                    ]
                ),
                audio_stream_factory=lambda _track: _AudioStream([]),
                on_segment_changes=lambda value: _append_async(
                    observed, ("segments", value)
                ),
                on_session_state_change=persist_state,
                on_ambient_turn=lambda _value: _append_async([], _value),
                on_degraded=lambda reason, _track_sid: observed.append(("degraded", reason)),
                max_stream_retries=1,
                retry_delay_s=0.0,
                clock=lambda: 0.0,
            )
            coordinator.track_joined(
                SimpleNamespace(identity="guest", name="Guest"),
                SimpleNamespace(sid="TR_guest", kind="audio"),
                SimpleNamespace(sid="TR_guest", kind="audio"),
            )
            await coordinator.wait_until_idle()
            return observed, state_attempts

        observed, state_attempts = asyncio.run(run())
        self.assertEqual(state_attempts, 2)
        second_state_index = [
            index for index, value in enumerate(observed) if value[0] == "state_attempt"
        ][1]
        unsafe_delivery_indexes = [
            index
            for index, value in enumerate(observed)
            if value[0] == "segments"
            and any(
                segment["speaker"]["actorTrust"] == "shared_mic_unverified"
                for segment in value[1]
            )
        ]
        self.assertTrue(
            all(second_state_index < delivery_index for delivery_index in unsafe_delivery_indexes)
        )
        self.assertIn(("degraded", "track_stream_retry"), observed)

    def test_call_wide_owner_guest_overlap_demotes_and_revises_both_tracks(self) -> None:
        coordinator = MultiTrackIngressCoordinator(
            call_session_id="call_1",
            owner_participant_identity="owner",
            stt_impl=_STT([]),
            audio_stream_factory=lambda _track: _AudioStream([]),
            on_segment_changes=lambda value: _append_async([], value),
            on_ambient_turn=lambda value: _append_async([], value),
        )
        owner = _segment("owner-segment", "TR_owner", 1, 0, 1_000, "owner_participant")
        guest = _segment(
            "guest-segment", "TR_guest", 2, 500, 1_500, "authenticated_participant"
        )

        self.assertEqual(coordinator.apply_call_wide_overlap([owner]), [])
        revisions = coordinator.apply_call_wide_overlap([guest])

        self.assertEqual(guest["speaker"]["attribution"], "unknown")
        self.assertTrue(guest["overlap"])
        self.assertEqual(len(revisions), 1)
        self.assertEqual(revisions[0]["segmentId"], "owner-segment")
        self.assertEqual(revisions[0]["revision"], 2)
        self.assertEqual(revisions[0]["speaker"]["attribution"], "unknown")
        self.assertEqual(revisions[0]["sequence"], 1)

    def test_call_wide_sequential_tracks_remain_attributed_across_recreated_coordinator(self) -> None:
        def coordinator():
            return MultiTrackIngressCoordinator(
                call_session_id="call_1",
                owner_participant_identity="owner",
                stt_impl=_STT([]),
                audio_stream_factory=lambda _track: _AudioStream([]),
                on_segment_changes=lambda value: _append_async([], value),
                on_ambient_turn=lambda value: _append_async([], value),
            )

        first = coordinator()
        owner = _segment("owner-segment", "TR_owner", 1, 0, 1_000, "owner_participant")
        guest = _segment(
            "guest-segment", "TR_guest", 2, 2_000, 3_000, "authenticated_participant"
        )
        self.assertEqual(first.apply_call_wide_overlap([owner]), [])
        self.assertEqual(first.apply_call_wide_overlap([guest]), [])
        self.assertEqual(owner["speaker"]["attribution"], "verified")
        self.assertEqual(guest["speaker"]["attribution"], "verified")

        # A reconnect starts a fresh bounded overlap window; it must not invent overlap with
        # pre-reconnect audio and must preserve the globally assigned sequence values supplied.
        recreated = coordinator()
        self.assertEqual(recreated.apply_call_wide_overlap([guest]), [])
        self.assertEqual(guest["sequence"], 2)

    def test_two_guest_tracks_are_ambient_and_never_owner_authorized(self) -> None:
        async def run():
            changes = []
            turns = []
            coordinator = MultiTrackIngressCoordinator(
                call_session_id="call_1",
                owner_participant_identity="owner",
                stt_impl=_STT(
                    [
                        [_final("Guest one", "A", 100.0, 0.0, 1.0)],
                        [_final("Guest two", "A", 101.0, 2.0, 3.0)],
                    ]
                ),
                audio_stream_factory=lambda track: _AudioStream([track.sid]),
                on_segment_changes=lambda value: _append_async(changes, value),
                on_ambient_turn=lambda value: _append_async(turns, value),
            )
            self.assertFalse(
                coordinator.track_joined(
                    SimpleNamespace(identity="owner", name="Owner"),
                    SimpleNamespace(sid="TR_owner", kind="audio"),
                    SimpleNamespace(sid="TR_owner", kind="audio"),
                )
            )
            for identity, sid in (("guest-1", "TR_guest_1"), ("guest-2", "TR_guest_2")):
                self.assertTrue(
                    coordinator.track_joined(
                        SimpleNamespace(identity=identity, name=identity),
                        SimpleNamespace(sid=sid, kind="audio"),
                        SimpleNamespace(sid=sid, kind="audio"),
                    )
                )
            await coordinator.wait_until_idle()
            return changes, turns

        changes, turns = asyncio.run(run())

        self.assertEqual(len(turns), 2)
        self.assertTrue(all(turn["ingressKind"] == "ambient_participant" for turn in turns))
        segments = [turn["segments"][0] for turn in turns]
        self.assertEqual(len({segment["segmentId"] for segment in segments}), 2)
        self.assertTrue(
            all(
                segment["speaker"]["actorTrust"] == "authenticated_participant"
                for segment in segments
            )
        )
        self.assertTrue(
            all(segment["speaker"]["attribution"] == "verified" for segment in segments)
        )

    def test_join_duplicate_leave_and_reconnect_are_single_flight(self) -> None:
        async def run():
            release = asyncio.Event()

            class BlockingStream(_SpeechStream):
                async def __aiter__(self):
                    await release.wait()
                    if False:
                        yield None

            class BlockingSTT:
                def stream(self):
                    return BlockingStream([])

            coordinator = MultiTrackIngressCoordinator(
                call_session_id="call_1",
                owner_participant_identity="owner",
                stt_impl=BlockingSTT(),
                audio_stream_factory=lambda _track: _AudioStream([]),
                on_segment_changes=lambda _value: _append_async([], _value),
                on_ambient_turn=lambda _value: _append_async([], _value),
            )
            participant = SimpleNamespace(identity="guest", name="Guest")
            track = SimpleNamespace(sid="TR_guest", kind="audio")
            publication = SimpleNamespace(sid="TR_guest", kind="audio")
            self.assertTrue(coordinator.track_joined(participant, track, publication))
            self.assertFalse(coordinator.track_joined(participant, track, publication))
            await coordinator.track_left("TR_guest")
            self.assertEqual(coordinator.active_track_sids, ())
            self.assertTrue(coordinator.track_joined(participant, track, publication))
            await coordinator.close()
            self.assertEqual(coordinator.active_track_sids, ())

        asyncio.run(run())

    def test_overlapping_tracks_emit_exact_timestamps_and_prior_revision(self) -> None:
        async def run():
            turns = []
            coordinator = MultiTrackIngressCoordinator(
                call_session_id="call_1",
                owner_participant_identity="owner",
                stt_impl=_STT(
                    [
                        [_final("First", "A", 0.0, 10.0, 12.0)],
                        [_final("Second", "A", 0.0, 11.0, 13.0)],
                    ]
                ),
                audio_stream_factory=lambda _track: _AudioStream([]),
                on_segment_changes=lambda _value: _append_async([], _value),
                on_ambient_turn=lambda value: _append_async(turns, value),
                clock=lambda: 0.0,
            )
            for identity, sid in (("guest-1", "TR_1"), ("guest-2", "TR_2")):
                coordinator.track_joined(
                    SimpleNamespace(identity=identity, name=identity),
                    SimpleNamespace(sid=sid, kind="audio"),
                    SimpleNamespace(sid=sid, kind="audio"),
                )
            await coordinator.wait_until_idle()
            return turns

        turns = asyncio.run(run())

        first = turns[0]["segments"][0]
        second_turn = turns[1]["segments"]
        second = next(item for item in second_turn if item["segmentId"] != first["segmentId"])
        first_revision = next(item for item in second_turn if item["segmentId"] == first["segmentId"])
        self.assertEqual((first["startTimeMs"], first["endTimeMs"]), (10_000, 12_000))
        self.assertTrue(second["overlap"])
        self.assertTrue(second["uncertain"])
        self.assertEqual(second["speaker"]["label"], "Unknown")
        self.assertEqual(second["speaker"]["attribution"], "unknown")
        self.assertEqual(first_revision["revision"], first["revision"] + 1)
        self.assertTrue(first_revision["overlap"])
        self.assertEqual(first_revision["speaker"]["label"], "Unknown")

    def test_ambient_track_count_is_bounded_and_reports_degraded(self) -> None:
        async def run():
            degraded = []

            class BlockingStream(_SpeechStream):
                async def __aiter__(self):
                    await asyncio.Event().wait()
                    if False:
                        yield None

            class BlockingSTT:
                def stream(self):
                    return BlockingStream([])

            coordinator = MultiTrackIngressCoordinator(
                call_session_id="call_1",
                owner_participant_identity="owner",
                stt_impl=BlockingSTT(),
                audio_stream_factory=lambda _track: _AudioStream([]),
                on_segment_changes=lambda _value: _append_async([], _value),
                on_ambient_turn=lambda _value: _append_async([], _value),
                on_degraded=lambda reason, track_sid: degraded.append((reason, track_sid)),
                max_tracks=1,
            )
            first = coordinator.track_joined(
                SimpleNamespace(identity="guest-1", name="Guest 1"),
                SimpleNamespace(sid="TR_1", kind="audio"),
                SimpleNamespace(sid="TR_1", kind="audio"),
            )
            second = coordinator.track_joined(
                SimpleNamespace(identity="guest-2", name="Guest 2"),
                SimpleNamespace(sid="TR_2", kind="audio"),
                SimpleNamespace(sid="TR_2", kind="audio"),
            )
            await coordinator.close()
            return first, second, degraded

        first, second, degraded = asyncio.run(run())
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(degraded, [("track_limit", "TR_2")])

    def test_transient_track_stt_failure_retries_without_affecting_owner_session(self) -> None:
        async def run():
            turns = []
            degraded = []

            class FailingStream(_SpeechStream):
                async def __aiter__(self):
                    raise RuntimeError("synthetic transient STT failure")
                    if False:
                        yield None

            class RetrySTT:
                def __init__(self):
                    self.calls = 0

                def stream(self):
                    self.calls += 1
                    if self.calls == 1:
                        return FailingStream([])
                    return _SpeechStream([_final("Guest recovered", "A", 0.0, 0.0, 1.0)])

            stt = RetrySTT()
            coordinator = MultiTrackIngressCoordinator(
                call_session_id="call_1",
                owner_participant_identity="owner",
                stt_impl=stt,
                audio_stream_factory=lambda _track: _AudioStream([]),
                on_segment_changes=lambda _value: _append_async([], _value),
                on_ambient_turn=lambda value: _append_async(turns, value),
                on_degraded=lambda reason, track_sid: degraded.append((reason, track_sid)),
                max_stream_retries=1,
                retry_delay_s=0.0,
                clock=lambda: 0.0,
            )
            coordinator.track_joined(
                SimpleNamespace(identity="guest", name="Guest"),
                SimpleNamespace(sid="TR_guest", kind="audio"),
                SimpleNamespace(sid="TR_guest", kind="audio"),
            )
            await coordinator.wait_until_idle()
            return stt.calls, turns, degraded

        calls, turns, degraded = asyncio.run(run())
        self.assertEqual(calls, 2)
        self.assertEqual(len(turns), 1)
        self.assertEqual(degraded, [("track_stream_retry", "TR_guest")])

    def test_late_join_stream_relative_timestamps_share_a_call_timeline(self) -> None:
        async def run():
            turns = []
            clock_values = iter((100.0, 100.0, 110.0))
            coordinator = MultiTrackIngressCoordinator(
                call_session_id="call_1",
                owner_participant_identity="owner",
                stt_impl=_STT(
                    [
                        [_final("First", "A", 0.0, 0.0, 1.0)],
                        [_final("Ten seconds later", "A", 0.0, 0.0, 1.0)],
                    ]
                ),
                audio_stream_factory=lambda _track: _AudioStream([]),
                on_segment_changes=lambda _value: _append_async([], _value),
                on_ambient_turn=lambda value: _append_async(turns, value),
                clock=lambda: next(clock_values),
            )
            for identity, sid in (("guest-1", "TR_1"), ("guest-2", "TR_2")):
                coordinator.track_joined(
                    SimpleNamespace(identity=identity, name=identity),
                    SimpleNamespace(sid=sid, kind="audio"),
                    SimpleNamespace(sid=sid, kind="audio"),
                )
            await coordinator.wait_until_idle()
            return turns

        turns = asyncio.run(run())

        first = turns[0]["segments"][0]
        second = turns[1]["segments"][0]
        self.assertEqual((first["startTimeMs"], first["endTimeMs"]), (0, 1_000))
        self.assertEqual((second["startTimeMs"], second["endTimeMs"]), (10_000, 11_000))
        self.assertFalse(first["overlap"])
        self.assertFalse(second["overlap"])

    def test_retained_overlap_history_is_bounded(self) -> None:
        coordinator = MultiTrackIngressCoordinator(
            call_session_id="call_1",
            owner_participant_identity="owner",
            stt_impl=_STT([]),
            audio_stream_factory=lambda _track: _AudioStream([]),
            on_segment_changes=lambda _value: _append_async([], _value),
            on_ambient_turn=lambda _value: _append_async([], _value),
            max_final_segments=2,
            overlap_window_ms=1_000,
            clock=lambda: 0.0,
        )

        for index in range(4):
            coordinator._apply_cross_track_overlap(
                [
                    {
                        "segmentId": f"segment_{index}",
                        "revision": 1,
                        "startTimeMs": index * 2_000,
                        "endTimeMs": index * 2_000 + 500,
                        "speaker": {"trackSid": f"TR_{index}"},
                    }
                ]
            )

        self.assertLessEqual(coordinator.retained_final_segment_count, 2)

    def test_latest_mode_is_used_for_ambient_persistence(self) -> None:
        async def run():
            turns = []
            coordinator = MultiTrackIngressCoordinator(
                call_session_id="call_1",
                owner_participant_identity="owner",
                mode="call",
                stt_impl=_STT([[_final("Ambient", "A", 0.0)]]),
                audio_stream_factory=lambda _track: _AudioStream([]),
                on_segment_changes=lambda _value: _append_async([], _value),
                on_ambient_turn=lambda value: _append_async(turns, value),
                clock=lambda: 0.0,
            )
            coordinator.set_mode("listen_only")
            coordinator.track_joined(
                SimpleNamespace(identity="guest", name="Guest"),
                SimpleNamespace(sid="TR_guest", kind="audio"),
                SimpleNamespace(sid="TR_guest", kind="audio"),
            )
            await coordinator.wait_until_idle()
            return turns

        turns = asyncio.run(run())
        self.assertEqual(turns[0]["mode"], "listen_only")


async def _append_async(target, value):
    target.append(value)


if __name__ == "__main__":
    unittest.main()
