"""Read-only QA observations must use the current Native presentation owner."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "qa/prompt-architecture/evals/run-native-surface-playwright-qa.cjs"

FIXTURE = r"""
const assert=require('assert'), crypto=require('crypto'), path=require('path');
const {createRequire}=require('module');
const runner=require(process.argv[1]);
const lc=path.resolve(path.dirname(process.argv[1]),'../../../viventium_v0_4/LibreChat');
const localRequire=createRequire(path.join(lc,'api/server/services/viventium/nativeCoordinatorPresentation.js'));
const api=localRequire('@librechat/api');
function fixture(kind='goal',surface='web') {
 const parent={ownerId:'qa-owner',conversationId:'qa-conversation',parentMessageId:'seed-answer'};
 const binding={_id:'qa-binding',kind:'native_coordinator_binding',active:true,tenantId:'qa-tenant',
  ownerId:parent.ownerId,conversationId:parent.conversationId,nativeConversationId:'qa-native'};
 const source={kind:'native_coordinator_source',bindingRef:binding._id,turnId:'qa-source',
  requestBody:{conversationId:parent.conversationId,messageId:parent.parentMessageId,viventiumSurface:surface}};
 const subject={source_turn_id:source.turnId,run_id:'qa-run',result_revision:1,state:'completed',
  intent_state:'accepted',restore_hold:false,...(kind==='turn'?{turn_id:'qa-turn',request_id:'qa-request',
   superseded:false,presentation_eligible:true}:{goal_id:'qa-goal'})};
 const insight='The generated badge is ready.';
 const digest=crypto.createHash('sha256').update(insight).digest('hex');
 const nativeResult={...subject,sha256:digest,total_chars:insight.length,publisher:{owner_id:parent.ownerId,
  conversation_id:binding.nativeConversationId,agent_id:'coordinator',run_id:subject.run_id,
  request_id:kind==='turn'?subject.request_id:'qa-publisher-request',
  message_id:kind==='turn'?subject.turn_id:'qa-publisher-message',
  stream_id:kind==='turn'?subject.turn_id:'qa-publisher-stream'}};
 const data={request_ref:binding._id,conversation_id:binding.nativeConversationId,run_id:subject.run_id,
  result_revision:1,result_digest:'sha256:'+digest,...(kind==='turn'?{turn_id:subject.turn_id,
   request_id:subject.request_id}:{goal_id:subject.goal_id})};
 const eventId=api.nativeCoordinatorResultEventId(data);
 const row={...api.buildCortexInsightDeliveryCandidates({...parent,surface,
  insights:[{cortexId:eventId,status:'completed',insight}]})[0],publicationId:eventId,insight,
  status:'sent',persistenceStatus:'persisted',persistedMessageId:'qa-result',sentAt:'2026-11-01T00:00:00Z',
  requiredSurfaces:api.requiredSurfacesFor(surface),presentedSurfaces:api.requiredSurfacesFor(surface),
  presentationReceiptHashes:['a'.repeat(64)]};
 const original={messageId:'seed-answer',user:parent.ownerId,conversationId:parent.conversationId,
  isCreatedByUser:false,text:'I will create it.',metadata:{viventium:{}}};
 const primary={...original,messageId:'primary-c',text:'42.'};
 const message={...original,messageId:'qa-result',parentMessageId:parent.parentMessageId,
  text:'Here is your badge.',attachments:[{file_id:'qa-file',filename:'badge.svg',bytes:80,type:'image/svg+xml'}],
  metadata:{viventium:{messageRevision:1,cortexInsightDeliveryIds:[row.deliveryId],
   cortexPresentationParentMessageId:parent.parentMessageId}}};
 const resultSource={bindingRef:binding._id,nativeConversationId:binding.nativeConversationId,
  runId:subject.run_id,resultRevision:1,resultDigest:'sha256:'+digest,sourceTurnId:source.turnId,
  sourceCallSessionId:'',...(kind==='turn'?{kind:'native_coordinator_turn',turnId:subject.turn_id,
   requestId:subject.request_id}:{goalId:subject.goal_id})};
 message.metadata.viventium.mainGenerationPresentation=api.buildMainGenerationPresentation(
  {nativeCoordinatorResult:resultSource},message.messageId,message.text);
 const callback={userId:parent.ownerId,conversationId:parent.conversationId,callbackMessageId:message.messageId,
  originRef:binding._id,status:'sent',surface,event:'main.followup',text:message.text,sentAt:row.sentAt,
  telegramSentMessageIds:['synthetic-receipt'],mainGenerationPresentation:message.metadata.viventium.mainGenerationPresentation};
 const tables={messages:[original,message,primary],viventium_glasshive_callback_bindings:[binding,source],
  viventiumcortexinsightdeliveries:[row],viventiumglasshivecallbackdeliveries:[callback],
  viventium_glasshive_mission_evidence:[]};
 const queries=[],requests=[],writes=[];
 function valueAt(v,k){return k.split('.').reduce((a,key)=>a?.[key],v);}
 function matches(v,q){return Object.entries(q).every(([k,w])=>k==='$or'?w.some(x=>matches(v,x)):
  w&&typeof w==='object'&&!Array.isArray(w)?Object.entries(w).every(([op,x])=>
   op==='$in'?x.includes(valueAt(v,k)):op==='$all'?x.every(y=>(valueAt(v,k)||[]).includes(y)):
   op==='$size'?(valueAt(v,k)||[]).length===x:op==='$exists'?(valueAt(v,k)!==undefined)===x:false):valueAt(v,k)===w);}
 const db={collection(name){return {find(q={}){queries.push({name,q});let rows=(tables[name]||[]).filter(v=>matches(v,q));
  const cursor={sort(){return cursor},limit(n){rows=rows.slice(0,n);return cursor},project(){return cursor},async toArray(){return rows}};return cursor},
  async findOne(q){queries.push({name,q});return (tables[name]||[]).find(v=>matches(v,q))||null},
  async updateOne(){writes.push(name);throw Error('QA observer must not write');}}}};
 const publications=[{type:kind==='turn'?'coordinator.turn_result_ready':'coordinator.result_ready',
  event_id:eventId,source_turn_id:source.turnId,data}];
 const request=async input=>{requests.push(input);assert.ok(!input.method||input.method==='GET');
  assert.strictEqual(input.ownerId,parent.ownerId);
  if(input.path.includes('/publications'))return {conversation_id:binding.nativeConversationId,publications,next_cursor:null};
  if(input.path.includes('/result?'))return nativeResult;
  return {conversation_id:binding.nativeConversationId,goals:kind==='goal'?[subject]:[],turns:kind==='turn'?[subject]:[]};};
 const result={observeBackgroundResults:true,finalMeta:{conversationId:parent.conversationId,
  responseMessageId:primary.messageId,requestMessageId:'primary-request'},cleanupFinalMetas:[{
   conversationId:parent.conversationId,responseMessageId:original.messageId,requestMessageId:'seed-request'}]};
 const read=(options={})=>runner.readConversationEvidence({db,result,conversationId:parent.conversationId,
  ownerId:parent.ownerId,env:{VIVENTIUM_TENANT_ID:'qa-tenant'},nativeRequest:request,...options});
 return {parent,binding,source,subject,nativeResult,row,original,message,primary,callback,tables,
  queries,requests,writes,result,db,read,request,publications};
}
"""


def _node(body: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["node", "-e", FIXTURE + body, str(RUNNER)], cwd=ROOT,
                          capture_output=True, text=True, check=False)


def test_native_goal_and_direct_turn_results_use_seed_source_and_saved_channel_receipts() -> None:
    result = _node(r"""
(async()=>{for(const kind of ['goal','turn'])for(const surface of ['web','telegram']) {
 const f=fixture(kind,surface), evidence=await f.read();
 assert.strictEqual(evidence.delayedMessageCount,1,kind+': missing owned seed result');
 assert.strictEqual(evidence.delayedVisibleText,'Here is your badge.');
 assert.strictEqual(evidence.nativeCoordinatorResults[0].state,'completed');
 assert.strictEqual(evidence.nativeCoordinatorResults[0].hasFollowUp,true);
 assert.deepStrictEqual(runner.inspectBackgroundResultObservation({expected_decision:'surface',
  required_background_attachment:'badge.svg'},evidence),{ok:true});
 assert.ok(f.requests.length>0,'must call actual owner with current Native result readers');
 assert.ok(f.queries.filter(q=>q.name==='viventium_glasshive_callback_bindings').every(q=>
  q.q.ownerId==='qa-owner'||q.q.bindingRef?.$in?.includes('qa-binding')));
 assert.deepStrictEqual(f.writes,[]);
 const observed=await runner.observePostCaseDbEvidence({db:f.db,result:f.result,maxObserveMs:0,
  followUpGraceMs:0,ownerId:f.parent.ownerId,env:{VIVENTIUM_TENANT_ID:'qa-tenant'},nativeRequest:f.request});
 assert.strictEqual(observed.delayedMessageCount,1);
}})().catch(e=>{console.error(e);process.exit(1)});
""")
    assert result.returncode == 0, result.stderr


def test_native_observation_rejects_foreign_stale_held_unsaved_and_unacknowledged_results() -> None:
    result = _node(r"""
(async()=>{const mutations={
 foreign_owner:f=>f.binding.ownerId='foreign', foreign_tenant:f=>f.binding.tenantId='foreign',
 foreign_conversation:f=>f.binding.conversationId='foreign', inactive:f=>f.binding.active=false,
 foreign_source:f=>f.subject.source_turn_id='other', source_parent:f=>f.source.requestBody.messageId='other',
 stale_run:f=>f.nativeResult.run_id='old', stale_revision:f=>f.nativeResult.result_revision=2,
 stale_digest:f=>f.nativeResult.sha256='b'.repeat(64), foreign_publisher:f=>f.nativeResult.publisher.owner_id='other',
 held:f=>f.subject.restore_hold=true, stopped:f=>f.subject.intent_state='stopped',
 unsaved:f=>delete f.message.metadata.viventium.mainGenerationPresentation,
 stale_saved:f=>f.message.metadata.viventium.mainGenerationPresentation.nativeCoordinatorResult.runId='old',
 message_changed:f=>f.message.text='Different after save.', message_foreign:f=>f.message.user='foreign',
 row_foreign:f=>f.row.userId='foreign', row_pending:f=>f.row.status='pending',
 row_receipt_missing:f=>f.row.presentationReceiptHashes=[], row_surface_missing:f=>f.row.presentedSurfaces=['web'],
 callback_pending:f=>f.callback.status='pending', callback_receipt_missing:f=>f.callback.telegramSentMessageIds=[],
 callback_authority:f=>f.callback.mainGenerationPresentation={version:1},
 duplicate_saved:f=>f.tables.messages.push({...f.message,messageId:'duplicate-result'}),
 };
 for(const [name,mutate] of Object.entries(mutations)){const f=fixture('goal','telegram');mutate(f);
  const e=await f.read(),verdict=runner.inspectBackgroundResultObservation({expected_decision:'surface'},e);
  assert.strictEqual(verdict.ok,false,name+' must not prove delivery');assert.strictEqual(e.delayedMessageCount,0,name);
  assert.deepStrictEqual(f.writes,[]);
 }
 const turn=fixture('turn');turn.nativeResult.superseded=true;
 assert.strictEqual(runner.inspectBackgroundResultObservation({expected_decision:'surface'},await turn.read()).ok,false);
})().catch(e=>{console.error(e);process.exit(1)});
""")
    assert result.returncode == 0, result.stderr


def test_native_suppression_requires_exact_authored_silence_and_no_saved_or_delayed_message() -> None:
    result = _node(r"""
(async()=>{function silent(){const f=fixture();f.tables.messages.splice(1,1);
 f.row.status='dropped';f.row.dropReason='semantic_suppression';f.row.persistenceStatus='pending';
 f.row.persistedMessageId='';f.original.metadata.viventium.cortexFollowUpDecision={result:'suppressed',
  deliveryStatus:'dropped',dropReason:'semantic_suppression',persistedMessageId:'',
  selectedStrategy:'no_response_suppressed',suppressionReason:'no_response_tag'};return f;}
 const f=silent(),e=await f.read();assert.strictEqual(e.nativeCoordinatorResults[0].state,'silent');
 assert.deepStrictEqual(runner.inspectBackgroundResultObservation({expected_decision:'suppress'},e),{ok:true});
 for(const name of ['missing_decision','wrong_drop','saved','delayed','held','missing_result','transport']){
  const f=silent();if(name==='missing_decision')delete f.original.metadata.viventium.cortexFollowUpDecision;
  if(name==='wrong_drop')f.row.dropReason='conversation_moved_on';
  if(name==='saved')f.row.persistedMessageId='qa-result';
  if(name==='delayed')f.tables.messages.push(f.message);
  if(name==='held')f.subject.restore_hold=true;
  if(name==='missing_result')f.nativeResult.state='running';
  if(name==='transport')f.nativeResult.publisher.owner_id='foreign';
  assert.strictEqual(runner.inspectBackgroundResultObservation({expected_decision:'suppress'},await f.read()).ok,false,name);
 }
 const native=silent();Object.assign(native.original.metadata.viventium.cortexFollowUpDecision,{
  nativeSilentDecision:true,selectedStrategy:'native_silent_suppressed',suppressionReason:'native_authored_silence'});
 assert.strictEqual(runner.inspectBackgroundResultObservation({expected_decision:'suppress'},await native.read()).ok,true);
})().catch(e=>{console.error(e);process.exit(1)});
""")
    assert result.returncode == 0, result.stderr



def test_native_observer_uses_actual_signed_get_and_restores_only_scoped_runtime_environment() -> None:
    result = _node(r"""
(async()=>{
 const {withNativeAccountEnv}=require(path.join(path.dirname(process.argv[1]),'native-background-observation.cjs'));
 const keys=['GLASSHIVE_PROVIDER_BASE_URL','WPR_API_TOKEN','VIVENTIUM_GLASSHIVE_SERVICE_ASSERTION_SECRET','VIVENTIUM_TENANT_ID'];
 const initial=keys.map(k=>[k,process.env[k]]);
 const config={GLASSHIVE_PROVIDER_BASE_URL:'http://127.0.0.1:65535',WPR_API_TOKEN:'synthetic-qa-token',
  VIVENTIUM_GLASSHIVE_SERVICE_ASSERTION_SECRET:'synthetic-qa-assertion-secret',VIVENTIUM_TENANT_ID:'qa-tenant'};
 const restored=()=>{for(const [key,value]of initial)assert.strictEqual(process.env[key],value,key+' not restored')};
 assert.strictEqual(withNativeAccountEnv(config,()=>{assert.strictEqual(process.env.WPR_API_TOKEN,config.WPR_API_TOKEN);return 42;}),42);restored();
 assert.throws(()=>withNativeAccountEnv(config,()=>{throw Error('synthetic sync failure')}));restored();
 const rejected=withNativeAccountEnv(config,()=>Promise.reject(Error('synthetic asynchronous failure')));restored();
 await assert.rejects(rejected);restored();
 const f=fixture('goal','telegram'),captured=[];
 const previousFetch=global.fetch;
 global.fetch=async (url,options)=>{
  const u=new URL(url);assert.strictEqual(u.origin,config.GLASSHIVE_PROVIDER_BASE_URL);assert.strictEqual(options.method,'GET');
  assert.strictEqual(options.headers.Authorization,'Bearer '+config.WPR_API_TOKEN);
  const assertion=options.headers['X-Viventium-Service-Assertion'];assert.ok(assertion);
  const [payload,signature]=assertion.split('.');assert.strictEqual(signature,crypto.createHmac('sha256',
   config.VIVENTIUM_GLASSHIVE_SERVICE_ASSERTION_SECRET).update(payload).digest('base64url'));
  const claims=JSON.parse(Buffer.from(payload,'base64url'));assert.strictEqual(claims.owner_id,'qa-owner');
  assert.strictEqual(claims.tenant_id,'qa-tenant');assert.ok(!options.body);
  captured.push(u.pathname+u.search);
  await Promise.resolve();restored();
  return new Response(JSON.stringify(await f.request({ownerId:'qa-owner',path:u.pathname+u.search})),{status:200,headers:{'content-type':'application/json'}});
 };
 try {
  await withNativeAccountEnv(config,()=>api.requestAccountApi({ownerId:'qa-owner',path:'/v1/coordinator/conversations/qa-native?include_history=false',method:'GET'}));
  const evidence=await f.read({nativeRequest:undefined,env:config});
  assert.strictEqual(evidence.delayedMessageCount,1);
  assert.ok(captured.some(x=>x.includes('/goals/qa-goal/result?run_id=qa-run')));
  restored();
  global.fetch=async()=>{throw Error('synthetic unavailable transport')};
  const failed=await f.read({nativeRequest:undefined,env:config});restored();
  assert.strictEqual(runner.inspectBackgroundResultObservation({expected_decision:'surface'},failed).ok,false);
  assert.strictEqual(JSON.stringify(failed).includes(config.WPR_API_TOKEN),false);
 }finally{global.fetch=previousFetch;restored();}
})().catch(e=>{console.error(e);process.exit(1)});
""")
    assert result.returncode == 0, result.stderr



def test_native_dependency_and_authority_errors_never_become_legacy_success() -> None:
    result = _node(r"""
(async()=>{
 const helper=require(path.join(path.dirname(process.argv[1]),'native-background-observation.cjs'));
 const f=fixture();
 await assert.rejects(helper.readNativeBackgroundObservation({db:f.db,result:f.result,
  conversationId:f.parent.conversationId,ownerId:f.parent.ownerId,env:{VIVENTIUM_TENANT_ID:'qa-tenant'},
  messages:f.tables.messages,libreChatRoot:path.join(lc,'synthetic-missing-source'),request:f.request}),
  error=>error.code==='MODULE_NOT_FOUND');
 f.tables.viventium_glasshive_mission_evidence.push({conversationId:f.parent.conversationId,
  ownerId:f.parent.ownerId,state:'completed',followUpMessageId:f.message.messageId});
 const failed=await f.read({nativeRequest:async()=>{throw Error('synthetic current Native unavailable')}});
 assert.strictEqual(runner.inspectBackgroundResultObservation({expected_decision:'surface'},failed).ok,false);
 const ownerless=await f.read({ownerId:undefined});assert.deepStrictEqual(ownerless.nativeCoordinatorResults,[]);
 assert.deepStrictEqual(f.writes,[]);
})().catch(e=>{console.error(e);process.exit(1)});
""")
    assert result.returncode == 0, result.stderr
