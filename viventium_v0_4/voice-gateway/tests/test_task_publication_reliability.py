"""UI transport faults cannot replay semantics or hold later cancellation."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch
from livekit.rtc import LocalParticipant
from livekit.rtc import participant as participant_module
from livekit.rtc._ffi_client import FfiQueue
from librechat_llm import LibreChatAuth, LibreChatLLM
from worker import _CallTaskEventPublisher, _publish_bounded_livekit_data
from test_librechat_llm import _CallTaskEventSession, _voice_task_event


def event(seq=1, state="running", task="task_1"):
    return _voice_task_event("event_"+str(seq), seq, state=state, event_type="state") | {"taskId": task}


def test_real_sdk_missing_ack_cannot_hold_cancel_and_cleans_subscription():
    async def run():
        entered=asyncio.Event(); queue=FfiQueue(); semantic=[]
        sdk=SimpleNamespace(queue=queue,request=lambda _:SimpleNamespace(publish_data=SimpleNamespace(async_id=1234)))
        native=SimpleNamespace(_ffi_handle=SimpleNamespace(handle=1))
        class Participant:
            async def publish_data(self,*args,**kwargs):
                entered.set()
                return await LocalParticipant.publish_data(native,*args,**kwargs)
        publisher=_CallTaskEventPublisher(Participant(),call_session_id="call_1",owner_participant_identity="owner")
        async def handler(value):
            semantic.append(value["state"]);publisher.offer(value)
        source=_CallTaskEventSession([event(1),event(2,"cancelling")],marker_first=True)
        llm=LibreChatLLM(origin="http://synthetic.invalid",auth=LibreChatAuth(call_session_id="call_1",call_secret="synthetic",job_id="job",worker_id="worker"),task_event_handler=handler)
        with patch.object(participant_module,"FfiClient",SimpleNamespace(instance=sdk)), patch("librechat_llm.aiohttp.ClientSession",return_value=source), patch("worker._LIVEKIT_DATA_PUBLISH_TIMEOUT_S",.03):
            stream=llm.start_call_task_event_stream()
            assert await llm.wait_call_task_event_stream_ready(timeout_s=.5)
            await asyncio.wait_for(entered.wait(),.5);await asyncio.sleep(.001)
            assert semantic==["running","cancelling"] and llm.is_task_output_suppressed("task_1")
            assert not stream.done() and len(queue._subscribers)==1
            await asyncio.sleep(.04)
            assert len(queue._subscribers)==0 and publisher._pending["task_1"]["sequence"]==2
            await publisher.close();await llm.close_background_continuations()
        assert source.closed and publisher._flush_task is None and not publisher._pending
    asyncio.run(run())


def test_retry_coalesces_new_terminal_without_replaying_semantic_handler():
    async def run():
        calls=[];semantic=[]
        class Participant:
            async def publish_data(self,payload,**kwargs):
                calls.append((json.loads(payload),kwargs))
                if len(calls)==1:raise RuntimeError("synthetic packet failure")
        publisher=_CallTaskEventPublisher(Participant(),call_session_id="call_1",owner_participant_identity="owner")
        async def handler(value):semantic.append(value["sequence"]);publisher.offer(value)
        llm=LibreChatLLM(origin="http://synthetic.invalid",auth=LibreChatAuth(call_session_id="call_1",call_secret="synthetic"),task_event_handler=handler)
        assert await llm._relay_task_event_once(event())
        await asyncio.sleep(.001)
        assert not await llm._relay_task_event_once(event())
        assert await llm._relay_task_event_once(event(3,"cancelled_confirmed"))
        assert not publisher.offer(event(2)) and len(calls)==1
        publisher._not_before=0;publisher.flush_if_due();await asyncio.sleep(.001)
        assert [item[0]["sequence"] for item in calls]==[1,3] and semantic==[1,3]
        assert calls[-1][1]["destination_identities"]==["owner"] and not publisher._pending
        await publisher.close();await llm.close_background_continuations()
    asyncio.run(run())


def test_new_revision_during_publish_survives_old_ack_single_flush_and_close():
    async def run():
        entered=asyncio.Event();release=asyncio.Event();sent=[]
        class Participant:
            async def publish_data(self,payload,**kwargs):
                sent.append(json.loads(payload)["sequence"])
                if len(sent)==1:entered.set();await release.wait()
        publisher=_CallTaskEventPublisher(Participant(),call_session_id="call_1",owner_participant_identity="owner")
        publisher.offer(event());await entered.wait();original=publisher._flush_task
        assert publisher.offer(event(2,"cancelled_confirmed")) and publisher._flush_task is original
        release.set()
        for _ in range(8):await asyncio.sleep(0)
        assert sent==[1,2] and not publisher._pending and not publisher.offer(event())
        await publisher.close()
        assert publisher._flush_task is None and not publisher.offer(event(3))
    asyncio.run(run())


def test_retention_scope_payload_and_close_remain_bounded():
    async def run():
        entered=asyncio.Event()
        class Participant:
            async def publish_data(self,*a,**k):entered.set();await asyncio.Future()
        publisher=_CallTaskEventPublisher(Participant(),call_session_id="call_1",owner_participant_identity="owner",max_tasks=2)
        assert not publisher.offer(event()|{"callSessionId":"foreign"})
        assert not publisher.offer(event()|{"sequence":True})
        assert not publisher.offer(event()|{"detail":"x"*20_000}) and not publisher._pending
        publisher.offer(event(task="first"));await entered.wait()
        publisher.offer(event(task="second"));publisher.offer(event(task="third"))
        assert len(publisher._pending)==2 and len(publisher._latest)==2
        await publisher.close()
        assert publisher._flush_task is None and not publisher._pending
        missing=_CallTaskEventPublisher(Participant(),call_session_id="call_1",owner_participant_identity="")
        assert not missing.offer(event());await missing.close()
    asyncio.run(run())


def test_shared_publish_propagates_close_cancellation():
    async def run():
        entered=asyncio.Event();cancelled=asyncio.Event()
        class Participant:
            async def publish_data(self,*a,**k):
                entered.set()
                try:await asyncio.Future()
                finally:cancelled.set()
        task=asyncio.create_task(_publish_bounded_livekit_data(Participant(),"{}",topic="test",correlation_id="event",destination_identity="owner"))
        await entered.wait();task.cancel()
        try:await task
        except asyncio.CancelledError:pass
        else:raise AssertionError("Shutdown cancellation swallowed")
        assert cancelled.is_set()
    asyncio.run(run())


def test_caption_uses_same_nonblocking_bounded_publisher_and_close_owner():
    async def run():
        entered=asyncio.Event()
        class Participant:
            async def publish_data(self,*a,**k):entered.set();await asyncio.Future()
        publisher=_CallTaskEventPublisher(Participant(),call_session_id="call_1",owner_participant_identity="owner",max_tasks=2)
        segment={"version":1,"callSessionId":"call_1","segmentId":"speaker-1","sequence":1,"revision":0,"text":"Original speech"}
        assert publisher.offer_speaker(segment)
        await entered.wait()
        assert publisher.offer_speaker(segment|{"revision":1})
        assert not publisher.offer_speaker(segment)
        assert publisher.offer(event())
        assert len(publisher._pending)==2 and len(publisher._latest)==2
        await publisher.close()
        assert publisher._flush_task is None and not publisher._pending
    asyncio.run(run())
