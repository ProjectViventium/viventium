from pathlib import Path
import hashlib
import json
import subprocess
import sys
import sqlite3
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'viventium_v0_4/prompt-workbench/backend'))
from prompt_workbench import evals


def test_worker_source_native_route_and_frame_evidence_fail_closed(tmp_path):
    runner = ROOT / 'qa/prompt-architecture/evals/run-worker-source-evals.cjs'
    script = r'''
const assert=require('assert'); const r=require(process.argv[1]);
const env={GLASSHIVE_DEFAULT_WORKER_PROFILE:'codex-cli',GLASSHIVE_DEFAULT_FALLBACK_WORKER_PROFILE:'claude-code',WPR_MODEL_CODEX_CLI:'synthetic-model',WPR_CODEX_CLI_REASONING_EFFORT:'xhigh',WPR_MODEL_CLAUDE_CODE:'synthetic-fallback',WPR_CLAUDE_CODE_EFFORT:'default'};
for(const slot of ['primary','fallback']) {
 const route=r.configuredWorkerRoute(slot,env);
 const key=slot==='primary'?'WPR_CODEX_CLI_REASONING_EFFORT':'WPR_CLAUDE_CODE_EFFORT';
 const bundle={env:{[key]:route.effort},provider_capabilities:{native_tools:true},application_developer_instructions:'exact source',developer_instructions:'exact source'};
 const record={state:'completed',model_id:route.model,provider_route_model:route.nativeModel,access_mode:'full',run_id:'run',worker_id:'worker',bootstrap_bundle_json:JSON.stringify(bundle)};
 assert.strictEqual(r.verifyNativeRun(record,route,'exact source').effort,route.effort);
 assert.throws(()=>r.verifyNativeRun({...record,model_id:'other'},route,'exact source'),/route_mismatch/);
 assert.throws(()=>r.verifyNativeRun({...record,state:'running'},route,'exact source'),/evidence_missing/);
 assert.throws(()=>r.verifyNativeRun(record,route,'another source'),/not_observed/);
 assert.throws(()=>r.verifyNativeRun({...record,bootstrap_bundle_json:JSON.stringify({...bundle,provider_capabilities:{native_tools:false}})},route,'exact source'),/route_mismatch/);
}
assert.throws(()=>r.configuredWorkerRoute('fallback',{}),/unavailable/);
assert.throws(()=>r.configuredWorkerRoute('unconfigured',env),/slot/);
assert.throws(()=>r.sourceInstructions({frames:{harness:'x'}},'codex-cli'),/frame_missing/);
const grokEnv={GLASSHIVE_DEFAULT_WORKER_PROFILE:'grok-build',WPR_MODEL_GROK_BUILD:'grok-selected',WPR_GROK_REASONING_EFFORT:'high'};
const grok=r.configuredWorkerRoute('primary',grokEnv);
assert.strictEqual(grok.model,'grok-build:grok-selected');
assert.throws(()=>r.configuredWorkerRoute('primary',{...grokEnv,WPR_GROK_REASONING_EFFORT:''}),/unavailable/);
const frames={harness:'host',project:'project',agents:'common',codex:'codex-only',claude:'claude-only'};
assert.strictEqual(r.sourceInstructions({frames},'grok-build'),'host\n\nproject\n\ncommon');
const grokBundle={env:{WPR_GROK_REASONING_EFFORT:'high'},provider_capabilities:{native_tools:true},developer_instructions:'exact grok',application_developer_instructions:'exact grok'};
const grokRecord={state:'completed',model_id:grok.model,provider_route_model:grok.nativeModel,access_mode:'full',run_id:'grok-run',worker_id:'grok-worker',bootstrap_bundle_json:JSON.stringify(grokBundle)};
assert.strictEqual(r.verifyNativeRun(grokRecord,grok,'exact grok').effort,'high');
assert.throws(()=>r.verifyNativeRun({...grokRecord,bootstrap_bundle_json:JSON.stringify({...grokBundle,env:{WPR_CLAUDE_CODE_EFFORT:'high'}})},grok,'exact grok'),/route_mismatch/);
assert.throws(()=>r.sourceInstructions({frames},'unsupported'),/unavailable/);
const semantic=r.configuredWorkerRoute('primary',grokEnv,false);
assert.strictEqual(semantic.access,'read_only');
assert.strictEqual(semantic.nativeTools,false);
const disabled={...grokRecord,access_mode:'read_only',bootstrap_bundle_json:JSON.stringify({...grokBundle,provider_capabilities:{native_tools:false}})};
assert.strictEqual(r.verifyNativeRun(disabled,semantic,'exact grok').nativeTools,false);
assert.throws(()=>r.verifyNativeRun(grokRecord,semantic,'exact grok'),/route_mismatch/);
assert.throws(()=>r.verifyNativeRun(disabled,grok,'exact grok'),/route_mismatch/);
assert.throws(()=>r.configuredWorkerRoute('primary',grokEnv,'false'),/native_tools/);

'''
    result = subprocess.run(['node','-e',script,str(runner)],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr


def test_worker_source_snapshot_requires_exact_bytes_and_source_lineage(tmp_path):
    runner = ROOT / 'qa/prompt-architecture/evals/run-worker-source-evals.cjs'
    source = {'sources':[{'path':'worker.py','text':'original','sha256':hashlib.sha256(b'original').hexdigest()}], 'frames':{}}
    snapshot = tmp_path/'source.json'; snapshot.write_text(json.dumps(source))
    script = r'''
const assert=require('assert'),fs=require('fs'),crypto=require('crypto'); const r=require(process.argv[1]);
const file=process.argv[2]; const digest=()=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
let target={sourceSnapshot:{path:file,sha256:digest()}};
assert(r.readWorkerSource(target,file).sources.length===1);
fs.appendFileSync(file,' '); assert.throws(()=>r.readWorkerSource(target,file),/hash_mismatch/);
let parsed=JSON.parse(fs.readFileSync(file));parsed.sources[0].text='changed';fs.writeFileSync(file,JSON.stringify(parsed));
target.sourceSnapshot.sha256=digest();assert.throws(()=>r.readWorkerSource(target,file),/lineage_mismatch/);
'''
    result=subprocess.run(['node','-e',script,str(runner),str(snapshot)],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr


def test_worker_source_suppressed_native_control_reaches_semantic_judgment():
    runner = ROOT / 'qa/prompt-architecture/evals/run-worker-source-evals.cjs'
    script = r'''
const assert=require('assert'),r=require(process.argv[1]);
const env={GLASSHIVE_DEFAULT_WORKER_PROFILE:'codex-cli',WPR_MODEL_CODEX_CLI:'synthetic',WPR_CODEX_CLI_REASONING_EFFORT:'high'};
const route=r.configuredWorkerRoute('primary',env,false);
const bundle={env:{WPR_CODEX_CLI_REASONING_EFFORT:'high'},provider_capabilities:{native_tools:false},application_developer_instructions:'exact source',developer_instructions:'exact source'};
const native={state:'completed',model_id:route.model,provider_route_model:route.nativeModel,access_mode:route.access,run_id:'run',worker_id:'worker',bootstrap_bundle_json:JSON.stringify(bundle),output_text:'{NTA}'};
// A completed silent model answer is judge input for both kinds of case. It is not a pass:
// the unchanged positive/suppression rubric still decides whether this answer is correct.
for(const expectedDecision of ['respond','suppress']) {
 const result=r.verifiedWorkerResponse({insight:''},native,route,'exact source');
 assert.strictEqual(result.responseForJudge,'{NTA}',expectedDecision);
 assert.strictEqual(result.observedRoute.state,'completed');
 assert.strictEqual(result.semanticJudge,undefined);
}
const spaced=' \n{ nTa }\t';
assert.strictEqual(r.verifiedWorkerResponse({insight:''},{...native,output_text:spaced},route,'exact source').responseForJudge,spaced);
const carrier={type:'assistant_response',content:'{NTA}',tool_name:null};
assert.strictEqual(r.verifiedWorkerResponse({insight:''},{...native,output_text:JSON.stringify(carrier)},route,'exact source').responseForJudge,'{NTA}');
assert.strictEqual(r.verifiedWorkerResponse({insight:''},{...native,output_text:JSON.stringify({...carrier,content:spaced})},route,'exact source').responseForJudge,spaced);
for(const invalid of [
 {...carrier,type:'tool_call'}, {...carrier,tool_name:'some_tool'},
 {...carrier,content:'{NTA} plus visible result'}, {...carrier,content:['{NTA}']},
 {...carrier,extra:'visible result'}, {content:'{NTA}'}, [carrier],
 {type:'assistant_response',content:'{NTA}'},
]) {
 assert.throws(()=>r.verifiedWorkerResponse({insight:''},{...native,output_text:JSON.stringify(invalid)},route,'exact source'),/response_unavailable/);
}
assert.strictEqual(r.verifiedWorkerResponse({insight:'Visible result'},native,route,'exact source').responseForJudge,'Visible result');
for(const output_text of ['', '   ', 'Nothing new to add.', '{NTA} plus invented result', null]) {
 assert.throws(()=>r.verifiedWorkerResponse({insight:''},{...native,output_text},route,'exact source'),/response_unavailable/);
}
for(const response of [null, {insight:'',error:'provider_error'}, {insight:'',errorClass:'provider_error'}, {insight:'',fallbackUsed:true}]) {
 assert.throws(()=>r.verifiedWorkerResponse(response,native,route,'exact source'),/provider_error|response_unavailable/);
}
for(const state of ['running','failed','cancelled']) {
 assert.throws(()=>r.verifiedWorkerResponse({insight:''},{...native,state},route,'exact source'),/evidence_missing/);
}
assert.throws(()=>r.verifiedWorkerResponse({insight:''},null,route,'exact source'),/evidence_missing/);
assert.throws(()=>r.verifiedWorkerResponse({insight:''},{...native,model_id:'foreign'},route,'exact source'),/route_mismatch/);
assert.throws(()=>r.verifiedWorkerResponse({insight:''},native,route,'foreign source'),/not_observed/);
'''
    result = subprocess.run(['node', '-e', script, str(runner)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_worker_source_native_silence_requires_exact_request_binding(tmp_path):
    runner = ROOT / 'qa/prompt-architecture/evals/run-exact-model-evals.cjs'
    db_path = tmp_path / 'runtime.sqlite'
    with sqlite3.connect(db_path) as db:
        db.executescript('''
CREATE TABLE provider_requests(run_id TEXT,session_id TEXT,message_id TEXT,owner_id TEXT,created_at TEXT);
CREATE TABLE provider_sessions(session_id TEXT,conversation_id TEXT,agent_id TEXT,model_id TEXT,access_mode TEXT);
CREATE TABLE runs(run_id TEXT,state TEXT,worker_id TEXT,provider_route_model TEXT,output_text TEXT);
CREATE TABLE workers(worker_id TEXT,state_dir TEXT,bootstrap_bundle_json TEXT);
INSERT INTO provider_requests VALUES ('run','session','request','owner','1');
INSERT INTO provider_sessions VALUES ('session','conversation','agent','codex-cli:synthetic','read_only');
INSERT INTO runs VALUES ('run','completed','worker','synthetic','{NTA}');
INSERT INTO workers VALUES ('worker','state','{}');
''')
    script = r'''
const assert=require('assert'),r=require(process.argv[1]);
const env={WPR_DB_PATH:process.argv[2]},identity={ownerId:'owner',conversationId:'conversation',agentId:'agent',nativeAuthority:true};
const actual=r.queryGlassHiveProviderRun(env,'request',identity);
assert.strictEqual(actual.output_text,'{NTA}');
assert.strictEqual(actual.state,'completed');
for(const field of ['ownerId','conversationId','agentId']) {
 assert.strictEqual(r.queryGlassHiveProviderRun(env,'request',{...identity,[field]:'foreign'}),null);
}
assert.strictEqual(r.queryGlassHiveProviderRun(env,'foreign-request',identity),null);
assert.strictEqual(r.queryGlassHiveProviderRun(env,'request'),null);
assert.strictEqual(r.queryGlassHiveProviderRun(env,'request',{...identity,nativeAuthority:false}).output_text,undefined);
'''
    result = subprocess.run(['node', '-e', script, str(runner), str(db_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('native_tools', [True, False])
@pytest.mark.parametrize('fault',[None,'model','effort','source','request','audit','judge','case'])
@pytest.mark.parametrize('profile,model_key,effort_key', [
    ('claude-code','WPR_MODEL_CLAUDE_CODE','WPR_CLAUDE_CODE_EFFORT'),
    ('grok-build','WPR_MODEL_GROK_BUILD','WPR_GROK_REASONING_EFFORT'),
])
def test_workbench_worker_replay_cannot_claim_unbound_route_or_unjudged_success(monkeypatch,tmp_path,fault,profile,model_key,effort_key,native_tools):
    for key,value in {'GLASSHIVE_DEFAULT_WORKER_PROFILE':profile,model_key:'synthetic',effort_key:'high'}.items():monkeypatch.setenv(key,value)
    route=evals._configured_worker_route('primary',native_tools); identity='a'*64; source='b'*64
    selected=[{'family':{'id':'worker'},'case':{'id':'case','fixture':{'workerSource':{'route':'primary','nativeTools':native_tools}}}}]
    row={'caseId':'case','status':'completed','requestedRoute':route.copy(),'observedRoute':{**route,'state':'completed','nativeTools':native_tools,'instructionsSha256':source},'requestIdentityHash':identity,'observedRequestIdentityHash':identity,'instructionsSha256':source,'nativeAudit':{'stdoutHash':'a'*16},'nativeCalls':[],'semanticJudge':{'status':'judged','pass':True,'rawHash':'a'*16,'attemptCount':1}}
    if fault in {'model','effort'}:row['observedRoute'][fault]='other'
    if fault=='source':row['observedRoute']['instructionsSha256']='c'*64
    if fault=='request':row['observedRequestIdentityHash']='c'*64
    if fault=='audit':row['nativeAudit']={}
    if fault=='judge':row['semanticJudge']['pass']=False
    if fault=='case':row['caseId']='other'
    payload={'kind':'worker_source_replay','sourceSnapshotSha256':source,'sourceFiles':[{'path':'worker.py','sha256':source}],'liveResults':[row]}
    (tmp_path/'exact-model-eval.json').write_text(json.dumps(payload))
    result=evals._worker_source_execution_route(tmp_path,selected=selected)
    assert result['status']==('unverified' if fault else 'verified')


def test_workbench_worker_target_never_uses_main_agent():
    family={'id':'worker','runner':'worker_source','promptRefs':['worker.host_native_harness'],'executionTarget':{'promptRef':'worker.host_native_harness'}}
    selected=[{'family':family,'case':{'id':'case'}}]
    assert evals._background_execution_target({'families':[family]},'worker',selected=selected)=={'mode':'worker_source_replay','promptRef':'worker.host_native_harness'}
    with pytest.raises(ValueError,match='isolated'):
        evals._background_execution_target({},None,selected=selected+[{'family':{'id':'main'},'case':{'id':'other'}}])
