import importlib.util
import json
from pathlib import Path

path = Path(__file__).resolve().parents[2] / 'scripts/viventium/queen_turn_diagnostics.py'
spec = importlib.util.spec_from_file_location('queen_turn_diagnostics', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_completed_public_message_only_and_no_text_leak():
    secret = 'private prompt and hidden reasoning must never be printed'
    events = [
        {'type': 'response_item', 'timestamp': '2026-01-01T00:00:01Z', 'payload': {'type':'reasoning','text':secret}},
        {'type':'response_item','timestamp':'2026-01-01T00:00:02Z','payload':{'type':'message','role':'assistant','channel':'analysis','content':[{'type':'output_text','text':secret}]}},
        {'type':'response_item','timestamp':'2026-01-01T00:00:03Z','payload':{'type':'message','role':'assistant','content':[{'type':'output_text','text':json.dumps({'type':'assistant_response','tool_name':None,'content':secret})}]}},
    ]
    result=module.native_events(map(json.dumps,events))
    assert result['first_complete_public_answer']=='2026-01-01T00:00:03+00:00'
    assert secret not in json.dumps(result)


def test_native_route_and_usage_are_whitelisted():
    events=[{'type':'turn_context','timestamp':'2026-01-01T00:00:01Z','payload':{'model':'example-model','effort':'low','prompt':'secret'}},
            {'type':'event_msg','payload':{'type':'token_count','info':{'last_token_usage':{'input_tokens':100,'cached_input_tokens':20,'output_tokens':5,'reasoning_output_tokens':2,'private':'secret'}}}}]
    result=module.native_events(map(json.dumps,events))
    assert result['effective_effort']=='low'
    assert result['first_usage']=={'input_tokens':100,'cached_input_tokens':20,'output_tokens':5,'reasoning_output_tokens':2}
    assert 'secret' not in json.dumps(result)


def test_exact_identity_required_even_when_log_is_truncated():
    old='2026-01-01T00:00:01Z info: [NativePreview] {"stage":"emit_submitted","messageId":"message... [truncated]'
    other='2026-01-01T00:00:02Z info: [NativePreview] {"messageId":"other","stage":"emit_submitted"}'
    current='2026-01-01T00:00:03Z info: [NativePreview] {"messageId":"message","stage":"emit_submitted","streamId":"... [truncated]'
    assert module.core_forwarding([old,other], 'message')['emit_submitted']=='UNKNOWN'
    assert module.core_forwarding([old,other,current], 'message')['emit_submitted']=='2026-01-01T00:00:03+00:00'


def test_empty_malformed_and_tool_events_are_unknown():
    events=['broken',json.dumps({'type':'response_item','payload':{'type':'message','role':'assistant','content':[{'type':'output_text','text':json.dumps({'type':'assistant_response','tool_name':'read','content':'not an answer'})}]}})]
    assert module.native_events(events)['first_complete_public_answer']=='UNKNOWN'


def test_public_whitespace_is_not_an_answer():
    assert not module.public_message({'type':'message','role':'assistant','content':[{'type':'output_text','text':'{"type":"assistant_response","tool_name":null,"content":" "}'}]})


def test_persistent_session_events_are_bounded_to_exact_run():
    events = [json.dumps({'type':'turn_context','timestamp':f'2026-01-01T00:00:0{n}Z','payload':{'model':f'model-{n}','effort':'low'}}) for n in [1,3,5]]
    result=module.native_events(events,'2026-01-01T00:00:02Z','2026-01-01T00:00:04Z')
    assert result['effective_model']=='model-3'
    assert result['context_ready']=='2026-01-01T00:00:03+00:00'


def test_intentional_silence_is_not_public_answer():
    assert not module.public_message({'type':'message','role':'assistant','content':[{'type':'output_text','text':'{"type":"assistant_response","tool_name":null,"content":"{NTA}"}'}]})


def test_claude_stdout_metadata_does_not_disclose_response_or_claim_timestamps():
    result=module.native_stdout_metadata([json.dumps({'type':'system','subtype':'init','model':'claude-example','prompt':'secret'}),json.dumps({'type':'result','result':'secret','usage':{'input_tokens':40,'output_tokens':3}})])
    assert result['effective_model']=='claude-example'
    assert 'secret' not in json.dumps(result)
    assert 'first_complete_public_answer' not in result


def test_public_commentary_separate_from_envelope_candidate_and_tools_safe():
    events = [
        {'type':'event_msg','timestamp':'2026-01-01T00:00:01Z','payload':{'type':'item_completed','item':{'type':'Reasoning','phase':'commentary','content':'secret'}}},
        {'type':'event_msg','timestamp':'2026-01-01T00:00:02Z','payload':{'type':'item_completed','item':{'type':'AgentMessage','phase':'commentary','content':'private answer'}}},
        {'type':'event_msg','timestamp':'2026-01-01T00:00:03Z','payload':{'type':'item_completed','item':{'type':'McpToolCall','arguments':'secret','result':'secret','status':'completed','duration':{'secs':1,'nanos':500000000}}}},
    ]
    result=module.native_events(map(json.dumps,events))
    assert result['first_completed_public_commentary']=='2026-01-01T00:00:02+00:00'
    assert result['response_envelope_candidate']=='UNKNOWN'
    assert result['public_tool_duration_sum_ms']==1500
    assert result['public_tool_calls']==[{'completed_at':'2026-01-01T00:00:03+00:00','duration_ms':1500,'status':'completed'}]
    assert 'secret' not in json.dumps(result) and 'private answer' not in json.dumps(result)


def test_commentary_and_tool_events_remain_exact_run_bounded():
    events=[json.dumps({'type':'event_msg','timestamp':'2026-01-01T00:00:01Z','payload':{'type':'item_completed','item':{'type':'AgentMessage','phase':'commentary','content':'old'}}})]
    result=module.native_events(events,'2026-01-01T00:00:02Z','2026-01-01T00:00:04Z')
    assert result['first_completed_public_commentary']=='UNKNOWN'
    assert result['public_tool_calls']==[]


def test_core_forwarding_shared_anchor_cannot_leak_into_later_run():
    line='2026-01-01T00:00:03Z info: [NativePreview] {"messageId":"shared","stage":"emit_submitted"}'
    windows=[{'run_id':'main','started_at':'2026-01-01T00:00:01Z','ended_at':'2026-01-01T00:00:04Z'},
             {'run_id':'followup','started_at':'2026-01-01T00:00:05Z','ended_at':'2026-01-01T00:00:08Z'}]
    assert module.core_forwarding([line],'shared','main',windows)['emit_submitted']=='2026-01-01T00:00:03+00:00'
    assert module.core_forwarding([line],'shared','followup',windows)['emit_submitted']=='UNKNOWN'


def test_core_forwarding_overlapping_or_incomplete_windows_fail_closed():
    line='2026-01-01T00:00:03Z info: [NativePreview] {"messageId":"shared","stage":"emit_submitted"}'
    a={'run_id':'main','started_at':'2026-01-01T00:00:01Z','ended_at':'2026-01-01T00:00:04Z'}
    assert module.core_forwarding([line],'shared','main',[a,{**a,'run_id':'writer'}])['emit_submitted']=='UNKNOWN'
    assert module.core_forwarding([line],'shared','main',[{**a,'ended_at':None}])['emit_submitted']=='UNKNOWN'


def test_envelope_candidate_does_not_claim_graph_or_voice_admission():
    envelope={'type':'assistant_response','content':'Synthetic answer','tool_name':None,'unvalidated_control':{'voice':'unsupported'}}
    event={'type':'response_item','timestamp':'2026-01-01T00:00:03Z','payload':{'type':'message','role':'assistant','content':[{'type':'output_text','text':json.dumps(envelope)}]}}
    result=module.native_events([json.dumps(event)])
    assert result['response_envelope_candidate']=='2026-01-01T00:00:03+00:00'
    assert result['first_complete_public_answer']==result['response_envelope_candidate']
    assert 'first_complete_admitted_envelope' not in result
