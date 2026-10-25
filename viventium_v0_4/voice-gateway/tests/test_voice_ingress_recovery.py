"""Original voice input survives definite non-admission, not ambiguous action replay."""
from __future__ import annotations

import asyncio
import json
import socket
import unittest
from unittest.mock import AsyncMock, Mock, patch
from types import SimpleNamespace

import aiohttp
from aiohttp import web
from livekit.agents.llm import ChatContext, ChatMessage
from librechat_llm import LibreChatAuth, LibreChatLLM, _post_voice_admission_receipt
from speaker_segments import SpeakerSegmentTracker, SPEAKER_CONTEXT_EXTRA_KEY
from worker import AuthoritativeCallModeState, ViventiumVoiceAgent, VoiceEngagementAuthority
from test_worker_turn_handling import _signed_voice_engagement, _verify_synthetic_voice_engagement


class TestVoiceIngressRecovery(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests=[];self.streams=[];self.mode="call";self.status=200;self.prelaunch_failures=0
        self.app=web.Application()
        self.app.router.add_post('/api/viventium/voice/chat',self.chat)
        self.app.router.add_get('/api/viventium/voice/stream/{stream}',self.sse)
        async def safety_state(request):
            return await self.safety_handler(request)
        self.app.router.add_post('/api/viventium/voice/speaker-session-state',safety_state)
        async def ambient(request):
            return await self.ambient_handler(request)
        self.app.router.add_post('/api/viventium/voice/ambient-transcript',ambient)
        self.runner=web.AppRunner(self.app);await self.runner.setup()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));self.port=sock.getsockname()[1]
        self.origin=f'http://127.0.0.1:{self.port}'
        self.llm=LibreChatLLM(origin=self.origin,auth=LibreChatAuth(call_session_id='call_1',call_secret='synthetic'),timeout_s=2)
        self.llm._start_task_continuation=Mock()

    async def asyncTearDown(self):
        for stream in self.streams:await stream.aclose()
        await self.llm.aclose();await self.runner.cleanup()

    async def chat(self,request):
        body=await request.json();self.requests.append(body)
        if self.prelaunch_failures:
            self.prelaunch_failures-=1
            return web.json_response({'code':'voice_turn_authority_unavailable','retryable':True},status=503)
        if self.status!=200:return web.json_response({'error':'synthetic rejection'},status=self.status)
        if self.mode in ('listen_only','wing'):
            return web.json_response({'status':'listen_only' if self.mode=='listen_only' else 'wing_passive','listenOnly':True})
        return web.json_response({'streamId':body['streamId'],'taskId':'task-'+str(len(self.requests)),
            'logical_turn_id':'turn-'+str(len(self.requests)),'revision':1})

    async def sse(self,request):
        value={'final':True,'responseMessage':{'messageId':'answer','content':[{'type':'text','text':'Four.'}]}}
        return web.Response(text='data: '+json.dumps(value)+'\n\n',content_type='text/event-stream')

    def source(self,identity,text):
        tracker=SpeakerSegmentTracker(call_session_id='call_1',participant_identity='owner',track_sid='TR_owner',owner_signed=True)
        tracker.ingest(transcript=text,is_final=True,created_at=100,provider_speaker_id=None,allow_owner_participant_track=True)
        mode=AuthoritativeCallModeState();mode.suspend()
        refresh=AsyncMock(side_effect=AssertionError('Redundant foreground authority RPC'))
        finalized=AsyncMock()
        agent=ViventiumVoiceAgent(instructions='Synthetic',speaker_tracker=tracker,authoritative_mode_state=mode,
            on_finalized_speaker_context=finalized,refresh_turn_authority=refresh,defer_turn_admission=True)
        message=ChatMessage(id=identity,role='user',content=[text])
        return agent,message,refresh

    async def stream(self,identity,text):
        agent,message,refresh=self.source(identity,text)
        await agent.on_user_turn_completed(ChatContext.empty(),message)
        refresh.assert_not_awaited()
        result=self.llm.chat(chat_ctx=ChatContext(items=[message]));self.streams.append(result)
        return result,message

    def refusal_log(self,event):
        def log(message,*args,**kwargs):
            if 'admission_connect_retry' in message:event.set()
        return log

    async def test_original_first_speech_survives_17_second_core_outage_then_next_turn_answers(self):
        refused=asyncio.Event()
        self.llm._timeout_s=25.0
        async def restore_after_drill_window():
            await asyncio.wait_for(refused.wait(),.5)
            await asyncio.sleep(17.7)
            await web.TCPSite(self.runner,'127.0.0.1',self.port).start()
        with patch('librechat_llm.logger.warning',side_effect=self.refusal_log(refused)):
            stream,message=await self.stream('original','What is 2 plus 2?')
            restore=asyncio.create_task(restore_after_drill_window())
            chunks=[part.delta.content async for part in stream if part.delta and part.delta.content]
            await restore
        self.assertEqual(chunks,['Four.'])
        self.assertEqual(len(self.requests),1)
        self.assertEqual(self.requests[0]['sourceEventId'],'voice:call_1:item:original')
        self.assertEqual(self.requests[0]['speakerSegments'],message.extra[SPEAKER_CONTEXT_EXTRA_KEY]['speakerSegments'])
        next_stream,_=await self.stream('next','And again?')
        self.assertEqual([part.delta.content async for part in next_stream if part.delta and part.delta.content],['Four.'])
        self.assertEqual([item['text'] for item in self.requests],['What is 2 plus 2?','And again?'])

    async def test_a_b_c_interruption_keeps_original_order_and_bodies_during_outage(self):
        refused=asyncio.Event()
        with patch('librechat_llm.logger.warning',side_effect=self.refusal_log(refused)):
            first,_=await self.stream('A','A: exact α\nfirst input')
            await asyncio.wait_for(refused.wait(),.5)
            await first.aclose()
            second,_=await self.stream('B','B: keep the original')
            await asyncio.sleep(.01);await second.aclose()
            third,_=await self.stream('C','C: latest question')
            await asyncio.sleep(.01)
            self.assertEqual(self.requests,[])
            await web.TCPSite(self.runner,'127.0.0.1',self.port).start()
            chunks=[part.delta.content async for part in third if part.delta and part.delta.content]
        self.assertEqual([item['sourceEventId'] for item in self.requests],
                         ['voice:call_1:item:A','voice:call_1:item:B','voice:call_1:item:C'])
        self.assertEqual([item['text'] for item in self.requests],['A: exact α\nfirst input','B: keep the original','C: latest question'])
        self.assertEqual(chunks,['Four.'])
        self.assertIsNotNone(first._presentation.interrupted_binding)
        self.assertEqual(len({item['streamId'] for item in self.requests}),3)

    async def test_end_during_connect_refusal_cancels_the_same_admission_without_late_post(self):
        refused=asyncio.Event()
        with patch('librechat_llm.logger.warning',side_effect=self.refusal_log(refused)):
            stream,_=await self.stream('end','Original unadmitted input')
            await asyncio.wait_for(refused.wait(),.5)
            await self.llm.close_background_continuations()
            await web.TCPSite(self.runner,'127.0.0.1',self.port).start()
            await asyncio.sleep(.03)
        self.assertEqual(self.requests,[])
        self.assertTrue(stream._presentation.admission_task.done())
        self.assertFalse(self.llm._background_continuations)

    async def test_listen_only_change_during_outage_is_decided_by_fresh_core(self):
        refused=asyncio.Event()
        with patch('librechat_llm.logger.warning',side_effect=self.refusal_log(refused)):
            stream,_=await self.stream('mode-change','Save this without an action')
            await asyncio.wait_for(refused.wait(),.5)
            self.mode='listen_only'
            await web.TCPSite(self.runner,'127.0.0.1',self.port).start()
            chunks=[part.delta.content async for part in stream if part.delta and part.delta.content]
        self.assertEqual(chunks,[])
        self.assertEqual(len(self.requests),1)

    async def test_wing_passive_and_revocation_never_replay_or_create_answer(self):
        await web.TCPSite(self.runner,'127.0.0.1',self.port).start()
        self.mode='wing'
        stream,_=await self.stream('wing','Room speech')
        self.assertEqual([part async for part in stream],[])
        self.status=403
        revoked,_=await self.stream('revoked','Do work')
        chunks=[part.delta.content async for part in revoked if part.delta and part.delta.content]
        self.assertEqual(chunks,["This call's connection is no longer authorized. Please reconnect the call."])
        self.assertEqual(len(self.requests),2)

    async def test_preflight_transport_retry_is_owned_by_same_admission_and_end_cleans_it(self):
        entered=asyncio.Event();release=asyncio.Event();prepared=[]
        async def prepare(context):
            prepared.append(context)
            entered.set()
            if not release.is_set():raise aiohttp.ClientConnectionError('synthetic revision outage')
            return True
        self.llm.set_turn_admission_handler(prepare)
        await web.TCPSite(self.runner,'127.0.0.1',self.port).start()
        stream,_=await self.stream('preflight','Original source')
        await entered.wait();await stream.aclose()
        self.assertEqual(self.requests,[])
        release.set()
        await asyncio.wait_for(stream._presentation.admission_task,1.5)
        self.assertEqual(len(self.requests),1)
        self.assertEqual(self.requests[0]['sourceEventId'],'voice:call_1:item:preflight')
        self.assertTrue(prepared)

    async def test_real_shared_mic_safety_post_retries_before_same_source_admission(self):
        safety=[];order=[]
        async def state(request):
            safety.append(await request.json());order.append('safety')
            return web.json_response({'accepted':True},status=503 if len(safety)<=3 else 200)
        self.safety_handler=state
        tombstone={'version':1,'callSessionId':'call_1','revision':1,
                   'attributionState':'shared_mic_unverified','detectedAt':'2026-10-24T12:00:00Z'}
        async def prepare(context):
            await self.llm.post_speaker_segment_revisions([],session_state=tombstone)
            order.append('admit')
            return True
        self.llm.set_turn_admission_handler(prepare)
        await web.TCPSite(self.runner,'127.0.0.1',self.port).start()
        stream,_=await self.stream('safety-source','Preserve original speech')
        self.assertEqual([part.delta.content async for part in stream if part.delta and part.delta.content],['Four.'])
        self.assertEqual(order,['safety','safety','safety','safety','admit'])
        self.assertEqual(len(self.requests),1)
        self.assertEqual(self.requests[0]['sourceEventId'],'voice:call_1:item:safety-source')
        self.assertTrue(all(item==tombstone for item in safety))

    async def test_preflight_revocation_is_not_retried_and_has_existing_authorization_notice(self):
        from librechat_llm import _NonRetryableVoiceIngressError
        attempts=[]
        async def prepare(context):
            attempts.append(context)
            raise _NonRetryableVoiceIngressError('synthetic revoked safety authority',status=403)
        self.llm.set_turn_admission_handler(prepare)
        await web.TCPSite(self.runner,'127.0.0.1',self.port).start()
        stream,_=await self.stream('revoked-preflight','Original unadmitted request')
        chunks=[part.delta.content async for part in stream if part.delta and part.delta.content]
        self.assertEqual(chunks,["This call's connection is no longer authorized. Please reconnect the call."])
        self.assertEqual(len(attempts),1)
        self.assertEqual(self.requests,[])

    async def test_end_while_required_preflight_is_unavailable_drops_no_new_post(self):
        entered=asyncio.Event()
        async def prepare(context):
            entered.set()
            raise aiohttp.ClientConnectionError('synthetic required preflight outage')
        self.llm.set_turn_admission_handler(prepare)
        await web.TCPSite(self.runner,'127.0.0.1',self.port).start()
        stream,_=await self.stream('end-preflight','Original not admitted')
        await entered.wait()
        await self.llm.close_background_continuations()
        self.assertTrue(stream._presentation.admission_task.done())
        self.assertEqual(self.requests,[])

    async def test_suspended_wing_keeps_preflight_choice_without_action_authority(self):
        mode=AuthoritativeCallModeState();mode.apply('wing');mode.suspend()
        self.assertEqual(mode.last_observed_mode,'wing')
        self.assertIsNone(mode.mode)
        self.assertFalse(mode.allows_agent_dispatch)

    async def test_typed_prelaunch_503_retries_exact_body_once(self):
        self.prelaunch_failures=1
        await web.TCPSite(self.runner,'127.0.0.1',self.port).start()
        stream,_=await self.stream('authority-temporary','Original words α')
        chunks=[part.delta.content async for part in stream if part.delta and part.delta.content]
        self.assertEqual(chunks,['Four.'])
        self.assertEqual(len(self.requests),2)
        self.assertEqual(self.requests[0],self.requests[1])

    async def test_a_then_empty_then_c_cannot_overtake_retained_original(self):
        refused=asyncio.Event()
        with patch('librechat_llm.logger.warning',side_effect=self.refusal_log(refused)):
            first,_=await self.stream('A-empty','A original')
            await asyncio.wait_for(refused.wait(),.5);await first.aclose()
            empty=self.llm.chat(chat_ctx=ChatContext(items=[ChatMessage(id='empty',role='user',content=[''])]));self.streams.append(empty)
            self.assertEqual([part async for part in empty],[])
            third,_=await self.stream('C-empty','C original')
            await asyncio.sleep(.01);self.assertEqual(self.requests,[])
            await web.TCPSite(self.runner,'127.0.0.1',self.port).start()
            self.assertEqual([part.delta.content async for part in third if part.delta and part.delta.content],['Four.'])
        self.assertEqual([body['text'] for body in self.requests],['A original','C original'])

    async def test_inflight_interim_tombstone_is_an_admission_barrier_and_survives_source_cancel(self):
        entered=asyncio.Event();release=asyncio.Event()
        async def safety(*args,**kwargs):
            entered.set();await release.wait();return {'accepted':[]}
        self.llm.post_speaker_segment_revisions=AsyncMock(side_effect=safety)
        task=self.llm.queue_speaker_segment_revisions([],session_state={'synthetic':'state'})
        await entered.wait()
        await web.TCPSite(self.runner,'127.0.0.1',self.port).start()
        stream,_=await self.stream('barrier-source','Do not outrun safety')
        await asyncio.sleep(.01);await stream.aclose()
        self.assertFalse(task.cancelled());self.assertEqual(self.requests,[])
        release.set();await asyncio.wait_for(stream._presentation.admission_task,1)
        self.assertEqual(len(self.requests),1)

    async def test_cancelled_tombstone_returns_to_existing_tracker_and_call_end_cancels_source(self):
        tracker=SpeakerSegmentTracker(call_session_id='call_1')
        state={'version':1,'callSessionId':'call_1','revision':1,'attributionState':'shared_mic_unverified'}
        entered=asyncio.Event()
        async def safety(*args,**kwargs):entered.set();await asyncio.Future()
        self.llm.post_speaker_segment_revisions=AsyncMock(side_effect=safety)
        task=self.llm.queue_speaker_segment_revisions([],session_state=state)
        self.llm.retain_speaker_safety_delivery(task,on_unconfirmed=lambda:tracker.requeue_session_state_changes([state]))
        await entered.wait()
        stream,_=await self.stream('end-safety','Retained source')
        await self.llm.close_background_continuations()
        self.assertTrue(task.cancelled())
        self.assertEqual(tracker.pop_session_state_changes(),[state])
        self.assertEqual(self.requests,[])

    async def test_wing_and_listen_only_never_queue_admission_failure_speech(self):
        await web.TCPSite(self.runner,'127.0.0.1',self.port).start()
        self.status=503
        self.llm.set_admission_notice_gate(lambda:False)
        for identity in ('wing-notice','listen-only-notice'):
            stream,_=await self.stream(identity,'Keep silent')
            self.assertEqual([part.delta.content async for part in stream if part.delta and part.delta.content],[])
        self.assertEqual(len(self.requests),2)

    async def test_consumed_wing_receipt_is_reused_after_later_authority_get_recovers(self):
        now=1787659200001
        authority=VoiceEngagementAuthority(call_session_id='call_1',owner_participant_identity='owner',
            verify_receipt=AsyncMock(side_effect=_verify_synthetic_voice_engagement),clock_ms=lambda:now,wait_timeout_s=0)
        receipt=_signed_voice_engagement()
        packet=SimpleNamespace(topic='viventium.voice.engagement.v1',participant=SimpleNamespace(identity='owner'),data=json.dumps(receipt).encode())
        self.assertTrue(authority.accept_packet(packet))
        segment={'callSessionId':'call_1','segmentId':'segment_000001','turnId':'turn_000001',
            'revision':1,'isFinal':True,'speaker':{'actorTrust':'owner_participant','attribution':'verified','participantIdentity':'owner'}}
        context={'speakerSegments':[segment]};reads=[]
        async def fresh(value):
            reads.append(True)
            if len(reads)==2:raise aiohttp.ClientConnectionError('synthetic fresh GET outage after consumed receipt')
            return {'version':1,'callSessionId':'call_1','mode':'wing','status':'listening','speakerSegments':[segment]}
        mode=AuthoritativeCallModeState();mode.apply('wing')
        agent=ViventiumVoiceAgent(instructions='Synthetic',authoritative_mode_state=mode,
            voice_engagement_authority=authority,refresh_turn_authority=fresh,defer_turn_admission=True)
        with self.assertRaises(aiohttp.ClientConnectionError):await agent.prepare_turn_admission(context)
        self.assertEqual(context['voiceEngagement'],receipt)
        self.assertIn('turn_000001',authority._consumed_turns)
        await agent.prepare_turn_admission(context)
        self.assertEqual(context['voiceEngagement'],receipt)
        self.assertEqual(authority._verify_receipt.await_count,1)
        self.assertEqual(len(reads),4)

    async def test_ambiguous_read_timeout_after_server_received_input_is_never_reposted(self):
        bodies=[]
        async def slow(request):
            bodies.append(await request.json());await asyncio.sleep(.08)
            return web.json_response({'streamId':'accepted','taskId':'task'})
        app=web.Application();app.router.add_post('/chat',slow)
        runner=web.AppRunner(app);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
        port=site._server.sockets[0].getsockname()[1]
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=.02)) as session:
                with self.assertRaises(asyncio.TimeoutError):
                    await _post_voice_admission_receipt(session,f'http://127.0.0.1:{port}/chat',headers={},
                        body={'text':'Exact source','sourceEventId':'one-source'},is_call_current=lambda:True)
            self.assertEqual(len(bodies),1)
        finally:await runner.cleanup()


class TestAmbientSourceRecovery(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = TestVoiceIngressRecovery.asyncSetUp
    asyncTearDown = TestVoiceIngressRecovery.asyncTearDown
    chat = TestVoiceIngressRecovery.chat
    sse = TestVoiceIngressRecovery.sse
    source = TestVoiceIngressRecovery.source
    stream = TestVoiceIngressRecovery.stream

    def guest_source(self):
        return {'version':1,'callSessionId':'call_1','mode':'wing','ingressKind':'ambient_participant',
                'turnId':'guest-turn','segments':[{'version':1,'callSessionId':'call_1',
                'segmentId':'guest-segment','revision':1,'turnId':'guest-turn',
                'text':'Original guest context','speaker':{'actorTrust':'authenticated_participant',
                'participantIdentity':'guest','attribution':'unverified'}}]}

    async def test_guest_refusal_then_restore_retains_exact_source_without_holding_owner(self):
        received=[];refused=asyncio.Event()
        async def ambient(request):
            received.append(await request.json());return web.json_response({'accepted':['guest-segment']})
        self.ambient_handler=ambient
        def warning(message,*args,**kwargs):
            if 'delivery_retry' in message:refused.set()
        payload=self.guest_source()
        with patch('librechat_llm.logger.warning',side_effect=warning):
            delivery=self.llm.queue_ambient_transcript(payload)
            caller=asyncio.ensure_future(asyncio.shield(delivery))
            await asyncio.wait_for(refused.wait(),1)
            caller.cancel()
            await asyncio.gather(caller,return_exceptions=True)
            self.assertFalse(delivery.done())
            self.assertFalse(self.llm._speaker_delivery_tasks)
            await web.TCPSite(self.runner,'127.0.0.1',self.port).start()
            stream,_=await self.stream('owner-with-guest','What is 2 plus 2?')
            self.assertEqual([part.delta.content async for part in stream if part.delta and part.delta.content],['Four.'])
            await asyncio.wait_for(delivery,1.5)
        self.assertEqual(received,[payload]);self.assertEqual(len(self.requests),1)
        self.assertEqual(self.requests[0]['sourceEventId'],'voice:call_1:item:owner-with-guest')
        self.assertNotIn('voiceEngagement',received[0]);self.assertFalse(self.llm._background_continuations)

    async def test_guest_end_during_outage_cancels_retention_without_late_post(self):
        refused=asyncio.Event();received=[]
        async def ambient(request):
            received.append(await request.json());return web.json_response({'accepted':[]})
        self.ambient_handler=ambient
        def warning(message,*args,**kwargs):
            if 'delivery_retry' in message:refused.set()
        with patch('librechat_llm.logger.warning',side_effect=warning):
            delivery=self.llm.queue_ambient_transcript(self.guest_source())
            await asyncio.wait_for(refused.wait(),1)
            await self.llm.close_background_continuations()
            await web.TCPSite(self.runner,'127.0.0.1',self.port).start()
            await asyncio.sleep(.02)
        self.assertTrue(delivery.cancelled());self.assertEqual(received,[])
        self.assertFalse(self.llm._background_continuations)

    async def test_guest_unknown_response_retries_same_idempotent_evidence_not_action(self):
        attempts=[];saved={}
        async def ambient(request):
            body=await request.json();attempts.append(body)
            for segment in body['segments']:saved[(segment['segmentId'],segment['revision'])]=segment
            if len(attempts)==1:
                request.transport.close()
                return web.Response()
            return web.json_response({'accepted':['guest-segment']})
        self.ambient_handler=ambient
        await web.TCPSite(self.runner,'127.0.0.1',self.port).start()
        await self.llm.queue_ambient_transcript(self.guest_source())
        self.assertEqual(len(attempts),2);self.assertEqual(attempts[0],attempts[1]);self.assertEqual(len(saved),1)
        self.assertEqual(self.requests,[])
        await self.llm.queue_ambient_transcript(self.guest_source())
        self.assertEqual(len(attempts),2)

    async def test_guest_revocation_is_final_and_deadline_releases_retention(self):
        calls=[]
        async def ambient(request):
            calls.append(await request.json());return web.json_response({'error':'revoked'},status=403)
        self.ambient_handler=ambient
        await web.TCPSite(self.runner,'127.0.0.1',self.port).start()
        with self.assertRaises(Exception):await self.llm.queue_ambient_transcript(self.guest_source())
        self.assertEqual(len(calls),1)
        await self.runner.cleanup();self.llm._timeout_s=.04
        with self.assertRaises(asyncio.TimeoutError):await self.llm.queue_ambient_transcript(self.guest_source())
        await asyncio.sleep(0)
        self.assertFalse(self.llm._background_continuations)
