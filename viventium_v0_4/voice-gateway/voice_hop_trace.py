"""Content-free voice hop timing and deterministic first-breach analysis."""

from __future__ import annotations

import json
from typing import Any, Optional


HOP_ORDER = (
    "utterance_end",
    "gateway_dispatch",
    "agent_start",
    "tool_start",
    "tool_end",
    "first_model_token",
    "tts_first_byte",
    "audio_output",
)


class VoiceHopTrace:
    def __init__(self, *, correlation_id: str, call_session_id: str) -> None:
        self.correlation_id = correlation_id
        self.call_session_id = call_session_id
        self._timestamps_ms: dict[str, float] = {}

    def record(self, hop: str, timestamp_ms: float) -> bool:
        if hop not in HOP_ORDER or hop in self._timestamps_ms:
            return False
        self._timestamps_ms[hop] = float(timestamp_ms)
        return True

    def has(self, hop: str) -> bool:
        return hop in self._timestamps_ms

    def missing_hops(self) -> list[str]:
        tool_observed = "tool_start" in self._timestamps_ms or "tool_end" in self._timestamps_ms
        required_hops = (
            HOP_ORDER
            if tool_observed
            else tuple(hop for hop in HOP_ORDER if hop not in {"tool_start", "tool_end"})
        )
        return [hop for hop in required_hops if hop not in self._timestamps_ms]

    def log_payload(self, hop: str) -> str:
        return json.dumps(
            {
                "event": "voice_hop",
                "correlationId": self.correlation_id,
                "callSessionId": self.call_session_id,
                "hop": hop,
                "timestampMs": self._timestamps_ms.get(hop),
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    def first_breach(self, gates_ms: dict[str, float]) -> Optional[dict[str, float | str]]:
        for left, right in zip(HOP_ORDER, HOP_ORDER[1:]):
            gate_key = f"{left}->{right}"
            if gate_key not in gates_ms:
                continue
            if left not in self._timestamps_ms or right not in self._timestamps_ms:
                continue
            elapsed = self._timestamps_ms[right] - self._timestamps_ms[left]
            if elapsed > float(gates_ms[gate_key]):
                return {
                    "hop": gate_key,
                    "elapsedMs": elapsed,
                    "gateMs": float(gates_ms[gate_key]),
                }
        return None

    def terminal_summary(self, gates_ms: dict[str, float]) -> dict[str, Any]:
        missing = self.missing_hops()
        return {
            "event": "voice_hop_trace_terminal",
            "correlationId": self.correlation_id,
            "callSessionId": self.call_session_id,
            "status": "incomplete" if missing else "complete",
            "missingHops": missing,
            "firstBreach": self.first_breach(gates_ms),
            "timestampsMs": dict(self._timestamps_ms),
        }
