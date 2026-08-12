import asyncio
import os
import sys
import unittest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from voice_progress import (
    AsyncVoiceProgressController,
    VoiceProgressStateMachine,
    parse_authoritative_call_state_packet,
    run_authoritative_mode_reconciliation,
    sync_authoritative_call_mode_once,
)


def _event(
    state="running",
    phase="tool",
    detail="Searching trusted sources",
    sequence=1,
    task_id="task_1",
):
    return {
        "version": 1,
        "taskId": task_id,
        "sequence": sequence,
        "state": state,
        "phase": phase,
        "detail": detail,
    }


class _ProgressController:
    def __init__(self):
        self.mode = "call"
        self.suspensions = 0

    def set_mode(self, mode):
        self.mode = mode

    def suspend_until_authoritative(self):
        self.suspensions += 1


class TestVoiceProgressStateMachine(unittest.TestCase):
    def test_neutral_ack_waits_for_authoritative_task_and_1_2_seconds(self) -> None:
        machine = VoiceProgressStateMachine(enabled=True)
        machine.on_task_event(_event(), now=0.0)

        self.assertEqual(machine.poll(now=1.19), [])
        self.assertEqual(machine.poll(now=1.2), [("task_1", "I'm on it.")])

    def test_early_model_output_suppresses_neutral_ack(self) -> None:
        machine = VoiceProgressStateMachine(enabled=True)
        machine.on_task_event(_event(), now=0.0)
        machine.on_model_output("task_1", now=0.5)

        self.assertEqual(machine.poll(now=1.3), [])

    def test_long_silence_speaks_truthful_phase_and_rate_limits_repeats(self) -> None:
        machine = VoiceProgressStateMachine(enabled=True)
        machine.on_task_event(_event(), now=0.0)
        machine.on_model_output("task_1", now=0.5)

        self.assertEqual(
            machine.poll(now=5.5),
            [("task_1", "I'm still working — Searching trusted sources.")],
        )
        self.assertEqual(machine.poll(now=6.0), [])
        self.assertEqual(machine.on_task_event(_event(), now=6.1), [])

    def test_long_silence_budget_starts_from_actual_audible_ack(self) -> None:
        machine = VoiceProgressStateMachine(enabled=True)
        machine.on_task_event(_event(), now=0.0)
        machine.on_model_output("task_1", now=0.5)
        machine.on_audible_ack("task_1", now=1.0)

        self.assertEqual(machine.poll(now=5.99), [])
        self.assertEqual(
            machine.poll(now=6.0),
            [("task_1", "I'm still working — Searching trusted sources.")],
        )

    def test_global_speech_limiter_prevents_two_tasks_talking_over_each_other(self) -> None:
        machine = VoiceProgressStateMachine(enabled=True, global_rate_limit_s=1.0)
        machine.on_task_event(_event(task_id="task_1"), now=0.0)
        machine.on_task_event(_event(task_id="task_2"), now=0.0)

        self.assertEqual(machine.poll(now=1.2), [("task_1", "I'm on it.")])
        self.assertEqual(machine.poll(now=1.7), [])
        self.assertEqual(machine.poll(now=2.2), [("task_2", "I'm on it.")])

    def test_cancellation_race_removes_pending_speech(self) -> None:
        machine = VoiceProgressStateMachine(enabled=True)
        machine.on_task_event(_event(), now=0.0)
        machine.on_task_event(_event(state="cancelling"), now=1.19)

        self.assertEqual(machine.poll(now=10.0), [])

    def test_cancel_barrier_recovering_stays_active_and_never_speaks_completion(self) -> None:
        machine = VoiceProgressStateMachine(enabled=True)
        recovering = _event(
            state="recovering",
            phase="cancel_barrier_recovering",
            detail="Cancellation protection is recovering",
            sequence=7,
        )
        recovering["error"] = {
            "code": "cancel_barrier_unavailable",
            "message": "Cancellation could not be made durable. Output remains locally suppressed.",
            "retryable": True,
        }

        self.assertEqual(machine.on_task_event(recovering, now=0.0), [])
        spoken = machine.poll(now=1.2)

        self.assertEqual(spoken, [("task_1", "I'm on it.")])
        self.assertFalse(any("completed" in text.lower() for _task_id, text in spoken))

    def test_terminal_tombstone_rejects_stale_replay_before_it_can_speak(self) -> None:
        machine = VoiceProgressStateMachine(enabled=True)
        machine.on_task_event(_event(sequence=5), now=0.0)
        machine.on_task_event(_event(state="cancelling", sequence=6), now=0.1)

        self.assertEqual(
            machine.on_task_event(
                _event(phase="retrieval", detail="Stale replay", sequence=5),
                now=1.0,
            ),
            [],
        )
        self.assertEqual(machine.poll(now=10.0), [])

    def test_listen_only_disables_all_progress_speech(self) -> None:
        machine = VoiceProgressStateMachine(enabled=False)
        machine.on_task_event(_event(), now=0.0)

        self.assertEqual(machine.poll(now=10.0), [])

    def test_dynamic_listen_only_clears_pending_work_stops_audio_and_can_resume(self) -> None:
        now = [0.0]
        spoken = []
        stopped = []
        controller = AsyncVoiceProgressController(
            machine=VoiceProgressStateMachine(enabled=True),
            speak=lambda task_id, text: spoken.append((task_id, text)),
            clock=lambda: now[0],
            stop_active_speech=lambda: stopped.append(True),
            initial_mode="call",
        )
        controller.on_task_event(_event())

        now[0] = 1.0
        controller.set_mode("listen_only")
        now[0] = 10.0
        controller.poll()
        controller.on_task_event(_event(phase="retrieval", detail="Reading sources"))

        self.assertEqual(spoken, [])
        self.assertEqual(stopped, [True])
        self.assertEqual(controller.mode, "listen_only")

        controller.set_mode("call")
        now[0] = 11.0
        controller.on_task_event(_event(phase="retrieval", detail="Reading sources"))
        now[0] = 12.21
        controller.poll()

        self.assertEqual(spoken, [("task_1", "I'm on it.")])
        self.assertEqual(controller.mode, "call")

    def test_fake_mode_server_switches_progress_and_ambient_without_reconnect(self) -> None:
        async def run():
            now = [0.0]
            spoken = []
            stopped = []
            ambient_modes = []
            transitions = []
            server_modes = iter(("listen_only", "call", None))

            async def fetch_mode():
                return next(server_modes)

            controller = AsyncVoiceProgressController(
                machine=VoiceProgressStateMachine(enabled=True),
                speak=lambda task_id, text: spoken.append((task_id, text)),
                clock=lambda: now[0],
                stop_active_speech=lambda: stopped.append(True),
                initial_mode="call",
            )
            controller.on_task_event(_event())
            await sync_authoritative_call_mode_once(
                fetch_mode=fetch_mode,
                progress_controller=controller,
                set_ambient_mode=ambient_modes.append,
                on_mode_transition=lambda previous, current: transitions.append(
                    (previous, current)
                ),
            )
            now[0] = 10.0
            controller.poll()
            await sync_authoritative_call_mode_once(
                fetch_mode=fetch_mode,
                progress_controller=controller,
                set_ambient_mode=ambient_modes.append,
                on_mode_transition=lambda previous, current: transitions.append(
                    (previous, current)
                ),
            )
            controller.on_task_event(_event())
            now[0] = 11.21
            controller.poll()
            await sync_authoritative_call_mode_once(
                fetch_mode=fetch_mode,
                progress_controller=controller,
                set_ambient_mode=ambient_modes.append,
                on_mode_transition=lambda previous, current: transitions.append(
                    (previous, current)
                ),
            )
            return spoken, stopped, ambient_modes, transitions, controller.mode

        spoken, stopped, ambient_modes, transitions, mode = asyncio.run(run())
        self.assertEqual(spoken, [("task_1", "I'm on it.")])
        self.assertEqual(stopped, [True, True])
        self.assertEqual(ambient_modes, ["listen_only", "call"])
        self.assertEqual(transitions, [("call", "listen_only"), ("listen_only", "call")])
        self.assertEqual(mode, "call")

    def test_uncertain_mode_interrupts_every_speech_plane_immediately(self) -> None:
        async def run():
            stopped = []
            uncertain = []
            controller = AsyncVoiceProgressController(
                machine=VoiceProgressStateMachine(enabled=True),
                speak=lambda _task_id, _text: None,
                clock=lambda: 0.0,
                stop_active_speech=lambda: stopped.append("progress"),
                initial_mode="call",
            )
            result = await sync_authoritative_call_mode_once(
                fetch_mode=lambda: _return_async(None),
                progress_controller=controller,
                set_ambient_mode=lambda _mode: None,
                on_state_uncertain=lambda: uncertain.append("main_and_followup"),
            )
            return result, stopped, uncertain

        result, stopped, uncertain = asyncio.run(run())
        self.assertIsNone(result)
        self.assertEqual(stopped, ["progress"])
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
            progress = _ProgressController()
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
                progress_controller=progress,
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
            progress = _ProgressController()
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
                progress_controller=progress,
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


if __name__ == "__main__":
    unittest.main()
