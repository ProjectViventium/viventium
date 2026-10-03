"""Ambient multi-track STT ingress with exactly one conversational/speaking AgentSession."""

from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from contextlib import suppress
from typing import Any, Awaitable, Callable

try:
    from livekit.plugins.assemblyai.stt import SpeechStream as AssemblyAISpeechStream
except ImportError:
    AssemblyAISpeechStream = None

from speaker_segments import (
    CallScopedSegmentSequencer,
    SpeakerSegmentTracker,
    demote_segment_to_unknown,
    shared_microphone_state_applies_to_track,
)


def speech_stream_call_timeline_offset_s(stream: Any, call_origin_at_ms: Any) -> float | None:
    """Translate SDK transcript time with its current public stream/retry clock pair."""
    values = (getattr(stream, 'start_time', None),
              getattr(stream, 'start_time_offset', None), call_origin_at_ms)
    if any(not isinstance(value, (int, float)) or isinstance(value, bool)
           or not math.isfinite(float(value)) for value in values):
        return None
    start_time, sdk_offset, origin_ms = (float(value) for value in values)
    return start_time - origin_ms / 1000.0 - sdk_offset


class AudioSampleTimeline:
    """Map stream sample timestamps to measured audio receipt time across frame gaps."""

    def __init__(self) -> None:
        self._frames: deque[tuple[float, float, float]] = deque(maxlen=4096)
        self._sdk_offset: float | None = None
        self._samples_s = 0.0
        self._generation_unproved = False

    @staticmethod
    def _finite(value: Any) -> bool:
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(float(value)))

    def push_frame(self, frame: Any, stream: Any, call_time_s: Any) -> None:
        duration = getattr(frame, "duration", None)
        offset = getattr(stream, "start_time_offset", None)
        if not all(self._finite(value) for value in (duration, offset, call_time_s)) or duration <= 0:
            return
        if offset != self._sdk_offset:
            # The SDK changes this public offset for a new provider connection/retry.
            if self._sdk_offset is not None:
                self._generation_unproved = True
            self._frames.clear()
            self._samples_s = 0.0
            self._sdk_offset = float(offset)
        start = self._samples_s
        self._samples_s += float(duration)
        self._frames.append((start, self._samples_s, float(call_time_s)))

    def physical_utc_available(self, stream: Any, alternative: Any = None) -> bool:
        # A retry retains the SDK input channel. Frames forwarded during backoff can
        # be replayed at the new connection; their provider sample origin is unproved.
        if self._sdk_offset is not None and getattr(stream, "start_time_offset", None) != self._sdk_offset:
            self._generation_unproved = True
        if self._generation_unproved:
            return False
        if alternative is not None:
            start = self.time_for(alternative, stream, end=False)
            end = self.time_for(alternative, stream, end=True)
            if (start is None) != (end is None):
                return False
        return True

    def time_for(self, alternative: Any, stream: Any, *, end: bool) -> float | None:
        if not self.physical_utc_available(stream):
            return None
        value = getattr(alternative, "end_time" if end else "start_time", None)
        words = getattr(alternative, "words", None) or []
        word = words[-1 if end else 0] if words else None
        offset = getattr(word, "start_time_offset", None)
        if not self._finite(offset):
            offset = getattr(stream, "start_time_offset", None)
        if not self._finite(value) or not self._finite(offset) or offset != self._sdk_offset:
            return None
        sample_time = float(value) - float(offset)
        for start, stop, receipt_end in self._frames:
            # A shared sample boundary has two different times after an audio gap:
            # the preceding frame end and the following frame start.
            within = start < sample_time <= stop if end else start <= sample_time < stop
            if within or (end and math.isclose(sample_time, stop, rel_tol=0, abs_tol=1e-8)):
                return receipt_end - (stop - sample_time)
        return None


def speech_stream_speaker_id(stream: Any, speaker_id: Any) -> Any:
    """An unresolved AssemblyAI label is not evidence of a distinct diarized voice."""
    # AssemblyAI's current wire contract uses PENDING for short/unassigned turns;
    # pinned LiveKit 1.5.10 only normalizes its older UNKNOWN value.
    # https://www.assemblyai.com/docs/streaming/label-speakers-and-separate-channels
    if (AssemblyAISpeechStream is not None and isinstance(stream, AssemblyAISpeechStream)
            and speaker_id in ("PENDING", "UNKNOWN")):
        return None
    return speaker_id


class _OwnerTemporarilyAbsent(RuntimeError):
    pass


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
        on_session_state_change: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
        owner_present: Callable[[], bool] | None = None,
        initial_speaker_session_state: dict[str, Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
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
        self._on_session_state_change = on_session_state_change
        self._owner_present = owner_present or (lambda: True)
        self._initial_speaker_session_state = (
            dict(initial_speaker_session_state)
            if isinstance(initial_speaker_session_state, dict)
            else None
        )
        self._clock = clock
        self._call_epoch = clock()
        self._call_epoch_at_ms = wall_clock() * 1000.0
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

    def call_timeline_origin_at_ms(self) -> float:
        """UTC anchor captured with this call's monotonic audio timeline origin."""
        return self._call_epoch_at_ms

    def apply_call_wide_overlap(
        self, segments: list[dict[str, Any]], *, timeline_available: bool = True,
    ) -> list[dict[str, Any]]:
        """Register owner or ambient finals in one call-wide overlap timeline."""
        return self._apply_cross_track_overlap(segments, timeline_available=timeline_available)

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
            initial_shared_microphone=shared_microphone_state_applies_to_track(
                self._initial_speaker_session_state,
                track_sid,
                identity,
            ),
        )
        task = asyncio.create_task(
            self._run_track(
                participant=participant,
                track=track,
                track_sid=track_sid,
                tracker=tracker,
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
    ) -> None:
        attempts = 0
        while True:
            try:
                await self._run_track_once(
                    participant=participant,
                    track=track,
                    track_sid=track_sid,
                    tracker=tracker,
                )
                return
            except _OwnerTemporarilyAbsent:
                attempts = 0
                while not self._owner_present():
                    await asyncio.sleep(0.05)
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
    ) -> None:
        if not self._owner_present():
            raise _OwnerTemporarilyAbsent
        await self._persist_pending_session_states(tracker)
        _ = participant, track_sid
        # Each STT stream has its own relative timing origin. Re-anchor every retry/resume on the
        # call timeline so an owner absence cannot move later guest speech back into old audio.
        stream_start_offset_s = self.call_timeline_offset_s()
        speech_stream = self._stt_impl.stream()
        audio_stream = self._audio_stream_factory(track)
        capabilities = getattr(self._stt_impl, "capabilities", None)
        sample_timeline = (AudioSampleTimeline() if getattr(capabilities, "streaming", False)
                           else None)

        async def _feed_audio() -> None:
            first_frame = True
            try:
                async for audio_event in audio_stream:
                    if not self._owner_present():
                        break
                    frame = getattr(audio_event, "frame", audio_event)
                    if first_frame:
                        duration = getattr(frame, "duration", 0.0)
                        if isinstance(duration, (int, float)) and math.isfinite(duration):
                            speech_stream.start_time = time.time() - max(float(duration), 0.0)
                        first_frame = False
                    if sample_timeline is not None:
                        sample_timeline.push_frame(frame, speech_stream, self.call_timeline_offset_s())
                    speech_stream.push_frame(frame)
            finally:
                speech_stream.end_input()

        feeder = asyncio.create_task(_feed_audio())
        try:
            async for event in speech_stream:
                if not self._owner_present():
                    raise _OwnerTemporarilyAbsent
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
                stream_offset_s = speech_stream_call_timeline_offset_s(
                    speech_stream, self.call_timeline_origin_at_ms())
                if stream_offset_s is None:
                    stream_offset_s = stream_start_offset_s
                start_time, end_time = stream_offset_s + relative_start, stream_offset_s + relative_end
                if sample_timeline is not None:
                    measured_start = sample_timeline.time_for(alternative, speech_stream, end=False)
                    measured_end = sample_timeline.time_for(alternative, speech_stream, end=True)
                    if measured_start is not None and measured_end is not None and measured_end > measured_start:
                        start_time, end_time = measured_start, measured_end
                changes = tracker.ingest(
                    transcript=str(getattr(alternative, "text", "") or ""),
                    is_final=is_final,
                    provider_speaker_id=speech_stream_speaker_id(
                        speech_stream, getattr(alternative, "speaker_id", None)),
                    created_at=float(getattr(event, "created_at", 0.0) or 0.0),
                    start_time=start_time,
                    end_time=end_time,
                )
                await self._persist_pending_session_states(tracker)
                if not self._owner_present():
                    raise _OwnerTemporarilyAbsent
                if changes and not is_final:
                    await self._on_segment_changes(changes)
                if is_final:
                    segments, revisions = tracker.finalize_turn(
                        str(getattr(alternative, "text", "") or "")
                    )
                    overlap_revisions = self._apply_cross_track_overlap(segments,
                        timeline_available=(sample_timeline is None or
                                            sample_timeline.physical_utc_available(speech_stream, alternative)))
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
        if not self._owner_present():
            raise _OwnerTemporarilyAbsent

    async def _persist_pending_session_states(
        self, tracker: SpeakerSegmentTracker
    ) -> None:
        if self._on_session_state_change is None:
            return
        states = tracker.pop_session_state_changes()
        if not states:
            return
        try:
            for state in states:
                await self._on_session_state_change(state)
        except BaseException:
            tracker.requeue_session_state_changes(states)
            raise

    def _apply_cross_track_overlap(
        self, segments: list[dict[str, Any]], *, timeline_available: bool = True,
    ) -> list[dict[str, Any]]:
        # Provider-relative times from replayed/backoff audio cannot prove call-wide
        # overlap. Keep attribution unchanged; do not register them as clock evidence.
        if not timeline_available:
            return []
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
