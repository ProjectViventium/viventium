from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts" / "viventium" / "native_mongodb_replica.js"


def config(socket_path: str) -> dict:
    return {
        "_id": "vivenNative",
        "version": 1,
        "term": 1,
        "members": [{"_id": 0, "host": socket_path, "arbiterOnly": False,
                     "buildIndexes": True, "hidden": False, "priority": 1,
                     "tags": {}, "secondaryDelaySecs": 0, "votes": 1}],
        "protocolVersion": 1,
        "writeConcernMajorityJournalDefault": True,
        "settings": {"chainingAllowed": True, "heartbeatIntervalMillis": 2000,
                     "heartbeatTimeoutSecs": 10, "electionTimeoutMillis": 10000,
                     "catchUpTimeoutMillis": -1, "catchUpTakeoverDelayMillis": 30000,
                     "getLastErrorModes": {}, "getLastErrorDefaults": {"w": 1, "wtimeout": 0},
                     "replicaSetId": "0123456789abcdef01234567"},
    }


@pytest.fixture
def replica_case(tmp_path: Path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is unavailable")
    librechat = tmp_path / "LibreChat"
    driver = librechat / "node_modules" / "mongoose"
    driver.mkdir(parents=True)
    (librechat / "package.json").write_text('{"private":true}\n')
    (driver / "index.js").write_text("""
const fs = require('node:fs');
const scenario = JSON.parse(fs.readFileSync(process.env.REPLICA_SCENARIO, 'utf8'));
const calls = [];
function save(value) { calls.push(value); fs.writeFileSync(process.env.REPLICA_CALLS, JSON.stringify(calls)); }
let configuration = scenario.config;
let hellos = 0;
class MongoClient {
  constructor(uri, options) { save({construct: {uri, options}}); }
  async connect() { save({connect:true}); }
  db(name) { save({db:name}); return {command: async command => {
    save({command});
    if (command.replSetGetConfig) {
      if (scenario.readError || !configuration) throw Object.assign(new Error('private server detail'), {code:scenario.readError || 94});
      return {ok:1, config:configuration};
    }
    if (command.replSetInitiate) { configuration = scenario.initializedConfig; return {ok:1}; }
    if (command.hello) {
      hellos++;
      return {ok:1, setName:scenario.helloSet || 'vivenNative', me:scenario.socket,
              hosts:[scenario.socket], isWritablePrimary:hellos > (scenario.notPrimaryCount || 0)};
    }
    throw new Error('unexpected command');
  }}; }
  async close() { save({close:true}); }
}
module.exports = {mongo:{MongoClient}};
""".lstrip())
    # Keep a real Unix socket below the platform path-length limit; no listener or driver connection.
    with tempfile.TemporaryDirectory(prefix="v-mr-", dir="/tmp") as directory:
        socket_path = Path(directory) / "mongo.sock"
        owner_socket = socket.socket(socket.AF_UNIX)
        owner_socket.bind(str(socket_path))
        socket_path.chmod(0o600)
        try:
            def run(scenario: dict, *, selected_socket: str | None = None, timeout: str = "1"):
                scenario = {"socket": str(socket_path), **scenario}
                scenario_path = tmp_path / "scenario.json"
                calls_path = tmp_path / "calls.json"
                scenario_path.write_text(json.dumps(scenario))
                calls_path.unlink(missing_ok=True)
                result = subprocess.run(
                    [node, str(HELPER), str(librechat), selected_socket or str(socket_path), timeout],
                    capture_output=True, text=True, timeout=10,
                    env={**os.environ, "REPLICA_SCENARIO": str(scenario_path), "REPLICA_CALLS": str(calls_path)},
                )
                calls = json.loads(calls_path.read_text()) if calls_path.exists() else []
                return result, calls

            yield socket_path, run
        finally:
            owner_socket.close()


def commands(calls: list[dict]) -> list[dict]:
    return [item["command"] for item in calls if "command" in item]


def test_initializes_only_uninitialized_exact_socket_and_waits_for_primary(replica_case):
    socket_path, run = replica_case
    result, calls = run({"initializedConfig": config(str(socket_path)), "notPrimaryCount": 1})
    assert result.returncode == 0, result.stderr
    issued = commands(calls)
    assert [c["replSetInitiate"] for c in issued if "replSetInitiate" in c] == [
        {"_id": "vivenNative", "members": [{"_id": 0, "host": str(socket_path)}]}
    ]
    assert sum("hello" in command for command in issued) == 2
    construction = calls[0]["construct"]
    assert construction["options"]["directConnection"] is True
    assert construction["uri"].startswith("mongodb://%2F")
    assert calls[-1] == {"close": True}


def test_existing_exact_replica_is_read_only(replica_case):
    socket_path, run = replica_case
    result, calls = run({"config": config(str(socket_path))})
    assert result.returncode == 0, result.stderr
    assert all("replSetInitiate" not in command and "replSetReconfig" not in command for command in commands(calls))
    assert calls[-1] == {"close": True}


@pytest.mark.parametrize("code", [13, 23, 50, 76])
def test_other_config_read_failures_never_initialize(replica_case, code):
    _, run = replica_case
    result, calls = run({"readError": code})
    assert result.returncode != 0
    assert len(commands(calls)) == 1
    assert "private server detail" not in result.stderr
    assert calls[-1] == {"close": True}


@pytest.mark.parametrize("mutation", [
    "set", "foreign_socket", "extra_member", "member_id", "hidden", "arbiter", "votes",
    "priority", "delay", "tags", "horizons", "protocol", "journal", "config_server",
    "custom_write_concern", "election", "unknown_option",
])
def test_unexpected_existing_replica_is_rejected_without_reconfiguration(replica_case, mutation):
    socket_path, run = replica_case
    value = config(str(socket_path))
    member = value["members"][0]
    if mutation == "set": value["_id"] = "foreignSet"
    elif mutation == "foreign_socket": member["host"] = str(socket_path) + ".foreign"
    elif mutation == "extra_member": value["members"].append({"_id": 1, "host": "localhost:27017"})
    elif mutation == "member_id": member["_id"] = 1
    elif mutation == "hidden": member["hidden"] = True
    elif mutation == "arbiter": member["arbiterOnly"] = True
    elif mutation == "votes": member["votes"] = 0
    elif mutation == "priority": member["priority"] = 0
    elif mutation == "delay": member["secondaryDelaySecs"] = 5
    elif mutation == "tags": member["tags"] = {"region": "other"}
    elif mutation == "horizons": member["horizons"] = {"public": "localhost:27017"}
    elif mutation == "protocol": value["protocolVersion"] = 0
    elif mutation == "journal": value["writeConcernMajorityJournalDefault"] = False
    elif mutation == "config_server": value["configsvr"] = True
    elif mutation == "custom_write_concern": value["settings"]["getLastErrorDefaults"] = {"w": 0, "wtimeout": 0}
    elif mutation == "election": value["settings"]["electionTimeoutMillis"] = 90000
    elif mutation == "unknown_option": value["unexpected"] = True
    result, calls = run({"config": value})
    assert result.returncode != 0
    assert len(commands(calls)) == 1
    assert calls[-1] == {"close": True}


def test_writable_primary_timeout_closes_without_reconfiguration(replica_case):
    socket_path, run = replica_case
    result, calls = run({"config": config(str(socket_path)), "notPrimaryCount": 10000}, timeout="0.15")
    assert result.returncode != 0
    assert "writable primary" in result.stderr
    assert all("replSetInitiate" not in command and "replSetReconfig" not in command for command in commands(calls))
    assert calls[-1] == {"close": True}


def test_primary_from_wrong_set_is_rejected(replica_case):
    socket_path, run = replica_case
    result, calls = run({"config": config(str(socket_path)), "helloSet": "otherSet"})
    assert result.returncode != 0
    assert calls[-1] == {"close": True}


@pytest.mark.parametrize("unsafe", ["tcp", "relative", "regular_file", "permissions", "symlink"])
def test_unsafe_socket_never_constructs_driver(replica_case, unsafe):
    socket_path, run = replica_case
    selected = str(socket_path)
    if unsafe == "tcp": selected = "127.0.0.1:27017"
    elif unsafe == "relative": selected = "mongo.sock"
    elif unsafe == "regular_file":
        other = socket_path.with_suffix(".file")
        other.write_text("synthetic")
        other.chmod(0o600)
        selected = str(other)
    elif unsafe == "permissions": socket_path.chmod(0o660)
    elif unsafe == "symlink":
        other = socket_path.with_suffix(".link")
        other.symlink_to(socket_path)
        selected = str(other)
    result, calls = run({}, selected_socket=selected)
    assert result.returncode != 0
    assert calls == []
