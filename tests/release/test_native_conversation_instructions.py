"""Exercise compiled Core conversation authority through the actual Native composer."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "viventium_v0_4/LibreChat"
NATIVE = ROOT / "viventium_v0_4/xPerfect/runtime_phase1"


def prepared_turn(tmp_path, scoped_capsule):
    node = shutil.which("node")
    if not node or not (CORE / "packages/api/dist/index.js").is_file():
        pytest.skip("Current compiled Core is required")
    script = r"""
const fs = require('node:fs');
const {buildPromptBundleFixture} = require('./scripts/test-support/promptBundle.cjs');
const promptPath = process.argv[1];
fs.writeFileSync(promptPath, JSON.stringify(buildPromptBundleFixture('./viventium/source_of_truth/prompts')));
process.env.VIVENTIUM_PROMPT_BUNDLE_PATH = promptPath;
const api = require('./packages/api');
if (typeof api.inheritNativeConversationCapabilityInventory !== 'function') throw new Error('Build current Core first');
const capsule = JSON.parse(process.argv[2]) ? '<viventium_feeling_state>Scoped synthetic state.</viventium_feeling_state>' : '';
const binding = {_id:'binding',ownerId:'owner',tenantId:'local',conversationId:'core-chat',agentId:'main',nativeConversationId:'native-chat',active:true,configuration:{model:'codex-cli:synthetic',effort:'high'}};
const source = {_id:'binding:turn',kind:'native_coordinator_source',bindingRef:'binding',turnId:'turn',requestBody:{conversationId:'core-chat',agent_id:'main'}};
let signed;
const adapter = api.createNativeCoordinatorContextAdapter({
 readSource:async()=>source,
 prepareContext:async()=>({instructions:['Identity.',capsule,'Current source evidence.'].filter(Boolean).join('\n\n'),memoryContext:'Exact current memory.',developerInstructionTail:capsule,
 messages:[{role:'user',content:'Original user request.  '}],inheritedConversation:{version:1,sources:[{text:'Original user request.  '}]},
 bundle:{agents_md:'Common broker authority.',codex_md:'Codex broker authority.',claude_md:'Claude broker authority.'}}),
 signBundle:bundle=>{signed=bundle;return {'X-GlassHive-Bootstrap-Bundle-B64':'signed','X-GlassHive-Bootstrap-Signature':'proof'};}
});
adapter.prepareNativeCoordinatorTurn({binding,source,turn:{conversation_id:'native-chat',request_ref:'binding',turn_id:'turn'}}).then(({body})=>{
 process.stdout.write(JSON.stringify({body,bundle:signed,capsule,inventory:api.getRequiredPromptText('worker.native_capability_inventory')}));
}).catch(error=>{console.error(error);process.exitCode=1;});
"""
    result = subprocess.run(
        [node, "-e", script, str(tmp_path / "prompts.json"), json.dumps(scoped_capsule)],
        cwd=CORE, check=True, capture_output=True, text=True, timeout=30,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("profile", ["codex-cli", "claude-code"])
@pytest.mark.parametrize("scoped_capsule", [False, True])
def test_compiled_core_inventory_and_tail_reach_native_once(tmp_path, monkeypatch, profile, scoped_capsule):
    value = prepared_turn(tmp_path, scoped_capsule)
    monkeypatch.syspath_prepend(str(NATIVE / "src"))
    from workers_projects_runtime.conversation_provider import (
        ChatCompletionRequest, _bootstrap_developer_instructions, _developer_instruction_snapshot,
    )
    payload = ChatCompletionRequest.model_validate(value["body"])
    selected = _bootstrap_developer_instructions(value["bundle"], profile)
    authority = _developer_instruction_snapshot(payload, selected, "Native structural contract.")
    assert authority.count(value["inventory"]) == 1
    assert ("Codex broker authority." in authority) is (profile == "codex-cli")
    assert ("Claude broker authority." in authority) is (profile == "claude-code")
    assert "Common broker authority." not in authority
    assert "Exact current memory." in authority
    assert value["body"]["messages"][-1]["content"] == "Original user request.  "
    if scoped_capsule:
        assert authority.count(value["capsule"]) == 1
        assert authority.endswith(value["capsule"])
        assert value["body"]["metadata"]["developer_instruction_tail"] == value["capsule"]
    else:
        assert "developer_instruction_tail" not in value["body"]["metadata"]
        assert "viventium_feeling_state" not in authority


def test_declared_missing_tail_retains_native_rejection(tmp_path, monkeypatch):
    value = prepared_turn(tmp_path, True)
    value["body"]["messages"][0]["content"] = "Authority without declared tail."
    monkeypatch.syspath_prepend(str(NATIVE / "src"))
    from fastapi import HTTPException
    from workers_projects_runtime.conversation_provider import ChatCompletionRequest, _developer_instruction_snapshot
    with pytest.raises(HTTPException, match="Declared developer instruction tail is absent"):
        _developer_instruction_snapshot(ChatCompletionRequest.model_validate(value["body"]))
