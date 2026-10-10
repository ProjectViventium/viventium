import asyncio, unittest
from types import MethodType
from unittest import mock
import test_worker_followup_scheduler as fixtures
_DummySession = fixtures._DummySession
class TestLateCortexWake(unittest.IsolatedAsyncioTestCase):
    _build_scheduler = fixtures.TestCortexFollowupScheduler._build_scheduler
    _callwide_event = fixtures.TestCortexFollowupScheduler._callwide_event
    _callwide_llm = fixtures.TestCortexFollowupScheduler._callwide_llm
    def event(self, **changes):
        return {**self._callwide_event(phase='follow_up',type='progress',
            source={'id':'stored-child'},createdAt='2026-01-01T00:00:00Z',turnId='synthetic-turn'),**changes}
    async def setup_late(self):
        session=_DummySession(); scheduler=self._build_scheduler(session=session)
        state={'ready':False,'fetches':0}
        async def fetch(_self,_http,_message,**_scope):
            state['fetches']+=1
            return {'insights':[{'cortex_id':'synthetic','insight':'INTERNAL MUST STAY SILENT'}],
                'followUp': {'messageId':'stored-child','text':'Main authored late result.'} if state['ready'] else None}
        scheduler._fetch_cortex=MethodType(fetch,scheduler)
        await scheduler.schedule('main_anchor',[], '', cortex_expected=True,
            task_ref={'taskId':'parent_task','streamId':'main_stream'}, trace_id='main_stream')
        self.assertEqual(session.say_calls,[])
        state['ready']=True
        getattr(scheduler,'set_task_stream_connected',lambda _connected:None)(True)
        return session,scheduler,state
    async def test_late_stored_child_after_grace_uses_existing_fetch_and_audio_ack_once(self):
        session,scheduler,state=await self.setup_late()
        scheduler._trace_handler=mock.AsyncMock(return_value=True)
        llm=self._callwide_llm(scheduler)
        self.assertTrue(await llm._relay_task_event_once(self.event()))
        await asyncio.gather(*getattr(scheduler,"_cortex_wake_tasks",set()))
        self.assertEqual([c['text'] for c in session.say_calls],['Main authored late result.'])
        self.assertEqual(scheduler._trace_handler.await_count,0)
        handle=session.speech_handles[0]; scheduler.note_started_playout(handle);handle.complete()
        await asyncio.sleep(0)
        self.assertEqual([c.args[2] for c in scheduler._trace_handler.await_args_list],
            ['audio.started','tts.completed','audio.completed'])
        await llm._relay_task_event_once(self.event(eventId='snapshot-again',type='snapshot',sequence=5))
        await asyncio.sleep(0)
        self.assertEqual(len(session.say_calls),1)
        self.assertGreaterEqual(state['fetches'],2)
        await scheduler.close()
    async def test_durable_snapshot_wakes_without_open_generation_sse(self):
        session,scheduler,_=await self.setup_late()
        llm=self._callwide_llm(scheduler)
        await llm._relay_task_event_once(self.event(type='snapshot'))
        await asyncio.gather(*getattr(scheduler,"_cortex_wake_tasks",set()))
        self.assertEqual(len(session.say_calls),1);await scheduler.close()
    async def test_wake_and_original_poll_race_speaks_exact_child_once(self):
        session=_DummySession();scheduler=self._build_scheduler(session=session)
        entered=asyncio.Event();release=asyncio.Event()
        async def fetch(_self,_http,_message,**_scope):
            entered.set();await release.wait()
            return {'followUp':{'messageId':'stored-child','text':'Main authored result.'}}
        scheduler._fetch_cortex=MethodType(fetch,scheduler)
        original=scheduler.schedule('main_anchor',[], '',cortex_expected=True)
        await entered.wait();llm=self._callwide_llm(scheduler)
        await llm._relay_task_event_once(self.event())
        release.set();await asyncio.gather(original,*getattr(scheduler,"_cortex_wake_tasks",set()))
        self.assertEqual(len(session.say_calls),1);await scheduler.close()
    async def test_wrong_call_owner_state_and_suppressed_parent_never_fetch(self):
        for changes in ({'callSessionId':'foreign'},{'owner':{'kind':'glasshive_run','id':'run'}},
            {'owner':{'kind':'generation_job','id':'foreign'}},{'state':'cancelled_confirmed'},
            {'resultMessageId':''}):
            session,scheduler,state=await self.setup_late();before=state['fetches']
            scheduler.on_task_event(self.event(**changes),is_task_suppressed=lambda _:False)
            await asyncio.sleep(0);self.assertEqual(state['fetches'],before);self.assertEqual(session.say_calls,[])
            await scheduler.close()
        session,scheduler,state=await self.setup_late();before=state['fetches']
        scheduler.on_task_event(self.event(),is_task_suppressed=lambda _:True)
        await asyncio.sleep(0);self.assertEqual(state['fetches'],before);await scheduler.close()
    async def test_newer_source_and_closed_call_remain_silent(self):
        session,scheduler,state=await self.setup_late();before=state['fetches']
        scheduler._seq+=1
        scheduler.on_task_event(self.event(),is_task_suppressed=lambda _:False)
        await asyncio.sleep(0);self.assertEqual(state['fetches'],before)
        await scheduler.close()
        scheduler.on_task_event(self.event(eventId='after-end'),is_task_suppressed=lambda _:False)
        self.assertIsNone(scheduler.schedule('main_anchor',[], '',cortex_expected=True))
        self.assertEqual(session.say_calls,[])
    async def test_published_id_does_not_speak_another_child_or_raw_insight(self):
        session,scheduler,state=await self.setup_late()
        scheduler.on_task_event(self.event(source={'id':'foreign-child'}),is_task_suppressed=lambda _:False)
        await asyncio.gather(*getattr(scheduler,"_cortex_wake_tasks",set()))
        self.assertEqual(session.say_calls,[]);await scheduler.close()
    async def test_listen_only_does_not_speak_or_ack_completed(self):
        session,scheduler,state=await self.setup_late();before=state['fetches'];scheduler.set_mode('listen_only')
        scheduler._trace_handler=mock.AsyncMock(return_value=True)
        scheduler.on_task_event(self.event(),is_task_suppressed=lambda _:False)
        await asyncio.gather(*getattr(scheduler,"_cortex_wake_tasks",set()));await scheduler.close()
        self.assertEqual(session.say_calls,[]);self.assertEqual(state['fetches'],before)
        self.assertNotIn('audio.completed',[c.args[2] for c in scheduler._trace_handler.await_args_list])

    async def test_exact_stopped_child_snapshot_does_not_replay_but_other_child_can_wake(self):
        session,scheduler,state=await self.setup_late();before=state['fetches']
        scheduler.on_task_event(self.event(presentation={'ref':'stored-child','state':'stop_requested','startedAtMs':123}),
            is_task_suppressed=lambda _:False)
        await asyncio.sleep(0);self.assertEqual(state['fetches'],before);self.assertEqual(session.say_calls,[])
        await scheduler.close()
    async def test_wake_does_not_cancel_an_unrelated_cortex_poll(self):
        session,scheduler,_=await self.setup_late()
        entered=asyncio.Event();block=asyncio.Event()
        async def fetch(_self,_http,message,**_scope):
            if message=='newer-anchor':entered.set();await block.wait();return None
            return {'followUp':{'messageId':'stored-child','text':'Main authored result.'}}
        scheduler._fetch_cortex=MethodType(fetch,scheduler)
        unrelated=scheduler.schedule('newer-anchor',[], '',cortex_expected=True)
        await entered.wait();scheduler._cortex_contexts.pop('main_anchor',None)
        scheduler.on_task_event(self.event(),is_task_suppressed=lambda _:False)
        await asyncio.gather(*scheduler._cortex_wake_tasks)
        self.assertFalse(unrelated.done());self.assertEqual(len(session.say_calls),0)
        await scheduler.close()
    async def test_close_cancels_a_wake_before_fetch_returns(self):
        session,scheduler,_=await self.setup_late();entered=asyncio.Event();block=asyncio.Event()
        async def fetch(_self,_http,message,**_scope):entered.set();await block.wait();return {'followUp':{'messageId':'stored-child','text':'Too late.'}}
        scheduler._fetch_cortex=MethodType(fetch,scheduler)
        scheduler.on_task_event(self.event(),is_task_suppressed=lambda _:False)
        await entered.wait();await scheduler.close();block.set();await asyncio.sleep(0)
        self.assertEqual(session.say_calls,[]);self.assertEqual(scheduler._cortex_wake_tasks,set())

    async def test_unavailable_authoritative_mode_abstains_before_accepting_fetch(self):
        session,scheduler,state=await self.setup_late();before=state['fetches']
        scheduler.suspend_until_authoritative()
        scheduler.on_task_event(self.event(),is_task_suppressed=lambda _:False)
        await asyncio.gather(*scheduler._cortex_wake_tasks)
        self.assertEqual(state['fetches'],before);self.assertEqual(session.say_calls,[])
        await scheduler.close()
    async def test_canonical_context_binds_actual_trace_http_without_saved_generation_context(self):
        from librechat_llm import LibreChatAuth, LibreChatLLM
        import test_librechat_llm as llm_fixtures
        session,scheduler,state=await self.setup_late()
        scheduler._auth=LibreChatAuth(call_session_id='call_123',call_secret='synthetic',job_id='job',worker_id='worker')
        llm=LibreChatLLM(origin='http://example.test',auth=scheduler._auth)
        scheduler._trace_handler=llm.record_followup_presentation
        context={'callSessionId':'call_123','taskId':'parent_task','streamId':'main_stream','turnId':'canonical-turn'}
        async def fetch(_self,_http,_message,**scope):
            self.assertEqual(scope,{'followup_message_id':'stored-child'})
            return {'followUp':{'messageId':'stored-child','text':'Main authored result.','presentationContext':context}}
        scheduler._fetch_cortex=MethodType(fetch,scheduler)
        transport=llm_fixtures._FakeDeliveryAckSession()
        with mock.patch('librechat_llm.aiohttp.ClientSession',return_value=transport):
            scheduler.on_task_event(self.event(),is_task_suppressed=lambda _:False)
            await asyncio.gather(*scheduler._cortex_wake_tasks)
            self.assertEqual(transport.post_calls,[])
            handle=session.speech_handles[0];scheduler.note_started_playout(handle,3000);handle.complete()
            await asyncio.sleep(0);await scheduler.close()
        bodies=[c[2]['json'] for c in transport.post_calls]
        self.assertEqual([b['stage'] for b in bodies],['audio.started','tts.completed','audio.completed'])
        for body in bodies:
            self.assertEqual(body['turnId'],'canonical-turn');self.assertEqual(body['taskId'],'parent_task')
            self.assertEqual(body['streamId'],'main_stream');self.assertEqual(body['presentationRef'],'stored-child')
    async def test_foreign_or_incomplete_accepted_context_cannot_play_or_post_ack(self):
        for change in ({'callSessionId':'foreign'},{'taskId':'foreign'},{'streamId':'foreign'},{'turnId':''}):
            session,scheduler,_=await self.setup_late()
            context={'callSessionId':'call_123','taskId':'parent_task','streamId':'main_stream','turnId':'canonical-turn',**change}
            async def fetch(_self,_http,_message,**scope):
                return {'followUp':{'messageId':'stored-child','text':'Must not play.','presentationContext':context}}
            scheduler._fetch_cortex=MethodType(fetch,scheduler)
            scheduler._trace_handler=mock.AsyncMock()
            scheduler.on_task_event(self.event(),is_task_suppressed=lambda _:False)
            await asyncio.gather(*scheduler._cortex_wake_tasks);await scheduler.close()
            self.assertEqual(session.say_calls,[]);scheduler._trace_handler.assert_not_awaited()

    async def test_transient_authority_loss_can_rearm_same_child_after_snapshot(self):
        session,scheduler,state=await self.setup_late()
        scheduler.suspend_until_authoritative()
        scheduler.on_task_event(self.event(),is_task_suppressed=lambda _:False)
        await asyncio.gather(*scheduler._cortex_wake_tasks)
        self.assertNotIn(('main_anchor','stored-child'),scheduler._cortex_wake_pairs)
        scheduler.set_mode('call')
        scheduler.on_task_event(self.event(type='snapshot'),is_task_suppressed=lambda _:False)
        await asyncio.gather(*scheduler._cortex_wake_tasks)
        self.assertEqual(len(session.say_calls),1)
        self.assertIn(('main_anchor','stored-child'),scheduler._cortex_wake_pairs)
        await scheduler.close()

    async def test_failed_fetch_window_can_rearm_without_a_retry_controller(self):
        session,scheduler,state=await self.setup_late()
        scheduler._timeout_s=.01
        fetches=0
        async def unavailable(_self,_http,_message,**scope):
            nonlocal fetches
            fetches+=1
            return None
        scheduler._fetch_cortex=MethodType(unavailable,scheduler)
        scheduler.on_task_event(self.event(),is_task_suppressed=lambda _:False)
        await asyncio.gather(*scheduler._cortex_wake_tasks)
        self.assertGreater(fetches,0)
        self.assertEqual(session.say_calls,[])
        self.assertNotIn(('main_anchor','stored-child'),scheduler._cortex_wake_pairs)
        async def available(_self,_http,_message,**scope):
            return {'followUp':{'messageId':'stored-child','text':'Main authored recovered result.'}}
        scheduler._fetch_cortex=MethodType(available,scheduler)
        scheduler.on_task_event(self.event(type='snapshot'),is_task_suppressed=lambda _:False)
        await asyncio.gather(*scheduler._cortex_wake_tasks)
        self.assertEqual([c['text'] for c in session.say_calls],['Main authored recovered result.'])
        await scheduler.close()

    async def test_missing_original_context_cannot_promote_historical_child_to_new_turn(self):
        session,scheduler,state=await self.setup_late();before=state['fetches']
        scheduler._cortex_contexts.clear()
        scheduler._seq+=1
        scheduler.on_task_event(self.event(type='snapshot'),is_task_suppressed=lambda _:False)
        await asyncio.sleep(0)
        self.assertEqual(state['fetches'],before);self.assertEqual(session.say_calls,[])
        self.assertEqual(scheduler._cortex_wake_pairs,{})
        await scheduler.close()

    async def test_original_presentation_guard_supersedes_without_sequence_change(self):
        session,scheduler,state=await self.setup_late();before=state['fetches']
        seq,_,trace=scheduler._cortex_contexts['main_anchor']
        scheduler._cortex_contexts['main_anchor']=(seq,lambda:False,trace)
        scheduler.on_task_event(self.event(type='snapshot'),is_task_suppressed=lambda _:False)
        await asyncio.sleep(0)
        self.assertEqual(state['fetches'],before);self.assertEqual(session.say_calls,[])
        await scheduler.close()

    async def test_wing_preserves_existing_speakable_mode_and_multiple_children_are_exact(self):
        session,scheduler,state=await self.setup_late();scheduler.set_mode('wing')
        requested=[]
        async def fetch(_self,_http,_message,**scope):
            child=scope['followup_message_id'];requested.append(child)
            return {'followUp':{'messageId':child,'text':'Main authored '+child+'.'}}
        scheduler._fetch_cortex=MethodType(fetch,scheduler)
        for child in ('stored-child','second-child'):
            scheduler.on_task_event(self.event(source={'id':child}),is_task_suppressed=lambda _:False)
        await asyncio.gather(*scheduler._cortex_wake_tasks)
        self.assertCountEqual(requested,['stored-child','second-child'])
        self.assertCountEqual([c['text'] for c in session.say_calls],
            ['Main authored stored-child.','Main authored second-child.'])
        scheduler.on_task_event(self.event(type='snapshot'),is_task_suppressed=lambda _:False)
        await asyncio.sleep(0);self.assertEqual(len(session.say_calls),2)
        await scheduler.close()

    async def test_durable_snapshot_recovers_both_publications_after_event_stream_gap(self):
        session,scheduler,state=await self.setup_late()
        requested=[]
        async def fetch(_self,_http,_message,**scope):
            child=scope['followup_message_id'];requested.append(child)
            if child=='citation-id':return {'followUp':None}
            return {'followUp':{'messageId':child,'text':'Main authored '+child+'.'}}
        scheduler._fetch_cortex=MethodType(fetch,scheduler)
        scheduler._timeout_s=.01
        scheduler.on_task_event(self.event(type='snapshot',source={'id':'second-child'},
            sources=[{'id':'stored-child'},{'id':'second-child'}, {'id':'citation-id'},
              {'url':'https://example.test/source','title':'Citation'}]),is_task_suppressed=lambda _:False)
        await asyncio.gather(*scheduler._cortex_wake_tasks)
        self.assertCountEqual([c['text'] for c in session.say_calls],
            ['Main authored stored-child.','Main authored second-child.'])
        self.assertCountEqual(requested,['stored-child','second-child','citation-id'])
        scheduler.on_task_event(self.event(type='snapshot',source={'id':'second-child'},
            sources=[{'id':'stored-child'},{'id':'second-child'}]),is_task_suppressed=lambda _:False)
        await asyncio.sleep(0);self.assertEqual(len(session.say_calls),2)
        await scheduler.close()

    async def test_existing_mixed_worker_cortex_allow_stale_delivery_is_preserved(self):
        session=_DummySession();scheduler=self._build_scheduler(session=session)
        async def no_worker(_self,_http,_message):return None
        async def cortex(_self,_http,_message,**scope):
            scheduler._seq+=1
            return {'followUp':{'messageId':'mixed-child','text':'Existing mixed delivery result.'}}
        scheduler._fetch_glasshive=MethodType(no_worker,scheduler)
        scheduler._fetch_cortex=MethodType(cortex,scheduler)
        await scheduler.schedule('mixed-parent',[], '',cortex_expected=True,glasshive_expected=True)
        self.assertEqual([c['text'] for c in session.say_calls],['Existing mixed delivery result.'])
        await scheduler.close()

    async def test_fresh_worker_waits_for_full_sync_then_recovers_unaccepted_child_once(self):
        session=_DummySession();scheduler=self._build_scheduler(session=session);fetches=[]
        async def fetch(_self,_http,_message,**scope):
            fetches.append(scope['followup_message_id'])
            return {'followUp':{'messageId':'stored-child','text':'Recovered current Main result.'}}
        scheduler._fetch_cortex=MethodType(fetch,scheduler)
        scheduler.on_task_event(self.event(type='snapshot'),is_task_suppressed=lambda _:False)
        await asyncio.sleep(0);self.assertEqual(fetches,[])
        scheduler.set_task_stream_connected(True)
        await asyncio.gather(*scheduler._cortex_wake_tasks)
        self.assertEqual(fetches,['stored-child']);self.assertEqual(len(session.say_calls),1)
        scheduler.set_task_stream_connected(False);scheduler.set_task_stream_connected(True)
        await asyncio.sleep(0);self.assertEqual(len(session.say_calls),1)
        await scheduler.close()

    async def test_newest_first_pages_do_not_promote_an_old_unspoken_child_after_newer_turn(self):
        session=_DummySession();scheduler=self._build_scheduler(session=session);fetch=mock.AsyncMock()
        scheduler._fetch_cortex=fetch
        newer=self.event(taskId='newer-task',streamId='newer-stream',owner={'kind':'generation_job','id':'newer-stream'},
            createdAt='2026-01-01T00:01:00Z',turnId='newer-turn',phase='running',state='running',source=None,resultMessageId='')
        scheduler.on_task_event(newer,is_task_suppressed=lambda _:False)
        scheduler.on_task_event(self.event(type='snapshot'),is_task_suppressed=lambda _:False)
        await asyncio.sleep(0);fetch.assert_not_awaited()
        scheduler.set_task_stream_connected(True)
        await asyncio.sleep(0);fetch.assert_not_awaited();self.assertEqual(session.say_calls,[])
        await scheduler.close()

    async def test_fresh_worker_retains_durable_stopped_child_silence(self):
        for state in ('stop_requested','completed','interrupted','superseded'):
            session=_DummySession();scheduler=self._build_scheduler(session=session);fetch=mock.AsyncMock()
            scheduler._fetch_cortex=fetch
            scheduler.on_task_event(self.event(type='snapshot',presentation={'ref':'stored-child','state':state,'startedAtMs':1000}),
                is_task_suppressed=lambda _:False)
            scheduler.set_task_stream_connected(True)
            await asyncio.sleep(0);fetch.assert_not_awaited();self.assertEqual(session.say_calls,[])
            await scheduler.close()

    async def test_stop_arriving_during_fetch_is_rechecked_before_speech_or_completed_ack(self):
        session,scheduler,_=await self.setup_late();entered=asyncio.Event();release=asyncio.Event()
        async def fetch(_self,_http,_message,**scope):
            entered.set();await release.wait()
            return {'followUp':{'messageId':'stored-child','text':'Must stay silent after Stop.'}}
        scheduler._fetch_cortex=MethodType(fetch,scheduler);scheduler._trace_handler=mock.AsyncMock()
        scheduler.on_task_event(self.event(),is_task_suppressed=lambda _:False)
        await entered.wait()
        scheduler.on_task_event(self.event(type='snapshot',presentation={'ref':'stored-child','state':'stop_requested','startedAtMs':1000}),
            is_task_suppressed=lambda _:False)
        release.set();await asyncio.gather(*scheduler._cortex_wake_tasks)
        self.assertEqual(session.say_calls,[]);scheduler._trace_handler.assert_not_awaited()
        await scheduler.close()

    async def test_listen_only_to_call_rearms_from_native_mode_without_another_task_event(self):
        session,scheduler,state=await self.setup_late();before=state['fetches'];scheduler.set_mode('listen_only')
        scheduler.on_task_event(self.event(),is_task_suppressed=lambda _:False)
        await asyncio.gather(*scheduler._cortex_wake_tasks)
        self.assertEqual(state['fetches'],before);self.assertEqual(session.say_calls,[])
        scheduler.set_mode('call')
        await asyncio.gather(*scheduler._cortex_wake_tasks)
        self.assertEqual(len(session.say_calls),1)
        scheduler.set_mode('call');await asyncio.sleep(0);self.assertEqual(len(session.say_calls),1)
        await scheduler.close()

    async def test_two_child_snapshot_gets_and_speech_keep_chronological_order_despite_slow_first_fetch(self):
        session,scheduler,_=await self.setup_late();order=[]
        async def fetch(_self,_http,_message,**scope):
            child=scope['followup_message_id'];order.append(child)
            if child=='stored-child':await asyncio.sleep(.02)
            return {'followUp':{'messageId':child,'text':'Main authored '+child+'.'}}
        scheduler._fetch_cortex=MethodType(fetch,scheduler)
        scheduler.on_task_event(self.event(type='snapshot',source={'id':'second-child'},
            sources=[{'id':'stored-child'},{'id':'second-child'}]),is_task_suppressed=lambda _:False)
        await asyncio.gather(*scheduler._cortex_wake_tasks)
        self.assertEqual(order,['stored-child','second-child'])
        self.assertEqual([c['text'] for c in session.say_calls],['Main authored stored-child.','Main authored second-child.'])
        await scheduler.close()

    async def test_created_at_is_optional_for_legacy_events_but_invalid_hydration_stamp_is_rejected(self):
        from librechat_llm import _extract_voice_task_event
        event=self.event();event.pop('createdAt')
        self.assertIsNotNone(_extract_voice_task_event({'voiceTaskEvent':event,'event':'voice_task_event'}))
        for value in ('not-a-date','2026-01-01T00:00:00',123):
            self.assertIsNone(_extract_voice_task_event({'voiceTaskEvent':{**event,'createdAt':value},'event':'voice_task_event'}))
        self.assertIsNotNone(_extract_voice_task_event({'voiceTaskEvent':self.event(),'event':'voice_task_event'}))

    async def test_mode_restoration_racing_done_callback_rearms_once(self):
        session,scheduler,state=await self.setup_late();scheduler.set_mode('listen_only')
        original_run=scheduler._run
        async def mode_gate(*args,**kwargs):
            if scheduler._mode=='listen_only':return
            return await original_run(*args,**kwargs)
        scheduler._run=mode_gate
        scheduler.on_task_event(self.event(),is_task_suppressed=lambda _:False)
        old_task=next(iter(scheduler._cortex_wake_tasks))
        await asyncio.sleep(0)
        self.assertTrue(old_task.done())
        self.assertIn(('main_anchor','stored-child'),scheduler._cortex_wake_pairs)
        scheduler.set_mode('call')
        await asyncio.sleep(0)
        await asyncio.gather(*scheduler._cortex_wake_tasks)
        self.assertEqual(len(session.say_calls),1)
        await scheduler.close()

    async def test_unchanged_mode_and_connected_refresh_do_not_rewalk_task_history(self):
        session,scheduler,_=await self.setup_late()
        with mock.patch.object(scheduler,'resume_pending') as resume:
            for _ in range(10):
                scheduler.set_mode('call');scheduler.set_task_stream_connected(True)
            resume.assert_not_called()
            scheduler.suspend_until_authoritative();scheduler.set_mode('call')
            self.assertEqual(resume.call_count,1)
            scheduler.set_task_stream_connected(False);scheduler.set_task_stream_connected(True)
            self.assertEqual(resume.call_count,2)
        await scheduler.close()

    async def test_late_first_cortex_publication_keeps_guard_without_an_early_cortex_sse_event(self):
        session=_DummySession();scheduler=self._build_scheduler(session=session)
        current=[True]
        self.assertIsNone(scheduler.schedule('main_anchor',[], '',cortex_expected=False,
            presentation_is_current=lambda:current[0],trace_id='original-trace'))
        fetch=mock.AsyncMock(return_value={'followUp':{'messageId':'stored-child','text':'Late first authored result.'}})
        scheduler._fetch_cortex=fetch
        scheduler.on_task_event(self.event(),is_task_suppressed=lambda _:False)
        await asyncio.gather(*scheduler._cortex_wake_tasks)
        self.assertEqual(len(session.say_calls),1)
        current[0]=False
        scheduler.on_task_event(self.event(source={'id':'later-child'}),is_task_suppressed=lambda _:False)
        await asyncio.sleep(0);self.assertEqual(fetch.await_count,1)
        await scheduler.close()

    async def test_fresh_hydration_rejects_superseded_main_parent_before_a_new_task_arrives(self):
        session=_DummySession();scheduler=self._build_scheduler(session=session);fetch=mock.AsyncMock()
        scheduler._fetch_cortex=fetch
        scheduler.on_task_event(self.event(type='snapshot',presentation={'ref':'main_anchor','state':'superseded','startedAtMs':1000}),
            is_task_suppressed=lambda _:False)
        scheduler.set_task_stream_connected(True)
        await asyncio.sleep(0);fetch.assert_not_awaited();self.assertEqual(session.say_calls,[])
        await scheduler.close()

    async def test_confirmed_non_cortex_source_is_not_refetched_by_snapshot_or_mode_recovery(self):
        session,scheduler,_=await self.setup_late();requested=[]
        async def fetch(_self,_http,_message,**scope):
            requested.append(scope['followup_message_id'])
            return {'followUp':None}
        scheduler._fetch_cortex=MethodType(fetch,scheduler)
        event=self.event(source={'id':'citation-id'},sources=[{'id':'citation-id'}])
        scheduler.on_task_event(event,is_task_suppressed=lambda _:False)
        await asyncio.gather(*scheduler._cortex_wake_tasks)
        for _ in range(3):
            scheduler.on_task_event({**event,'type':'snapshot',
                'presentation':{'ref':'main_anchor','state':'completed'}},is_task_suppressed=lambda _:False)
            await asyncio.sleep(0)
        scheduler.set_mode('listen_only');scheduler.set_mode('call')
        scheduler.set_task_stream_connected(False);scheduler.set_task_stream_connected(True)
        await asyncio.sleep(0)
        self.assertEqual(requested,['citation-id']);self.assertEqual(session.say_calls,[])
        self.assertIn(('main_anchor','citation-id'),scheduler._cortex_wake_pairs)
        await scheduler.close()

    async def test_initial_call_fetch_authority_loss_and_restore_before_done_rearms_once(self):
        session,scheduler,_=await self.setup_late();requested=[]
        async def fetch(_self,_http,_message,**scope):
            requested.append(scope['followup_message_id'])
            if len(requested)==1:
                scheduler.suspend_until_authoritative()
                asyncio.get_running_loop().call_soon(scheduler.set_mode,'call')
                return None
            return {'followUp':{'messageId':'stored-child','text':'Recovered after native authority restoration.'}}
        scheduler._fetch_cortex=MethodType(fetch,scheduler)
        self.assertEqual(scheduler._mode,'call');self.assertTrue(scheduler._authoritative_mode_available)
        scheduler.on_task_event(self.event(),is_task_suppressed=lambda _:False)
        first=next(iter(scheduler._cortex_wake_tasks))
        await first
        await asyncio.sleep(0)
        await asyncio.gather(*scheduler._cortex_wake_tasks)
        await asyncio.sleep(0)
        self.assertEqual(requested,['stored-child','stored-child'])
        self.assertEqual([c['text'] for c in session.say_calls],['Recovered after native authority restoration.'])
        self.assertTrue(scheduler._authoritative_mode_available);self.assertEqual(scheduler._mode,'call')
        await scheduler.close()

    async def test_failed_fetch_does_not_automatically_retry_without_a_native_transition(self):
        session,scheduler,_=await self.setup_late();scheduler._timeout_s=.001
        fetch=mock.AsyncMock(return_value=None);scheduler._fetch_cortex=fetch
        scheduler.on_task_event(self.event(),is_task_suppressed=lambda _:False)
        await asyncio.gather(*scheduler._cortex_wake_tasks)
        count=fetch.await_count
        for _ in range(5):await asyncio.sleep(0)
        self.assertGreater(count,0);self.assertEqual(fetch.await_count,count)
        self.assertEqual(scheduler._cortex_wake_tasks,set());self.assertEqual(session.say_calls,[])
        await scheduler.close()

    async def test_accepted_child_losing_mode_or_current_guard_posts_only_exact_interrupted_ack(self):
        from librechat_llm import LibreChatAuth, LibreChatLLM
        import test_librechat_llm as llm_fixtures
        for loss, main_started in ((loss, main_started) for loss in ('listen_only','authority_unknown','superseded','stopped') for main_started in (0,1234)):
            with self.subTest(loss=loss,main_started=main_started):
                session,scheduler,_=await self.setup_late()
                scheduler._auth=LibreChatAuth(call_session_id='call_123',call_secret='synthetic',job_id='job',worker_id='worker')
                llm=LibreChatLLM(origin='http://example.test',auth=scheduler._auth)
                if main_started:
                    from librechat_llm import _VoicePresentation
                    llm._presentation_by_trace_id['main_stream']=_VoicePresentation(sequence=1,source_event_id='main-event',
                        presentation_ref='main_anchor',trace_id='main_stream',logical_turn_id='main-parent-turn',
                        revision=1,audio_started_at_ms=main_started)
                scheduler._trace_handler=llm.record_followup_presentation
                context={'callSessionId':'call_123','taskId':'parent_task','streamId':'main_stream','turnId':'original-canonical-turn'}
                requested=[]
                async def fetch(_self,_http,_message,**scope):
                    requested.append(scope['followup_message_id'])
                    if loss=='listen_only':scheduler.set_mode('listen_only')
                    elif loss=='authority_unknown':scheduler.suspend_until_authoritative()
                    elif loss=='superseded':scheduler._seq+=1
                    else:scheduler.on_task_event(self.event(presentation={
                        'ref':'stored-child','state':'stop_requested','startedAtMs':1000}),is_task_suppressed=lambda _:False)
                    return {'followUp':{'messageId':'stored-child','text':'Must not play after guard loss.',
                        'presentationContext':context}}
                scheduler._fetch_cortex=MethodType(fetch,scheduler)
                transport=llm_fixtures._FakeDeliveryAckSession()
                with mock.patch('librechat_llm.aiohttp.ClientSession',return_value=transport):
                    scheduler.on_task_event(self.event(),is_task_suppressed=lambda _:False)
                    await asyncio.gather(*scheduler._cortex_wake_tasks)
                    scheduler.set_mode('call')
                    scheduler.on_task_event(self.event(type='snapshot'),is_task_suppressed=lambda _:False)
                    scheduler.set_task_stream_connected(False);scheduler.set_task_stream_connected(True)
                    await asyncio.sleep(0)
                    await scheduler.close()
                self.assertEqual(session.say_calls,[]);self.assertEqual(requested,['stored-child'])
                bodies=[c[2]['json'] for c in transport.post_calls]
                self.assertEqual([b['stage'] for b in bodies],['audio.interrupted'])
                self.assertEqual(bodies[0]['turnId'],'original-canonical-turn')
                self.assertEqual(bodies[0]['taskId'],'parent_task');self.assertEqual(bodies[0]['streamId'],'main_stream')
                self.assertEqual(bodies[0]['presentationRef'],'stored-child')
                self.assertNotIn('startedAtMs',bodies[0])

    async def test_canonical_child_zero_start_does_not_inherit_existing_main_clock(self):
        from librechat_llm import LibreChatAuth, LibreChatLLM, _VoicePresentation
        import test_librechat_llm as llm_fixtures
        llm=LibreChatLLM(origin='http://example.test',auth=LibreChatAuth(call_session_id='call_123',
            call_secret='synthetic',job_id='job',worker_id='worker'))
        llm._presentation_by_trace_id['main_stream']=_VoicePresentation(sequence=1,source_event_id='main-event',
            presentation_ref='main_anchor',trace_id='main_stream',logical_turn_id='main-parent-turn',
            revision=1,audio_started_at_ms=1234)
        context={'callSessionId':'call_123','taskId':'parent_task','streamId':'main_stream','turnId':'child-original-turn'}
        transport=llm_fixtures._FakeDeliveryAckSession()
        with mock.patch('librechat_llm.aiohttp.ClientSession',return_value=transport):
            self.assertTrue(await llm.record_followup_presentation('main_stream','stored-child','audio.interrupted',
                task_ref=context,started_at_ms=0))
            self.assertTrue(await llm.record_followup_presentation('main_stream','stored-child','audio.started',
                task_ref=context,started_at_ms=3000))
        bodies=[c[2]['json'] for c in transport.post_calls]
        self.assertNotIn('startedAtMs',bodies[0]);self.assertEqual(bodies[1]['startedAtMs'],3000)
        for body in bodies:
            self.assertEqual(body['turnId'],'child-original-turn');self.assertEqual(body['presentationRef'],'stored-child')
            self.assertEqual(body['taskId'],'parent_task');self.assertEqual(body['streamId'],'main_stream')
