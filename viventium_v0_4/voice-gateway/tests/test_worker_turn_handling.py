import inspect
import os
import sys
import tempfile
import types
import unittest
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worker import (
    _apply_requested_voice_route,
    _attach_room_diagnostics,
    _build_assemblyai_stt_kwargs,
    _build_voice_capability_catalog,
    _ensure_turn_detector_runner_registered,
    _semantic_turn_detector_status,
    _silero_vad_kwargs_for_env,
    _supports_semantic_turn_detector,
    _turn_detector_model_is_cached,
    _turn_detector_runner_registered,
    _vad_kwargs_cache_key,
    _active_voice_job_markers,
    _clear_active_voice_job_marker,
    _mark_active_voice_job,
    _voice_sync_transcription_enabled,
    ViventiumVoiceAgent,
    _publish_livekit_speaker_segments,
    _publish_livekit_task_event,
    _interrupt_livekit_speech_handles,
    _interrupt_agent_session_speech,
    _apply_authoritative_call_mode_to_speech_planes,
    _suspend_all_call_speech_until_authoritative,
    _apply_task_cancel_suppression,
    AuthoritativeCallModeState,
    CallTaskStreamSpeechAuthority,
    _ingest_raw_stt_speaker_event,
    _linked_participant_speaker_context,
    _participant_identity_connected,
    _build_room_options,
    build_stt_selection,
    load_env,
    load_turn_detection,
    optional_module_available,
)
from livekit.agents import StopResponse
from livekit.agents.stt import SpeechData, SpeechEvent, SpeechEventType
from livekit.agents.llm.chat_context import ChatContext, ChatMessage
from speaker_segments import SpeakerSegmentTracker, SPEAKER_CONTEXT_EXTRA_KEY
from worker import (
    _apply_requested_voice_route,
    _attach_room_diagnostics,
    _build_assemblyai_stt_kwargs,
    _build_voice_capability_catalog,
    _ensure_turn_detector_runner_registered,
    _semantic_turn_detector_status,
    _silero_vad_kwargs_for_env,
    _supports_semantic_turn_detector,
    _turn_detector_model_is_cached,
    _turn_detector_runner_registered,
    _vad_kwargs_cache_key,
    _active_voice_job_markers,
    _wait_for_active_voice_jobs_before_prewarm,
    _clear_active_voice_job_marker,
    _mark_active_voice_job,
    _voice_sync_transcription_enabled,
    ViventiumVoiceAgent,
    _publish_livekit_speaker_segments,
    _publish_livekit_task_event,
    _interrupt_livekit_speech_handles,
    _interrupt_agent_session_speech,
    _register_presentation_lifecycle_handlers,
    _apply_authoritative_call_mode_to_speech_planes,
    _suspend_all_call_speech_until_authoritative,
    _apply_task_cancel_suppression,
    AuthoritativeCallModeState,
    CallTaskStreamSpeechAuthority,
    _ingest_raw_stt_speaker_event,
    _linked_participant_speaker_context,
    build_stt_selection,
    load_env,
    load_turn_detection,
    optional_module_available,
)


def _authoritative_state(*, mode="call", revision=7):
    return {
        "version": 1,
        "callSessionId": "call_1",
        "mode": mode,
        "status": "listening",
        "revision": revision,
        "updatedAt": "2026-08-09T20:37:04.000Z",
    }


def _stream_health(state, *, status=200):
    return {
        "version": 1,
        "callSessionId": "call_1",
        "state": state,
        "status": status,
        "retryable": state in {"connecting", "disconnected"},
    }


class TestWorkerTurnHandling(unittest.TestCase):
    def test_room_options_bind_backend_claimed_owner_across_refresh(self) -> None:
        options = _build_room_options(
            sync_transcription=False,
            participant_identity="backend-claimed-owner",
        )

        self.assertEqual(options.participant_identity, "backend-claimed-owner")
        self.assertFalse(options.close_on_disconnect)

    def test_participant_presence_is_scoped_to_backend_claimed_owner(self) -> None:
        class Participant:
            def __init__(self, identity: str):
                self.identity = identity

        room = SimpleNamespace(
            remote_participants={"observer": Participant("observer")}
        )
        self.assertFalse(
            _participant_identity_connected(room, "backend-claimed-owner")
        )
        room.remote_participants["backend-claimed-owner"] = Participant(
            "backend-claimed-owner"
        )
        self.assertTrue(
            _participant_identity_connected(room, "backend-claimed-owner")
        )

    def test_task_stream_401_or_death_never_authorizes_session_readiness(self) -> None:
        suspended = []
        applied = []

        async def fetch_state():
            raise AssertionError("terminal stream must not fetch or restore call state")

        authority = CallTaskStreamSpeechAuthority(
            call_session_id="call_1",
            fetch_call_state=fetch_state,
            suspend=lambda: suspended.append("suspended"),
            apply_state=applied.append,
        )

        asyncio.run(
            authority.on_stream_health(
                {
                    "version": 1,
                    "callSessionId": "call_1",
                    "state": "terminal",
                    "status": 401,
                    "retryable": False,
                }
            )
        )

        self.assertFalse(authority.mark_session_ready(_authoritative_state()))
        self.assertFalse(authority.authoritative)
        self.assertEqual(applied, [])
        self.assertGreaterEqual(len(suspended), 2)

    def test_task_stream_reconnect_fetches_authoritative_snapshot_before_resuming(self) -> None:
        operations = []
        allow_snapshot = asyncio.Event()

        async def fetch_state():
            operations.append("fetch_started")
            await allow_snapshot.wait()
            operations.append("fetch_complete")
            return _authoritative_state(mode="wing", revision=8)

        authority = CallTaskStreamSpeechAuthority(
            call_session_id="call_1",
            fetch_call_state=fetch_state,
            suspend=lambda: operations.append("suspend"),
            apply_state=lambda state: operations.append(
                ("apply", state["mode"], state["revision"])
            ),
        )

        async def run():
            await authority.on_stream_health(_stream_health("connected"))
            self.assertTrue(authority.mark_session_ready(_authoritative_state()))
            await authority.on_stream_health(_stream_health("disconnected"))
            reconnect = asyncio.create_task(
                authority.on_stream_health(_stream_health("connected"))
            )
            await asyncio.sleep(0)
            self.assertFalse(authority.authoritative)
            self.assertNotIn(("apply", "wing", 8), operations)
            allow_snapshot.set()
            await reconnect

        asyncio.run(run())

        self.assertTrue(authority.authoritative)
        self.assertLess(
            operations.index("fetch_complete"),
            operations.index(("apply", "wing", 8)),
        )
        self.assertEqual(operations.count(("apply", "wing", 8)), 1)

    def test_task_stream_reconnect_remains_silent_until_snapshot_retry_succeeds(self) -> None:
        snapshots = [None, _authoritative_state(mode="call", revision=9)]
        operations = []

        async def fetch_state():
            operations.append("fetch")
            return snapshots.pop(0)

        authority = CallTaskStreamSpeechAuthority(
            call_session_id="call_1",
            fetch_call_state=fetch_state,
            suspend=lambda: operations.append("suspend"),
            apply_state=lambda state: operations.append(("apply", state["revision"])),
        )

        async def run():
            await authority.on_stream_health(_stream_health("connected"))
            self.assertTrue(authority.mark_session_ready(_authoritative_state()))
            await authority.on_stream_health(_stream_health("disconnected"))
            await authority.on_stream_health(_stream_health("connected"))
            self.assertFalse(authority.authoritative)
            self.assertNotIn(("apply", 9), operations)
            self.assertTrue(await authority.reconcile())

        asyncio.run(run())

        self.assertTrue(authority.authoritative)
        self.assertEqual(operations.count(("apply", 9)), 1)

    def test_raw_stt_event_preserves_timing_and_revises_same_mic_speakers(self) -> None:
        tracker = SpeakerSegmentTracker(
            call_session_id="call_1",
            participant_identity="owner",
            track_sid="TR_owner",
            owner_signed=True,
        )
        first = SpeechEvent(
            type=SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[
                SpeechData(
                    language="en",
                    text="First stable owner sentence",
                    start_time=0.0,
                    end_time=1.0,
                    speaker_id="A",
                )
            ],
        )
        changes, is_final = _ingest_raw_stt_speaker_event(
            tracker, first, timeline_offset_s=10.0
        )
        self.assertTrue(is_final)
        self.assertEqual(changes[-1]["startTimeMs"], 10_000)
        self.assertEqual(changes[-1]["endTimeMs"], 11_000)
        self.assertEqual(changes[-1]["speaker"]["actorTrust"], "owner_participant")
        tracker.finalize_turn("First stable owner sentence")

        second = SpeechEvent(
            type=SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[
                SpeechData(
                    language="en",
                    text="Second stable guest sentence",
                    start_time=2.0,
                    end_time=3.0,
                    speaker_id="B",
                )
            ],
        )
        changes, _ = _ingest_raw_stt_speaker_event(
            tracker, second, timeline_offset_s=10.0
        )
        self.assertTrue(tracker.shared_microphone_detected)
        self.assertTrue(
            any(
                item["speaker"]["actorTrust"] == "shared_mic_unverified"
                and item["revision"] > 1
                for item in changes
            )
        )
        self.assertEqual(changes[-1]["speaker"]["actorTrust"], "shared_mic_unverified")

    def test_timingless_raw_or_user_input_event_cannot_verify_owner(self) -> None:
        tracker = SpeakerSegmentTracker(
            call_session_id="call_1",
            participant_identity="owner",
            owner_signed=True,
        )
        timingless = SpeechEvent(
            type=SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[
                SpeechData(
                    language="en",
                    text="Timing is unavailable here",
                    speaker_id="A",
                )
            ],
        )
        [segment], _ = _ingest_raw_stt_speaker_event(
            tracker, timingless, timeline_offset_s=0.0
        )
        self.assertEqual(segment["speaker"]["attribution"], "unknown")

        user_input_only = SimpleNamespace(
            transcript="LiveKit stripped timing",
            is_final=True,
            speaker_id="A",
        )
        changes, is_final = _ingest_raw_stt_speaker_event(
            tracker, user_input_only, timeline_offset_s=0.0
        )
        self.assertEqual(changes, [])
        self.assertFalse(is_final)

    def test_listen_only_owner_turn_persists_segments_once_then_stops_before_llm(self) -> None:
        tracker = SpeakerSegmentTracker(
            call_session_id="call_1",
            participant_identity="owner",
            owner_signed=True,
        )
        tracker.ingest(
            transcript="Synthetic listen only statement",
            is_final=True,
            provider_speaker_id="A",
            created_at=1.0,
            start_time=0.0,
            end_time=1.0,
        )
        mode_state = AuthoritativeCallModeState()
        mode_state.apply("listen_only")
        persisted = []

        async def persist(context, mode):
            persisted.append((context, mode))

        agent = ViventiumVoiceAgent(
            instructions="test",
            speaker_tracker=tracker,
            authoritative_mode_state=mode_state,
            persist_suppressed_turn=persist,
        )
        message = ChatMessage(role="user", content=["Synthetic listen only statement"])

        with self.assertRaises(StopResponse):
            asyncio.run(agent.on_user_turn_completed(ChatContext.empty(), message))

        self.assertEqual(len(persisted), 1)
        context, mode = persisted[0]
        self.assertEqual(mode, "listen_only")
        self.assertEqual(len(context["speakerSegments"]), 1)
        self.assertEqual(
            context["speakerSegments"][0]["text"], "Synthetic listen only statement"
        )

    def test_uncertain_mode_and_transition_race_fail_closed_then_call_restores(self) -> None:
        mode_state = AuthoritativeCallModeState()
        persisted = []

        async def persist(context, mode):
            persisted.append((context, mode))

        agent = ViventiumVoiceAgent(
            instructions="test",
            authoritative_mode_state=mode_state,
            persist_suppressed_turn=persist,
        )

        with self.assertRaises(StopResponse):
            asyncio.run(
                agent.on_user_turn_completed(
                    ChatContext.empty(), ChatMessage(role="user", content=["First"])
                )
            )
        mode_state.apply("call")
        asyncio.run(
            agent.on_user_turn_completed(
                ChatContext.empty(), ChatMessage(role="user", content=["Second"])
            )
        )
        mode_state.apply("listen_only")
        with self.assertRaises(StopResponse):
            asyncio.run(
                agent.on_user_turn_completed(
                    ChatContext.empty(), ChatMessage(role="user", content=["Third"])
                )
            )
        mode_state.apply("call")
        asyncio.run(
            agent.on_user_turn_completed(
                ChatContext.empty(), ChatMessage(role="user", content=["Fourth"])
            )
        )

        self.assertEqual([mode for _context, mode in persisted], ["uncertain", "listen_only"])

    def test_cancel_acceptance_synchronously_stops_all_task_speech_but_not_backend(self) -> None:
        calls = []
        progress = SimpleNamespace(suppress_task=lambda task_id: calls.append(("progress", task_id)))
        followup = SimpleNamespace(cancel_pending=lambda: calls.append(("followup", None)))
        session = SimpleNamespace(interrupt=lambda *, force=False: calls.append(("main", force)))
        backend_task_state = {"state": "cancelling"}

        _apply_task_cancel_suppression(
            "task_1",
            progress_controller=progress,
            followup_scheduler=followup,
            session=session,
        )

        self.assertEqual(
            calls,
            [("progress", "task_1"), ("followup", None), ("main", True)],
        )
        self.assertEqual(backend_task_state, {"state": "cancelling"})

    def test_mode_transition_halts_main_progress_and_followup_without_cancelling_task(self) -> None:
        class Progress:
            def __init__(self):
                self.modes = []
                self.suspensions = 0

            def set_mode(self, mode):
                self.modes.append(mode)

            def suspend_until_authoritative(self):
                self.suspensions += 1

        class Plane:
            def __init__(self):
                self.modes = []
                self.suspensions = 0

            def set_mode(self, mode):
                self.modes.append(mode)

            def suspend_until_authoritative(self):
                self.suspensions += 1

        class Session:
            def __init__(self):
                self.interrupts = []

            def interrupt(self, *, force=False):
                self.interrupts.append(force)

        progress = Progress()
        ambient = Plane()
        followup = Plane()
        session = Session()
        backend_task_state = {"state": "running"}

        _apply_authoritative_call_mode_to_speech_planes(
            "listen_only",
            progress_controller=progress,
            ambient_ingress=ambient,
            followup_scheduler=followup,
            session=session,
        )
        _suspend_all_call_speech_until_authoritative(
            progress_controller=progress,
            followup_scheduler=followup,
            session=session,
        )

        self.assertEqual(progress.modes, ["listen_only"])
        self.assertEqual(ambient.modes, ["listen_only"])
        self.assertEqual(followup.modes, ["listen_only"])
        self.assertEqual(progress.suspensions, 1)
        self.assertEqual(followup.suspensions, 1)
        self.assertEqual(session.interrupts, [True, True])
        self.assertEqual(backend_task_state, {"state": "running"})

    def test_listen_only_transition_interrupts_only_active_progress_handles(self) -> None:
        class FakeHandle:
            def __init__(self, done: bool) -> None:
                self._done = done
                self.forces = []

            def done(self):
                return self._done

            def interrupt(self, *, force=False):
                self.forces.append(force)

        active = FakeHandle(False)
        completed = FakeHandle(True)
        handles = {active, completed}

        _interrupt_livekit_speech_handles(handles)

        self.assertEqual(active.forces, [True])
        self.assertEqual(completed.forces, [])
        self.assertEqual(handles, set())

    def test_listen_only_transition_interrupts_main_speech_without_reconnect(self) -> None:
        class FakeSession:
            def __init__(self) -> None:
                self.interrupt_forces = []
                self.reconnects = 0

            def interrupt(self, *, force=False):
                self.interrupt_forces.append(force)

        session = FakeSession()

        _interrupt_agent_session_speech(session)

        self.assertEqual(session.interrupt_forces, [True])
        self.assertEqual(session.reconnects, 0)

    def test_owner_binding_uses_job_publisher_not_first_remote_participant(self) -> None:
        guest = SimpleNamespace(
            identity="aaa-guest",
            name="Guest",
            track_publications={"guest": SimpleNamespace(sid="TR_guest", source="SOURCE_MICROPHONE")},
        )
        owner = SimpleNamespace(
            identity="zzz-owner",
            name="Owner",
            track_publications={"owner": SimpleNamespace(sid="TR_owner", source="SOURCE_MICROPHONE")},
        )
        room = SimpleNamespace(remote_participants={"guest": guest, "owner": owner})

        context = _linked_participant_speaker_context(room, "zzz-owner")

        self.assertEqual(context["participant_identity"], "zzz-owner")
        self.assertEqual(context["track_sid"], "TR_owner")
        self.assertTrue(context["owner_signed"])

    def test_missing_job_publisher_abstains_instead_of_trusting_remote(self) -> None:
        room = SimpleNamespace(
            remote_participants={
                "guest": SimpleNamespace(
                    identity="guest",
                    name="Guest",
                    track_publications={},
                )
            }
        )

        self.assertEqual(_linked_participant_speaker_context(room, ""), {})
        self.assertEqual(_linked_participant_speaker_context(room, "owner-not-connected"), {})

    def test_voice_agent_consumes_speaker_side_channel_once_before_llm(self) -> None:
        tracker = SpeakerSegmentTracker(
            call_session_id="call_1",
            participant_identity="owner-participant",
            participant_name="Owner",
            track_sid="TR_owner",
            owner_signed=True,
        )
        tracker.ingest(
            transcript="Synthetic request",
            is_final=True,
            provider_speaker_id="A",
            created_at=100.0,
        )
        agent = ViventiumVoiceAgent(instructions="test", speaker_tracker=tracker)
        message = ChatMessage(role="user", content=["Synthetic request"])

        asyncio.run(agent.on_user_turn_completed(ChatContext.empty(), message))

        context = message.extra[SPEAKER_CONTEXT_EXTRA_KEY]
        self.assertEqual(
            context["speakerSegments"][0]["speaker"]["providerSpeakerId"],
            "A",
        )
        second_message = ChatMessage(role="user", content=["Next request"])
        asyncio.run(agent.on_user_turn_completed(ChatContext.empty(), second_message))
        self.assertEqual(
            second_message.extra[SPEAKER_CONTEXT_EXTRA_KEY]["speakerSegments"][0]["speaker"]["label"],
            "Unknown",
        )

    def test_publishes_versioned_speaker_segment_to_livekit_topic(self) -> None:
        class FakeParticipant:
            def __init__(self) -> None:
                self.calls = []

            async def publish_data(
                self, payload, *, reliable, topic, destination_identities
            ):
                self.calls.append((payload, reliable, topic, destination_identities))

        participant = FakeParticipant()
        segment = {
            "version": 1,
            "segmentId": "segment_000001",
            "callSessionId": "call_1",
            "turnId": "turn_000001",
            "sequence": 1,
            "revision": 1,
            "text": "Synthetic request",
            "isFinal": True,
            "speaker": {
                "key": "provider:A",
                "label": "Speaker 1",
                "source": "provider_diarization",
                "attribution": "unverified",
                "actorTrust": "shared_mic_unverified",
                "providerSpeakerId": "A",
            },
        }

        asyncio.run(
            _publish_livekit_speaker_segments(
                participant,
                [segment],
                owner_participant_identity="owner",
            )
        )

        self.assertEqual(len(participant.calls), 1)
        payload, reliable, topic, destinations = participant.calls[0]
        self.assertTrue(reliable)
        self.assertEqual(topic, "viventium.speaker.v1")
        self.assertEqual(destinations, ["owner"])
        self.assertEqual(json.loads(payload), segment)

    def test_publishes_authoritative_task_event_to_livekit_topic(self) -> None:
        class FakeParticipant:
            def __init__(self) -> None:
                self.calls = []

            async def publish_data(
                self, payload, *, reliable, topic, destination_identities
            ):
                self.calls.append((payload, reliable, topic, destination_identities))

        participant = FakeParticipant()
        task_event = {
            "version": 1,
            "eventId": "event_1",
            "sequence": 1,
            "taskId": "task_1",
            "state": "running",
            "phase": "searching",
        }

        asyncio.run(
            _publish_livekit_task_event(
                participant,
                task_event,
                owner_participant_identity="owner",
            )
        )

        payload, reliable, topic, destinations = participant.calls[0]
        self.assertTrue(reliable)
        self.assertEqual(topic, "viventium.task.v1")
        self.assertEqual(destinations, ["owner"])
        self.assertEqual(json.loads(payload), task_event)

    def test_publishes_recovering_retryable_error_to_owner_task_topic_unmodified(self) -> None:
        class FakeParticipant:
            def __init__(self) -> None:
                self.calls = []

            async def publish_data(
                self, payload, *, reliable, topic, destination_identities
            ):
                self.calls.append((payload, reliable, topic, destination_identities))

        participant = FakeParticipant()
        task_event = {
            "version": 1,
            "eventId": "event_recovering",
            "sequence": 7,
            "emittedAt": "2026-08-09T20:37:07.000Z",
            "callSessionId": "call_1",
            "taskId": "task_1",
            "type": "error",
            "state": "recovering",
            "phase": "cancel_barrier_recovering",
            "cancellable": True,
            "retryable": False,
            "owner": {"kind": "generation_job", "id": "stream_1"},
            "error": {
                "code": "cancel_barrier_unavailable",
                "message": "Cancellation could not be made durable. Output remains locally suppressed.",
                "retryable": True,
            },
        }

        asyncio.run(
            _publish_livekit_task_event(
                participant,
                task_event,
                owner_participant_identity="owner",
            )
        )

        payload, reliable, topic, destinations = participant.calls[0]
        self.assertTrue(reliable)
        self.assertEqual(topic, "viventium.task.v1")
        self.assertEqual(destinations, ["owner"])
        self.assertEqual(json.loads(payload), task_event)

    def test_livekit_data_publish_failure_never_breaks_call(self) -> None:
        class FailingParticipant:
            async def publish_data(self, *_args, **_kwargs):
                raise RuntimeError("synthetic transport failure")

        task_event = {
            "version": 1,
            "eventId": "event_1",
            "sequence": 1,
            "taskId": "task_1",
            "state": "running",
        }
        segment = {
            "version": 1,
            "callSessionId": "call_1",
            "turnId": "turn_1",
            "segmentId": "segment_1",
            "sequence": 1,
            "revision": 1,
            "text": "Synthetic",
            "isFinal": True,
            "speaker": {"label": "Unknown", "source": "unknown", "attribution": "unknown"},
        }

        asyncio.run(
            _publish_livekit_task_event(
                FailingParticipant(), task_event, owner_participant_identity="owner"
            )
        )
        asyncio.run(
            _publish_livekit_speaker_segments(
                FailingParticipant(), [segment], owner_participant_identity="owner"
            )
        )

    def test_oversize_livekit_data_packet_is_not_published(self) -> None:
        class FakeParticipant:
            def __init__(self) -> None:
                self.calls = []

            async def publish_data(self, *args, **kwargs):
                self.calls.append((args, kwargs))

        participant = FakeParticipant()
        task_event = {
            "version": 1,
            "eventId": "event_1",
            "sequence": 1,
            "taskId": "task_1",
            "state": "running",
            "detail": "x" * 20_000,
        }

        asyncio.run(
            _publish_livekit_task_event(
                participant, task_event, owner_participant_identity="owner"
            )
        )

        self.assertEqual(participant.calls, [])

    def test_private_livekit_packets_fail_closed_without_owner_destination(self) -> None:
        class FakeParticipant:
            def __init__(self) -> None:
                self.calls = []

            async def publish_data(self, *args, **kwargs):
                self.calls.append((args, kwargs))

        participant = FakeParticipant()
        task_event = {
            "version": 1,
            "eventId": "event_1",
            "sequence": 1,
            "taskId": "task_1",
            "state": "running",
        }

        asyncio.run(
            _publish_livekit_task_event(
                participant, task_event, owner_participant_identity=""
            )
        )

        self.assertEqual(participant.calls, [])
    def test_active_voice_job_markers_are_process_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(
                os.environ,
                {
                    "TMPDIR": tmp_dir,
                    "VIVENTIUM_VOICE_WORKER_RUN_ID": "test-run",
                },
                clear=False,
            ):
                marker = _mark_active_voice_job("job-1")
                self.assertIn(marker, _active_voice_job_markers())
                _clear_active_voice_job_marker(marker)
                self.assertEqual(_active_voice_job_markers(), [])

    def test_room_participant_disconnect_does_not_clear_active_marker(self) -> None:
        class FakeRoom:
            name = "room"

            def __init__(self) -> None:
                self.handlers = {}
                self.remote_participants = {"owner": object()}

            def on(self, event_name):
                def _register(handler):
                    self.handlers[event_name] = handler
                    return handler

                return _register

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(
                os.environ,
                {
                    "TMPDIR": tmp_dir,
                    "VIVENTIUM_VOICE_WORKER_RUN_ID": "test-run",
                },
                clear=False,
            ):
                marker = _mark_active_voice_job("job-1")
                room = FakeRoom()
                ctx = SimpleNamespace(room=room)
                participant = SimpleNamespace(identity="observer")

                _attach_room_diagnostics(
                    ctx,
                    call_session_id="test-call",
                    active_job_marker=marker,
                )
                room.handlers["participant_disconnected"](participant)

                self.assertIn(marker, _active_voice_job_markers())
                _clear_active_voice_job_marker(marker)

    def test_room_empty_participant_disconnect_keeps_marker_until_job_shutdown(self) -> None:
        class FakeRoom:
            name = "room"

            def __init__(self) -> None:
                self.handlers = {}
                self.remote_participants = {}

            def on(self, event_name):
                def _register(handler):
                    self.handlers[event_name] = handler
                    return handler

                return _register

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(
                os.environ,
                {
                    "TMPDIR": tmp_dir,
                    "VIVENTIUM_VOICE_WORKER_RUN_ID": "test-run",
                },
                clear=False,
            ):
                marker = _mark_active_voice_job("job-1")
                room = FakeRoom()
                ctx = SimpleNamespace(room=room)
                participant = SimpleNamespace(identity="owner")

                _attach_room_diagnostics(
                    ctx,
                    call_session_id="test-call",
                    active_job_marker=marker,
                )
                room.handlers["participant_disconnected"](participant)

                self.assertIn(marker, _active_voice_job_markers())
                _clear_active_voice_job_marker(marker)

    def test_optional_module_available_handles_missing_parent_package(self) -> None:
        with patch(
            "worker.importlib.util.find_spec",
            side_effect=ModuleNotFoundError("No module named 'livekit.plugins.turn_detector'"),
        ):
            self.assertFalse(optional_module_available("livekit.plugins.turn_detector.multilingual"))

    def test_load_env_defaults_to_stt_for_assemblyai_when_turn_detector_missing(self) -> None:
        with (
            patch.dict(os.environ, {"VIVENTIUM_STT_PROVIDER": "assemblyai"}, clear=True),
            patch("worker.HAS_TURN_DETECTOR", False),
        ):
            env = load_env()

        self.assertEqual(env.voice_turn_detection, "stt")
        self.assertEqual(env.voice_min_endpointing_delay_s, 0.0)
        self.assertEqual(env.voice_max_endpointing_delay_s, 1.8)
        self.assertEqual(env.voice_min_interruption_words, 1)
        self.assertEqual(env.voice_false_interruption_timeout_s, 2.0)
        self.assertTrue(env.voice_resume_false_interruption)
        self.assertEqual(env.voice_min_consecutive_speech_delay_s, 0.2)
        self.assertEqual(env.voice_aec_warmup_duration_s, 3.0)
        self.assertIsNone(env.assemblyai_min_end_of_turn_silence_when_confident_ms)
        self.assertIsNone(env.assemblyai_max_turn_silence_ms)

    def test_load_env_keeps_stt_default_for_assemblyai_when_turn_detector_is_available(self) -> None:
        with (
            patch.dict(os.environ, {"VIVENTIUM_STT_PROVIDER": "assemblyai"}, clear=True),
            patch("worker.HAS_TURN_DETECTOR", True),
        ):
            env = load_env()

        self.assertEqual(env.voice_turn_detection, "stt")
        self.assertEqual(env.voice_min_endpointing_delay_s, 0.0)
        self.assertEqual(env.voice_max_endpointing_delay_s, 1.8)

    def test_load_env_respects_explicit_turn_detector_override(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "VIVENTIUM_STT_PROVIDER": "assemblyai",
                    "VIVENTIUM_TURN_DETECTION": "turn_detector",
                },
                clear=True,
            ),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=True),
            patch("worker._ensure_turn_detector_runner_registered", return_value=True),
        ):
            env = load_env()

        self.assertEqual(env.voice_turn_detection, "turn_detector")
        self.assertEqual(env.voice_min_endpointing_delay_s, 0.35)
        self.assertEqual(env.voice_max_endpointing_delay_s, 1.8)
        self.assertEqual(env.voice_min_interruption_words, 1)

    def test_explicit_turn_detector_falls_back_to_aligned_profile_when_uncached(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "VIVENTIUM_STT_PROVIDER": "assemblyai",
                    "VIVENTIUM_TURN_DETECTION": "turn_detector",
                },
                clear=True,
            ),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=False),
            patch("worker._ensure_turn_detector_runner_registered", return_value=False),
        ):
            env = load_env()

        self.assertEqual(env.voice_turn_detection, "stt")
        self.assertEqual(env.voice_min_endpointing_delay_s, 0.0)
        self.assertEqual(env.voice_max_endpointing_delay_s, 1.8)

    def test_load_env_respects_turn_handling_overrides(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIVENTIUM_STT_PROVIDER": "assemblyai",
                "VIVENTIUM_TURN_DETECTION": "stt",
                "VIVENTIUM_VOICE_MIN_INTERRUPTION_WORDS": "3",
                "VIVENTIUM_VOICE_FALSE_INTERRUPTION_TIMEOUT_S": "off",
                "VIVENTIUM_VOICE_RESUME_FALSE_INTERRUPTION": "false",
                "VIVENTIUM_VOICE_MIN_CONSECUTIVE_SPEECH_DELAY_S": "0.45",
                "VIVENTIUM_VOICE_AEC_WARMUP_DURATION_S": "0.75",
                "VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD": "0.33",
                "VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS": "220",
                "VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS": "1500",
                "VIVENTIUM_ASSEMBLYAI_FORMAT_TURNS": "true",
            },
            clear=True,
        ):
            env = load_env()

        self.assertEqual(env.voice_turn_detection, "stt")
        self.assertEqual(env.voice_min_interruption_words, 3)
        self.assertIsNone(env.voice_false_interruption_timeout_s)
        self.assertFalse(env.voice_resume_false_interruption)
        self.assertEqual(env.voice_min_consecutive_speech_delay_s, 0.45)
        self.assertEqual(env.voice_aec_warmup_duration_s, 0.75)
        self.assertEqual(env.assemblyai_end_of_turn_confidence_threshold, 0.33)
        self.assertEqual(env.assemblyai_min_end_of_turn_silence_when_confident_ms, 220)
        self.assertEqual(env.assemblyai_max_turn_silence_ms, 1500)
        self.assertTrue(env.assemblyai_format_turns)

    def test_requested_assemblyai_override_recomputes_turn_profile_from_local_default(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "VIVENTIUM_STT_PROVIDER": "whisper_local",
                    "ASSEMBLYAI_API_KEY": "assemblyai-test",
                    "OPENAI_API_KEY": "openai-test",
                },
                clear=True,
            ),
            patch("worker.HAS_ASSEMBLYAI", True),
        ):
            env = load_env()
            capabilities = _build_voice_capability_catalog(env)
            updated = _apply_requested_voice_route(
                env,
                {
                    "stt": {"provider": "assemblyai", "variant": "u3-rt-pro"},
                    "tts": {"provider": "openai", "variant": "gpt-4o-mini-tts"},
                },
                capabilities,
            )

        self.assertEqual(updated.stt_provider, "assemblyai")
        self.assertEqual(updated.voice_turn_detection, "stt")
        self.assertEqual(updated.voice_min_endpointing_delay_s, 0.0)
        self.assertEqual(updated.voice_max_endpointing_delay_s, 1.8)
        self.assertEqual(updated.voice_min_interruption_words, 1)
        self.assertEqual(updated.voice_min_consecutive_speech_delay_s, 0.2)
        self.assertEqual(_silero_vad_kwargs_for_env(updated)["min_silence_duration"], 0.5)

    def test_requested_local_override_recomputes_turn_profile_from_assemblyai_default(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "VIVENTIUM_STT_PROVIDER": "assemblyai",
                    "ASSEMBLYAI_API_KEY": "assemblyai-test",
                    "OPENAI_API_KEY": "openai-test",
                },
                clear=True,
            ),
            patch("worker.HAS_ASSEMBLYAI", True),
            patch("worker._turn_detector_model_is_cached", return_value=False),
        ):
            env = load_env()
            capabilities = _build_voice_capability_catalog(env)
            updated = _apply_requested_voice_route(
                env,
                {
                    "stt": {"provider": "pywhispercpp", "variant": "tiny.en"},
                    "tts": {"provider": "openai", "variant": "gpt-4o-mini-tts"},
                },
                capabilities,
            )

        self.assertEqual(updated.stt_provider, "pywhispercpp")
        self.assertEqual(updated.stt_model, "tiny.en")
        self.assertEqual(updated.voice_turn_detection, "vad")
        self.assertEqual(updated.voice_min_endpointing_delay_s, 0.5)
        self.assertEqual(updated.voice_max_endpointing_delay_s, 3.0)
        self.assertEqual(updated.voice_min_interruption_words, 0)
        self.assertEqual(updated.voice_min_consecutive_speech_delay_s, 0.0)

    def test_local_whisper_uses_semantic_turn_detector_when_cached(self) -> None:
        with (
            patch.dict(os.environ, {"VIVENTIUM_STT_PROVIDER": "whisper_local"}, clear=True),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=True),
            patch("worker._ensure_turn_detector_runner_registered", return_value=True),
        ):
            env = load_env()

        self.assertTrue(_supports_semantic_turn_detector("whisper_local"))
        self.assertTrue(_supports_semantic_turn_detector("pywhispercpp"))
        self.assertEqual(env.voice_turn_detection, "turn_detector")
        self.assertEqual(env.voice_min_endpointing_delay_s, 0.35)
        self.assertEqual(env.voice_max_endpointing_delay_s, 1.8)
        self.assertEqual(env.voice_min_interruption_words, 0)
        self.assertEqual(env.voice_min_consecutive_speech_delay_s, 0.2)
        self.assertEqual(env.voice_aec_warmup_duration_s, 1.0)

    def test_local_whisper_semantic_turn_detector_respects_explicit_min_words_override(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "VIVENTIUM_STT_PROVIDER": "whisper_local",
                    "VIVENTIUM_VOICE_MIN_INTERRUPTION_WORDS": "2",
                },
                clear=True,
            ),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=True),
            patch("worker._ensure_turn_detector_runner_registered", return_value=True),
        ):
            env = load_env()

        self.assertEqual(env.voice_turn_detection, "turn_detector")
        self.assertEqual(env.voice_min_interruption_words, 2)

    def test_local_whisper_falls_back_to_vad_when_runner_is_not_registered(self) -> None:
        with (
            patch.dict(os.environ, {"VIVENTIUM_STT_PROVIDER": "whisper_local"}, clear=True),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=True),
            patch("worker._ensure_turn_detector_runner_registered", return_value=False),
        ):
            env = load_env()

        self.assertEqual(env.voice_turn_detection, "vad")
        self.assertEqual(env.voice_min_endpointing_delay_s, 0.5)
        self.assertEqual(env.voice_max_endpointing_delay_s, 3.0)
        self.assertEqual(env.voice_min_interruption_words, 0)
        self.assertEqual(env.voice_aec_warmup_duration_s, 1.0)

    def test_local_whisper_uncached_fallback_uses_less_eager_vad(self) -> None:
        with (
            patch.dict(os.environ, {"VIVENTIUM_STT_PROVIDER": "whisper_local"}, clear=True),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=False),
            patch("worker._ensure_turn_detector_runner_registered", return_value=False),
        ):
            env = load_env()

        self.assertEqual(env.voice_turn_detection, "vad")
        self.assertEqual(env.voice_min_endpointing_delay_s, 0.5)
        self.assertEqual(env.voice_max_endpointing_delay_s, 3.0)
        self.assertEqual(_silero_vad_kwargs_for_env(env)["min_speech_duration"], 0.35)
        self.assertEqual(_silero_vad_kwargs_for_env(env)["min_silence_duration"], 0.5)

    def test_local_whisper_respects_explicit_vad_min_speech_override(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "VIVENTIUM_STT_PROVIDER": "whisper_local",
                    "VIVENTIUM_STT_VAD_MIN_SPEECH": "0.22",
                },
                clear=True,
            ),
            patch("worker._turn_detector_model_is_cached", return_value=False),
        ):
            env = load_env()
            vad_kwargs = _silero_vad_kwargs_for_env(env)

        self.assertEqual(vad_kwargs["min_speech_duration"], 0.22)

    def test_local_whisper_respects_explicit_vad_min_silence_override(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "VIVENTIUM_STT_PROVIDER": "whisper_local",
                    "VIVENTIUM_STT_VAD_MIN_SILENCE": "0.72",
                },
                clear=True,
            ),
            patch("worker._turn_detector_model_is_cached", return_value=False),
        ):
            env = load_env()
            vad_kwargs = _silero_vad_kwargs_for_env(env)

        self.assertEqual(vad_kwargs["min_silence_duration"], 0.72)

    def test_vad_kwargs_cache_key_changes_when_requested_route_changes_vad_timing(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "VIVENTIUM_STT_PROVIDER": "whisper_local",
                    "ASSEMBLYAI_API_KEY": "assemblyai-test",
                    "OPENAI_API_KEY": "openai-test",
                },
                clear=True,
            ),
            patch("worker.HAS_ASSEMBLYAI", True),
            patch("worker._turn_detector_model_is_cached", return_value=False),
        ):
            env = load_env()
            local_key = _vad_kwargs_cache_key(_silero_vad_kwargs_for_env(env))
            capabilities = _build_voice_capability_catalog(env)
            updated = _apply_requested_voice_route(
                env,
                {
                    "stt": {"provider": "assemblyai", "variant": "u3-rt-pro"},
                    "tts": {"provider": "openai", "variant": "gpt-4o-mini-tts"},
                },
                capabilities,
            )
            assemblyai_key = _vad_kwargs_cache_key(_silero_vad_kwargs_for_env(updated))

        self.assertEqual(env.voice_turn_detection, "vad")
        self.assertEqual(_silero_vad_kwargs_for_env(env)["min_speech_duration"], 0.35)
        self.assertEqual(_silero_vad_kwargs_for_env(env)["min_silence_duration"], 0.5)
        self.assertEqual(updated.voice_turn_detection, "stt")
        self.assertEqual(_silero_vad_kwargs_for_env(updated)["min_speech_duration"], 0.1)
        self.assertEqual(_silero_vad_kwargs_for_env(updated)["min_silence_duration"], 0.5)
        self.assertNotEqual(local_key, assemblyai_key)

    def test_load_env_raises_memory_warning_threshold_for_local_voice_route(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIVENTIUM_STT_PROVIDER": "whisper_local",
                "VIVENTIUM_TTS_PROVIDER": "local_chatterbox_turbo_mlx_8bit",
            },
            clear=True,
        ):
            env = load_env()

        self.assertEqual(env.voice_job_memory_warn_mb, 2200.0)
        self.assertEqual(env.voice_job_memory_limit_mb, 0.0)

    def test_load_env_keeps_chatterbox_only_memory_warning_threshold(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIVENTIUM_STT_PROVIDER": "assemblyai",
                "VIVENTIUM_TTS_PROVIDER": "local_chatterbox_turbo_mlx_8bit",
            },
            clear=True,
        ):
            env = load_env()

        self.assertEqual(env.voice_job_memory_warn_mb, 1400.0)

    def test_load_env_keeps_hosted_voice_memory_warning_threshold(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIVENTIUM_STT_PROVIDER": "assemblyai",
                "VIVENTIUM_TTS_PROVIDER": "openai",
            },
            clear=True,
        ):
            env = load_env()

        self.assertEqual(env.voice_job_memory_warn_mb, 500.0)

    def test_all_local_route_prewarms_tts_before_worker_registration(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIVENTIUM_STT_PROVIDER": "whisper_local",
                "VIVENTIUM_TTS_PROVIDER": "local_chatterbox_turbo_mlx_8bit",
            },
            clear=True,
        ):
            env = load_env()

        self.assertTrue(env.voice_prewarm_local_tts)

    def test_local_whisper_respects_explicit_tts_prewarm_override(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIVENTIUM_STT_PROVIDER": "whisper_local",
                "VIVENTIUM_TTS_PROVIDER": "local_chatterbox_turbo_mlx_8bit",
                "VIVENTIUM_VOICE_PREWARM_LOCAL_TTS": "true",
            },
            clear=True,
        ):
            env = load_env()

        self.assertTrue(env.voice_prewarm_local_tts)

    def test_load_env_respects_memory_warning_overrides(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIVENTIUM_STT_PROVIDER": "whisper_local",
                "VIVENTIUM_TTS_PROVIDER": "local_chatterbox_turbo_mlx_8bit",
                "VIVENTIUM_VOICE_JOB_MEMORY_WARN_MB": "1600",
                "VIVENTIUM_VOICE_JOB_MEMORY_LIMIT_MB": "2200",
            },
            clear=True,
        ):
            env = load_env()

        self.assertEqual(env.voice_job_memory_warn_mb, 1600.0)
        self.assertEqual(env.voice_job_memory_limit_mb, 2200.0)

    def test_build_assemblyai_stt_kwargs_includes_model_and_configured_values(self) -> None:
        # The engine model is always passed (the selectable Listening picker depends on it); the
        # optional endpointing knobs are still only included when configured.
        env = SimpleNamespace(
            assemblyai_stt_model="universal-streaming-multilingual",
            assemblyai_end_of_turn_confidence_threshold=0.27,
            assemblyai_min_end_of_turn_silence_when_confident_ms=210,
            assemblyai_max_turn_silence_ms=1300,
            assemblyai_format_turns=True,
        )

        self.assertEqual(
            _build_assemblyai_stt_kwargs(env),
            {
                "model": "universal-streaming-multilingual",
                "speaker_labels": True,
                "end_of_turn_confidence_threshold": 0.27,
                "min_turn_silence": 210,
                "max_turn_silence": 1300,
                "format_turns": True,
            },
        )

    def test_build_stt_selection_passes_assemblyai_turn_kwargs(self) -> None:
        env = SimpleNamespace(
            stt_provider="assemblyai",
            assemblyai_stt_model="u3-rt-pro",
            assemblyai_end_of_turn_confidence_threshold=0.29,
            assemblyai_min_end_of_turn_silence_when_confident_ms=190,
            assemblyai_max_turn_silence_ms=1250,
            assemblyai_format_turns=False,
        )

        with (
            patch("worker.HAS_ASSEMBLYAI", True),
            patch.dict(os.environ, {"ASSEMBLYAI_API_KEY": "assemblyai-test"}, clear=False),
            patch("worker.assemblyai_stt.STT", return_value="assemblyai-stt") as stt_cls,
        ):
            stt_impl, provider = build_stt_selection(env, vad=object())

        self.assertEqual(stt_impl, "assemblyai-stt")
        self.assertEqual(provider, "assemblyai")
        stt_cls.assert_called_once_with(
            model="u3-rt-pro",
            speaker_labels=True,
            end_of_turn_confidence_threshold=0.29,
            min_turn_silence=190,
            max_turn_silence=1250,
        )

    def test_local_whisper_selection_fails_honestly_without_openai_fallback(self) -> None:
        fake_pywhispercpp_provider = types.ModuleType("pywhispercpp_provider")

        def _fail_get_stt(*_args, **_kwargs):
            raise RuntimeError("selected model is corrupt")

        fake_pywhispercpp_provider.get_stt = _fail_get_stt
        env = SimpleNamespace(
            stt_provider="whisper_local",
            stt_model="large-v3-turbo",
            stt_language="en",
        )

        with (
            patch.dict(sys.modules, {"pywhispercpp_provider": fake_pywhispercpp_provider}),
            patch("worker.openai.STT", side_effect=AssertionError("OpenAI fallback must not run")),
        ):
            with self.assertRaisesRegex(RuntimeError, "will not silently switch"):
                build_stt_selection(env, vad=object())

    def test_load_turn_detection_returns_turn_detector_when_available(self) -> None:
        env = SimpleNamespace(voice_turn_detection="turn_detector", stt_provider="assemblyai")

        with (
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=True),
            patch("worker._ensure_turn_detector_runner_registered", return_value=True),
            patch("worker._load_turn_detector_model_class", return_value=lambda: "semantic-detector"),
        ):
            turn_detection, reason = load_turn_detection(env, has_vad=True)

        self.assertEqual(turn_detection, "semantic-detector")
        self.assertEqual(reason, "semantic_turn_detector")

    def test_load_turn_detection_falls_back_to_stt_when_turn_detector_weights_missing(self) -> None:
        env = SimpleNamespace(voice_turn_detection="turn_detector", stt_provider="assemblyai")

        with (
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=False),
            patch("worker._ensure_turn_detector_runner_registered", return_value=False),
            patch("worker._load_turn_detector_model_class") as detector_cls,
        ):
            turn_detection, reason = load_turn_detection(env, has_vad=True)

        detector_cls.assert_not_called()
        self.assertEqual(turn_detection, "stt")
        self.assertEqual(reason, "stt_end_of_turn")

    def test_load_turn_detection_falls_back_to_vad_for_local_stt_when_runner_missing(self) -> None:
        env = SimpleNamespace(voice_turn_detection="turn_detector", stt_provider="pywhispercpp")

        with (
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=True),
            patch("worker._ensure_turn_detector_runner_registered", return_value=False),
            patch("worker._load_turn_detector_model_class") as detector_cls,
        ):
            turn_detection, reason = load_turn_detection(env, has_vad=True)

        detector_cls.assert_not_called()
        self.assertEqual(turn_detection, "vad")
        self.assertEqual(reason, "vad_silence")

    def test_semantic_turn_detector_status_requires_registered_local_runner(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=True),
            patch("worker._ensure_turn_detector_runner_registered", return_value=False),
        ):
            self.assertEqual(
                _semantic_turn_detector_status("pywhispercpp"),
                (False, "local_inference_runner_unregistered"),
            )

    def test_semantic_turn_detector_status_allows_remote_inference(self) -> None:
        with (
            patch.dict(os.environ, {"LIVEKIT_REMOTE_EOT_URL": "https://example.invalid/eot"}, clear=True),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=False),
        ):
            self.assertEqual(
                _semantic_turn_detector_status("pywhispercpp"),
                (True, "remote_inference"),
            )

    def test_turn_detector_runner_registration_does_not_import_when_assets_missing(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=False),
            patch("builtins.__import__") as import_fn,
        ):
            self.assertFalse(_ensure_turn_detector_runner_registered())

        import_fn.assert_not_called()

    def test_turn_detector_runner_registration_imports_multilingual_plugin(self) -> None:
        registered_runners = {}
        FakeInferenceRunner = type(
            "FakeInferenceRunner",
            (),
            {"registered_runners": registered_runners},
        )

        def fake_import(name: str, *args, **kwargs):
            if name == "livekit.agents.inference_runner":
                return SimpleNamespace(_InferenceRunner=FakeInferenceRunner)
            if name == "livekit.plugins.turn_detector.multilingual":
                registered_runners["lk_end_of_utterance_multilingual"] = object()
                return SimpleNamespace()
            raise ImportError(name)

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("worker.HAS_TURN_DETECTOR", True),
            patch("worker._turn_detector_model_is_cached", return_value=True),
            patch("builtins.__import__", side_effect=fake_import),
        ):
            self.assertFalse(_turn_detector_runner_registered())
            self.assertTrue(_ensure_turn_detector_runner_registered())
            self.assertTrue(_turn_detector_runner_registered())

    def test_load_turn_detection_falls_back_to_stt_when_turn_detector_missing(self) -> None:
        env = SimpleNamespace(voice_turn_detection="turn_detector", stt_provider="assemblyai")

        with patch("worker.HAS_TURN_DETECTOR", False):
            turn_detection, reason = load_turn_detection(env, has_vad=True)

        self.assertEqual(turn_detection, "stt")
        self.assertEqual(reason, "stt_end_of_turn")

    def test_installed_agents_sdk_accepts_interruption_kwargs(self) -> None:
        from livekit.agents import AgentSession

        params = inspect.signature(AgentSession.__init__).parameters

        for name in (
            "min_interruption_words",
            "false_interruption_timeout",
            "resume_false_interruption",
            "min_consecutive_speech_delay",
            "aec_warmup_duration",
        ):
            self.assertIn(name, params)

    def test_turn_detector_model_cache_check_looks_for_exact_assets(self) -> None:
        manifest = {
            "repo_id": "livekit/turn-detector",
            "revision": "v0.4.1-intl",
            "onnx_filename": "model_q8.onnx",
        }

        with (
            patch("worker._get_turn_detector_cache_manifest", return_value=manifest),
            patch(
                "huggingface_hub.hf_hub_download",
                side_effect=[
                    "/tmp/model_q8.onnx",
                    "/tmp/config.json",
                    "/tmp/languages.json",
                    "/tmp/special_tokens_map.json",
                    "/tmp/tokenizer.json",
                    "/tmp/tokenizer_config.json",
                ],
            ) as download,
        ):
            self.assertTrue(_turn_detector_model_is_cached())

        self.assertEqual(download.call_count, 6)

    def test_turn_detector_model_cache_check_rejects_partial_snapshot(self) -> None:
        manifest = {
            "repo_id": "livekit/turn-detector",
            "revision": "v0.4.1-intl",
            "onnx_filename": "model_q8.onnx",
        }

        with (
            patch("worker._get_turn_detector_cache_manifest", return_value=manifest),
            patch(
                "huggingface_hub.hf_hub_download",
                side_effect=[
                    "/tmp/model_q8.onnx",
                    OSError("missing tokenizer config"),
                ],
            ),
        ):
            self.assertFalse(_turn_detector_model_is_cached())

    def test_turn_detector_model_cache_check_returns_false_when_exact_assets_missing(self) -> None:
        manifest = {
            "repo_id": "livekit/turn-detector",
            "revision": "v0.4.1-intl",
            "onnx_filename": "model_q8.onnx",
        }

        with (
            patch("worker._get_turn_detector_cache_manifest", return_value=manifest),
            patch("huggingface_hub.hf_hub_download", side_effect=OSError("missing")),
        ):
            self.assertFalse(_turn_detector_model_is_cached())

    def test_voice_sync_transcription_defaults_to_fast_async_display(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(_voice_sync_transcription_enabled())

        with patch.dict(os.environ, {"VIVENTIUM_VOICE_SYNC_TRANSCRIPTION": "1"}, clear=True):
            self.assertTrue(_voice_sync_transcription_enabled())

    def test_pinned_livekit_word_tokenizer_preserves_spacing_for_synced_transcripts(self) -> None:
        from livekit.agents import tokenize

        tokenizer = tokenize.basic.WordTokenizer(
            retain_format=True,
            ignore_punctuation=False,
            split_character=True,
        )

        text = "Night, friend. Ha. Which one?"
        self.assertEqual("".join(tokenizer.tokenize(text)), text)

    def test_pinned_livekit_synchronizer_uses_display_safe_word_tokenizer_for_opt_in_sync(self) -> None:
        from livekit.agents.voice.transcription import synchronizer

        source = inspect.getsource(synchronizer.TranscriptSynchronizer)

        self.assertIn("WordTokenizer", source)
        self.assertIn("retain_format=True", source)
        self.assertIn("ignore_punctuation=False", source)
        self.assertIn("split_character=True", source)

    def test_presentation_events_distinguish_provisional_barge_in_from_generated_reply(self) -> None:
        class Session:
            def __init__(self):
                self.handlers = {}

            def on(self, name):
                def register(handler):
                    self.handlers[name] = handler
                    return handler

                return register

        class Llm:
            def __init__(self):
                self.handles = []
                self.provisional = 0

            def register_speech_handle(self, handle):
                self.handles.append(handle)

            def note_provisional_interruption(self):
                self.provisional += 1

        session = Session()
        llm = Llm()
        _register_presentation_lifecycle_handlers(session, llm)

        generated = object()
        session.handlers["speech_created"](
            SimpleNamespace(
                source="generate_reply",
                user_initiated=True,
                speech_handle=generated,
            )
        )
        session.handlers["speech_created"](
            SimpleNamespace(source="say", user_initiated=True, speech_handle=object())
        )
        session.handlers["overlapping_speech"](
            SimpleNamespace(is_interruption=False)
        )
        session.handlers["overlapping_speech"](
            SimpleNamespace(is_interruption=True)
        )

        self.assertEqual(llm.handles, [generated])
        self.assertEqual(llm.provisional, 1)

    def test_replacement_prewarm_never_outwaits_an_active_call(self) -> None:
        marker = SimpleNamespace()
        with (
            patch.dict(
                os.environ,
                {"VIVENTIUM_VOICE_REPLACEMENT_PREWARM_MAX_WAIT_S": "0.01"},
                clear=False,
            ),
            patch(
                "worker._active_voice_job_markers",
                side_effect=[[marker], [marker], []],
            ) as active_markers,
            patch("worker.time.monotonic", side_effect=[0.0, 1.0, 2.0]),
            patch("worker.time.sleep"),
        ):
            _wait_for_active_voice_jobs_before_prewarm()

        self.assertEqual(active_markers.call_count, 3)

    def test_room_empty_participant_disconnect_clears_active_marker(self) -> None:
        class FakeRoom:
            name = "room"

            def __init__(self) -> None:
                self.handlers = {}
                self.remote_participants = {}

            def on(self, event_name):
                def _register(handler):
                    self.handlers[event_name] = handler
                    return handler

                return _register

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(
                os.environ,
                {
                    "TMPDIR": tmp_dir,
                    "VIVENTIUM_VOICE_WORKER_RUN_ID": "test-run",
                },
                clear=False,
            ):
                marker = _mark_active_voice_job("job-1")
                room = FakeRoom()
                ctx = SimpleNamespace(room=room)
                participant = SimpleNamespace(identity="owner")

                _attach_room_diagnostics(
                    ctx,
                    call_session_id="test-call",
                    active_job_marker=marker,
                )
                room.handlers["participant_disconnected"](participant)

                self.assertNotIn(marker, _active_voice_job_markers())

    def test_local_whisper_defaults_tts_prewarm_off_to_protect_stt_latency(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIVENTIUM_STT_PROVIDER": "whisper_local",
                "VIVENTIUM_TTS_PROVIDER": "local_chatterbox_turbo_mlx_8bit",
            },
            clear=True,
        ):
            env = load_env()

        self.assertFalse(env.voice_prewarm_local_tts)


if __name__ == "__main__":
    unittest.main()
