from __future__ import annotations

import errno
import json
import importlib.util
import hashlib
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
ASSEMBLER = REPO_ROOT / "scripts" / "viventium" / "assemble_native_payload.py"
NATIVE_RUNTIME = REPO_ROOT / "scripts" / "viventium" / "native_runtime.py"
NATIVE_ENTRYPOINT = REPO_ROOT / "scripts" / "viventium" / "native_entrypoint.sh"
CANDIDATE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "native-payload-candidate.yml"
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "native-payload-release.yml"
NATIVE_INSTALLER = REPO_ROOT / "scripts" / "viventium" / "install_native_payload.py"
NATIVE_PROXY = REPO_ROOT / "scripts" / "viventium" / "native_runtime_proxy.js"
NATIVE_FIRST_ADMIN_RECOVERY = (
    REPO_ROOT / "scripts" / "viventium" / "native_first_admin_recovery.js"
)
NATIVE_VERIFY_AGENT = REPO_ROOT / "scripts" / "viventium" / "native_verify_agent.js"
GENERATE_COMPLIANCE = REPO_ROOT / "scripts" / "viventium" / "generate_native_compliance.py"
VERIFY_COMPLIANCE = REPO_ROOT / "scripts" / "viventium" / "verify_native_compliance.py"
COMPONENT_MANIFEST = (
    REPO_ROOT / "scripts" / "viventium" / "verify_native_component_manifest.py"
)
BOOTSTRAP_SWIFT = (
    REPO_ROOT
    / "apps"
    / "macos"
    / "ViventiumBootstrap"
    / "Sources"
    / "ViventiumBootstrap"
    / "main.swift"
)
HELPER_SWIFT = REPO_ROOT / "apps" / "macos" / "ViventiumHelper" / "Sources" / "ViventiumHelper" / "ViventiumHelperApp.swift"


def synthetic_macos_home(*parts: str) -> str:
    return "/" + "/".join(("Users", *parts))
PYTHON_STANDALONE_LICENSE_FILES = (
    "LICENSE.bdb.txt",
    "LICENSE.bzip2.txt",
    "LICENSE.cpython.txt",
    "LICENSE.expat.txt",
    "LICENSE.libX11.txt",
    "LICENSE.libXau.txt",
    "LICENSE.libedit.txt",
    "LICENSE.libffi.txt",
    "LICENSE.liblzma.txt",
    "LICENSE.libuuid.txt",
    "LICENSE.libxcb.txt",
    "LICENSE.mpdecimal.txt",
    "LICENSE.ncurses.txt",
    "LICENSE.openssl-1.1.txt",
    "LICENSE.openssl-3.txt",
    "LICENSE.sqlite.txt",
    "LICENSE.tcl.txt",
    "LICENSE.tix.txt",
    "LICENSE.zlib.txt",
    "python-licenses.rst",
)


def executable(path: Path, body: str = "#!/bin/sh\nexit 0\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def file(path: Path, body: str = "fixture\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o644)
    return path


def native_proxy_sandpack_fixture(release_root: Path) -> tuple[Path, str]:
    index = file(
        release_root
        / "runtime"
        / "librechat"
        / "client"
        / "dist"
        / "sandpack-bundler"
        / "index.html",
        '<script>window._env_=Object.assign({},window._env_,{IS_ONPREM:"true"})</script>\n',
    )
    return index.parent, hashlib.sha256(index.read_bytes()).hexdigest()


def fixture_inputs(tmp_path: Path) -> dict[str, Path]:
    node = tmp_path / "node"
    executable(node / "bin" / "node", "#!/bin/sh\necho v24.16.0\n")
    file(node / "LICENSE")

    python = tmp_path / "python"
    executable(python / "bin" / "python3", f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    file(python / "bin" / "pip")
    file(python / "lib" / "python3.12" / "LICENSE.txt")
    file(python / "lib" / "python3.12" / "os.py")
    file(python / "lib" / "python3.12" / "site-packages" / "pip" / "__init__.py")
    for name in PYTHON_STANDALONE_LICENSE_FILES:
        file(python / "python-build-standalone-licenses" / name, f"Synthetic {name}\n")

    mongo = tmp_path / "mongodb"
    executable(mongo / "bin" / "mongod", "#!/bin/sh\necho 'db version v8.0.23'\n")
    executable(mongo / "bin" / "mongos")
    file(mongo / "LICENSE-Community.txt")
    file(mongo / "MPL-2")
    file(mongo / "THIRD-PARTY-NOTICES")

    librechat = tmp_path / "LibreChat"
    file(librechat / "package.json", '{"version":"v0.8.3"}\n')
    file(librechat / "package-lock.json", "{}\n")
    file(librechat / "api" / "server" / "index.js", "// built server fixture\n")
    file(librechat / "client" / "dist" / "index.html", "<html>ready</html>\n")
    file(
        librechat / "client" / "dist" / "sandpack-bundler" / "index.html",
        '<script>window._env_={IS_ONPREM:"true"}</script>\n',
    )
    file(
        librechat / "client" / "dist-compliance" / "module-closure.json",
        '{"schemaVersion":1,"packageLockPaths":[]}\n',
    )
    file(
        librechat / "client" / "dist-compliance" / "manifest.json",
        '{"schemaVersion":1,"packages":[],"vendoredComponents":[]}\n',
    )
    file(
        librechat / "client" / "scripts" / "collect-browser-compliance.cjs",
        "// browser compliance verifier fixture\n",
    )
    file(
        librechat / "client" / "third_party" / "browser-compliance" / "overrides.json",
        '{"schemaVersion":1,"sources":[],"packageOverrides":[],"supplementalNotices":[]}\n',
    )
    file(librechat / "packages" / "api" / "dist" / "index.js", "// built package fixture\n")
    file(librechat / "node_modules" / "dependency" / "index.js", "module.exports = {}\n")
    file(librechat / "scripts" / "viventium-seed-agents.js", "// seed fixture\n")
    file(librechat / "scripts" / "viventium-reconcile-user-defaults.js", "// reconcile fixture\n")
    file(librechat / "config" / "issue-password-reset-link.js", "// reset fixture\n")
    file(
        librechat / "viventium" / "source_of_truth" / "local.viventium-agents.yaml",
        "meta:\n  mainAgentId: agent_viventium_main_fixture\nmainAgent:\n  id: agent_viventium_main_fixture\n",
    )
    file(
        librechat
        / "viventium"
        / "source_of_truth"
        / "managed-agent-baseline-migration.json",
        '{"schema_version":1,"migrations":[],"artifact_sha256":"fixture"}\n',
    )

    helper = tmp_path / "Viventium.app"
    executable(helper / "Contents" / "MacOS" / "Viventium")
    file(helper / "Contents" / "Info.plist", "<plist/>\n")

    bootstrap = tmp_path / "ViventiumBootstrap.app"
    executable(bootstrap / "Contents" / "MacOS" / "ViventiumBootstrap")
    file(bootstrap / "Contents" / "Info.plist", "<plist/>\n")

    compiled = tmp_path / "compiled"
    file(compiled / "librechat.yaml", "version: 1.3.4\ncache: false\n")
    file(compiled / "prompt-bundle.json", '{"schema_version":1,"prompts":[]}\n')
    file(
        compiled / "native-runtime.env",
        "VIVENTIUM_RUNTIME_PROFILE=native\n"
        "VIVENTIUM_INSTALL_MODE=native\n"
        "VIVENTIUM_INSTALL_EXPERIENCE=express\n"
        "VIVENTIUM_CONNECTED_ACCOUNTS_ENABLED=true\n"
        "OPENAI_API_KEY=user_provided\n"
        "ANTHROPIC_API_KEY=user_provided\n"
        "GROQ_API_KEY=user_provided\n"
        "XAI_API_KEY=user_provided\n"
        "VIVENTIUM_LC_API_PORT=3180\n"
        "VIVENTIUM_LC_FRONTEND_PORT=3190\n"
        "VIVENTIUM_PLAYGROUND_PORT=3300\n"
        "SANDPACK_BUNDLER_URL=http://127.0.0.1:3191/\n"
        "SANDPACK_STATIC_BUNDLER_URL=http://127.0.0.1:3191/\n"
        "START_SCHEDULING_MCP=false\n",
    )
    file(
        compiled / "viventium-agents.yaml",
        "meta:\n  mainAgentId: agent_viventium_main_fixture\n"
        "mainAgent:\n  id: agent_viventium_main_fixture\n  tools: [file_search]\n",
    )

    return {
        "node": node,
        "python": python,
        "mongodb": mongo,
        "librechat": librechat,
        "helper": helper,
        "bootstrap": bootstrap,
        "compiled": compiled,
    }


def run_assembler(tmp_path: Path, inputs: dict[str, Path], output: Path, *extra: str):
    return subprocess.run(
        [
            sys.executable,
            str(ASSEMBLER),
            "--repo-root",
            str(REPO_ROOT),
            "--librechat-root",
            str(inputs["librechat"]),
            "--node-root",
            str(inputs["node"]),
            "--python-root",
            str(inputs["python"]),
            "--mongodb-root",
            str(inputs["mongodb"]),
            "--helper-app",
            str(inputs["helper"]),
            "--bootstrap-app",
            str(inputs["bootstrap"]),
            "--compiled-config-root",
            str(inputs["compiled"]),
            "--output-dir",
            str(output),
            "--arch",
            "arm64",
            "--source-commit",
            "a" * 40,
            "--source-date-epoch",
            "1700000000",
            "--mode",
            "local-qa",
            *extra,
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def tree_digest(root: Path) -> list[tuple[str, bytes, int]]:
    return [
        (str(path.relative_to(root)), path.read_bytes(), path.stat().st_mode & 0o777)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def load_native_runtime():
    spec = importlib.util.spec_from_file_location("native_runtime_under_test", NATIVE_RUNTIME)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_native_assembler(monkeypatch):
    monkeypatch.syspath_prepend(str(ASSEMBLER.parent))
    spec = importlib.util.spec_from_file_location("native_assembler_under_test", ASSEMBLER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_native_installer(monkeypatch):
    monkeypatch.syspath_prepend(str(NATIVE_INSTALLER.parent))
    spec = importlib.util.spec_from_file_location("native_installer_under_test", NATIVE_INSTALLER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_native_installer_eperm_liveness_still_reaches_bounded_sigkill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installer = load_native_installer(monkeypatch)
    process_group = 424242
    liveness_checks = 0
    signals: list[int] = []

    def fake_killpg(pid: int, sent_signal: int) -> None:
        nonlocal liveness_checks
        assert pid == process_group
        if sent_signal == 0:
            liveness_checks += 1
            if liveness_checks <= 2:
                raise PermissionError(errno.EPERM, "synthetic macOS process-group race")
            raise ProcessLookupError(errno.ESRCH, "synthetic group drained")
        signals.append(sent_signal)

    process = type(
        "SyntheticOwnedProcess",
        (),
        {"pid": process_group, "poll": lambda self: 0},
    )()
    monkeypatch.setattr(installer.os, "killpg", fake_killpg)

    installer.terminate_owned_process(process, timeout=0)

    assert signals == [signal.SIGTERM, signal.SIGKILL]
    assert liveness_checks >= 3


def test_native_maintenance_surfaces_public_safe_owner_recovery_guidance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    (support / "logs").mkdir(parents=True)
    guidance = (
        "Native first-admin owner verification did not complete. Restore or promote the recorded "
        "administrator, or restore the latest Viventium backup, then retry; otherwise inspect "
        "native-first-admin-recovery.log before retrying."
    )
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(["synthetic"], 1),
    )

    with pytest.raises(runtime.RuntimeError_, match="Restore or promote the recorded administrator"):
        runtime.run_native_maintenance(
            "first-admin-recovery",
            ["synthetic"],
            support,
            cwd=tmp_path,
            env={},
            public_failure_message=guidance,
        )


@pytest.mark.parametrize("surface", ["health", "doctor"])
def test_native_health_surfaces_recovery_for_closed_state_without_owner_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, surface: str
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    file(
        support / "state" / "native-runtime.json",
        '{"schema_version":1}\n',
    )
    monkeypatch.setattr(runtime, "release_root", lambda: tmp_path / "release")
    monkeypatch.setattr(runtime, "packaged_health", lambda _root: None)
    monkeypatch.setattr(runtime, "validate_support_children", lambda _support: None)
    monkeypatch.setattr(runtime, "reject_pending_restore_for_read", lambda _support: None)
    monkeypatch.setattr(runtime, "owned_service_pid", lambda *_args: 123)
    monkeypatch.setattr(runtime, "semantic_unix_http_ready", lambda *_args: True)
    monkeypatch.setattr(runtime, "semantic_http_ready", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(runtime, "native_child_environment", lambda _support: {})
    monkeypatch.setattr(
        runtime,
        "build_metadata",
        lambda _root: {"source_commit": "a" * 40, "sandpack_index_sha256": "b" * 64},
    )
    monkeypatch.setattr(
        runtime,
        "ensure_first_admin_state",
        lambda _support: {"schema_version": 1, "status": "closed"},
    )

    args = type("Args", (), {"app_support_dir": support, "installed_only": False})()
    with pytest.raises(
        runtime.RuntimeError_, match="Restore or promote the recorded administrator"
    ) as raised:
        getattr(runtime, surface)(args)

    assert not isinstance(raised.value.__cause__, KeyError)


def test_assembler_builds_deterministic_relocatable_payload_and_bootstrap(tmp_path: Path) -> None:
    inputs = fixture_inputs(tmp_path)
    first = tmp_path / "first"
    second = tmp_path / "second"

    one = run_assembler(tmp_path, inputs, first)
    two = run_assembler(tmp_path, inputs, second)

    assert one.returncode == 0, one.stderr
    assert two.returncode == 0, two.stderr
    assert tree_digest(first) == tree_digest(second)
    payload = first / "payload"
    assert (payload / "runtime" / "node" / "bin" / "node").is_file()
    assert (payload / "runtime" / "python" / "bin" / "python3").is_file()
    assert (payload / "runtime" / "mongodb" / "bin" / "mongod").is_file()
    assert not (payload / "runtime" / "node" / "bin" / "npm").exists()
    assert not (payload / "runtime" / "python" / "bin" / "pip").exists()
    assert not (payload / "runtime" / "python" / "lib" / "python3.12" / "site-packages").exists()
    assert not (payload / "runtime" / "mongodb" / "bin" / "mongos").exists()
    assert (payload / "runtime" / "librechat" / "client" / "dist" / "index.html").is_file()
    assert (payload / "runtime" / "defaults" / "viventium-agents.yaml").is_file()
    assembled_agents = yaml.safe_load(
        (payload / "runtime" / "defaults" / "viventium-agents.yaml").read_text(encoding="utf-8")
    )
    assert assembled_agents["mainAgent"]["tools"] == ["file_search"]
    assert (payload / "runtime" / "defaults" / "native-runtime.env").is_file()
    assert (payload / "runtime" / "scripts" / "native_verify_agent.js").is_file()
    assert (
        payload / "runtime" / "scripts" / "native_first_admin_recovery.js"
    ).read_bytes() == NATIVE_FIRST_ADMIN_RECOVERY.read_bytes()
    assert (payload / "bin" / "viventium-native-registration-close").is_file()
    assert (payload / "bin" / "viventium-native-password-reset-link").is_file()
    assert (payload / "apps" / "Viventium.app" / "Contents" / "MacOS" / "Viventium").is_file()
    assert (first / "bootstrap" / "ViventiumBootstrap.app").is_dir()
    bootstrap_python = (
        first
        / "bootstrap"
        / "ViventiumBootstrap.app"
        / "Contents"
        / "Resources"
        / "runtime"
        / "python"
    )
    assert tree_digest(payload / "runtime" / "python") == tree_digest(bootstrap_python)
    payload_python_manifest = json.loads(
        (payload / "release-metadata" / "python-runtime-manifest.json").read_text()
    )
    bootstrap_python_manifest = json.loads(
        (
            first
            / "bootstrap"
            / "ViventiumBootstrap.app"
            / "Contents"
            / "Resources"
            / "python-runtime-manifest.json"
        ).read_text()
    )
    assert payload_python_manifest == bootstrap_python_manifest
    assert payload_python_manifest["component"]["name"] == "python"
    assert payload_python_manifest["files"]
    assert len(payload_python_manifest["tree_sha256"]) == 64
    metadata = json.loads((payload / "release-metadata" / "build.json").read_text())
    sandpack_index = (
        payload
        / "runtime"
        / "librechat"
        / "client"
        / "dist"
        / "sandpack-bundler"
        / "index.html"
    )
    component_policy = json.loads(
        (REPO_ROOT / "release" / "native-payload" / "components.json").read_text()
    )
    assert metadata == {
        "arch": "arm64",
        "components": {
            "librechat": {"commit": component_policy["librechat"]["commit"]},
            "mongodb": {
                "archive_sha256": component_policy["mongodb"]["architectures"]["arm64"][
                    "sha256"
                ],
                "version": component_policy["mongodb"]["version"],
            },
            "node": {
                "archive_sha256": component_policy["node"]["architectures"]["arm64"][
                    "sha256"
                ],
                "version": component_policy["node"]["version"],
            },
            "python": {
                "archive_sha256": component_policy["python"]["architectures"]["arm64"][
                    "sha256"
                ],
                "license_source_commit": component_policy["python"]["license_source"][
                    "commit"
                ],
                "license_source_sha256": component_policy["python"]["license_source"][
                    "sha256"
                ],
                "version": component_policy["python"]["version"],
            },
        },
        "mode": "local-qa",
        "data_schema": {"maximum": 1, "minimum": 1, "target": 1},
        "source_commit": "a" * 40,
        "source_date_epoch": 1700000000,
        "sandpack_index_sha256": hashlib.sha256(sandpack_index.read_bytes()).hexdigest(),
    }
    assert not any(path.is_symlink() for path in first.rglob("*"))
    assert {mode for _, _, mode in tree_digest(first)} <= {0o644, 0o755}


def test_assembler_rejects_missing_built_runtime_and_external_symlink(tmp_path: Path) -> None:
    inputs = fixture_inputs(tmp_path)
    (inputs["librechat"] / "client" / "dist" / "index.html").unlink()
    missing = run_assembler(tmp_path, inputs, tmp_path / "missing")
    assert missing.returncode != 0
    assert "built LibreChat" in missing.stderr

    inputs = fixture_inputs(tmp_path / "missing-compliance-fixture")
    (inputs["librechat"] / "client" / "dist-compliance" / "manifest.json").unlink()
    missing_compliance = run_assembler(
        tmp_path,
        inputs,
        tmp_path / "missing-compliance",
    )
    assert missing_compliance.returncode != 0
    assert "browser compliance" in missing_compliance.stderr.lower()

    inputs = fixture_inputs(tmp_path / "second-fixture")
    outside = file(tmp_path / "outside-secret", "must not copy\n")
    (inputs["librechat"] / "escape").symlink_to(outside)
    unsafe = run_assembler(tmp_path, inputs, tmp_path / "unsafe")
    assert unsafe.returncode != 0
    assert "symlink" in unsafe.stderr.lower()
    assert not (tmp_path / "unsafe").exists()


def test_assembler_rejects_unattestable_component_metadata(tmp_path: Path) -> None:
    inputs = fixture_inputs(tmp_path)
    policy = json.loads(
        (REPO_ROOT / "release" / "native-payload" / "components.json").read_text()
    )

    policy["librechat"]["commit"] = "not-a-full-commit"
    invalid_commit_policy = file(
        tmp_path / "invalid-commit-components.json", json.dumps(policy)
    )
    invalid_commit = run_assembler(
        tmp_path,
        inputs,
        tmp_path / "invalid-commit-candidate",
        "--components",
        str(invalid_commit_policy),
    )
    assert invalid_commit.returncode != 0
    assert "LibreChat component commit" in invalid_commit.stderr

    policy = json.loads(
        (REPO_ROOT / "release" / "native-payload" / "components.json").read_text()
    )
    policy["node"]["architectures"]["arm64"]["sha256"] = "not-a-digest"
    invalid_digest_policy = file(
        tmp_path / "invalid-digest-components.json", json.dumps(policy)
    )
    invalid_digest = run_assembler(
        tmp_path,
        inputs,
        tmp_path / "invalid-digest-candidate",
        "--components",
        str(invalid_digest_policy),
    )
    assert invalid_digest.returncode != 0
    assert "node arm64 component digest" in invalid_digest.stderr


def test_assembler_excludes_runtime_artifacts_and_python_bytecode(tmp_path: Path) -> None:
    inputs = fixture_inputs(tmp_path)
    private_fixture = synthetic_macos_home("build-owner", "private") + "\n"
    file(inputs["librechat"] / "logs" / ".runtime-audit.json", private_fixture)
    file(inputs["librechat"] / "nested" / "request-audit.json", private_fixture)
    file(inputs["librechat"] / "node_modules" / "telemetry" / "logs" / "index.js", "export {}\n")
    file(inputs["librechat"] / "node_modules" / "dependency" / ".cache" / "compiler.json", private_fixture)
    file(inputs["python"] / "lib" / "__pycache__" / "module.cpython-312.pyc", "bytecode\n")
    file(inputs["bootstrap"] / "Contents" / "Resources" / "module.pyo", "bytecode\n")

    output = tmp_path / "candidate"
    completed = run_assembler(tmp_path, inputs, output)

    assert completed.returncode == 0, completed.stderr
    relative_files = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }
    assert not any("/__pycache__/" in f"/{path}/" for path in relative_files)
    assert not any("/.cache/" in f"/{path}/" for path in relative_files)
    assert not any(path.endswith(("-audit.json", ".pyc", ".pyo")) for path in relative_files)
    assert "payload/runtime/librechat/node_modules/telemetry/logs/index.js" in relative_files


def test_distributable_candidate_fails_closed_without_redistribution_approval(tmp_path: Path) -> None:
    inputs = fixture_inputs(tmp_path)
    completed = run_assembler(
        tmp_path,
        inputs,
        tmp_path / "candidate",
        "--mode",
        "candidate",
    )
    assert completed.returncode != 0
    assert "redistribution approval" in completed.stderr


def test_candidate_sandpack_runtime_is_bound_to_public_policy(monkeypatch, tmp_path: Path) -> None:
    assembler = load_native_assembler(monkeypatch)
    librechat = fixture_inputs(tmp_path)["librechat"]

    local_digest = assembler.validate_sandpack_runtime(librechat, mode="local-qa")
    assert len(local_digest) == 64
    with pytest.raises(assembler.AssemblyError, match="does not match public policy"):
        assembler.validate_sandpack_runtime(librechat, mode="candidate")


def test_local_qa_install_and_health_entrypoints_run_without_target_build_tools(tmp_path: Path) -> None:
    inputs = fixture_inputs(tmp_path)
    output = tmp_path / "candidate"
    completed = run_assembler(tmp_path, inputs, output)
    assert completed.returncode == 0, completed.stderr
    payload = output / "payload"
    support = tmp_path / "Application Support" / "Viventium"

    install = subprocess.run(
        [
            str(payload / "bin" / "viventium-native-install"),
            "--app-support-dir",
            str(support),
            "--local-qa",
            "--no-start",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert install.returncode == 0, install.stderr
    assert (support / "config.yaml").is_file()
    installed_env = (support / "runtime" / "runtime.env").read_text(encoding="utf-8")
    assert installed_env == (payload / "runtime" / "defaults" / "native-runtime.env").read_text(
        encoding="utf-8"
    )
    assert (payload / "bin" / "viventium").is_file()
    assert (
        payload
        / "runtime"
        / "librechat"
        / "viventium"
        / "source_of_truth"
        / "managed-agent-baseline-migration.json"
    ).is_file()
    assert json.loads((support / "state" / "native-runtime.json").read_text())["release_root"] == str(payload)
    secrets_path = support / "state" / "native-secrets.json"
    secrets = json.loads(secrets_path.read_text())
    assert set(secrets) == {"JWT_SECRET", "JWT_REFRESH_SECRET", "CREDS_KEY", "CREDS_IV"}
    assert secrets_path.stat().st_mode & 0o777 == 0o600
    assert all(value not in json.dumps(tree_digest(payload), default=str) for value in secrets.values())
    health = subprocess.run(
        [str(payload / "bin" / "viventium-native-health"), "--app-support-dir", str(support), "--installed-only"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert health.returncode == 0, health.stderr
    assert not list(payload.rglob("__pycache__"))
    assert not list(payload.rglob("*.py[co]"))

    forbidden = ("npm ", "npx ", "pip ", "brew ", "git ", "curl ")
    for path in (payload / "bin").iterdir():
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert not any(token in text for token in forbidden), path


def test_stale_pid_record_is_quarantined_without_signalling_unrelated_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    path = runtime.pid_path(support, "mongodb")
    record = {
        "schema_version": 1,
        "pid": os.getpid(),
        "token": "a" * 64,
        "process_start": "not-the-current-start",
        "release_root": str(runtime.release_root()),
        "service": "mongodb",
    }
    runtime.write_atomic(path, json.dumps(record))
    signalled: list[tuple[int, int]] = []
    monkeypatch.setattr(runtime.os, "killpg", lambda pid, signal: signalled.append((pid, signal)))

    runtime.stop(type("Args", (), {"app_support_dir": support})())

    assert signalled == []
    assert not path.exists()
    assert len(list(path.parent.glob(f"{path.name}.stale.*"))) == 1


def test_process_guard_record_binds_and_stops_only_owned_process_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    root = tmp_path / "release"
    interpreter = root / "runtime" / "python" / "bin" / "python3"
    executable(interpreter, f"#!/bin/sh\nexec {shlex.quote(sys.executable)} \"$@\"\n")
    guard = root / "runtime" / "scripts" / "native_process_guard.py"
    guard.parent.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "scripts" / "viventium" / "native_process_guard.py", guard)
    guard.chmod(0o755)
    support = tmp_path / "support"
    (support / "logs").mkdir(parents=True)
    (support / "runtime").mkdir()
    monkeypatch.setattr(runtime, "release_root", lambda: root)
    monkeypatch.setattr(runtime, "process_executable", lambda _pid: interpreter)

    runtime.spawn(
        "mongodb",
        [sys.executable, "-c", "import time; time.sleep(60)"],
        support,
        cwd=tmp_path,
        env=dict(os.environ),
    )
    record_path = runtime.pid_path(support, "mongodb")
    record = json.loads(record_path.read_text())
    assert runtime.live_pid(record_path, root) == record["pid"]
    assert " -E -s -B " in runtime.process_value(record["pid"], "command")

    args = type("Args", (), {"app_support_dir": support})()
    runtime.stop(args)
    assert runtime.live_pid(runtime.pid_path(support, "mongodb"), root) is None


def test_native_listener_pid_probe_parses_only_lsof_process_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = load_native_runtime()

    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["/usr/sbin/lsof"], 0, stdout="123\n456\n", stderr=""
        ),
    )
    assert runtime.listener_pids(3190) == {123, 456}

    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["/usr/sbin/lsof"], 0, stdout="COMMAND PID\n", stderr=""
        ),
    )
    with pytest.raises(runtime.RuntimeError_, match="listener ownership"):
        runtime.listener_pids(3190)

    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["/usr/sbin/lsof"], 1, stdout="", stderr="permission denied\n"
        ),
    )
    with pytest.raises(runtime.RuntimeError_, match="could not be verified"):
        runtime.listener_pids(3190)


def test_native_process_executable_ignores_macos_loader_text_mappings() -> None:
    if sys.platform != "darwin":
        pytest.skip("Native process executable proof is macOS-specific")
    runtime = load_native_runtime()

    executable = runtime.process_executable(os.getpid())

    assert executable is not None
    assert executable.is_file()
    assert executable.name != "dyld"
    assert not executable.name.startswith("dyld_shared_cache")


def test_native_start_refuses_foreign_listener_before_mutable_initialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    root = tmp_path / "release"
    support = tmp_path / "support"
    support.mkdir(mode=0o700)
    mutable_calls: list[str] = []

    monkeypatch.setattr(runtime, "runtime_state", lambda _support: {"release_root": str(root)})
    monkeypatch.setattr(runtime, "release_root", lambda: root)
    monkeypatch.setattr(runtime, "packaged_health", lambda _root: None)
    monkeypatch.setattr(
        runtime,
        "build_metadata",
        lambda _root: {"source_commit": "a" * 40, "sandpack_index_sha256": "0" * 64},
    )
    monkeypatch.setattr(
        runtime,
        "listener_pids",
        lambda port: {4242} if port == 3190 else set(),
    )
    monkeypatch.setattr(
        runtime,
        "ensure_first_admin_state",
        lambda _support: mutable_calls.append("first-admin") or {"status": "open"},
    )
    monkeypatch.setattr(
        runtime,
        "runtime_secrets",
        lambda _support: mutable_calls.append("secrets") or {},
    )
    monkeypatch.setattr(
        runtime,
        "spawn",
        lambda *_args, **_kwargs: mutable_calls.append("spawn"),
    )

    args = type("Args", (), {"app_support_dir": support, "timeout": 0.1})()
    with pytest.raises(runtime.RuntimeError_, match="port 3190.*another process.*no changes"):
        runtime.start(args)

    assert mutable_calls == []


def test_native_install_refuses_foreign_listener_without_support_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    root = tmp_path / "release"
    support = tmp_path / "new-support"

    monkeypatch.setattr(runtime, "release_root", lambda: root)
    monkeypatch.setattr(runtime, "packaged_health", lambda _root: None)
    monkeypatch.setattr(
        runtime,
        "listener_pids",
        lambda port: {4242} if port == 3190 else set(),
    )
    args = type(
        "Args",
        (),
        {
            "app_support_dir": support,
            "local_qa": True,
            "no_helper": True,
            "no_start": False,
            "no_open": True,
            "timeout": 0.1,
        },
    )()

    with pytest.raises(runtime.RuntimeError_, match="port 3190.*another process.*no changes"):
        runtime.install(args)

    assert not support.exists()


def test_native_collision_preflight_does_not_quarantine_stale_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    root = tmp_path / "release"
    support = tmp_path / "support"
    record_path = runtime.pid_path(support, "frontend-proxy")
    runtime.write_atomic(record_path, "{\"invalid\":true}\n")
    original = record_path.read_bytes()
    monkeypatch.setattr(runtime, "listener_pids", lambda port: {4242} if port == 3190 else set())

    with pytest.raises(runtime.RuntimeError_, match="no changes"):
        runtime.preflight_service_ports(support, root)

    assert record_path.read_bytes() == original
    assert not list(record_path.parent.glob(f"{record_path.name}.stale.*"))


def test_native_collision_preflight_checks_isolated_sandpack_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    root = tmp_path / "release"
    support = tmp_path / "support"
    monkeypatch.setattr(runtime, "listener_pids", lambda port: {4242} if port == 3191 else set())

    with pytest.raises(runtime.RuntimeError_, match="port 3191.*another process.*no changes"):
        runtime.preflight_service_ports(support, root)


def test_native_proxy_ownership_requires_both_web_origins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    root = tmp_path / "release"
    support = tmp_path / "support"
    monkeypatch.setattr(runtime, "live_pid", lambda *_args, **_kwargs: 4242)
    monkeypatch.setattr(runtime, "listeners_owned_by_guard", lambda listeners, pid: listeners == {pid})
    monkeypatch.setattr(runtime, "listener_pids", lambda port: {4242} if port == 3190 else set())

    assert runtime.owned_listener_pid("frontend-proxy", support, root) is None


def test_native_lifecycle_lock_rejects_concurrent_mutation(tmp_path: Path) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    holder_source = (
        "import importlib.util,sys,time\n"
        "from pathlib import Path\n"
        "spec=importlib.util.spec_from_file_location('holder',sys.argv[1])\n"
        "module=importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(module)\n"
        "with module.lifecycle_lock(Path(sys.argv[2]),timeout=1):\n"
        " print('LOCKED',flush=True)\n"
        " time.sleep(30)\n"
    )
    holder = subprocess.Popen(
        [sys.executable, "-B", "-c", holder_source, str(NATIVE_RUNTIME), str(support)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "LOCKED"
        with pytest.raises(runtime.RuntimeError_, match="lifecycle operation"):
            with runtime.lifecycle_lock(support, timeout=0.2):
                raise AssertionError("concurrent lifecycle lock must not be acquired")
    finally:
        holder.terminate()
        holder.wait(timeout=5)


def test_native_lifecycle_lock_cannot_be_bypassed_with_a_different_tmpdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    first_tmp = tmp_path / "caller-tmp-a"
    second_tmp = tmp_path / "caller-tmp-b"
    first_tmp.mkdir()
    second_tmp.mkdir()
    support = tmp_path / "support"

    monkeypatch.setattr(tempfile, "tempdir", str(first_tmp))
    with runtime.lifecycle_lock(support, timeout=0.2):
        monkeypatch.setattr(tempfile, "tempdir", str(second_tmp))
        with pytest.raises(runtime.RuntimeError_, match="lifecycle operation"):
            with runtime.lifecycle_lock(support, timeout=0.2):
                raise AssertionError("TMPDIR must not create a second lock namespace")


def test_native_support_identity_canonicalizes_a_symlinked_parent_without_following_leaf(
    tmp_path: Path,
) -> None:
    runtime = load_native_runtime()
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    alias_parent = tmp_path / "alias-parent"
    alias_parent.symlink_to(real_parent, target_is_directory=True)

    assert runtime.lexical_support(alias_parent / "support") == real_parent / "support"

    leaf_target = real_parent / "leaf-target"
    leaf_target.mkdir()
    leaf_alias = real_parent / "leaf-alias"
    leaf_alias.symlink_to(leaf_target, target_is_directory=True)
    with pytest.raises(runtime.RuntimeError_, match="mutable path is unsafe"):
        runtime.validate_support_children(runtime.lexical_support(leaf_alias))


def test_native_old_release_stop_and_registration_hook_cannot_touch_active_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    invoked_root = tmp_path / "old-release"
    active_root = tmp_path / "active-release"
    support = tmp_path / "support"
    state = file(
        support / "state" / "native-runtime.json",
        json.dumps(
            {
                "schema_version": 1,
                "release_root": str(active_root),
                "installed_at": 1,
                "local_qa": True,
            }
        ),
    )
    state.chmod(0o600)
    first_admin = file(
        support / "state" / "native-first-admin.json",
        json.dumps({"schema_version": 1, "status": "closed"}),
    )
    first_admin.chmod(0o600)
    calls: list[str] = []
    monkeypatch.setattr(runtime, "release_root", lambda: invoked_root)
    monkeypatch.setattr(
        runtime,
        "stop_service",
        lambda service, _support, _root: calls.append(f"stop:{service}"),
    )
    monkeypatch.setattr(runtime, "start", lambda *_args, **_kwargs: calls.append("start"))

    with pytest.raises(runtime.RuntimeError_, match="release pointer"):
        runtime.stop(type("Args", (), {"app_support_dir": support})())
    with pytest.raises(runtime.RuntimeError_, match="release pointer"):
        runtime.registration_close(
            type("Args", (), {"app_support_dir": support, "timeout": 1.0})()
        )
    with pytest.raises(runtime.RuntimeError_, match="release pointer"):
        runtime.refuse_cross_mode_install(support)

    assert calls == []


def test_native_start_failure_stops_only_services_launched_by_that_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    root = tmp_path / "release"
    support = tmp_path / "support"
    support.mkdir(mode=0o700)
    spawned: list[str] = []
    stopped: list[str] = []

    monkeypatch.setattr(runtime, "runtime_state", lambda _support: {"release_root": str(root)})
    monkeypatch.setattr(runtime, "release_root", lambda: root)
    monkeypatch.setattr(runtime, "packaged_health", lambda _root: None)
    monkeypatch.setattr(
        runtime,
        "build_metadata",
        lambda _root: {"source_commit": "a" * 40, "sandpack_index_sha256": "0" * 64},
    )
    monkeypatch.setattr(runtime, "preflight_service_ports", lambda *_args: None)
    monkeypatch.setattr(runtime, "preflight_mongodb_socket", lambda *_args: None)
    monkeypatch.setattr(runtime, "preflight_api_socket", lambda *_args: None)
    monkeypatch.setattr(runtime, "live_pid", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        runtime,
        "ensure_first_admin_state",
        lambda _support: {"schema_version": 1, "status": "open", "token": "a" * 64},
    )
    monkeypatch.setattr(runtime, "native_child_environment", lambda _support: {})
    monkeypatch.setattr(runtime, "runtime_secrets", lambda _support: {})
    monkeypatch.setattr(
        runtime,
        "spawn",
        lambda service, *_args, **_kwargs: spawned.append(service),
    )
    monkeypatch.setattr(runtime, "wait_owned_mongodb_socket", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        runtime,
        "stop_service",
        lambda service, _support, _root: stopped.append(service),
    )

    with pytest.raises(runtime.RuntimeError_, match="MongoDB did not become ready"):
        runtime.start(type("Args", (), {"app_support_dir": support, "timeout": 0.1})())

    assert spawned == ["mongodb"]
    assert stopped == ["mongodb"]


def test_native_start_failure_preserves_a_preexisting_owned_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    root = tmp_path / "release"
    support = tmp_path / "support"
    support.mkdir(mode=0o700)
    stopped: list[str] = []
    maintenance: list[tuple[str, list[str]]] = []

    monkeypatch.setattr(runtime, "runtime_state", lambda _support: {"release_root": str(root)})
    monkeypatch.setattr(runtime, "release_root", lambda: root)
    monkeypatch.setattr(runtime, "packaged_health", lambda _root: None)
    monkeypatch.setattr(
        runtime,
        "build_metadata",
        lambda _root: {"source_commit": "a" * 40, "sandpack_index_sha256": "0" * 64},
    )
    monkeypatch.setattr(runtime, "preflight_service_ports", lambda *_args: None)
    monkeypatch.setattr(runtime, "preflight_mongodb_socket", lambda *_args: None)
    monkeypatch.setattr(runtime, "preflight_api_socket", lambda *_args: None)
    monkeypatch.setattr(
        runtime,
        "live_pid",
        lambda path, *_args, **_kwargs: 111 if Path(path).name.startswith("mongodb.") else None,
    )
    monkeypatch.setattr(
        runtime,
        "ensure_first_admin_state",
        lambda _support: {"schema_version": 1, "status": "open", "token": "a" * 64},
    )
    monkeypatch.setattr(runtime, "native_child_environment", lambda _support: {})
    monkeypatch.setattr(runtime, "runtime_secrets", lambda _support: {})
    monkeypatch.setattr(runtime, "spawn", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        runtime,
        "run_native_maintenance",
        lambda label, command, *_args, **_kwargs: maintenance.append((label, command)),
    )
    monkeypatch.setattr(runtime, "wait_owned_mongodb_socket", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        runtime,
        "stop_service",
        lambda service, _support, _root: stopped.append(service),
    )

    with pytest.raises(runtime.RuntimeError_, match="LibreChat did not become ready"):
        runtime.start(type("Args", (), {"app_support_dir": support, "timeout": 0.1})())

    assert stopped == ["librechat"]
    assert maintenance[0] == (
        "first-admin-recovery",
        [
            str(root / "runtime" / "node" / "bin" / "node"),
            str(root / "runtime" / "scripts" / "native_first_admin_recovery.js"),
            str(support / "state" / "native-first-admin.json"),
            str(root / "runtime" / "librechat"),
            runtime.mongodb_uri(support),
            str(root / "runtime" / "defaults" / "viventium-agents.yaml"),
        ],
    )


def test_native_mongodb_connections_use_a_support_owned_unix_socket(tmp_path: Path) -> None:
    runtime = load_native_runtime()
    support = runtime.lexical_support(tmp_path / "support with spaces")

    socket_path = support / "runtime" / "mongodb-27117.sock"
    assert runtime.mongodb_uri(support) == (
        f"mongodb://{urllib.parse.quote(str(socket_path), safe='')}/LibreChat"
    )


def test_native_mongodb_launch_is_unix_only_and_never_reserves_a_tcp_port() -> None:
    runtime = load_native_runtime()
    source = NATIVE_RUNTIME.read_text(encoding="utf-8")

    assert runtime.SERVICE_PORTS == {"frontend-proxy": (3190, 3191)}
    mongodb_launch = source[source.index('spawn(\n            "mongodb"') :]
    mongodb_launch = mongodb_launch[: mongodb_launch.index('if preexisting["mongodb"]')]
    assert '"--bind_ip", str(mongodb_socket_path(support))' in mongodb_launch
    assert '"--nounixsocket"' in mongodb_launch
    assert '"--filePermissions", "0600"' in mongodb_launch
    assert '"--bind_ip", "127.0.0.1"' not in mongodb_launch
    assert '"--unixSocketPrefix"' not in mongodb_launch
    assert 'wait_owned_mongodb_socket(support, root, args.timeout)' in source


def test_native_mongodb_socket_preflight_rejects_a_foreign_listener_without_unlinking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = load_native_runtime()
    short_root = Path(tempfile.mkdtemp(prefix="viventium-mongo-preflight-", dir="/private/tmp"))
    support = short_root / "support"
    root = short_root / "release"
    socket_path = runtime.mongodb_socket_path(support)
    socket_path.parent.mkdir(parents=True)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(socket_path))
    socket_path.chmod(0o600)
    listener.listen()
    monkeypatch.setattr(runtime, "unix_socket_pids", lambda _path: {4242})
    monkeypatch.setattr(runtime, "live_pid", lambda *_args, **_kwargs: None)
    try:
        with pytest.raises(runtime.RuntimeError_, match="MongoDB socket.*another process"):
            runtime.preflight_mongodb_socket(support, root)
        assert socket_path.exists()
    finally:
        listener.close()
        shutil.rmtree(short_root)


def test_native_private_socket_metadata_rejects_group_or_world_access() -> None:
    runtime = load_native_runtime()
    short_root = Path(tempfile.mkdtemp(prefix="viventium-socket-mode-", dir="/private/tmp"))
    target = short_root / "service.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        listener.bind(str(target))
        target.chmod(0o660)
        listener.listen()
        with pytest.raises(runtime.RuntimeError_, match="socket path is unsafe"):
            runtime.private_socket_metadata(target, "synthetic")
    finally:
        listener.close()
        shutil.rmtree(short_root)


def test_native_mongodb_socket_readiness_rejects_tcp_listeners_in_its_guard_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = load_native_runtime()
    short_root = Path(tempfile.mkdtemp(prefix="viventium-mongo-ready-", dir="/private/tmp"))
    support = short_root / "support"
    root = short_root / "release"
    socket_path = runtime.mongodb_socket_path(support)
    socket_path.parent.mkdir(parents=True)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(socket_path))
    socket_path.chmod(0o600)
    listener.listen()
    monkeypatch.setattr(runtime, "owned_mongodb_socket_pid", lambda *_args: 111)
    monkeypatch.setattr(runtime, "process_group_tcp_listener_pids", lambda _pid: {222})
    try:
        with pytest.raises(runtime.RuntimeError_, match="must not expose a TCP listener"):
            runtime.wait_owned_mongodb_socket(support, root, 0.1)
    finally:
        listener.close()
        shutil.rmtree(short_root)


def test_native_wait_refuses_semantically_healthy_foreign_listener(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    root = tmp_path / "release"
    semantic_calls: list[str] = []

    monkeypatch.setattr(runtime, "live_pid", lambda *_args: 111)
    monkeypatch.setattr(runtime, "listener_pids", lambda _port: {222})
    monkeypatch.setattr(
        runtime,
        "semantic_http_ready",
        lambda url, *_args: semantic_calls.append(url) or True,
    )

    with pytest.raises(runtime.RuntimeError_, match="does not belong to mongodb"):
        runtime.wait_owned_service(
            "mongodb",
            27117,
            support,
            root,
            0.1,
        )

    assert semantic_calls == []


def test_native_wait_accepts_real_listener_only_inside_owned_guard_process_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not Path("/usr/sbin/lsof").is_file():
        pytest.skip("Native listener ownership requires macOS lsof")
    runtime = load_native_runtime()
    root = tmp_path / "release"
    interpreter = root / "runtime" / "python" / "bin" / "python3"
    executable(interpreter, f"#!/bin/sh\nexec {shlex.quote(sys.executable)} \"$@\"\n")
    guard = root / "runtime" / "scripts" / "native_process_guard.py"
    guard.parent.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "scripts" / "viventium" / "native_process_guard.py", guard)
    guard.chmod(0o755)
    support = tmp_path / "support"
    (support / "logs").mkdir(parents=True)
    (support / "runtime").mkdir()
    monkeypatch.setattr(runtime, "release_root", lambda: root)
    monkeypatch.setattr(runtime, "process_executable", lambda _pid: interpreter)

    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    listener_script = file(
        tmp_path / "synthetic-listener.py",
        "import socket, sys, time\n"
        "listener = socket.socket()\n"
        "listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
        "listener.bind(('127.0.0.1', int(sys.argv[1])))\n"
        "listener.listen()\n"
        "time.sleep(60)\n",
    )
    runtime.spawn(
        "frontend-proxy",
        [sys.executable, str(listener_script), str(port)],
        support,
        cwd=tmp_path,
        env=dict(os.environ),
    )
    try:
        deadline = time.monotonic() + 3.0
        listeners: set[int] = set()
        while time.monotonic() < deadline and not listeners:
            listeners = runtime.listener_pids(port)
            time.sleep(0.05)
        record = json.loads(runtime.pid_path(support, "frontend-proxy").read_text())
        assert os.getpgid(record["pid"]) == record["pid"]
        assert record["process_start"] == runtime.process_value(record["pid"], "lstart")
        command = runtime.process_value(record["pid"], "command")
        assert command is not None
        assert str(guard) in command
        assert f"--token {record['token']}" in command
        guard_pid = runtime.live_pid(runtime.pid_path(support, "frontend-proxy"), root)
        assert guard_pid is not None
        assert listeners
        assert {os.getpgid(pid) for pid in listeners} == {guard_pid}
        assert runtime.wait_owned_service("frontend-proxy", port, support, root, 5.0) is True
        listeners = runtime.listener_pids(port)
        assert listeners
        assert listeners != {guard_pid}
        assert runtime.listeners_owned_by_guard(listeners, guard_pid) is True
    finally:
        runtime.stop_service("frontend-proxy", support, root)


def owned_helper(path: Path, source_commit: str) -> None:
    executable(path / "Contents" / "MacOS" / "ViventiumHelper")
    file(
        path / "Contents" / "Resources" / "viventium-owner.json",
        json.dumps(
            {
                "product": "ai.viventium.helper",
                "schema_version": 1,
                "source_commit": source_commit,
            }
        ),
    )


def test_helper_activation_refuses_unrelated_app_and_rolls_back_owned_prior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    home = tmp_path / "home"
    target = home / "Applications" / "Viventium.app"
    file(target / "Contents" / "Info.plist", "unrelated\n")
    source = tmp_path / "source" / "Viventium.app"
    owned_helper(source, "b" * 40)
    support = tmp_path / "support"
    monkeypatch.setattr(runtime, "user_home", lambda: home)

    with pytest.raises(runtime.RuntimeError_, match="unrelated application"):
        runtime.install_helper(source, support)
    assert (target / "Contents" / "Info.plist").read_text() == "unrelated\n"

    (target / "Contents" / "Info.plist").unlink()
    owned_helper(target, "a" * 40)
    file(target / "prior.txt", "prior\n")
    real_replace = runtime.os.replace

    def fail_activation(source_path, destination_path):
        if Path(source_path).name.startswith(".Viventium.app.installing"):
            raise OSError("synthetic activation failure")
        return real_replace(source_path, destination_path)

    monkeypatch.setattr(runtime.os, "replace", fail_activation)
    with pytest.raises(OSError, match="synthetic activation failure"):
        runtime.install_helper(source, support)
    assert (target / "prior.txt").read_text() == "prior\n"


def test_native_helper_refuses_symlinked_applications_without_touching_external_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    home = tmp_path / "home"
    home.mkdir()
    external = tmp_path / "external-applications"
    external.mkdir()
    sentinel = file(external / "personal-app.txt", "untouched\n")
    (home / "Applications").symlink_to(external, target_is_directory=True)
    source = tmp_path / "source" / "Viventium.app"
    owned_helper(source, "b" * 40)
    support = tmp_path / "support"
    monkeypatch.setattr(runtime, "user_home", lambda: home)

    with pytest.raises(runtime.RuntimeError_, match="Applications directory is unsafe"):
        runtime.install_helper(source, support)

    assert sentinel.read_text(encoding="utf-8") == "untouched\n"
    assert sorted(path.name for path in external.iterdir()) == ["personal-app.txt"]


def test_candidate_workflow_is_exact_dual_arch_relocatable_producer() -> None:
    workflow = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "macos-15",
        "macos-15-intel",
        "arm64",
        "x86_64",
        "release/native-payload/components.json",
        "python-build-standalone-licenses",
        "license_source",
        "mongodb-redistribution-approved",
        "bootstrap_components.py",
        "npm ci",
        "npm run build:packages",
        "npm run build:client",
        "npm ci --omit=dev --workspace api --include-workspace-root",
        "npm ls --omit=dev --workspace api --include-workspace-root",
        "node client/scripts/collect-browser-compliance.cjs --verify",
        "npm run test:production-runtime-load",
        "test ! -e node_modules/@codesandbox/nodebox",
        "npm audit --omit=dev --audit-level=moderate",
        "assemble_native_payload.py",
        "/usr/bin/diff -qr",
        '"$candidate_root/payload/runtime/python"',
        '"$candidate_root/bootstrap/ViventiumBootstrap.app/Contents/Resources/runtime/python"',
        "verify_native_public_safety.py",
        '/usr/bin/strip -S "$bundle_root/Viventium.app/Contents/MacOS/ViventiumHelper"',
        '/usr/bin/strip -S "$bundle_root/ViventiumBootstrap.app/Contents/MacOS/ViventiumBootstrap"',
        '/usr/bin/codesign --force --sign - "$bundle_root/Viventium.app/Contents/MacOS/ViventiumHelper"',
        '/usr/bin/codesign --force --sign - "$bundle_root/ViventiumBootstrap.app/Contents/MacOS/ViventiumBootstrap"',
        '/usr/bin/codesign --force --sign - "$candidate_root/payload/apps/Viventium.app"',
        '/usr/bin/codesign --force --sign - "$candidate_root/bootstrap/ViventiumBootstrap.app"',
        '/usr/bin/codesign --verify --strict --verbose=2 "$candidate_root/payload/apps/Viventium.app"',
        '/usr/bin/codesign --verify --strict --verbose=2 "$candidate_root/bootstrap/ViventiumBootstrap.app"',
        'env PYTHONDONTWRITEBYTECODE=1 \\',
        '--forbid-prefix "$GITHUB_WORKSPACE"',
        '--forbid-prefix "$RUNNER_TEMP"',
        '--forbid-prefix "$HOME"',
        "viventium-native-install",
        "viventium-native-health",
        "native-payload-root-${{ matrix.expected_arch }}",
        "native-runtime.env",
        "scheduling_cortex",
        "-iTCP:3180",
        "login-after-restart.json",
        "confirm_password",
        "--cookie-jar",
        "?token=${first_admin_token}",
        "connected-accounts-config.json",
        "endpoints.json",
    ):
        assert required in workflow
    assert "macos-latest" not in workflow
    assert "curl |" not in workflow
    assert "actions/checkout@v" not in workflow
    assert 'python-version: "3.12"' in workflow
    assert "Record hosted Python toolchain" in workflow
    assert "python -VV" in workflow
    assert "glasshive:\n              enabled: false" in workflow
    assert "glasshive: { enabled: false }" not in workflow
    assert "VIVENTIUM_LOCAL_SUBSCRIPTION_AUTH=true" not in workflow
    assert '/bin/cp -R "${RUNNER_TEMP}/components/python"' not in workflow
    assert '"token": sys.argv[1]' not in workflow
    completed_bundle_step = workflow.index('candidate_root="$GITHUB_WORKSPACE/dist/candidate"')
    completed_bundle_workflow = workflow[completed_bundle_step:]
    assert completed_bundle_workflow.index("--self-check --candidate") < completed_bundle_workflow.index(
        '/usr/bin/codesign --force --sign - "$candidate_root/bootstrap/ViventiumBootstrap.app"'
    )
    assert completed_bundle_workflow.index(
        '/usr/bin/codesign --force --sign - "$candidate_root/bootstrap/ViventiumBootstrap.app"'
    ) < completed_bundle_workflow.index("verify_native_public_safety.py")
    smoke_step = workflow.index("Run target-like install and health smoke without build tools")
    upload_step = workflow.index("Upload exact candidate transport")
    assert "verify_native_public_safety.py" in workflow[smoke_step:upload_step]


def test_native_entrypoints_never_write_python_bytecode_into_the_immutable_payload() -> None:
    source = NATIVE_ENTRYPOINT.read_text(encoding="utf-8")
    assert '"$release_root/runtime/python/bin/python3" -E -s -B \\' in source
    assert "unset PYTHONHOME PYTHONPATH PYTHONSTARTUP PYTHONUSERBASE" in source
    assert "export PYTHONNOUSERSITE=1" in source


def test_native_python_isolation_ignores_pythonpath_and_user_site_startup(tmp_path: Path) -> None:
    injected = tmp_path / "injected"
    marker = tmp_path / "injected-marker"
    file(
        injected / "sitecustomize.py",
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('injected')\n",
    )
    home = tmp_path / "home"
    user_site = (
        home
        / "Library"
        / "Python"
        / f"{sys.version_info.major}.{sys.version_info.minor}"
        / "lib"
        / "python"
        / "site-packages"
    )
    file(
        user_site / "usercustomize.py",
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('user-injected')\n",
    )
    completed = subprocess.run(
        [sys.executable, "-E", "-s", "-B", "-c", "print('ISOLATED')"],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "HOME": str(home),
            "PYTHONPATH": str(injected),
            "PYTHONUSERBASE": str(home / "Library" / "Python"),
        },
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ISOLATED"
    assert not marker.exists()


def test_native_release_selects_payload_archive_from_verified_manifest_and_installs_it() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert workflow.count("verify_native_public_safety.py") >= 2
    assert "/usr/bin/diff -qr" in workflow
    assert "candidate/payload/runtime/python" in workflow
    assert "candidate/bootstrap/ViventiumBootstrap.app/Contents/Resources/runtime/python" in workflow
    assert "payload[\"artifact\"][\"filename\"]" in workflow
    assert "-name '*.zip'" not in workflow
    assert "viventium-native-install" in workflow
    assert "--app-support-dir" in workflow
    assert '"$matching_release/bin/viventium-native-install"' in workflow
    assert '"$matching_release/bin/viventium-native-health"' in workflow
    assert "__viventium_native_health" in workflow


def test_native_bootstrap_activation_health_owns_full_install_start_and_rollback() -> None:
    source = NATIVE_INSTALLER.read_text(encoding="utf-8")
    activation = source[source.index("activate_candidate(") :]
    assert "transactional_health" in source
    assert "--app-support-dir" in source
    assert "restart_prior_release" in source
    assert "current_data_schema=" in source
    assert "active / \"bin\" / \"viventium-native-install\"" not in activation


def test_native_bootstrap_rejects_non_https_and_credentialed_release_urls_before_open(
    monkeypatch, tmp_path: Path
) -> None:
    installer = load_native_installer(monkeypatch)
    called = False

    def forbidden_open(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("unsafe URL must be rejected before opening")

    monkeypatch.setattr(installer.urllib.request, "urlopen", forbidden_open)
    unsafe = (
        "file:///etc/passwd",
        "http://example.test/release.zip",
        "https://user:password@example.test/release.zip",
        "https://example.test:8443/release.zip",
        "https://example.test/release.zip#fragment",
    )
    for index, url in enumerate(unsafe):
        with pytest.raises(installer.BootstrapError, match="HTTPS release URL"):
            installer.download(url, tmp_path / f"asset-{index}", 1024)
    assert called is False


def test_native_bootstrap_validates_every_redirect_before_following(monkeypatch) -> None:
    installer = load_native_installer(monkeypatch)
    handler = installer.ValidatedHTTPSRedirectHandler()
    request = installer.urllib.request.Request("https://example.test/release.zip")
    parent_called = False

    def parent_redirect(_self, *_args, **_kwargs):
        nonlocal parent_called
        parent_called = True
        return object()

    monkeypatch.setattr(
        installer.urllib.request.HTTPRedirectHandler,
        "redirect_request",
        parent_redirect,
    )
    unsafe_redirects = (
        "http://example.test/release.zip",
        "https://user:password@example.test/release.zip",
        "https://example.test:8443/release.zip",
        "https://example.test/release.zip#fragment",
    )
    for redirected_url in unsafe_redirects:
        with pytest.raises(installer.BootstrapError, match="HTTPS release URL"):
            handler.redirect_request(request, None, 302, "Found", {}, redirected_url)
    assert parent_called is False

    result = handler.redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://downloads.example.test/release.zip",
    )
    assert parent_called is True
    assert result is not None


def test_native_semantic_health_refuses_non_loopback_urls_before_open(monkeypatch) -> None:
    runtime = load_native_runtime()
    called = False

    def forbidden_open(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("unsafe semantic URL must be rejected before opening")

    monkeypatch.setattr(runtime.urllib.request, "urlopen", forbidden_open)
    for url in (
        "file:///etc/passwd",
        "http://localhost:3190/health",
        "http://127.0.0.1:9999/health",
        "http://user:password@127.0.0.1:3190/health",
        "https://127.0.0.1:3190/health",
    ):
        assert runtime.semantic_http_ready(url) is False
    assert called is False


def test_native_semantic_health_verifies_exact_isolated_sandpack_index(monkeypatch) -> None:
    runtime = load_native_runtime()
    body = b'<script>window._env_={IS_ONPREM:"true"}</script>'

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit=-1):
            return body

    monkeypatch.setattr(runtime.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    digest = hashlib.sha256(body).hexdigest()

    assert runtime.semantic_http_ready(
        "http://127.0.0.1:3191/index.html", expected_sha256=digest
    )
    assert not runtime.semantic_http_ready("http://127.0.0.1:3191/index.html")
    assert not runtime.semantic_http_ready(
        "http://127.0.0.1:3191/", expected_sha256=digest
    )
    assert not runtime.semantic_http_ready(
        "http://127.0.0.1:3191/index.html", expected_sha256="0" * 64
    )


def test_native_runtime_uses_canonical_config_stable_auth_and_identity_health() -> None:
    source = NATIVE_RUNTIME.read_text(encoding="utf-8")
    proxy = NATIVE_PROXY.read_text(encoding="utf-8")
    assert '"CONFIG_PATH": str(root / "runtime" / "defaults" / "librechat.yaml")' in source
    assert '"VIVENTIUM_LOCAL_SUBSCRIPTION_AUTH": "true"' not in source
    assert '"VIVENTIUM_BOOTSTRAP_REGISTRATION_ONCE": "true"' in source
    assert "VIVENTIUM_OPENAI_LOCAL_CALLBACK_MANUAL_ONLY" not in source
    assert "wait_port(" not in source
    assert "wait_owned_service" in source
    assert "__viventium_native_health" in source
    assert "__viventium_native_health" in proxy
    assert "VIVENTIUM_NATIVE_RELEASE_ID" in proxy
    assert "VIVENTIUM_NATIVE_API_SOCKET" in source
    assert "VIVENTIUM_NATIVE_PROXY_TARGET_SOCKET" in source
    assert "VIVENTIUM_NATIVE_PROXY_TARGET_SOCKET" in proxy
    assert "VIVENTIUM_NATIVE_PROXY_TARGET_PORT" not in source
    assert "VIVENTIUM_NATIVE_PROXY_TARGET_PORT" not in proxy
    assert "socketPath: targetSocket" in proxy
    assert "net.connect({path: targetSocket}" in proxy
    assert '"librechat": 3180' not in source
    assert '"SANDPACK_BUNDLER_URL": "http://127.0.0.1:3191/"' in source
    assert '"SANDPACK_STATIC_BUNDLER_URL": "http://127.0.0.1:3191/"' in source
    assert '"VIVENTIUM_NATIVE_SANDPACK_LISTEN_PORT": "3191"' in source
    assert '"VIVENTIUM_NATIVE_SANDPACK_INDEX_SHA256": sandpack_index_sha256' in source
    assert '"VIVENTIUM_NATIVE_SANDPACK_ROOT": str(' in source
    assert "VIVENTIUM_NATIVE_SANDPACK_ROOT" in proxy
    assert "VIVENTIUM_NATIVE_SANDPACK_LISTEN_PORT" in proxy
    assert "127.0.0.1" in proxy
    assert "IS_ONPREM" in proxy
    assert "viventium-reconcile-user-defaults.js" in source
    assert "viventium-seed-agents.js" in source
    assert "--owner-id=" in source
    assert "agent-managed-baseline.json" in source
    assert "verify_default_agent" in source


def test_native_payload_cli_matches_helper_and_lifecycle_contract(tmp_path: Path) -> None:
    inputs = fixture_inputs(tmp_path)
    output = tmp_path / "candidate"
    completed = run_assembler(tmp_path, inputs, output)
    assert completed.returncode == 0, completed.stderr
    payload = output / "payload"
    cli = (payload / "bin" / "viventium").read_text(encoding="utf-8")
    for command in (
        "launch",
        "start",
        "stop",
        "status",
        "doctor",
        "password-reset-link",
        "snapshot",
        "restore",
        "uninstall",
    ):
        assert command in cli
    for unavailable in ("configure", "upgrade"):
        assert f"|{unavailable}|" not in cli
        assert f"|{unavailable}}}" not in cli
    assert "viventium-native-start" in cli
    assert "viventium-native-$command_name" in cli


def test_native_helper_offers_only_the_implemented_native_continuity_actions() -> None:
    source = HELPER_SWIFT.read_text(encoding="utf-8")
    native_menu = source.split("if self.controller.nativeRuntimeMode {", 1)[1].split("} else {", 1)[0]
    assert "Check for Signed Updates" not in native_menu
    assert "createBackupSnapshot" in native_menu
    assert "restoreNativeSnapshot" in native_menu
    assert "configure" not in native_menu.lower()
    assert "Install updates with a new signed Viventium Bootstrap" in native_menu
    assert 'arguments: ["restore", snapshotPath]' in source
    assert 'logFileName: "helper-restore.log"' in source
    assert 'manager.fileExists(atPath: "\\(repoRoot)/bin/viventium-native-start")' in source
    assert 'process.arguments = ["\\(repoRoot)/bin/viventium"] + arguments' in source
    assert 'environment["VIVENTIUM_APP_SUPPORT_DIR"] = appSupportDir' in source


def test_native_password_reset_link_uses_only_bundled_runtime_and_local_mongo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    root = tmp_path / "release"
    support = tmp_path / "support"
    node = executable(root / "runtime" / "node" / "bin" / "node")
    script = file(root / "runtime" / "librechat" / "config" / "issue-password-reset-link.js")
    file(
        support / "state" / "native-runtime.json",
        json.dumps({"schema_version": 1, "release_root": str(root), "installed_at": 1, "local_qa": True}),
    ).chmod(0o600)
    captured: dict[str, object] = {}

    monkeypatch.setattr(runtime, "release_root", lambda: root)
    monkeypatch.setattr(runtime, "packaged_health", lambda _root: None)
    monkeypatch.setattr(
        runtime, "start", lambda _args, **_kwargs: captured.setdefault("started", True)
    )
    monkeypatch.setattr(
        runtime,
        "native_child_environment",
        lambda _support: {"HOME": "/synthetic-home", "PATH": "/usr/bin:/bin"},
    )
    monkeypatch.setattr(runtime, "runtime_secrets", lambda _support: {"CREDS_KEY": "a" * 32, "CREDS_IV": "b" * 32})
    monkeypatch.setattr(runtime, "require_owned_service", lambda *_args: 4242)

    def run(command, **kwargs):
        captured["command"] = command
        captured["cwd"] = kwargs["cwd"]
        captured["env"] = kwargs["env"]
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(runtime.subprocess, "run", run)
    args = type("Args", (), {"app_support_dir": support, "email": "new-user@example.com", "timeout": 3.0})()

    runtime.password_reset_link(args)

    assert captured["started"] is True
    assert captured["command"] == [str(node), str(script), "--email", "new-user@example.com"]
    assert captured["cwd"] == root / "runtime" / "librechat"
    environment = captured["env"]
    assert environment["MONGO_URI"] == runtime.mongodb_uri(support)
    assert environment["DOMAIN_CLIENT"] == "http://127.0.0.1:3190"
    assert environment["PATH"] == "/usr/bin:/bin"
    assert "OPENAI_API_KEY" not in environment


def test_native_password_reset_link_fails_closed_when_bundled_helper_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    root = tmp_path / "release"
    support = tmp_path / "support"
    file(
        support / "state" / "native-runtime.json",
        json.dumps({"schema_version": 1, "release_root": str(root), "installed_at": 1, "local_qa": True}),
    ).chmod(0o600)
    monkeypatch.setattr(runtime, "release_root", lambda: root)
    monkeypatch.setattr(runtime, "packaged_health", lambda _root: None)

    args = type("Args", (), {"app_support_dir": support, "email": "new-user@example.com", "timeout": 3.0})()
    with pytest.raises(runtime.RuntimeError_, match="password-reset helper"):
        runtime.password_reset_link(args)


def test_native_schema_refuses_unknown_existing_data_and_checkpoints_before_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    root = tmp_path / "release"
    file(
        root / "release-metadata" / "build.json",
        json.dumps({"data_schema": {"minimum": 1, "maximum": 2, "target": 2}, "source_commit": "a" * 40}),
    )
    monkeypatch.setattr(runtime, "release_root", lambda: root)
    support = tmp_path / "support"
    file(support / "data" / "mongodb" / "collection.wt", "existing\n")
    with pytest.raises(runtime.RuntimeError_, match="schema is unknown"):
        runtime.inspect_data_schema(support, root)

    schema_state = file(
        support / "state" / "native-data-schema.json",
        json.dumps({"schema_version": 1, "current": 1}),
    )
    schema_state.chmod(0o600)
    with pytest.raises(runtime.RuntimeError_, match="migration implementation"):
        runtime.prepare_data_schema(support, root)
    checkpoints = list((support / "backups").glob("native-pre-migration-*"))
    assert len(checkpoints) == 1
    assert (checkpoints[0] / "checkpoint.json").is_file()


def test_native_install_refuses_established_source_app_support_without_mutation(tmp_path: Path) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    source_env = file(
        support / "runtime" / "runtime.env",
        "VIVENTIUM_RUNTIME_PROFILE=isolated\n",
    )
    original = source_env.read_bytes()

    with pytest.raises(runtime.RuntimeError_, match="source/Docker"):
        runtime.refuse_cross_mode_install(support)

    assert source_env.read_bytes() == original
    assert not (support / "state" / "native-runtime.json").exists()


def test_native_runtime_env_parser_rejects_secrets_paths_placeholders_and_wrong_ports(
    tmp_path: Path,
) -> None:
    runtime = load_native_runtime()
    valid = file(
        tmp_path / "native-runtime.env",
        "VIVENTIUM_RUNTIME_PROFILE=native\n"
        "VIVENTIUM_INSTALL_MODE=native\n"
        "VIVENTIUM_INSTALL_EXPERIENCE=express\n"
        "VIVENTIUM_CONNECTED_ACCOUNTS_ENABLED=true\n"
        "OPENAI_API_KEY=user_provided\n"
        "ANTHROPIC_API_KEY=user_provided\n"
        "GROQ_API_KEY=user_provided\n"
        "XAI_API_KEY=user_provided\n"
        "VIVENTIUM_LC_API_PORT=3180\n"
        "VIVENTIUM_LC_FRONTEND_PORT=3190\n"
        "VIVENTIUM_PLAYGROUND_PORT=3300\n"
        "SANDPACK_BUNDLER_URL=http://127.0.0.1:3191/\n"
        "SANDPACK_STATIC_BUNDLER_URL=http://127.0.0.1:3191/\n"
        "VIVENTIUM_MAIN_AGENT_ID=agent_viventium_main_fixture\n"
        "VIVENTIUM_MEMORY_HARDENING_SCHEDULE='0 3 * * *'\n"
        "START_SCHEDULING_MCP=false\n",
    )

    parsed = runtime.load_native_runtime_env(valid)
    assert parsed["VIVENTIUM_MEMORY_HARDENING_SCHEDULE"] == "0 3 * * *"

    forbidden = {
        "secret": "OPENAI_API_KEY=must-not-load\n",
        "path": "VIVENTIUM_PROMPT_BUNDLE_PATH=/path/to/build/prompt.json\n",
        "placeholder": "VIVENTIUM_REMOTE_VALUE='${UNRESOLVED}'\n",
        "port": "VIVENTIUM_LC_API_PORT=9999\n",
    }
    original = valid.read_text(encoding="utf-8")
    for label, addition in forbidden.items():
        candidate = file(tmp_path / f"{label}.env", original + addition)
        with pytest.raises(runtime.RuntimeError_, match="Native runtime environment"):
            runtime.load_native_runtime_env(candidate)


def test_native_child_environment_does_not_inherit_host_provider_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    file(
        support / "runtime" / "runtime.env",
        "VIVENTIUM_RUNTIME_PROFILE=native\n"
        "VIVENTIUM_INSTALL_MODE=native\n"
        "VIVENTIUM_INSTALL_EXPERIENCE=express\n"
        "VIVENTIUM_CONNECTED_ACCOUNTS_ENABLED=true\n"
        "OPENAI_API_KEY=user_provided\n"
        "ANTHROPIC_API_KEY=user_provided\n"
        "GROQ_API_KEY=user_provided\n"
        "XAI_API_KEY=user_provided\n"
        "VIVENTIUM_LC_API_PORT=3180\n"
        "VIVENTIUM_LC_FRONTEND_PORT=3190\n"
        "VIVENTIUM_PLAYGROUND_PORT=3300\n"
        "SANDPACK_BUNDLER_URL=http://127.0.0.1:3191/\n"
        "SANDPACK_STATIC_BUNDLER_URL=http://127.0.0.1:3191/\n",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "host-secret-must-not-cross-boundary")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "host-secret-must-not-cross-boundary")

    child = runtime.native_child_environment(support)

    assert child["OPENAI_API_KEY"] == "user_provided"
    assert child["ANTHROPIC_API_KEY"] == "user_provided"
    assert child["GROQ_API_KEY"] == "user_provided"
    assert child["XAI_API_KEY"] == "user_provided"
    assert child["VIVENTIUM_RUNTIME_PROFILE"] == "native"
    assert child["VIVENTIUM_CONNECTED_ACCOUNTS_ENABLED"] == "true"
    assert child["TMPDIR"] == str(support / "runtime" / "tmp")
    assert child["LANG"] == "en_US.UTF-8"


def test_first_admin_proxy_closes_replay_and_reopens_definite_upstream_error() -> None:
    source = NATIVE_PROXY.read_text(encoding="utf-8")
    assert "timingSafeEqual" in source
    assert "request.headers.origin !== allowedOrigin" in source
    assert "writeFirstAdmin({schema_version: 1, status: 'pending'" in source
    assert "writeFirstAdmin(state);" in source
    assert "VIVENTIUM_NATIVE_REGISTRATION_CLOSE_HOOK" in source
    assert "reloadClosedRegistration" in source
    assert "already been used or is invalid" in source
    assert "/login?redirect_to=%2Fc%2Fnew%3Fsetup%3Daccounts" in source
    assert "/login?setup=accounts" not in source
    assert "connect-src 'self'" in source
    assert "HttpOnly; SameSite=Strict" in source
    assert "function firstAdminCookie" in source
    assert "requestURL.pathname === '/register'" in source
    assert (
        "location.href='/login?redirect_to=%2Fc%2Fnew%3Fsetup%3Daccounts'"
        in source
    )
    assert ".catch(() =>" in source
    assert "x.token=" not in source
    assert 'name="confirm_password"' in source
    assert "submitted.confirm_password !== submitted.password" in source
    assert "confirm_password: submitted.confirm_password" in source


def test_first_admin_recovery_uses_the_driver_available_through_pruned_mongoose(
    tmp_path: Path,
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is unavailable")
    librechat = tmp_path / "LibreChat"
    file(librechat / "package.json", '{"private":true}\n')
    file(
        librechat / "node_modules" / "mongoose" / "package.json",
        '{"name":"mongoose","version":"8.24.1","main":"index.js"}\n',
    )
    file(
        librechat / "node_modules" / "mongoose" / "index.js",
        """
class MongoClient {
  async connect() {}
  db() {
    return {collection: () => ({countDocuments: async () => 0})};
  }
  async close() {}
}
module.exports = {mongo: {MongoClient}};
""".lstrip(),
    )
    state = tmp_path / "native-first-admin.json"

    completed = subprocess.run(
        [
            node,
            str(NATIVE_FIRST_ADMIN_RECOVERY),
            str(state),
            str(librechat),
            "mongodb://127.0.0.1:27017/LibreChat",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    recovered = json.loads(state.read_text(encoding="utf-8"))
    assert recovered["schema_version"] == 1
    assert recovered["status"] == "open"
    assert len(recovered["token"]) == 64


def test_first_admin_recovery_resolves_one_real_admin_id_without_storing_email(
    tmp_path: Path,
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is unavailable")
    librechat = tmp_path / "LibreChat"
    file(librechat / "package.json", '{"private":true}\n')
    file(
        librechat / "node_modules" / "mongoose" / "package.json",
        '{"name":"mongoose","version":"8.24.1","main":"index.js"}\n',
    )
    file(
        librechat / "node_modules" / "mongoose" / "index.js",
        """
class MongoClient {
  async connect() {}
  db() {
    return {collection: () => ({
      countDocuments: async () => 1,
      find: () => ({limit: () => ({toArray: async () => [{_id: '0123456789abcdef01234567'}]})}),
    })};
  }
  async close() {}
}
module.exports = {mongo: {MongoClient}};
""".lstrip(),
    )
    state = tmp_path / "native-first-admin.json"

    completed = subprocess.run(
        [
            node,
            str(NATIVE_FIRST_ADMIN_RECOVERY),
            str(state),
            str(librechat),
            "mongodb://127.0.0.1:27017/LibreChat",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    recovered = json.loads(state.read_text(encoding="utf-8"))
    assert recovered["status"] == "closed"
    assert recovered["admin_user_id"] == "0123456789abcdef01234567"
    assert "email" not in recovered


def test_first_admin_recovery_preserves_closed_owner_across_multi_admin_restart(
    tmp_path: Path,
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is unavailable")
    librechat = tmp_path / "LibreChat"
    file(librechat / "package.json", '{"private":true}\n')
    file(
        librechat / "node_modules" / "mongoose" / "package.json",
        '{"name":"mongoose","version":"8.24.1","main":"index.js"}\n',
    )
    file(
        librechat / "node_modules" / "mongoose" / "index.js",
        """
class ObjectId {
  constructor(value) { this.value = value; }
  toString() { return this.value; }
}
class MongoClient {
  async connect() {}
  db() {
    return {collection: () => ({
      countDocuments: async () => 2,
      findOne: async query => {
        if (String(query._id) !== '0123456789abcdef01234567') {
          throw new Error('recovery did not query the stored owner id');
        }
        return {_id: query._id, role: 'ADMIN', email: 'owner@example.test'};
      },
      find: () => { throw new Error('closed owner must not be re-inferred'); },
    })};
  }
  async close() {}
}
module.exports = {mongo: {MongoClient, ObjectId}};
""".lstrip(),
    )
    state = tmp_path / "native-first-admin.json"
    original = (
        '{"schema_version":1,"status":"closed",'
        '"admin_user_id":"0123456789abcdef01234567","reconciled_at":123}\n'
    )
    state.write_text(original, encoding="utf-8")
    state.chmod(0o600)

    completed = subprocess.run(
        [
            node,
            str(NATIVE_FIRST_ADMIN_RECOVERY),
            str(state),
            str(librechat),
            "mongodb://127.0.0.1:27017/LibreChat",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert state.read_text(encoding="utf-8") == original


def test_legacy_closed_owner_recovers_from_shipped_main_agent_without_admin_scan_or_db_writes(
    tmp_path: Path,
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is unavailable")
    librechat = tmp_path / "LibreChat"
    file(librechat / "package.json", '{"private":true}\n')
    file(
        librechat / "node_modules" / "mongoose" / "package.json",
        '{"name":"mongoose","version":"8.24.1","main":"index.js"}\n',
    )
    file(
        librechat / "node_modules" / "mongoose" / "index.js",
        """
class ObjectId {
  constructor(value) { this.value = value; }
  toString() { return this.value; }
}
const ownerId = '0123456789abcdef01234567';
class MongoClient {
  async connect() {}
  db() {
    return {collection: name => {
      if (name === 'users') return {
        countDocuments: async () => 2,
        findOne: async query => {
          if (String(query._id) !== ownerId || query.role !== 'ADMIN') {
            throw new Error('recovery did not verify the exact main-agent author');
          }
          if (query.email?.$ne !== 'viventium-system@example.com') {
            throw new Error('recovery omitted the non-placeholder owner filter');
          }
          return {_id: query._id, role: 'ADMIN', email: 'owner@example.test'};
        },
        find: () => { throw new Error('legacy recovery must not enumerate administrators'); },
        updateOne: async () => { throw new Error('legacy recovery must not mutate users'); },
      };
      if (name === 'agents') return {
        findOne: async query => {
          if (query.id !== 'agent_viventium_main_test') {
            throw new Error('recovery did not query the shipped main agent id');
          }
          return {id: query.id, author: ownerId};
        },
        updateOne: async () => { throw new Error('legacy recovery must not mutate agents'); },
      };
      if (name === 'aclentries') {
        throw new Error('legacy recovery must not read or mutate ACL entries');
      }
      throw new Error(`unexpected collection ${name}`);
    }};
  }
  async close() {}
}
module.exports = {mongo: {MongoClient, ObjectId}};
""".lstrip(),
    )
    file(
        librechat / "node_modules" / "js-yaml" / "package.json",
        '{"name":"js-yaml","version":"4.0.0","main":"index.js"}\n',
    )
    file(
        librechat / "node_modules" / "js-yaml" / "index.js",
        "module.exports = {JSON_SCHEMA: {}, load: JSON.parse};\n",
    )
    bundle = tmp_path / "viventium-agents.json"
    bundle.write_text(
        json.dumps(
            {
                "meta": {"mainAgentId": "agent_viventium_main_test"},
                "mainAgent": {"id": "agent_viventium_main_test"},
                "backgroundAgents": [],
            }
        ),
        encoding="utf-8",
    )
    state = tmp_path / "native-first-admin.json"
    state.write_text(
        '{"schema_version":1,"status":"closed","admin_created_at":123}\n',
        encoding="utf-8",
    )
    state.chmod(0o600)

    completed = subprocess.run(
        [
            node,
            str(NATIVE_FIRST_ADMIN_RECOVERY),
            str(state),
            str(librechat),
            "mongodb://127.0.0.1:27017/LibreChat",
            str(bundle),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    recovered = json.loads(state.read_text(encoding="utf-8"))
    assert recovered == {
        "schema_version": 1,
        "status": "closed",
        "admin_created_at": 123,
        "admin_user_id": "0123456789abcdef01234567",
        "reconciled_at": recovered["reconciled_at"],
    }
    assert isinstance(recovered["reconciled_at"], int)
    assert state.stat().st_mode & 0o777 == 0o600
    recovered_bytes = state.read_bytes()

    repeated = subprocess.run(
        completed.args,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert repeated.returncode == 0, repeated.stderr
    assert state.read_bytes() == recovered_bytes


@pytest.mark.parametrize("owner_status", ["deleted", "demoted"])
def test_first_admin_recovery_rejects_deleted_or_demoted_stored_owner(
    tmp_path: Path, owner_status: str
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is unavailable")
    librechat = tmp_path / "LibreChat"
    file(librechat / "package.json", '{"private":true}\n')
    file(
        librechat / "node_modules" / "mongoose" / "package.json",
        '{"name":"mongoose","version":"8.24.1","main":"index.js"}\n',
    )
    record = (
        "null"
        if owner_status == "deleted"
        else "{_id: query._id, role: 'USER', email: 'owner@example.test'}"
    )
    file(
        librechat / "node_modules" / "mongoose" / "index.js",
        f"""
class ObjectId {{
  constructor(value) {{ this.value = value; }}
  toString() {{ return this.value; }}
}}
class MongoClient {{
  async connect() {{}}
  db() {{
    return {{collection: () => ({{
      findOne: async query => {{
        if (String(query._id) !== '0123456789abcdef01234567') {{
          throw new Error('recovery did not query the stored owner id');
        }}
        if (query.role !== 'ADMIN' || query.email?.$ne !== 'viventium-system@example.com') {{
          throw new Error('recovery omitted the production administrator filters');
        }}
        const record = {record};
        if (!record || record.role !== query.role || record.email === query.email.$ne) return null;
        return record;
      }},
      find: () => {{ throw new Error('invalid stored owner must not be re-inferred'); }},
    }})}};
  }}
  async close() {{}}
}}
module.exports = {{mongo: {{MongoClient, ObjectId}}}};
""".lstrip(),
    )
    state = tmp_path / "native-first-admin.json"
    original = (
        '{"schema_version":1,"status":"closed",'
        '"admin_user_id":"0123456789abcdef01234567","reconciled_at":123}\n'
    )
    state.write_text(original, encoding="utf-8")
    state.chmod(0o600)

    completed = subprocess.run(
        [
            node,
            str(NATIVE_FIRST_ADMIN_RECOVERY),
            str(state),
            str(librechat),
            "mongodb://127.0.0.1:27017/LibreChat",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "no longer a valid local administrator" in completed.stderr
    assert "latest Viventium backup" in completed.stderr
    assert state.read_text(encoding="utf-8") == original


def test_first_admin_recovery_rejects_unsafe_existing_state_permissions(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is unavailable")
    librechat = tmp_path / "LibreChat"
    file(librechat / "package.json", '{"private":true}\n')
    file(
        librechat / "node_modules" / "mongoose" / "package.json",
        '{"name":"mongoose","version":"8.24.1","main":"index.js"}\n',
    )
    file(
        librechat / "node_modules" / "mongoose" / "index.js",
        """
class MongoClient {
  async connect() {}
  db() { return {collection: () => ({countDocuments: async () => 0})}; }
  async close() {}
}
module.exports = {mongo: {MongoClient}};
""".lstrip(),
    )
    state = tmp_path / "native-first-admin.json"
    original = '{"schema_version":1,"status":"closed","admin_user_id":"bad"}\n'
    state.write_text(original, encoding="utf-8")
    state.chmod(0o644)

    completed = subprocess.run(
        [
            node,
            str(NATIVE_FIRST_ADMIN_RECOVERY),
            str(state),
            str(librechat),
            "mongodb://127.0.0.1:27017/LibreChat",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "owner-owned mode 0600" in completed.stderr
    assert state.read_text(encoding="utf-8") == original

    state.chmod(0o600)
    invalid = subprocess.run(
        [
            node,
            str(NATIVE_FIRST_ADMIN_RECOVERY),
            str(state),
            str(librechat),
            "mongodb://127.0.0.1:27017/LibreChat",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert invalid.returncode != 0
    assert "latest Viventium backup" in invalid.stderr
    assert "protected owner state was not changed" in invalid.stderr
    assert state.read_text(encoding="utf-8") == original


def test_native_agent_verification_looks_up_the_exact_stored_owner(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is unavailable")
    librechat = tmp_path / "LibreChat"
    file(librechat / "package.json", '{"private":true}\n')
    file(
        librechat / "node_modules" / "mongodb" / "package.json",
        '{"name":"mongodb","version":"6.0.0","main":"index.js"}\n',
    )
    file(
        librechat / "node_modules" / "mongodb" / "index.js",
        """
class ObjectId {
  constructor(value) { this.value = value; }
  toString() { return this.value; }
}
const ownerId = '0123456789abcdef01234567';
const agentId = 'agent_viventium_main_test';
const agentResourceId = '111111111111111111111111';
const roleIds = {agent: '222222222222222222222222', remoteAgent: '333333333333333333333333'};
class MongoClient {
  async connect() {}
  db() {
    return {collection: name => {
      if (name === 'users') return {
        findOne: async query => {
          if (String(query._id) !== ownerId) throw new Error('verification did not query stored owner');
          return {_id: query._id, role: 'ADMIN', email: 'owner@example.test'};
        },
        find: () => { throw new Error('verification must not sample administrators'); },
      };
      if (name === 'agents') return {find: () => ({toArray: async () => [
        {_id: agentResourceId, id: agentId, author: ownerId},
      ]})};
      if (name === 'accessroles') return {find: () => ({toArray: async () => [
        {_id: roleIds.agent, resourceType: 'agent'},
        {_id: roleIds.remoteAgent, resourceType: 'remoteAgent'},
      ]})};
      if (name === 'aclentries') return {find: () => ({toArray: async () => [
        {resourceId: agentResourceId, resourceType: 'agent', roleId: roleIds.agent},
        {resourceId: agentResourceId, resourceType: 'remoteAgent', roleId: roleIds.remoteAgent},
      ]})};
      throw new Error(`unexpected collection ${name}`);
    }};
  }
  async close() {}
}
module.exports = {MongoClient, ObjectId};
""".lstrip(),
    )
    file(
        librechat / "node_modules" / "js-yaml" / "package.json",
        '{"name":"js-yaml","version":"4.0.0","main":"index.js"}\n',
    )
    file(
        librechat / "node_modules" / "js-yaml" / "index.js",
        "module.exports = {JSON_SCHEMA: {}, load: JSON.parse};\n",
    )
    bundle = tmp_path / "bundle.json"
    bundle.write_text(
        json.dumps(
            {
                "meta": {"mainAgentId": "agent_viventium_main_test"},
                "mainAgent": {"id": "agent_viventium_main_test"},
                "backgroundAgents": [],
            }
        ),
        encoding="utf-8",
    )
    baseline = tmp_path / "agent-managed-baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "bundle_sha256": "a" * 64,
                "agents": {
                    "agent_viventium_main_test": {"fields": {"instructions": "test"}}
                },
            }
        ),
        encoding="utf-8",
    )
    baseline.chmod(0o600)

    completed = subprocess.run(
        [
            node,
            str(NATIVE_VERIFY_AGENT),
            str(librechat),
            "mongodb://127.0.0.1:27017/LibreChat",
            str(bundle),
            "0123456789abcdef01234567",
            str(baseline),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["owner"] == "0123456789abcdef01234567"


@pytest.mark.parametrize("owner_status", ["deleted", "demoted"])
def test_native_agent_verification_rejects_deleted_or_demoted_exact_owner(
    tmp_path: Path, owner_status: str
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is unavailable")
    librechat = tmp_path / "LibreChat"
    file(librechat / "package.json", '{"private":true}\n')
    file(
        librechat / "node_modules" / "mongodb" / "package.json",
        '{"name":"mongodb","version":"6.0.0","main":"index.js"}\n',
    )
    record = (
        "null"
        if owner_status == "deleted"
        else "{_id: query._id, role: 'USER', email: 'owner@example.test'}"
    )
    file(
        librechat / "node_modules" / "mongodb" / "index.js",
        f"""
class ObjectId {{
  constructor(value) {{ this.value = value; }}
  toString() {{ return this.value; }}
}}
class MongoClient {{
  async connect() {{}}
  db() {{
    return {{collection: name => {{
      if (name !== 'users') throw new Error('verification continued after invalid owner');
      return {{findOne: async query => {{
        if (String(query._id) !== '0123456789abcdef01234567') {{
          throw new Error('verification did not query the stored owner id');
        }}
        if (query.role !== 'ADMIN' || query.email?.$ne !== 'viventium-system@example.com') {{
          throw new Error('verification omitted the production administrator filters');
        }}
        const record = {record};
        if (!record || record.role !== query.role || record.email === query.email.$ne) return null;
        return record;
      }}}};
    }}}};
  }}
  async close() {{}}
}}
module.exports = {{MongoClient, ObjectId}};
""".lstrip(),
    )
    file(
        librechat / "node_modules" / "js-yaml" / "package.json",
        '{"name":"js-yaml","version":"4.0.0","main":"index.js"}\n',
    )
    file(
        librechat / "node_modules" / "js-yaml" / "index.js",
        "module.exports = {JSON_SCHEMA: {}, load: JSON.parse};\n",
    )
    bundle = tmp_path / "bundle.json"
    bundle.write_text(
        json.dumps(
            {
                "meta": {"mainAgentId": "agent_viventium_main_test"},
                "mainAgent": {"id": "agent_viventium_main_test"},
                "backgroundAgents": [],
            }
        ),
        encoding="utf-8",
    )
    baseline = tmp_path / "agent-managed-baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "bundle_sha256": "a" * 64,
                "agents": {
                    "agent_viventium_main_test": {"fields": {"instructions": "test"}}
                },
            }
        ),
        encoding="utf-8",
    )
    baseline.chmod(0o600)

    completed = subprocess.run(
        [
            node,
            str(NATIVE_VERIFY_AGENT),
            str(librechat),
            "mongodb://127.0.0.1:27017/LibreChat",
            str(bundle),
            "0123456789abcdef01234567",
            str(baseline),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "not the verified local administrator" in completed.stderr
    assert "Restore or promote the recorded administrator" in completed.stderr


def test_first_admin_proxy_connection_error_allows_same_token_retry(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is unavailable")

    def free_port() -> int:
        with socket.socket() as handle:
            handle.bind(("127.0.0.1", 0))
            return int(handle.getsockname()[1])

    proxy_port = free_port()
    sandpack_port = free_port()
    state = tmp_path / "first-admin.json"
    token = "a" * 64
    state.write_text(json.dumps({"schema_version": 1, "status": "open", "token": token}) + "\n")
    state.chmod(0o600)
    short_root = Path(tempfile.mkdtemp(prefix="viventium-proxy-", dir="/private/tmp"))
    release_root = short_root / "release"
    sandpack_root, sandpack_digest = native_proxy_sandpack_fixture(release_root)
    app_support = short_root / "Viventium"
    runtime_dir = app_support / "runtime"
    runtime_dir.mkdir(parents=True)
    target_socket = runtime_dir / "librechat-api.sock"
    stale_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale_socket.bind(str(target_socket))
    stale_socket.close()
    target_socket.chmod(0o600)
    hook_called = tmp_path / "registration-close-called"
    hook = tmp_path / "registration-close-hook"
    hook.write_text(
        "#!/bin/sh\n"
        f"test \"$1\" = --app-support-dir && test \"$2\" = {str(app_support)!r}\n"
        f"/usr/bin/touch {str(hook_called)!r}\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    environment = {
        **os.environ,
        "VIVENTIUM_NATIVE_RELEASE_ID": "b" * 40,
        "VIVENTIUM_NATIVE_RELEASE_ROOT": str(release_root),
        "VIVENTIUM_NATIVE_FIRST_ADMIN_STATE": str(state),
        "VIVENTIUM_NATIVE_PROXY_TARGET_SOCKET": str(target_socket),
        "VIVENTIUM_NATIVE_PROXY_LISTEN_PORT": str(proxy_port),
        "VIVENTIUM_NATIVE_SANDPACK_LISTEN_PORT": str(sandpack_port),
        "VIVENTIUM_NATIVE_SANDPACK_ROOT": str(sandpack_root),
        "VIVENTIUM_NATIVE_SANDPACK_INDEX_SHA256": sandpack_digest,
        "VIVENTIUM_NATIVE_REGISTRATION_CLOSE_HOOK": str(hook),
        "VIVENTIUM_APP_SUPPORT_DIR": str(app_support),
    }
    proxy = subprocess.Popen(
        [node, str(NATIVE_PROXY)], env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
    )
    payload = json.dumps(
        {
            "email": "native-proxy-qa@example.com",
            "password": "Synthetic-QA-2026!",
            "confirm_password": "Synthetic-QA-2026!",
            "name": "Native QA",
        }
    ).encode()

    def request() -> int:
        value = urllib.request.Request(
            f"http://127.0.0.1:{proxy_port}/__viventium_native_first_admin",
            data=payload,
            headers={
                "Origin": "http://127.0.0.1:3190",
                "Content-Type": "application/json",
                "Cookie": f"viventium_native_first_admin={token}",
            },
        )
        try:
            with urllib.request.urlopen(value, timeout=3) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code

    forwarded_gets: list[str] = []

    class RegistrationHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            forwarded_gets.append(self.path)
            self.send_response(200)
            self.end_headers()

        def do_POST(self):
            self.send_response(201)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, _format, *args):
            return

    class UnixHTTPServer(HTTPServer):
        address_family = socket.AF_UNIX

    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{proxy_port}/__viventium_native_health", timeout=0.2
                ):
                    break
            except OSError:
                time.sleep(0.05)

        with urllib.request.urlopen(f"http://127.0.0.1:{sandpack_port}/", timeout=3) as response:
            assert response.status == 200
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert response.headers["Referrer-Policy"] == "no-referrer"
            assert response.headers["Content-Security-Policy"] == (
                "frame-ancestors http://127.0.0.1:3190"
            )
            assert b'IS_ONPREM:"true"' in response.read()
        with pytest.raises(urllib.error.HTTPError) as traversal:
            urllib.request.urlopen(
                f"http://127.0.0.1:{sandpack_port}/%2e%2e/%2e%2e/etc/passwd",
                timeout=3,
            )
        assert traversal.value.code in {403, 404}
        with pytest.raises(urllib.error.HTTPError) as method:
            urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{sandpack_port}/index.html",
                    data=b"not-allowed",
                    method="POST",
                ),
                timeout=3,
            )
        assert method.value.code == 405

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, request, fp, code, message, headers, new_url):
                return None

        opener = urllib.request.build_opener(NoRedirect)
        with pytest.raises(urllib.error.HTTPError) as hostile_host:
            opener.open(
                urllib.request.Request(
                    f"http://127.0.0.1:{proxy_port}/__viventium_native_health",
                    headers={"Host": "attacker.example"},
                ),
                timeout=3,
            )
        assert hostile_host.value.code == 421
        assert hostile_host.value.headers.get("Set-Cookie") is None

        with pytest.raises(urllib.error.HTTPError) as public_register:
            opener.open(f"http://127.0.0.1:{proxy_port}/register", timeout=3)
        assert public_register.value.code == 403
        assert public_register.value.headers.get("Set-Cookie") is None
        assert json.loads(state.read_text()) == {
            "schema_version": 1,
            "status": "open",
            "token": token,
        }

        with pytest.raises(urllib.error.HTTPError) as redirect:
            opener.open(
                f"http://127.0.0.1:{proxy_port}/__viventium_native_first_admin?token={token}",
                timeout=3,
            )
        assert redirect.value.code == 303
        assert redirect.value.headers["Location"] == "/__viventium_native_first_admin"
        cookie = redirect.value.headers["Set-Cookie"]
        assert cookie.startswith(f"viventium_native_first_admin={token};")
        assert "HttpOnly" in cookie
        assert "SameSite=Strict" in cookie
        clean_page_request = urllib.request.Request(
            f"http://127.0.0.1:{proxy_port}/__viventium_native_first_admin",
            headers={"Cookie": cookie.split(";", 1)[0]},
        )
        with urllib.request.urlopen(clean_page_request, timeout=3) as clean_page:
            page = clean_page.read().decode("utf-8")
            assert clean_page.status == 200
            assert "connect-src 'self'" in clean_page.headers["Content-Security-Policy"]
            assert 'name="confirm_password"' in page
            assert "/login?redirect_to=%2Fc%2Fnew%3Fsetup%3Daccounts" in page
            assert "/login?setup=accounts" not in page
            assert token not in page

        assert request() == 502
        assert json.loads(state.read_text()) == {"schema_version": 1, "status": "open", "token": token}

        target_socket.unlink()
        server = UnixHTTPServer(str(target_socket), RegistrationHandler)
        target_socket.chmod(0o600)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with pytest.raises(urllib.error.HTTPError) as hostile_proxy:
                opener.open(
                    urllib.request.Request(
                        f"http://127.0.0.1:{proxy_port}/api/config",
                        headers={"Host": "attacker.example"},
                    ),
                    timeout=3,
                )
            assert hostile_proxy.value.code == 421
            assert forwarded_gets == []
            assert request() == 201
        finally:
            server.shutdown()
            thread.join(timeout=3)
        closed = json.loads(state.read_text())
        assert closed["status"] == "closed"
        assert "token" not in closed
        assert hook_called.is_file()
        assert request() == 409
    finally:
        proxy.terminate()
        proxy.wait(timeout=5)
        shutil.rmtree(short_root)


def test_first_admin_proxy_hook_failure_stays_closed_and_returns_service_unavailable(
    tmp_path: Path,
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is unavailable")

    def free_port() -> int:
        with socket.socket() as handle:
            handle.bind(("127.0.0.1", 0))
            return int(handle.getsockname()[1])

    proxy_port = free_port()
    sandpack_port = free_port()
    token = "c" * 64
    state = file(
        tmp_path / "first-admin.json",
        json.dumps({"schema_version": 1, "status": "open", "token": token}) + "\n",
    )
    state.chmod(0o600)
    short_root = Path(tempfile.mkdtemp(prefix="viventium-proxy-", dir="/private/tmp"))
    release_root = short_root / "release"
    sandpack_root, sandpack_digest = native_proxy_sandpack_fixture(release_root)
    app_support = short_root / "Viventium"
    runtime_dir = app_support / "runtime"
    runtime_dir.mkdir(parents=True)
    target_socket = runtime_dir / "librechat-api.sock"
    hook = executable(tmp_path / "registration-close-hook", "#!/bin/sh\nexit 1\n")

    class RegistrationHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(201)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, _format, *args):
            return

    class UnixHTTPServer(HTTPServer):
        address_family = socket.AF_UNIX

    server = UnixHTTPServer(str(target_socket), RegistrationHandler)
    target_socket.chmod(0o600)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    proxy = subprocess.Popen(
        [node, str(NATIVE_PROXY)],
        env={
            **os.environ,
            "VIVENTIUM_NATIVE_RELEASE_ID": "d" * 40,
            "VIVENTIUM_NATIVE_RELEASE_ROOT": str(release_root),
            "VIVENTIUM_NATIVE_FIRST_ADMIN_STATE": str(state),
            "VIVENTIUM_NATIVE_PROXY_TARGET_SOCKET": str(target_socket),
            "VIVENTIUM_NATIVE_PROXY_LISTEN_PORT": str(proxy_port),
            "VIVENTIUM_NATIVE_SANDPACK_LISTEN_PORT": str(sandpack_port),
            "VIVENTIUM_NATIVE_SANDPACK_ROOT": str(sandpack_root),
            "VIVENTIUM_NATIVE_SANDPACK_INDEX_SHA256": sandpack_digest,
            "VIVENTIUM_NATIVE_REGISTRATION_CLOSE_HOOK": str(hook),
            "VIVENTIUM_APP_SUPPORT_DIR": str(app_support),
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    request = urllib.request.Request(
        f"http://127.0.0.1:{proxy_port}/__viventium_native_first_admin",
        data=json.dumps(
            {
                "email": "native-proxy-hook-qa@example.com",
                "password": "Synthetic-QA-2026!",
                "confirm_password": "Synthetic-QA-2026!",
                "name": "Native Hook QA",
            }
        ).encode(),
        headers={
            "Origin": "http://127.0.0.1:3190",
            "Content-Type": "application/json",
            "Cookie": f"viventium_native_first_admin={token}",
        },
    )
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{proxy_port}/__viventium_native_health", timeout=0.2
                ):
                    break
            except OSError:
                time.sleep(0.05)
        with pytest.raises(urllib.error.HTTPError) as response:
            urllib.request.urlopen(request, timeout=5)
        assert response.value.code == 503
        closed = json.loads(state.read_text(encoding="utf-8"))
        assert closed["status"] == "closed"
        assert "token" not in closed
    finally:
        proxy.terminate()
        proxy.wait(timeout=5)
        server.shutdown()
        thread.join(timeout=3)
        shutil.rmtree(short_root)


def test_native_proxy_never_forwards_to_obsolete_or_foreign_tcp_target(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is unavailable")

    def free_port() -> int:
        with socket.socket() as handle:
            handle.bind(("127.0.0.1", 0))
            return int(handle.getsockname()[1])

    class ForeignHandler(BaseHTTPRequestHandler):
        requests = 0

        def do_GET(self):
            type(self).requests += 1
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"foreign")

        def log_message(self, _format, *args):
            return

    foreign_port = free_port()
    proxy_port = free_port()
    sandpack_port = free_port()
    foreign = HTTPServer(("127.0.0.1", foreign_port), ForeignHandler)
    foreign_thread = threading.Thread(target=foreign.serve_forever, daemon=True)
    foreign_thread.start()

    short_root = Path(tempfile.mkdtemp(prefix="viventium-proxy-", dir="/private/tmp"))
    release_root = short_root / "release"
    sandpack_root, sandpack_digest = native_proxy_sandpack_fixture(release_root)
    app_support = short_root / "Viventium"
    runtime_dir = app_support / "runtime"
    runtime_dir.mkdir(parents=True)
    target_socket = runtime_dir / "librechat-api.sock"
    stale_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale_socket.bind(str(target_socket))
    stale_socket.close()
    target_socket.chmod(0o600)
    state = file(
        app_support / "state" / "native-first-admin.json",
        json.dumps({"schema_version": 1, "status": "closed"}) + "\n",
    )
    state.chmod(0o600)
    hook = executable(tmp_path / "registration-close-hook", "#!/bin/sh\nexit 0\n")
    proxy = subprocess.Popen(
        [node, str(NATIVE_PROXY)],
        env={
            **os.environ,
            "VIVENTIUM_NATIVE_RELEASE_ID": "e" * 40,
            "VIVENTIUM_NATIVE_RELEASE_ROOT": str(release_root),
            "VIVENTIUM_NATIVE_FIRST_ADMIN_STATE": str(state),
            "VIVENTIUM_NATIVE_PROXY_TARGET_SOCKET": str(target_socket),
            # A foreign listener may acquire the former Native API port. This
            # compatibility-looking variable must never influence routing.
            "VIVENTIUM_NATIVE_PROXY_TARGET_PORT": str(foreign_port),
            "VIVENTIUM_NATIVE_PROXY_LISTEN_PORT": str(proxy_port),
            "VIVENTIUM_NATIVE_SANDPACK_LISTEN_PORT": str(sandpack_port),
            "VIVENTIUM_NATIVE_SANDPACK_ROOT": str(sandpack_root),
            "VIVENTIUM_NATIVE_SANDPACK_INDEX_SHA256": sandpack_digest,
            "VIVENTIUM_NATIVE_REGISTRATION_CLOSE_HOOK": str(hook),
            "VIVENTIUM_APP_SUPPORT_DIR": str(app_support),
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 5
        response_code = None
        while time.monotonic() < deadline:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{proxy_port}/api/config", timeout=0.2)
            except urllib.error.HTTPError as error:
                response_code = error.code
                break
            except OSError:
                time.sleep(0.05)
        assert response_code == 502
        assert ForeignHandler.requests == 0
    finally:
        proxy.terminate()
        proxy.wait(timeout=5)
        foreign.shutdown()
        foreign.server_close()
        foreign_thread.join(timeout=3)
        shutil.rmtree(short_root)


def test_native_runtime_identifies_exact_unix_socket_owner_with_system_lsof() -> None:
    runtime = load_native_runtime()
    short_root = Path(tempfile.mkdtemp(prefix="viventium-lsof-", dir="/private/tmp"))
    support = short_root / "Viventium"
    (support / "runtime").mkdir(parents=True)
    target_socket = runtime.native_api_socket_path(support)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        listener.bind(str(target_socket))
        target_socket.chmod(0o600)
        listener.listen()
        assert os.getpid() in runtime.unix_socket_pids(target_socket)
        assert runtime.api_socket_metadata(support) is not None
    finally:
        listener.close()
        shutil.rmtree(short_root)


def test_native_runtime_treats_an_absent_unix_socket_as_unowned(tmp_path: Path) -> None:
    runtime = load_native_runtime()

    assert runtime.unix_socket_pids(tmp_path / "absent.sock") == set()


def test_native_runtime_rejects_overlong_private_socket_paths_before_launch(monkeypatch) -> None:
    runtime = load_native_runtime()
    monkeypatch.setattr(runtime.sys, "platform", "darwin")
    support = Path("/private/tmp") / ("v" * 100)

    with pytest.raises(runtime.RuntimeError_, match="too long for private service sockets"):
        runtime.validate_native_socket_lengths(support)


def test_native_runtime_semantically_probes_private_api_socket() -> None:
    runtime = load_native_runtime()
    short_root = Path(tempfile.mkdtemp(prefix="viventium-api-health-", dir="/private/tmp"))
    target_socket = short_root / "api.sock"

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/api/health" else 503)
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, _format, *args):
            return

    class UnixHTTPServer(HTTPServer):
        address_family = socket.AF_UNIX

    server = UnixHTTPServer(str(target_socket), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assert runtime.semantic_unix_http_ready(target_socket, "/api/health") is True
        assert runtime.semantic_unix_http_ready(target_socket, "/broken") is False
        assert runtime.semantic_unix_http_ready(target_socket, "/api/health\r\nX-Test: bad") is False
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        shutil.rmtree(short_root)


def test_registration_close_stops_backend_before_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    state = file(
        support / "state" / "native-first-admin.json",
        json.dumps({"schema_version": 1, "status": "closed"}) + "\n",
    )
    state.chmod(0o600)
    root = tmp_path / "release"
    runtime_state = file(
        support / "state" / "native-runtime.json",
        json.dumps(
            {
                "schema_version": 1,
                "release_root": str(root),
                "installed_at": 1,
                "local_qa": True,
            }
        ),
    )
    runtime_state.chmod(0o600)
    calls: list[str] = []
    monkeypatch.setattr(runtime, "release_root", lambda: root)
    monkeypatch.setattr(
        runtime,
        "stop_service",
        lambda service, actual_support, actual_root: calls.append(
            f"stop:{service}:{actual_support == support}:{actual_root == root}"
        ),
    )
    monkeypatch.setattr(runtime, "start", lambda _args, **_kwargs: calls.append("start"))

    runtime.registration_close(
        type("Args", (), {"app_support_dir": support, "timeout": 1.0})()
    )

    assert calls == ["stop:librechat:True:True", "start"]


def test_native_identity_seed_waits_for_real_first_admin_and_preserves_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = load_native_runtime()
    root = tmp_path / "release"
    support = tmp_path / "support"
    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        runtime,
        "run_native_maintenance",
        lambda label, command, _support, **_kwargs: calls.append((label, command)),
    )
    monkeypatch.setattr(
        runtime,
        "verify_default_agent",
        lambda _root, _support, _env: calls.append(("verify-default-agent", [])),
    )

    runtime.maintain_native_identity(
        root,
        support,
        {},
        {"schema_version": 1, "status": "open", "token": "a" * 64},
    )
    assert calls == []

    with pytest.raises(runtime.RuntimeError_, match="administrator identity"):
        runtime.maintain_native_identity(
            root,
            support,
            {},
            {"schema_version": 1, "status": "closed"},
        )

    runtime.maintain_native_identity(
        root,
        support,
        {},
        {
            "schema_version": 1,
            "status": "closed",
            "admin_user_id": "0123456789abcdef01234567",
        },
    )
    assert [label for label, _command in calls] == [
        "user-default-reconciliation",
        "default-agent-seed",
        "verify-default-agent",
    ]
    seed_command = next(command for label, command in calls if label == "default-agent-seed")
    assert "--owner-id=0123456789abcdef01234567" in seed_command
    assert f"--managed-baseline={support / 'state' / 'agent-managed-baseline.json'}" in seed_command
    assert not any(argument.startswith("--email=") for argument in seed_command)


def test_native_helper_decodes_native_mode_uses_semantic_health_and_hides_source_tools() -> None:
    source = HELPER_SWIFT.read_text(encoding="utf-8")
    assert "var nativeRuntime: Bool? = nil" in source
    assert "__viventium_native_health" in source
    assert (
        "let apiHealthPort = runtime.nativeRuntime ? runtime.frontendPort : runtime.apiPort"
        in source
    )
    assert "let apiSurfaceReady = await self.apiHealthy(port: apiHealthPort)" in source
    assert "if self.controller.nativeRuntimeMode" in source
    assert 'Text("Source-only tools are unavailable in Native")' in source
    assert 'blockers == ["native_signed_bootstrap_required"]' in source


def test_native_helper_opens_the_exact_loopback_authority_accepted_by_proxy() -> None:
    source = HELPER_SWIFT.read_text(encoding="utf-8")
    assert (
        'let host = runtime.nativeRuntime\n'
        '            ? "127.0.0.1"\n'
        '            : (LocalNetworkAddressResolver.currentHost() ?? "localhost")'
        in source
    )


@pytest.mark.parametrize("relative", ["state", "runtime", "logs", "data", "data/mongodb", "backups"])
def test_native_mutable_child_symlink_is_rejected_without_touching_external_target(
    tmp_path: Path, relative: str
) -> None:
    runtime = load_native_runtime()
    support = tmp_path / "support"
    support.mkdir()
    target = support / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    external = tmp_path / f"external-{relative.replace('/', '-')}"
    external.mkdir()
    sentinel = file(external / "sentinel.txt", "untouched\n")
    target.symlink_to(external, target_is_directory=True)

    with pytest.raises(runtime.RuntimeError_, match="mutable path is unsafe"):
        runtime.validate_support_children(support)

    assert sentinel.read_text(encoding="utf-8") == "untouched\n"
    assert sorted(path.name for path in external.iterdir()) == ["sentinel.txt"]


def test_native_top_level_support_symlink_is_rejected_without_touching_external_target(
    tmp_path: Path,
) -> None:
    runtime = load_native_runtime()
    external = tmp_path / "external-support"
    external.mkdir()
    sentinel = file(external / "sentinel.txt", "untouched\n")
    support = tmp_path / "support"
    support.symlink_to(external, target_is_directory=True)

    with pytest.raises(runtime.RuntimeError_, match="mutable path is unsafe"):
        runtime.runtime_secrets(runtime.lexical_support(support))

    assert sentinel.read_text(encoding="utf-8") == "untouched\n"
    assert sorted(path.name for path in external.iterdir()) == ["sentinel.txt"]


def test_native_compliance_inventories_nested_and_workspace_packages_and_fails_unapproved(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "payload"
    metadata = {
        "arch": "arm64",
        "components": {
            "node": {"version": "24.16.0", "archive_sha256": "1" * 64},
            "python": {
                "version": "3.12.13",
                "archive_sha256": "2" * 64,
                "license_source_commit": "4" * 40,
                "license_source_sha256": "5" * 64,
            },
            "mongodb": {"version": "8.0.23", "archive_sha256": "3" * 64},
        },
        "source_commit": "a" * 40,
        "source_date_epoch": 1700000000,
    }
    file(payload / "release-metadata" / "build.json", json.dumps(metadata))
    file(payload / "runtime/node/LICENSE", "Synthetic Node license\n")
    file(payload / "runtime/python/lib/python3.12/LICENSE.txt", "Synthetic Python license\n")
    for name in PYTHON_STANDALONE_LICENSE_FILES:
        file(
            payload / "runtime/python/share/licenses/python-build-standalone" / name,
            f"Synthetic {name}\n",
        )
    spec = importlib.util.spec_from_file_location(
        "native_component_manifest_for_compliance", COMPONENT_MANIFEST
    )
    assert spec and spec.loader
    component_manifest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(component_manifest)
    python_runtime_manifest = component_manifest.build_manifest(
        payload / "runtime/python",
        name="python",
        component=metadata["components"]["python"],
    )
    file(
        payload / "release-metadata/python-runtime-manifest.json",
        json.dumps(python_runtime_manifest, sort_keys=True, separators=(",", ":"))
        + "\n",
    )
    file(payload / "runtime/mongodb/LICENSE-Community.txt", "Synthetic MongoDB community license\n")
    file(payload / "runtime/mongodb/THIRD-PARTY-NOTICES", "Synthetic MongoDB third-party notices\n")
    file(payload / "runtime/mongodb/MPL-2", "Synthetic MongoDB MPL text\n")
    librechat = payload / "runtime" / "librechat"
    file(librechat / "package.json", json.dumps({"name": "librechat", "version": "1.0.0", "license": "MIT"}))
    file(librechat / "LICENSE", "Synthetic LibreChat license\n")
    packages = (
        ("packages/workspace", "workspace-package", "Apache-2.0"),
        ("node_modules/top", "top-package", "MIT"),
        ("node_modules/top/node_modules/nested", "nested-package", "BSD-3-Clause"),
        ("node_modules/dual", "dual-license-package", "(MIT OR GPL-3.0-only)"),
    )
    for relative, name, license_value in packages:
        file(librechat / relative / "package.json", json.dumps({"name": name, "version": "1.0.0", "license": license_value}))
        file(librechat / relative / "LICENSE", f"Synthetic {name} license\n")
    file(
        librechat / "node_modules/top/dist/package.json",
        json.dumps({"name": "subpath-export", "version": "1.0.0", "license": "GPL-3.0-only"}),
    )
    file(
        librechat / "package-lock.json",
        json.dumps(
            {
                "name": "librechat",
                "lockfileVersion": 3,
                "packages": {
                    "": {"name": "librechat", "version": "1.0.0", "license": "MIT"},
                    "packages/workspace": {"version": "1.0.0", "license": "Apache-2.0"},
                    "node_modules/top": {
                        "version": "1.0.0",
                        "license": "MIT",
                        "resolved": "https://registry.npmjs.org/top/-/top-1.0.0.tgz",
                        "integrity": "sha512-synthetic-top",
                    },
                    "node_modules/top/node_modules/nested": {
                        "version": "1.0.0",
                        "license": "BSD-3-Clause",
                    },
                    "node_modules/dual": {
                        "version": "1.0.0",
                        "license": "(MIT OR GPL-3.0-only)",
                    },
                    "node_modules/pruned-platform-package": {
                        "version": "1.0.0",
                        "license": "MIT",
                    },
                },
            }
        ),
    )
    browser_lock_path = "node_modules/top"
    browser_directory = (
        "licenses/"
        f"{browser_lock_path.replace('/', '__')}--"
        f"{hashlib.sha256(browser_lock_path.encode()).hexdigest()[:12]}"
    )
    browser_metadata = json.dumps(
        {"name": "top-package", "version": "1.0.0", "license": "MIT"},
        separators=(",", ":"),
    ) + "\n"
    file(librechat / browser_lock_path / "package.json", browser_metadata)
    browser_license = "Synthetic top-package browser license\n"
    metadata_relative = f"{browser_directory}/package.json"
    license_relative = f"{browser_directory}/LICENSE"
    file(librechat / "client/dist-compliance/module-closure.json", json.dumps({
        "schemaVersion": 1,
        "packageLockPaths": [browser_lock_path],
    }))
    file(librechat / "client/dist-compliance" / metadata_relative, browser_metadata)
    file(librechat / "client/dist-compliance" / license_relative, browser_license)
    file(librechat / "client/dist-compliance/manifest.json", json.dumps({
        "schemaVersion": 1,
        "packages": [{
            "lockPath": browser_lock_path,
            "name": "top-package",
            "version": "1.0.0",
            "resolved": "https://registry.npmjs.org/top/-/top-1.0.0.tgz",
            "license": "MIT",
            "licenseSource": "installed-package.json#license(s)",
            "integrity": "sha512-synthetic-top",
            "packageMetadata": {
                "path": metadata_relative,
                "sha256": hashlib.sha256(browser_metadata.encode()).hexdigest(),
            },
            "legalFiles": [{
                "path": license_relative,
                "sha256": hashlib.sha256(browser_license.encode()).hexdigest(),
            }],
        }],
        "vendoredComponents": [],
    }))
    file(
        librechat / "client/third_party/browser-compliance/overrides.json",
        json.dumps({
            "schemaVersion": 1,
            "sources": [],
            "packageOverrides": [],
            "supplementalNotices": [],
        }),
    )
    approval = file(tmp_path / "mongodb-approved", "reviewed\n")
    command = [
        sys.executable,
        str(GENERATE_COMPLIANCE),
        "--payload-root",
        str(payload),
        "--output-dir",
        str(payload / "release-metadata"),
        "--mongodb-redistribution-approved",
        str(approval),
    ]
    generated = subprocess.run(command, check=False, capture_output=True, text=True)
    assert generated.returncode == 0, generated.stderr
    scan = json.loads((payload / "release-metadata" / "native-license-scan.json").read_text())
    by_name = {item["name"]: item for item in scan["packages"]}
    assert by_name["Python standalone runtime"]["license_files"] == [
        "runtime/python/lib/python3.12/LICENSE.txt"
    ]
    assert by_name["MongoDB Community Server"]["license_files"] == [
        "runtime/mongodb/LICENSE-Community.txt",
        "runtime/mongodb/THIRD-PARTY-NOTICES",
        "runtime/mongodb/MPL-2",
    ]
    assert "pip" not in by_name
    assert by_name["python-build-standalone bundled dependencies"]["allowed"] is True
    assert len(
        by_name["python-build-standalone bundled dependencies"]["license_files"]
    ) == len(PYTHON_STANDALONE_LICENSE_FILES)
    assert all(
        len(digest) == 64
        for item in scan["packages"]
        for digest in item["license_file_sha256"].values()
    )
    assert by_name["workspace-package"]["path"].endswith("packages/workspace")
    assert by_name["nested-package"]["path"].endswith("node_modules/top/node_modules/nested")
    assert "subpath-export" not in by_name
    assert by_name["dual-license-package"]["allowed"] is True
    browser_records = [
        item for item in scan["packages"]
        if item.get("inventory_scope") == "compiled-browser"
    ]
    assert [(item["name"], item["lock_path"]) for item in browser_records] == [
        ("top-package", "node_modules/top")
    ]
    assert browser_records[0]["license_files"] == [
        f"runtime/librechat/client/dist-compliance/{license_relative}"
    ]
    assert "Synthetic nested-package license" in (
        payload / "release-metadata" / "native-third-party-notices.txt"
    ).read_text()
    verified = subprocess.run(
        [sys.executable, str(VERIFY_COMPLIANCE), "--payload-root", str(payload)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert verified.returncode == 0, verified.stderr

    file(
        librechat / "client/dist-compliance" / license_relative,
        "tampered compiled-browser license\n",
    )
    browser_tampered = subprocess.run(
        [sys.executable, str(VERIFY_COMPLIANCE), "--payload-root", str(payload)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert browser_tampered.returncode != 0
    assert "license hash mismatch" in browser_tampered.stderr
    file(librechat / "client/dist-compliance" / license_relative, browser_license)

    file(
        librechat / "client/dist-compliance/licenses/unreferenced.txt",
        "unreferenced browser compliance material\n",
    )
    unreferenced = subprocess.run(command, check=False, capture_output=True, text=True)
    assert unreferenced.returncode != 0
    assert "unreferenced or missing shipped files" in unreferenced.stderr
    (librechat / "client/dist-compliance/licenses/unreferenced.txt").unlink()

    file(payload / "runtime/mongodb/THIRD-PARTY-NOTICES", "tampered after compliance generation\n")
    tampered = subprocess.run(
        [sys.executable, str(VERIFY_COMPLIANCE), "--payload-root", str(payload)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert tampered.returncode != 0
    assert "license hash mismatch" in tampered.stderr

    file(
        librechat / "node_modules" / "top" / "node_modules" / "nested" / "package.json",
        json.dumps({"name": "nested-package", "version": "1.0.0", "license": "GPL-3.0-only"}),
    )
    rejected = subprocess.run(command, check=False, capture_output=True, text=True)
    assert rejected.returncode != 0
    assert "require license review" in rejected.stderr


def test_native_compliance_rejects_allowed_declaration_without_shipped_notice(
    tmp_path: Path,
) -> None:
    source = GENERATE_COMPLIANCE.read_text(encoding="utf-8")
    assert "license_allowed(license_value) and bool(notices)" in source
    assert '"notice_present": bool(notices)' in source
    verifier = VERIFY_COMPLIANCE.read_text(encoding="utf-8")
    assert 'package.get("notice_present") is not True' in verifier
    assert "or not relative_paths" in verifier


def test_bootstrap_launcher_uses_only_its_signed_bundled_python() -> None:
    source = BOOTSTRAP_SWIFT.read_text(encoding="utf-8")
    assert "Contents/Resources/runtime/python/bin/python3" in source
    assert "install_native_payload.py" in source
    assert 'process.arguments = ["-E", "-s", "-B", installer.path]' in source
    assert '!$0.key.hasPrefix("PYTHON")' in source
    assert 'environment["PYTHONNOUSERSITE"] = "1"' in source
    assert 'executableURL = URL(fileURLWithPath: "/usr/bin/python3")' not in source
    assert "brew" not in source.lower()
    assert "source install" not in source.lower()
