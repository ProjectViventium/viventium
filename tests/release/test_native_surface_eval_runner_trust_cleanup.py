import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = (
    ROOT
    / "qa"
    / "prompt-architecture"
    / "evals"
    / "run-native-surface-playwright-qa.cjs"
)


def test_voice_cleanup_ends_only_calls_created_by_this_run() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const requests = [];
global.fetch = async (url, options) => {
  requests.push({url, method: options.method, authorization: options.headers.Authorization});
  const callSessionId = decodeURIComponent(new URL(url).pathname.split('/').at(-2));
  return {ok:true,status:200,text:async()=>JSON.stringify({callSessionId,status:'ended'})};
};
(async()=>{
  const args = {apiBase:'http://localhost:3180'};
  assert.deepStrictEqual(await runner.endQaCallSessions({args,token:'synthetic-token',
    createdCallIds:new Set()}), {ok:true,endedCallCount:0});
  assert.strictEqual(requests.length,0);
  assert.deepStrictEqual(await runner.endQaCallSessions({args,token:'synthetic-token',
    createdCallIds:new Set(['qa-call-a','qa-call-b','qa-call-a'])}),
    {ok:true,endedCallCount:2});
  assert.deepStrictEqual(requests.map(x=>x.url),[
    'http://localhost:3180/api/viventium/calls/qa-call-a/end',
    'http://localhost:3180/api/viventium/calls/qa-call-b/end']);
  assert.ok(requests.every(x=>x.method==='POST' && x.authorization==='Bearer synthetic-token'));
})().catch(error=>{console.error(error);process.exit(1)});
"""
    result = _node(script)
    assert result.returncode == 0, result.stderr


def test_voice_cleanup_checks_receipt_and_continues_after_failed_end() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const called = [];
global.fetch = async (url) => {
  const id = decodeURIComponent(new URL(url).pathname.split('/').at(-2));
  called.push(id);
  if(id==='unavailable') throw new Error('synthetic private network detail');
  return {ok:id!=='denied',status:id==='denied'?403:200,text:async()=>JSON.stringify({
    callSessionId:id==='mismatch'?'someone-else':id,
    status:id==='not-ended'?'created':'ended'})};
};
(async()=>{
  const ids=['unavailable','denied','mismatch','not-ended','valid'];
  const result=await runner.endQaCallSessions({args:{apiBase:'http://localhost:3180'},
    token:'synthetic-token',createdCallIds:new Set(ids)});
  assert.deepStrictEqual(called,ids);
  assert.deepStrictEqual(result,{ok:false,endedCallCount:1});
  assert.strictEqual(JSON.stringify(result).includes('private'),false);
})().catch(error=>{console.error(error);process.exit(1)});
"""
    result = _node(script)
    assert result.returncode == 0, result.stderr


def test_judge_failure_metadata_keeps_typed_status_without_private_payload() -> None:
    script = r"""
const assert = require('assert');
const crypto = require('crypto');
const runner = require(process.argv[1]);
const hash = value => crypto.createHash('sha256').update(value).digest('hex').slice(0,16);
const events = [{final:true,responseMessage:{content:[
  {type:'error',error_class:'host_capacity',status:503,code:'synthetic_private_code',
   error:'synthetic_private_message',token:'synthetic_private_token',name:'Error'},
  {type:'text',text:'synthetic_private_response'},
]}}];
const result = runner.summarizeJudgeFailureMetadata(events,'host_capacity');
assert.strictEqual(result.errorClass,'host_capacity');
assert.strictEqual(result.errorStatus,503);
assert.deepStrictEqual(result.errorCodeHashes,[hash('synthetic_private_code')]);
assert.deepStrictEqual(result.errorNameHashes,[hash('Error')]);
assert.strictEqual(result.errorName,'Error');
assert.strictEqual(result.errorCode,null);
assert.strictEqual(runner.summarizeJudgeFailureMetadata([
 {final:true,responseMessage:{content:[{type:'error',error_class:'provider_response_failed',
  code:'ECONNREFUSED',statusCode:502,name:'TypeError'}]}}
]).errorCode,'ECONNREFUSED');
assert.strictEqual(result.errorPartCount,1);
assert.strictEqual(result.finalEventReceived,true);
assert.strictEqual(JSON.stringify(result).includes('synthetic_private'),false);
"""
    result = _node(script)
    assert result.returncode == 0, result.stderr


def test_judge_metadata_does_not_invent_failure_or_export_unknown_error_strings() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const success = runner.summarizeJudgeFailureMetadata([
 {final:true,responseMessage:{content:[{type:'text',text:'synthetic_private_text'}]}}
]);
assert.strictEqual(success.errorClass,null);
assert.strictEqual(success.errorStatus,null);
assert.strictEqual(success.errorPartCount,0);
assert.deepStrictEqual(success.errorCodeHashes,[]);
const unknown = runner.summarizeJudgeFailureMetadata([
 {final:true,error:'synthetic_secret_token',responseMessage:{content:{private:'body'}}}
],{status:'503',statusCode:999,code:'synthetic_private_code',name:'synthetic_private_name',
 message:'synthetic_private_message',token:'synthetic_private_token'});
assert.strictEqual(unknown.errorClass,null);
assert.strictEqual(unknown.errorStatus,null);
assert.strictEqual(unknown.errorCode,null);
assert.strictEqual(unknown.errorName,null);
assert.match(unknown.publicErrorClassHash,/^[0-9a-f]{16}$/);
assert.strictEqual(JSON.stringify(unknown).includes('synthetic_'),false);
"""
    result = _node(script)
    assert result.returncode == 0, result.stderr


def test_judge_retains_both_failed_attempts_without_changing_gate_or_cleanup() -> None:
    script = r"""
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const Module = require('module');
const file = process.argv[1];
const loaded = new Module(file,module);
loaded.filename = file;
loaded.paths = Module._nodeModulePaths(path.dirname(file));
loaded._compile(fs.readFileSync(file,'utf8') +
 '\nmodule.exports.testRunJudge=runJudge; buildText=testCase=>testCase.prompt;',file);
let posts = 0;
let streams = 0;
const payloads = [];
global.fetch = async (url,options={}) => {
 if (options.method === 'POST') {
  posts += 1; payloads.push(JSON.parse(options.body));
  return new Response(JSON.stringify({streamId:'synthetic-stream-'+posts}),
    {status:200,headers:{'Content-Type':'application/json'}});
 }
 streams += 1;
 const event = {final:true,conversation:{conversationId:'synthetic-conversation-'+streams},
  responseMessage:{messageId:'synthetic-response-'+streams,content:[
   {type:'error',error_class:'provider_response_failed',status:streams===1?502:503,
    code:'synthetic-private-code-'+streams,error:'synthetic-private-error'}]},
  requestMessage:{messageId:'synthetic-request-'+streams}};
 return new Response('data: '+JSON.stringify(event)+'\n\n',
   {status:200,headers:{'Content-Type':'text/event-stream'}});
};
(async()=>{
 const result = await loaded.exports.testRunJudge({
  args:{apiBase:'http://synthetic.invalid',judgeEndpoint:'synthetic-provider',
    judgeModel:'synthetic-model',qaRunId:'synthetic-qa',timeoutMs:1000},
  token:'synthetic-private-token',
  testCase:{id:'synthetic-case',prompt:'Synthetic prompt.',rubric:['Synthetic rubric.']},
  result:{ok:true,text:'Synthetic answer.'},
 });
 assert.strictEqual(posts,2); assert.strictEqual(streams,2);
 assert.strictEqual(result.ok,false);
 assert.strictEqual(result.verdict,'judge_parse_failed');
 assert.strictEqual(result.error,'provider_response_failed');
 assert.strictEqual(result.attempts,2);
 assert.strictEqual(result.cleanupFinalMetas.length,2);
 assert.deepStrictEqual(result.attemptDiagnostics.map(x=>x.errorStatus),[502,503]);
 assert.deepStrictEqual(result.attemptDiagnostics.map(x=>x.startStatus),[200,200]);
 assert.deepStrictEqual(result.attemptDiagnostics.map(x=>x.streamStatus),[200,200]);
 assert.deepStrictEqual(result.attemptDiagnostics.map(x=>x.attempt),[1,2]);
 assert.ok(result.attemptDiagnostics.every(x=>/^[a-f0-9]{16}$/.test(x.streamIdHash)));
 assert.strictEqual(JSON.stringify(result.attemptDiagnostics).includes('synthetic-private'),false);
 assert.ok(payloads.every(x=>x.ephemeralAgent && x.endpoint==='agents' && x.temperature===0));
})().catch(error=>{console.error(error);process.exit(1)});
"""
    result = _node(script)
    assert result.returncode == 0, result.stderr


def _node(source: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", "-e", source, str(RUNNER)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def test_voice_workbench_typed_input_uses_the_server_owned_participant_contract() -> None:
    script = r"""
const assert = require('assert');
const crypto = require('crypto');
const runner = require(process.argv[1]);
const input = {inputKind:'participant_text', session:{callSessionId:'synthetic-call',
  ownerParticipantIdentity:'server-owner'}, sourceEventId:'synthetic-source', text:'  Hello café.  '};
assert.deepStrictEqual(runner.buildVoiceTypedInput(input), {version:1,kind:'participant_text',
  callSessionId:'synthetic-call',participantIdentity:'server-owner',sourceEventId:'synthetic-source',
  textSha256:crypto.createHash('sha256').update('Hello café.','utf8').digest('hex')});
assert.strictEqual(runner.buildVoiceTypedInput({...input,inputKind:undefined}),null);
assert.throws(()=>runner.buildVoiceTypedInput({...input,inputKind:'microphone_owner'}),
  /voice_input_kind_unsupported/);
assert.throws(()=>runner.buildVoiceTypedInput({...input,session:{callSessionId:'synthetic-call',
  participantIdentity:'guessed-owner'}}),/voice_typed_input_binding_unavailable/);
assert.throws(()=>runner.buildVoiceTypedInput({...input,text:' '}),/voice_typed_input_binding_unavailable/);
assert.throws(()=>runner.buildVoiceTypedInput({...input,sourceEventId:'x'.repeat(161)}),
  /voice_typed_input_binding_unavailable/);
"""
    result = _node(script)
    assert result.returncode == 0, result.stderr
    source = RUNNER.read_text()
    assert 'session: state.body, sourceEventId, text' in source
    assert '...(typedInput ? { typedInput } : {})' in source


def test_native_surface_reads_current_core_trace_metadata_incrementally() -> None:
    script = r"""
const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const runner = require(process.argv[1]);
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'native-frame-trace-'));
const trace = {
  version:2, family:'main_run_create', surface:'voice',
  requested_provider:'h1111111111111111', provider:'h1111111111111111',
  requested_model:'h2222222222222222', model:'h2222222222222222',
  requested_effort:'high', effective_effort:'high', fallback_used:false, fallback_reason:'none',
  agent_id_hash:'3333333333333333', request_identity_hash:'4444444444444444',
  source_hashes:{agent_source:'5555555555555555',librechat_source:'6666666666666666',
    compiled_runtime_config:'7777777777777777',live_installed_runtime_config:'7777777777777777',
    compiler_version:'8888888888888888'},
  layer_tokens:{main_instructions:100}, layer_hashes:{main_instructions:'9999999999999999'},
};
try {
  for (const fileName of ['debug-synthetic.log', 'debug-synthetic.log.1']) {
    const file = path.join(dir, fileName);
    fs.writeFileSync(file, 'old unrelated log\n');
    const before = runner.collectFrameOffsets({logDir:dir});
    fs.appendFileSync(file, 'Unrelated private runtime content\n' +
      'synthetic debug: [PromptFrameTraceTelemetry] '+JSON.stringify(trace)+'\n');
    const delta = runner.readFrameDelta(before,{logDir:dir});
    assert.strictEqual(delta.frames.length,1);
    const frame=delta.frames[0];
    assert.strictEqual(frame.layer_token_estimates.main_instructions,100);
    assert.strictEqual(frame.source_hashes.agent_source,trace.source_hashes.agent_source);
    const evidence=runner.completionEvidenceForCase(delta.frames,'voice',trace.request_identity_hash,true);
    assert.strictEqual(evidence.verified,true);
    assert.deepStrictEqual(evidence.completionProviderHashes,['1111111111111111']);
    assert.deepStrictEqual(evidence.completionModelHashes,['2222222222222222']);
    assert.deepStrictEqual(evidence.requestedEfforts,['high']);
    assert.strictEqual(JSON.stringify(delta).includes('Unrelated private runtime content'),false);
    assert.strictEqual(runner.readFrameDelta(delta.afterOffsets,{logDir:dir}).frames.length,0);
    fs.renameSync(file, file + '.replaced');
    fs.writeFileSync(file,'synthetic debug: [PromptFrameTraceTelemetry] '+JSON.stringify(trace)+'\n');
    fs.writeFileSync(file + '.gz','synthetic debug: [PromptFrameTraceTelemetry] '+JSON.stringify(trace)+'\n');
    fs.writeFileSync(file + '.invalid','synthetic debug: [PromptFrameTraceTelemetry] '+JSON.stringify(trace)+'\n');
    const replacement = runner.readFrameDelta(delta.afterOffsets,{logDir:dir});
    assert.strictEqual(replacement.frames.length,1);
    assert.strictEqual(runner.readFrameDelta(replacement.afterOffsets,{logDir:dir}).frames.length,0);
  }
} finally {fs.rmSync(dir,{recursive:true,force:true});}
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_current_trace_metadata_keeps_missing_source_and_route_lineage_blocked() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const trace={version:2,family:'main_run_create',surface:'voice',
  requested_provider:'h1111111111111111',provider:'h1111111111111111',
  requested_model:'h2222222222222222',model:'h2222222222222222',
  requested_effort:'high',effective_effort:'high',fallback_used:false,fallback_reason:'none',
  agent_id_hash:'3333333333333333',request_identity_hash:'4444444444444444',
  source_hashes:{agent_source:'5555555555555555',librechat_source:'6666666666666666',
    compiled_runtime_config:'7777777777777777',live_installed_runtime_config:'7777777777777777',
    compiler_version:'8888888888888888'}};
const parse=x=>runner.parsePromptFrameTraceLine('debug: [PromptFrameTraceTelemetry] '+JSON.stringify(x));
for(const change of [
  {source_hashes:{...trace.source_hashes,agent_source:'none'}},
  {source_hashes:{...trace.source_hashes,live_installed_runtime_config:'9999999999999999'}},
  {model:'hmissing'},
  {version:1},
]) {
  assert.throws(()=>runner.completionEvidenceForCase([parse({...trace,...change})],
    'voice',trace.request_identity_hash,true),/completion_prompt_frame_source_lineage_missing/);
}
assert.throws(()=>runner.completionEvidenceForCase([parse({...trace,effective_effort:undefined})],
  'voice',trace.request_identity_hash,true),/completion_prompt_frame_route_identity_missing/);
assert.strictEqual(runner.parsePromptFrameTraceLine('unrelated text'),null);
assert.strictEqual(runner.parsePromptFrameTraceLine('debug: [PromptFrameTraceTelemetry] null').parse_error,true);
assert.strictEqual(runner.parsePromptFrameTraceLine('debug: [PromptFrameTraceTelemetry] broken').parse_error,true);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_cli_filters_select_one_exact_native_surface_case() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const args = runner.parseArgs([
  '--family=telegram_smart_delivery',
  '--case-id=telegram_copy_ready_email_skips_optional_audio',
  '--surface=telegram',
  '--max-cases=1',
]);
const bank = {
  families: [
    {
      id: 'telegram_smart_delivery',
      cases: [
        { id: 'telegram_copy_ready_email_skips_optional_audio', surface: 'telegram' },
        { id: 'telegram_conversation_keeps_smart_audio', surface: 'telegram' },
      ],
    },
    { id: 'other_family', cases: [{ id: 'web_case', surface: 'web' }] },
  ],
};
const selected = runner.selectPromptCases(bank, args);
assert.deepStrictEqual(selected.map((item) => item.id), [
  'telegram_copy_ready_email_skips_optional_audio',
]);
assert.strictEqual(args.family, 'telegram_smart_delivery');
assert.strictEqual(args.caseId, 'telegram_copy_ready_email_skips_optional_audio');
assert.strictEqual(args.surface, 'telegram');
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_visible_text_accepts_current_nested_sse_delta_shape() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const events = [
  { event: 'on_message_delta', data: { delta: { content: [{ type: 'text', text: '{"pass":' }] } } },
  { event: 'on_message_delta', data: { delta: { text: 'true}' } } },
  { final: true, responseMessage: { text: '   ' } },
];
assert.strictEqual(runner.extractVisibleText(events), '{"pass":true}');
assert.strictEqual(runner.extractFinalStreamError(events), null);
assert.strictEqual(
  runner.extractFinalStreamError([{
    final: true,
    responseMessage: {
      text: '',
      content: [{ type: 'error', error_class: 'provider_rate_limited' }],
    },
  }]),
  'provider_rate_limited',
);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_cli_filters_fail_closed_when_no_case_matches() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const args = runner.parseArgs(['--case-id=missing_case', '--surface=telegram']);
assert.throws(
  () => runner.selectPromptCases({ families: [] }, args),
  /native_surface_case_selection_empty/,
);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_plural_case_filter_and_workbench_flags_are_exact_and_fail_closed() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const bank = {
  families: [{
    id: 'telegram_smart_delivery',
    promptRefs: ['main.conscious_agent', 'surface.telegram.text'],
    cases: [
      { id: 'telegram_first', surface: 'telegram' },
      { id: 'telegram_second', surface: 'telegram' },
      { id: 'web_third', surface: 'web' },
    ],
  }],
};
const args = runner.parseArgs([
  '--family=telegram_smart_delivery',
  '--case-ids=telegram_second,telegram_first',
  '--surface=telegram',
  '--prompt-id=surface.telegram.text',
  '--run-live',
]);
const selected = runner.selectPromptCases(bank, args);
assert.deepStrictEqual(selected.map((item) => item.id), ['telegram_second', 'telegram_first']);
assert.deepStrictEqual(args.caseIds, ['telegram_second', 'telegram_first']);
assert.strictEqual(args.promptId, 'surface.telegram.text');
assert.strictEqual(args.runLive, true);
assert.throws(
  () => runner.selectPromptCases(bank, runner.parseArgs([
    '--case-id=telegram_first', '--case-ids=telegram_first,telegram_second',
  ])),
  /native_surface_case_selection_conflict/,
);
assert.throws(
  () => runner.selectPromptCases(bank, runner.parseArgs([
    '--case-ids=telegram_first,telegram_first',
  ])),
  /native_surface_case_selection_duplicate/,
);
assert.throws(
  () => runner.selectPromptCases(bank, runner.parseArgs([
    '--case-ids=telegram_first,missing_case', '--surface=telegram',
  ])),
  /native_surface_case_selection_missing/,
);
assert.throws(
  () => runner.selectPromptCases(bank, runner.parseArgs([
    '--case-ids=',
  ])),
  /native_surface_case_selection_empty_requested_ids/,
);
assert.throws(
  () => runner.selectPromptCases(bank, runner.parseArgs([
    '--case-ids=telegram_first,,telegram_second',
  ])),
  /native_surface_case_selection_malformed_requested_ids/,
);
for (const emptySelector of ['--case-id=', '--family=', '--surface=', '--prompt-id=']) {
  assert.throws(
    () => runner.selectPromptCases(bank, runner.parseArgs([emptySelector])),
    /native_surface_case_selection_empty_selector/,
  );
}
assert.throws(
  () => runner.selectPromptCases(bank, runner.parseArgs([
    '--case-ids=telegram_first,telegram_second', '--max-cases=1',
  ])),
  /native_surface_case_selection_truncated/,
);
for (const invalidLimit of ['--max-cases=', '--max-cases=0', '--max-cases=two']) {
  assert.throws(
    () => runner.selectPromptCases(bank, runner.parseArgs([invalidLimit])),
    /native_surface_case_selection_invalid_max_cases/,
  );
}
for (const duplicateSelector of [
  ['--family=telegram_smart_delivery', '--family=telegram_smart_delivery'],
  ['--case-id=telegram_first', '--case-id=telegram_first'],
  ['--case-ids=telegram_first', '--case-ids=telegram_first'],
  ['--surface=telegram', '--surface=telegram'],
  ['--prompt-id=surface.telegram.text', '--prompt-id=surface.telegram.text'],
]) {
  assert.throws(
    () => runner.selectPromptCases(bank, runner.parseArgs(duplicateSelector)),
    /native_surface_case_selection_duplicate_selector/,
  );
}
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_selected_cases_retain_family_semantic_judge_requirement() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const cases = runner.flattenPromptCases({
  families: [
    {
      id: 'telegram_smart_delivery',
      semanticJudge: true,
      cases: [{ id: 'telegram_case', surface: 'telegram' }],
    },
    {
      id: 'case_override',
      semanticJudge: false,
      cases: [{ id: 'case_semantic', surface: 'voice', semanticJudge: true }],
    },
    {
      id: 'decision_quality',
      cases: [{
        id: 'decision_case',
        surface: 'scheduler',
        decisionQualityContract: { transportPassIsSemanticPass: false },
      }],
    },
  ],
});
assert.strictEqual(cases[0].semanticJudge, true);
assert.strictEqual(cases[0].familySemanticJudge, true);
assert.strictEqual(cases[1].semanticJudge, true);
assert.strictEqual(cases[1].familySemanticJudge, false);
assert.strictEqual(cases[2].semanticJudge, false);
assert.strictEqual(cases[2].familySemanticJudge, false);
assert.strictEqual(runner.caseRequiresSemanticJudge(cases[0]), true);
assert.strictEqual(runner.caseRequiresSemanticJudge(cases[1]), true);
assert.strictEqual(runner.caseRequiresSemanticJudge(cases[2]), true);
assert.strictEqual(runner.caseRequiresSemanticJudge({ semanticJudge: false }), false);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_native_runner_requires_explicit_live_authority() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
assert.doesNotThrow(() => runner.assertNativeLiveRunRequested(
  runner.parseArgs(['--run-live']),
));
assert.throws(
  () => runner.assertNativeLiveRunRequested(runner.parseArgs([])),
  /native_surface_live_run_not_authorized/,
);
assert.throws(
  () => runner.assertNativeLiveRunRequested(runner.parseArgs(['--run-live', '--no-live'])),
  /native_surface_live_run_not_authorized/,
);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_completion_prompt_frame_surface_must_match_exactly() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const expectedRequestIdentityHash = runner.buildPromptFrameRequestIdentityHash({
  ownerId: 'synthetic-owner',
  surface: 'telegram',
  sourceEventId: 'server-valid-source-event',
});
const unrelatedRequestIdentityHash = 'fedcba9876543210';
const exactRoute = {
  requested_provider: 'openAI',
  requested_model: 'gpt-test',
  requested_effort: 'high',
  provider: 'openAI',
  model: 'gpt-test',
  effective_effort: 'high',
  fallback_used: false,
  fallback_reason: 'none',
};
const matching = runner.assertCompletionPromptFrameSurface([
  { event: 'viventium.prompt_frame', prompt_family: 'background_activation', surface: 'web' },
  {
    event: 'viventium.prompt_frame',
    prompt_family: 'main_run_create',
    surface: 'web',
    request_identity_hash: unrelatedRequestIdentityHash,
    agent_id_hash: 'fedcba9876543210',
    ...exactRoute,
    provider: 'other-provider',
    model: 'other-model',
  },
  {
    event: 'viventium.prompt_frame',
    prompt_family: 'main_run_create',
    surface: 'telegram',
    request_identity_hash: expectedRequestIdentityHash,
    agent_id_hash: '0123456789abcdef',
    ...exactRoute,
  },
], 'telegram', expectedRequestIdentityHash);
assert.strictEqual(matching.verified, true);
assert.strictEqual(matching.requestedSurface, 'telegram');
assert.strictEqual(matching.observedSurface, 'telegram');
assert.strictEqual(matching.completionFrameCount, 1);
assert.strictEqual(matching.requestIdentityHash, expectedRequestIdentityHash);
assert.strictEqual(matching.actualCompletionAgentIdHash, '0123456789abcdef');
assert.match(matching.completionProviderHashes[0], /^[0-9a-f]{16}$/);
assert.match(matching.completionModelHashes[0], /^[0-9a-f]{16}$/);
assert.deepStrictEqual(matching.requestedEfforts, ['high']);
assert.deepStrictEqual(matching.effectiveEfforts, ['high']);
assert.strictEqual(matching.fallbackUsed, false);
assert.deepStrictEqual(matching.fallbackReasons, ['none']);
assert.throws(
  () => runner.assertCompletionPromptFrameSurface([
    {
      event: 'viventium.prompt_frame', prompt_family: 'main_run_create', surface: 'web',
      request_identity_hash: expectedRequestIdentityHash,
      agent_id_hash: '0123456789abcdef', ...exactRoute,
    },
  ], 'telegram', expectedRequestIdentityHash),
  /completion_prompt_frame_surface_mismatch/,
);
assert.throws(
  () => runner.assertCompletionPromptFrameSurface([
    { event: 'viventium.prompt_frame', prompt_family: 'background_activation', surface: 'telegram' },
  ], 'telegram', expectedRequestIdentityHash),
  /completion_prompt_frame_missing/,
);
assert.throws(
  () => runner.assertCompletionPromptFrameSurface([{
      event: 'viventium.prompt_frame', prompt_family: 'main_run_create', surface: 'telegram',
      request_identity_hash: unrelatedRequestIdentityHash,
      agent_id_hash: '0123456789abcdef', ...exactRoute,
  }], 'telegram', expectedRequestIdentityHash),
  /completion_prompt_frame_request_identity_unrelated_only/,
);
assert.throws(
  () => runner.assertCompletionPromptFrameSurface([
    {
      event: 'viventium.prompt_frame', prompt_family: 'main_run_create', surface: 'telegram',
      agent_id_hash: '0123456789abcdef', ...exactRoute,
    },
    {
      event: 'viventium.prompt_frame', prompt_family: 'main_run_create', surface: 'telegram',
      request_identity_hash: expectedRequestIdentityHash,
      agent_id_hash: '0123456789abcdef', ...exactRoute,
    },
  ], 'telegram', expectedRequestIdentityHash),
  /completion_prompt_frame_request_identity_missing/,
);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_request_identity_uses_exact_trusted_surface_and_telegram_source_event() -> None:
    script = r"""
const assert = require('assert');
const crypto = require('crypto');
const runner = require(process.argv[1]);
const ownerId = 'synthetic-owner-id';
const telegramUserId = 'qa_native_1234';
const telegramChatId = 'qa_native_1234';
const sourceSequence = 123456789;
const sourceOrderScope = runner.buildTelegramSourceOrderScope({
  ownerId,
  telegramUserId,
  telegramChatId,
  messageThreadId: '',
});
const sourceEventId = runner.buildTelegramSourceEventId({
  sourceOrderScope,
  sourceSequence,
});
const expectedSourceOrderScope = crypto.createHash('sha256').update([
  'viventium.telegram-source-order.v2',
  'telegram-interactive-v1',
  ownerId,
  telegramUserId,
  telegramChatId,
  '',
].join('\0')).digest('hex');
const expectedSourceEventId = crypto.createHash('sha256').update([
  'viventium.telegram-source-event.v1',
  expectedSourceOrderScope,
  String(sourceSequence),
].join('\0')).digest('hex');
const expectedRequestIdentityHash = crypto.createHash('sha256').update([
  'viventium.prompt-frame-request.v1',
  ownerId,
  'telegram',
  expectedSourceEventId,
].join('\0')).digest('hex').slice(0, 16);
assert.strictEqual(sourceOrderScope, expectedSourceOrderScope);
assert.strictEqual(sourceEventId, expectedSourceEventId);
assert.strictEqual(
  runner.buildPromptFrameRequestIdentityHash({
    ownerId,
    surface: 'telegram',
    sourceEventId,
  }),
  expectedRequestIdentityHash,
);
assert.strictEqual(runner.trustedCompletionSurface('wing'), 'voice');
assert.strictEqual(runner.trustedCompletionSurface('listen_only'), 'voice');
assert.strictEqual(runner.trustedCompletionSurface('scheduler'), 'workbench');
assert.strictEqual(runner.trustedCompletionSurface('telegram'), 'telegram');
assert.throws(
  () => runner.buildPromptFrameRequestIdentityHash({
    ownerId: '', surface: 'telegram', sourceEventId,
  }),
  /prompt_frame_request_identity_context_invalid/,
);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_telegram_source_order_is_observed_and_verified_before_chat() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);

(async () => {
  const sourceOrderScope = 'a'.repeat(64);
  const sourceEventId = 'b'.repeat(64);
  const sourceSequence = 123456789;
  const calls = [];
  const fetcher = async (url, options) => {
    calls.push({ url, options });
    if (url.endsWith('/api/viventium/telegram/source-order')) {
      return {
        ok: true,
        status: 200,
        body: {
          observed: true,
          sourceOrderScope,
          sourceEventId,
          latestSourceSequence: sourceSequence,
          stale: false,
          durability: 'durable',
          replicaSafe: true,
        },
      };
    }
    return { ok: true, status: 200, body: { streamId: 'synthetic-stream' } };
  };
  const body = {
    text: 'Synthetic Telegram request',
    telegramUserId: 'qa_telegram_user',
    telegramChatId: 'qa_telegram_chat',
    telegramMessageThreadId: '',
    telegramMessageId: String(sourceSequence),
    sourceSequence,
    sourceOrderScope,
    sourceEventId,
  };
  const result = await runner.startTelegramSurfaceTurn({
    args: { apiBase: 'http://localhost:3180' },
    headers: { 'X-VIVENTIUM-TELEGRAM-SECRET': 'synthetic-secret' },
    body,
    fetcher,
  });
  assert.deepStrictEqual(calls.map((entry) => new URL(entry.url).pathname), [
    '/api/viventium/telegram/source-order',
    '/api/viventium/telegram/chat',
  ]);
  assert.strictEqual(result.sourceOrder.observed, true);
  assert.strictEqual(result.sourceOrder.sourceOrderScope, sourceOrderScope);
  assert.strictEqual(result.sourceOrder.sourceEventId, sourceEventId);
  assert.strictEqual(result.sourceOrder.latestSourceSequence, sourceSequence);
  assert.strictEqual(result.start.body.streamId, 'synthetic-stream');

  for (const badBody of [
    { observed: false, sourceOrderScope, sourceEventId, latestSourceSequence: sourceSequence },
    { observed: true, sourceOrderScope: 'c'.repeat(64), sourceEventId, latestSourceSequence: sourceSequence },
    { observed: true, sourceOrderScope, sourceEventId: 'd'.repeat(64), latestSourceSequence: sourceSequence },
    { observed: true, sourceOrderScope, sourceEventId, latestSourceSequence: sourceSequence + 1 },
  ]) {
    const badCalls = [];
    await assert.rejects(
      () => runner.startTelegramSurfaceTurn({
        args: { apiBase: 'http://localhost:3180' },
        headers: { 'X-VIVENTIUM-TELEGRAM-SECRET': 'synthetic-secret' },
        body,
        fetcher: async (url) => {
          badCalls.push(url);
          return { ok: true, status: 200, body: badBody };
        },
      }),
      /telegram_source_order_observation_unverified/,
    );
    assert.strictEqual(badCalls.length, 1);
    assert.match(badCalls[0], /\/api\/viventium\/telegram\/source-order$/);
  }
})().catch((error) => { console.error(error); process.exit(1); });
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_cleanup_restores_mapping_and_removes_only_exact_qa_run_rows() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);

function readPath(value, dotted) {
  return dotted.split('.').reduce((current, key) => current?.[key], value);
}
function equal(left, right) {
  return String(left) === String(right);
}
function matches(row, query) {
  return Object.entries(query || {}).every(([key, expected]) => {
    const actual = readPath(row, key);
    if (expected && typeof expected === 'object' && !Array.isArray(expected)) {
      if ('$in' in expected) return expected.$in.some((value) => equal(actual, value));
      if ('$gte' in expected) return new Date(actual).getTime() >= new Date(expected.$gte).getTime();
    }
    return equal(actual, expected);
  });
}
function database(seed) {
  const rows = structuredClone(seed);
  return {
    rows,
    collection(name) {
      const collection = rows[name];
      return {
        find(query) {
          let selected = collection.filter((row) => matches(row, query));
          return {
            project() { return this; },
            limit(count) { selected = selected.slice(0, count); return this; },
            async toArray() { return structuredClone(selected); },
          };
        },
        async findOne(query) {
          return structuredClone(collection.find((row) => matches(row, query)) || null);
        },
        async countDocuments(query) {
          return collection.filter((row) => matches(row, query)).length;
        },
        async deleteOne(query) {
          const index = collection.findIndex((row) => matches(row, query));
          if (index < 0) return { deletedCount: 0 };
          collection.splice(index, 1);
          return { deletedCount: 1 };
        },
        async replaceOne(query, replacement) {
          const index = collection.findIndex((row) => matches(row, query));
          if (index < 0) return { matchedCount: 0, modifiedCount: 0 };
          collection[index] = structuredClone(replacement);
          return { matchedCount: 1, modifiedCount: 1 };
        },
      };
    },
  };
}

(async () => {
  const runStartedAt = new Date('2026-08-25T20:00:00.000Z');
  const originalMapping = {
    _id: 'mapping-qa',
    telegramUserId: 'qa_native_1234',
    libreChatUserId: 'qa-user',
    telegramUsername: 'prior_synthetic',
  };
  const db = database({
    sessions: [
      { _id: 'session-run', user: 'qa-user', refreshTokenHash: 'rotated-run-hash' },
      { _id: 'session-other-qa', user: 'qa-user', refreshTokenHash: 'other-run-hash' },
      { _id: 'session-personal', user: 'personal-user', refreshTokenHash: 'personal-hash' },
    ],
    telegramusermappings: [{
      ...originalMapping,
      telegramUsername: 'qa_native_surface',
      viventiumNativeSurfaceQaRunId: 'native-run-1',
    }],
    messages: [
      {
        _id: 'message-run',
        user: 'qa-user',
        conversationId: 'conversation-run',
        createdAt: '2026-08-25T20:00:01.000Z',
        metadata: { viventium: { qaRun: true, qaRunId: 'native-run-1' } },
      },
      {
        _id: 'message-old-qa',
        user: 'qa-user',
        conversationId: 'conversation-old',
        createdAt: '2026-08-24T20:00:00.000Z',
        metadata: { viventium: { qaRun: false } },
      },
      {
        _id: 'message-personal',
        user: 'personal-user',
        conversationId: 'conversation-personal',
        createdAt: '2026-08-25T20:00:01.000Z',
        metadata: { viventium: { qaRun: true, qaRunId: 'native-run-1' } },
      },
    ],
    conversations: [
      { _id: 'conversation-row-run', user: 'qa-user', conversationId: 'conversation-run' },
      { _id: 'conversation-row-old', user: 'qa-user', conversationId: 'conversation-old' },
      { _id: 'conversation-row-personal', user: 'personal-user', conversationId: 'conversation-personal' },
    ],
  });

  const result = await runner.cleanupExactQaArtifacts({
    db,
    qaUser: {
      _id: 'qa-user', email: 'qa@example.com', role: 'USER', viventiumApprovalStatus: 'approved',
    },
    qaEmail: 'qa@example.com',
    ownerEmail: 'owner@example.com',
    qaRunId: 'native-run-1',
    runStartedAt,
    sessionRecord: { _id: 'session-run', user: 'qa-user', refreshTokenHash: 'run-hash' },
    mappingState: {
      telegramUserId: 'qa_native_1234',
      currentId: 'mapping-qa',
      originalDocument: originalMapping,
    },
    preexistingConversationIds: new Set(['conversation-old']),
    trackedConversationIds: new Set(['conversation-run']),
  });

  assert.deepStrictEqual(result, {
    cleaned: true,
    mappingAction: 'restored',
    removedSessionCount: 1,
    removedMessageCount: 1,
    removedConversationCount: 1,
  });
  assert.deepStrictEqual(db.rows.telegramusermappings, [originalMapping]);
  assert.deepStrictEqual(db.rows.sessions.map((row) => row._id), ['session-other-qa', 'session-personal']);
  assert.deepStrictEqual(
    db.rows.messages.map((row) => row._id).sort(),
    ['message-old-qa', 'message-personal'],
  );
  assert.deepStrictEqual(
    db.rows.conversations.map((row) => row.conversationId).sort(),
    ['conversation-old', 'conversation-personal'],
  );
})().catch((error) => { console.error(error); process.exit(1); });
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_cleanup_deletes_only_the_exact_new_mapping_and_failure_blocks_run() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);

(async () => {
  const deletions = [];
  const db = {
    collection(name) {
      return {
        find() { return { project() { return this; }, limit() { return this; }, async toArray() { return []; } }; },
        async findOne(query) {
          if (name === 'telegramusermappings') {
            return {
              _id: 'new-mapping',
              telegramUserId: 'qa_native_5678',
              libreChatUserId: 'qa-user',
              viventiumNativeSurfaceQaRunId: 'native-run-2',
            };
          }
          return null;
        },
        async countDocuments() { return 0; },
        async deleteOne(query) {
          deletions.push({ name, query });
          return { deletedCount: name === 'sessions' ? 0 : 1 };
        },
        async replaceOne() { throw new Error('must_not_restore_new_mapping'); },
      };
    },
  };

  await assert.rejects(
    () => runner.cleanupExactQaArtifacts({
      db,
      qaUser: {
        _id: 'qa-user', email: 'qa@example.com', role: 'USER', viventiumApprovalStatus: 'approved',
      },
      qaEmail: 'qa@example.com',
      ownerEmail: 'owner@example.com',
      qaRunId: 'native-run-2',
      runStartedAt: new Date('2026-08-25T20:00:00.000Z'),
      sessionRecord: { _id: 'session-run', user: 'qa-user', refreshTokenHash: 'run-hash' },
      mappingState: {
        telegramUserId: 'qa_native_5678',
        currentId: 'new-mapping',
        originalDocument: null,
      },
      preexistingConversationIds: new Set(),
      trackedConversationIds: new Set(),
    }),
    /native_surface_qa_cleanup_failed/,
  );
  assert.strictEqual(
    deletions.some((entry) => entry.name === 'telegramusermappings'),
    true,
  );

  const summary = runner.summarizeRun({
    generatedAt: '2026-08-25T20:00:00.000Z',
    args: { semanticRequired: false },
    browserProbe: { ok: true },
    cleanup: { ok: false, error: 'native_surface_qa_cleanup_failed' },
    cases: [],
  });
  assert.strictEqual(summary.cleanupOk, false);
  assert.strictEqual(summary.status, 'completed_with_failures_or_gaps');
  const absentCleanup = runner.summarizeRun({
    generatedAt: '2026-08-25T20:00:00.000Z',
    args: { semanticRequired: false },
    browserProbe: { ok: true },
    cases: [],
  });
  assert.strictEqual(absentCleanup.cleanupOk, false);
  const emptySelection = runner.summarizeRun({
    generatedAt: '2026-08-25T20:00:00.000Z',
    args: { semanticRequired: false },
    browserProbe: { ok: true },
    cleanup: { ok: true },
    selection: { selectedCaseIds: [], selectedCaseCount: 0 },
    cases: [],
  });
  assert.strictEqual(emptySelection.selectedCoverageOk, false);
  assert.strictEqual(emptySelection.status, 'completed_with_failures_or_gaps');
})().catch((error) => { console.error(error); process.exit(1); });
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_cleanup_refuses_unproven_conversation_and_cross_owner_session() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);

(async () => {
  const deletions = [];
  const db = {
    collection(name) {
      return {
        find(query) {
          const values = name === 'conversations'
            ? [{ _id: 'empty-row', user: 'qa-user', conversationId: 'unproven-empty' }]
            : [];
          return {
            project() { return this; },
            limit() { return this; },
            async toArray() { return values; },
          };
        },
        async findOne() { return null; },
        async countDocuments() { return 0; },
        async deleteOne(query) {
          deletions.push({ name, query });
          return { deletedCount: 1 };
        },
      };
    },
  };

  await assert.rejects(
    () => runner.cleanupExactQaArtifacts({
      db,
      qaUser: {
        _id: 'qa-user', email: 'qa@example.com', role: 'USER',
        viventiumApprovalStatus: 'approved',
      },
      qaEmail: 'qa@example.com',
      ownerEmail: 'owner@example.com',
      qaRunId: 'native-run-3',
      runStartedAt: new Date('2026-08-25T20:00:00.000Z'),
      sessionRecord: {
        _id: 'personal-session', user: 'personal-user', refreshTokenHash: 'personal-hash',
      },
      mappingState: null,
      preexistingConversationIds: new Set(),
      trackedConversationIds: new Set(['unproven-empty']),
    }),
    /native_surface_qa_cleanup_failed/,
  );
  assert.deepStrictEqual(deletions, []);
})().catch((error) => { console.error(error); process.exit(1); });
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_personal_or_admin_account_is_refused_before_any_cleanup() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
assert.throws(
  () => runner.assertSelectedSyntheticQaUser({
    qaEmail: 'owner@example.com',
    ownerEmail: 'owner@example.com',
    user: {
      _id: 'owner', email: 'owner@example.com', role: 'USER', viventiumApprovalStatus: 'approved',
    },
  }),
  /personal_owner_account_refused/,
);
assert.throws(
  () => runner.assertSelectedSyntheticQaUser({
    qaEmail: 'qa@example.com',
    ownerEmail: 'owner@example.com',
    user: {
      _id: 'qa', email: 'qa@example.com', role: 'ADMIN', viventiumApprovalStatus: 'approved',
    },
  }),
  /admin_qa_account_refused/,
);
assert.throws(
  () => runner.assertSelectedSyntheticQaUser({
    qaEmail: 'qa@real-company.test',
    ownerEmail: 'owner@example.com',
    user: {
      _id: 'qa', email: 'qa@real-company.test', role: 'USER',
      viventiumApprovalStatus: 'approved',
    },
  }),
  /synthetic_qa_account_required/,
);
assert.throws(
  () => runner.assertSelectedSyntheticQaUser({
    qaEmail: 'qa@example.com',
    ownerEmail: 'owner@example.com',
    user: { _id: 'qa', email: 'qa@example.com', role: 'USER' },
  }),
  /approved_synthetic_qa_account_required/,
);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_canonical_artifact_summary_has_strict_workbench_coverage_fields() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const privateRun = {
  generatedAt: '2026-08-25T20:00:00.000Z',
  args: { semanticRequired: true },
  browserProbe: { ok: true, mcpStatus: { public: {} } },
  cleanup: { ok: true, mappingAction: 'restored' },
  selection: {
    selectedCaseIds: ['telegram_case'],
    selectedCaseCount: 1,
  },
  cases: [{
    caseId: 'telegram_case',
    status: 'completed',
    surface: 'telegram',
    route: 'telegram_gateway',
    responseHash: 'response-hash',
    requestedSurface: 'telegram',
    requestedCompletionSurface: 'telegram',
    observedCompletionSurface: 'telegram',
    completionExpected: true,
    completionSurfaceVerified: true,
    requestIdentityHash: '3333333333333333',
    actualCompletionAgentIdHash: '0123456789abcdef',
    completionProviderHashes: ['1111111111111111'],
    completionModelHashes: ['2222222222222222'],
    semanticPass: true,
    judge: { verdict: 'pass' },
    frameSummary: { surfaces: ['telegram'] },
    private: {
      completionFrames: [{
        event: 'viventium.prompt_frame',
        prompt_family: 'main_run_create',
        surface: 'telegram',
        request_identity_hash: '3333333333333333',
        agent_id_hash: '0123456789abcdef',
        provider: 'openAI',
        model: 'gpt-test',
      }],
    },
  }],
};
const summary = runner.summarizeRun(privateRun);
assert.strictEqual(summary.selectedCoverageOk, true);
assert.strictEqual(summary.selectedCaseCount, 1);
assert.strictEqual(summary.resultCount, 1);
assert.strictEqual(summary.completedCount, 1);
assert.strictEqual(summary.failedCount, 0);
assert.strictEqual(summary.semanticJudgedCount, 1);
assert.strictEqual(summary.semanticPassedCount, 1);
assert.strictEqual(summary.semanticFailedCount, 0);
assert.strictEqual(summary.cleanupOk, true);
assert.strictEqual(summary.status, 'completed_with_semantic_native_surface_evidence');
const missingRequestIdentity = structuredClone(privateRun);
delete missingRequestIdentity.cases[0].requestIdentityHash;
assert.strictEqual(runner.summarizeRun(missingRequestIdentity).completionEvidenceOk, false);
const substitutedRequestIdentity = structuredClone(privateRun);
substitutedRequestIdentity.cases[0].private.completionFrames[0].request_identity_hash =
  '4444444444444444';
assert.strictEqual(runner.summarizeRun(substitutedRequestIdentity).completionEvidenceOk, false);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_canonical_artifact_keeps_frames_but_never_raw_runtime_ids() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const privateRun = {
  selection: { selectedCaseIds: ['safe_case'], selectedCaseCount: 1 },
      cases: [{
        caseId: 'safe_case',
        requestIdentityHash: '3333333333333333',
        judge: {
      verdict: 'pass',
      cleanupFinalMetas: [{
        conversationId: 'raw-judge-conversation', responseMessageId: 'raw-judge-message',
      }],
    },
    private: {
      result: {
        text: 'safe synthetic answer',
        finalMeta: {
          conversationId: 'raw-main-conversation',
          responseMessageId: 'raw-main-message',
          requestMessageId: 'raw-request-message',
        },
        privateEvents: [{
          messageId: 'raw-event-message',
          metadata: { viventium: { interactionContext: {
            source_event_id: 'raw-source-event', ownerId: 'raw-owner-id',
          } } },
        }],
      },
      frames: [{
        event: 'viventium.prompt_frame',
        prompt_family: 'main_run_create',
        surface: 'telegram',
        request_identity_hash: '3333333333333333',
        agent_id_hash: '0123456789abcdef',
        provider: 'openAI',
        model: 'gpt-test',
        debug_redacted_layers: { prompt: 'must-not-enter-artifact' },
      }, {
        event: 'viventium.prompt_frame',
        prompt_family: 'main_run_create',
        surface: 'telegram',
        request_identity_hash: '4444444444444444',
        agent_id_hash: 'fedcba9876543210',
        provider: 'unrelated-private-provider',
        model: 'unrelated-private-model',
      }],
      completionFrames: [{
        event: 'viventium.prompt_frame',
        prompt_family: 'main_run_create',
        surface: 'telegram',
        request_identity_hash: '3333333333333333',
        agent_id_hash: '0123456789abcdef',
        provider: 'openAI',
        model: 'gpt-test',
      }],
    },
  }],
};
const artifact = runner.buildCanonicalArtifact(privateRun);
const encoded = JSON.stringify(artifact);
for (const raw of [
  'raw-judge-conversation', 'raw-judge-message', 'raw-main-conversation',
  'raw-main-message', 'raw-request-message', 'raw-event-message', 'raw-source-event',
  'raw-owner-id', 'must-not-enter-artifact',
  'unrelated-private-provider', 'unrelated-private-model',
]) {
  assert.strictEqual(encoded.includes(raw), false, raw);
}
assert.strictEqual(
  artifact.cases[0].private.result.finalMetaHashes.conversationIdHash.length,
  16,
);
assert.strictEqual(artifact.cases[0].private.result.privateEventHashes.length, 1);
assert.strictEqual(artifact.cases[0].private.frames[0].provider, 'openAI');
assert.strictEqual(artifact.cases[0].private.frames[0].model, 'gpt-test');
assert.strictEqual(artifact.cases[0].private.frames[0].request_identity_hash, '3333333333333333');
assert.strictEqual(artifact.cases[0].private.frames.length, 1);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_main_finally_requires_cleanup_and_cleanup_failure_exits_nonzero() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "native-surface-playwright-qa.json" in source
    assert "finally {" in source
    assert "await qaAuth.cleanup()" in source
    assert "cleanupFailure" in source
    assert "!summary.cleanupOk" in source
    assert "privateRun.summary = summary" in source
    for field in (
        "selectedCaseCount",
        "resultCount",
        "completedCount",
        "failedCount",
        "semanticJudgedCount",
        "semanticPassedCount",
        "semanticFailedCount",
    ):
        assert field in source
    assert "await qaAuth.close()" not in source


# Reuse the owning runner's existing typed observations without running a live surface.
_NATIVE_JUDGE_OBSERVATION_FIXTURE = r"""
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const Module = require('module');
const file = process.argv[1];
const loaded = new Module(file, module);
loaded.filename = file;
loaded.paths = Module._nodeModulePaths(path.dirname(file));
loaded._compile(fs.readFileSync(file, 'utf8') +
  '\nmodule.exports.judgeObservationTest = { summarizeNativeEventsForJudge, readConversationEvidence };', file);
const runner = loaded.exports;
const fixture = {
  user: 'owner-test', conversationId: 'conversation-test', messageId: 'message-test',
  isCreatedByUser: false, content: [], createdAt: new Date('2026-01-01T00:00:00Z'),
  attachments: [{ file_id: 'native_synthetic_private_id', filename: 'sample.txt', bytes: 17,
    type: 'text/plain', filepath: '/home/test/private/sample.txt',
    download_url: 'https://artifact.example.test/v1/signed-links/synthetic-private' }],
  metadata: { viventium: { nativeToolEvidence: {
    logicalTurnId: 'turn-test', revision: 1,
    evidence: { version: 1, owner_id: 'owner-test', conversation_id: 'conversation-test',
      message_id: 'message-test', request_id: 'chatcmpl-synthetic-private-id',
      run_id: 'run_synthetic_private_id', invocation_id: 'synthetic-private-invocation',
      omitted_results: 0, results: [{ id: 'synthetic-private-call-id', name: 'use_tool',
        status: 'failed', arguments: { text: 'synthetic-private-arguments' },
        output: { text: JSON.stringify({ type: 'MCP', output: { OkayOutput: JSON.stringify({
          status: 'blocked', reason: 'delegation_dispatch_unconfirmed', retryable: true,
          workRef: 'synthetic-private-work-ref',
          download_url: 'https://artifact.example.test/v1/signed-links/synthetic-private',
        }) } }), bytes: 123, redacted: false, omitted_bytes: 0 },
      }],
    },
  } } },
};
const events = [ { event: 'attachment', data: fixture.attachments[0] },
  { final: true, responseMessage: fixture } ];
const summarize = events => JSON.parse(
  runner.judgeObservationTest.summarizeNativeEventsForJudge(events));
"""


def test_judge_projects_bound_native_tools_and_normal_files_without_claiming_download() -> None:
    script = _NATIVE_JUDGE_OBSERVATION_FIXTURE + r"""
const summary = summarize(events);
assert.strictEqual(summary.native_tool_evidence.availability, 'observed');
assert.strictEqual(summary.native_tool_evidence.calls[0].name, 'use_tool');
assert.strictEqual(summary.native_tool_evidence.calls[0].status, 'failed');
assert.strictEqual(summary.native_tool_evidence.calls[0].result_status, 'blocked');
assert.strictEqual(summary.native_tool_evidence.calls[0].result_reason, 'delegation_dispatch_unconfirmed');
assert.strictEqual(summary.native_tool_evidence.calls[0].retryable, true);
assert.strictEqual(summary.normal_attachments.length, 1);
assert.strictEqual(summary.normal_attachments[0].status, 'attached');
assert.strictEqual(summary.normal_attachments[0].bytes, 17);
assert.strictEqual(summary.normal_attachments[0].owner_download_verified, false);
const unavailable = summarize([{ event: 'attachment', data: {
  filename: 'sample.txt', nativeOutputFile: { version: 1, status: 'unavailable',
    code: 'native_output_file_unavailable' },
} }]);
assert.strictEqual(unavailable.normal_attachments[0].status, 'unavailable');
assert.strictEqual(unavailable.normal_attachments[0].code, 'native_output_file_unavailable');
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_judge_keeps_unknown_malformed_and_wrong_scope_native_evidence_unavailable() -> None:
    script = _NATIVE_JUDGE_OBSERVATION_FIXTURE + r"""
for (const field of ['user', 'conversationId', 'messageId']) {
  const message = structuredClone(fixture);
  message[field] = 'different-scope-test';
  assert.strictEqual(summarize([{ final: true, responseMessage: message }])
    .native_tool_evidence.availability, 'unavailable', field);
}
for (const invalid of [undefined, {}, { evidence: { version: 2, results: [] } },
  { evidence: { ...fixture.metadata.viventium.nativeToolEvidence.evidence,
    results: [null] } },
]) {
  const message = structuredClone(fixture);
  message.metadata.viventium.nativeToolEvidence = invalid;
  const observation = summarize([{ final: true, responseMessage: message }]).native_tool_evidence;
  assert.strictEqual(observation.availability, 'unavailable');
  assert.strictEqual(observation.calls, undefined);
}
const completedTool = structuredClone(fixture);
completedTool.metadata.viventium.nativeToolEvidence.evidence.results[0].status = 'completed';
const observation = summarize([{ final: true, responseMessage: completedTool }]).native_tool_evidence;
assert.strictEqual(observation.calls[0].status, 'completed');
assert.strictEqual(observation.calls[0].result_status, 'blocked');
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_existing_db_observations_reach_same_judge_without_sensitive_payloads() -> None:
    script = _NATIVE_JUDGE_OBSERVATION_FIXTURE + r"""
(async () => {
  const db = { collection: () => ({ find: () => ({ sort: () => ({ toArray: async () => [fixture] }) }) }) };
  const result = { finalMeta: { conversationId: fixture.conversationId,
    responseMessageId: fixture.messageId }, text: 'The file is ready.', privateEvents: events };
  result.postCaseEvidence = await runner.judgeObservationTest.readConversationEvidence({
    db, result, conversationId: fixture.conversationId,
  });
  assert.strictEqual(result.postCaseEvidence.nativeToolObservations.availability, 'observed');
  assert.strictEqual(result.postCaseEvidence.normalAttachmentObservations.availability, 'observed');
  assert.strictEqual(result.postCaseEvidence.normalAttachmentObservations.attachments.length, 1);
  const prompt = runner.buildJudgePrompt({ id: 'case-test', surface: 'voice',
    prompt: 'Give me the file.', rubric: ['Deliver the actual file.'] }, result);
  assert(prompt.includes('normal_files'));
  assert(prompt.includes('native_tool_evidence'));
  assert(prompt.includes('delegation_dispatch_unconfirmed'));
  for (const privateValue of ['synthetic-private-arguments', 'synthetic-private-work-ref',
    'synthetic-private-invocation', 'synthetic-private-call-id', 'native_synthetic_private_id',
    'chatcmpl-synthetic-private-id', 'run_synthetic_private_id',
    'https://artifact.example.test', '/home/test/private']) {
    assert.strictEqual(prompt.includes(privateValue), false, privateValue);
  }
  const unsafe = structuredClone(fixture);
  unsafe.metadata.viventium.nativeToolEvidence.evidence.results[0].name =
    'https://artifact.example.test/private 11111111-2222-7333-8444-555555555555 run_private_test';
  unsafe.attachments[0].filename = '/home/test/private/sample.txt';
  const sanitized = JSON.stringify(summarize([{ final: true, responseMessage: unsafe }]));
  for (const privateValue of ['https://artifact.example.test', '/home/test/private',
    '11111111-2222-7333-8444-555555555555', 'run_private_test']) {
    assert.strictEqual(sanitized.includes(privateValue), false);
  }
})().catch(error => { console.error(error); process.exit(1); });
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr
