"""Ambient multi-track STT ingress with exactly one conversational/speaking AgentSession."""

from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from typing import Any, Awaitable, Callable

from speaker_segments import (
    CallScopedSegmentSequencer,
    SpeakerSegmentTracker,
    demote_segment_to_unknown,
)


class MultiTrackIngressCoordinator:
    """Transcribe non-owner microphone tracks as non-authoritative ambient evidence."""

    def __init__(
        self,
        *,
        call_session_id: str,
        owner_participant_identity: str,
        mode: str = "call",
        stt_impl: Any,
        audio_stream_factory: Callable[[Any], Any],
        on_segment_changes: Callable[[list[dict[str, Any]]], Awaitable[None]],
        on_ambient_turn: Callable[[dict[str, Any]], Awaitable[None]],
        clock: Callable[[], float] = time.monotonic,
        overlap_window_ms: int = 60_000,
        max_final_segments: int = 512,
        max_tracks: int = 8,
        on_degraded: Callable[[str, str], Any] | None = None,
        max_stream_retries: int = 2,
        retry_delay_s: float = 0.25,
        segment_sequencer: CallScopedSegmentSequencer | None = None,
    ) -> None:
        self._call_session_id = call_session_id
        self._owner_identity = owner_participant_identity
        self._mode = mode if mode in {"call", "wing", "listen_only"} else "call"
        self._stt_impl = stt_impl
        self._audio_stream_factory = audio_stream_factory
        self._on_segment_changes = on_segment_changes
        self._on_ambient_turn = on_ambient_turn
        self._clock = clock
        self._call_epoch = clock()
        self._overlap_window_ms = max(int(overlap_window_ms), 1_000)
        self._max_final_segments = max(int(max_final_segments), 1)
        self._max_tracks = max(int(max_tracks), 1)
        self._on_degraded = on_degraded
        self._max_stream_retries = max(int(max_stream_retries), 0)
        self._retry_delay_s = max(float(retry_delay_s), 0.0)
        self._segment_sequencer = segment_sequencer or CallScopedSegmentSequencer()
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._registration_sequence = 0
        self._final_segments: dict[str, dict[str, Any]] = {}

    @property
    def active_track_sids(self) -> tuple[str, ...]:
        return tuple(sorted(self._tasks))

    @property
    def retained_final_segment_count(self) -> int:
        return len(self._final_segments)

    def set_mode(self, mode: str) -> None:
        if mode in {"call", "wing", "listen_only"}:
            self._mode = mode

    def call_timeline_offset_s(self) -> float:
        return max(self._clock() - self._call_epoch, 0.0)

    def apply_call_wide_overlap(
        self, segments: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Register owner or ambient finals in one call-wide overlap timeline."""
        return self._apply_cross_track_overlap(segments)

    def track_joined(self, participant: Any, track: Any, publication: Any) -> bool:
        identity = str(getattr(participant, "identity", "") or "").strip()
        if not identity or identity == self._owner_identity:
            return False
        track_sid = str(
            getattr(publication, "sid", "") or getattr(track, "sid", "") or ""
        ).strip()
        if not track_sid or track_sid in self._tasks:
            return False
        kind = str(getattr(track, "kind", "") or getattr(publication, "kind", "")).lower()
        if kind and "audio" not in kind:
            return False
        if len(self._tasks) >= self._max_tracks:
            self._report_degraded("track_limit", track_sid)
            return False
        self._registration_sequence += 1
        stream_start_offset_s = max(self._clock() - self._call_epoch, 0.0)
        namespace = f"ambient_{self._registration_sequence:03d}"
        tracker = SpeakerSegmentTracker(
            call_session_id=self._call_session_id,
            participant_identity=identity,
            participant_name=str(getattr(participant, "name", "") or "").strip(),
            track_sid=track_sid,
            owner_signed=False,
            participant_authenticated=True,
            id_namespace=namespace,
            segment_sequencer=self._segment_sequencer,
        )
        task = asyncio.create_task(
            self._run_track(
                participant=participant,
                track=track,
                track_sid=track_sid,
                tracker=tracker,
                stream_start_offset_s=stream_start_offset_s,
            )
        )
        self._tasks[track_sid] = task
        task.add_done_callback(
            lambda completed, sid=track_sid: self._tasks.pop(sid, None)
            if self._tasks.get(sid) is completed
            else None
        )
        return True

    async def track_left(self, track_sid: str) -> None:
        task = self._tasks.pop(track_sid, None)
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    async def close(self) -> None:
        tasks = list(self._tasks.values())
        self._tasks.clear()
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task

    async def wait_until_idle(self) -> None:
        tasks = list(self._tasks.values())
        if tasks:
            await asyncio.gather(*tasks)

    async def _run_track(
        self,
        *,
        participant: Any,
        track: Any,
        track_sid: str,
        tracker: SpeakerSegmentTracker,
        stream_start_offset_s: float,
    ) -> None:
        attempts = 0
        while True:
            try:
                await self._run_track_once(
                    participant=participant,
                    track=track,
                    track_sid=track_sid,
                    tracker=tracker,
                    stream_start_offset_s=stream_start_offset_s,
                )
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                attempts += 1
                if attempts > self._max_stream_retries:
                    self._report_degraded("track_stream_failed", track_sid)
                    return
                self._report_degraded("track_stream_retry", track_sid)
                await asyncio.sleep(self._retry_delay_s * attempts)

    async def _run_track_once(
        self,
        *,
        participant: Any,
        track: Any,
        track_sid: str,
        tracker: SpeakerSegmentTracker,
        stream_start_offset_s: float,
    ) -> None:
        _ = participant, track_sid
        speech_stream = self._stt_impl.stream()
        audio_stream = self._audio_stream_factory(track)

        async def _feed_audio() -> None:
            try:
                async for audio_event in audio_stream:
                    frame = getattr(audio_event, "frame", audio_event)
                    speech_stream.push_frame(frame)
            finally:
                speech_stream.end_input()

        feeder = asyncio.create_task(_feed_audio())
        try:
            async for event in speech_stream:
                event_type = str(getattr(event, "type", "")).lower()
                alternatives = getattr(event, "alternatives", None) or []
                if not alternatives or (
                    "interim_transcript" not in event_type
                    and "final_transcript" not in event_type
                ):
                    continue
                alternative = alternatives[0]
                is_final = "final_transcript" in event_type
                relative_start = float(getattr(alternative, "start_time", 0.0) or 0.0)
                relative_end = float(getattr(alternative, "end_time", 0.0) or 0.0)
                changes = tracker.ingest(
                    transcript=str(getattr(alternative, "text", "") or ""),
                    is_final=is_final,
                    provider_speaker_id=getattr(alternative, "speaker_id", None),
                    created_at=float(getattr(event, "created_at", 0.0) or 0.0),
                    start_time=stream_start_offset_s + relative_start,
                    end_time=stream_start_offset_s + relative_end,
                )
                if changes and not is_final:
                    await self._on_segment_changes(changes)
                if is_final:
                    segments, revisions = tracker.finalize_turn(
                        str(getattr(alternative, "text", "") or "")
                    )
                    overlap_revisions = self._apply_cross_track_overlap(segments)
                    all_revisions = [*revisions, *overlap_revisions]
                    if segments or all_revisions:
                        await self._on_segment_changes([*segments, *all_revisions])
                        await self._on_ambient_turn(
                            {
                                "version": 1,
                                "callSessionId": self._call_session_id,
                                "mode": self._mode,
                                "ingressKind": "ambient_participant",
                                "turnId": segments[0]["turnId"] if segments else "",
                                "segments": [*segments, *all_revisions],
                            }
                        )
        finally:
            if not feeder.done():
                feeder.cancel()
            with suppress(asyncio.CancelledError):
                await feeder

    def _apply_cross_track_overlap(
        self, segments: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        revisions: list[dict[str, Any]] = []
        for segment in segments:
            start_ms = segment.get("startTimeMs")
            end_ms = segment.get("endTimeMs")
            current_track = segment.get("speaker", {}).get("trackSid")
            if not isinstance(start_ms, (int, float)) or not isinstance(end_ms, (int, float)):
                self._final_segments[segment["segmentId"]] = segment.copy()
                self._trim_final_segments()
                continue
            for previous_id, previous in list(self._final_segments.items()):
                previous_track = previous.get("speaker", {}).get("trackSid")
                if not current_track or not previous_track or previous_track == current_track:
                    continue
                previous_start = previous.get("startTimeMs")
                previous_end = previous.get("endTimeMs")
                if not isinstance(previous_start, (int, float)) or not isinstance(
                    previous_end, (int, float)
                ):
                    continue
                if float(previous_end) < float(start_ms) - self._overlap_window_ms:
                    self._final_segments.pop(previous_id, None)
                    continue
                if max(float(start_ms), float(previous_start)) >= min(
                    float(end_ms), float(previous_end)
                ):
                    continue
                demoted_current = demote_segment_to_unknown(
                    segment,
                    increment_revision=False,
                )
                segment.clear()
                segment.update(demoted_current)
                if not previous.get("overlap"):
                    revised_previous = demote_segment_to_unknown(
                        previous,
                        increment_revision=True,
                    )
                    self._final_segments[previous_id] = revised_previous
                    revisions.append(revised_previous.copy())
            self._final_segments[segment["segmentId"]] = segment.copy()
            self._trim_final_segments()
        return revisions

    def _report_degraded(self, reason: str, track_sid: str) -> None:
        if self._on_degraded is None:
            return
        try:
            result = self._on_degraded(reason, track_sid)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)
        except Exception:
            # Degraded telemetry must never break the owner call path.
            return

    def _trim_final_segments(self) -> None:
        while len(self._final_segments) > self._max_final_segments:
            oldest_id = next(iter(self._final_segments))
            self._final_segments.pop(oldest_id, None)
