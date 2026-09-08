from __future__ import annotations

import argparse
import contextlib
import errno
import json
import importlib.util
import hashlib
import io
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import tarfile
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
LOOPBACK_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


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
    file(
        compiled / "config.yaml",
        "version: 1\n"
        "install:\n  mode: native\n  experience: express\n"
        "integrations:\n"
        "  glasshive:\n"
        "    enabled: false\n"
        "    provider:\n      enabled: false\n"
        "    host_worker:\n      enabled: false\n",
    )
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
        "GROQ_BASE_URL=https://api.groq.com/openai/v1/\n"
        "XAI_BASE_URL=https://api.x.ai/v1\n"
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


def glasshive_source_fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    repo = tmp_path / "parent"
    source = tmp_path / "GlassHive"
    file(source / "LICENSE", "Synthetic component license\n")
    file(source / "runtime_phase1" / "pyproject.toml", '[project]\nname="synthetic-runtime"\nversion="1.0"\n')
    file(source / "runtime_phase1" / "uv.lock", "version = 1\n")
    file(source / "runtime_phase1" / "workstation-requirements.lock", "synthetic-worker==1.0\n")
    file(source / "runtime_phase1" / "src" / "workers_projects_runtime" / "api.py", "app = None\n")
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(source), "-c", "user.name=Synthetic Builder", "-c",
         "user.email=builder@example.invalid", "commit", "-qm", "Synthetic fixture"],
        check=True,
    )
    pin = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    file(repo / "components.lock.json", json.dumps({"components": [{"name": "GlassHive", "ref": pin}]}))
    return repo, source, pin


@pytest.mark.parametrize("local_qa_worktree", [False, True])
def test_native_glasshive_staging_uses_selected_source_and_hash_locked_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, local_qa_worktree: bool,
) -> None:
    assembler = load_native_assembler(monkeypatch)
    repo, source, pin = glasshive_source_fixture(tmp_path)
    uv = executable(tmp_path / "uv")
    python = executable(tmp_path / "python")
    output = tmp_path / "payload" / "runtime" / "glasshive"
    if local_qa_worktree:
        file(source / "runtime_phase1/src/workers_projects_runtime/native_continuity.py", "value = 'reviewed change'\n")
    calls = []

    def build(command, **kwargs):
        calls.append((command, kwargs))
        if "export" in command:
            file(Path(command[command.index("--output-file") + 1]), "synthetic==1.0 --hash=sha256:" + "a" * 64)
        else:
            target = Path(command[command.index("--target") + 1])
            file(target / "synthetic" / "__init__.py", "value = 1\n")
            executable(target / "bin" / "synthetic", "#!/private/build/python\n")
            file(target / "synthetic-1.0.dist-info" / "METADATA", "Name: synthetic\nVersion: 1.0\nLicense-Expression: MIT\n")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setenv("WPR_API_TOKEN", "synthetic-owner-secret")
    monkeypatch.setattr(assembler, "run_glasshive_build", build)
    manifest = assembler.stage_glasshive(
        repo, source, python, uv, output, source_date_epoch=1700000000, local_qa_worktree=local_qa_worktree,
    )

    assert manifest["commit"] == pin
    assert manifest["source_kind"] == ("local-qa-worktree" if local_qa_worktree else "component-pin")
    assert len(manifest["source_tree_sha256"]) == 64
    assert (output / "src/workers_projects_runtime/native_continuity.py").exists() == local_qa_worktree
    assert manifest["uv_lock_sha256"] == hashlib.sha256((source / "runtime_phase1" / "uv.lock").read_bytes()).hexdigest()
    assert (output / "src" / "workers_projects_runtime" / "api.py").is_file()
    assert (output / "workstation-requirements.lock").is_file()
    assert (output / "site-packages" / "synthetic" / "__init__.py").is_file()
    assert not (output / "site-packages" / "bin").exists()
    assert not (output / ".git").exists()
    assert "--locked" in calls[0][0]
    assert "--no-dev" in calls[0][0]
    assert "--no-emit-project" in calls[0][0]
    assert "--require-hashes" in calls[1][0]
    assert "--only-binary" in calls[1][0]
    assert str(python) in calls[1][0]
    assert all("WPR_API_TOKEN" not in kwargs["env"] for _, kwargs in calls)


def test_native_candidate_never_accepts_local_qa_worktree_input(monkeypatch):
    assembler = load_native_assembler(monkeypatch)
    with pytest.raises(assembler.AssemblyError, match="restricted to local QA"):
        assembler.assemble(argparse.Namespace(mode="candidate", glasshive_local_qa_worktree=True))


@pytest.mark.parametrize("failure", [None, "digest", "traversal", "link", "missing-companion", "package-version", "package-json", "notice-digest", "notice-replace", "notice-escape"])
def test_native_body_staging_binds_complete_publisher_archive(tmp_path, monkeypatch, failure):
    assembler = load_native_assembler(monkeypatch)
    archive = tmp_path / "body.tgz"
    entries = {"package/package.json": json.dumps({"name": "synthetic-body", "version": "1.2.3"}),
               "package/bin/body": "executable bytes", "package/bin/companion": "companion bytes",
               "package/LICENSE": "Synthetic license"}
    if failure == "traversal":
        entries["package/../escape"] = "escape"
    elif failure == "missing-companion":
        entries.pop("package/bin/companion")
    elif failure == "package-version":
        entries["package/package.json"] = json.dumps({"name": "synthetic-body", "version": "1.2.4"})
    elif failure == "package-json":
        entries["package/package.json"] = "[]"
    with tarfile.open(archive, "w:gz") as bundle:
        for name, body in entries.items():
            item = tarfile.TarInfo(name); data = body.encode(); item.size = len(data); item.mode = 0o755 if "/bin/" in name else 0o644
            bundle.addfile(item, io.BytesIO(data))
        if failure == "link":
            item = tarfile.TarInfo("package/link"); item.type = tarfile.SYMTYPE; item.linkname = "bin/body"; bundle.addfile(item)
    policy = {"version": "1.2.3", "license": "MIT", "license_files": ["LICENSE"], "architectures": {"arm64": {
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "package_name": "synthetic-body", "package_version": "1.2.3",
        "executable": "bin/body", "required_files": ["bin/body", "bin/companion", "LICENSE"]}}}
    file(tmp_path / "notices/NOTICE", "Synthetic notice")
    policy["additional_notices"] = [{"source": "notices/NOTICE", "destination": "NOTICE",
                                     "sha256": hashlib.sha256(b"Synthetic notice").hexdigest()}]
    if failure == "digest":
        policy["architectures"]["arm64"]["sha256"] = "0" * 64
    elif failure == "notice-digest":
        policy["additional_notices"][0]["sha256"] = "0" * 64
    elif failure == "notice-replace":
        policy["additional_notices"][0]["destination"] = "LICENSE"
    elif failure == "notice-escape":
        policy["additional_notices"][0]["source"] = "../NOTICE"
    output = tmp_path / "staged"
    if failure:
        with pytest.raises(assembler.AssemblyError):
            assembler.stage_native_body(tmp_path, archive, output, policy, "arm64", source_date_epoch=1700000000)
        assert not (tmp_path / "escape").exists()
    else:
        result = assembler.stage_native_body(tmp_path, archive, output, policy, "arm64", source_date_epoch=1700000000)
        assert (output / "bin/companion").read_text() == "companion bytes"
        assert (output / "NOTICE").read_text() == "Synthetic notice"
        assert result["executable"] == "bin/body" and result["version"] == "1.2.3"
        assert result["archive_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
        assert result["executable_sha256"] == hashlib.sha256(b"executable bytes").hexdigest()


def test_native_code_inventory_reuses_verifier_without_per_file_processes(tmp_path, monkeypatch):
    assembler = load_native_assembler(monkeypatch)
    executable = tmp_path / "runtime/python/lib/native.so"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"\xcf\xfa\xed\xfe" + b"synthetic")
    file(tmp_path / "runtime/python/README.txt", "ordinary dependency text")
    monkeypatch.setattr(assembler.subprocess, "run", lambda *_args, **_kwargs: pytest.fail("per-file subprocess is unnecessary"))
    assert assembler.macho_paths(tmp_path) == ["runtime/python/lib/native.so", "apps/Viventium.app"]


@pytest.mark.parametrize("change", ["wrong_pin", "modified_source", "untracked_source"])
def test_native_glasshive_staging_refuses_unselected_or_dirty_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str,
) -> None:
    assembler = load_native_assembler(monkeypatch)
    repo, source, _ = glasshive_source_fixture(tmp_path)
    if change == "wrong_pin":
        file(repo / "components.lock.json", json.dumps({"components": [{"name": "GlassHive", "ref": "a" * 40}]}))
    elif change == "modified_source":
        file(source / "runtime_phase1" / "src" / "workers_projects_runtime" / "api.py", "changed = True\n")
    else:
        file(source / "runtime_phase1" / "src" / "private.json", '{"private":"synthetic"}')
    with pytest.raises(assembler.AssemblyError, match="GlassHive.*(pin|source)"):
        assembler.stage_glasshive(
            repo, source, tmp_path / "python", tmp_path / "uv", tmp_path / "output",
            source_date_epoch=1700000000,
        )


def test_native_compliance_includes_glasshive_wheels_and_holds_unknown_licenses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend(str(GENERATE_COMPLIANCE.parent))
    spec = importlib.util.spec_from_file_location("native_glasshive_compliance", GENERATE_COMPLIANCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path / "runtime" / "glasshive"
    file(root / "LICENSE", "Synthetic first-party license\n")
    dependency = root / "site-packages" / "synthetic-1.0.dist-info"
    file(dependency / "METADATA", "Name: synthetic\nVersion: 1.0\nLicense-Expression: MIT\nLicense-File: LICENSE\n")
    file(dependency / "licenses" / "LICENSE", "Synthetic MIT notice\n")
    unknown = root / "site-packages" / "unreviewed-2.0.dist-info"
    file(unknown / "METADATA", "Name: unreviewed\nVersion: 2.0\n")
    file(unknown / "LICENSE", "Synthetic unreviewed notice\n")
    packages = module.glasshive_inventory(tmp_path, {"glasshive": {"version": "0.3.0"}})
    records = {item["name"]: module.scan_package_record(tmp_path, item) for item in packages}
    assert set(records) == {"GlassHive", "synthetic", "unreviewed"}
    assert records["synthetic"]["allowed"] is True
    assert records["synthetic"]["license_files"] == ["runtime/glasshive/site-packages/synthetic-1.0.dist-info/licenses/LICENSE"]
    assert records["unreviewed"]["allowed"] is False
    assert records["unreviewed"]["license"] == "NOASSERTION"
    file(dependency / "METADATA", "Name: synthetic\nVersion: 1.0\nLicense-Expression: MIT\nLicense-File: ../../outside\n")
    with pytest.raises(module.ComplianceError, match="unsafe"):
        module.glasshive_inventory(tmp_path, {"glasshive": {"version": "0.3.0"}})


@pytest.mark.parametrize("failure", [None, "undeclared", "executable", "notice", "identity"])
def test_native_body_compliance_requires_exact_inventory_and_retains_license_hold(tmp_path, monkeypatch, failure):
    monkeypatch.syspath_prepend(str(GENERATE_COMPLIANCE.parent))
    spec = importlib.util.spec_from_file_location("native_body_compliance", GENERATE_COMPLIANCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bodies = {}
    for profile, license_value in (("codex-cli", "Apache-2.0"), ("claude-code", "LicenseRef-Anthropic-Commercial")):
        root = tmp_path / "runtime/native-bodies" / profile
        file(root / "package.json", json.dumps({"name": profile, "version": "1.0"}))
        file(root / "LICENSE", "Synthetic notice")
        executable(root / "body")
        bodies[profile] = {"package_name": profile, "package_version": "1.0", "license": license_value,
                           "license_files": ["LICENSE"], "executable": "body",
                           "executable_sha256": hashlib.sha256((root / "body").read_bytes()).hexdigest()}
    if failure == "undeclared":
        file(tmp_path / "runtime/native-bodies/unselected/body")
    elif failure == "executable":
        file(tmp_path / "runtime/native-bodies/codex-cli/body", "changed")
    elif failure == "notice":
        (tmp_path / "runtime/native-bodies/codex-cli/LICENSE").unlink()
    elif failure == "identity":
        bodies["codex-cli"]["package_version"] = "2.0"
    if failure:
        with pytest.raises(module.ComplianceError):
            module.native_body_inventory(tmp_path, {"glasshive": {"native_bodies": bodies}})
    else:
        packages = module.native_body_inventory(tmp_path, {"glasshive": {"native_bodies": bodies}})
        records = {item["name"]: module.scan_package_record(tmp_path, item) for item in packages}
        assert records["codex-cli"]["allowed"] is True
        assert records["claude-code"]["allowed"] is False
        assert records["claude-code"]["notice_present"] is True


@pytest.mark.parametrize("failure", [None, "digest", "identity", "missing"])
def test_native_browser_adapter_inventory_verifies_retained_pruned_metadata(tmp_path, monkeypatch, failure):
    monkeypatch.syspath_prepend(str(GENERATE_COMPLIANCE.parent))
    spec = importlib.util.spec_from_file_location("native_browser_metadata", GENERATE_COMPLIANCE)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    root = tmp_path / "runtime/librechat"; closure = root / "client/dist-compliance"
    file(root / "package-lock.json", json.dumps({"lockfileVersion": 3, "packages": {
        "node_modules/synthetic-adapter": {"version": "1.0", "integrity": "sha512-synthetic"}}}))
    file(root / "client/third_party/browser-compliance/overrides.json", json.dumps({
        "schemaVersion": 1, "sources": [], "packageOverrides": [], "supplementalNotices": []}))
    file(closure / "module-closure.json", json.dumps({"schemaVersion": 1, "packageLockPaths": []}))
    def record(name, body):
        file(closure / name, body)
        return {"path": name, "sha256": hashlib.sha256(body.encode()).hexdigest()}
    metadata = record("vendored/synthetic/package.json", json.dumps({"name": "synthetic-adapter", "version": "1.0"}))
    component = {"id": "synthetic", "name": "Synthetic adapter", "upstreamPackage": "synthetic-adapter",
        "upstreamVersion": "1.0", "upstreamIntegrity": "sha512-synthetic", "license": "MIT", "modified": True,
        "packageMetadata": metadata, "notice": record("vendored/synthetic/NOTICE", "Synthetic notice"),
        "legalFiles": [record("vendored/synthetic/LICENSE", "Synthetic license")]}
    if failure == "digest": file(closure / metadata["path"], "changed")
    elif failure == "identity": component["packageMetadata"] = record(metadata["path"], json.dumps({"name": "other", "version": "1.0"}))
    elif failure == "missing": (closure / metadata["path"]).unlink()
    file(closure / "manifest.json", json.dumps({"schemaVersion": 1, "packages": [], "vendoredComponents": [component]}))
    assert not (root / "node_modules/synthetic-adapter").exists()
    if failure:
        with pytest.raises(module.ComplianceError): module.browser_inventory(tmp_path)
    else:
        assert module.browser_inventory(tmp_path)[0]["name"] == "Synthetic adapter"


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
    monkeypatch.setattr(runtime, "native_child_environment", lambda _support, **_kwargs: {})
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
    assert (payload / "runtime" / "defaults" / "config.yaml").read_bytes() == (
        inputs["compiled"] / "config.yaml"
    ).read_bytes()
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
    assert (payload / "bin" / "viventium-native-provider-auth").is_file()
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
            "librechat": {"commit": next(item["ref"] for item in json.loads((REPO_ROOT / "components.lock.json").read_text())["components"] if item["name"] == "LibreChat")},
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
    for owner in ("life_setup.py", "life_bootstrap.py", "config_settings.py"):
        assert (first / "payload/runtime/scripts" / owner).read_bytes() == (REPO_ROOT / "scripts/viventium" / owner).read_bytes()
    assert (first / "payload/templates/life-v0.01/AGENTS.md").read_bytes() == (REPO_ROOT / "templates/life-v0.01/AGENTS.md").read_bytes()
    assert not any(path.is_symlink() for path in first.rglob("*"))
    assert {mode for _, _, mode in tree_digest(first)} <= {0o644, 0o755}


def test_assembler_refreshes_prebuilt_bootstrap_from_selected_source(tmp_path: Path) -> None:
    inputs = fixture_inputs(tmp_path)
    names = ("native_payload.py", "install_native_payload.py")
    for name in names:
        file(inputs["bootstrap"] / "Contents/Resources/scripts" / name, "# stale producer input\n")
    output = tmp_path / "candidate"
    result = run_assembler(tmp_path, inputs, output)
    assert result.returncode == 0, result.stderr
    for name in names:
        expected = (REPO_ROOT / "scripts/viventium" / name).read_bytes()
        assert (output / "bootstrap/ViventiumBootstrap.app/Contents/Resources/scripts" / name).read_bytes() == expected
    assert (output / "payload/runtime/scripts/native_payload.py").read_bytes() == (output / "bootstrap/ViventiumBootstrap.app/Contents/Resources/scripts/native_payload.py").read_bytes()


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


@pytest.mark.parametrize(
    ("artifact", "marker"),
    tuple(
        (artifact, marker)
        for artifact in (
            "config.yaml",
            "librechat.yaml",
            "prompt-bundle.json",
            "native-runtime.env",
            "viventium-agents.yaml",
        )
        for marker in ("glasshive-harness", "glasshive-workers-projects")
    ),
)
def test_assembler_rejects_unavailable_glasshive_native_advertisements(
    tmp_path: Path,
    artifact: str,
    marker: str,
) -> None:
    inputs = fixture_inputs(tmp_path)
    path = inputs["compiled"] / artifact
    path.write_text(
        path.read_text(encoding="utf-8") + f"\nforbidden: {marker}\n",
        encoding="utf-8",
    )

    completed = run_assembler(tmp_path, inputs, tmp_path / "candidate")

    assert completed.returncode != 0
    assert "advertise unavailable GlassHive runtime" in completed.stderr


@pytest.mark.parametrize(
    "path",
    (
        ("enabled",),
        ("provider", "enabled"),
        ("host_worker", "enabled"),
    ),
)
def test_assembler_rejects_enabled_unbundled_glasshive_config(
    tmp_path: Path,
    path: tuple[str, ...],
) -> None:
    inputs = fixture_inputs(tmp_path)
    config_path = inputs["compiled"] / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    target = config["integrations"]["glasshive"]
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = True
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    completed = run_assembler(tmp_path, inputs, tmp_path / "candidate")

    assert completed.returncode != 0
    assert "enable unavailable GlassHive runtime" in completed.stderr


def test_native_candidate_config_excludes_unbundled_glasshive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = yaml.safe_load(
        (REPO_ROOT / "config.minimal.example.yaml").read_text(encoding="utf-8")
    )
    # This fixture's synthetic Node has no npm installation; sequential-thinking bundling has
    # its own native-component tests and is not part of the unbundled-GlassHive contract.
    config.setdefault("integrations", {})["sequential_thinking"] = {"enabled": False}
    glasshive = config.setdefault("integrations", {}).setdefault("glasshive", {})
    glasshive["enabled"] = False
    glasshive.setdefault("provider", {})["enabled"] = False
    glasshive.setdefault("host_worker", {})["enabled"] = False
    for role in ("memory", "deep_memory"):
        config["llm"][role] = {"provider": "openai", "model": "gpt-5.6-sol", "reasoning_effort": "medium"}
    config_path = tmp_path / "native-config.yaml"
    compiled = tmp_path / "compiled"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(compiled),
        ],
        cwd=REPO_ROOT,
        check=True,
    )
    shutil.copyfile(config_path, compiled / "config.yaml")

    load_native_assembler(monkeypatch).validate_native_compiled_defaults(compiled)
    inputs = fixture_inputs(tmp_path / "assembly-inputs")
    inputs["compiled"] = compiled
    output = tmp_path / "candidate"
    completed = run_assembler(tmp_path, inputs, output)
    assert completed.returncode == 0, completed.stderr
    assert (
        output / "payload" / "runtime" / "defaults" / "config.yaml"
    ).read_bytes() == config_path.read_bytes()


@pytest.mark.parametrize("records", [[], [{"name": "LibreChat", "ref": "not-a-pin"}], [{"name": "LibreChat", "ref": "a" * 40}] * 2, None])
def test_native_release_selection_rejects_ambiguous_or_invalid_parent_pin(tmp_path, monkeypatch, records):
    assembler = load_native_assembler(monkeypatch)
    file(tmp_path / "components.lock.json", json.dumps({"components": records}))
    with pytest.raises(assembler.AssemblyError, match="LibreChat parent component pin"):
        assembler.selected_component_pin(tmp_path, "LibreChat")


def test_native_release_selection_follows_parent_lock_without_rewriting_prior_manifest(tmp_path, monkeypatch):
    assembler = load_native_assembler(monkeypatch)
    policy = assembler.read_components(REPO_ROOT / "release/native-payload/components.json")
    lock = tmp_path / "components.lock.json"
    file(lock, json.dumps({"components": [{"name": "LibreChat", "ref": "a" * 40}]}))
    first = assembler.release_component_manifest(policy, "arm64", tmp_path)
    file(lock, json.dumps({"components": [{"name": "LibreChat", "ref": "b" * 40}]}))
    second = assembler.release_component_manifest(policy, "arm64", tmp_path)
    assert first["librechat"]["commit"] == "a" * 40
    assert second["librechat"]["commit"] == "b" * 40
    assert "librechat" not in policy


def test_assembler_rejects_unattestable_component_metadata(tmp_path: Path) -> None:
    inputs = fixture_inputs(tmp_path)
    policy = json.loads(
        (REPO_ROOT / "release" / "native-payload" / "components.json").read_text()
    )

    policy["librechat"] = {"commit": "0" * 40}
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
    assert "Native source pins belong only in components.lock.json" in invalid_commit.stderr

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


@pytest.mark.parametrize(
    "relative",
    (
        Path("runtime.env"),
        Path("runtime.local.env"),
        Path("service-env/librechat.owner.env"),
    ),
)
def test_assembler_rejects_generated_owner_environment_inputs(
    tmp_path: Path,
    relative: Path,
) -> None:
    inputs = fixture_inputs(tmp_path)
    file(inputs["librechat"] / relative, "OWNER_VALUE=weak-sentinel\n")

    completed = run_assembler(tmp_path, inputs, tmp_path / "candidate")

    assert completed.returncode != 0
    assert "secret-shaped input" in completed.stderr
    assert "weak-sentinel" not in completed.stderr


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


@pytest.mark.parametrize("recovered_status", ["open", "closed"])
def test_native_install_opens_current_first_admin_state_after_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recovered_status: str
) -> None:
    inputs = fixture_inputs(tmp_path)
    output = tmp_path / "candidate"
    result = run_assembler(tmp_path, inputs, output)
    assert result.returncode == 0, result.stderr
    runtime = load_native_runtime()
    support = tmp_path / "support"
    root = output / "payload"
    monkeypatch.setattr(runtime, "release_root", lambda: root)
    monkeypatch.setattr(runtime, "preflight_service_ports", lambda *_: None)
    monkeypatch.setattr(runtime, "guard_pid_snapshot", lambda *_: {})
    monkeypatch.setattr(runtime, "health", lambda *_: None)
    current = {"schema_version": 1, "status": recovered_status}
    if recovered_status == "open":
        current["token"] = "b" * 64
    else:
        current["admin_user_id"] = "c" * 24
    def startup(*_args, **_kwargs):
        previous = runtime.ensure_first_admin_state(support)
        assert previous["status"] == "open"
        assert previous["token"] != current.get("token")
        runtime.write_atomic(support / "state/native-first-admin.json", json.dumps(current))
    monkeypatch.setattr(runtime, "start", startup)
    opened = []
    monkeypatch.setattr(runtime.subprocess, "run", lambda command, **_: opened.append(command) or subprocess.CompletedProcess(command, 0))
    runtime.install(argparse.Namespace(app_support_dir=support, local_qa=True,
        no_helper=True, no_start=False, no_open=False, timeout=1))
    expected = "http://127.0.0.1:3190/"
    if recovered_status == "open":
        expected += "__viventium_native_first_admin?token=" + current["token"]
    assert opened == [["/usr/bin/open", expected]]
    assert runtime.ensure_first_admin_state(support) == current


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
    assert (support / "config.yaml").read_bytes() == (
        inputs["compiled"] / "config.yaml"
    ).read_bytes()
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


@pytest.mark.parametrize("invalid", [None, "no_pending", "prepared", "health_passed", "key", "digest", "active", "pending_symlink", "writable_manifest"])
def test_native_install_accepts_only_exact_bootstrap_replacement(tmp_path, monkeypatch, invalid):
    monkeypatch.syspath_prepend(str(ASSEMBLER.parent))
    import native_payload
    runtime = load_native_runtime()
    support = tmp_path / "support"
    install_root = support / "native"
    root = install_root / "releases" / "candidate"
    root.mkdir(parents=True)
    old = install_root / "releases" / "previous"
    old.mkdir()
    state = file(support / "state/native-runtime.json", json.dumps({
        "schema_version": 1, "release_root": str(old), "local_qa": True,
    }))
    state.chmod(0o600)
    before = state.read_bytes()
    manifest = file(root / ".viventium-manifest.json", '{"verified":"candidate"}\n')
    manifest.chmod(0o600 if invalid == "writable_manifest" else 0o444)
    (install_root / "active").symlink_to(old if invalid == "active" else root, target_is_directory=True)
    pending = file(native_payload._pending_activation_path(install_root), json.dumps({
        "schema": 1, "candidateReleaseKey": "wrong" if invalid == "key" else root.name,
        "priorReleaseKey": old.name, "phase": invalid if invalid in {"prepared", "health_passed"} else "pointer_switched",
        "manifestSha256": "0" * 64 if invalid == "digest" else hashlib.sha256(manifest.read_bytes()).hexdigest(),
    }))
    pending.chmod(0o600)
    if invalid == "no_pending":
        pending.unlink()
    elif invalid == "pending_symlink":
        target = pending.with_name("original.json")
        pending.rename(target)
        pending.symlink_to(target)
    monkeypatch.setattr(runtime, "release_root", lambda: root)
    if invalid:
        with pytest.raises(runtime.RuntimeError_):
            runtime.refuse_cross_mode_install(support)
    else:
        runtime.refuse_cross_mode_install(support)
        # The exception belongs only to install. A stale lifecycle command stays fenced.
        with pytest.raises(runtime.RuntimeError_, match="release pointer"):
            runtime.installed_release_root(support)
    assert state.read_bytes() == before


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
    monkeypatch.setattr(runtime, "native_child_environment", lambda _support, **_kwargs: {})
    monkeypatch.setattr(runtime, "runtime_secrets", lambda _support, **_kwargs: {})
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


@pytest.mark.parametrize("failed_service", ["librechat", "glasshive-mcp"])
def test_native_start_failure_preserves_a_preexisting_owned_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_service: str
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
        lambda _root: {"source_commit": "a" * 40, "sandpack_index_sha256": "0" * 64,
                       "components": {"glasshive": {"commit": "b" * 40}} if failed_service == "glasshive-mcp" else {}},
    )
    monkeypatch.setattr(runtime, "preflight_service_ports", lambda *_args: None)
    monkeypatch.setattr(runtime, "preflight_mongodb_socket", lambda *_args: None)
    monkeypatch.setattr(runtime, "preflight_api_socket", lambda *_args: None)
    monkeypatch.setattr(runtime, "preflight_private_socket", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime, "native_body_paths", lambda _root: {"codex-cli": root / "body"} if failed_service == "glasshive-mcp" else {})
    monkeypatch.setattr(runtime, "native_glasshive_transport_environment", lambda *_args: {})
    monkeypatch.setattr(runtime, "native_glasshive_environment", lambda *_args: {})
    monkeypatch.setattr(runtime, "wait_owned_glasshive_socket", lambda *_args, **kwargs: not kwargs.get("mcp"))
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
    monkeypatch.setattr(runtime, "native_child_environment", lambda _support, **_kwargs: {})
    monkeypatch.setattr(runtime, "runtime_secrets", lambda _support, **_kwargs: {})
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

    with pytest.raises(runtime.RuntimeError_, match="did not become ready"):
        runtime.start(type("Args", (), {"app_support_dir": support, "timeout": 0.1})())

    assert stopped == (["glasshive-mcp", "glasshive"] if failed_service == "glasshive-mcp" else ["librechat"])
    assert maintenance[0] == ("mongodb-replica-ready", [
        str(root / "runtime/node/bin/node"), str(root / "runtime/scripts/native_mongodb_replica.js"),
        str(root / "runtime/librechat"), str(runtime.mongodb_socket_path(support)), "0.1",
    ])
    assert maintenance[1] == (
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
        f"mongodb://{urllib.parse.quote(str(socket_path), safe='')}/LibreChat?directConnection=true"
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
    monkeypatch.syspath_prepend(str(NATIVE_RUNTIME.parent))
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


@pytest.mark.parametrize("phase", ["activate", "backup", "rollback"])
def test_sealed_helper_cleanup_preserves_prior_app_and_original_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    monkeypatch.syspath_prepend(str(NATIVE_RUNTIME.parent))
    import native_payload
    runtime = load_native_runtime()
    home = tmp_path / "home"
    home.mkdir()
    target = home / "Applications" / "Viventium.app"
    source = tmp_path / "source" / "Viventium.app"
    owned_helper(source, "b" * 40)
    owned_helper(target, "a" * 40)
    file(target / "prior.txt", "prior\n")
    for bundle in (source, target):
        for current, _directories, files in os.walk(bundle, topdown=False):
            for name in files:
                path = Path(current) / name
                path.chmod(0o555 if path.stat().st_mode & 0o111 else 0o444)
            Path(current).chmod(0o555)
    source_before = {str(p.relative_to(source)): (p.stat().st_mode, p.read_bytes())
                     for p in source.rglob("*") if p.is_file()}
    source_directory_modes = {
        str(path.relative_to(source)): path.stat().st_mode
        for path in [source, *source.rglob("*")] if path.is_dir()
    }
    support = tmp_path / "support"
    monkeypatch.setattr(runtime, "user_home", lambda: home)
    monkeypatch.setattr(runtime, "quiesce_helper", lambda _app: None)
    real_replace = runtime.os.replace
    def replace_bundle(source_path, destination_path):
        # Exercise Darwin's sealed-directory rename constraint on every test host.
        if Path(source_path).is_dir() and not Path(source_path).stat().st_mode & 0o200:
            raise PermissionError("sealed directory requires owner write for rename")
        if ((phase == "activate" and Path(source_path).name.startswith(".Viventium.app.installing"))
                or (phase == "backup" and Path(source_path) == target)):
            raise OSError("synthetic activation failure")
        return real_replace(source_path, destination_path)
    monkeypatch.setattr(runtime.os, "replace", replace_bundle)
    try:
        if phase in ("activate", "backup"):
            with pytest.raises(OSError, match="synthetic activation failure"):
                runtime.install_helper(source, support)
        else:
            backup = runtime.install_helper(source, support)
            assert backup is not None
            assert target.stat().st_mode & 0o777 == 0o555
            assert backup.stat().st_mode & 0o777 == 0o555
            runtime.rollback_helper(target, backup)
        assert (target / "prior.txt").read_text() == "prior\n"
        assert target.stat().st_mode & 0o777 == 0o555
        assert not list(target.parent.glob(".Viventium.app.installing.*"))
        assert {str(p.relative_to(source)): (p.stat().st_mode, p.read_bytes())
                for p in source.rglob("*") if p.is_file()} == source_before
        assert {
            str(path.relative_to(source)): path.stat().st_mode
            for path in [source, *source.rglob("*")] if path.is_dir()
        } == source_directory_modes
    finally:
        for app in [source, target, *target.parent.glob(".Viventium.app.installing.*")]:
            if app.exists():
                native_payload._make_verified_tree_removable(app)


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
        '/usr/bin/codesign --force --sign - --entitlements apps/macos/ViventiumHelper/ViventiumHelper.entitlements "$candidate_root/payload/apps/Viventium.app"',
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
        "compiled-defaults/config.yaml",
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
    assert "glasshive:\n              enabled: true" in workflow
    assert "glasshive: { enabled: false }" not in workflow
    assert 'native_glasshive["enabled"] = False' not in workflow
    assert '--glasshive-root "$GITHUB_WORKSPACE/viventium_v0_4/GlassHive"' in workflow
    assert '--codex-archive "${RUNNER_TEMP}/downloads/codex-cli.tar.gz"' in workflow
    assert '--claude-code-archive "${RUNNER_TEMP}/downloads/claude-code.tar.gz"' in workflow
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
        "provider-auth",
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
    assert 'FileManager.default.fileExists(atPath: "\\(repoRoot)/bin/viventium-native-start")' in source
    assert "process.arguments = HelperCLICommand.arguments(" in source
    assert "repoRoot: repoRoot, appSupportDir: appSupportDir, command: arguments" in source
    assert 'return ["\\(repoRoot)/bin/viventium"] +' in source
    assert '(native ? [] : ["--app-support-dir", appSupportDir]) + action' in source
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
    monkeypatch.setattr(runtime, "runtime_secrets", lambda _support, **_kwargs: {"CREDS_KEY": "a" * 32, "CREDS_IV": "b" * 32})
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


def test_native_runtime_accepts_compiler_owned_contract_and_rejects_endpoint_changes(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ASSEMBLER.parent))
    import config_compiler
    runtime = load_native_runtime()
    native = config_compiler.render_native_runtime_env({"install": {"mode": "native"}}, {
        "OPENAI_API_KEY": "synthetic-secret", "START_GLASSHIVE": "true",
        "GROQ_BASE_URL": "https://untrusted.invalid", "XAI_BASE_URL": "https://untrusted.invalid",
    })
    path = tmp_path / "native-runtime.env"
    config_compiler.dump_env(path, native)
    assert runtime.load_native_runtime_env(path) == native
    assert "synthetic-secret" not in path.read_text()
    assert native["START_GLASSHIVE"] == "false"
    for name in ("GROQ_BASE_URL", "XAI_BASE_URL"):
        config_compiler.dump_env(path, {**native, name: "https://untrusted.invalid"})
        with pytest.raises(runtime.RuntimeError_, match="fixed Native profile"):
            runtime.load_native_runtime_env(path)


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
        "GROQ_BASE_URL=https://api.groq.com/openai/v1/\n"
        "XAI_BASE_URL=https://api.x.ai/v1\n"
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


def test_native_guard_creates_private_mutable_files_regardless_of_launcher_umask(tmp_path):
    result = subprocess.run([
        sys.executable, str(REPO_ROOT / "scripts/viventium/native_process_guard.py"),
        "--token", "a" * 64, "--", sys.executable, "-c",
        "from pathlib import Path; Path('uploads').mkdir(); Path('uploads/report.txt').write_text('user work')",
    ], cwd=tmp_path, umask=0o022, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "uploads").stat().st_mode & 0o777 == 0o700
    assert (tmp_path / "uploads/report.txt").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("components", [[], "invalid", {"glasshive": []}, {"glasshive": "invalid"}, {"glasshive": {"native_bodies": []}}])
def test_native_body_inventory_rejects_malformed_structure(tmp_path, monkeypatch, components):
    runtime = load_native_runtime()
    monkeypatch.setattr(runtime, "build_metadata", lambda _root: {"components": components})
    with pytest.raises(runtime.RuntimeError_, match="inventory"):
        runtime.native_body_paths(tmp_path)


def test_native_harness_uses_packaged_bodies_and_compiled_route_without_host_credentials(tmp_path, monkeypatch):
    runtime = load_native_runtime(); root = tmp_path / "release"; support = tmp_path / "support"
    bodies = {"codex-cli": root / "codex", "claude-code": root / "claude"}
    monkeypatch.setattr(runtime, "native_body_paths", lambda _root: bodies)
    monkeypatch.setattr(runtime, "ensure_support_directories", lambda *_args: None)
    monkeypatch.setattr(runtime, "build_metadata", lambda _root: {"source_commit": "a" * 40, "components": {"glasshive": {"commit": "b" * 40}}})
    monkeypatch.setattr(runtime, "runtime_secrets", lambda *_args, **_kwargs: {"CREDS_KEY": "c" * 64})
    monkeypatch.setattr(runtime, "load_native_runtime_env", lambda _path: {
        "WPR_MODEL_CODEX_CLI": "selected-primary", "WPR_CODEX_CLI_REASONING_EFFORT": "medium",
        "WPR_MODEL_CLAUDE_CODE": "selected-fallback", "WPR_CLAUDE_CODE_EFFORT": "high",
        "GLASSHIVE_PROVIDER_ALLOW_FULL_ACCESS": "false", "OPENAI_API_KEY": "user_provided",
        "VIVENTIUM_PROMPT_BUNDLE_PATH": "/retired-build/prompt-bundle.json"})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "host-secret-must-not-leak")
    env = runtime.native_glasshive_environment(root, support)
    assert env["VIVENTIUM_PROMPT_BUNDLE_PATH"] == str(root / "runtime/defaults/prompt-bundle.json")
    assert env["WPR_CODEX_BIN"] == str(bodies["codex-cli"])
    assert env["WPR_CLAUDE_CODE_BIN"] == str(bodies["claude-code"])
    assert env["WPR_MODEL_CODEX_CLI"] == "selected-primary"
    assert env["WPR_CODEX_CLI_REASONING_EFFORT"] == "medium"
    assert env["WPR_MODEL_CLAUDE_CODE"] == "selected-fallback"
    assert env["WPR_CLAUDE_CODE_EFFORT"] == "high"
    assert env["GLASSHIVE_PROVIDER_ALLOW_FULL_ACCESS"] == "false"
    assert "OPENAI_API_KEY" not in env and "ANTHROPIC_API_KEY" not in env
    assert len({env[name] for name in ("WPR_API_TOKEN", "GLASSHIVE_PROVIDER_API_KEY", "GLASSHIVE_MCP_API_KEY", "VIVENTIUM_GLASSHIVE_SERVICE_ASSERTION_SECRET")}) == 4


def test_native_glasshive_socket_is_private_before_server_start(tmp_path):
    runtime = load_native_runtime()
    root = tmp_path / "release"
    file(root / "runtime/glasshive/site-packages/uvicorn.py", """
import os, stat
class Config:
    def __init__(self, *args, **kwargs): self.uds = kwargs['uds']
class Server:
    def __init__(self, config): self.config = config
    def run(self, *, sockets):
        assert len(sockets) == 1
        assert stat.S_IMODE(os.stat(self.config.uds).st_mode) == 0o600
        assert sockets[0].getsockname() == self.config.uds
""")
    support = Path(tempfile.mkdtemp(prefix="vi-private-uds-", dir="/private/tmp"))
    try:
        (support / "runtime").mkdir(mode=0o700)
        command = runtime.glasshive_server_command(root, support)
        command[0] = sys.executable
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert runtime.native_glasshive_socket_path(support).stat().st_mode & 0o777 == 0o600
    finally:
        shutil.rmtree(support)


def test_native_cleanup_drains_other_owned_services_after_socket_error(tmp_path, monkeypatch):
    runtime = load_native_runtime()
    stopped = []
    def stop_service(service, support, root):
        stopped.append(service)
        if service == "glasshive":
            raise runtime.RuntimeError_("unsafe socket remains untouched")
    monkeypatch.setattr(runtime, "stop_service", stop_service)
    with pytest.raises(runtime.RuntimeError_, match="glasshive: unsafe socket"):
        runtime.stop_attempt_services(tmp_path, tmp_path, {service: None for service in runtime.SERVICE_ORDER})
    assert stopped == list(reversed(runtime.SERVICE_ORDER))


def test_native_cortex_slot_is_stable_per_mutable_root(tmp_path, monkeypatch):
    runtime = load_native_runtime()
    monkeypatch.setenv("VIVENTIUM_RUNTIME_SLOT_ID", "foreign-runtime")
    slots = []
    for name in ("first", "second"):
        support = tmp_path / name
        file(support / "runtime/runtime.env", "\n".join(f"{key}={value}" for key, value in runtime.NATIVE_FIXED_ENV.items()))
        first = runtime.native_child_environment(support)["VIVENTIUM_RUNTIME_SLOT_ID"]
        assert runtime.native_child_environment(support)["VIVENTIUM_RUNTIME_SLOT_ID"] == first
        assert str(support) not in first
        assert first != "foreign-runtime"
        slots.append(first)
    assert slots[0] != slots[1]


def test_native_child_logs_use_private_mutable_support(tmp_path, monkeypatch):
    runtime = load_native_runtime()
    support = tmp_path / "support"
    file(support / "runtime/runtime.env", "\n".join(
        f"{key}={value}" for key, value in runtime.NATIVE_FIXED_ENV.items()))
    monkeypatch.setenv("LIBRECHAT_LOG_DIR", str(tmp_path / "foreign"))

    child = runtime.native_child_environment(support)

    logs = support / "logs/librechat"
    assert child["LIBRECHAT_LOG_DIR"] == str(logs)
    assert logs.is_dir()
    assert logs.stat().st_mode & 0o777 == 0o700
    assert not (tmp_path / "foreign").exists()


def test_native_child_files_use_the_existing_uploads_continuity_root(tmp_path, monkeypatch):
    runtime = load_native_runtime()
    support = tmp_path / "support"
    file(support / "runtime/runtime.env", "\n".join(
        f"{key}={value}" for key, value in runtime.NATIVE_FIXED_ENV.items()))
    monkeypatch.setenv("VIVENTIUM_LIBRECHAT_UPLOADS_ROOT", str(tmp_path / "foreign"))
    monkeypatch.setenv("VIVENTIUM_LIBRECHAT_IMAGE_OUTPUT_ROOT", str(tmp_path / "foreign-images"))

    child = runtime.native_child_environment(support)

    uploads = support / "data/uploads"
    images = uploads / "images"
    assert child["VIVENTIUM_LIBRECHAT_UPLOADS_ROOT"] == str(uploads)
    assert child["VIVENTIUM_LIBRECHAT_IMAGE_OUTPUT_ROOT"] == str(images)
    assert images.stat().st_mode & 0o777 == 0o700
    assert str(images.relative_to(support)).startswith("data/uploads/")
    assert "data/uploads" in runtime.NATIVE_RESTORE_ROOTS
    assert not (tmp_path / "foreign").exists()
    assert not (tmp_path / "foreign-images").exists()


def test_native_child_files_reject_external_image_symlink(tmp_path):
    runtime = load_native_runtime()
    support = tmp_path / "support"
    file(support / "runtime/runtime.env", "\n".join(
        f"{key}={value}" for key, value in runtime.NATIVE_FIXED_ENV.items()))
    outside = tmp_path / "outside"
    outside.mkdir()
    (support / "data/uploads").mkdir(parents=True)
    (support / "data/uploads/images").symlink_to(outside, target_is_directory=True)

    with pytest.raises(runtime.RuntimeError_, match="unsafe"):
        runtime.native_child_environment(support)
    assert list(outside.iterdir()) == []


def test_native_child_logs_reject_external_symlink(tmp_path):
    runtime = load_native_runtime()
    support = tmp_path / "support"
    file(support / "runtime/runtime.env", "\n".join(
        f"{key}={value}" for key, value in runtime.NATIVE_FIXED_ENV.items()))
    outside = tmp_path / "outside"
    outside.mkdir()
    (support / "logs").mkdir()
    (support / "logs/librechat").symlink_to(outside, target_is_directory=True)

    with pytest.raises(runtime.RuntimeError_, match="unsafe"):
        runtime.native_child_environment(support)
    assert list(outside.iterdir()) == []


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
        "GROQ_BASE_URL=https://api.groq.com/openai/v1/\n"
        "XAI_BASE_URL=https://api.x.ai/v1\n"
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
    assert "/login?redirect_to=%2Fc%2Fnew" in source
    assert "/login?setup=accounts" not in source
    assert "connect-src 'self'" in source
    assert "HttpOnly; SameSite=Strict" in source
    assert "function firstAdminCookie" in source
    assert "requestURL.pathname === '/register'" in source
    assert 'href="viventium://connect-ai"' in source
    assert 'href="/login?redirect_to=%2Fc%2Fnew"' in source
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
      find: () => ({limit: () => ({toArray: async () => [{_id: '0123456789abcdef' + '01234567'}]})}),
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
            with LOOPBACK_OPENER.open(value, timeout=3) as response:
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
                with LOOPBACK_OPENER.open(
                    f"http://127.0.0.1:{proxy_port}/__viventium_native_health", timeout=0.2
                ):
                    break
            except OSError:
                time.sleep(0.05)

        with LOOPBACK_OPENER.open(f"http://127.0.0.1:{sandpack_port}/", timeout=3) as response:
            assert response.status == 200
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert response.headers["Referrer-Policy"] == "no-referrer"
            assert response.headers["Content-Security-Policy"] == (
                "frame-ancestors http://127.0.0.1:3190"
            )
            assert b'IS_ONPREM:"true"' in response.read()
        with pytest.raises(urllib.error.HTTPError) as traversal:
            LOOPBACK_OPENER.open(
                f"http://127.0.0.1:{sandpack_port}/%2e%2e/%2e%2e/etc/passwd",
                timeout=3,
            )
        assert traversal.value.code in {403, 404}
        with pytest.raises(urllib.error.HTTPError) as method:
            LOOPBACK_OPENER.open(
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

        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)
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
        with LOOPBACK_OPENER.open(clean_page_request, timeout=3) as clean_page:
            page = clean_page.read().decode("utf-8")
            assert clean_page.status == 200
            assert "connect-src 'self'" in clean_page.headers["Content-Security-Policy"]
            assert 'name="confirm_password"' in page
            assert "/login?redirect_to=%2Fc%2Fnew" in page
            assert "setup%3Daccounts" not in page
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
                with LOOPBACK_OPENER.open(
                    f"http://127.0.0.1:{proxy_port}/__viventium_native_health", timeout=0.2
                ):
                    break
            except OSError:
                time.sleep(0.05)
        with pytest.raises(urllib.error.HTTPError) as response:
            LOOPBACK_OPENER.open(request, timeout=5)
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


def test_native_glasshive_proxy_retains_auth_owner_rejection_and_private_socket_boundary():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is unavailable")
    def free_port():
        with socket.socket() as handle:
            handle.bind(("127.0.0.1", 0))
            return handle.getsockname()[1]
    received = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append((self.path, dict(self.headers)))
            self.send_response(403 if self.headers.get("X-Viventium-Service-Assertion") == "foreign-owner" else 200)
            self.end_headers()
            self.wfile.write(b"owner boundary")
        def log_message(self, *_args):
            pass
    class UnixHTTPServer(HTTPServer):
        address_family = socket.AF_UNIX
    with tempfile.TemporaryDirectory(prefix="viv-gh-proxy-", dir="/private/tmp") as raw:
        base = Path(raw); support = base / "support"; runtime_dir = support / "runtime"
        runtime_dir.mkdir(parents=True, mode=0o700)
        servers = []
        proxy = None
        try:
            for name in ("librechat-api.sock", "glasshive.sock", "glasshive-mcp.sock", "scheduling.sock"):
                server = UnixHTTPServer(str(runtime_dir / name), Handler)
                (runtime_dir / name).chmod(0o600)
                thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
                servers.append((server, thread))
            release = base / "release"
            sandpack, digest = native_proxy_sandpack_fixture(release)
            state = file(support / "state/native-first-admin.json", json.dumps({"schema_version": 1, "status": "closed"}))
            hook = executable(base / "close-hook")
            port, artifact_port = free_port(), free_port()
            environment = {"PATH": "/usr/bin:/bin", "VIVENTIUM_NATIVE_RELEASE_ID": "e" * 40,
                "VIVENTIUM_NATIVE_RELEASE_ROOT": str(release), "VIVENTIUM_NATIVE_FIRST_ADMIN_STATE": str(state),
                "VIVENTIUM_NATIVE_PROXY_TARGET_SOCKET": str(runtime_dir / "librechat-api.sock"),
                "VIVENTIUM_NATIVE_PROXY_LISTEN_PORT": str(port), "VIVENTIUM_NATIVE_SANDPACK_LISTEN_PORT": str(artifact_port),
                "VIVENTIUM_NATIVE_SANDPACK_ROOT": str(sandpack), "VIVENTIUM_NATIVE_SANDPACK_INDEX_SHA256": digest,
                "VIVENTIUM_NATIVE_REGISTRATION_CLOSE_HOOK": str(hook), "VIVENTIUM_APP_SUPPORT_DIR": str(support),
                "VIVENTIUM_NATIVE_GLASSHIVE_SOCKET": str(runtime_dir / "glasshive.sock"),
                "VIVENTIUM_NATIVE_GLASSHIVE_MCP_SOCKET": str(runtime_dir / "glasshive-mcp.sock"),
                "WPR_API_TOKEN": "a" * 64, "GLASSHIVE_PROVIDER_API_KEY": "b" * 64, "GLASSHIVE_MCP_API_KEY": "c" * 64,
                "VIVENTIUM_NATIVE_SCHEDULING_SOCKET": str(runtime_dir / "scheduling.sock"),
                "SCHEDULING_MCP_API_KEY": "d" * 64, "SCHEDULER_LIBRECHAT_SECRET": "e" * 64}
            proxy = subprocess.Popen([node, str(NATIVE_PROXY)], env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            def request(path, headers=None):
                try:
                    with LOOPBACK_OPENER.open(urllib.request.Request(f"http://127.0.0.1:{port}" + path, headers=headers or {}), timeout=2) as response:
                        return response.status, response.read()
                except urllib.error.HTTPError as error:
                    return error.code, error.read()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    if request("/__viventium_native_health")[0] == 200: break
                except OSError: time.sleep(0.05)
            prefix = "/__viventium_native_glasshive/v1/work/work-1"
            for headers in ({}, {"Cookie": "session=synthetic"}, {"Authorization": "Bearer wrong"}):
                assert request(prefix, headers)[0] == 401
            assert received == []
            assert request(prefix, {"Authorization": "Bearer " + "a" * 64,
                                    "X-Viventium-Service-Assertion": "foreign-owner"})[0] == 403
            assert request(prefix + "?detail=1", {"Authorization": "Bearer " + "a" * 64,
                          "X-Viventium-Service-Assertion": "correct-owner", "Cookie": "session=synthetic"}) == (200, b"owner boundary")
            assert received[-1][0] == "/v1/work/work-1?detail=1"
            assert {key.lower(): value for key, value in received[-1][1].items()}["x-viventium-service-assertion"] == "correct-owner"
            assert not any(name.lower() == "cookie" for name in received[-1][1])
            assert request("/__viventium_native_glasshive_mcp/mcp", {"Authorization": "Bearer " + "a" * 64})[0] == 401
            assert request("/__viventium_native_glasshive_mcp/mcp", {"X-WPR-Token": "c" * 64})[0] == 200
            schedule_prefix = "/__viventium_native_scheduling/"
            for headers in ({}, {"Cookie": "session=synthetic"}, {"X-WPR-Token": "c" * 64},
                            {"X-Viventium-Scheduler-Secret": "e" * 64},
                            {"X-GlassHive-Signature": "synthetic"}):
                before = len(received)
                assert request(schedule_prefix + "mcp", headers)[0] == 401
                assert len(received) == before
            assert request(schedule_prefix + "mcp", {"Authorization": "Bearer " + "d" * 64})[0] == 200
            assert received[-1][0] == "/mcp"
            assert request(schedule_prefix + "internal/glasshive/recurring-schedules",
                           {"X-Viventium-Scheduler-Secret": "e" * 64})[0] == 200
            callback_path = "/internal/scheduled-prompts/glasshive-callback"
            before = len(received)
            assert request(callback_path, {"Cookie": "session=synthetic"})[0] == 401
            assert len(received) == before
            assert request(callback_path, {"X-GlassHive-Signature": "synthetic"})[0] == 200
            assert received[-1][0] == callback_path
            (runtime_dir / "scheduling.sock").chmod(0o666)
            assert request(schedule_prefix + "mcp", {"Authorization": "Bearer " + "d" * 64})[0] == 503
            before = len(received)
            (runtime_dir / "glasshive.sock").chmod(0o666)
            assert request(prefix, {"Authorization": "Bearer " + "b" * 64})[0] == 503
            assert len(received) == before
        finally:
            if proxy is not None:
                proxy.terminate(); proxy.wait(timeout=5)
            for server, thread in servers:
                server.shutdown(); server.server_close(); thread.join(timeout=2)


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
                LOOPBACK_OPENER.open(f"http://127.0.0.1:{proxy_port}/api/config", timeout=0.2)
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


@pytest.mark.parametrize("profile,arguments,expected", [
    ("codex-cli", [], ["login", "-c", 'cli_auth_credentials_store="file"']),
    ("codex-cli", ["--device-auth"], ["login", "--device-auth", "-c", 'cli_auth_credentials_store="file"']),
    ("codex-cli", ["--with-api-key"], ["login", "--with-api-key", "-c", 'cli_auth_credentials_store="file"']),
    ("claude-code", [], ["auth", "login"]),
    ("claude-code", ["--console"], ["auth", "login", "--console"]),
    ("claude-code", ["--sso"], ["auth", "login", "--sso"]),
])
def test_native_provider_auth_preserves_published_login_choices(tmp_path, monkeypatch, profile, arguments, expected):
    runtime = load_native_runtime()
    root, support = tmp_path / "release", tmp_path / "support"
    monkeypatch.setattr(runtime, "native_body_paths", lambda _: {"codex-cli": root / "codex", "claude-code": root / "claude"})
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-unselected")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "synthetic-unselected")
    command, env = runtime.native_provider_auth_command(root, support, profile, "login", arguments)
    assert command[1:] == expected
    assert command[0] == str(root / ("codex" if profile == "codex-cli" else "claude"))
    assert env["HOME"] == str(support / "runtime/glasshive-home")
    assert env["CODEX_HOME"] == str(support / "runtime/glasshive-home/.codex")
    assert not {"OPENAI_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "WPR_API_TOKEN"} & env.keys()
    assert Path(env["CODEX_HOME"]).stat().st_mode & 0o777 == 0o700


def test_native_provider_auth_parser_preserves_helper_lifecycle_options():
    runtime = load_native_runtime()
    command = runtime.parser().parse_args(["provider-auth", "codex-cli", "login", "--", "--device-auth"])
    assert command.provider == "codex-cli" and command.provider_arguments[-1] == "--device-auth"
    assert runtime.parser().parse_args(["start", "--respect-stopped"]).respect_stopped


def test_native_provider_auth_cancel_joins_only_its_child(tmp_path, monkeypatch):
    runtime = load_native_runtime()
    monkeypatch.setattr(runtime, "lifecycle_lock", lambda *_: contextlib.nullcontext())
    monkeypatch.setattr(runtime, "installed_release_root", lambda _: tmp_path)
    monkeypatch.setattr(runtime, "ensure_first_admin_state", lambda _: {"status": "closed", "admin_user_id": "a" * 24})
    monkeypatch.setattr(runtime, "native_provider_auth_command", lambda *_: (["/owned/provider", "login"], {"HOME": str(tmp_path)}))
    events = []
    class Child:
        def wait(self, **kwargs):
            events.append(("wait", kwargs))
            if not kwargs:
                raise KeyboardInterrupt()
            return 0
        def poll(self):
            return None
        def terminate(self):
            events.append(("terminate", {}))
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *_args, **_kwargs: Child())
    args = argparse.Namespace(app_support_dir=tmp_path, provider="codex-cli", action="login", provider_arguments=[])
    with pytest.raises(KeyboardInterrupt):
        runtime.provider_auth(args)
    assert events == [("wait", {}), ("terminate", {}), ("wait", {"timeout": 5})]


def test_native_provider_auth_refuses_incomplete_owner_before_launch(tmp_path, monkeypatch):
    runtime = load_native_runtime()
    monkeypatch.setattr(runtime, "lifecycle_lock", lambda *_: contextlib.nullcontext())
    monkeypatch.setattr(runtime, "installed_release_root", lambda _: tmp_path)
    monkeypatch.setattr(runtime, "ensure_first_admin_state", lambda _: {"status": "open"})
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *_args, **_kwargs: pytest.fail("must not launch provider"))
    args = argparse.Namespace(app_support_dir=tmp_path, provider="claude-code", action="login", provider_arguments=[])
    with pytest.raises(runtime.RuntimeError_, match="owner setup"):
        runtime.provider_auth(args)


@pytest.mark.parametrize("action,login_exit,status_exit,expected", [
    ("login", 1, 0, "did not complete"),
    ("logout", 0, 0, "disconnect was not verified"),
    ("logout", 0, 2, "disconnect was not verified"),
    ("logout", 0, -15, "disconnect was not verified"),
    ("logout", 0, "timeout", "disconnect status is unavailable"),
    ("logout", 0, "config_failure", "disconnect was not verified"),
    ("logout", 0, 1, None),
])
def test_native_provider_auth_lifecycle_failure_and_disconnect(tmp_path, monkeypatch, action, login_exit, status_exit, expected):
    runtime = load_native_runtime()
    monkeypatch.setattr(runtime, "lifecycle_lock", lambda *_: contextlib.nullcontext())
    monkeypatch.setattr(runtime, "installed_release_root", lambda _: tmp_path)
    monkeypatch.setattr(runtime, "ensure_first_admin_state", lambda _: {"status": "closed", "admin_user_id": "a" * 24})
    commands = []
    def command(_root, _support, _profile, operation, arguments):
        commands.append(operation)
        return ["/owned/provider", operation], {"HOME": str(tmp_path)}
    monkeypatch.setattr(runtime, "native_provider_auth_command", command)
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *_args, **_kwargs: type("Child", (), {"wait": lambda _: login_exit})())
    def status(*_args, **_kwargs):
        if status_exit == "timeout":
            raise subprocess.TimeoutExpired([], 10)
        if status_exit == "config_failure":
            return subprocess.CompletedProcess([], 1, stdout="", stderr="Invalid configuration")
        return subprocess.CompletedProcess([], status_exit, stdout="", stderr="Not logged in" if status_exit == 1 else "")
    monkeypatch.setattr(runtime.subprocess, "run", status)
    args = argparse.Namespace(app_support_dir=tmp_path, provider="codex-cli", action=action, provider_arguments=[])
    if expected:
        with pytest.raises(runtime.RuntimeError_, match=expected):
            runtime.provider_auth(args)
    else:
        runtime.provider_auth(args)
    assert commands == (["logout", "status"] if action == "logout" else ["login"])


def test_native_provider_auth_rejects_stale_installed_payload_before_login(tmp_path, monkeypatch):
    runtime = load_native_runtime()
    monkeypatch.setattr(runtime, "lifecycle_lock", lambda *_: contextlib.nullcontext())
    monkeypatch.setattr(runtime, "release_root", lambda: tmp_path / "old")
    monkeypatch.setattr(runtime, "runtime_state", lambda _: {"release_root": str(tmp_path / "current")})
    state = tmp_path / "state/native-runtime.json"
    state.parent.mkdir()
    state.write_text("{}")
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *_args, **_kwargs: pytest.fail("must not launch provider"))
    args = argparse.Namespace(app_support_dir=tmp_path, provider="codex-cli", action="login", provider_arguments=[])
    with pytest.raises(runtime.RuntimeError_, match="Installed release pointer"):
        runtime.provider_auth(args)


def test_native_scheduling_keeps_legacy_service_selection_and_separates_credentials(tmp_path, monkeypatch):
    runtime = load_native_runtime()
    root, support = tmp_path / "release", tmp_path / "support"
    metadata = {"components": {}}
    monkeypatch.setattr(runtime, "build_metadata", lambda _: metadata)
    monkeypatch.setattr(runtime, "runtime_secrets", lambda *_args, **_kwargs: {"CREDS_KEY": "a" * 64})
    assert runtime.release_services(root) == runtime.CORE_SERVICE_ORDER
    assert runtime.native_scheduling_environment(root, support) == {}
    metadata["components"]["scheduling"] = {"version": "0.1.0"}
    assert runtime.release_services(root) == (*runtime.CORE_SERVICE_ORDER, "scheduling")
    env = runtime.native_scheduling_environment(root, support)
    assert env["SCHEDULING_MCP_API_KEY"] != env["SCHEDULER_LIBRECHAT_SECRET"]
    assert env["VIVENTIUM_SCHEDULER_SECRET"] == env["SCHEDULER_LIBRECHAT_SECRET"]
    assert env["SCHEDULING_DB_PATH"] == str(support / "state/runtime/native/scheduling/schedules.db")
    assert env["SCHEDULING_MCP_URL"].endswith("/__viventium_native_scheduling/mcp")
    assert env["GLASSHIVE_SCHEDULING_OWNER_URL"] == env["SCHEDULING_MCP_URL"]
    assert (support / "state/runtime/native/scheduling").stat().st_mode & 0o777 == 0o700
    assert not any(name.startswith("OPENAI") or name.startswith("ANTHROPIC") for name in env)
    command = runtime.scheduling_server_command(root, support)
    assert command[:3] == [str(root / "runtime/python/bin/python3"), "-I", "-B"]
    assert command[-1] == str(support / "runtime/scheduling.sock")
    assert "--port" not in command


def test_native_redis_uses_private_persistent_store_and_preserves_legacy_service_state(tmp_path, monkeypatch):
    runtime = load_native_runtime()
    root, support = tmp_path / "release", tmp_path / "support"
    metadata = {"components": {}}
    monkeypatch.setattr(runtime, "build_metadata", lambda _: metadata)
    assert runtime.native_redis_environment(root, support) == {}
    metadata["components"]["redis"] = {"version": "7.2.15"}
    assert runtime.release_services(root) == ("mongodb", "redis", "librechat", "frontend-proxy")
    environment = runtime.native_redis_environment(root, support)
    assert environment["USE_REDIS_STREAMS"] == "true"
    assert environment["REDIS_SOCKET_PATH"] == str(support / "runtime/redis.sock")
    assert "REDIS_URI" not in environment
    command = runtime.native_redis_command(root, support)
    for option, expected in (("--port", "0"), ("--unixsocketperm", "600"),
                             ("--appendonly", "yes"), ("--appendfsync", "always")):
        assert command[command.index(option) + 1] == expected
    assert command[command.index("--dir") + 1] == str(support / "state/runtime/native/continuity/redis")
    for services in (runtime.CORE_SERVICE_ORDER, runtime.release_services(root), runtime.SERVICE_ORDER):
        assert runtime.validate_coherent_service_state(dict.fromkeys(services, 42)) == set(services)
    with pytest.raises(runtime.RuntimeError_, match="inconsistent"):
        runtime.validate_coherent_service_state({"mongodb": 42, "redis": 43})


def test_native_redis_rejects_changed_source_before_executing_build(tmp_path, monkeypatch):
    assembler = load_native_assembler(monkeypatch)
    archive = file(tmp_path / "redis.tar.gz", "untrusted archive")
    monkeypatch.setattr(assembler.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not build unverified archive"))
    with pytest.raises(assembler.AssemblyError, match="publisher policy"):
        assembler.stage_redis(archive, tmp_path / "output", {"source": {"sha256": "a" * 64}},
                              "arm64", source_date_epoch=1788624000)


def test_native_copy_excludes_customized_development_sources_only(tmp_path, monkeypatch):
    module = load_native_assembler(monkeypatch)
    source = tmp_path / "librechat"
    destination = tmp_path / "payload"
    kept = ["api/server/index.js", "client/dist/index.html", "packages/api/dist/index.js",
            "node_modules/vendor/test/entry.js", "node_modules/vendor/runtime.spec.js",
            "viventium/MCPs/scheduling-cortex/src/server.py"]
    excluded = ["client/src/main.tsx", "api/test/fixture.js", "api/server/foo.test.js",
                "packages/api/src/foo.spec.ts", "viventium/MCPs/scheduling-cortex/tests/test_server.py",
                "librechat.example.yaml", ".venv/bin/python"]
    for relative in kept + excluded:
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n")
    module.copy_safe(source, destination, boundary=source, source_date_epoch=1, customized_librechat=True)
    assert all((destination / relative).is_file() for relative in kept)
    assert all(not (destination / relative).exists() for relative in excluded)


def test_native_work_view_and_artifact_links_use_the_existing_proxy_origin(tmp_path, monkeypatch):
    runtime = load_native_runtime()
    monkeypatch.setattr(runtime, "native_body_paths", lambda *_: {"codex": tmp_path / "codex"})
    monkeypatch.setattr(runtime, "runtime_secrets", lambda *_: {"CREDS_KEY": "11" * 32})
    environment = runtime.native_glasshive_transport_environment(tmp_path / "release", tmp_path / "support")
    public_base = environment["GLASSHIVE_RUNTIME_PUBLIC_BASE_URL"]
    assert public_base == environment["WPR_MCP_BASE_URL"]
    assert public_base + "/v1" == environment["GLASSHIVE_PROVIDER_BASE_URL"]
    assert urllib.parse.urlparse(public_base + "/w/opaque-ref").path.startswith("/__viventium_native_glasshive/w/")
