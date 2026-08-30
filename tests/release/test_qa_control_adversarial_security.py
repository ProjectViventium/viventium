from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import resource
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "bin" / "viventium"
LOCAL_CONTROL = ROOT / "scripts" / "viventium" / "local_qa_runtime_control.py"
EMO_CONTROL = ROOT / "scripts" / "viventium" / "librechat_emo_qa_parent_control.py"
FIXTURE_PROCESS = ROOT / "scripts" / "viventium" / "librechat_emo_qa_fixture.js"
LAUNCHER = ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"

AMBIENT_QA_AUTHORITY_ENV = (
    "VIVENTIUM_APP_SUPPORT_DIR",
    "VIVENTIUM_RUNTIME_DIR",
    "VIVENTIUM_CONFIG_FILE",
    "VIVENTIUM_COMPONENTS_LOCK_FILE",
    "VIVENTIUM_CLI_LOCK_DIR",
    "VIVENTIUM_RUNTIME_PROFILE",
    "VIVENTIUM_PYTHON_BIN",
    "VIVENTIUM_DISABLE_ACTIVE_CHECKOUT_REEXEC",
    "VIVENTIUM_LOCAL_QA_CASE_ID",
    "VIVENTIUM_LOCAL_QA_CASE_TOKEN",
    "VIVENTIUM_LOCAL_QA_SESSION_REF",
    "VIVENTIUM_LOCAL_QA_MODE",
    "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST",
    "VIVENTIUM_TELEGRAM_LOCAL_QA_MODE",
    "VIVENTIUM_GLASSHIVE_LOCAL_QA_MODE",
    "VIVENTIUM_RELEASE_LOCAL_QA_MODE",
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_private(path: Path, content: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    os.chmod(path, 0o600)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def install_service_artifact(installed: Path) -> tuple[str, str]:
    relative = "viventium_v0_4/LibreChat/api/server/service.js"
    service = installed / relative
    service.parent.mkdir(parents=True, exist_ok=True)
    service.write_text("module.exports = Object.freeze({ candidate: 1 });\n", encoding="utf-8")
    manifest = installed / "scripts/viventium/parallel_work_runtime_artifact_manifest.json"
    manifest_payload = {
        "contractVersion": 1,
        "entries": [{"kind": "file", "path": relative, "trackedOnly": False}],
    }
    write_private(
        manifest,
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
    )
    acknowledgement = installed / "scripts/viventium/local_qa_service_ack.py"
    acknowledgement.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    acknowledgement.chmod(0o755)
    measured = [{"path": relative, "sha256": _sha256(service.read_bytes())}]
    running_digest = _sha256(
        json.dumps(measured, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return _sha256(manifest.read_bytes()), running_digest


def artifact_identity(
    *, manifest_digest: str, running_digest: str
) -> dict[str, object]:
    return {
        "contractVersion": 1,
        "readiness": {
            "factsSha256": "4" * 64,
            "storagePolicySha256": "5" * 64,
            "storageMeasurementSha256": "6" * 64,
        },
        "source": {
            "revision": "1" * 40,
            "clean": True,
            "worktreeHash": "2" * 64,
            "componentsLockSha256": "3" * 64,
        },
        "nestedComponents": [
            {
                "name": "LibreChat",
                "pin": "4" * 40,
                "revision": "4" * 40,
                "clean": True,
                "worktreeHash": "5" * 64,
            }
        ],
        "prebuiltHelper": {
            "sourceDeclaredSha256": "6" * 64,
            "sourceMeasuredSha256": "6" * 64,
            "binaryDeclaredSha256": "7" * 64,
            "binaryMeasuredSha256": "7" * 64,
            "binaryExecutable": True,
        },
        "installed": {
            "rootRevision": "8" * 40,
            "componentsLockSha256": "9" * 64,
            "nestedRevisionsHash": "a" * 64,
            "prebuiltSourceSha256": "b" * 64,
            "prebuiltBinarySha256": "c" * 64,
            "promptBundleSha256": "d" * 64,
            "runtimeEnvSha256": "e" * 64,
            "libreChatConfigSha256": "f" * 64,
            "frontendBuildSha256": "0" * 64,
            "apiBuildSha256": "1" * 64,
            "runningServiceSha256": running_digest,
            "runtimeServiceManifestSha256": manifest_digest,
            "runtimeOwnerExecutableSha256": "2" * 64,
            "ownerCommandContractSha256": "3" * 64,
        },
    }


def local_inputs(tmp_path: Path) -> dict[str, Path]:
    installed = tmp_path / "installed"
    installed.mkdir()
    manifest_digest, running_digest = install_service_artifact(installed)
    runtime = tmp_path / "runtime"
    identity = runtime / "parallel-work-artifact-identity.json"
    request = runtime / "parallel-work-local-qa-request.json"
    state = runtime / "local-qa" / "active.json"
    write_private(
        identity,
        json.dumps(
            artifact_identity(
                manifest_digest=manifest_digest,
                running_digest=running_digest,
            ),
            sort_keys=True,
        )
        + "\n",
    )
    write_private(
        request,
        '{"contractVersion":1,"mode":"local-qa","requested":true}\n',
    )
    return {
        "artifact_identity_path": identity,
        "installed_root": installed,
        "local_qa_request_path": request,
        "state_path": state,
    }


def activate(module, paths: dict[str, Path], *, now: datetime | None = None):
    return module.activate_session(
        **paths,
        case_id="EMO-UC-048",
        expires_in_seconds=900,
        now=now or datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc),
        token_bytes=lambda size: b"q" * size,
    )


def trusted_node() -> Path:
    for candidate in (
        Path("/opt/homebrew/opt/node@24/bin/node"),
        Path("/usr/local/opt/node@24/bin/node"),
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    pytest.skip("trusted Node 24 is not installed")


@pytest.mark.parametrize(
    "attack",
    (
        ("--app-support-dir", "cli"),
        ("--runtime-dir", "cli"),
        ("--app-support-dir", "equals"),
        ("--runtime-dir", "equals"),
        ("--app-support-dir", "duplicate"),
        ("--runtime-dir", "duplicate"),
        ("--config-file", "cli"),
        ("--config-file", "equals"),
        ("--config-file", "duplicate"),
        ("--lock-file", "cli"),
        ("--lock-file", "equals"),
        ("--lock-file", "duplicate"),
        *[(name, "env") for name in AMBIENT_QA_AUTHORITY_ENV],
    ),
)
def test_public_qa_cli_rejects_global_authority_overrides_without_echo(
    tmp_path: Path, attack: tuple[str, str]
) -> None:
    name, mode = attack
    private_value = str(tmp_path / ("private-" + hashlib.sha256(name.encode()).hexdigest()))
    env = os.environ.copy()
    for variable in AMBIENT_QA_AUTHORITY_ENV:
        env.pop(variable, None)
    command = [str(CLI)]
    if mode == "cli":
        command.extend([name, private_value])
    elif mode == "equals":
        command.append(f"{name}={private_value}")
    elif mode == "duplicate":
        command.extend([name, str(tmp_path / "first"), name, private_value])
    else:
        env[name] = private_value
    command.extend(["qa-control", "status"])

    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr == '{"error":"qa_authority_invalid"}\n'
    assert private_value not in completed.stderr


def test_public_qa_cli_rejects_even_canonical_ambient_authority() -> None:
    env = os.environ.copy()
    for variable in AMBIENT_QA_AUTHORITY_ENV:
        env.pop(variable, None)
    canonical = str(Path.home() / "Library/Application Support/Viventium")
    env["VIVENTIUM_APP_SUPPORT_DIR"] = canonical

    completed = subprocess.run(
        [str(CLI), "qa-control", "status"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr == '{"error":"qa_authority_invalid"}\n'
    assert canonical not in completed.stderr


@pytest.mark.parametrize(
    ("variable", "private_value"),
    [
        (variable, private_value)
        for variable in AMBIENT_QA_AUTHORITY_ENV
        for private_value in ("", "private-env-i-marker")
    ],
)
def test_public_qa_control_env_i_without_home_reaches_typed_authority_guard(
    variable: str, private_value: str
) -> None:
    clean_environment = (
        f"PATH={os.environ.get('PATH', '/usr/bin:/bin')}",
        f"{variable}={private_value}",
    )

    completed = subprocess.run(
        [
            "/usr/bin/env",
            "-i",
            *clean_environment,
            "/bin/bash",
            str(CLI),
            "qa-control",
            "status",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert all(not item.startswith("HOME=") for item in clean_environment)
    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr == '{"error":"qa_authority_invalid"}\n'
    assert str(ROOT) not in completed.stderr
    assert "unbound variable" not in completed.stderr
    if private_value:
        assert private_value not in completed.stderr


@pytest.mark.parametrize("command", ("qa-control", "qa-evidence", "release-check"))
def test_each_qa_entrypoint_rejects_ambient_or_global_authority(command: str) -> None:
    for arguments, injected in (
        ([command], {"VIVENTIUM_RUNTIME_PROFILE": "private-marker"}),
        (["--runtime-dir=/tmp/private-marker", command], {}),
    ):
        env = os.environ.copy()
        for variable in AMBIENT_QA_AUTHORITY_ENV:
            env.pop(variable, None)
        env.update(injected)
        completed = subprocess.run(
            [str(CLI), *arguments],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert completed.returncode == 2
        assert completed.stdout == ""
        assert completed.stderr == '{"error":"qa_authority_invalid"}\n'
        assert "private-marker" not in completed.stderr


def test_adversarial_release_test_has_emotional_cortex_qa_owner() -> None:
    owners = (ROOT / "qa/release-test-owners.yaml").read_text(encoding="utf-8")
    expected = (
        "  tests/release/test_qa_control_adversarial_security.py:\n"
        "    qa_owner: qa/emotional-cortex/cases.md"
    )
    assert expected in owners


@pytest.mark.parametrize(
    ("target", "mutation"),
    (
        ("artifact", "symlink"),
        ("artifact", "open_mode"),
        ("artifact", "duplicate"),
        ("artifact", "oversize"),
        ("artifact", "invalid_utf8"),
        ("request", "symlink"),
        ("request", "open_mode"),
        ("request", "oversize"),
        ("request", "invalid_utf8"),
    ),
)
def test_request_and_artifact_inputs_fail_closed(
    tmp_path: Path, target: str, mutation: str
) -> None:
    module = load(LOCAL_CONTROL, f"local_control_private_{target}_{mutation}")
    paths = local_inputs(tmp_path)
    path = (
        paths["artifact_identity_path"]
        if target == "artifact"
        else paths["local_qa_request_path"]
    )
    valid = path.read_bytes()
    if mutation == "symlink":
        backing = path.with_suffix(".backing")
        path.rename(backing)
        path.symlink_to(backing)
    elif mutation == "open_mode":
        os.chmod(path, 0o644)
    elif mutation == "duplicate":
        write_private(path, b'{"contractVersion":1,"contractVersion":1}\n')
    elif mutation == "oversize":
        write_private(path, b" " * (128 * 1024) + valid)
    else:
        write_private(path, b'{"contractVersion":"\xff"}')

    with pytest.raises(ValueError):
        activate(module, paths)


@pytest.mark.parametrize("target", ("artifact", "request", "session"))
def test_private_reads_reject_symlinked_parent_components(
    tmp_path: Path, target: str
) -> None:
    module = load(LOCAL_CONTROL, f"local_control_parent_symlink_{target}")
    real_parent = tmp_path / "real-private"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-private"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    private_file = real_parent / f"{target}.json"
    write_private(private_file, '{"contractVersion":1}\n')

    with pytest.raises(ValueError, match="invalid"):
        module._read_private_file(
            linked_parent / private_file.name,
            label=f"{target} state",
            max_bytes=4096,
        )


def test_session_state_uses_bounded_fd_read_not_path_read_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load(LOCAL_CONTROL, "local_control_fd_identity")
    paths = local_inputs(tmp_path)
    activate(module, paths)

    def forbidden_read_text(*_args, **_kwargs):
        raise AssertionError("Path.read_text must not read private QA state")

    monkeypatch.setattr(Path, "read_text", forbidden_read_text)
    assert module._read_state(paths["state_path"])["caseId"] == "EMO-UC-048"


@pytest.mark.parametrize("mutation", ("oversize", "invalid_utf8"))
def test_session_state_rejects_oversize_and_invalid_utf8(
    tmp_path: Path, mutation: str
) -> None:
    module = load(LOCAL_CONTROL, f"local_control_state_{mutation}")
    paths = local_inputs(tmp_path)
    activate(module, paths)
    state = paths["state_path"]
    if mutation == "oversize":
        write_private(state, b" " * (128 * 1024) + state.read_bytes())
    else:
        write_private(state, b'{"caseId":"\xff"}')

    with pytest.raises(ValueError, match="session state is invalid"):
        module._read_state(state)


def test_local_control_cli_returns_one_typed_error_for_io_and_unicode(
    tmp_path: Path,
) -> None:
    paths = local_inputs(tmp_path)
    private_value = str(tmp_path / "private-missing-artifact.json")
    command = [
        sys.executable,
        str(LOCAL_CONTROL),
        "activate",
        "--state",
        str(paths["state_path"]),
        "--installed-root",
        str(paths["installed_root"]),
        "--artifact-identity",
        private_value,
        "--local-qa-request",
        str(paths["local_qa_request_path"]),
        "--case-id",
        "EMO-UC-048",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr == '{"error": "operation_failed"}\n'
    assert private_value not in completed.stderr
    assert "Traceback" not in completed.stderr

    write_private(paths["state_path"], b'{"caseId":"\xff"}')
    status = subprocess.run(
        [
            sys.executable,
            str(LOCAL_CONTROL),
            "status",
            "--state",
            str(paths["state_path"]),
            "--installed-root",
            str(paths["installed_root"]),
            "--artifact-identity",
            str(paths["artifact_identity_path"]),
            "--local-qa-request",
            str(paths["local_qa_request_path"]),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert status.returncode == 2
    assert status.stdout == ""
    assert status.stderr == '{"error": "operation_failed"}\n'
    assert "Traceback" not in status.stderr


def test_session_timestamps_are_canonical_exact_milliseconds(tmp_path: Path) -> None:
    module = load(LOCAL_CONTROL, "local_control_milliseconds")
    paths = local_inputs(tmp_path)
    result = activate(
        module,
        paths,
        now=datetime(2026, 8, 23, 12, 0, 0, 123456, tzinfo=timezone.utc),
    )
    state = json.loads(paths["state_path"].read_text(encoding="utf-8"))

    assert state["startedAt"] == "2026-08-23T12:00:00.123+00:00"
    assert state["expiresAt"] == "2026-08-23T12:15:00.123+00:00"
    assert result["expiresAt"] == state["expiresAt"]


def test_session_binds_independently_measured_component_artifact_digest(
    tmp_path: Path,
) -> None:
    module = load(LOCAL_CONTROL, "local_control_component_digest")
    paths = local_inputs(tmp_path)
    identity = json.loads(paths["artifact_identity_path"].read_text(encoding="utf-8"))
    running_digest = identity["installed"]["runningServiceSha256"]

    activate(module, paths)
    state = json.loads(paths["state_path"].read_text(encoding="utf-8"))
    exports = module.emit_shell_exports(
        **paths,
        now=datetime(2026, 8, 23, 12, 0, 1, tzinfo=timezone.utc),
    )

    assert state["componentArtifactDigest"] == f"sha256:{running_digest}"
    assert (
        f"VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST=sha256:{running_digest}"
        in exports
    )


def test_session_rejects_self_attested_or_stale_component_artifact_digest(
    tmp_path: Path,
) -> None:
    module = load(LOCAL_CONTROL, "local_control_component_digest_drift")
    paths = local_inputs(tmp_path)
    identity = json.loads(paths["artifact_identity_path"].read_text(encoding="utf-8"))
    identity["installed"]["runningServiceSha256"] = "f" * 64
    write_private(paths["artifact_identity_path"], json.dumps(identity) + "\n")

    with pytest.raises(ValueError, match="artifact identity"):
        activate(module, paths)


def test_launcher_clears_ambient_component_digest_then_emits_canonical_value() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")
    qa_block = source.split("# Installed local-QA fault controls", 1)[1].split(
        "# === VIVENTIUM END ===", 1
    )[0]

    assert "unset VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST" in qa_block
    assert "emit-shell" in qa_block
    assert "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST" in source


def test_node_resolution_ignores_attacker_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load(EMO_CONTROL, "emo_control_trusted_node")
    trusted = tmp_path / "trusted" / "node"
    attacker = tmp_path / "attacker" / "node"
    for path, label in ((trusted, "trusted"), (attacker, "attacker")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"#!/bin/sh\necho {label}\n", encoding="utf-8")
        os.chmod(path, 0o755)
    monkeypatch.setattr(module, "TRUSTED_NODE_CANDIDATES", (trusted,), raising=False)
    monkeypatch.setenv("PATH", str(attacker.parent))

    assert Path(module._node_binary()) == trusted.resolve()


def test_node_preload_and_loader_environment_cannot_intercept_child(
    tmp_path: Path,
) -> None:
    module = load(EMO_CONTROL, "emo_control_node_env")
    marker = tmp_path / "preload-ran"
    preload = tmp_path / "preload.js"
    preload.write_text(
        f"require('fs').writeFileSync({json.dumps(str(marker))}, 'hit');\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        {
            "NODE_OPTIONS": f"--require={preload}",
            "NODE_PATH": str(tmp_path / "modules"),
            "NODE_EXTRA_CA_CERTS": str(tmp_path / "ca.pem"),
            "DYLD_INSERT_LIBRARIES": str(tmp_path / "inject.dylib"),
            "LD_PRELOAD": str(tmp_path / "inject.so"),
        }
    )
    code = (
        "let s=''; process.stdin.on('data',d=>s+=d); "
        "process.stdin.on('end',()=>process.stdout.write(JSON.stringify({ok:JSON.parse(s).ok})));"
    )

    result = module._run_private_json(
        argv=[str(trusted_node()), "-e", code],
        cwd=tmp_path,
        env=env,
        document={"ok": True},
        private_values=[],
    )

    assert result == {"ok": True}
    assert not marker.exists()


def test_allowed_component_env_is_still_private_and_cannot_be_echoed(
    tmp_path: Path,
) -> None:
    module = load(EMO_CONTROL, "emo_control_component_env_echo")
    component_digest = "sha256:" + "3" * 64
    with pytest.raises(ValueError, match="operation_failed"):
        module._run_private_json(
            argv=[
                sys.executable,
                "-c",
                "import os; print(os.environ['VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST'])",
            ],
            cwd=tmp_path,
            env={"VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST": component_digest},
            document={"schemaVersion": 1},
            private_values=[component_digest],
        )


@pytest.mark.parametrize("attack", ("oversize", "invalid_utf8"))
def test_child_json_output_is_bounded_and_strict_utf8(
    tmp_path: Path, attack: str
) -> None:
    module = load(EMO_CONTROL, f"emo_control_child_{attack}")
    if attack == "oversize":
        probe = "import json; print(json.dumps('x' * (128 * 1024)))"
    else:
        probe = "import os; os.write(1, b'\\xff')"

    with pytest.raises(ValueError, match="operation_failed"):
        module._run_private_json(
            argv=[sys.executable, "-c", probe],
            cwd=tmp_path,
            env=os.environ.copy(),
            document={"schemaVersion": 1},
            private_values=[],
        )


def test_child_capture_kills_a_64_mib_producer_before_completion_with_bounded_rss(
    tmp_path: Path,
) -> None:
    module = load(EMO_CONTROL, "emo_control_child_64_mib")
    marker = tmp_path / "producer-finished"
    probe = (
        "import os, pathlib; chunk=b'x'*65536; "
        "[os.write(1, chunk) for _ in range(1024)]; "
        f"pathlib.Path({str(marker)!r}).write_text('finished')"
    )
    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    started = time.monotonic()

    with pytest.raises(ValueError, match="operation_failed"):
        module._run_private_json(
            argv=[sys.executable, "-c", probe],
            cwd=tmp_path,
            env=os.environ.copy(),
            document={"schemaVersion": 1},
            private_values=[],
        )

    elapsed = time.monotonic() - started
    after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_unit = 1 if sys.platform == "darwin" else 1024
    assert not marker.exists()
    assert elapsed < 10
    assert (after - before) * rss_unit < 16 * 1024 * 1024


def fixture_document() -> dict[str, object]:
    owner = "ab" * 12
    namespace = "cd" * 16
    conversation = "emo_uc_048_conversation_" + namespace
    parent = "emo_uc_048_parent_" + namespace

    def digest(label: str, value: str) -> str:
        return "sha256:" + hashlib.sha256(f"{label}\0{value}".encode()).hexdigest()

    return {
        "fixture": {
            "componentArtifactDigest": "sha256:" + "3" * 64,
            "caseTokenHash": "sha256:" + "1" * 64,
            "conversationId": conversation,
            "conversationScopeHash": digest("conversation", conversation),
            "email": f"emo-uc-048-{namespace}@local-qa.invalid",
            "expiresAt": "2099-08-23T12:15:00.123+00:00",
            "ownerId": owner,
            "ownerScopeHash": digest("owner", owner),
            "parentMessageId": parent,
            "parentScopeHash": digest("parent", parent),
        },
        "fixtureRef": "emo048_fixture_" + "2" * 24,
        "schemaVersion": 1,
    }


def fake_librechat_root(tmp_path: Path, marker: Path) -> Path:
    root = tmp_path / "fake-librechat"
    write_private(root / "package.json", '{"name":"fixture-probe"}\n')
    mongoose = root / "node_modules" / "mongoose"
    schemas = root / "node_modules" / "@librechat" / "data-schemas"
    write_private(mongoose / "package.json", '{"main":"index.js"}\n')
    write_private(
        mongoose / "index.js",
        "const fs=require('fs'); module.exports={"
        f"connect:async()=>{{fs.writeFileSync({json.dumps(str(marker))},'hit');throw new Error('stop');}},"
        "disconnect:async()=>{}};\n",
    )
    write_private(schemas / "package.json", '{"main":"index.js"}\n')
    write_private(schemas / "index.js", "exports.createModels=()=>({});\n")
    return root


def fake_duplicate_rows_librechat_root(tmp_path: Path) -> Path:
    root = tmp_path / "fake-librechat-duplicates"
    document = fixture_document()
    fixture = document["fixture"]
    owner = {
        "_id": fixture["ownerId"],
        "email": fixture["email"],
        "provider": "viventium_local_qa_fixture",
        "idOnTheSource": f"viventium:local-qa:emo_uc_048:{fixture['caseTokenHash']}",
        "expiresAt": fixture["expiresAt"],
    }
    conversation = {
        "_id": "conversation-row",
        "user": fixture["ownerId"],
        "conversationId": fixture["conversationId"],
        "tags": ["viventium:local-qa:emo_uc_048", fixture["caseTokenHash"]],
        "expiredAt": fixture["expiresAt"],
    }
    message = {
        "_id": "message-row",
        "user": fixture["ownerId"],
        "conversationId": fixture["conversationId"],
        "messageId": fixture["parentMessageId"],
        "isCreatedByUser": False,
        "expiredAt": fixture["expiresAt"],
        "metadata": {
            "viventium": {
                "localQaFixture": {
                    "schemaVersion": 1,
                    "caseId": "emo_uc_048",
                    "componentArtifactDigest": fixture["componentArtifactDigest"],
                    "caseTokenHash": fixture["caseTokenHash"],
                    "ownerScopeHash": fixture["ownerScopeHash"],
                    "conversationScopeHash": fixture["conversationScopeHash"],
                    "parentScopeHash": fixture["parentScopeHash"],
                    "expiresAt": fixture["expiresAt"],
                }
            }
        },
    }
    write_private(root / "package.json", '{"name":"fixture-duplicate-probe"}\n')
    mongoose = root / "node_modules/mongoose"
    schemas = root / "node_modules/@librechat/data-schemas"
    write_private(mongoose / "package.json", '{"main":"index.js"}\n')
    write_private(
        mongoose / "index.js",
        "module.exports={connect:async()=>{},disconnect:async()=>{}};\n",
    )
    write_private(schemas / "package.json", '{"main":"index.js"}\n')
    write_private(
        schemas / "index.js",
        "const chain=(value)=>({select(){return this},limit(){return this},lean:async()=>value});\n"
        f"const owner={json.dumps(owner)};\n"
        f"const conversation={json.dumps(conversation)};\n"
        f"const message={json.dumps(message)};\n"
        "exports.createModels=()=>({"
        "User:{findById:()=>chain(owner),findOne:()=>chain(owner),find:()=>chain([owner,owner])},"
        "Conversation:{findOne:()=>chain(conversation),find:()=>chain([conversation,conversation])},"
        "Message:{findOne:()=>chain(message),find:()=>chain([message,message])},"
        "LocalQaCortexFaultControl:{countDocuments:async()=>0}"
        "});\n",
    )
    return root


def run_fixture_process(
    tmp_path: Path,
    raw: bytes,
    arguments: list[str],
    *,
    component_digest: str | None = "sha256:" + "3" * 64,
) -> tuple[subprocess.CompletedProcess[bytes], bool]:
    marker = tmp_path / "models-loaded"
    root = fake_librechat_root(tmp_path, marker)
    scope = tmp_path / "scope.json"
    write_private(scope, raw)
    descriptor = os.open(scope, os.O_RDONLY)
    try:
        rendered = [str(descriptor) if value == "{fd}" else value for value in arguments]
        env = {
            "MONGO_URI": "mongodb://127.0.0.1:27117/qa",
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "VIVENTIUM_LIBRECHAT_ROOT": str(root),
        }
        if component_digest is not None:
            env["VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST"] = component_digest
        completed = subprocess.run(
            [str(trusted_node()), str(FIXTURE_PROCESS), *rendered],
            cwd=ROOT,
            env=env,
            pass_fds=(descriptor,),
            capture_output=True,
            timeout=15,
            check=False,
        )
    finally:
        os.close(descriptor)
    return completed, marker.exists()


def test_real_fixture_process_rejects_json_and_argument_attacks(tmp_path: Path) -> None:
    valid = json.dumps(fixture_document(), separators=(",", ":")).encode()
    duplicate_json = valid.replace(b'"schemaVersion":1', b'"schemaVersion":1,"schemaVersion":1')
    invalid_utf8 = valid.replace(
        b'"schemaVersion":1', b'"schemaVersion":"\xff","schemaVersion":1'
    )
    attacks = {
        "duplicate_json": (
            duplicate_json,
            ["provision", "--json", "--scope-fd", "{fd}"],
        ),
        "duplicate_json_flag": (
            valid,
            ["provision", "--json", "--json", "--scope-fd", "{fd}"],
        ),
        "duplicate_scope_fd": (
            valid,
            ["provision", "--scope-fd", "{fd}", "--scope-fd", "{fd}"],
        ),
        "unknown_argument": (
            valid,
            ["provision", "--unknown", "--scope-fd", "{fd}"],
        ),
        "invalid_utf8": (
            invalid_utf8,
            ["provision", "--json", "--scope-fd", "{fd}"],
        ),
        "oversize": (
            valid + b" " * (9 * 1024),
            ["provision", "--json", "--scope-fd", "{fd}"],
        ),
        "expired_scope": (
            valid.replace(
                b'2099-08-23T12:15:00.123+00:00',
                b'2000-08-23T12:15:00.123+00:00',
            ),
            ["provision", "--json", "--scope-fd", "{fd}"],
        ),
    }

    for name, (raw, arguments) in attacks.items():
        case_root = tmp_path / name
        case_root.mkdir()
        completed, reached_models = run_fixture_process(case_root, raw, arguments)
        assert completed.returncode == 1, name
        assert completed.stdout == b"", name
        assert completed.stderr == b'{"ok":false,"error":"fixture_operation_failed"}\n', name
        assert reached_models is False, name


def test_real_fixture_process_attack_harness_reaches_models_for_valid_input(
    tmp_path: Path,
) -> None:
    valid = json.dumps(fixture_document(), separators=(",", ":")).encode()
    completed, reached_models = run_fixture_process(
        tmp_path,
        valid,
        ["provision", "--json", "--scope-fd", "{fd}"],
    )

    assert completed.returncode == 1
    assert completed.stderr == b'{"ok":false,"error":"fixture_operation_failed"}\n'
    assert reached_models is True


def test_real_fixture_process_allows_expired_scope_only_for_exact_destroy(
    tmp_path: Path,
) -> None:
    expired = json.dumps(fixture_document(), separators=(",", ":")).encode().replace(
        b"2099-08-23T12:15:00.123+00:00",
        b"2000-08-23T12:15:00.123+00:00",
    )
    completed, reached_models = run_fixture_process(
        tmp_path,
        expired,
        ["destroy", "--json", "--scope-fd", "{fd}"],
    )

    assert completed.returncode == 1
    assert completed.stderr == b'{"ok":false,"error":"fixture_operation_failed"}\n'
    assert reached_models is True


@pytest.mark.parametrize(
    "component_digest",
    (None, "sha256:" + "4" * 64, "ambient-not-a-digest"),
)
def test_real_fixture_process_rejects_missing_or_wrong_component_digest_before_models(
    tmp_path: Path, component_digest: str | None
) -> None:
    valid = json.dumps(fixture_document(), separators=(",", ":")).encode()
    completed, reached_models = run_fixture_process(
        tmp_path,
        valid,
        ["inspect", "--json", "--scope-fd", "{fd}"],
        component_digest=component_digest,
    )

    assert completed.returncode == 1
    assert completed.stdout == b""
    assert completed.stderr == b'{"ok":false,"error":"fixture_operation_failed"}\n'
    assert reached_models is False


def test_real_fixture_process_rejects_duplicate_fixture_rows(tmp_path: Path) -> None:
    root = fake_duplicate_rows_librechat_root(tmp_path)
    scope = tmp_path / "scope.json"
    write_private(scope, json.dumps(fixture_document(), separators=(",", ":")))
    descriptor = os.open(scope, os.O_RDONLY)
    try:
        completed = subprocess.run(
            [
                str(trusted_node()),
                str(FIXTURE_PROCESS),
                "inspect",
                "--json",
                "--scope-fd",
                str(descriptor),
            ],
            cwd=ROOT,
            env={
                "MONGO_URI": "mongodb://127.0.0.1:27117/qa",
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                "VIVENTIUM_LIBRECHAT_ROOT": str(root),
                "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST": (
                    "sha256:" + "3" * 64
                ),
            },
            pass_fds=(descriptor,),
            capture_output=True,
            timeout=15,
            check=False,
        )
    finally:
        os.close(descriptor)

    assert completed.returncode == 1
    assert completed.stdout == b""
    assert completed.stderr == b'{"ok":false,"error":"fixture_operation_failed"}\n'
