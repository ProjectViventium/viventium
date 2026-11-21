import inspect
import base64
import hashlib
import hmac
import os
import sys
import tempfile
import types
import unittest
import asyncio
import json
from types import SimpleNamespace
from dataclasses import replace
from unittest.mock import MagicMock, patch


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worker import (
    _build_current_call_runtime_context,
    _apply_requested_voice_route,
    _attach_room_diagnostics,
    _build_assemblyai_stt_kwargs,
    _build_voice_capability_catalog,
    _active_voice_job_markers,
    _clear_active_voice_job_marker,
    _mark_active_voice_job,
    _voice_sync_transcription_enabled,
    _record_completed_tts_trace,
    ViventiumVoiceAgent,
    _publish_livekit_speaker_segments,
    _publish_livekit_task_event,
    _interrupt_livekit_speech_handles,
    _interrupt_agent_session_speech,
    _register_presentation_lifecycle_handlers,
    _apply_authoritative_call_mode_to_speech_planes,
    _classify_authoritative_mode_sync,
    _suspend_all_call_speech_until_authoritative,
    _suspend_call_response_playout_until_authoritative,
    _apply_task_cancel_suppression,
    AuthoritativeCallModeState,
    VoiceEngagementAuthority,
    CallTaskStreamSpeechAuthority,
    TaskStreamAudioAuthorityGate,
    _ingest_raw_stt_speaker_event,
    _linked_participant_speaker_context,
    build_stt_selection,
    build_turn_handling,
    load_env,
)
from livekit import rtc
from livekit.agents import StopResponse, inference
from livekit.agents.stt import SpeechData, SpeechEvent, SpeechEventType
from livekit.agents.llm.chat_context import ChatContext, ChatMessage
from speaker_segments import SpeakerSegmentTracker, SPEAKER_CONTEXT_EXTRA_KEY


def _real_sdk_speaker():
    """A real LiveKit ``io.AudioOutput`` (pause-capable, like RoomIO's) that plays into nothing."""
    from livekit.agents.voice import io as lk_io

    class Speaker(lk_io.AudioOutput):
        def __init__(self):
            super().__init__(label='synthetic', capabilities=lk_io.AudioOutputCapabilities(pause=True),
                             sample_rate=24000)
            self.frames = []; self._pushed = 0.0
            self.pauses = 0; self.resumes = 0; self.paused = False
        async def capture_frame(self, frame):
            await super().capture_frame(frame)
            self.frames.append(frame); self._pushed += frame.duration
        def flush(self):
            super().flush()
            pushed, self._pushed = self._pushed, 0.0
            if pushed:
                asyncio.get_running_loop().call_soon(
                    lambda: self.on_playback_finished(playback_position=pushed, interrupted=False))
        def clear_buffer(self): pass
        def pause(self):
            super().pause(); self.pauses += 1; self.paused = True
        def resume(self):
            super().resume(); self.resumes += 1; self.paused = False

    return Speaker()


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


def _signed_voice_engagement(
    *,
    call_session_id="call_1",
    turn_id="turn_000001",
    participant_identity="owner",
    segment_ids=None,
    directly_addressed=True,
    revision=1,
    now_ms=1787659200000,
    secret="synthetic-core-only-signing-secret",
):
    receipt = {
        "version": 1,
        "callSessionId": call_session_id,
        "turnId": turn_id,
        "participantIdentity": participant_identity,
        "segmentIds": segment_ids or ["segment_000001"],
        "directlyAddressed": directly_addressed,
        "source": "semantic_model",
        "revision": revision,
        "issuedAtMs": now_ms,
        "expiresAtMs": now_ms + 30_000,
    }
    signed_values = [
        receipt["version"],
        receipt["callSessionId"],
        receipt["turnId"],
        receipt["participantIdentity"],
        receipt["segmentIds"],
        receipt["directlyAddressed"],
        receipt["source"],
        receipt["revision"],
        receipt["issuedAtMs"],
        receipt["expiresAtMs"],
    ]
    encoded = json.dumps(signed_values, ensure_ascii=False, separators=(",", ":")).encode()
    digest = hmac.new(secret.encode(), encoded, hashlib.sha256).digest()
    receipt["attestation"] = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return receipt


async def _verify_synthetic_voice_engagement(receipt):
    expected = _signed_voice_engagement(
        call_session_id=receipt["callSessionId"],
        turn_id=receipt["turnId"],
        participant_identity=receipt["participantIdentity"],
        segment_ids=receipt["segmentIds"],
        directly_addressed=receipt["directlyAddressed"],
        revision=receipt["revision"],
        now_ms=receipt["issuedAtMs"],
    )
    return hmac.compare_digest(expected["attestation"], receipt["attestation"])


class TestWorkerTurnHandling(unittest.TestCase):
    def test_tts_completion_trace_requires_correlated_non_cancelled_metrics(self) -> None:
        llm_impl = MagicMock()
        llm_impl.record_completed_trace_stage.return_value = True

        self.assertTrue(
            _record_completed_tts_trace(
                llm_impl,
                SimpleNamespace(cancelled=False),
                "request_1",
            )
        )
        self.assertFalse(
            _record_completed_tts_trace(
                llm_impl,
                SimpleNamespace(cancelled=True),
                "request_2",
            )
        )
        self.assertFalse(
            _record_completed_tts_trace(
                llm_impl,
                SimpleNamespace(cancelled=False),
                "",
            )
        )
        llm_impl.record_completed_trace_stage.assert_called_once_with(
            "request_1",
            "tts.completed",
        )

    def test_terminal_authoritative_mode_sync_does_not_apply_none_or_warn_unavailable(self) -> None:
        self.assertEqual(
            _classify_authoritative_mode_sync(None, terminal_state_seen=True),
            "terminal",
        )
        self.assertEqual(
            _classify_authoritative_mode_sync(None, terminal_state_seen=False),
            "unavailable",
        )
        self.assertEqual(
            _classify_authoritative_mode_sync("call", terminal_state_seen=False),
            "apply",
        )

    @staticmethod
    def _task_stream_audio_session():
        class Audio:
            can_pause = True

            def __init__(self):
                self.pauses = 0
                self.resumes = 0
                self.playback_enabled = True

            def pause(self):
                self.pauses += 1
                self.playback_enabled = False

            def resume(self):
                self.resumes += 1
                self.playback_enabled = True

        class Output:
            def __init__(self):
                self.audio = Audio()
                self.enabled = []

            def set_audio_enabled(self, enabled):
                self.enabled.append(enabled)

        class Session:
            def __init__(self):
                self.output = Output()
                self.interrupts = []

            def interrupt(self, *, force=False):
                self.interrupts.append(force)

        return Session()

    def test_task_stream_reconnect_before_first_token_gates_audio_without_cancelling_generation(self) -> None:
        session = self._task_stream_audio_session()
        gate = TaskStreamAudioAuthorityGate(session)
        generation = {"state": "waiting_for_first_token", "finals": 0}

        async def fetch_state():
            return _authoritative_state(revision=8)

        def apply_state(_state):
            gate.restore()
            return True

        authority = CallTaskStreamSpeechAuthority(
            call_session_id="call_1",
            fetch_call_state=fetch_state,
            suspend=gate.suspend,
            terminate=gate.terminate,
            apply_state=apply_state,
        )

        async def run():
            await authority.on_stream_health(_stream_health("connected"))
            self.assertTrue(authority.mark_session_ready(_authoritative_state()))
            session.output.audio.pauses = 0
            session.output.audio.resumes = 0
            await authority.on_stream_health(_stream_health("disconnected"))
            await authority.on_stream_health(_stream_health("connecting"))
            self.assertEqual(generation["state"], "waiting_for_first_token")
            await authority.on_stream_health(_stream_health("connected"))

        asyncio.run(run())

        self.assertTrue(authority.authoritative)
        self.assertEqual(session.output.audio.pauses, 1)
        self.assertEqual(session.output.audio.resumes, 1)
        self.assertEqual(session.interrupts, [])
        self.assertEqual(generation, {"state": "waiting_for_first_token", "finals": 0})

    def test_task_stream_reconnect_midstream_restores_once_and_preserves_final_delivery(self) -> None:
        session = self._task_stream_audio_session()
        gate = TaskStreamAudioAuthorityGate(session)
        generation = {"state": "streaming", "tokens": ["part one"], "finals": 0}

        async def fetch_state():
            generation["tokens"].append("part two")
            return _authoritative_state(revision=9)

        def apply_state(_state):
            gate.restore()
            return True

        authority = CallTaskStreamSpeechAuthority(
            call_session_id="call_1",
            fetch_call_state=fetch_state,
            suspend=gate.suspend,
            terminate=gate.terminate,
            apply_state=apply_state,
        )

        async def run():
            await authority.on_stream_health(_stream_health("connected"))
            self.assertTrue(authority.mark_session_ready(_authoritative_state()))
            session.output.audio.pauses = 0
            session.output.audio.resumes = 0
            await authority.on_stream_health(_stream_health("disconnected"))
            await authority.on_stream_health(_stream_health("connected"))
            # Duplicate health/reconciliation must not replay the presentation.
            await authority.on_stream_health(_stream_health("connected"))
            generation["state"] = "completed"
            generation["finals"] += 1

        asyncio.run(run())

        self.assertEqual(session.output.audio.pauses, 1)
        self.assertEqual(session.output.audio.resumes, 1)
        self.assertEqual(session.interrupts, [])
        self.assertEqual(generation["tokens"], ["part one", "part two"])
        self.assertEqual(generation["finals"], 1)

    def test_transient_state_reconciliation_gates_audio_without_cancelling_attached_generation(
        self,
    ) -> None:
        session = self._task_stream_audio_session()
        gate = TaskStreamAudioAuthorityGate(session)
        mode_state = AuthoritativeCallModeState()
        mode_state.apply("call")

        class Plane:
            def __init__(self):
                self.suspensions = 0

            def suspend_until_authoritative(self):
                self.suspensions += 1

        followup = Plane()
        attached_generation = {"state": "streaming", "finals": 0}

        gated = _suspend_call_response_playout_until_authoritative(
            followup_scheduler=followup,
            audio_gate=gate,
            authoritative_mode_state=mode_state,
        )
        attached_generation["state"] = "completed"
        attached_generation["finals"] += 1

        self.assertTrue(gated)
        self.assertFalse(mode_state.allows_agent_dispatch)
        self.assertEqual(followup.suspensions, 1)
        self.assertEqual(session.output.audio.pauses, 1)
        self.assertEqual(session.interrupts, [])
        self.assertEqual(attached_generation, {"state": "completed", "finals": 1})

        self.assertTrue(gate.restore())
        self.assertEqual(session.output.audio.resumes, 1)

    def test_authority_and_false_interruption_audio_holds_cannot_release_each_other(
        self,
    ) -> None:
        session = self._task_stream_audio_session()
        gate = TaskStreamAudioAuthorityGate(session)
        self.assertTrue(gate.bind_current_output())

        self.assertTrue(gate.suspend())
        session.output.audio.pause()
        session.output.audio.resume()
        self.assertTrue(gate.gated)
        self.assertFalse(session.output.audio.playback_enabled)
        self.assertEqual(session.output.audio.pauses, 1)
        self.assertEqual(session.output.audio.resumes, 0)

        self.assertTrue(gate.restore())
        self.assertTrue(session.output.audio.playback_enabled)
        self.assertEqual(session.output.audio.resumes, 1)

        session.output.audio.pause()
        self.assertTrue(gate.suspend())
        self.assertTrue(gate.restore())
        self.assertFalse(session.output.audio.playback_enabled)
        self.assertEqual(session.output.audio.pauses, 2)
        self.assertEqual(session.output.audio.resumes, 1)

        session.output.audio.resume()
        self.assertTrue(session.output.audio.playback_enabled)
        self.assertEqual(session.output.audio.resumes, 2)

    def test_authority_hold_survives_the_real_sdk_resume_before_each_reply(self) -> None:
        # LiveKit 1.8.11 added a caller of the audio output's pause/resume: before a reply's audio
        # is forwarded, AgentActivity._reconcile_playout_pause() resumes the output when its own
        # false-interruption pause is not in force. That resume must not release Viventium's
        # authority hold. Real AgentSession, real io.AudioOutput, real reply pipeline.
        from livekit.agents import AgentSession, llm as lk_llm
        from livekit.agents.llm import ChatChunk, ChoiceDelta
        from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS
        from livekit.agents.voice.agent_activity import AgentActivity
        from worker import Agent, _ReasonScopedAudioPauseCoordinator

        class BackendStream(lk_llm.LLMStream):
            async def _run(self):
                self._event_ch.send_nowait(ChatChunk(id='stream-a', delta=ChoiceDelta(
                    role='assistant', content='A reply made while authority is uncertain.')))

        class Backend(lk_llm.LLM):
            def chat(self, *, chat_ctx, tools=None, conn_options=DEFAULT_API_CONNECT_OPTIONS, **kwargs):
                return BackendStream(self, chat_ctx=chat_ctx, tools=tools or [], conn_options=conn_options)

        async def one_frame(agent, text, settings):
            async for _piece in text: pass
            yield rtc.AudioFrame(data=b'\0\0'*240, sample_rate=24000, num_channels=1, samples_per_channel=240)

        async def run():
            backend = Backend()
            session = AgentSession(llm=backend, vad=None, stt=None, tts=None, tts_text_transforms=['filter_emoji'],
                                   turn_handling={'turn_detection': 'manual', 'preemptive_generation': {'enabled': False}})
            speaker = _real_sdk_speaker()
            session.output.audio = speaker
            sdk_reconciles = []; sdk_resumes = []
            real_reconcile = AgentActivity._reconcile_playout_pause
            real_resume = _ReasonScopedAudioPauseCoordinator.resume

            def reconcile(activity, speech_handle):
                sdk_reconciles.append(speech_handle.id)
                return real_reconcile(activity, speech_handle)

            def resume(coordinator):
                sdk_resumes.append(speaker.paused)
                return real_resume(coordinator)

            with patch.object(Agent.default, 'tts_node', one_frame), \
                 patch.object(AgentActivity, '_reconcile_playout_pause', reconcile), \
                 patch.object(_ReasonScopedAudioPauseCoordinator, 'resume', resume):
                await session.start(agent=ViventiumVoiceAgent(instructions='Synthetic', llm=backend))
                try:
                    gate = TaskStreamAudioAuthorityGate(session)
                    self.assertTrue(gate.bind_current_output())
                    self.assertTrue(gate.suspend())
                    held = (speaker.pauses, speaker.resumes, speaker.paused)
                    handle = session.generate_reply(user_input='Synthetic request.')
                    await asyncio.wait_for(handle, 5)
                    during = (speaker.pauses, speaker.resumes, speaker.paused, len(speaker.frames))
                    self.assertTrue(gate.restore())
                    restored = (speaker.pauses, speaker.resumes, speaker.paused)
                    # Without a Viventium hold the SDK's own pause and resume pass straight through.
                    session.output.audio.pause()
                    sdk_paused = speaker.paused
                    session.output.audio.resume()
                    passthrough = (speaker.pauses, speaker.resumes, speaker.paused)
                finally:
                    await session.aclose()
            return held, during, restored, sdk_paused, passthrough, sdk_reconciles, sdk_resumes

        held, during, restored, sdk_paused, passthrough, sdk_reconciles, sdk_resumes = asyncio.run(run())
        self.assertEqual(held, (1, 0, True))
        # The SDK reconciled playout for the reply and called resume on the (still paused) output...
        self.assertEqual(len(sdk_reconciles), 1)
        self.assertIn(True, sdk_resumes)
        # ...and the output stayed paused: the reply was generated, nothing was released.
        self.assertEqual(during, (1, 0, True, 1))
        self.assertEqual(restored, (1, 1, False))
        self.assertTrue(sdk_paused)
        self.assertEqual(passthrough, (2, 2, False))

    def test_stale_reconnect_snapshot_stays_gated_and_call_end_interrupts(self) -> None:
        session = self._task_stream_audio_session()
        gate = TaskStreamAudioAuthorityGate(session)

        async def fetch_state():
            return _authoritative_state(revision=6)

        def reject_stale(state):
            if state["revision"] < 7:
                return False
            gate.restore()
            return True

        authority = CallTaskStreamSpeechAuthority(
            call_session_id="call_1",
            fetch_call_state=fetch_state,
            suspend=gate.suspend,
            terminate=gate.terminate,
            apply_state=reject_stale,
        )

        async def run():
            await authority.on_stream_health(_stream_health("connected"))
            self.assertTrue(authority.mark_session_ready(_authoritative_state(revision=7)))
            session.output.audio.pauses = 0
            session.output.audio.resumes = 0
            await authority.on_stream_health(_stream_health("disconnected"))
            await authority.on_stream_health(_stream_health("connected"))
            self.assertFalse(authority.authoritative)
            await authority.on_stream_health(_stream_health("terminal", status=401))

        asyncio.run(run())

        self.assertEqual(session.output.audio.pauses, 1)
        self.assertEqual(session.output.audio.resumes, 0)
        self.assertEqual(session.interrupts, [True])

    def test_presentation_events_distinguish_provisional_barge_in_from_generated_reply(self) -> None:
        class Session:
            def __init__(self):
                self.handlers = {}
                self.current_speech = SimpleNamespace(done=lambda: False, interrupted=False)

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

            def note_provisional_interruption(self, *, speech_handle):
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

    def test_terminal_task_stream_410_shuts_down_job_once_and_cannot_restore(self) -> None:
        session = self._task_stream_audio_session()
        gate = TaskStreamAudioAuthorityGate(session)
        shutdown = MagicMock()
        fetch_state = MagicMock(side_effect=AssertionError("terminal call cannot fetch"))
        authority = CallTaskStreamSpeechAuthority(
            call_session_id="call_1",
            fetch_call_state=fetch_state,
            suspend=gate.suspend,
            terminate=gate.terminate,
            shutdown=shutdown,
            apply_state=lambda _state: gate.restore(),
        )

        async def run():
            await authority.on_stream_health(_stream_health("connected"))
            self.assertTrue(authority.mark_session_ready(_authoritative_state()))
            await authority.on_stream_health(_stream_health("terminal", status=410))
            await authority.on_stream_health(_stream_health("stopped"))
            await authority.on_stream_health(_stream_health("connected"))
            self.assertFalse(await authority.reconcile())
            self.assertFalse(authority.mark_session_ready(_authoritative_state()))

        asyncio.run(run())

        shutdown.assert_called_once_with()
        fetch_state.assert_not_called()
        self.assertFalse(authority.authoritative)
        self.assertFalse(authority.stream_connected)
        self.assertTrue(gate.gated)
        self.assertEqual(session.interrupts, [True])

    def test_retryable_task_stream_gap_keeps_job_live_and_restores_owned_snapshot(self) -> None:
        shutdown = MagicMock()
        fetched = []

        async def fetch_state():
            fetched.append("fresh")
            return _authoritative_state(revision=8)

        authority = CallTaskStreamSpeechAuthority(
            call_session_id="call_1",
            fetch_call_state=fetch_state,
            suspend=lambda: None,
            terminate=lambda: None,
            shutdown=shutdown,
            apply_state=lambda _state: True,
        )

        async def run():
            await authority.on_stream_health(_stream_health("connected"))
            self.assertTrue(authority.mark_session_ready(_authoritative_state()))
            await authority.on_stream_health(_stream_health("disconnected"))
            self.assertFalse(authority.authoritative)
            await authority.on_stream_health(_stream_health("connected"))
            self.assertTrue(authority.authoritative)

        asyncio.run(run())

        shutdown.assert_not_called()
        self.assertEqual(fetched, ["fresh"])

    def test_authoritative_end_uses_same_once_only_local_job_shutdown(self) -> None:
        terminate = MagicMock()
        shutdown = MagicMock()
        authority = CallTaskStreamSpeechAuthority(
            call_session_id="call_1",
            fetch_call_state=None,
            suspend=lambda: None,
            terminate=terminate,
            shutdown=shutdown,
            apply_state=lambda _state: True,
        )

        authority.terminate()
        authority.terminate()
        asyncio.run(authority.on_stream_health(_stream_health("stopped")))

        terminate.assert_called_once_with()
        shutdown.assert_called_once_with()
        self.assertFalse(authority.authoritative)
        self.assertFalse(authority.stream_connected)

    def test_inflight_task_stream_snapshot_cannot_restore_after_terminal_end(self) -> None:
        shutdown = MagicMock()
        applied = []

        async def run():
            fetching = asyncio.Event()
            release = asyncio.Event()

            async def fetch_state():
                fetching.set()
                await release.wait()
                return _authoritative_state(revision=8)

            authority = CallTaskStreamSpeechAuthority(
                call_session_id="call_1",
                fetch_call_state=fetch_state,
                suspend=lambda: None,
                terminate=lambda: None,
                shutdown=shutdown,
                apply_state=applied.append,
            )
            await authority.on_stream_health(_stream_health("connected"))
            self.assertTrue(authority.mark_session_ready(_authoritative_state()))
            applied.clear()
            restore = asyncio.create_task(authority.reconcile())
            await fetching.wait()
            await authority.on_stream_health(_stream_health("terminal", status=410))
            release.set()

            self.assertFalse(await restore)
            self.assertFalse(authority.authoritative)
            self.assertFalse(authority.stream_connected)
            self.assertEqual(applied, [])

        asyncio.run(run())
        shutdown.assert_called_once_with()

    def test_inflight_task_stream_snapshot_stays_gated_until_new_connection(self) -> None:
        shutdown = MagicMock()
        applied = []
        fetched = []

        async def run():
            fetching = asyncio.Event()
            release = asyncio.Event()

            async def fetch_state():
                fetched.append("fresh")
                fetching.set()
                await release.wait()
                return _authoritative_state(revision=8)

            authority = CallTaskStreamSpeechAuthority(
                call_session_id="call_1",
                fetch_call_state=fetch_state,
                suspend=lambda: None,
                terminate=lambda: None,
                shutdown=shutdown,
                apply_state=applied.append,
            )
            await authority.on_stream_health(_stream_health("connected"))
            self.assertTrue(authority.mark_session_ready(_authoritative_state()))
            applied.clear()
            restore = asyncio.create_task(authority.reconcile())
            await fetching.wait()
            await authority.on_stream_health(_stream_health("disconnected"))
            release.set()

            self.assertFalse(await restore)
            self.assertFalse(authority.authoritative)
            self.assertEqual(applied, [])
            await authority.on_stream_health(_stream_health("connected"))
            self.assertTrue(authority.authoritative)
            self.assertEqual(len(applied), 1)

        asyncio.run(run())
        shutdown.assert_not_called()
        self.assertEqual(fetched, ["fresh", "fresh"])

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

    def test_stt_audio_offset_uses_paired_call_utc_origin_for_latency(self) -> None:
        for origin in (1_790_000_000_000.0, None):
            tracker = SpeakerSegmentTracker(call_session_id="call_clock")
            tracker.ingest(
                transcript="A stable timing test sentence.", is_final=True,
                provider_speaker_id="A", created_at=1_790_000_012.0,
                start_time=10.0, end_time=11.0,
            )
            message = SimpleNamespace(text_content="A stable timing test sentence.", extra={})
            agent = ViventiumVoiceAgent(
                instructions="test", speaker_tracker=tracker,
                speaker_timeline_origin=(lambda: origin) if origin is not None else None,
            )
            asyncio.run(agent.on_user_turn_completed(None, message))
            context = message.extra[SPEAKER_CONTEXT_EXTRA_KEY]
            self.assertEqual(context["utteranceEndOffsetMs"], 11_000.0)
            self.assertEqual(context["sttFinalObservedAtMs"], 1_790_000_012_000.0)
            if origin is not None:
                self.assertEqual(context["utteranceEndClock"], "utc")
                self.assertEqual(context["utteranceEndAtMs"], origin + 11_000.0)
                self.assertEqual(context["utteranceEndTimingSource"], "stt_call_audio_timeline")
            else:
                self.assertEqual(context["utteranceEndClock"], "call_audio_relative")
                self.assertNotIn("utteranceEndAtMs", context)

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

    def test_passive_wing_owner_turn_stops_before_any_llm_or_external_action(self) -> None:
        tracker = SpeakerSegmentTracker(
            call_session_id="call_1",
            participant_identity="owner",
            owner_signed=True,
        )
        tracker.ingest(
            transcript="I should remember to pick up the blue folder tomorrow afternoon.",
            is_final=True,
            provider_speaker_id="A",
            created_at=1.0,
            start_time=0.0,
            end_time=1.5,
        )
        mode_state = AuthoritativeCallModeState()
        mode_state.apply("wing")
        authority = VoiceEngagementAuthority(
            call_session_id="call_1",
            owner_participant_identity="owner",
            verify_receipt=_verify_synthetic_voice_engagement,
            clock_ms=lambda: 1787659200001,
            wait_timeout_s=0.0,
        )
        persisted = []

        async def persist(context, mode):
            persisted.append((context, mode))

        agent = ViventiumVoiceAgent(
            instructions="test",
            speaker_tracker=tracker,
            authoritative_mode_state=mode_state,
            voice_engagement_authority=authority,
            persist_suppressed_turn=persist,
        )
        message = ChatMessage(
            role="user",
            content=["I should remember to pick up the blue folder tomorrow afternoon."],
        )

        with self.assertRaises(StopResponse):
            asyncio.run(agent.on_user_turn_completed(ChatContext.empty(), message))

        self.assertEqual(len(persisted), 1)
        self.assertEqual(persisted[0][1], "wing")
        self.assertNotIn("voiceEngagement", message.extra[SPEAKER_CONTEXT_EXTRA_KEY])

    def test_signed_directly_addressed_owner_turn_crosses_wing_authority_once(self) -> None:
        tracker = SpeakerSegmentTracker(
            call_session_id="call_1",
            participant_identity="owner",
            owner_signed=True,
        )
        tracker.ingest(
            transcript="Please launch the requested worker.",
            is_final=True,
            provider_speaker_id="A",
            created_at=1.0,
            start_time=0.0,
            end_time=1.5,
        )
        mode_state = AuthoritativeCallModeState()
        mode_state.apply("wing")
        authority = VoiceEngagementAuthority(
            call_session_id="call_1",
            owner_participant_identity="owner",
            verify_receipt=_verify_synthetic_voice_engagement,
            clock_ms=lambda: 1787659200001,
            wait_timeout_s=0.0,
        )
        receipt = _signed_voice_engagement()
        packet = SimpleNamespace(
            topic="viventium.voice.engagement.v1",
            participant=SimpleNamespace(identity="owner"),
            data=json.dumps(receipt).encode(),
        )
        self.assertTrue(authority.accept_packet(packet))
        persisted = []

        async def persist(context, mode):
            persisted.append((context, mode))

        agent = ViventiumVoiceAgent(
            instructions="test",
            speaker_tracker=tracker,
            authoritative_mode_state=mode_state,
            voice_engagement_authority=authority,
            persist_suppressed_turn=persist,
        )
        message = ChatMessage(role="user", content=["Please launch the requested worker."])

        asyncio.run(agent.on_user_turn_completed(ChatContext.empty(), message))

        self.assertEqual(persisted, [])
        self.assertEqual(
            message.extra[SPEAKER_CONTEXT_EXTRA_KEY]["voiceEngagement"], receipt
        )
        self.assertFalse(authority.accept_packet(packet))

    def test_signed_wing_turn_dispatches_only_after_two_fresh_owner_revision_checks(
        self,
    ) -> None:
        tracker = SpeakerSegmentTracker(
            call_session_id="call_1",
            participant_identity="owner",
            owner_signed=True,
        )
        tracker.ingest(
            transcript="Please launch the requested worker.",
            is_final=True,
            provider_speaker_id="A",
            created_at=1.0,
            start_time=0.0,
            end_time=1.5,
        )
        mode_state = AuthoritativeCallModeState()
        mode_state.apply("wing")
        authority = VoiceEngagementAuthority(
            call_session_id="call_1",
            owner_participant_identity="owner",
            verify_receipt=_verify_synthetic_voice_engagement,
            clock_ms=lambda: 1787659200001,
            wait_timeout_s=0.0,
        )
        receipt = _signed_voice_engagement()
        authority.accept_packet(
            SimpleNamespace(
                topic="viventium.voice.engagement.v1",
                participant=SimpleNamespace(identity="owner"),
                data=json.dumps(receipt).encode(),
            )
        )
        refreshed = []

        async def refresh(context):
            refreshed.append(context["speakerSegments"][0]["revision"])
            return {
                "version": 1,
                "callSessionId": "call_1",
                "mode": "wing",
                "status": "listening",
                "revision": 8,
                "speakerSegments": context["speakerSegments"],
            }

        agent = ViventiumVoiceAgent(
            instructions="test",
            speaker_tracker=tracker,
            authoritative_mode_state=mode_state,
            voice_engagement_authority=authority,
            refresh_turn_authority=refresh,
        )
        message = ChatMessage(role="user", content=["Please launch the requested worker."])

        asyncio.run(agent.on_user_turn_completed(ChatContext.empty(), message))

        self.assertEqual(refreshed, [1, 1])
        self.assertEqual(
            message.extra[SPEAKER_CONTEXT_EXTRA_KEY]["voiceEngagement"], receipt
        )

    def test_signed_wing_turn_is_suppressed_when_persisted_mode_changes_during_receipt_wait(
        self,
    ) -> None:
        tracker = SpeakerSegmentTracker(
            call_session_id="call_1",
            participant_identity="owner",
            owner_signed=True,
        )
        tracker.ingest(
            transcript="Please launch the requested worker.",
            is_final=True,
            provider_speaker_id="A",
            created_at=1.0,
            start_time=0.0,
            end_time=1.5,
        )
        mode_state = AuthoritativeCallModeState()
        mode_state.apply("wing")
        receipt = _signed_voice_engagement()
        persisted = []
        refresh_count = 0

        class RacingAuthority:
            async def await_turn(self, _turn_id, _segments):
                await asyncio.sleep(0)
                return receipt

        async def refresh(_context):
            nonlocal refresh_count
            refresh_count += 1
            return {
                "version": 1,
                "callSessionId": "call_1",
                "mode": "wing" if refresh_count == 1 else "listen_only",
                "status": "listening",
                "revision": 7 + refresh_count,
                "speakerSegments": _context.get("speakerSegments", []),
            }

        async def persist(context, mode):
            persisted.append((context, mode))

        agent = ViventiumVoiceAgent(
            instructions="test",
            speaker_tracker=tracker,
            authoritative_mode_state=mode_state,
            voice_engagement_authority=RacingAuthority(),
            persist_suppressed_turn=persist,
            refresh_turn_authority=refresh,
        )
        message = ChatMessage(role="user", content=["Please launch the requested worker."])

        with self.assertRaises(StopResponse):
            asyncio.run(agent.on_user_turn_completed(ChatContext.empty(), message))

        self.assertEqual([mode for _context, mode in persisted], ["listen_only"])
        self.assertEqual(refresh_count, 2)
        self.assertNotIn("voiceEngagement", message.extra[SPEAKER_CONTEXT_EXTRA_KEY])

    def test_signed_wing_turn_is_suppressed_when_latest_persisted_segment_loses_owner_trust(
        self,
    ) -> None:
        tracker = SpeakerSegmentTracker(
            call_session_id="call_1",
            participant_identity="owner",
            owner_signed=True,
        )
        tracker.ingest(
            transcript="Please launch the requested worker.",
            is_final=True,
            provider_speaker_id="A",
            created_at=1.0,
            start_time=0.0,
            end_time=1.5,
        )
        mode_state = AuthoritativeCallModeState()
        mode_state.apply("wing")
        authority = VoiceEngagementAuthority(
            call_session_id="call_1",
            owner_participant_identity="owner",
            verify_receipt=_verify_synthetic_voice_engagement,
            clock_ms=lambda: 1787659200001,
            wait_timeout_s=0.0,
        )
        receipt = _signed_voice_engagement()
        authority.accept_packet(
            SimpleNamespace(
                topic="viventium.voice.engagement.v1",
                participant=SimpleNamespace(identity="owner"),
                data=json.dumps(receipt).encode(),
            )
        )
        persisted = []
        refresh_count = 0

        async def refresh(context):
            nonlocal refresh_count
            refresh_count += 1
            trusted = context["speakerSegments"][0]
            downgraded = {
                **trusted,
                "revision": int(trusted["revision"]) + 1,
                "uncertain": True,
                "speaker": {
                    **trusted["speaker"],
                    "attribution": "unverified",
                    "actorTrust": "shared_mic_unverified",
                },
            }
            return {
                "version": 1,
                "callSessionId": "call_1",
                "mode": "wing",
                "status": "listening",
                "revision": 8,
                "speakerSegments": [trusted] if refresh_count == 1 else [downgraded],
            }

        async def persist(context, mode):
            persisted.append((context, mode))

        agent = ViventiumVoiceAgent(
            instructions="test",
            speaker_tracker=tracker,
            authoritative_mode_state=mode_state,
            voice_engagement_authority=authority,
            persist_suppressed_turn=persist,
            refresh_turn_authority=refresh,
        )
        message = ChatMessage(role="user", content=["Please launch the requested worker."])

        with self.assertRaises(StopResponse):
            asyncio.run(agent.on_user_turn_completed(ChatContext.empty(), message))

        self.assertEqual([mode for _context, mode in persisted], ["wing"])
        self.assertEqual(refresh_count, 2)
        self.assertEqual(persisted[0][0]["speakerSegments"][0]["revision"], 2)
        self.assertNotIn("voiceEngagement", message.extra[SPEAKER_CONTEXT_EXTRA_KEY])

    def test_gateway_fails_closed_when_fresh_persisted_turn_authority_is_unavailable(self) -> None:
        mode_state = AuthoritativeCallModeState()
        mode_state.apply("call")
        persisted = []

        async def refresh(_context):
            return None

        async def persist(context, mode):
            persisted.append((context, mode))

        agent = ViventiumVoiceAgent(
            instructions="test",
            authoritative_mode_state=mode_state,
            persist_suppressed_turn=persist,
            refresh_turn_authority=refresh,
        )

        with self.assertRaises(StopResponse):
            asyncio.run(
                agent.on_user_turn_completed(
                    ChatContext.empty(), ChatMessage(role="user", content=["Sensitive action"])
                )
            )

        self.assertEqual([mode for _context, mode in persisted], ["uncertain"])

    def test_gateway_fails_closed_when_persisted_call_session_changes_before_dispatch(
        self,
    ) -> None:
        tracker = SpeakerSegmentTracker(
            call_session_id="call_1",
            participant_identity="owner",
            owner_signed=True,
        )
        tracker.ingest(
            transcript="Please launch the requested worker.",
            is_final=True,
            provider_speaker_id="A",
            created_at=1.0,
            start_time=0.0,
            end_time=1.5,
        )
        mode_state = AuthoritativeCallModeState()
        mode_state.apply("call")
        persisted = []

        async def refresh(context):
            return {
                "version": 1,
                "callSessionId": "different_call",
                "mode": "call",
                "status": "listening",
                "revision": 8,
                "speakerSegments": context["speakerSegments"],
            }

        async def persist(context, mode):
            persisted.append((context, mode))

        agent = ViventiumVoiceAgent(
            instructions="test",
            speaker_tracker=tracker,
            authoritative_mode_state=mode_state,
            persist_suppressed_turn=persist,
            refresh_turn_authority=refresh,
        )

        with self.assertRaises(StopResponse):
            asyncio.run(
                agent.on_user_turn_completed(
                    ChatContext.empty(),
                    ChatMessage(role="user", content=["Please launch the requested worker."]),
                )
            )

        self.assertEqual([mode for _context, mode in persisted], ["uncertain"])
        self.assertIsNone(mode_state.mode)

    def test_forged_or_unsigned_browser_engagement_never_becomes_action_authority(self) -> None:
        authority = VoiceEngagementAuthority(
            call_session_id="call_1",
            owner_participant_identity="owner",
            verify_receipt=_verify_synthetic_voice_engagement,
            clock_ms=lambda: 1787659200001,
            wait_timeout_s=0.0,
        )
        signed = _signed_voice_engagement()
        for participant, forged in [
            ("guest", signed),
            ("owner", {**signed, "attestation": "forged"}),
            ("owner", {**signed, "callSessionId": "another_call"}),
            ("owner", {**signed, "participantIdentity": "guest"}),
            ("owner", {**signed, "source": "browser"}),
            ("owner", {**signed, "expiresAtMs": 1787659199999}),
        ]:
            with self.subTest(participant=participant, payload=forged):
                packet = SimpleNamespace(
                    topic="viventium.voice.engagement.v1",
                    participant=SimpleNamespace(identity=participant),
                    data=json.dumps(forged).encode(),
                )
                self.assertFalse(authority.accept_packet(packet))

        changed_turn = {**signed, "turnId": "turn_000002"}
        structurally_valid_packet = SimpleNamespace(
            topic="viventium.voice.engagement.v1",
            participant=SimpleNamespace(identity="owner"),
            data=json.dumps(changed_turn).encode(),
        )
        self.assertTrue(authority.accept_packet(structurally_valid_packet))
        self.assertIsNone(
            asyncio.run(
                authority.await_turn(
                    "turn_000002",
                    [
                        {
                            "segmentId": "segment_000001",
                            "turnId": "turn_000002",
                            "revision": 1,
                            "isFinal": True,
                            "speaker": {
                                "participantIdentity": "owner",
                                "attribution": "verified",
                                "actorTrust": "owner_participant",
                            },
                        }
                    ],
                )
            )
        )

    def test_gateway_transport_secret_forgery_cannot_bypass_core_verification(self) -> None:
        authority = VoiceEngagementAuthority(
            call_session_id="call_1",
            owner_participant_identity="owner",
            verify_receipt=_verify_synthetic_voice_engagement,
            clock_ms=lambda: 1787659200001,
            wait_timeout_s=0.0,
        )
        forged = _signed_voice_engagement(secret="synthetic-call-secret")
        packet = SimpleNamespace(
            topic="viventium.voice.engagement.v1",
            participant=SimpleNamespace(identity="owner"),
            data=json.dumps(forged).encode(),
        )
        segments = [
            {
                "segmentId": "segment_000001",
                "turnId": "turn_000001",
                "revision": 1,
                "isFinal": True,
                "speaker": {
                    "participantIdentity": "owner",
                    "attribution": "verified",
                    "actorTrust": "owner_participant",
                },
            }
        ]
        self.assertTrue(authority.accept_packet(packet))
        self.assertFalse(hasattr(authority, "_call_secret"))
        self.assertIsNone(asyncio.run(authority.await_turn("turn_000001", segments)))

    def test_gateway_fails_closed_when_core_engagement_verification_is_unavailable(self) -> None:
        authority = VoiceEngagementAuthority(
            call_session_id="call_1",
            owner_participant_identity="owner",
            clock_ms=lambda: 1787659200001,
            wait_timeout_s=0.0,
        )
        signed = _signed_voice_engagement()
        packet = SimpleNamespace(
            topic="viventium.voice.engagement.v1",
            participant=SimpleNamespace(identity="owner"),
            data=json.dumps(signed).encode(),
        )
        segments = [
            {
                "segmentId": "segment_000001",
                "turnId": "turn_000001",
                "revision": 1,
                "isFinal": True,
                "speaker": {
                    "participantIdentity": "owner",
                    "attribution": "verified",
                    "actorTrust": "owner_participant",
                },
            }
        ]

        self.assertTrue(authority.accept_packet(packet))
        self.assertIsNone(asyncio.run(authority.await_turn("turn_000001", segments)))

    def test_gateway_waits_for_model_signed_owner_receipt_after_final_speaker_publication(self) -> None:
        tracker = SpeakerSegmentTracker(
            call_session_id="call_1",
            participant_identity="owner",
            owner_signed=True,
        )
        tracker.ingest(
            transcript="Please launch the requested worker.",
            is_final=True,
            provider_speaker_id="A",
            created_at=1.0,
            start_time=0.0,
            end_time=1.0,
        )
        segments, _ = tracker.finalize_turn("Please launch the requested worker.")
        authority = VoiceEngagementAuthority(
            call_session_id="call_1",
            owner_participant_identity="owner",
            verify_receipt=_verify_synthetic_voice_engagement,
            clock_ms=lambda: 1787659200001,
            wait_timeout_s=0.25,
        )
        receipt = _signed_voice_engagement()

        async def relay_after_publication():
            pending = asyncio.create_task(
                authority.await_turn("turn_000001", segments)
            )
            await asyncio.sleep(0)
            self.assertFalse(pending.done())
            accepted = authority.accept_packet(
                SimpleNamespace(
                    topic="viventium.voice.engagement.v1",
                    participant=SimpleNamespace(identity="owner"),
                    data=json.dumps(receipt).encode(),
                )
            )
            return accepted, await pending

        accepted, delivered = asyncio.run(relay_after_publication())

        self.assertTrue(accepted)
        self.assertEqual(delivered, receipt)

    def test_signed_negative_semantic_verdict_wakes_wing_without_granting_authority(self) -> None:
        tracker = SpeakerSegmentTracker(
            call_session_id="call_1",
            participant_identity="owner",
            owner_signed=True,
        )
        tracker.ingest(
            transcript="A private ambient thought about a blue folder.",
            is_final=True,
            provider_speaker_id="A",
            created_at=1.0,
            start_time=0.0,
            end_time=1.0,
        )
        segments, _ = tracker.finalize_turn(
            "A private ambient thought about a blue folder."
        )
        authority = VoiceEngagementAuthority(
            call_session_id="call_1",
            owner_participant_identity="owner",
            verify_receipt=_verify_synthetic_voice_engagement,
            clock_ms=lambda: 1787659200001,
            wait_timeout_s=0.25,
        )
        receipt = _signed_voice_engagement(directly_addressed=False)

        async def relay_negative_decision():
            pending = asyncio.create_task(
                authority.await_turn("turn_000001", segments)
            )
            await asyncio.sleep(0)
            accepted = authority.accept_packet(
                SimpleNamespace(
                    topic="viventium.voice.engagement.v1",
                    participant=SimpleNamespace(identity="owner"),
                    data=json.dumps(receipt).encode(),
                )
            )
            return accepted, await pending

        accepted, delivered = asyncio.run(relay_negative_decision())

        self.assertTrue(accepted)
        self.assertIsNone(delivered)

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
        followup = SimpleNamespace(cancel_pending=lambda: calls.append(("followup", None)))
        session = SimpleNamespace(interrupt=lambda *, force=False: calls.append(("main", force)))
        backend_task_state = {"state": "cancelling"}

        _apply_task_cancel_suppression(
            "task_1",
            followup_scheduler=followup,
            session=session,
        )

        self.assertEqual(
            calls,
            [("followup", None), ("main", True)],
        )
        self.assertEqual(backend_task_state, {"state": "cancelling"})

    def test_mode_transition_halts_main_and_followup_without_cancelling_task(self) -> None:

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

        ambient = Plane()
        followup = Plane()
        session = Session()
        backend_task_state = {"state": "running"}

        _apply_authoritative_call_mode_to_speech_planes(
            "listen_only",
            ambient_ingress=ambient,
            followup_scheduler=followup,
            session=session,
        )
        _suspend_all_call_speech_until_authoritative(
            followup_scheduler=followup,
            session=session,
        )

        self.assertEqual(ambient.modes, ["listen_only"])
        self.assertEqual(followup.modes, ["listen_only"])
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
            track_publications={"guest": SimpleNamespace(
                sid="TR_guest", source=rtc.TrackSource.SOURCE_MICROPHONE,
                kind=rtc.TrackKind.KIND_AUDIO, subscribed=True,
                track=SimpleNamespace(sid="TR_guest"),
            )},
        )
        owner = SimpleNamespace(
            identity="zzz-owner",
            name="Owner",
            track_publications={"owner": SimpleNamespace(
                sid="TR_owner", source=rtc.TrackSource.SOURCE_MICROPHONE,
                kind=rtc.TrackKind.KIND_AUDIO, subscribed=True,
                track=SimpleNamespace(sid="TR_owner"),
            )},
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
        context = _linked_participant_speaker_context(room, "owner-not-connected")
        self.assertIs(context.get("owner_signed", False), False)
        self.assertEqual(context.get("track_sid", ""), "")
        self.assertNotEqual(context.get("participant_identity"), "guest")
        tracker = SpeakerSegmentTracker(call_session_id="call_1", **context)
        tracker.ingest(
            transcript="Synthetic request", is_final=True, created_at=100.0,
            provider_speaker_id=None, allow_owner_participant_track=True,
        )
        segment = tracker._segments_by_id["segment_000001"]
        self.assertEqual(segment["speaker"]["actorTrust"], "unknown")
        self.assertEqual(segment["speaker"]["source"], "unknown")
        self.assertTrue(segment["uncertain"])

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

    def test_requested_assemblyai_route_uses_the_listeners_own_end_of_turn(self) -> None:
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
        # The recipe follows the route this call was given, not the worker's configured default.
        self.assertIsInstance(build_turn_handling(env.stt_provider)["turn_detection"], inference.TurnDetector)
        self.assertEqual(build_turn_handling(updated.stt_provider)["turn_detection"], "stt")

    def test_current_call_facts_keep_available_semantic_detection_label(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            env = load_env()
        facts = _build_current_call_runtime_context(env, "call-current", turn_detection=object())
        self.assertEqual(facts["turnHandling"]["turnDetection"], "turn_detector")

    def test_requested_local_route_reports_ready_route_and_local_turn_model(self) -> None:
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
        turn_handling = build_turn_handling(updated.stt_provider)
        self.assertIsInstance(turn_handling["turn_detection"], inference.TurnDetector)
        facts = _build_current_call_runtime_context(
            updated, "call-current", turn_detection=turn_handling["turn_detection"],
        )
        self.assertEqual(facts["readyRoute"]["stt"], {"provider": "pywhispercpp", "variant": "tiny.en"})
        self.assertEqual(facts["readyRoute"]["tts"], {"provider": "openai", "variant": "gpt-4o-mini-tts"})
        self.assertEqual(facts["turnHandling"]["turnDetection"], "turn_detector")
        self.assertEqual(
            facts["turnHandling"]["maxEndpointingDelayS"], turn_handling["endpointing"]["max_delay"],
        )
        self.assertNotIn("api_key", json.dumps(facts))

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

        # Hosted routes use the SDK's own 1.8 default (it was 500 on 1.5).
        self.assertEqual(env.voice_job_memory_warn_mb, 1000.0)

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
        # The engine model is always passed (the selectable Listening picker depends on it). Of the
        # provider's end-of-turn settings only the fixed one-second cap is passed (see the recipe).
        env = SimpleNamespace(
            assemblyai_stt_model="universal-streaming-multilingual",
            assemblyai_format_turns=True,
        )

        self.assertEqual(
            _build_assemblyai_stt_kwargs(env),
            {
                "model": "universal-streaming-multilingual",
                "speaker_labels": True,
                "max_turn_silence": 1000,
                "format_turns": True,
            },
        )

    def test_build_stt_selection_passes_assemblyai_engine_speaker_labels_and_fixed_turn_cap(self) -> None:
        env = SimpleNamespace(
            stt_provider="assemblyai",
            assemblyai_stt_model="u3-rt-pro",
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
            max_turn_silence=1000,
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
                self.current_speech = SimpleNamespace(done=lambda: False, interrupted=False)

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

            def note_provisional_interruption(self, *, speech_handle):
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





if __name__ == "__main__":
    unittest.main()


class TestActualTTSMetricsTrace(unittest.TestCase):
    def _attach_actual_callback(self, llm):
        import ast
        from pathlib import Path
        import worker

        tree = ast.parse(Path(worker.__file__).read_text())
        names = {"_record_completed_tts_trace", "_attach_tts_latency_logger"}
        nodes = [node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef) and node.name in names]
        namespace = {
            "llm_impl": llm,
            "attached_tts_metric_sources": set(),
            "logger": MagicMock(),
            "call_session_id": "synthetic-call",
            "_metric_value": lambda metrics, key: getattr(metrics, key, None),
            "_metric_ms": lambda metrics, key: getattr(metrics, key, 0) * 1000,
        }
        module = ast.Module(body=ast.parse("from __future__ import annotations").body + nodes,
                            type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), "actual-worker-tts-metrics", "exec"), namespace)
        callbacks = {}
        tts = SimpleNamespace(on=lambda event, callback: callbacks.setdefault(event, callback))
        namespace["_attach_tts_latency_logger"]("synthetic-provider", tts)
        return callbacks["metrics_collected"], namespace

    def test_actual_metrics_event_retains_the_completion_trace_join(self):
        llm = MagicMock()
        llm.record_next_trace_hop.return_value = "synthetic-trace"
        callback, namespace = self._attach_actual_callback(llm)
        callback(SimpleNamespace(type="tts_metrics", timestamp=10.0, duration=2.0,
                                 ttfb=0.25, cancelled=False))
        llm.record_next_trace_hop.assert_called_once_with("tts_first_byte", 8250.0)
        llm.record_completed_trace_stage.assert_called_once_with("synthetic-trace", "tts.completed")
        self.assertEqual(namespace["logger"].info.call_args.args[2], "synthetic-trace")

    def test_cancelled_metrics_do_not_confirm_completion(self):
        llm = MagicMock()
        llm.record_next_trace_hop.return_value = "synthetic-trace"
        callback, _ = self._attach_actual_callback(llm)
        callback(SimpleNamespace(type="tts_metrics", timestamp=10.0, duration=2.0,
                                 ttfb=0.25, cancelled=True))
        llm.record_completed_trace_stage.assert_not_called()

    def test_missing_metrics_identity_stays_unmatched(self):
        llm = MagicMock()
        callback, namespace = self._attach_actual_callback(llm)
        callback(SimpleNamespace(type="tts_metrics", duration=2.0, ttfb=0.25, cancelled=False))
        llm.record_next_trace_hop.assert_not_called()
        llm.record_completed_trace_stage.assert_not_called()
        self.assertEqual(namespace["logger"].info.call_args.args[2], "unmatched")

class TestNativePublicPartFlush(unittest.TestCase):
    def _marker(self, part='run-a:1'):
        return {'version': 1, 'complete': True, 'request_id': 'request-a', 'run_id': 'run-a',
                'part_id': part, 'message_id': 'message-a', 'stream_id': 'stream-a'}

    async def _node(self, chunks):
        from livekit.agents.llm import ChatChunk
        from livekit.agents.types import FlushSentinel
        from worker import Agent
        async def source(*args):
            for chunk in chunks: yield chunk
        agent = ViventiumVoiceAgent(instructions='Synthetic')
        with patch.object(Agent.default, 'llm_node', source):
            return [chunk async for chunk in agent.llm_node(None, [], None)]

    def test_native_flush_after_exact_content_then_later_words_without_control_metadata(self):
        from livekit.agents.llm import ChatChunk, ChoiceDelta
        from livekit.agents.types import FlushSentinel
        def c(text=None, marker=None):
            return ChatChunk(id='stream-a', delta=ChoiceDelta(content=text, extra={'viventium_public_part_complete': marker} if marker else {}))
        text = '<emphasis>First complete part.</emphasis>'
        chunks = asyncio.run(self._node([c(text), c(marker=self._marker()), c(marker=self._marker()),
                                         c(' Later long part.'), c(marker=self._marker('run-a:2'))]))
        self.assertEqual([str(type(c).__name__) for c in chunks], ['ChatChunk', 'FlushSentinel', 'ChatChunk', 'FlushSentinel'])
        self.assertEqual(''.join(c.delta.content or '' for c in chunks if isinstance(c, ChatChunk)), text+' Later long part.')
        self.assertTrue(all(not c.delta.extra for c in chunks if isinstance(c, ChatChunk)))

    def test_native_question_flushes_unterminated_text_while_provider_is_paused(self):
        from livekit.agents.llm import ChatChunk, ChoiceDelta
        from livekit.agents.types import FlushSentinel
        from worker import Agent
        async def run():
            reached=asyncio.Event();release=asyncio.Event()
            async def source(*args):
                yield ChatChunk(id='main',delta=ChoiceDelta(content='Choose size'))
                yield ChatChunk(id='main',delta=ChoiceDelta(extra={'viventium_native_input_offer':{'version':1,'requestKey':'a'*64,'streamId':'main'}}))
                reached.set();await release.wait()
                yield ChatChunk(id='main',delta=ChoiceDelta(content='Later actual answer.'))
            agent=ViventiumVoiceAgent(instructions='Synthetic');chunks=[]
            with patch.object(Agent.default,'llm_node',source):
                stream=agent.llm_node(None,[],None)
                chunks.append(await anext(stream));chunks.append(await anext(stream))
                self.assertIsInstance(chunks[1],FlushSentinel)
                self.assertEqual(chunks[0].delta.content,'Choose size')
                self.assertFalse(chunks[0].delta.extra)
                release.set();chunks.extend([chunk async for chunk in stream])
            self.assertEqual(chunks[2].delta.content,'Later actual answer.')
        asyncio.run(run())

    def test_no_content_or_untyped_extra_never_invents_flush(self):
        from livekit.agents.llm import ChatChunk, ChoiceDelta
        from livekit.agents.types import FlushSentinel
        inputs = [ChatChunk(id='a', delta=ChoiceDelta(extra={'viventium_public_part_complete': self._marker()})),
                  ChatChunk(id='a', delta=ChoiceDelta(content='Public.', extra={'other': True})),
                  ChatChunk(id='a', delta=ChoiceDelta(extra={'viventium_public_part_complete': {'complete': True}}))]
        chunks = asyncio.run(self._node(inputs))
        self.assertFalse(any(isinstance(c, FlushSentinel) for c in chunks))
        self.assertEqual(''.join(c.delta.content or '' for c in chunks), 'Public.')
        self.assertEqual(chunks[0].delta.extra, {'other': True})

    def test_actual_sdk_serializes_fresh_tts_nodes_and_drains_word_tag_buffers(self):
        # LiveKit 1.8.11 splits a reply on FlushSentinel in the reply pipeline itself
        # (AgentActivity._pipeline_reply_task), not inside perform_tts_inference as 1.5.10 did.
        # So this runs the real AgentSession pipeline: backend chunks -> our llm_node (public-part
        # marker -> FlushSentinel) -> SDK segmenting -> a fresh tts_node per public part.
        from livekit.agents import AgentSession, llm as lk_llm
        from livekit.agents.llm import ChatChunk, ChoiceDelta
        from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS
        from worker import Agent
        first = '<emphasis>First complete part.</emphasis>'
        later = '<soft>' + ('Many words with intact punctuation. ' * 60) + 'Last word.</soft>'
        marker = self._marker

        def chunk(text=None, part=None):
            return ChatChunk(id='stream-a', delta=ChoiceDelta(
                role='assistant', content=text,
                extra={'viventium_public_part_complete': marker(part)} if part else {}))

        async def run():
            backend_paused = asyncio.Event(); backend_release = asyncio.Event()
            first_part_drained = asyncio.Event(); gate = asyncio.Event()
            events = []; segments = []

            class BackendStream(lk_llm.LLMStream):
                async def _run(self):
                    self._event_ch.send_nowait(chunk(first[:17]))
                    self._event_ch.send_nowait(chunk(first[17:]))
                    self._event_ch.send_nowait(chunk(part='run-a:1'))
                    backend_paused.set()
                    await backend_release.wait()
                    self._event_ch.send_nowait(chunk(later))
                    self._event_ch.send_nowait(chunk(part='run-a:2'))

            class Backend(lk_llm.LLM):
                _voice_native_streaming = True
                _voice_accepts_inline_controls = True
                def chat(self, *, chat_ctx, tools=None, conn_options=DEFAULT_API_CONNECT_OPTIONS, **kwargs):
                    return BackendStream(self, chat_ctx=chat_ctx, tools=tools or [], conn_options=conn_options)

            async def native_node(agent, text, settings):
                index = len(segments); segments.append(''); events.append(('start', index))
                async for piece in text: segments[index] += piece
                if index == 0:
                    first_part_drained.set()
                    await gate.wait()
                if segments[index]:
                    yield rtc.AudioFrame(data=b'\0\0'*240, sample_rate=24000, num_channels=1, samples_per_channel=240)
                events.append(('done', index))

            backend = Backend()
            session = AgentSession(llm=backend, vad=None, stt=None, tts=None, tts_text_transforms=['filter_emoji'],
                                   turn_handling={'turn_detection': 'manual', 'preemptive_generation': {'enabled': False}})
            speaker = _real_sdk_speaker()
            session.output.audio = speaker
            agent = ViventiumVoiceAgent(instructions='Synthetic', llm=backend)
            with patch.object(Agent.default, 'tts_node', native_node):
                await session.start(agent=agent)
                try:
                    handle = session.generate_reply(user_input='Synthetic request.')
                    # The first public part is complete and drained into its own TTS input
                    # while the backend is still paused before the rest of the reply.
                    await asyncio.wait_for(asyncio.gather(backend_paused.wait(), first_part_drained.wait()), 5)
                    drained_while_backend_paused = list(segments)
                    backend_release.set()
                    for _ in range(20): await asyncio.sleep(0.01)
                    started_while_first_part_renders = list(events)
                    gate.set()
                    await asyncio.wait_for(handle, 5)
                finally:
                    await session.aclose()
            return drained_while_backend_paused, started_while_first_part_renders, segments, events, speaker.frames
        drained, started, segments, events, frames = asyncio.run(run())
        self.assertEqual(drained, [first])
        self.assertEqual(started, [('start', 0)])
        self.assertEqual(segments, [first, later])
        self.assertLess(events.index(('done', 0)), events.index(('start', 1)))
        self.assertEqual(len(frames), 2)

    def test_cancellation_closes_native_input_and_does_not_start_later_segment(self):
        from livekit.agents.types import FlushSentinel
        from livekit.agents.voice.generation import perform_tts_inference
        async def run():
            entered = asyncio.Event(); closed = []; starts = []
            async def source():
                try:
                    yield 'First complete.'; yield FlushSentinel(); yield 'Forbidden later.'
                finally: closed.append('source')
            async def node(text, settings):
                starts.append(len(starts))
                try:
                    async for _ in text: pass
                    entered.set(); await asyncio.Event().wait()
                    yield None
                finally: closed.append('node')
            task, data = perform_tts_inference(node=node, input=source(), model_settings=None, text_transforms=None)
            await entered.wait(); task.cancel()
            with self.assertRaises(asyncio.CancelledError): await task
            return starts, closed
        starts, closed = asyncio.run(run())
        self.assertEqual(starts, [0]); self.assertIn('node', closed); self.assertIn('source', closed)


class TestNativeStartedPresentationProjection(unittest.TestCase):
    def test_native_started_callback_is_synchronous_exact_handle_and_ignores_other_states(self):
        import inspect
        from unittest.mock import Mock, patch
        from types import SimpleNamespace
        from worker import _register_presentation_lifecycle_handlers
        class Session:
            def __init__(self):
                self.handlers = {}
                self.current_speech = object()
            def on(self, name):
                def register(handler):
                    self.handlers[name] = handler
                    return handler
                return register
        session = Session()
        llm = SimpleNamespace(record_speech_started=Mock(), register_speech_handle=Mock(),
                              note_provisional_interruption=Mock())
        _register_presentation_lifecycle_handlers(session, llm)
        callback = session.handlers["agent_state_changed"]
        self.assertFalse(inspect.iscoroutinefunction(callback))
        with patch("librechat_llm.aiohttp.ClientSession") as no_network:
            callback(SimpleNamespace(new_state="speaking", created_at=2.5))
            callback(SimpleNamespace(new_state="listening", created_at=3.0))
        no_network.assert_not_called()
        llm.record_speech_started.assert_called_once_with(session.current_speech, 2500.0)


class TestFalseInterruptionPresentationConsumer(unittest.TestCase):
    def test_actual_false_interruption_event_keeps_handle_identity_and_resume_outcome(self):
        from unittest.mock import Mock, call
        class Session:
            def __init__(self):
                self.handlers = {}
                self.current_speech = object()
            def on(self, name):
                def register(handler):
                    self.handlers[name] = handler
                    return handler
                return register
        session = Session()
        llm = SimpleNamespace(resolve_false_interruption=Mock())
        _register_presentation_lifecycle_handlers(session, llm)
        callback = session.handlers["agent_false_interruption"]
        callback(SimpleNamespace(resumed=True))
        callback(SimpleNamespace(resumed=False))
        self.assertEqual(llm.resolve_false_interruption.call_args_list, [
            call(session.current_speech, resumed=True),
            call(session.current_speech, resumed=False),
        ])
