"""Privacy-safe, call-scoped speaker attribution for Viventium voice calls."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Optional


SPEAKER_CONTEXT_EXTRA_KEY = "viventiumSpeakerContextV1"
MIN_STABLE_SPEAKER_DURATION_S = 0.5
MIN_STABLE_SPEAKER_TEXT_CHARS = 6


class CallScopedSegmentSequencer:
    """Assign one immutable ordering key to each segment across every call track."""

    def __init__(self, *, max_entries: int = 16_384) -> None:
        self._next_sequence = 0
        self._by_segment_id: dict[str, int] = {}
        self._max_entries = max(int(max_entries), 1)

    def sequence_for(self, segment_id: str) -> int:
        sequence = self._by_segment_id.get(segment_id)
        if sequence is not None:
            return sequence
        self._next_sequence += 1
        self._by_segment_id[segment_id] = self._next_sequence
        while len(self._by_segment_id) > self._max_entries:
            self._by_segment_id.pop(next(iter(self._by_segment_id)))
        return self._next_sequence


def attach_speaker_context_to_message(
    tracker: "SpeakerSegmentTracker", message: Any
) -> dict[str, Any]:
    """Consume one turn of speaker events and attach it structurally to a LiveKit message."""
    text_content = getattr(message, "text_content", None)
    if not isinstance(text_content, str):
        content = getattr(message, "content", None)
        text_content = "".join(item for item in content or [] if isinstance(item, str))
    segments, revisions = tracker.finalize_turn(text_content or "")
    labels = {
        item.get("speaker", {}).get("label", "")
        for item in segments
        if item.get("speaker", {}).get("label")
    }
    if not labels or labels == {"Unknown"}:
        legacy_label = "room"
    elif len(labels) == 1:
        legacy_label = next(iter(labels))
    else:
        legacy_label = "multiple"
    context = {
        "speakerSegments": segments,
        "speakerSegmentRevisions": revisions,
        "speakerLabel": legacy_label,
        "ownerParticipantIdentity": tracker.participant_identity,
        "ownerTrackSid": tracker.track_sid,
        "utteranceEndAtMs": max(
            (
                float(item.get("endTimeMs"))
                for item in segments
                if isinstance(item.get("endTimeMs"), (int, float))
            ),
            default=tracker.last_observed_at_ms,
        ),
    }
    extra = getattr(message, "extra", None)
    if not isinstance(extra, dict):
        extra = {}
        setattr(message, "extra", extra)
    extra[SPEAKER_CONTEXT_EXTRA_KEY] = context
    return context


class SpeakerSegmentTracker:
    """Build versioned speaker segments without inferring biometric identity.

    Provider speaker IDs are useful only inside one call. A single diarized voice on a signed
    participant track may use the participant label. As soon as a second voice is observed on that
    track, every segment from the track is downgraded to an unverified, call-scoped speaker label.
    """

    def __init__(
        self,
        *,
        call_session_id: str,
        participant_identity: str = "",
        participant_name: str = "",
        track_sid: str = "",
        owner_signed: bool = False,
        participant_authenticated: bool = False,
        id_namespace: str = "",
        segment_sequencer: Optional[CallScopedSegmentSequencer] = None,
        max_retained_segments: int = 8_192,
        initial_shared_microphone: bool = False,
    ) -> None:
        self._call_session_id = call_session_id
        self._participant_identity = participant_identity.strip()
        self._participant_name = participant_name.strip()
        self._track_sid = track_sid.strip()
        self._owner_signed = bool(owner_signed and self._participant_identity)
        self._participant_authenticated = bool(
            participant_authenticated and self._participant_identity
        )
        self._id_namespace = "".join(
            character for character in id_namespace if character.isalnum() or character == "_"
        ).strip("_")
        self._segment_sequencer = segment_sequencer or CallScopedSegmentSequencer()
        self._max_retained_segments = max(int(max_retained_segments), 1)
        self._turn_sequence = 1
        self._segment_sequence = 0
        self._provider_speaker_order: dict[str, int] = {}
        self._shared_microphone_tombstone = bool(initial_shared_microphone)
        self._segments_by_id: dict[str, dict[str, Any]] = {}
        self._current_turn_segment_ids: list[str] = []
        self._pending_revisions: list[dict[str, Any]] = []
        self._pending_session_states: list[dict[str, Any]] = []
        self._shared_session_state_emitted = bool(initial_shared_microphone)
        self._active_segment_ids: dict[str, str] = {}
        self._last_event_fingerprint: Optional[tuple[str, bool, str, float]] = None
        self._last_observed_at_ms: Optional[float] = None

    @property
    def turn_id(self) -> str:
        namespace = f"{self._id_namespace}_" if self._id_namespace else ""
        return f"turn_{namespace}{self._turn_sequence:06d}"

    @property
    def participant_identity(self) -> str:
        return self._participant_identity

    @property
    def track_sid(self) -> str:
        return self._track_sid

    @property
    def last_observed_at_ms(self) -> Optional[float]:
        return self._last_observed_at_ms

    @property
    def shared_microphone_detected(self) -> bool:
        return self._shared_microphone_tombstone or len(self._provider_speaker_order) > 1

    def ingest(
        self,
        *,
        transcript: str,
        is_final: bool,
        provider_speaker_id: Optional[str],
        created_at: float,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> list[dict[str, Any]]:
        text = (transcript or "").strip()
        if not text:
            return []
        provider_id = (provider_speaker_id or "").strip()
        fingerprint = (text, bool(is_final), provider_id, float(created_at or 0.0))
        if fingerprint == self._last_event_fingerprint:
            return []
        self._last_event_fingerprint = fingerprint
        if created_at:
            self._last_observed_at_ms = float(created_at) * 1000.0
        stable_attribution = self._stable_attribution_evidence(
            text=text,
            is_final=bool(is_final),
            start_time=start_time,
            end_time=end_time,
        )

        changes: list[dict[str, Any]] = []
        observed_new_speaker = bool(
            provider_id and provider_id not in self._provider_speaker_order
        )
        if observed_new_speaker:
            self._provider_speaker_order[provider_id] = len(self._provider_speaker_order) + 1
            if self.shared_microphone_detected:
                self._shared_microphone_tombstone = True
                if not self._shared_session_state_emitted:
                    detected_at = (
                        datetime.fromtimestamp(float(created_at), tz=timezone.utc)
                        if float(created_at or 0.0) > 1_000_000_000
                        else datetime.now(timezone.utc)
                    )
                    self._pending_session_states.append(
                        {
                            "version": 1,
                            "callSessionId": self._call_session_id,
                            "revision": 1,
                            "attributionState": "shared_mic_unverified",
                            "detectedAt": detected_at.isoformat().replace("+00:00", "Z"),
                            **(
                                {"sourceTrackSid": self._track_sid}
                                if self._track_sid
                                else {}
                            ),
                        }
                    )
                    self._shared_session_state_emitted = True
                changes.extend(self._downgrade_existing_segments())

        active_segment_id = self._active_segment_ids.get(provider_id)
        active = self._segments_by_id.get(active_segment_id or "")
        active_provider = (
            (active or {}).get("speaker", {}).get("providerSpeakerId", "")
            if active
            else ""
        )
        if active is not None and active_provider == provider_id and not active.get("isFinal"):
            active["text"] = text
            active["isFinal"] = bool(is_final)
            active["revision"] += 1
            has_timing = start_time is not None and end_time is not None
            if has_timing:
                active["startTimeMs"] = round(float(start_time) * 1000)
                active["endTimeMs"] = round(float(end_time) * 1000)
            active["speaker"] = self._speaker_payload(
                provider_id,
                stable_attribution=stable_attribution,
            )
            active["uncertain"] = active["speaker"]["attribution"] == "unknown"
            changes.append(deepcopy(active))
            if is_final:
                self._active_segment_ids.pop(provider_id, None)
            return changes

        self._segment_sequence += 1
        namespace = f"{self._id_namespace}_" if self._id_namespace else ""
        segment_id = f"segment_{namespace}{self._segment_sequence:06d}"
        speaker = self._speaker_payload(
            provider_id,
            stable_attribution=stable_attribution,
        )
        segment: dict[str, Any] = {
            "version": 1,
            "segmentId": segment_id,
            "callSessionId": self._call_session_id,
            "turnId": self.turn_id,
            "sequence": self._segment_sequencer.sequence_for(segment_id),
            "revision": 1,
            "text": text,
            "isFinal": bool(is_final),
            "speaker": speaker,
            "overlap": False,
            "uncertain": speaker["attribution"] == "unknown",
        }
        has_timing = start_time is not None and end_time is not None
        if has_timing:
            segment["startTimeMs"] = round(float(start_time) * 1000)
            segment["endTimeMs"] = round(float(end_time) * 1000)
        self._segments_by_id[segment_id] = segment
        self._current_turn_segment_ids.append(segment_id)
        self._trim_segment_history()
        if not is_final:
            self._active_segment_ids[provider_id] = segment_id
        changes.append(deepcopy(segment))
        return changes

    def finalize_turn(
        self, final_text: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        text = (final_text or "").strip()
        if not self._current_turn_segment_ids and text:
            self.ingest(
                transcript=text,
                is_final=True,
                provider_speaker_id=None,
                created_at=0.0,
            )

        current = [
            deepcopy(self._segments_by_id[segment_id])
            for segment_id in self._current_turn_segment_ids
        ]
        revisions = [deepcopy(item) for item in self._pending_revisions]
        self._pending_revisions = []
        self._current_turn_segment_ids = []
        self._active_segment_ids = {}
        self._last_event_fingerprint = None
        self._turn_sequence += 1
        return current, revisions

    def pop_session_state_changes(self) -> list[dict[str, Any]]:
        states = [deepcopy(item) for item in self._pending_session_states]
        self._pending_session_states = []
        return states

    def _trim_segment_history(self) -> None:
        current = set(self._current_turn_segment_ids)
        while len(self._segments_by_id) > self._max_retained_segments:
            removable = next(
                (
                    segment_id
                    for segment_id in self._segments_by_id
                    if segment_id not in current
                ),
                None,
            )
            if removable is None:
                return
            self._segments_by_id.pop(removable, None)

    def _downgrade_existing_segments(self) -> list[dict[str, Any]]:
        revisions: list[dict[str, Any]] = []
        for segment in self._segments_by_id.values():
            provider_id = segment.get("speaker", {}).get("providerSpeakerId", "")
            if not provider_id:
                continue
            updated_speaker = self._speaker_payload(
                provider_id,
                stable_attribution=self._segment_has_stable_attribution(segment),
            )
            if segment.get("speaker") == updated_speaker:
                continue
            segment["speaker"] = updated_speaker
            segment["uncertain"] = False
            segment["revision"] += 1
            revision = deepcopy(segment)
            self._pending_revisions.append(revision)
            revisions.append(deepcopy(revision))
        return revisions

    @staticmethod
    def _stable_attribution_evidence(
        *,
        text: str,
        is_final: bool,
        start_time: Optional[float],
        end_time: Optional[float],
    ) -> bool:
        if not is_final or start_time is None or end_time is None:
            return False
        try:
            duration_s = float(end_time) - float(start_time)
        except (TypeError, ValueError):
            return False
        normalized_text = " ".join((text or "").split())
        return (
            duration_s >= MIN_STABLE_SPEAKER_DURATION_S
            and len(normalized_text) >= MIN_STABLE_SPEAKER_TEXT_CHARS
            and len(normalized_text.split()) >= 2
        )

    @classmethod
    def _segment_has_stable_attribution(cls, segment: dict[str, Any]) -> bool:
        start_ms = segment.get("startTimeMs")
        end_ms = segment.get("endTimeMs")
        return cls._stable_attribution_evidence(
            text=str(segment.get("text") or ""),
            is_final=bool(segment.get("isFinal")),
            start_time=float(start_ms) / 1000.0
            if isinstance(start_ms, (int, float)) and not isinstance(start_ms, bool)
            else None,
            end_time=float(end_ms) / 1000.0
            if isinstance(end_ms, (int, float)) and not isinstance(end_ms, bool)
            else None,
        )

    def _speaker_payload(
        self,
        provider_id: str,
        *,
        stable_attribution: bool,
    ) -> dict[str, Any]:
        participant_fields: dict[str, Any] = {}
        if self._participant_identity:
            participant_fields["participantIdentity"] = self._participant_identity
        if self._participant_name:
            participant_fields["participantName"] = self._participant_name
        if self._track_sid:
            participant_fields["trackSid"] = self._track_sid

        if not provider_id or not stable_attribution:
            return {
                "key": "unknown",
                "label": "Unknown",
                "source": "unknown",
                "attribution": "unknown",
                "actorTrust": "unknown",
                **({"providerSpeakerId": provider_id} if provider_id else {}),
                **participant_fields,
            }

        if self._owner_signed and not self.shared_microphone_detected:
            return {
                "key": f"participant:{self._participant_identity}",
                "label": self._participant_name or "Participant",
                "source": "hybrid",
                "attribution": "verified",
                "actorTrust": "owner_participant",
                "providerSpeakerId": provider_id,
                **participant_fields,
            }

        if self._participant_authenticated and not self.shared_microphone_detected:
            return {
                "key": f"participant:{self._participant_identity}",
                "label": self._participant_name or "Participant",
                "source": "hybrid",
                "attribution": "verified",
                "actorTrust": "authenticated_participant",
                "providerSpeakerId": provider_id,
                **participant_fields,
            }

        speaker_number = self._provider_speaker_order.get(provider_id)
        if speaker_number is None:
            return {
                "key": "unknown",
                "label": "Unknown",
                "source": "unknown",
                "attribution": "unknown",
                "actorTrust": "unknown",
                **participant_fields,
            }
        return {
            "key": f"provider:{provider_id}",
            "label": f"Speaker {speaker_number}",
            "source": "provider_diarization",
            "attribution": "unverified",
            "actorTrust": "shared_mic_unverified",
            "providerSpeakerId": provider_id,
            **participant_fields,
        }


def demote_segment_to_unknown(
    segment: dict[str, Any],
    *,
    increment_revision: bool,
) -> dict[str, Any]:
    """Abstain on ambiguous overlap without discarding call-scoped track/provider evidence."""
    updated = deepcopy(segment)
    speaker = updated.get("speaker") if isinstance(updated.get("speaker"), dict) else {}
    preserved = {
        key: speaker[key]
        for key in (
            "participantIdentity",
            "participantName",
            "trackSid",
            "providerSpeakerId",
        )
        if key in speaker
    }
    updated["speaker"] = {
        "key": "unknown",
        "label": "Unknown",
        "source": "unknown",
        "attribution": "unknown",
        "actorTrust": "unknown",
        **preserved,
    }
    updated["overlap"] = True
    updated["uncertain"] = True
    if increment_revision:
        updated["revision"] = int(updated.get("revision") or 0) + 1
    return updated
