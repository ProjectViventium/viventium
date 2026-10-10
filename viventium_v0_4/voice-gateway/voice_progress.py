"""Validate and reconcile server-owned Voice call state."""

from __future__ import annotations

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








async def sync_authoritative_call_mode_once(
    *,
    fetch_mode: Callable[[], Awaitable[Any]],
    mode_state: Any,
    set_ambient_mode: Callable[[str], None],
    on_mode_transition: Optional[Callable[[str, str], None]] = None,
    on_state_uncertain: Optional[Callable[[], None]] = None,
    on_terminal_state: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    """Validate one mode snapshot; the caller grants dispatch after audio restore."""
    try:
        state = await fetch_mode()
    except Exception:
        state = None
    if isinstance(state, dict):
        status = state.get("status")
        if status in {"ended", "failed"}:
            mode_state.suspend()
            if on_terminal_state is not None:
                on_terminal_state(str(status))
            return None
        mode = state.get("mode")
    else:
        mode = state
    if mode not in {"call", "wing", "listen_only"}:
        mode_state.suspend()
        if on_state_uncertain is not None:
            on_state_uncertain()
        return None
    previous_mode = mode_state.mode
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
