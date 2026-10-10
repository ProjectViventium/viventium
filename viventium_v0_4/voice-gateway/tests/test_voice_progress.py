import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from voice_progress import (
    parse_authoritative_call_state_packet,
    run_authoritative_mode_reconciliation,
    sync_authoritative_call_mode_once,
)


class _ModeState:
    def __init__(self):
        self._mode = "call"
        self.authoritative = True
        self.suspensions = 0

    @property
    def mode(self):
        return self._mode if self.authoritative else None

    def apply(self, mode):
        self._mode = mode
        self.authoritative = True

    def suspend(self):
        self.authoritative = False
        self.suspensions += 1


class TestAuthoritativeCallModeState(unittest.TestCase):
    def test_mode_reconciliation_returns_snapshot_before_audio_restore_grant(self):
        async def run():
            state = _ModeState()
            ambient_modes = []
            transitions = []
            for mode in ("listen_only", "call"):
                state.suspend()
                result = await sync_authoritative_call_mode_once(
                    fetch_mode=lambda: _return_async(mode),
                    mode_state=state,
                    set_ambient_mode=ambient_modes.append,
                    on_mode_transition=lambda previous, current: transitions.append((previous, current)),
                )
                self.assertIsNone(state.mode)
                state.apply(result)  # Existing caller grant, after successful audio restore.
            return state.mode, ambient_modes, transitions

        mode, ambient_modes, transitions = asyncio.run(run())
        self.assertEqual(mode, "call")
        self.assertEqual(ambient_modes, ["listen_only", "call"])
        self.assertEqual(transitions, [(None, "listen_only"), (None, "call")])

    def test_uncertain_mode_suspends_dispatch_and_interrupts_existing_planes(self):
        async def run():
            state = _ModeState()
            uncertain = []
            result = await sync_authoritative_call_mode_once(
                fetch_mode=lambda: _return_async(None),
                mode_state=state,
                set_ambient_mode=lambda _mode: None,
                on_state_uncertain=lambda: uncertain.append("main_and_followup"),
            )
            return result, state, uncertain

        result, state, uncertain = asyncio.run(run())
        self.assertIsNone(result)
        self.assertIsNone(state.mode)
        self.assertEqual(state.suspensions, 1)
        self.assertEqual(uncertain, ["main_and_followup"])


    def test_signed_owner_call_state_push_is_strict_and_monotonic(self) -> None:
        payload = {
            "version": 1,
            "callSessionId": "call_1",
            "mode": "listen_only",
            "status": "listening",
            "revision": 8,
            "updatedAt": "2026-08-09T20:37:04.000Z",
        }

        self.assertEqual(
            parse_authoritative_call_state_packet(
                payload,
                expected_call_session_id="call_1",
                expected_owner_identity="owner",
                source_identity="owner",
                latest_revision=7,
            ),
            ("listen_only", "listening", 8),
        )
        self.assertIsNone(
            parse_authoritative_call_state_packet(
                payload,
                expected_call_session_id="call_1",
                expected_owner_identity="owner",
                source_identity="guest",
                latest_revision=7,
            )
        )
        self.assertIsNone(
            parse_authoritative_call_state_packet(
                payload,
                expected_call_session_id="call_1",
                expected_owner_identity="owner",
                source_identity="owner",
                latest_revision=8,
            )
        )

    def test_120_minute_http_reconciliation_is_bounded_to_five_second_cadence(self) -> None:
        async def run():
            now = [0.0]
            call_times = []
            sleep_delays = []

            async def reconcile_once():
                call_times.append(now[0])
                # Model the full fail-closed request timeout; it must consume the period.
                now[0] += 0.2

            async def advance(delay):
                sleep_delays.append(delay)
                now[0] += delay

            calls = await run_authoritative_mode_reconciliation(
                reconcile_once=reconcile_once,
                clock=lambda: now[0],
                sleep=advance,
                duration_s=120 * 60,
            )
            return calls, call_times, sleep_delays

        calls, call_times, sleep_delays = asyncio.run(run())

        self.assertLessEqual(calls, 1_500)
        self.assertEqual(calls, 1_440)
        self.assertEqual(call_times[:3], [0.0, 5.0, 10.0])
        self.assertAlmostEqual(call_times[-1], 7_195.0)
        self.assertTrue(all(abs(delay - 4.8) < 1e-9 for delay in sleep_delays))

    def test_normal_200ms_reconciliation_tail_does_not_suspend_speech(self) -> None:
        async def run():
            now = [0.0]
            progress = _ModeState()
            uncertain = []

            async def fetch_mode():
                now[0] += 0.2
                return {
                    "version": 1,
                    "callSessionId": "call_1",
                    "mode": "call",
                    "status": "listening",
                    "revision": 3,
                }

            result = await sync_authoritative_call_mode_once(
                fetch_mode=fetch_mode,
                mode_state=progress,
                set_ambient_mode=lambda _mode: None,
                on_state_uncertain=lambda: uncertain.append(True),
            )
            return result, progress, uncertain

        result, progress, uncertain = asyncio.run(run())
        self.assertEqual(result, "call")
        self.assertEqual(progress.suspensions, 0)
        self.assertEqual(uncertain, [])

    def test_terminal_authoritative_state_stops_speech_without_cancelling_work(self) -> None:
        async def run():
            progress = _ModeState()
            terminal = []
            backend_work = {"state": "running"}
            result = await sync_authoritative_call_mode_once(
                fetch_mode=lambda: _return_async(
                    {
                        "version": 1,
                        "callSessionId": "call_1",
                        "mode": "call",
                        "status": "ended",
                        "revision": 9,
                    }
                ),
                mode_state=progress,
                set_ambient_mode=lambda _mode: None,
                on_terminal_state=lambda status: terminal.append(status),
            )
            return result, progress, terminal, backend_work

        result, progress, terminal, backend_work = asyncio.run(run())
        self.assertIsNone(result)
        self.assertEqual(progress.suspensions, 1)
        self.assertEqual(terminal, ["ended"])
        self.assertEqual(backend_work, {"state": "running"})


async def _return_async(value):
    return value
