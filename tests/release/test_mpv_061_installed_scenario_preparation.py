import json
import os
import re
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "qa"
    / "modern-playground-voice"
    / "scripts"
    / "prepare_mpv_061_installed_scenario.cjs"
)
RUNNER = SCRIPT.with_name("run_mpv_061_installed_journey.cjs")


def _node(
    source: str, *arguments: object, timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    assert arguments
    return subprocess.run(
        [
            "node",
            "-e",
            source,
            str(arguments[0]),
            *[json.dumps(value) for value in arguments[1:]],
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _module_call(expression: str, *arguments: object, timeout: int = 30) -> object:
    completed = _node(
        "const moduleUnderTest=require(process.argv[1]);"
        "const args=process.argv.slice(2).map(JSON.parse);"
        f"Promise.resolve({expression}).then((value)=>process.stdout.write(JSON.stringify(value)))"
        ".catch((error)=>{process.stderr.write(String(error.code||error.message));process.exit(2);});",
        str(SCRIPT),
        *arguments,
        timeout=timeout,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_preparer_exists_and_is_public_safe() -> None:
    assert SCRIPT.is_file()
    source = SCRIPT.read_text(encoding="utf-8")
    personal_home_path = re.compile(
        r'''(?<![A-Za-z0-9_])/(?:Users|home)/[^/\s"']+(?:/|[\s"'])'''
    )
    personal_identity_assignment = re.compile(
        r'''(?im)\b(?:author|maintainer|created_?by|owner_?(?:name|email|username))\b'''
        r'''\s*[:=]\s*[`"'][^`"']+[`"']'''
    )
    assert personal_home_path.search(source) is None
    assert personal_identity_assignment.search(source) is None
    assert "API_KEY" not in source
    assert "fetchImpl(" in source
    assert "assertLoopbackOrigin" in source


def test_public_safety_guard_uses_structural_checks_not_identity_literals() -> None:
    test_source = Path(__file__).read_text(encoding="utf-8")
    bare_identity_assertion = re.compile(
        r'''assert\s+["'][A-Za-z][A-Za-z-]{2,}["']\s+not\s+in\s+source\.lower\(\)'''
    )
    assert bare_identity_assertion.search(test_source) is None


def test_public_scenario_has_exact_eight_turn_contract() -> None:
    turns = _module_call("moduleUnderTest.SCENARIO_TURNS")
    assert [
        (item["kind"], item["mode"], item["directlyAddressed"]) for item in turns
    ] == [
        ("authorizedCallLaunch", "call", True),
        ("trustedWingLaunch", "wing", True),
        ("quickConversation", "call", True),
        ("authorizedCallControl", "call", True),
        ("trustedWingControl", "wing", True),
        ("passiveWingDenial", "wing", False),
        ("listenOnlyDenial", "listen_only", True),
        ("unverifiedWingDenial", "wing", True),
    ]
    assert "mission alpha" in turns[0]["speech"].lower()
    assert "mission bravo" in turns[0]["speech"].lower()
    assert "mission alpha only" in turns[3]["speech"].lower()
    assert "blue folder" in turns[5]["speech"].lower()
    assert "third synthetic worker" in turns[6]["speech"].lower()
    assert all(item["expectedTranscript"] in item["speech"] for item in turns)


def test_exact_model_and_main_agent_are_derived_and_cross_checked() -> None:
    resolved = _module_call(
        "moduleUnderTest.resolveConfiguredIdentity(...args)",
        {
            "agents": {"default_main_agent_id": "agent_main"},
        },
        {
            "mainAgent": {
                "id": "agent_main",
                "name": "Viventium",
                "voice_llm_provider": "xai",
                "voice_llm_model": "grok-4.5",
                "voice_fallback_llm_provider": "openAI",
                "voice_fallback_llm_model": "gpt-5.6-terra",
            }
        },
        {"VIVENTIUM_MAIN_AGENT_ID": "agent_main"},
    )
    assert resolved == {
        "assistant": {
            "provider": "xai",
            "model": "grok-4.5",
            "fallback": {"provider": "openAI", "model": "gpt-5.6-terra"},
        },
        "agent": {"id": "agent_main", "name": "Viventium"},
    }

    completed = _node(
        "const p=require(process.argv[1]);"
        "try{p.resolveConfiguredIdentity({agents:{default_main_agent_id:'agent_a'}},"
        "{mainAgent:{id:'agent_b',name:'Viventium',voice_llm_provider:'xai',voice_llm_model:'grok-4.5'}},"
        "{VIVENTIUM_MAIN_AGENT_ID:'agent_a'});process.exit(1)}"
        "catch(error){process.stdout.write(error.code)}",
        str(SCRIPT),
    )
    assert completed.returncode == 0
    assert completed.stdout == "installed_agent_identity_mismatch"


def test_strict_candidate_rejects_dirty_or_unpinned_identity() -> None:
    valid = {
        "candidateDigest": "a" * 64,
        "artifactDigest": "b" * 64,
        "checks": [
            {"id": "SOURCE-IDENTITY", "status": "PASS"},
            {"id": "NESTED-PINS", "status": "PASS"},
            {"id": "PREBUILT-IDENTITY", "status": "PASS"},
            {"id": "INSTALLED-ARTIFACT", "status": "PASS"},
        ],
        "measuredIdentity": {
            "source": {"clean": True},
            "nestedComponents": [
                {
                    "name": "LibreChat",
                    "clean": True,
                    "pin": "1" * 40,
                    "revision": "1" * 40,
                }
            ],
        },
        "runtimeBinding": {
            "active": True,
            "ownerRootMatches": True,
            "runtimeRootMatches": True,
        },
    }
    accepted = _module_call("moduleUnderTest.assertStrictCandidate(args[0])", valid)
    assert accepted["candidateMode"] == "strict"
    assert accepted["releaseCandidateVerified"] is True

    dirty = json.loads(json.dumps(valid))
    dirty["measuredIdentity"]["source"]["clean"] = False
    completed = _node(
        "const p=require(process.argv[1]);const value=JSON.parse(process.argv[2]);"
        "try{p.assertStrictCandidate(value);process.exit(1)}"
        "catch(error){process.stdout.write(error.code)}",
        str(SCRIPT),
        dirty,
    )
    assert completed.returncode == 0
    assert completed.stdout == "strict_candidate_identity_invalid"


def test_diagnostic_mode_requires_existing_mpv_contract_and_never_claims_ready() -> (
    None
):
    result = _module_call(
        "moduleUnderTest.resolveDiagnosticPolicy(args[0],args[1])",
        {"VIVENTIUM_QA_ALLOW_DIAGNOSTIC_CANDIDATE": "1"},
        {
            "supported": True,
            "status": "PRE_GATE_COMPLETE",
            "releaseReady": False,
            "receiptEligible": False,
            "releaseLabel": "PRE-GATE / NOT READY",
        },
    )
    assert result == {
        "candidateMode": "diagnostic",
        "status": "PRE_GATE_COMPLETE",
        "releaseReady": False,
        "receiptEligible": False,
        "releaseLabel": "PRE-GATE / NOT READY",
    }

    completed = _node(
        "const p=require(process.argv[1]);"
        "try{p.resolveDiagnosticPolicy({VIVENTIUM_QA_ALLOW_DIAGNOSTIC_CANDIDATE:'1'},"
        "{supported:false});process.exit(1)}catch(error){process.stdout.write(error.code)}",
        str(SCRIPT),
    )
    assert completed.returncode == 0
    assert completed.stdout == "diagnostic_candidate_unsupported_by_mpv061_runner"


def test_runner_exports_truthful_diagnostic_and_observer_contracts() -> None:
    completed = _node(
        "const r=require(process.argv[1]);"
        "process.stdout.write(JSON.stringify({diagnostic:r.DIAGNOSTIC_CANDIDATE_CONTRACT,"
        "observer:r.SCENARIO_OBSERVER_CONTRACT}))",
        str(RUNNER),
    )
    assert completed.returncode == 0, completed.stderr
    contracts = json.loads(completed.stdout)
    assert contracts["diagnostic"] == {
        "version": 1,
        "supported": True,
        "status": "PRE_GATE_COMPLETE",
        "releaseReady": False,
        "releaseCandidateVerified": False,
        "acceptanceEligible": False,
        "receiptEligible": False,
        "releaseLabel": "PRE-GATE / NOT READY",
    }
    observer = contracts["observer"]
    assert observer["runtimeIdentityFields"] == ["ownerBindingSha256"]
    assert observer["effectStages"] == {
        "launch": ["launch.prepared", "launch.accepted", "launch.failed"],
        "control": ["action.accepted", "control.completed"],
        "tool": ["tool.completed"],
        "controller": ["controller.completed"],
        "cortex": ["cortex.completed"],
        "liveMemory": ["live_memory.completed"],
        "recall": ["recall.completed"],
        "titleModel": ["title_model.completed"],
        "response": ["response.completed"],
        "tts": ["tts.completed"],
        "audio": ["audio.completed"],
    }
    assert observer["fallback"] == {
        "available": True,
        "stages": [
            "attempt.history.complete",
            "provider.request.forwarded",
            "provider.attempt.completed",
            "provider.fallback.completed",
        ],
        "controlledTriggerAvailable": True,
        "defaultRequirement": "required",
    }
    assert observer["workerCompletionDelivery"] == {
        "available": True,
        "producerScope": "librechat.voice_worker_completion_delivery",
        "stages": ["response.completed", "tts.completed", "audio.completed"],
        "blocker": None,
    }
    assert observer["unavailableEffectPlanes"] == []
    named = [stage for stages in observer["effectStages"].values() for stage in stages]
    assert named == [
        "launch.prepared",
        "launch.accepted",
        "launch.failed",
        "action.accepted",
        "control.completed",
        "tool.completed",
        "controller.completed",
        "cortex.completed",
        "live_memory.completed",
        "recall.completed",
        "title_model.completed",
        "response.completed",
        "tts.completed",
        "audio.completed",
    ]


def test_preparer_blocks_when_worker_completion_delivery_has_no_producer(
    tmp_path: Path,
) -> None:
    root = tmp_path / "not-created"
    completed = _node(
        "const p=require(process.argv[1]);"
        "const args=process.argv.slice(2).map(JSON.parse);const base=require(args[0]);"
        "const r={...base,SCENARIO_OBSERVER_CONTRACT:{...base.SCENARIO_OBSERVER_CONTRACT,"
        "workerCompletionDelivery:{available:false,producerScope:null,stages:[],"
        "blocker:'worker_completion_delivery_trace_unavailable'}}};"
        "try{p.installedObserverContract(r,args[1]);process.exit(1)}"
        "catch(error){process.stdout.write(error.code)}",
        str(SCRIPT),
        str(RUNNER),
        str(root / "owner.json"),
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "worker_completion_delivery_trace_unavailable"
    assert not root.exists()


def test_preparer_preserves_safe_runner_candidate_blockers() -> None:
    completed = _node(
        "const p=require(process.argv[1]);"
        "const runner={measureInstalledCandidate(){const error=new Error('private');"
        "error.code='strict_candidate_identity_invalid';throw error}};"
        "try{p.measureRunnerCandidate(runner,{candidateMode:'strict'});process.exit(1)}"
        "catch(error){process.stdout.write(error.code)}",
        str(SCRIPT),
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "strict_candidate_identity_invalid"


def test_local_say_and_ffmpeg_create_two_distinct_private_audible_wavs(
    tmp_path: Path,
) -> None:
    root = tmp_path.resolve()
    root.chmod(0o700)
    result = _module_call(
        "moduleUnderTest.generateSpeechFixtures(args[0],moduleUnderTest.SCENARIO_TURNS)",
        str(root),
        timeout=90,
    )
    initial = Path(result["initial"])
    reconnect = Path(result["reconnect"])
    assert initial.is_file() and reconnect.is_file()
    assert stat.S_IMODE(initial.stat().st_mode) == 0o600
    assert stat.S_IMODE(reconnect.stat().st_mode) == 0o600
    assert result["initialSha256"] != result["reconnectSha256"]
    assert len(result["startAfterMs"]) == 8
    assert result["startAfterMs"] == sorted(result["startAfterMs"])
    assert min(result["startAfterMs"]) >= 5_000
    checked = _module_call(
        "({initial:!!moduleUnderTest.inspectAudibleWav(args[0]),"
        "reconnect:!!moduleUnderTest.inspectAudibleWav(args[1])})",
        str(initial),
        str(reconnect),
    )
    assert checked == {"initial": True, "reconnect": True}


def test_scenario_builder_binds_private_outputs_exact_route_and_restart(
    tmp_path: Path,
) -> None:
    root = tmp_path.resolve()
    root.chmod(0o700)
    for name, content in {
        "initial.wav": b"initial",
        "reconnect.wav": b"reconnect",
        "attachment-alpha.json": b"alpha",
        "attachment-bravo.md": b"bravo",
        "identity.json": b"{}",
        "runtime-handoff.json": b'{"schema":"viventium.voice.mpv-061.runtime-handoff.v1","MONGO_URI":"mongodb://127.0.0.1:27017/fixture"}',
    }.items():
        target = root / name
        target.write_bytes(content)
        target.chmod(0o600)
    scenario = _module_call(
        "moduleUnderTest.buildScenario(args[0])",
        {
            "evidenceRoot": str(root),
            "artifactIdentity": str(root / "identity.json"),
            "identity": {
                "assistant": {
                    "provider": "xai",
                    "model": "grok-4.5",
                    "fallback": {"provider": "openAI", "model": "gpt-5.6-terra"},
                },
                "agent": {"id": "agent_main", "name": "Viventium"},
            },
            "runtime": {
                "playgroundUrl": "http://127.0.0.1:3300",
                "coreUrl": "http://127.0.0.1:3190",
                "mongoUriFile": str(root / "runtime-handoff.json"),
                "voice": {
                    "stt": {"provider": "pywhispercpp", "variant": "large-v3-turbo"},
                    "tts": {"provider": "xai", "variant": "Sal"},
                },
            },
            "speech": {
                "initial": str(root / "initial.wav"),
                "reconnect": str(root / "reconnect.wav"),
                "startAfterMs": [
                    8000,
                    42000,
                    76000,
                    110000,
                    144000,
                    178000,
                    212000,
                    246000,
                ],
                "armAfterMs": [
                    7000,
                    41000,
                    75000,
                    109000,
                    143000,
                    177000,
                    211000,
                    245000,
                ],
            },
            "attachments": [
                {
                    "worker": "A",
                    "path": str(root / "attachment-alpha.json"),
                    "artifactLabel": "mpv-061-worker-alpha-result.txt",
                },
                {
                    "worker": "B",
                    "path": str(root / "attachment-bravo.md"),
                    "artifactLabel": "mpv-061-worker-bravo-result.txt",
                },
            ],
            "restart": {
                "executable": str(ROOT / "bin" / "viventium"),
                "arguments": [
                    "dev-runtime",
                    "activate-current",
                    "--validate",
                    "--restart",
                    "--allow-protected-folder",
                    "--allow-dirty-local-testing",
                ],
            },
            "observation": {
                "runtimeIdentityFile": str(root / "runtime-identity.json"),
                "fallbackStage": "provider.fallback.completed",
                "fallbackStages": [
                    "attempt.history.complete",
                    "provider.request.forwarded",
                    "provider.attempt.completed",
                    "provider.fallback.completed",
                ],
                "effectStages": {
                    key: [f"{key}.observed"]
                    for key in [
                        "launch",
                        "control",
                        "tool",
                        "controller",
                        "cortex",
                        "liveMemory",
                        "recall",
                        "titleModel",
                        "response",
                        "tts",
                        "audio",
                    ]
                },
            },
        },
    )
    assert scenario["schema"] == "viventium.voice.mpv-061.installed-journey-scenario.v1"
    assert scenario["runtime"]["assistant"] == {
        "provider": "xai",
        "model": "grok-4.5",
        "fallback": {"provider": "openAI", "model": "gpt-5.6-terra"},
    }
    assert scenario["runtime"]["agent"]["id"] == "agent_main"
    assert scenario["browser"] == {"headed": True, "headless": False}
    assert scenario["surfaces"]["reconnectButton"] == "Start voice call"
    assert [item["kind"] for item in scenario["turns"]] == [
        "authorizedCallLaunch",
        "trustedWingLaunch",
        "quickConversation",
        "authorizedCallControl",
        "trustedWingControl",
        "passiveWingDenial",
        "listenOnlyDenial",
        "unverifiedWingDenial",
    ]


def test_help_is_side_effect_free_and_current_diagnostic_is_fail_closed(
    tmp_path: Path,
) -> None:
    root = tmp_path / "never-created"
    help_result = subprocess.run(
        ["node", str(SCRIPT), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert help_result.returncode == 0
    assert "--evidence-root" in help_result.stdout
    assert not root.exists()

    environment = os.environ.copy()
    environment["VIVENTIUM_QA_ALLOW_DIAGNOSTIC_CANDIDATE"] = "1"
    diagnostic = subprocess.run(
        [
            "node",
            str(SCRIPT),
            "--evidence-root",
            str(root),
            "--candidate-mode",
            "diagnostic",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    assert diagnostic.returncode == 2
    payload = json.loads(diagnostic.stdout)
    assert payload["caseId"] == "MPV-061"
    assert payload["status"] == "BLOCKED"
    assert payload["blocker"] in {
        "diagnostic_active_runtime_identity_unproven",
        "installed_runtime_metadata_conflict",
        "installed_runtime_owner_mismatch",
    }
    assert payload["releaseLabel"] == "PRE-GATE / NOT READY"
    assert payload["receiptEligible"] is False
    assert not root.exists()
