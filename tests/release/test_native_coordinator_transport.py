"""Core's goal reader follows the actual Native router, including its snapshot shape."""

import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
LIBRECHAT = ROOT / "viventium_v0_4" / "LibreChat"
NATIVE_SOURCE = ROOT / "viventium_v0_4" / "xPerfect" / "runtime_phase1" / "src"


def test_core_goal_reader_uses_real_native_routes(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    if not NATIVE_SOURCE.is_dir() or not (LIBRECHAT / "node_modules").is_dir():
        pytest.skip("Native source and installed Core Node dependencies are required")
    monkeypatch.syspath_prepend(str(NATIVE_SOURCE))
    from workers_projects_runtime.coordinator_api import install_coordinator_routes

    text = "One. Two."
    sha256 = hashlib.sha256(text.encode()).hexdigest()
    observed = []

    def refresh(tenant, owner, cid, include_history):
        assert (tenant, owner, cid) == ("local", "owner", "native-chat")
        observed.append(("snapshot", include_history))
        return {"conversation_id": cid, "goals": [
            {"goal_id": "unrelated", "source_turn_id": "other", "run_id": "other"},
            {"goal_id": "goal", "source_turn_id": "original", "run_id": "run",
             "state": "completed", "intent_state": "active", "restore_hold": False},
        ]}

    def read_result(tenant, owner, cid, goal_id, offset, max_chars, run_id):
        assert (tenant, owner, cid, goal_id, run_id) == ("local", "owner", "native-chat", "goal", "run")
        assert max_chars == 64000
        observed.append(("result", offset))
        end = min(len(text), offset + 5)
        return {"goal_id": goal_id, "run_id": run_id, "state": "completed",
                "output_text": text[offset:end], "offset": offset,
                "next_offset": end if end < len(text) else None,
                "sha256": sha256, "failure_class": ""}

    app = FastAPI()
    install_coordinator_routes(app, SimpleNamespace(refresh=refresh, read_result=read_result),
                               lambda _request: ("local", "owner"), lambda *_: None)
    required = {
        ("POST", "/v1/coordinator/conversations"),
        ("GET", "/v1/coordinator/conversations/{conversation_id}"),
        ("POST", "/v1/coordinator/conversations/{conversation_id}/turns"),
        ("GET", "/v1/coordinator/conversations/{conversation_id}/turns/{turn_id}"),
        ("POST", "/v1/coordinator/conversations/{conversation_id}/turns/{turn_id}/prepare"),
        ("GET", "/v1/coordinator/conversations/{conversation_id}/goals/{goal_id}/dispatch"),
        ("POST", "/v1/coordinator/conversations/{conversation_id}/goals/{goal_id}/prepare"),
        ("GET", "/v1/coordinator/conversations/{conversation_id}/goals/{goal_id}/result"),
        ("GET", "/v1/coordinator/conversations/{conversation_id}/goals/{goal_id}/actions/{action_key}/preparation"),
        ("POST", "/v1/coordinator/conversations/{conversation_id}/goals/{goal_id}/actions/preflight"),
        ("POST", "/v1/coordinator/conversations/{conversation_id}/goals/{goal_id}/actions"),
        ("POST", "/v1/coordinator/conversations/{conversation_id}/goals/{goal_id}/actions/receipt"),
    }
    actual = {(method.upper(), path) for path, operations in app.openapi()["paths"].items()
              for method in operations}
    assert required <= actual
    paths = [
        "/v1/coordinator/conversations/native-chat?include_history=false",
        "/v1/coordinator/conversations/native-chat/goals/goal/result?offset=0&max_chars=64000&run_id=run",
        "/v1/coordinator/conversations/native-chat/goals/goal/result?offset=5&max_chars=64000&run_id=run",
    ]
    with TestClient(app) as client:
        assert client.get("/v1/coordinator/conversations/native-chat/goals/goal").status_code == 404
        responses = {path: client.get(path) for path in paths}
    assert all(response.status_code == 200 for response in responses.values())
    fixture = tmp_path / "native-http-responses.json"
    fixture.write_text(json.dumps({path: response.json() for path, response in responses.items()}))
    script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const [sourcePath, fixturePath] = process.argv.slice(1);
const fixture = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
const compiled = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
}).outputText;
const sourceModule = {exports: {}};
vm.runInNewContext(compiled, {module: sourceModule, exports: sourceModule.exports,
  require: (name) => ['node:crypto', 'zod'].includes(name) ? require(name) : {},
}, {filename: sourcePath});
const calls = [];
const request = async (owner, path) => {
  if (owner !== 'owner' || !Object.hasOwn(fixture, path)) throw Error('Native route unavailable');
  calls.push(path);
  return fixture[path];
};
(async () => {
  const result = await sourceModule.exports.readNativeCoordinatorGoalResult({
    ownerId: 'owner', conversationId: 'native-chat', goalId: 'goal', runId: 'run',
  }, request);
  process.stdout.write(JSON.stringify({calls, result}));
})().catch((error) => { process.stderr.write(error.message); process.exitCode = 1; });
"""
    result = subprocess.run(["node", "-e", script,
        str(LIBRECHAT / "packages/api/src/glasshive/nativeCoordinatorContext.ts"), str(fixture)],
        cwd=LIBRECHAT, capture_output=True, text=True, check=True)
    decoded = json.loads(result.stdout)
    assert decoded["calls"] == paths
    assert decoded["result"]["outputText"] == text
    assert decoded["result"]["sourceTurnId"] == "original"
    assert decoded["result"]["resultDigest"] == f"sha256:{sha256}"
    assert observed == [("snapshot", False), ("result", 0), ("result", 5)]
