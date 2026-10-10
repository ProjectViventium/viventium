"""Private policy proposal: genuine owner-track provenance, no acoustic claim."""
import asyncio
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from livekit import rtc
from livekit.agents.stt import SpeechData, SpeechEvent, SpeechEventType, STTCapabilities, StreamAdapter
import inspect
import worker
from speaker_segments import SpeakerSegmentTracker
from worker import AuthoritativeCallModeState, ViventiumVoiceAgent


def observe(*, diarization=False, mode="call", owner_signed=True, identity="owner",
            track="TR_owner", shared=False, final=True, provider_ids=(None,),
            streaming=True, wrapped_diarization=False, capability_present=True,
            mode_sequence=None, capability_sequence=None, room=None, event_actions=None,
            sdk_default_capability=False, prewrapped=False):
    context = (worker._linked_participant_speaker_context(room, "owner") if room is not None
        else dict(owner_signed=owner_signed, participant_identity=identity, track_sid=track,
                  participant_authenticated=not owner_signed))
    tracker = SpeakerSegmentTracker(call_session_id="synthetic-call", **context,
        initial_shared_microphone=shared)
    mode_state = AuthoritativeCallModeState()
    if mode is not None:
        mode_state.apply(mode)
    frames = []
    class SpeechStream:
        start_time = 1_790_000_001.0
        start_time_offset = 0.0
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def push_frame(self, frame): frames.append(frame)
        async def __aiter__(self):
            for idx, provider_id in enumerate(provider_ids):
                if event_actions: event_actions[idx]()
                if mode_sequence: mode_state.apply(mode_sequence[idx])
                if capability_sequence: caps.diarization = capability_sequence[idx]
                alternative = SpeechData(language="en", text=f"Natural request {idx}.")
                if provider_id is not None:
                    alternative.speaker_id = provider_id
                    alternative.start_time = idx + 0.1
                    alternative.end_time = idx + 1.0
                yield SpeechEvent(type=(SpeechEventType.FINAL_TRANSCRIPT if final
                    else SpeechEventType.INTERIM_TRANSCRIPT), alternatives=[alternative])
                tracker.finalize_turn(alternative.text)
    stream = SpeechStream()
    caps = (STTCapabilities(streaming=streaming, interim_results=False)
            if sdk_default_capability else SimpleNamespace(streaming=streaming))
    if capability_present and not sdk_default_capability: caps.diarization = diarization
    provider = SimpleNamespace(capabilities=caps, stream=lambda **kwargs: stream)
    adapted = SimpleNamespace(capabilities=SimpleNamespace(diarization=wrapped_diarization),
        stream=lambda **kwargs: stream)
    if prewrapped:
        provider.on = lambda *args: None
        provider = StreamAdapter(stt=provider,vad=object())
        provider.stream = lambda **kwargs: stream
    activity = SimpleNamespace(stt=provider, vad=object(), _audio_recognition=None,
        session=SimpleNamespace(conn_options=SimpleNamespace(stt_conn_options="synthetic"),
            _recorder_io=None, _started_at=1_790_000_000.0))
    options = {}
    if room is not None and "refresh_speaker_track" in inspect.signature(ViventiumVoiceAgent).parameters:
        options["refresh_speaker_track"] = lambda: worker._refresh_owner_speaker_track(tracker,room,"owner")
    agent = ViventiumVoiceAgent(instructions="Synthetic capability check.",
        speaker_tracker=tracker, authoritative_mode_state=mode_state, **options)
    agent._get_activity_or_raise = lambda: activity
    async def audio():
        yield SimpleNamespace(duration=0.02)
        await asyncio.Event().wait()
    async def run():
        async for _ in agent.stt_node(audio(), None): pass
    with patch("livekit.agents.stt.StreamAdapter", return_value=adapted):
        asyncio.run(run())
    return tracker


def test_final_default_non_declaring_stt_call_uses_real_owner_track():
    segment = observe()._segments_by_id["segment_000001"]
    assert segment["speaker"]["source"] == "participant_track"
    assert segment["speaker"]["actorTrust"] == "owner_participant"
    assert segment["speaker"]["participantIdentity"] == "owner"
    assert segment["speaker"]["trackSid"] == "TR_owner"
    assert "providerSpeakerId" not in segment["speaker"]
    assert "startTimeMs" not in segment and "endTimeMs" not in segment
    assert segment["isFinal"] and not segment["uncertain"]


@pytest.mark.parametrize("change", [
    {"diarization":True}, {"diarization":None}, {"diarization":"false"},
    {"diarization":0}, {"capability_present":False}, {"mode":"wing"},
    {"mode":"listen_only"}, {"mode":None}, {"owner_signed":False},
    {"identity":""}, {"track":""}, {"shared":True}, {"final":False},
])
def test_missing_expected_attribution_and_restricted_context_do_not_gain_track_authority(change):
    segment = observe(**change)._segments_by_id["segment_000001"]
    assert segment["speaker"]["source"] == "unknown"
    assert segment["speaker"]["actorTrust"] == "unknown"
    assert segment["uncertain"]


def test_automatic_stream_adapter_does_not_hide_true_diarization_capability():
    segment = observe(diarization=True, streaming=False, wrapped_diarization=False)._segments_by_id["segment_000001"]
    assert segment["speaker"]["source"] == "unknown"


def test_false_diarization_producer_survives_automatic_adapter_without_faking_metadata():
    segment = observe(streaming=False)._segments_by_id["segment_000001"]
    assert segment["speaker"]["source"] == "participant_track"
    assert "providerSpeakerId" not in segment["speaker"]


def test_real_second_speaker_still_downgrades_and_tombstones_every_previous_track_segment():
    tracker = observe(diarization=True, provider_ids=("A", "B"))
    assert tracker.shared_microphone_detected
    assert all(s["speaker"]["actorTrust"] == "shared_mic_unverified" for s in tracker._segments_by_id.values())
    assert tracker.pop_session_state_changes()[0]["attributionState"] == "shared_mic_unverified"


def test_later_real_second_speaker_revokes_previous_track_only_evidence():
    tracker = SpeakerSegmentTracker(call_session_id="synthetic-mixed-route", owner_signed=True,
        participant_identity="owner", track_sid="TR_owner")
    import worker
    import inspect
    declared = {"stt_diarization":False,"call_mode":"call"}
    allowed = {key:value for key,value in declared.items()
        if key in inspect.signature(worker._ingest_raw_stt_speaker_event).parameters}
    event = SpeechEvent(type=SpeechEventType.FINAL_TRANSCRIPT,
        alternatives=[SpeechData(language="en", text="A natural first request.")])
    worker._ingest_raw_stt_speaker_event(tracker,event,timeline_offset_s=0.0,**allowed)
    first = tracker.finalize_turn(event.alternatives[0].text)[0][0]
    assert first["speaker"]["source"] == "participant_track"
    for idx, speaker_id in enumerate(["A","B"]):
        tracker.ingest(transcript=f"A stable later sentence {idx}.", is_final=True,
            provider_speaker_id=speaker_id, created_at=10.0+idx, start_time=idx, end_time=idx+1.0)
        tracker.finalize_turn("A stable later sentence.")
    revised = tracker._segments_by_id[first["segmentId"]]
    assert revised["revision"] > first["revision"]
    assert revised["speaker"]["actorTrust"] != "owner_participant"
    assert revised["uncertain"]
    assert tracker.shared_microphone_detected


def test_current_mode_is_read_per_event_instead_of_cached_at_call_start():
    tracker = observe(provider_ids=(None,None,None), mode_sequence=("call","wing","call"))
    assert [s["speaker"]["source"] for s in tracker._segments_by_id.values()] == [
        "participant_track","unknown","participant_track"]


def test_current_captured_stt_capability_is_read_per_event():
    tracker = observe(provider_ids=(None,None,None), capability_sequence=(False,True,False))
    assert [s["speaker"]["source"] for s in tracker._segments_by_id.values()] == [
        "participant_track","unknown","participant_track"]


def test_track_evidence_keeps_existing_duplicate_event_suppression():
    import inspect
    tracker = SpeakerSegmentTracker(call_session_id="synthetic-duplicate", owner_signed=True,
        participant_identity="owner", track_sid="TR_owner")
    options = dict(transcript="A natural request.",is_final=True,provider_speaker_id=None,created_at=10.0)
    if "allow_owner_participant_track" in inspect.signature(tracker.ingest).parameters:
        options["allow_owner_participant_track"] = True
    first = tracker.ingest(**options)
    assert first[0]["speaker"]["source"] == "participant_track"
    assert tracker.ingest(**options) == []
    assert len(tracker._segments_by_id) == 1


def test_whisper_uses_existing_sdk_capability_without_loading_a_real_model():
    import pywhispercpp_provider
    with patch("pywhispercpp_provider._get_model", return_value=object()):
        stt = pywhispercpp_provider.PyWhisperCppSTT()
    assert stt.capabilities.diarization is False
    assert stt.capabilities.streaming is False


def microphone(sid="TR_current", *, source=rtc.TrackSource.SOURCE_MICROPHONE,
               subscribed=True, track=True, track_sid=None, kind=rtc.TrackKind.KIND_AUDIO,
               muted=False):
    return SimpleNamespace(sid=sid,source=source,subscribed=subscribed,kind=kind,muted=muted,
        track=(SimpleNamespace(sid=sid if track_sid is None else track_sid,kind=kind) if track else None))


def room_with(*publications, identity="owner"):
    participant = SimpleNamespace(identity=identity,name="Signed participant",track_publications={
        str(index):item for index,item in enumerate(publications)})
    return SimpleNamespace(remote_participants={identity:participant})


def segments(tracker):
    return list(tracker._segments_by_id.values())


def refresh(tracker, room):
    if hasattr(worker,"_refresh_owner_speaker_track"):
        worker._refresh_owner_speaker_track(tracker,room,"owner")


def ingest_track(tracker, *, final=True, text="A natural spoken request.", provider=None, created=10.0):
    options = dict(transcript=text,is_final=final,provider_speaker_id=provider,created_at=created)
    if provider is not None:
        options.update(start_time=0.0,end_time=1.0)
    if "allow_owner_participant_track" in inspect.signature(tracker.ingest).parameters:
        options["allow_owner_participant_track"] = True
    return tracker.ingest(**options)


def test_actual_sdk_source_selects_microphone_after_secondary_screen_audio():
    screen = microphone("TR_screen",source=rtc.TrackSource.SOURCE_SCREENSHARE_AUDIO)
    room = room_with(screen,microphone())
    context = worker._linked_participant_speaker_context(room,"owner")
    assert context["track_sid"] == "TR_current"
    assert context["owner_signed"] is True
    assert segments(observe(room=room))[0]["speaker"]["trackSid"] == "TR_current"


@pytest.mark.parametrize("pub", [
    microphone(source=rtc.TrackSource.SOURCE_SCREENSHARE_AUDIO),
    microphone(source=rtc.TrackSource.SOURCE_CAMERA),
    microphone(subscribed=False),microphone(track=False),
    microphone(track_sid="TR_other"),microphone(kind=rtc.TrackKind.KIND_VIDEO),
    microphone(sid=""),
])
def test_non_current_microphone_publications_never_gain_signed_track_authority(pub):
    room=room_with(pub)
    context=worker._linked_participant_speaker_context(room,"owner")
    assert context.get("track_sid","") == ""
    assert context.get("owner_signed",False) is False
    assert segments(observe(room=room))[0]["speaker"]["source"] == "unknown"


def test_wrong_owner_publication_never_binds():
    assert worker._linked_participant_speaker_context(room_with(microphone(),identity="guest"),"owner").get("owner_signed",False) is False
    assert segments(observe(room=room_with(microphone(),identity="guest")))[0]["speaker"]["source"] == "unknown"


def test_ambiguous_two_subscribed_microphones_abstain_without_first_publication_fallback():
    room=room_with(microphone("TR_old"),microphone("TR_new"))
    assert worker._linked_participant_speaker_context(room,"owner").get("track_sid","") == ""
    assert segments(observe(room=room))[0]["speaker"]["source"] == "unknown"


def test_initially_muted_then_delayed_subscription_refreshes_actual_sid_per_event():
    room=room_with(microphone("TR_delayed",subscribed=False,track=False,muted=True))
    def publish():
        room.remote_participants["owner"].track_publications={"current":microphone("TR_delayed",muted=False)}
    tracker=observe(room=room,provider_ids=(None,None),event_actions=(lambda:None,publish))
    first,last=segments(tracker)
    assert first["speaker"]["source"] == "unknown"
    assert "trackSid" not in first["speaker"]
    assert last["speaker"]["source"] == "participant_track"
    assert last["speaker"]["trackSid"] == "TR_delayed"


def test_reload_and_republish_use_only_current_publication_sid_and_keep_old_segment_sid():
    old=microphone("TR_old");new=microphone("TR_new")
    room=room_with(old)
    def republish():
        old.track=None;old.subscribed=False
        room.remote_participants["owner"].track_publications={"old":old,"new":new}
    tracker=observe(room=room,provider_ids=(None,None),event_actions=(lambda:None,republish))
    assert [s["speaker"]["trackSid"] for s in segments(tracker)] == ["TR_old","TR_new"]
    assert all(s["speaker"]["source"] == "participant_track" for s in segments(tracker))
    reloaded=observe(room=room)
    assert segments(reloaded)[0]["speaker"]["trackSid"] == "TR_new"
    # A delayed old unsubscribe callback cannot select or clear the already subscribed new SID.
    refresh(tracker,room)
    assert tracker.track_sid == "TR_new"


def test_missing_participant_then_owner_subscription_binds_without_guessed_track():
    room=SimpleNamespace(remote_participants={})
    def join(): room.remote_participants=room_with(microphone("TR_joined")).remote_participants
    tracker=observe(room=room,provider_ids=(None,None),event_actions=(lambda:None,join))
    assert segments(tracker)[0]["speaker"]["source"] == "unknown"
    assert segments(tracker)[1]["speaker"]["trackSid"] == "TR_joined"
    assert segments(tracker)[1]["speaker"]["source"] == "participant_track"


@pytest.mark.parametrize("provider", [None,"A"])
def test_late_old_track_interim_cannot_promote_onto_replacement_track(provider):
    room=room_with(microphone("TR_old"))
    tracker=SpeakerSegmentTracker(call_session_id="synthetic-republish",**worker._linked_participant_speaker_context(room,"owner"))
    old=ingest_track(tracker,final=False,provider=provider)[0]
    room.remote_participants["owner"].track_publications={"new":microphone("TR_new")}
    refresh(tracker,room)
    final=ingest_track(tracker,text="A natural completed request.",created=11.0,provider=provider)[0]
    assert final["segmentId"] == old["segmentId"]
    assert final["revision"] == old["revision"]+1
    assert final["speaker"]["trackSid"] == "TR_old"
    assert final["speaker"]["source"] == "unknown" and final["uncertain"]
    tracker.finalize_turn(final["text"])
    current=ingest_track(tracker,created=12.0,provider=provider)[0]
    assert current["speaker"]["trackSid"] == "TR_new"
    assert current["speaker"]["source"] == ("hybrid" if provider else "participant_track")


def test_shared_participant_tombstone_survives_republish_and_preserves_old_revision_provenance():
    room=room_with(microphone("TR_old"))
    tracker=SpeakerSegmentTracker(call_session_id="synthetic-shared-republish",**worker._linked_participant_speaker_context(room,"owner"))
    first=ingest_track(tracker)[0];tracker.finalize_turn(first["text"])
    for idx,provider in enumerate(("A","B")):
        tracker.ingest(transcript="Two stable observed voices.",is_final=True,provider_speaker_id=provider,
            created_at=11+idx,start_time=idx,end_time=idx+1)
        tracker.finalize_turn("Two stable observed voices.")
    state=tracker.pop_session_state_changes()[0]
    assert state["sharedParticipantIdentities"] == ["owner"]
    room.remote_participants["owner"].track_publications={"new":microphone("TR_new")}
    refresh(tracker,room)
    assert tracker.shared_microphone_detected
    last=ingest_track(tracker,created=14.0)[0]
    assert last["speaker"]["trackSid"] == "TR_new"
    assert last["speaker"]["source"] == "unknown" and last["uncertain"]
    revised=tracker._segments_by_id[first["segmentId"]]
    assert revised["speaker"]["trackSid"] == "TR_old"
    assert revised["revision"] > first["revision"] and revised["uncertain"]
    from speaker_segments import shared_microphone_state_applies_to_track
    restored=SpeakerSegmentTracker(call_session_id="synthetic-shared-republish",**worker._linked_participant_speaker_context(room,"owner"),
        initial_shared_microphone=shared_microphone_state_applies_to_track(state,"TR_new","owner"))
    assert ingest_track(restored)[0]["speaker"]["source"] == "unknown"


def test_second_provider_speaker_after_republish_downgrades_old_provider_segment_without_relabeling_track():
    room=room_with(microphone("TR_old"))
    tracker=SpeakerSegmentTracker(call_session_id="synthetic-late-revision",**worker._linked_participant_speaker_context(room,"owner"))
    first=tracker.ingest(transcript="Stable first voice.",is_final=True,provider_speaker_id="A",created_at=10,start_time=0,end_time=1)[0]
    tracker.finalize_turn(first["text"])
    room.remote_participants["owner"].track_publications={"new":microphone("TR_new")};refresh(tracker,room)
    tracker.ingest(transcript="Stable second voice.",is_final=True,provider_speaker_id="B",created_at=11,start_time=1,end_time=2)
    revised=tracker._segments_by_id[first["segmentId"]]
    assert revised["speaker"]["trackSid"] == "TR_old"
    assert revised["speaker"]["providerSpeakerId"] == "A"
    assert revised["speaker"]["actorTrust"] == "shared_mic_unverified"
    assert not revised["uncertain"] and revised["revision"] > first["revision"]


def test_third_party_sdk_default_false_is_non_declaration_and_uses_participant_authority():
    caps=STTCapabilities(streaming=True,interim_results=False)
    assert caps.diarization is False
    segment=segments(observe(sdk_default_capability=True))[0]
    assert segment["speaker"]["source"] == "participant_track"
    assert "providerSpeakerId" not in segment["speaker"]


def test_late_unstable_provider_segment_keeps_unknown_uncertainty_during_shared_revision():
    tracker=SpeakerSegmentTracker(call_session_id="synthetic-unstable",owner_signed=True,participant_identity="owner",track_sid="TR_owner")
    first=tracker.ingest(transcript="Um",is_final=True,provider_speaker_id="A",created_at=10)[0]
    tracker.finalize_turn("Um")
    tracker.ingest(transcript="Stable second voice.",is_final=True,provider_speaker_id="B",created_at=11,start_time=1,end_time=2)
    revised=tracker._segments_by_id[first["segmentId"]]
    assert revised["speaker"]["source"] == "unknown"
    assert revised["uncertain"] and revised["speaker"]["providerSpeakerId"] == "A"


def test_preexisting_native_stream_adapter_uses_actual_diarizing_producer_not_wrapper_false():
    segment=segments(observe(diarization=True,prewrapped=True))[0]
    assert segment["speaker"]["source"] == "unknown" and segment["uncertain"]


def test_preexisting_native_stream_adapter_keeps_default_non_declaring_producer_track_authority():
    segment=segments(observe(sdk_default_capability=True,prewrapped=True))[0]
    assert segment["speaker"]["source"] == "participant_track"


def test_owner_track_refresh_keeps_identity_out_of_display_label():
    room=room_with(microphone())
    tracker=SpeakerSegmentTracker(call_session_id="synthetic-label",**worker._linked_participant_speaker_context(room,"owner"))
    room.remote_participants["owner"].name="owner"
    refresh(tracker,room)
    segment=ingest_track(tracker)[0]
    assert segment["speaker"]["label"] == "You"
    assert segment["speaker"]["participantName"] == "You"
