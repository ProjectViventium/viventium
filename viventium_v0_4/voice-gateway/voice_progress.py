"""Truthful spoken progress state machine driven only by authoritative task events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional


VOICE_CALL_STATUSES = {
    "created",
    "connecting",
    "listening",
    "speaking",
    "working",
    "needs_input",
    "degraded",
    "failed",
    "ended",
}


def parse_voice_call_state_v1(
    payload: Any, *, expected_call_session_id: str
) -> Optional[dict[str, Any]]:
    if (
        not isinstance(payload, dict)
        or payload.get("version") != 1
        or payload.get("callSessionId") != expected_call_session_id
        or payload.get("mode") not in {"call", "wing", "listen_only"}
        or payload.get("status") not in VOICE_CALL_STATUSES
        or not isinstance(payload.get("revision"), int)
        or isinstance(payload.get("revision"), bool)
        or payload["revision"] < 0
        or not isinstance(payload.get("updatedAt"), str)
        or not payload["updatedAt"].strip()
        or len(payload["updatedAt"]) > 64
    ):
        return None
    try:
        updated_at = datetime.fromisoformat(payload["updatedAt"].replace("Z", "+00:00"))
    except ValueError:
        return None
    if updated_at.tzinfo is None:
        return None
    return {
        "version": 1,
        "callSessionId": expected_call_session_id,
        "mode": str(payload["mode"]),
        "status": str(payload["status"]),
        "revision": int(payload["revision"]),
        "updatedAt": payload["updatedAt"],
    }


def parse_authoritative_call_state_packet(
    payload: Any,
    *,
    expected_call_session_id: str,
    expected_owner_identity: str,
    source_identity: str,
    latest_revision: int,
) -> Optional[tuple[str, str, int]]:
    """Validate an owner-bound VoiceCallStateV1 packet before changing any speech plane."""
    if (
        not isinstance(payload, dict)
        or payload.get("version") != 1
        or not expected_owner_identity
        or source_identity != expected_owner_identity
        or payload.get("callSessionId") != expected_call_session_id
        or parse_voice_call_state_v1(
            payload, expected_call_session_id=expected_call_session_id
        )
        is None
        or payload["revision"] <= latest_revision
    ):
        return None
    return str(payload["mode"]), payload["status"].strip(), int(payload["revision"])


@dataclass
class _ActiveTask:
    task_id: str
    started_at: float
    last_activity_at: float
    phase: str
    detail: str
    latest_sequence: int
    model_acknowledged: bool = False
    neutral_ack_spoken: bool = False
    last_spoken_at: Optional[float] = None


class VoiceProgressStateMachine:
    def __init__(
        self,
        *,
        enabled: bool,
        neutral_ack_delay_s: float = 1.2,
        silence_update_s: float = 5.0,
        phase_rate_limit_s: float = 4.0,
        global_rate_limit_s: float = 1.0,
        tombstone_ttl_s: float = 86_400.0,
        max_tombstones: int = 2_048,
    ) -> None:
        self._enabled = enabled
        self._neutral_ack_delay_s = neutral_ack_delay_s
        self._silence_update_s = silence_update_s
        self._phase_rate_limit_s = phase_rate_limit_s
        self._global_rate_limit_s = max(float(global_rate_limit_s), 0.0)
        self._tombstone_ttl_s = max(float(tombstone_ttl_s), 1.0)
        self._max_tombstones = max(int(max_tombstones), 1)
        self._tasks: dict[str, _ActiveTask] = {}
        self._terminal_tombstones: dict[str, tuple[int, float]] = {}
        self._last_global_spoken_at: Optional[float] = None

    def set_enabled(self, enabled: bool) -> None:
        """Enable future speech, discarding stale work whenever speech is disabled."""
        self._enabled = bool(enabled)
        if not self._enabled:
            self._tasks.clear()

    def on_task_event(self, event: dict[str, Any], *, now: float) -> list[tuple[str, str]]:
        if not self._enabled:
            return []
        task_id = str(event.get("taskId") or "").strip()
        state = str(event.get("state") or "")
        if not task_id:
            return []
        sequence = event.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
            return []
        self._prune_tombstones(now)
        tombstone = self._terminal_tombstones.get(task_id)
        if tombstone is not None:
            if sequence > tombstone[0]:
                self._terminal_tombstones[task_id] = (sequence, now)
            return []
        if state in {
            "cancelling",
            "cancelled_confirmed",
            "cancelled_unenforceable",
            "completed",
            "failed",
        }:
            self._tasks.pop(task_id, None)
            self._terminal_tombstones[task_id] = (sequence, now)
            self._prune_tombstones(now)
            return []
        if state not in {"queued", "running", "needs_input", "recovering"}:
            return []
        phase = str(event.get("phase") or "").strip()
        detail = str(event.get("detail") or event.get("label") or phase).strip()
        task = self._tasks.get(task_id)
        if task is None:
            self._tasks[task_id] = _ActiveTask(
                task_id=task_id,
                started_at=now,
                last_activity_at=now,
                phase=phase,
                detail=detail,
                latest_sequence=sequence,
            )
            return []
        if sequence <= task.latest_sequence:
            return []
        task.latest_sequence = sequence
        phase_changed = bool(phase and phase != task.phase)
        task.phase = phase or task.phase
        task.detail = detail or task.detail
        task.last_activity_at = now
        if (
            phase_changed
            and task.last_spoken_at is not None
            and now - task.last_spoken_at >= self._phase_rate_limit_s
            and self._global_speech_allowed(now)
        ):
            self._record_speech_candidate(task, now)
            return [(task_id, self._progress_text(task))]
        return []

    def on_model_output(self, task_id: str, *, now: float) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.model_acknowledged = True
        task.last_activity_at = now

    def on_audible_ack(self, task_id: str, *, now: float) -> None:
        task = self._tasks.get((task_id or "").strip())
        if task is None:
            return
        task.model_acknowledged = True
        task.last_spoken_at = now
        self._last_global_spoken_at = now

    def suppress_task(self, task_id: str, *, now: float) -> None:
        normalized = (task_id or "").strip()
        if not normalized:
            return
        task = self._tasks.pop(normalized, None)
        latest_sequence = task.latest_sequence if task is not None else -1
        self._terminal_tombstones[normalized] = (latest_sequence, now)
        self._prune_tombstones(now)

    def poll(self, *, now: float) -> list[tuple[str, str]]:
        if not self._enabled:
            return []
        messages: list[tuple[str, str]] = []
        for task in self._tasks.values():
            if (
                not task.model_acknowledged
                and not task.neutral_ack_spoken
                and now - task.started_at >= self._neutral_ack_delay_s
                and self._global_speech_allowed(now)
            ):
                task.neutral_ack_spoken = True
                self._record_speech_candidate(task, now)
                messages.append((task.task_id, "I'm on it."))
                continue
            # Activity events are not audible acknowledgements. Anchor the silence budget to
            # actual/scheduled speech so repeated backend progress cannot hide dead air.
            silence_anchor = task.last_spoken_at or task.started_at
            if (
                now - silence_anchor >= self._silence_update_s
                and self._global_speech_allowed(now)
            ):
                self._record_speech_candidate(task, now)
                messages.append((task.task_id, self._progress_text(task)))
        return messages

    def _global_speech_allowed(self, now: float) -> bool:
        return (
            self._last_global_spoken_at is None
            or now - self._last_global_spoken_at >= self._global_rate_limit_s
        )

    def _record_speech_candidate(self, task: _ActiveTask, now: float) -> None:
        task.last_spoken_at = now
        self._last_global_spoken_at = now

    def _prune_tombstones(self, now: float) -> None:
        expired = [
            task_id
            for task_id, (_sequence, created_at) in self._terminal_tombstones.items()
            if now - created_at > self._tombstone_ttl_s
        ]
        for task_id in expired:
            self._terminal_tombstones.pop(task_id, None)
        while len(self._terminal_tombstones) > self._max_tombstones:
            self._terminal_tombstones.pop(next(iter(self._terminal_tombstones)))

    @staticmethod
    def _progress_text(task: _ActiveTask) -> str:
        if task.detail:
            return f"I'm still working — {task.detail}."
        return "I'm still working on it."


class AsyncVoiceProgressController:
    """Small scheduler wrapper; state-machine tests do not depend on real time."""

    def __init__(
        self,
        *,
        machine: VoiceProgressStateMachine,
        speak: Callable[[str, str], None],
        clock: Callable[[], float],
        stop_active_speech: Optional[Callable[[], None]] = None,
        initial_mode: str = "call",
    ) -> None:
        self._machine = machine
        self._speak = speak
        self._clock = clock
        self._stop_active_speech = stop_active_speech
        self._mode = (
            initial_mode
            if initial_mode in {"call", "wing", "listen_only"}
            else "call"
        )
        self._speech_enabled = self._mode != "listen_only"

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        if mode not in {"call", "wing", "listen_only"}:
            return
        self._mode = mode
        should_enable = mode != "listen_only"
        was_enabled = self._speech_enabled
        self._speech_enabled = should_enable
        self._machine.set_enabled(should_enable)
        if was_enabled and not should_enable and self._stop_active_speech is not None:
            self._stop_active_speech()

    def suspend_until_authoritative(self) -> None:
        """Fail safe after call-state lookup failure without disconnecting audio."""
        was_enabled = self._speech_enabled
        self._speech_enabled = False
        self._machine.set_enabled(False)
        if was_enabled and self._stop_active_speech is not None:
            self._stop_active_speech()

    def on_task_event(self, event: dict[str, Any]) -> None:
        state = str(event.get("state") or "")
        for task_id, text in self._machine.on_task_event(event, now=self._clock()):
            self._speak(task_id, text)
        if (
            state
            in {
                "cancelling",
                "cancelled_confirmed",
                "cancelled_unenforceable",
            }
            and self._stop_active_speech is not None
        ):
            self._stop_active_speech()

    def suppress_task(self, task_id: str) -> None:
        self._machine.suppress_task(task_id, now=self._clock())
        if self._stop_active_speech is not None:
            self._stop_active_speech()

    def on_model_output(self, task_id: str) -> None:
        self._machine.on_model_output(task_id, now=self._clock())

    def on_audible_ack(self, task_id: str) -> None:
        self._machine.on_audible_ack(task_id, now=self._clock())

    def poll(self) -> None:
        for task_id, text in self._machine.poll(now=self._clock()):
            self._speak(task_id, text)


async def sync_authoritative_call_mode_once(
    *,
    fetch_mode: Callable[[], Awaitable[Any]],
    progress_controller: AsyncVoiceProgressController,
    set_ambient_mode: Callable[[str], None],
    on_mode_transition: Optional[Callable[[str, str], None]] = None,
    on_state_uncertain: Optional[Callable[[], None]] = None,
    on_terminal_state: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    """Atomically apply one server-owned mode snapshot without reconnecting audio."""
    try:
        state = await fetch_mode()
    except Exception:
        state = None
    if isinstance(state, dict):
        status = state.get("status")
        if status in {"ended", "failed"}:
            progress_controller.suspend_until_authoritative()
            if on_terminal_state is not None:
                on_terminal_state(str(status))
            return None
        mode = state.get("mode")
    else:
        mode = state
    if mode not in {"call", "wing", "listen_only"}:
        progress_controller.suspend_until_authoritative()
        if on_state_uncertain is not None:
            on_state_uncertain()
        return None
    previous_mode = progress_controller.mode
    progress_controller.set_mode(mode)
    set_ambient_mode(mode)
    if mode != previous_mode and on_mode_transition is not None:
        on_mode_transition(previous_mode, mode)
    return mode


async def run_authoritative_mode_reconciliation(
    *,
    reconcile_once: Callable[[], Awaitable[None]],
    interval_s: float = 5.0,
    clock: Callable[[], float],
    sleep: Callable[[float], Awaitable[None]],
    duration_s: Optional[float] = None,
) -> int:
    """Run fixed-cadence HTTP reconciliation; request time consumes each interval."""
    interval = min(max(float(interval_s), 0.25), 60.0)
    started_at = clock()
    next_run_at = started_at
    calls = 0
    while duration_s is None or clock() - started_at < max(float(duration_s), 0.0):
        await reconcile_once()
        calls += 1
        next_run_at += interval
        delay_s = max(next_run_at - clock(), 0.0)
        if delay_s == 0.0:
            next_run_at = clock()
        await sleep(delay_s)
    return calls
