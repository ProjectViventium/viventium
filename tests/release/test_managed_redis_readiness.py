"""Redis readiness uses a real command; every listener here is disposable."""
from __future__ import annotations

import importlib.util
import json
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import urllib.parse
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest


ROOT = Path(__file__).resolve().parents[2]
SUMMARY = ROOT / "scripts/viventium/install_summary.py"
HELPER = ROOT / "apps/macos/ViventiumHelper/Sources/ViventiumHelper/ViventiumHelperApp.swift"
PING = (b"PING",)
QUIT = (b"QUIT",)


@pytest.fixture
def summary():
    spec = importlib.util.spec_from_file_location("managed_redis_summary", SUMMARY)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _RespReader:
    def __init__(self, connection: socket.socket) -> None:
        self.connection = connection
        self.pending = b""

    def exact(self, count: int) -> bytes:
        while len(self.pending) < count:
            incoming = self.connection.recv(4096)
            if not incoming:
                raise EOFError
            self.pending += incoming
        result, self.pending = self.pending[:count], self.pending[count:]
        return result

    def line(self) -> bytes:
        while b"\r\n" not in self.pending:
            incoming = self.connection.recv(4096)
            if not incoming:
                raise EOFError
            self.pending += incoming
        result, self.pending = self.pending.split(b"\r\n", 1)
        return result

    def command(self) -> tuple[bytes, ...]:
        header = self.line()
        if not header.startswith(b"*"):
            raise ValueError("Expected a RESP command")
        parts = []
        for _ in range(int(header[1:])):
            size = self.line()
            if not size.startswith(b"$"):
                raise ValueError("Expected a RESP bulk string")
            parts.append(self.exact(int(size[1:])))
            if self.exact(2) != b"\r\n":
                raise ValueError("Invalid bulk string")
        return tuple(parts)


class _RedisListener:
    def __init__(self, listener: socket.socket, mode: str, auth: tuple[bytes, ...] | None,
                 tls_context: ssl.SSLContext | None = None) -> None:
        self.listener = listener
        self.mode = mode
        self.auth = auth
        self.tls_context = tls_context
        self.connections = 0
        self.commands: list[tuple[bytes, ...]] = []
        self.errors: list[Exception] = []
        self.stopped = threading.Event()
        self.listener.settimeout(0.05)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self) -> None:
        while not self.stopped.is_set():
            try:
                connection, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self.connections += 1
            if self.tls_context is not None:
                try:
                    connection.settimeout(1)
                    connection = self.tls_context.wrap_socket(connection, server_side=True)
                except (OSError, ssl.SSLError):
                    connection.close()
                    continue
            with connection:
                connection.settimeout(1)
                reader = _RespReader(connection)
                try:
                    while not self.stopped.is_set():
                        command = reader.command()
                        self.commands.append(command)
                        if command[0] == b"AUTH":
                            response = b"+OK\r\n" if command == self.auth else b"-WRONGPASS rejected\r\n"
                            connection.sendall(response)
                            continue
                        if command == QUIT:
                            connection.sendall(b"+OK\r\n")
                            break
                        if command != PING:
                            raise ValueError("Readiness issued a command other than AUTH/PING/QUIT")
                        mode = self.mode
                        if mode == "silent":
                            connection.settimeout(0.05)
                            while not self.stopped.is_set():
                                try:
                                    if not connection.recv(1):
                                        break
                                except socket.timeout:
                                    continue
                            break
                        if mode == "fragmented":
                            for part in (b"+", b"PO", b"NG", b"\r", b"\n"):
                                connection.sendall(part)
                                time.sleep(0.005)
                        elif mode == "error":
                            connection.sendall(b"-NOAUTH Authentication required\r\n")
                        elif mode == "wrong":
                            connection.sendall(b"+OK\r\n")
                        else:
                            connection.sendall(b"+PONG\r\n")
                except (EOFError, socket.timeout, ConnectionError, BrokenPipeError):
                    pass
                except Exception as exc:
                    self.errors.append(exc)

    def close(self) -> None:
        self.stopped.set()
        self.listener.close()
        self.thread.join(timeout=2)
        assert not self.thread.is_alive(), "Synthetic Redis listener did not stop"
        assert not self.errors, self.errors


@contextmanager
def redis_listener(
    *, mode: str = "pong", unix: bool = False, auth: tuple[bytes, ...] | None = None,
    tls_context: ssl.SSLContext | None = None,
) -> Iterator[tuple[_RedisListener, dict[str, str]]]:
    with tempfile.TemporaryDirectory(prefix="v-redis-") as temporary:
        listener = socket.socket(socket.AF_UNIX if unix else socket.AF_INET, socket.SOCK_STREAM)
        env = {"USE_REDIS": "true", "USE_REDIS_STREAMS": "true"}
        if unix:
            path = str(Path(temporary) / "r.sock")
            listener.bind(path)
            env["REDIS_SOCKET_PATH"] = path
            # The configured Unix transport remains authoritative over a stale TCP URI.
            env["REDIS_URI"] = "redis://127.0.0.1:1"
        else:
            listener.bind(("127.0.0.1", 0))
            scheme, host = ("rediss", "localhost") if tls_context is not None else ("redis", "127.0.0.1")
            env["REDIS_URI"] = f"{scheme}://{host}:{listener.getsockname()[1]}"
        listener.listen(4)
        server = _RedisListener(listener, mode, auth, tls_context)
        try:
            yield server, env
        finally:
            server.close()


@pytest.mark.parametrize("unix", [False, True], ids=["tcp", "native-unix"])
def test_ready_requires_an_actual_ping_response(summary, unix: bool) -> None:
    with redis_listener(unix=unix) as (server, env):
        assert summary.redis_protocol_ready(env, timeout=0.3)
        assert server.commands == [PING, QUIT]


def test_closed_port_is_unready_without_waiting_for_an_http_probe(summary) -> None:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    env = {"USE_REDIS": "true", "REDIS_URI": f"redis://127.0.0.1:{port}"}
    started = time.monotonic()
    assert not summary.redis_protocol_ready(env, timeout=0.15)
    assert time.monotonic() - started < 1.2


@pytest.mark.parametrize("unix", [False, True], ids=["tcp", "native-unix"])
def test_a_listening_but_nonresponding_dependency_is_bounded_and_recovers(summary, unix: bool) -> None:
    with redis_listener(mode="silent", unix=unix) as (server, env):
        started = time.monotonic()
        assert not summary.redis_protocol_ready(env, timeout=0.15)
        assert time.monotonic() - started < 1.2
        assert server.commands == [PING]
        server.mode = "pong"
        assert summary.redis_protocol_ready(env, timeout=0.3)
        assert server.commands == [PING, PING, QUIT]


@pytest.mark.parametrize("mode", ["wrong", "error"])
def test_any_response_other_than_pong_is_unready(summary, mode: str) -> None:
    with redis_listener(mode=mode) as (server, env):
        assert not summary.redis_protocol_ready(env, timeout=0.3)
        assert server.commands == [PING, QUIT]


def test_fragmented_pong_is_still_a_complete_successful_reply(summary) -> None:
    with redis_listener(mode="fragmented") as (server, env):
        assert summary.redis_protocol_ready(env, timeout=0.3)
        assert server.commands == [PING, QUIT]


@pytest.mark.parametrize("flags", [
    {}, {"USE_REDIS": "false", "USE_REDIS_STREAMS": "false"},
    {"USE_REDIS": "0", "USE_REDIS_STREAMS": "off"},
])
def test_disabled_redis_never_connects_to_an_old_configured_endpoint(summary, flags: dict[str, str]) -> None:
    with redis_listener() as (server, env):
        assert summary.redis_protocol_ready({**env, "USE_REDIS": "false", "USE_REDIS_STREAMS": "false", **flags})
        assert server.commands == []


@pytest.mark.parametrize("flag", ["USE_REDIS", "USE_REDIS_STREAMS"])
def test_either_active_consumer_requires_redis(summary, flag: str) -> None:
    assert not summary.redis_protocol_ready({flag: "true"}, timeout=0.15)


@pytest.mark.parametrize("uri", ["", "http://127.0.0.1:6381", "redis://", "redis://host:99999", "redis://127.0.0.1:0"])
def test_missing_or_unsupported_config_is_not_ready(summary, uri: str) -> None:
    assert not summary.redis_protocol_ready({"USE_REDIS": "true", "REDIS_URI": uri}, timeout=0.15)


@pytest.mark.parametrize("separate_credentials", [False, True], ids=["uri", "separate-env"])
def test_auth_is_read_only_and_credentials_do_not_enter_process_arguments_or_output(
    summary, monkeypatch, capsys, separate_credentials: bool,
) -> None:
    username, password = "readiness-user", "synthetic:p@ssword"
    auth = (b"AUTH", username.encode(), password.encode())
    process_arguments: list[list[str]] = []
    def capture_run(arguments, **kwargs):
        process_arguments.append(list(arguments))
        raise AssertionError("Portable readiness must not spawn a platform command")

    monkeypatch.setattr(summary.subprocess, "run", capture_run)
    with redis_listener(auth=auth) as (server, env):
        if separate_credentials:
            env.update(REDIS_USERNAME=username, REDIS_PASSWORD=password)
        else:
            env["REDIS_URI"] = env["REDIS_URI"].replace("redis://", "redis://readiness-user:synthetic%3Ap%40ssword@")
        assert summary.redis_protocol_ready(env, timeout=0.3)
        assert server.commands == [auth, PING, QUIT]
    captured = capsys.readouterr()
    for value in (username, password, "synthetic%3Ap%40ssword"):
        assert value not in repr(process_arguments)
        assert value not in captured.out + captured.err


@pytest.mark.parametrize("unix", [False, True])
def test_python_readiness_does_not_require_a_platform_netcat(summary, monkeypatch, unix: bool) -> None:
    def no_command(*_args, **_kwargs):
        raise AssertionError("Readiness must work without a platform command")

    monkeypatch.setattr(summary.subprocess, "run", no_command)
    with redis_listener(unix=unix) as (server, env):
        assert summary.redis_protocol_ready(env, timeout=0.3)
        assert server.commands == [PING, QUIT]


@pytest.fixture(scope="module")
def tls_contexts(tmp_path_factory):
    executable = shutil.which("openssl")
    if executable is None:
        pytest.skip("OpenSSL is required to create the disposable TLS certificate")
    folder = tmp_path_factory.mktemp("redis-tls")
    key, cert = folder / "key.pem", folder / "cert.pem"
    config = folder / "openssl.cnf"
    config.write_text("[req]\ndistinguished_name=dn\nx509_extensions=extensions\nprompt=no\n"
                      "[dn]\nCN=localhost\n[extensions]\nsubjectAltName=DNS:localhost\n")
    build = subprocess.run([executable, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                            "-keyout", str(key), "-out", str(cert), "-days", "1", "-config", str(config)],
                           capture_output=True, timeout=10)
    assert build.returncode == 0, "Disposable TLS certificate generation failed"
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(cert, key)
    client = ssl.create_default_context(cafile=str(cert))
    return server, client


def test_rediss_uses_verified_tls_and_the_same_authenticated_command_contract(summary, monkeypatch, tls_contexts) -> None:
    server_context, client_context = tls_contexts
    monkeypatch.setattr(summary.ssl, "create_default_context", lambda: client_context)
    with redis_listener(tls_context=server_context, auth=(b"AUTH", b"synthetic:secret")) as (server, env):
        env["REDIS_PASSWORD"] = "synthetic:secret"
        assert summary.redis_protocol_ready(env, timeout=1)
        assert server.commands == [(b"AUTH", b"synthetic:secret"), PING, QUIT]


def test_rediss_does_not_downgrade_when_the_certificate_is_untrusted(summary, tls_contexts) -> None:
    server_context, _client = tls_contexts
    with redis_listener(tls_context=server_context) as (server, env):
        assert not summary.redis_protocol_ready(env, timeout=1)
        assert server.commands == []


def test_auth_rejection_does_not_turn_into_a_successful_ping(summary) -> None:
    with redis_listener(auth=(b"AUTH", b"right")) as (server, env):
        env["REDIS_PASSWORD"] = "wrong"
        assert not summary.redis_protocol_ready(env, timeout=0.3)
        assert server.commands[0] == (b"AUTH", b"wrong")


def test_oversized_credentials_are_unready_before_spawning_or_connecting(summary, monkeypatch) -> None:
    password = "s" * 8192

    def no_spawn(*_args, **_kwargs):
        raise AssertionError("Oversized credentials must be rejected before starting a probe")

    monkeypatch.setattr(summary.subprocess, "run", no_spawn)
    with redis_listener(auth=(b"AUTH", password.encode())) as (server, env):
        started = time.monotonic()
        assert not summary.redis_protocol_ready({**env, "REDIS_PASSWORD": password}, timeout=0.15)
        assert time.monotonic() - started < 1.2
        assert server.connections == 0
        assert server.commands == []


def test_live_status_reports_dependency_failure_and_recovery_with_http_still_running(
    summary, monkeypatch, tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    config = {"install": {"experience": "express"}, "integrations": {"telegram": {"enabled": True}}}
    monkeypatch.setattr(summary, "http_ok", lambda _url: True)
    monkeypatch.setattr(summary, "local_network_host", lambda: None)
    monkeypatch.setattr(summary, "pid_file_process_running", lambda _path: True)
    original_probe = summary.redis_protocol_ready
    probes = []

    def bounded_probe(env, **_kwargs):
        probes.append(env)
        return original_probe(env, timeout=0.15)

    monkeypatch.setattr(summary, "redis_protocol_ready", bounded_probe)
    with redis_listener(mode="silent") as (server, env):
        rows = summary.build_service_rows(config, env, runtime_dir=runtime, probe_live=True)
        services = {name: (status, detail) for name, status, detail in rows}
        assert services["Redis"][0] == "Action Required"
        assert services["LibreChat API"][0] == "Running with issues"
        assert services["Telegram Bridge"][0] == "Running with issues"
        assert "Redis" in services["Telegram Bridge"][1]
        assert summary.resolve_summary_heading(True, rows, True)[0] == "Viventium needs attention"
        assert len(probes) == 1, "Consumers must share this summary's dependency result"
        server.mode = "pong"
        recovered = summary.build_service_rows(config, env, runtime_dir=runtime, probe_live=True)
        recovered_services = {name: status for name, status, _detail in recovered}
        assert recovered_services["Redis"] == "Running"
        assert recovered_services["LibreChat API"] == "Running"
        assert recovered_services["Telegram Bridge"] == "Running"
        assert len(probes) == 2


def test_configured_summary_does_not_probe_or_claim_a_live_dependency(summary, monkeypatch) -> None:
    def no_probe(*_args, **_kwargs):
        raise AssertionError("Configured-only summary performed a live command")

    monkeypatch.setattr(summary, "redis_protocol_ready", no_probe)
    monkeypatch.setattr(summary, "local_network_host", lambda: None)
    rows = summary.build_service_rows({}, {"USE_REDIS": "true", "REDIS_URI": "redis://127.0.0.1:1"}, probe_live=False)
    assert next(status for name, status, _detail in rows if name == "Redis") == "Configured"


@pytest.fixture(scope="module")
def helper_probe(tmp_path_factory):
    """Compile the owning Swift readiness methods, retaining their real bounded nc call."""
    directory = tmp_path_factory.mktemp("redis-helper")
    source = HELPER.read_text()
    runtime = "private struct RuntimePorts:" + source.split("private struct RuntimePorts:", 1)[1].split(
        "private extension HelperController", 1,
    )[0]
    snapshot = "private struct StackHealthSnapshot" + source.split("private struct StackHealthSnapshot", 1)[1].split(
        "private struct HealWorkflowSettings", 1,
    )[0]
    readiness = "    nonisolated static func managedServicesRunning(runtime:" + source.split(
        "    nonisolated static func managedServicesRunning(runtime:", 1,
    )[1].split("    nonisolated static func stackOwnedByDifferentRepo(", 1)[0]
    bounded_process = "    private nonisolated static func runSystemProcess(" + source.split(
        "    private nonisolated static func runSystemProcess(", 1,
    )[1].split("    private nonisolated static func launchAtLoginFastPathEnabled()", 1)[0]
    harness = directory / "readiness.swift"
    harness.write_text("import Foundation\nimport Darwin\n" + runtime + snapshot +
        "\nprivate class HelperController {\n" + readiness + bounded_process + r'''
    static var httpMode = "healthy"
    static func firstHTTPStatus(urls: [URL]) async -> Int? {
        let local = ["localhost", "127.0.0.1", "::1"].contains(urls.first?.host ?? "")
        if self.httpMode == "local-missing" && local { return nil }
        if self.httpMode == "local-503" && local { return 503 }
        if self.httpMode == "remote-missing" && !local { return nil }
        return 200
    }
    static func candidateURLs(for url: URL) -> [URL] { [url] }
}
@main struct Probe {
    static func main() async throws {
        let support = CommandLine.arguments[1]
        HelperController.httpMode = CommandLine.arguments[2]
        let runtime = RuntimeEnvParser().readRuntime(appSupportDir: support)
        let readiness = await HelperController.managedServicesReadiness(runtime: runtime)
        let ready = readiness.ready
        let running = await HelperController.managedServicesRunning(runtime: runtime)
        let snapshot = StackHealthSnapshot(apiReady: true, frontendReady: true,
            playgroundReady: false, requiresPlayground: false, optionalSurfacesReady: ready,
            allLocalServicesRunning: readiness.allLocalServicesRunning)
        let values = RuntimeEnvParser().readRuntimeValues(appSupportDir: support)
        let arguments = runtime.redisReadiness?.arguments ?? []
        let endpoint = URLComponents(string: values["REDIS_URI"] ?? "")
        let credentials = [values["REDIS_USERNAME"], values["REDIS_PASSWORD"], endpoint?.user, endpoint?.password].compactMap { $0 }.filter { !$0.isEmpty }
        let safeArguments = credentials.allSatisfy { secret in !arguments.contains { $0.contains(secret) } }
        let result: [String: Bool] = ["ready": ready, "running": running,
            "coreHealthy": snapshot.coreHealthy, "needsAttention": snapshot.needsAttention,
            "credentialArgsSafe": safeArguments, "allLocalServicesRunning": snapshot.allLocalServicesRunning]
        print(String(data: try JSONSerialization.data(withJSONObject: result), encoding: .utf8)!)
    }
}
''')
    executable = directory / "readiness"
    build = subprocess.run(["xcrun", "swiftc", "-parse-as-library", str(harness), "-o", str(executable)],
                           capture_output=True, text=True, timeout=60)
    assert build.returncode == 0, build.stderr

    def run(env: dict[str, str], http_mode: str = "healthy") -> dict[str, bool]:
        runtime_dir = directory / "support/runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        values = {"START_GLASSHIVE": "true", "VIVENTIUM_VOICE_ENABLED": "false", **env}
        (runtime_dir / "runtime.env").write_text("".join(f"{key}={value}\n" for key, value in values.items()))
        started = time.monotonic()
        result = subprocess.run([str(executable), str(runtime_dir.parent), http_mode], capture_output=True, text=True, timeout=5)
        assert time.monotonic() - started < 3.5, "Managed readiness exceeded its bounded probe budget"
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    return run


@pytest.mark.parametrize("unix", [False, True], ids=["tcp", "native-unix"])
def test_helper_reports_attention_without_granting_stop_authority_and_recovers(helper_probe, unix: bool) -> None:
    with redis_listener(mode="silent", unix=unix) as (server, env):
        failed = helper_probe(env)
        assert failed == {"ready": False, "running": True, "coreHealthy": True,
                          "needsAttention": True, "credentialArgsSafe": True,
                          "allLocalServicesRunning": True}
        server.mode = "pong"
        assert helper_probe(env) == {**failed, "ready": True, "needsAttention": False}


def test_helper_disabled_dependency_does_not_inherit_a_stale_endpoint(helper_probe) -> None:
    with redis_listener() as (server, env):
        result = helper_probe({**env, "USE_REDIS": "false", "USE_REDIS_STREAMS": "false"})
        assert result["ready"]
        assert not result["needsAttention"]
        assert server.commands == []


@pytest.mark.parametrize("separate_credentials", [False, True], ids=["uri", "separate-env"])
def test_helper_authenticates_without_putting_credentials_in_nc_arguments(helper_probe, separate_credentials: bool) -> None:
    username, password = "readiness-user", "synthetic:p@ssword"
    with redis_listener(auth=(b"AUTH", username.encode(), password.encode())) as (server, env):
        if separate_credentials:
            env.update(REDIS_USERNAME=username, REDIS_PASSWORD=password)
        else:
            env["REDIS_URI"] = env["REDIS_URI"].replace("redis://", "redis://readiness-user:synthetic%3Ap%40ssword@")
        result = helper_probe(env)
        assert result["ready"] and result["credentialArgsSafe"]
        assert server.commands == [(b"AUTH", username.encode(), password.encode()), PING, QUIT]


def test_python_and_helper_decode_the_same_escaped_uri_credentials(summary, helper_probe) -> None:
    username, password = "readiness+u:sér", "synthetic:100%+word@"
    auth = (b"AUTH", username.encode(), password.encode())
    with redis_listener(auth=auth) as (server, env):
        credentials = urllib.parse.quote(username, safe="") + ":" + urllib.parse.quote(password, safe="")
        env["REDIS_URI"] = env["REDIS_URI"].replace("redis://", "redis://" + credentials + "@")
        assert summary.redis_protocol_ready(env, timeout=0.3)
        result = helper_probe(env)
        assert result["ready"] and result["credentialArgsSafe"]
        assert server.commands == [auth, PING, QUIT, auth, PING, QUIT]


def test_helper_oversized_credentials_are_bounded_and_do_not_connect(helper_probe) -> None:
    password = "s" * 8192
    with redis_listener(auth=(b"AUTH", password.encode())) as (server, env):
        result = helper_probe({**env, "REDIS_PASSWORD": password})
        assert not result["ready"]
        assert result["needsAttention"] and result["running"]
        assert server.connections == 0
        assert server.commands == []


@pytest.mark.parametrize("http_mode,all_local_running", [
    ("local-missing", False), ("local-503", True), ("remote-missing", True),
])
def test_helper_collector_distinguishes_missing_local_process_from_degraded_or_remote_dependency(
    helper_probe, http_mode: str, all_local_running: bool,
) -> None:
    result = helper_probe({"USE_REDIS": "false", "USE_REDIS_STREAMS": "false",
                           "START_SCHEDULING_MCP": "true",
                           "SCHEDULING_MCP_URL": "https://remote.example.invalid/mcp"}, http_mode=http_mode)
    assert not result["ready"] and result["needsAttention"]
    assert result["allLocalServicesRunning"] == all_local_running
    assert result["running"] == all_local_running
