import os
import sys
import unittest
import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from speaker_segments import SpeakerSegmentTracker, shared_microphone_state_applies_to_track
from worker import (
    AuthoritativeCallModeState,
    VoiceRouteError,
    _abandon_voice_session_claim,
    _apply_requested_voice_route,
    _classify_runtime_voice_provider_failure,
    _claim_voice_session,
    _establish_voice_response_plane,
    _mark_voice_session_ready,
    _parse_dispatch_claim_id,
    _report_voice_gateway_failure,
    _report_voice_gateway_initialization_failure_and_abandon,
    _report_voice_initialization_failure_and_abandon,
    _resolve_canonical_owner_participant,
    _validate_dispatch_job_bindings,
    _validate_voice_session_claim,
    build_stt_selection,
    load_env,
)
from librechat_llm import LibreChatAuth


def _capability(provider, modality, *, available=True, is_local=False, variants=()):
    return {
        "id": provider,
        "modality": modality,
        "available": available,
        "isLocal": is_local,
        "variants": [{"id": variant} for variant in variants],
    }


def _claim(**overrides):
    payload = {
        "status": "claimed",
        "callSessionId": "call-1",
        "roomName": "room-1",
        "gatewayAgentName": "voice-gateway",
        "ownerParticipantIdentity": "owner-1",
        "requestedVoiceRoute": {
            "stt": {"provider": "pywhispercpp", "variant": "tiny.en"},
            "tts": {
                "provider": "local_chatterbox_turbo_mlx_8bit",
                "variant": "local-model",
            },
        },
        "callState": {
            "version": 1,
            "callSessionId": "call-1",
            "mode": "call",
            "status": "listening",
            "revision": 1,
            "updatedAt": "2026-08-09T20:37:04.000Z",
        },
        "speakerSessionState": None,
    }
    payload.update(overrides)
    return payload


class VoiceClaimBoundaryTests(unittest.TestCase):
    def test_dispatch_claim_id_is_structural_and_bounded(self):
        self.assertEqual(
            _parse_dispatch_claim_id('{"callSessionId":"call-1","dispatchClaimId":"claim-1"}'),
            "claim-1",
        )
        self.assertIsNone(_parse_dispatch_claim_id('{"callSessionId":"call-1"}'))
        self.assertIsNone(_parse_dispatch_claim_id("not-json"))

    def test_task_stream_auth_rejection_never_calls_backend_ready(self):
        operations = []

        class TaskStream:
            def start_call_task_event_stream(self):
                operations.append("stream_start")
                return object()

            async def wait_call_task_event_stream_ready(self, *, timeout_s):
                operations.append(("stream_wait", timeout_s))
                return False

            async def stop_call_task_event_stream(self):
                operations.append("stream_stop")

        async def mark_ready():
            operations.append("backend_ready")
            return _claim()["callState"]

        task, ready = asyncio.run(
            _establish_voice_response_plane(
                llm_impl=TaskStream(),
                mark_ready=mark_ready,
                timeout_s=1.5,
            )
        )

        self.assertIsNone(task)
        self.assertIsNone(ready)
        self.assertEqual(
            operations,
            ["stream_start", ("stream_wait", 1.5), "stream_stop"],
        )

    def test_task_stream_handshake_precedes_backend_ready(self):
        operations = []
        stream_task = object()

        class TaskStream:
            def start_call_task_event_stream(self):
                operations.append("stream_start")
                return stream_task

            async def wait_call_task_event_stream_ready(self, *, timeout_s):
                operations.append(("stream_wait", timeout_s))
                return True

            async def stop_call_task_event_stream(self):
                operations.append("stream_stop")

        async def mark_ready():
            operations.append("backend_ready")
            return _claim()["callState"]

        task, ready = asyncio.run(
            _establish_voice_response_plane(
                llm_impl=TaskStream(),
                mark_ready=mark_ready,
                timeout_s=1.5,
            )
        )

        self.assertIs(task, stream_task)
        self.assertEqual(ready["status"], "listening")
        self.assertEqual(
            operations,
            ["stream_start", ("stream_wait", 1.5), "backend_ready"],
        )

    def test_failed_call_can_be_reclaimed_then_only_ready_clears_tombstone(self):
        def claim_for_state(*, failed, revision):
            return _claim(
                callState={
                    "version": 1,
                    "callSessionId": "call-1",
                    "mode": "wing",
                    "status": "failed" if failed else "listening",
                    "revision": revision,
                    "updatedAt": "2026-08-09T20:37:04.000Z",
                }
            )

        class Response:
            def __init__(self, status, payload):
                self.status = status
                self.payload = payload

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def json(self):
                return self.payload

            async def read(self):
                return b""

        class RecoverySession:
            active_job = None
            failed = False
            revision = 6
            calls = []

            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            def post(self, url, *, headers, json=None):
                type(self).calls.append((url, dict(headers), json))
                job_id = headers.get("X-VIVENTIUM-JOB-ID")
                worker_id = headers.get("X-VIVENTIUM-WORKER-ID")
                if url.endswith("/failure"):
                    type(self).failed = True
                    type(self).revision = 7
                    return Response(
                        200,
                        {
                            "version": 1,
                            "callSessionId": "call-1",
                            "status": "failed",
                            "error": {"code": "provider_failure"},
                        },
                    )
                if url.endswith("/claim/abandon"):
                    released = self.active_job == (job_id, worker_id)
                    if released:
                        type(self).active_job = None
                    return Response(200, {"version": 1, "released": released})
                if url.endswith("/ready"):
                    if self.active_job != (job_id, worker_id):
                        return Response(409, {"code": "auth_expired"})
                    type(self).failed = False
                    type(self).revision = 9
                    return Response(
                        200,
                        {
                            "version": 1,
                            "callSessionId": "call-1",
                            "mode": "wing",
                            "status": "listening",
                            "revision": 9,
                            "updatedAt": "2026-08-09T20:37:09.000Z",
                        },
                    )
                if self.active_job not in {None, (job_id, worker_id)}:
                    return Response(409, {"code": "auth_expired"})
                type(self).active_job = (job_id, worker_id)
                return Response(
                    200,
                    claim_for_state(
                        failed=type(self).failed,
                        revision=type(self).revision,
                    ),
                )

        first_auth = LibreChatAuth(
            call_session_id="call-1",
            call_secret="secret",
            job_id="job-1",
            worker_id="worker-1",
        )
        retry_auth = LibreChatAuth(
            call_session_id="call-1",
            call_secret="secret",
            job_id="job-2",
            worker_id="worker-2",
        )

        async def run():
            first = await _claim_voice_session(
                "http://backend",
                first_auth,
                expected_room_name="room-1",
                expected_gateway_agent_name="voice-gateway",
                expected_owner_participant_identity=None,
                dispatch_claim_id="dispatch-claim-1",
            )
            await _report_voice_gateway_failure(
                "http://backend",
                first_auth,
                classification="provider_failure",
                modality="stt",
                provider="assemblyai",
                phase="initialization",
                fatal=True,
            )
            await _abandon_voice_session_claim(
                "http://backend", first_auth, reason="gateway_initialization_failed"
            )
            reclaimed = await _claim_voice_session(
                "http://backend",
                retry_auth,
                expected_room_name="room-1",
                expected_gateway_agent_name="voice-gateway",
                expected_owner_participant_identity=None,
                dispatch_claim_id="dispatch-claim-2",
            )
            ready = await _mark_voice_session_ready("http://backend", retry_auth)
            return first, reclaimed, ready

        with patch("worker.aiohttp.ClientSession", RecoverySession):
            first, reclaimed, ready = asyncio.run(run())

        self.assertEqual(first["callState"]["status"], "listening")
        self.assertEqual(reclaimed["callState"]["status"], "failed")
        startup_gate = AuthoritativeCallModeState()
        self.assertFalse(startup_gate.allows_agent_dispatch)
        startup_gate.apply(ready["mode"])
        self.assertTrue(startup_gate.allows_agent_dispatch)
        self.assertEqual(ready["status"], "listening")
        ready_url, ready_headers, ready_body = next(
            call for call in RecoverySession.calls if call[0].endswith("/ready")
        )
        self.assertEqual(
            ready_url,
            "http://backend/api/viventium/voice/call-sessions/call-1/ready",
        )
        self.assertEqual(ready_headers["X-VIVENTIUM-JOB-ID"], "job-2")
        self.assertEqual(ready_headers["X-VIVENTIUM-WORKER-ID"], "worker-2")
        self.assertEqual(ready_body, {"version": 1})
        claim_headers = [
            headers for url, headers, _body in RecoverySession.calls if url.endswith("/claim")
        ]
        self.assertEqual(
            [headers.get("X-VIVENTIUM-DISPATCH-CLAIM") for headers in claim_headers],
            ["dispatch-claim-1", "dispatch-claim-2"],
        )

    def test_wrong_or_non_listening_ready_response_fails_closed(self):
        class Response:
            def __init__(self, status, payload):
                self.status = status
                self.payload = payload

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def json(self):
                return self.payload

            async def read(self):
                return b""

        class ReadySession:
            response = Response(409, {"code": "auth_expired"})

            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            def post(self, _url, *, headers, json=None):
                return type(self).response

        auth = LibreChatAuth(
            call_session_id="call-1",
            call_secret="secret",
            job_id="job-2",
            worker_id="worker-2",
        )
        gate = AuthoritativeCallModeState()
        with patch("worker.aiohttp.ClientSession", ReadySession):
            rejected = asyncio.run(_mark_voice_session_ready("http://backend", auth))
            ReadySession.response = Response(
                200,
                {
                    "version": 1,
                    "callSessionId": "call-1",
                    "mode": "call",
                    "status": "failed",
                    "revision": 10,
                    "updatedAt": "2026-08-09T20:37:10.000Z",
                },
            )
            malformed = asyncio.run(_mark_voice_session_ready("http://backend", auth))
        self.assertIsNone(rejected)
        self.assertIsNone(malformed)
        self.assertFalse(gate.allows_agent_dispatch)

    def test_claim_without_worker_identity_fails_before_http(self):
        class ForbiddenSession:
            constructed = False

            def __init__(self, **_kwargs):
                type(self).constructed = True

            async def __aenter__(self):
                raise AssertionError("claim HTTP must not run without worker authority")

            async def __aexit__(self, *_args):
                return False

        auth = LibreChatAuth(
            call_session_id="call-1",
            call_secret="secret",
            job_id="job-1",
            worker_id="",
        )
        with patch("worker.aiohttp.ClientSession", ForbiddenSession):
            result = asyncio.run(
                _claim_voice_session(
                    "http://backend",
                    auth,
                    expected_room_name="room-1",
                    expected_gateway_agent_name="voice-gateway",
                    expected_owner_participant_identity=None,
                )
            )
        self.assertIsNone(result)
        self.assertFalse(ForbiddenSession.constructed)

    def test_fatal_provider_failure_is_reported_before_claim_abandon(self):
        claim_payload = _claim()

        class Response:
            def __init__(self, status, payload):
                self.status = status
                self.payload = payload

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def json(self):
                return self.payload

            async def read(self):
                return b""

        class FailureServerSession:
            calls = []

            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            def post(self, url, *, headers, json=None):
                type(self).calls.append((url, dict(headers), json))
                if url.endswith("/failure"):
                    return Response(
                        200,
                        {
                            "version": 1,
                            "callSessionId": "call-1",
                            "status": "failed",
                            "error": {
                                "code": "provider_failure",
                                "message": "The configured voice provider is unavailable.",
                                "retryable": True,
                            },
                        },
                    )
                if url.endswith("/claim/abandon"):
                    return Response(200, {"version": 1, "released": True})
                return Response(200, claim_payload)

        async def run():
            auth = LibreChatAuth(
                call_session_id="call-1",
                call_secret="secret",
                job_id="job-1",
                worker_id="worker-1",
            )
            reported, released = await _report_voice_initialization_failure_and_abandon(
                "http://backend",
                auth,
                VoiceRouteError(
                    "provider_failure",
                    modality="stt",
                    provider="assemblyai",
                    reason="initialization failed",
                ),
            )
            return reported, released

        with patch("worker.aiohttp.ClientSession", FailureServerSession):
            reported, released = asyncio.run(run())

        self.assertEqual(reported["status"], "failed")
        self.assertTrue(released)
        self.assertTrue(FailureServerSession.calls[0][0].endswith("/failure"))
        self.assertTrue(FailureServerSession.calls[1][0].endswith("/claim/abandon"))
        failure_url, failure_headers, failure_body = FailureServerSession.calls[0]
        self.assertEqual(
            failure_url,
            "http://backend/api/viventium/voice/call-sessions/call-1/failure",
        )
        self.assertEqual(failure_headers["X-VIVENTIUM-JOB-ID"], "job-1")
        self.assertEqual(failure_headers["X-VIVENTIUM-WORKER-ID"], "worker-1")
        self.assertEqual(
            failure_body,
            {
                "version": 1,
                "classification": "provider_failure",
                "phase": "initialization",
                "fatal": True,
                "modality": "stt",
                "provider": "assemblyai",
            },
        )
        self.assertNotIn("message", failure_body)

    def test_runtime_provider_error_is_structurally_classified_without_mic_copy(self):
        stt_impl = object()
        tts_impl = object()
        self.assertEqual(
            _classify_runtime_voice_provider_failure(
                SimpleNamespace(source=stt_impl),
                stt_impl=stt_impl,
                tts_impl=tts_impl,
                stt_provider="assemblyai",
                tts_provider="elevenlabs",
            ),
            ("stt", "assemblyai"),
        )
        self.assertEqual(
            _classify_runtime_voice_provider_failure(
                SimpleNamespace(source=tts_impl),
                stt_impl=stt_impl,
                tts_impl=tts_impl,
                stt_provider="assemblyai",
                tts_provider="elevenlabs",
            ),
            ("tts", "elevenlabs"),
        )
        self.assertIsNone(
            _classify_runtime_voice_provider_failure(
                SimpleNamespace(source=object()),
                stt_impl=stt_impl,
                tts_impl=tts_impl,
                stt_provider="assemblyai",
                tts_provider="elevenlabs",
            )
        )

    def test_gateway_initialization_failure_reports_before_releasing_lease(self):
        class Response:
            def __init__(self, payload):
                self.status = 200
                self.payload = payload

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def json(self):
                return self.payload

        class GatewayFailureSession:
            calls = []

            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            def post(self, url, *, headers, json=None):
                type(self).calls.append((url, json))
                if url.endswith("/failure"):
                    return Response(
                        {
                            "version": 1,
                            "callSessionId": "call-1",
                            "status": "failed",
                            "error": {"code": "gateway_down"},
                        }
                    )
                return Response({"version": 1, "released": True})

        auth = LibreChatAuth(
            call_session_id="call-1",
            call_secret="secret",
            job_id="job-1",
            worker_id="worker-1",
        )
        with patch("worker.aiohttp.ClientSession", GatewayFailureSession):
            reported, released = asyncio.run(
                _report_voice_gateway_initialization_failure_and_abandon(
                    "http://backend", auth
                )
            )
        self.assertEqual(reported["status"], "failed")
        self.assertTrue(released)
        self.assertEqual(
            [url.rsplit("/", 1)[-1] for url, _body in GatewayFailureSession.calls],
            ["failure", "abandon"],
        )
        self.assertEqual(
            GatewayFailureSession.calls[0][1],
            {
                "version": 1,
                "classification": "gateway_down",
                "phase": "initialization",
                "fatal": True,
            },
        )

    def test_owner_timeout_abandons_matching_lease_and_allows_immediate_retry(self):
        claim_payload = _claim()

        class Response:
            def __init__(self, status, payload):
                self.status = status
                self.payload = payload

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def json(self):
                return self.payload

            async def read(self):
                return b""

        class LeaseServerSession:
            active_job_id = None
            calls = []

            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            def post(self, url, *, headers, json=None):
                self.calls.append((url, dict(headers), json))
                job_id = headers.get("X-VIVENTIUM-JOB-ID")
                if url.endswith("/claim/abandon"):
                    released = self.active_job_id == job_id
                    if released:
                        type(self).active_job_id = None
                    return Response(200, {"version": 1, "released": released})
                if self.active_job_id not in {None, job_id}:
                    return Response(409, {"code": "auth_expired"})
                type(self).active_job_id = job_id
                return Response(200, claim_payload)

        async def run():
            first_auth = LibreChatAuth(
                call_session_id="call-1",
                call_secret="secret",
                job_id="job-1",
                worker_id="worker-1",
            )
            retry_auth = LibreChatAuth(
                call_session_id="call-1",
                call_secret="secret",
                job_id="job-2",
                worker_id="worker-2",
            )
            first = await _claim_voice_session(
                "http://backend",
                first_auth,
                expected_room_name="room-1",
                expected_gateway_agent_name="voice-gateway",
                expected_owner_participant_identity=None,
            )
            blocked = await _claim_voice_session(
                "http://backend",
                retry_auth,
                expected_room_name="room-1",
                expected_gateway_agent_name="voice-gateway",
                expected_owner_participant_identity=None,
            )
            released = await _abandon_voice_session_claim(
                "http://backend", first_auth, reason="owner_timeout"
            )
            retry = await _claim_voice_session(
                "http://backend",
                retry_auth,
                expected_room_name="room-1",
                expected_gateway_agent_name="voice-gateway",
                expected_owner_participant_identity=None,
            )
            return first, blocked, released, retry

        with patch("worker.aiohttp.ClientSession", LeaseServerSession):
            first, blocked, released, retry = asyncio.run(run())

        self.assertEqual(first["ownerParticipantIdentity"], "owner-1")
        self.assertIsNone(blocked)
        self.assertTrue(released)
        self.assertEqual(retry["ownerParticipantIdentity"], "owner-1")
        abandon_url, abandon_headers, abandon_body = next(
            call for call in LeaseServerSession.calls if call[0].endswith("/claim/abandon")
        )
        self.assertEqual(abandon_url, "http://backend/api/viventium/voice/claim/abandon")
        self.assertEqual(abandon_headers["X-VIVENTIUM-JOB-ID"], "job-1")
        self.assertEqual(abandon_headers["X-VIVENTIUM-WORKER-ID"], "worker-1")
        self.assertEqual(abandon_body, {"reason": "owner_timeout"})

    def test_dispatch_job_agent_mismatch_fails_before_claim_or_connect(self):
        job = SimpleNamespace(
            room=SimpleNamespace(name="room-1"),
            agent_name="forged-agent",
            participant=None,
        )
        with self.assertRaisesRegex(RuntimeError, "dispatch agent mismatch"):
            _validate_dispatch_job_bindings(
                job,
                fallback_room_name="",
                call_session_id="call-1",
                registered_agent_name="voice-gateway",
            )

    def test_room_level_dispatch_bindings_allow_absent_optional_participant(self):
        job = SimpleNamespace(
            room=SimpleNamespace(name="room-1"),
            agent_name="voice-gateway",
            participant=None,
        )
        self.assertEqual(
            _validate_dispatch_job_bindings(
                job,
                fallback_room_name="",
                call_session_id="call-1",
                registered_agent_name="voice-gateway",
            ),
            ("room-1", None),
        )

    def test_room_dispatch_without_publisher_accepts_only_backend_canonical_owner(self):
        validated = _validate_voice_session_claim(
            _claim(),
            expected_call_session_id="call-1",
            expected_room_name="room-1",
            expected_gateway_agent_name="voice-gateway",
            expected_owner_participant_identity=None,
        )
        self.assertEqual(validated["ownerParticipantIdentity"], "owner-1")

    def test_room_dispatch_connects_then_waits_for_exact_canonical_owner_before_providers(self):
        events = []
        owner = SimpleNamespace(identity="owner-1")

        class Context:
            async def connect(self, *, auto_subscribe):
                events.append(("connect", auto_subscribe))

            async def wait_for_participant(self, *, identity):
                events.append(("wait", identity))
                return owner

        async def run():
            participant = await _resolve_canonical_owner_participant(
                Context(), "owner-1", timeout_s=0.1
            )
            events.append(("provider_construct", participant.identity))
            return participant

        participant = asyncio.run(run())
        self.assertIs(participant, owner)
        self.assertEqual(events[0][0], "connect")
        self.assertEqual(events[1], ("wait", "owner-1"))
        self.assertEqual(events[2], ("provider_construct", "owner-1"))

    def test_room_dispatch_mismatched_participant_fails_before_provider_construction(self):
        events = []

        class Context:
            async def connect(self, *, auto_subscribe):
                events.append("connect")

            async def wait_for_participant(self, *, identity):
                events.append(("wait", identity))
                return SimpleNamespace(identity="guest-1")

        async def run():
            participant = await _resolve_canonical_owner_participant(
                Context(), "owner-1", timeout_s=0.1
            )
            events.append("provider_construct")
            return participant

        with self.assertRaisesRegex(RuntimeError, "canonical owner mismatch"):
            asyncio.run(run())
        self.assertNotIn("provider_construct", events)

    def test_room_dispatch_owner_timeout_fails_before_provider_construction(self):
        events = []

        class Context:
            async def connect(self, *, auto_subscribe):
                events.append("connect")

            async def wait_for_participant(self, *, identity):
                events.append(("wait", identity))
                await asyncio.Event().wait()

        async def run():
            await _resolve_canonical_owner_participant(
                Context(), "owner-1", timeout_s=0.01
            )
            events.append("provider_construct")

        with self.assertRaisesRegex(RuntimeError, "canonical owner unavailable"):
            asyncio.run(run())
        self.assertNotIn("provider_construct", events)

    def test_claim_requires_exact_server_bound_call_room_agent_and_owner(self):
        validated = _validate_voice_session_claim(
            _claim(),
            expected_call_session_id="call-1",
            expected_room_name="room-1",
            expected_gateway_agent_name="voice-gateway",
            expected_owner_participant_identity="owner-1",
        )

        self.assertEqual(validated["ownerParticipantIdentity"], "owner-1")
        self.assertEqual(
            validated["requestedVoiceRoute"]["tts"]["provider"],
            "local_chatterbox_turbo_mlx_8bit",
        )

    def test_claim_rejects_forged_or_stale_dispatch_bindings(self):
        cases = (
            ("callSessionId", "stale-call"),
            ("roomName", "forged-room"),
            ("gatewayAgentName", "other-agent"),
            ("ownerParticipantIdentity", "guest-sorts-before-owner"),
        )
        for field, expected in cases:
            kwargs = {
                "expected_call_session_id": "call-1",
                "expected_room_name": "room-1",
                "expected_gateway_agent_name": "voice-gateway",
                "expected_owner_participant_identity": "owner-1",
            }
            expected_arg = {
                "callSessionId": "expected_call_session_id",
                "roomName": "expected_room_name",
                "gatewayAgentName": "expected_gateway_agent_name",
                "ownerParticipantIdentity": "expected_owner_participant_identity",
            }[field]
            kwargs[expected_arg] = expected
            with self.subTest(field=field), self.assertRaisesRegex(
                RuntimeError, "canonical voice claim mismatch"
            ):
                _validate_voice_session_claim(_claim(), **kwargs)

    def test_claim_rejects_missing_canonical_field_or_route(self):
        expected = {
            "expected_call_session_id": "call-1",
            "expected_room_name": "room-1",
            "expected_gateway_agent_name": "voice-gateway",
            "expected_owner_participant_identity": "owner-1",
        }
        for field in (
            "callSessionId",
            "roomName",
            "gatewayAgentName",
            "ownerParticipantIdentity",
            "requestedVoiceRoute",
            "callState",
        ):
            payload = _claim()
            payload.pop(field)
            with self.subTest(field=field), self.assertRaisesRegex(
                RuntimeError, "invalid canonical voice claim"
            ):
                _validate_voice_session_claim(payload, **expected)

    def test_claim_call_state_is_authoritative_over_stale_dispatch_mode(self):
        validated = _validate_voice_session_claim(
            _claim(
                callState={
                    "version": 1,
                    "callSessionId": "call-1",
                    "mode": "listen_only",
                    "status": "listening",
                    "revision": 9,
                    "updatedAt": "2026-08-09T20:37:04.000Z",
                }
            ),
            expected_call_session_id="call-1",
            expected_room_name="room-1",
            expected_gateway_agent_name="voice-gateway",
            expected_owner_participant_identity=None,
        )
        stale_dispatch_metadata = {"mode": "call", "listenOnlyModeEnabled": False}
        self.assertEqual(validated["callState"]["mode"], "listen_only")
        self.assertEqual(stale_dispatch_metadata["mode"], "call")

    def test_claim_rejects_malformed_or_unbounded_shared_track_state(self):
        expected = {
            "expected_call_session_id": "call-1",
            "expected_room_name": "room-1",
            "expected_gateway_agent_name": "voice-gateway",
            "expected_owner_participant_identity": "owner-1",
        }
        for shared_track_sids in ("TR_guest", [""], [f"TR_{index}" for index in range(65)]):
            payload = _claim(
                speakerSessionState={
                    "version": 1,
                    "callSessionId": "call-1",
                    "revision": 1,
                    "attributionState": "shared_mic_unverified",
                    "detectedAt": "2026-08-09T12:00:00.000Z",
                    "sharedTrackSids": shared_track_sids,
                }
            )
            with self.subTest(shared_track_sids=shared_track_sids), self.assertRaisesRegex(
                RuntimeError, "invalid canonical voice claim"
            ):
                _validate_voice_session_claim(payload, **expected)

    def test_reconnect_shared_mic_tombstone_prevents_owner_verification(self):
        claim = _claim(
            speakerSessionState={
                "version": 1,
                "callSessionId": "call-1",
                "revision": 4,
                "attributionState": "shared_mic_unverified",
                "detectedAt": "2026-08-09T12:00:00.000Z",
                "sourceTrackSid": "track-owner",
            }
        )
        validated = _validate_voice_session_claim(
            claim,
            expected_call_session_id="call-1",
            expected_room_name="room-1",
            expected_gateway_agent_name="voice-gateway",
            expected_owner_participant_identity="owner-1",
        )
        tracker = SpeakerSegmentTracker(
            call_session_id="call-1",
            participant_identity="owner-1",
            participant_name="Owner",
            track_sid="track-owner",
            owner_signed=True,
            initial_shared_microphone=(
                validated["speakerSessionState"]["attributionState"]
                == "shared_mic_unverified"
            ),
        )

        [segment] = tracker.ingest(
            transcript="A sufficiently stable sentence after reconnect.",
            is_final=True,
            provider_speaker_id="speaker-a",
            created_at=1.0,
            start_time=0.0,
            end_time=2.0,
        )

        self.assertEqual(segment["speaker"]["attribution"], "unverified")
        self.assertEqual(segment["speaker"]["actorTrust"], "shared_mic_unverified")
        self.assertNotEqual(segment["speaker"]["actorTrust"], "owner_participant")

    def test_reconnect_scoped_guest_tombstones_do_not_demote_separate_owner_track(self):
        claim = _claim(
            speakerSessionState={
                "version": 1,
                "callSessionId": "call-1",
                "revision": 1,
                "attributionState": "shared_mic_unverified",
                "detectedAt": "2026-08-09T12:00:00.000Z",
                "sourceTrackSid": "track-guest-2",
                "sharedTrackSids": ["track-guest-1", "track-guest-2"],
                "sourceParticipantIdentity": "guest-2",
                "sharedParticipantIdentities": ["guest-1", "guest-2"],
            }
        )
        validated = _validate_voice_session_claim(
            claim,
            expected_call_session_id="call-1",
            expected_room_name="room-1",
            expected_gateway_agent_name="voice-gateway",
            expected_owner_participant_identity="owner-1",
        )
        state = validated["speakerSessionState"]
        owner = SpeakerSegmentTracker(
            call_session_id="call-1",
            participant_identity="owner-1",
            participant_name="Owner",
            track_sid="track-owner",
            owner_signed=True,
            initial_shared_microphone=shared_microphone_state_applies_to_track(
                state, "track-owner-reconnected", "owner-1"
            ),
        )
        guest = SpeakerSegmentTracker(
            call_session_id="call-1",
            participant_identity="guest-2",
            participant_name="Guest",
            track_sid="track-guest-2",
            participant_authenticated=True,
            initial_shared_microphone=shared_microphone_state_applies_to_track(
                state, "track-guest-reconnected", "guest-2"
            ),
        )

        [owner_segment] = owner.ingest(
            transcript="Owner remains verified after reconnect.",
            is_final=True,
            provider_speaker_id="speaker-a",
            created_at=1.0,
            start_time=0.0,
            end_time=2.0,
        )
        [guest_segment] = guest.ingest(
            transcript="Guest remains unverified after reconnect.",
            is_final=True,
            provider_speaker_id="speaker-a",
            created_at=1.0,
            start_time=0.0,
            end_time=2.0,
        )

        self.assertEqual(owner_segment["speaker"]["actorTrust"], "owner_participant")
        self.assertEqual(owner_segment["speaker"]["attribution"], "verified")
        self.assertEqual(
            guest_segment["speaker"]["actorTrust"], "shared_mic_unverified"
        )


class AuthoritativeRouteTests(unittest.TestCase):
    def setUp(self):
        with patch.dict(
            os.environ,
            {
                "VIVENTIUM_VOICE_STT_PROVIDER": "openai",
                "VIVENTIUM_TTS_PROVIDER": "openai",
                "OPENAI_API_KEY": "synthetic",
            },
            clear=True,
        ):
            self.env = load_env()

    def test_unavailable_requested_local_route_fails_without_openai_egress(self):
        capabilities = [
            _capability("pywhispercpp", "stt", available=False, is_local=True),
            _capability(
                "local_chatterbox_turbo_mlx_8bit", "tts", available=False, is_local=True
            ),
            _capability("openai", "stt", available=True),
            _capability("openai", "tts", available=True),
        ]
        with patch("worker.openai.STT", side_effect=AssertionError("no OpenAI STT")):
            with self.assertRaises(VoiceRouteError) as raised:
                _apply_requested_voice_route(
                    self.env,
                    {
                        "stt": {"provider": "pywhispercpp", "variant": "tiny.en"},
                        "tts": {
                            "provider": "local_chatterbox_turbo_mlx_8bit",
                            "variant": "local-model",
                        },
                    },
                    capabilities,
                )
        self.assertEqual(raised.exception.code, "provider_failure")
        self.assertEqual(raised.exception.egress_class, "local")

    def test_unavailable_requested_cloud_route_fails_without_openai_fallback(self):
        capabilities = [
            _capability("assemblyai", "stt", available=False),
            _capability("elevenlabs", "tts", available=False),
            _capability("openai", "stt", available=True),
            _capability("openai", "tts", available=True),
        ]
        with self.assertRaises(VoiceRouteError) as raised:
            _apply_requested_voice_route(
                self.env,
                {
                    "stt": {"provider": "assemblyai", "variant": "universal-streaming"},
                    "tts": {"provider": "elevenlabs", "variant": "voice-1"},
                },
                capabilities,
            )
        self.assertEqual(raised.exception.code, "provider_failure")
        self.assertEqual(raised.exception.provider, "assemblyai")

    def test_unknown_or_missing_canonical_route_fails_as_no_route(self):
        for route in (
            {"stt": {}, "tts": {}},
            {
                "stt": {"provider": "invented-stt"},
                "tts": {"provider": "invented-tts"},
            },
        ):
            with self.subTest(route=route), self.assertRaises(VoiceRouteError) as raised:
                _apply_requested_voice_route(self.env, route, [])
            self.assertEqual(raised.exception.code, "no_route")

    def test_explicit_fallback_is_retained_only_with_same_egress_class(self):
        cloud_env = replace(self.env, tts_provider_fallback="elevenlabs")
        route = {
            "stt": {"provider": "openai", "variant": "gpt-4o-mini-transcribe"},
            "tts": {"provider": "openai", "variant": "gpt-4o-mini-tts"},
        }
        capabilities = [
            _capability(
                "openai",
                "stt",
                variants=("gpt-4o-mini-transcribe",),
            ),
            _capability("openai", "tts", variants=("gpt-4o-mini-tts",)),
            _capability("elevenlabs", "tts", variants=("voice-1",)),
        ]
        updated = _apply_requested_voice_route(cloud_env, route, capabilities)
        self.assertEqual(updated.tts_provider_fallback, "elevenlabs")

        local_env = replace(self.env, tts_provider_fallback="openai")
        local_capabilities = [
            _capability("pywhispercpp", "stt", is_local=True, variants=("tiny.en",)),
            _capability(
                "local_chatterbox_turbo_mlx_8bit",
                "tts",
                is_local=True,
                variants=("local-model",),
            ),
            _capability("openai", "tts", variants=("gpt-4o-mini-tts",)),
        ]
        local = _apply_requested_voice_route(
            local_env,
            {
                "stt": {"provider": "pywhispercpp", "variant": "tiny.en"},
                "tts": {
                    "provider": "local_chatterbox_turbo_mlx_8bit",
                    "variant": "local-model",
                },
            },
            local_capabilities,
        )
        self.assertEqual(local.tts_provider_fallback, "")

    def test_assemblyai_runtime_unavailable_never_constructs_openai(self):
        env = replace(self.env, stt_provider="assemblyai")
        with (
            patch("worker.HAS_ASSEMBLYAI", False),
            patch("worker.openai.STT", side_effect=AssertionError("OpenAI fallback must not run")),
        ):
            with self.assertRaises(VoiceRouteError) as raised:
                build_stt_selection(env, vad=object())
        self.assertEqual(raised.exception.provider, "assemblyai")


if __name__ == "__main__":
    unittest.main()
