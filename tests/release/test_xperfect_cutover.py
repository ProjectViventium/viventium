"""The new component never adopts or modifies the retained GlassHive checkout."""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "viventium_v0_4/viventium-librechat-start.sh"


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def shell_function(name: str) -> str:
    source = LAUNCHER.read_text()
    start = source.index(name + "() {\n")
    end = source.index("\n}\n", start) + 3
    return source[start:end] + "\n"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          text=True, capture_output=True).stdout.strip()


def make_repo(path: Path, text: str) -> str:
    path.mkdir(parents=True)
    git(path, "init")
    (path / "component.txt").write_text(text)
    git(path, "add", "component.txt")
    git(path, "-c", "user.name=Synthetic QA", "-c", "user.email=qa@example.invalid",
        "commit", "-m", "Synthetic component")
    return git(path, "rev-parse", "HEAD")


def test_legacy_config_bootstraps_xperfect_without_touching_old_checkout(tmp_path):
    module = load_module("xperfect_bootstrap", "scripts/viventium/bootstrap_components.py")
    old = tmp_path / "installed/viventium_v0_4/GlassHive"
    old_sha = make_repo(old, "retained original\n")
    git(old, "remote", "add", "origin", "https://github.com/example/retained.git")
    (old / "component.txt").write_text("uncommitted original work\n")
    (old / "untracked.txt").write_text("retained untracked work\n")
    before = {p.relative_to(old).as_posix(): p.read_bytes()
              for p in old.rglob("*") if p.is_file()}
    source = tmp_path / "source"
    pin = make_repo(source, "new xPerfect\n")
    new = {"name": "xPerfect", "path": "viventium_v0_4/xPerfect", "origin": str(source), "ref": pin}
    legacy = {"name": "GlassHive", "path": "viventium_v0_4/GlassHive",
              "origin": "https://github.com/example/retained.git", "ref": old_sha}
    selected = module.select_components([legacy, new], {"integrations": {"glasshive": {"enabled": True}}})
    assert selected == [new]
    module.clone_or_update_component(tmp_path / "installed", selected[0], True)
    installed = tmp_path / "installed/viventium_v0_4/xPerfect"
    assert git(installed, "rev-parse", "HEAD") == pin
    assert git(installed, "remote", "get-url", "origin") == str(source)
    assert {p.relative_to(old).as_posix(): p.read_bytes()
            for p in old.rglob("*") if p.is_file()} == before
    assert module.select_components([legacy, new], {"integrations": {"glasshive": {"enabled": False}}}) == []


def component_asgi_kind(target: str) -> str:
    """How the selected component defines a uvicorn target: a factory, an app, or not at all."""
    module, _, name = target.partition(":")
    source = ROOT / "viventium_v0_4/xPerfect/runtime_phase1/src" / (module.replace(".", "/") + ".py")
    for node in ast.parse(source.read_text()).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "factory"
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(item, ast.Name) and item.id == name for item in targets):
            return "app"
    return "missing"


def uvicorn_command_target(line: str) -> tuple[str, bool]:
    argv = shlex.split(line)
    return next(arg for arg in argv if arg.startswith("workers_projects_runtime.api:")), "--factory" in argv


@pytest.mark.parametrize("launcher", ["native", "systemd", "source"])
def test_every_runtime_launcher_names_an_app_the_selected_component_defines(launcher):
    # A stub uvicorn accepts any target; resolve each launcher's target in the real component.
    if launcher == "native":
        runtime = load_module("xperfect_native_runtime", "scripts/viventium/native_runtime.py")
        code = runtime.glasshive_server_command(Path("/release"), Path("/support"))[4]
        config = next(node for node in ast.walk(ast.parse(code))
                      if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "Config")
        target = config.args[0].value
        factory = any(item.arg == "factory" and item.value.value is True for item in config.keywords)
    elif launcher == "systemd":
        unit = (ROOT / "deploy/glasshive/systemd/glasshive-runtime.service").read_text()
        target, factory = uvicorn_command_target(next(line for line in unit.splitlines() if line.startswith("ExecStart=")))
    else:
        target, factory = uvicorn_command_target(next(
            line for line in LAUNCHER.read_text().splitlines()
            if "uv run uvicorn workers_projects_runtime.api:" in line and "kill_by_pattern" not in line))
    assert component_asgi_kind(target) == ("factory" if factory else "app")


def test_healthy_foreign_listeners_are_not_reused(tmp_path):
    # A healthy HTTP payload is not proof that the selected source is serving it.
    script = "set -eu\n" + shell_function("glasshive_stack_ready") + """
GLASSHIVE_RUNTIME_PORT=18766
GLASSHIVE_MCP_PORT=18767
GLASSHIVE_UI_PORT=18780
GLASSHIVE_SERVICE_TOPOLOGY=local
GLASSHIVE_RUNTIME_DIR=/synthetic/xPerfect/runtime_phase1
GLASSHIVE_UI_DIR=/synthetic/xPerfect/frontends/glass-drive-ui
curl() { if [[ "$*" == *http_code* ]]; then printf '400'; else printf '{"status":"ok"}'; fi; }
glasshive_local_listener_matches() { return 1; }
if glasshive_stack_ready; then exit 9; fi
"""
    result = subprocess.run(["bash", "-c", script], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


@pytest.fixture
def process_identity(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts/viventium"))
    return load_module("xperfect_process_identity_tests", "scripts/viventium/xperfect_process_identity.py")


@pytest.fixture
def listening_service(tmp_path):
    import socket
    children = []

    def start(service, *, component="xPerfect", target=None, wrapper=False, extra_options=()):
        component_root = tmp_path / component
        service_root = component_root / ("frontends/glass-drive-ui" if service == "ui" else "runtime_phase1")
        service_root.mkdir(parents=True, exist_ok=True)
        python = service_root / ".venv/bin/python"
        python.parent.mkdir(parents=True, exist_ok=True)
        if not python.exists():
            python.symlink_to(sys.executable)
        code = """import socket, sys, time
port = int(sys.argv[sys.argv.index('--port') + 1])
with socket.socket() as listener:
    listener.bind(('127.0.0.1', port))
    listener.listen()
    print('ready', flush=True)
    time.sleep(60)
"""
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        if service == "mcp":
            package = service_root / "workers_projects_runtime"
            package.mkdir(exist_ok=True)
            (package / "__init__.py").write_text("")
            (package / "mcp_server.py").write_text(code)
            argv = [str(python), "-m", "workers_projects_runtime.mcp_server"]
        else:
            (service_root / "uvicorn.py").write_text(code)
            default_target = "glass_drive_ui.server:app" if service == "ui" else "workers_projects_runtime.api:create_app"
            argv = [str(python), "-m", "uvicorn", target or default_target]
            if wrapper:
                entrypoint = python.parent / "uvicorn"
                entrypoint.write_text(f"#!{python}\n" + code)
                entrypoint.chmod(0o755)
                argv = [str(entrypoint), target or default_target]
            if service == "runtime":
                argv.append("--factory")
        argv.extend(["--port", str(port), *extra_options])
        child = subprocess.Popen(argv, cwd=service_root, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
        children.append(child)
        assert child.stdout and child.stdout.readline().strip() == "ready"
        return child, component_root, port

    yield start
    for child in children:
        child.terminate()
        child.communicate(timeout=5)


@pytest.mark.parametrize("service", ["runtime", "mcp", "ui"])
def test_listener_identity_requires_exact_checkout_service_and_port(process_identity, listening_service, tmp_path, service):
    child, root, port = listening_service(service)
    assert process_identity.service_process_matches(child.pid, root, service, port)
    assert not process_identity.service_process_matches(child.pid, root, service, port + 1)
    assert not process_identity.service_process_matches(child.pid, root, "ui" if service != "ui" else "runtime", port)
    legacy_child, legacy_root, legacy_port = listening_service(service, component="GlassHive")
    assert not process_identity.service_process_matches(legacy_child.pid, root, service, legacy_port)
    child.terminate()
    child.wait(timeout=5)
    assert not process_identity.service_process_matches(child.pid, root, service, port)


@pytest.mark.parametrize("service", ["runtime", "ui"])
def test_listener_in_expected_directory_with_foreign_entrypoint_is_rejected(process_identity, listening_service, service):
    child, root, port = listening_service(service, target="other_service:app")
    assert not process_identity.service_process_matches(child.pid, root, service, port)


@pytest.mark.parametrize("listeners", ["", "123\n456"])
def test_listener_discovery_fails_closed_when_absent_or_ambiguous(listeners):
    script = "set -eu\n" + shell_function("glasshive_local_listener_matches")
    script += f"find_port_listener_pids() {{ printf '%s\\n' {shlex.quote(listeners)}; }}\n"
    script += "PYTHON_BIN=false\nGLASSHIVE_DIR=/synthetic/xPerfect\nVIVENTIUM_CORE_DIR=/synthetic\n"
    script += "if glasshive_local_listener_matches 18766 runtime; then exit 9; fi\n"
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("restart", ["true", "false"])
def test_start_never_stops_foreign_listener_even_when_restart_requested(tmp_path, restart):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    script = "set -eu\n" + shell_function("glasshive_local_ports_owned") + shell_function("start_glasshive") + f"""
START_GLASSHIVE=true
GLASSHIVE_RUNTIME_DIR={shlex.quote(str(runtime))}
GLASSHIVE_HTTP_REQUEST_HEAD_MAX_BYTES=65536
GLASSHIVE_HTTP_REQUEST_HEAD_MIN_BYTES=16384
GLASSHIVE_RUNTIME_PORT=18766
GLASSHIVE_MCP_PORT=18767
GLASSHIVE_UI_PORT=18780
RESTART_SERVICES={restart}
load_local_qa_runtime_control() {{ :; }}
log_error() {{ :; }}
log_warn() {{ :; }}
port_in_use() {{ return 0; }}
glasshive_local_listener_matches() {{ return 1; }}
glasshive_stack_ready() {{ return 0; }}
stop_pid_file_scoped() {{ exit 8; }}
kill_port_listeners() {{ exit 8; }}
if start_glasshive; then exit 9; fi
"""
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_external_split_health_does_not_require_local_checkout_ownership():
    script = "set -eu\n" + shell_function("glasshive_runtime_healthy") + """
GLASSHIVE_SERVICE_TOPOLOGY=external_split
GLASSHIVE_RUNTIME_BASE_URL=http://runtime.example.invalid
viventium_glasshive_runtime_healthy() { return 0; }
glasshive_local_listener_matches() { exit 8; }
glasshive_runtime_healthy
"""
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_local_source_override_uses_new_component_path_only(tmp_path):
    module = load_module("xperfect_source_override", "scripts/viventium/bootstrap_components.py")
    old = tmp_path / "viventium_v0_4/GlassHive/.git"
    old.mkdir(parents=True)
    component = {"name": "xPerfect", "path": "viventium_v0_4/xPerfect", "origin": "https://github.com/xPerfectAI/xPerfect.git", "ref": "a" * 40}
    assert module.apply_local_origin_overrides([component], tmp_path) == [component]
    new = tmp_path / component["path"]
    (new / ".git").mkdir(parents=True)
    assert module.apply_local_origin_overrides([component], tmp_path)[0]["origin"] == str(new)


def test_missing_new_checkout_never_bootstraps_the_retained_old_one(tmp_path):
    module = load_module("xperfect_missing_source", "scripts/viventium/bootstrap_components.py")
    old = tmp_path / "installed/viventium_v0_4/GlassHive"
    make_repo(old, "original\n")
    before = {p.relative_to(old).as_posix(): p.read_bytes() for p in old.rglob("*") if p.is_file()}
    component = {"name": "xPerfect", "path": "viventium_v0_4/xPerfect", "origin": str(tmp_path / "unavailable"), "ref": "a" * 40}
    with pytest.raises(subprocess.CalledProcessError):
        module.clone_or_update_component(tmp_path / "installed", component, True)
    assert before == {p.relative_to(old).as_posix(): p.read_bytes() for p in old.rglob("*") if p.is_file()}


def test_watchdog_teardown_never_stops_foreign_listener():
    script = "set -eu\n" + shell_function("stop_candidate_glasshive_stack") + """
glasshive_local_ports_owned() { return 1; }
stop_pid_file_scoped() { exit 8; }
kill_port_listeners() { exit 8; }
if stop_candidate_glasshive_stack; then exit 9; fi
"""
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("service", ["runtime", "mcp", "ui"])
def test_shell_listener_check_accepts_exact_real_service(listening_service, service):
    child, root, port = listening_service(service)
    script = "set -eu\n" + shell_function("find_port_listener_pids") + shell_function("glasshive_local_listener_matches")
    script += f"PYTHON_BIN={shlex.quote(sys.executable)}\nVIVENTIUM_CORE_DIR={shlex.quote(str(ROOT))}\nGLASSHIVE_DIR={shlex.quote(str(root))}\n"
    script += f"glasshive_local_listener_matches {port} {service}\n"
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_symlink_to_old_checkout_cannot_claim_new_identity(process_identity, listening_service, tmp_path):
    child, old_root, port = listening_service("runtime", component="GlassHive")
    alias = tmp_path / "xPerfect"
    alias.symlink_to(old_root, target_is_directory=True)
    assert not process_identity.service_process_matches(child.pid, alias, "runtime", port)


@pytest.mark.parametrize("service", ["runtime", "ui"])
def test_deployed_uvicorn_wrapper_has_exact_listener_identity(process_identity, listening_service, service):
    child, root, port = listening_service(service, wrapper=True)
    assert process_identity.service_process_matches(child.pid, root, service, port)


@pytest.mark.skipif(sys.platform != "darwin", reason="framework interpreters are macOS-only")
def test_framework_interpreter_reexec_keeps_exact_listener_identity(process_identity, tmp_path, monkeypatch):
    # A framework python3.x re-executes Resources/Python.app and passes that path as argv[0].
    framework = tmp_path / "Python.framework/Versions/3.12"
    app = framework / "Resources/Python.app/Contents/MacOS/Python"
    foreign_app = tmp_path / "Other.framework/Versions/3.12/Resources/Python.app/Contents/MacOS/Python"
    for path in (framework / "bin/python3.12", app, foreign_app):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    root = tmp_path / "xPerfect"
    service_root = root / "runtime_phase1"
    (service_root / ".venv/bin").mkdir(parents=True)
    (service_root / ".venv/bin/python").symlink_to(framework / "bin/python3.12")
    port = 18766
    arguments = ("-m", "uvicorn", "workers_projects_runtime.api:create_app", "--factory", "--port", str(port))
    observed = {"value": (app.resolve(), (str(app), *arguments))}
    monkeypatch.setattr(process_identity.process_inspector, "_live_process_image_and_argv",
                        lambda pid: observed["value"])
    monkeypatch.setattr(process_identity.process_inspector, "_process_cwd", lambda pid: service_root.resolve())
    assert process_identity.service_process_matches(4242, root, "runtime", port)
    observed["value"] = (foreign_app.resolve(), (str(foreign_app), *arguments))
    assert not process_identity.service_process_matches(4242, root, "runtime", port)
    observed["value"] = (app.resolve(), (str(foreign_app), *arguments))
    assert not process_identity.service_process_matches(4242, root, "runtime", port)


def test_duplicate_port_option_cannot_claim_listener_identity(process_identity, listening_service):
    child, root, port = listening_service("runtime", extra_options=("--port", "12345"))
    assert not process_identity.service_process_matches(child.pid, root, "runtime", port)


def test_git_helper_status_does_not_rewrite_retained_original(tmp_path):
    root = tmp_path / "workspace"
    make_repo(root, "parent\n")
    old = root / "viventium_v0_4/GlassHive"
    make_repo(old, "original\n")
    git(old, "remote", "add", "origin", "https://github.com/example/retained.git")
    (old / "component.txt").write_text("uncommitted work\n")
    before = {p.relative_to(old).as_posix(): p.read_bytes() for p in old.rglob("*") if p.is_file()}
    (root / "git-helper.sh").write_bytes((ROOT / "git-helper.sh").read_bytes())
    manifest = root / "devops/git/repos.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes((ROOT / "devops/git/repos.json").read_bytes())
    git(root, "remote", "add", "origin", "https://github.com/ProjectViventium/viventium.git")
    for entry in json.loads(manifest.read_text())["repos"]:
        component = root / entry["path"]
        make_repo(component, "managed component\n")
        git(component, "remote", "add", "origin", entry["origin"])
    result = subprocess.run(["bash", str(root / "git-helper.sh"), "status"],
                            cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "[xPerfect]" in result.stdout
    assert "[GlassHive]" not in result.stdout
    assert before == {p.relative_to(old).as_posix(): p.read_bytes() for p in old.rglob("*") if p.is_file()}
