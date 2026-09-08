from pathlib import Path
import hashlib
import json
import subprocess
import sys
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


@pytest.mark.parametrize('fault',[None,'model','effort','source','request','audit','judge','case'])
def test_workbench_worker_replay_cannot_claim_unbound_route_or_unjudged_success(monkeypatch,tmp_path,fault):
    for key,value in {'GLASSHIVE_DEFAULT_WORKER_PROFILE':'claude-code','WPR_MODEL_CLAUDE_CODE':'synthetic','WPR_CLAUDE_CODE_EFFORT':'default'}.items():monkeypatch.setenv(key,value)
    route=evals._configured_worker_route('primary'); identity='a'*64; source='b'*64
    selected=[{'family':{'id':'worker'},'case':{'id':'case','fixture':{'workerSource':{'route':'primary'}}}}]
    row={'caseId':'case','status':'completed','requestedRoute':route.copy(),'observedRoute':{**route,'state':'completed','nativeTools':True,'instructionsSha256':source},'requestIdentityHash':identity,'observedRequestIdentityHash':identity,'instructionsSha256':source,'nativeAudit':{'stdoutHash':'a'*16},'nativeCalls':[],'semanticJudge':{'status':'judged','pass':True,'rawHash':'a'*16,'attemptCount':1}}
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
