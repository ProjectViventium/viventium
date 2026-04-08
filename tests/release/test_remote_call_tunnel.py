from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import types
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "viventium" / "remote_call_tunnel.py"


def load_module():
    spec = importlib.util.spec_from_file_location("remote_call_tunnel", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_state_is_healthy_requires_live_targets_and_public_urls(monkeypatch) -> None:
    module = load_module()
    probed_urls: list[str] = []

    monkeypatch.setattr(module, "pid_is_running", lambda _pid: True)

    def fake_probe(url: str | None, timeout_seconds: float = 4.0) -> bool:
        assert timeout_seconds == module.DEFAULT_HEALTH_TIMEOUT_SECONDS
        if url:
            probed_urls.append(url)
        return True

    monkeypatch.setattr(module, "probe_local_endpoint", fake_probe)

    state = {
        "provider": "cloudflare_quick_tunnel",
        "playground": {
            "pid": 123,
            "target": "http://localhost:3300",
            "public_url": "https://voice.example.trycloudflare.com",
        },
        "livekit": {
            "pid": 456,
            "target": "http://localhost:7888",
            "public_url": "https://livekit.example.trycloudflare.com",
        },
        "public_playground_url": "https://voice.example.trycloudflare.com",
        "public_livekit_url": "wss://livekit.example.trycloudflare.com",
    }

    assert module.state_is_healthy(state) is True
    assert probed_urls == [
        "http://localhost:3300",
        "http://localhost:7888",
    ]


def test_state_is_healthy_for_tailscale_requires_provider_state(monkeypatch) -> None:
    module = load_module()

    monkeypatch.setattr(module, "probe_local_endpoint", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(module, "tailscale_state_ready", lambda _state: True)

    state = {
        "provider": "tailscale_tailnet_https",
        "client": {
            "target": "http://localhost:3190",
            "public_url": "https://home-node.tail123.ts.net",
        },
        "api": {
            "target": "http://localhost:3180",
            "public_url": "https://home-node.tail123.ts.net:8443",
        },
        "public_client_url": "https://home-node.tail123.ts.net",
        "public_api_url": "https://home-node.tail123.ts.net:8443",
    }

    assert module.state_is_healthy(state) is True


def test_parse_timeout_seconds_prefers_positive_env_values() -> None:
    module = load_module()

    assert module.parse_timeout_seconds("180") == 180
    assert module.parse_timeout_seconds("0") == module.DEFAULT_REMOTE_CALL_TUNNEL_TIMEOUT_SECONDS
    assert module.parse_timeout_seconds("not-a-number") == module.DEFAULT_REMOTE_CALL_TUNNEL_TIMEOUT_SECONDS


def test_resolve_binary_falls_back_to_known_homebrew_paths(monkeypatch, tmp_path: Path) -> None:
    module = load_module()
    fake_bin = tmp_path / "cloudflared"
    fake_bin.write_text("", encoding="utf-8")

    monkeypatch.setattr(module.shutil, "which", lambda _name: None)
    monkeypatch.setitem(module.COMMON_BINARY_PATHS, "cloudflared", (str(fake_bin),))

    assert module.resolve_binary("cloudflared") == str(fake_bin)


def test_state_is_healthy_rejects_dead_local_target(monkeypatch) -> None:
    module = load_module()

    monkeypatch.setattr(module, "pid_is_running", lambda _pid: True)

    def fake_probe(url: str | None, timeout_seconds: float = 4.0) -> bool:
        if url == "http://localhost:3300":
            return False
        return True

    monkeypatch.setattr(module, "probe_local_endpoint", fake_probe)

    state = {
        "provider": "cloudflare_quick_tunnel",
        "playground": {
            "pid": 123,
            "target": "http://localhost:3300",
            "public_url": "https://voice.example.trycloudflare.com",
        },
        "livekit": {
            "pid": 456,
            "target": "http://localhost:7888",
            "public_url": "https://livekit.example.trycloudflare.com",
        },
        "public_playground_url": "https://voice.example.trycloudflare.com",
        "public_livekit_url": "wss://livekit.example.trycloudflare.com",
    }

    assert module.state_is_healthy(state) is False


def test_probe_local_endpoint_accepts_tcp_reachability(monkeypatch) -> None:
    module = load_module()

    class DummySocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    captured: list[tuple[tuple[str, int], float]] = []

    def fake_create_connection(address: tuple[str, int], timeout: float):
        captured.append((address, timeout))
        return DummySocket()

    monkeypatch.setattr(module.socket, "create_connection", fake_create_connection)

    assert module.probe_local_endpoint("http://localhost:3300") is True
    assert captured == [(("localhost", 3300), module.DEFAULT_HEALTH_TIMEOUT_SECONDS)]


def test_ensure_upnp_mapping_passes_requested_lease_seconds(monkeypatch) -> None:
    module = load_module()
    captured: list[list[str]] = []

    monkeypatch.setattr(module, "list_upnpc_state", lambda _bin: {"mappings": {}})

    def fake_run_checked(command: list[str], **_kwargs):
        captured.append(command)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module, "run_checked", fake_run_checked)

    module.ensure_upnp_mapping(
        "/opt/homebrew/bin/upnpc",
        protocol="TCP",
        external_port=443,
        internal_host="10.0.0.2",
        internal_port=64823,
        description="Viventium public HTTPS",
        lease_seconds=7200,
    )

    assert captured == [[
        "/opt/homebrew/bin/upnpc",
        "-a",
        "10.0.0.2",
        "64823",
        "443",
        "TCP",
        "7200",
    ]]


def test_tailscale_state_ready_requires_matching_dns_name(monkeypatch) -> None:
    module = load_module()

    monkeypatch.setattr(module, "resolve_binary", lambda _name: "/opt/homebrew/bin/tailscale")
    monkeypatch.setattr(module, "probe_local_endpoint", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        module,
        "tailscale_status_json",
        lambda _bin: {"Self": {"DNSName": "home-node.tail123.ts.net."}},
    )

    assert (
        module.tailscale_state_ready(
                {
                    "provider": "tailscale_tailnet_https",
                    "client": {"target": "http://localhost:3190", "public_url": "https://x"},
                    "tailscale": {"dns_name": "other-node.tail123.ts.net", "managed_ports": [443]},
                    "public_client_url": "https://home-node.tail123.ts.net",
                }
            )
            is False
    )


def test_cmd_start_cloudflare_saves_state_without_waiting_for_local_targets(monkeypatch, tmp_path: Path) -> None:
    module = load_module()

    class DummyLock:
        def fileno(self):
            return 0

        def close(self):
            return None

    monkeypatch.setattr(module, "with_lock", lambda _path: DummyLock())
    monkeypatch.setattr(module.fcntl, "flock", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "load_state", lambda _path: {})
    monkeypatch.setattr(module, "ensure_cloudflared", lambda _auto_install: "/usr/local/bin/cloudflared")
    monkeypatch.setattr(module, "stop_state", lambda _state: None)
    monkeypatch.setattr(
        module,
        "start_quick_tunnel",
        lambda *_args, **kwargs: (111 if "3300" in kwargs["target_url"] else 222, "https://example.trycloudflare.com"),
    )
    saved: dict[str, object] = {}
    monkeypatch.setattr(module, "save_state", lambda _path, state: saved.update(state))

    args = types.SimpleNamespace(
        state_file=str(tmp_path / "public-network.json"),
        log_dir=str(tmp_path / "logs"),
        client_port=3190,
        api_port=3180,
        playground_port=3300,
        livekit_port=7888,
        public_client_origin="",
        public_api_origin="",
        public_playground_origin="",
        public_livekit_url="",
        livekit_turn_tls_port=5349,
        livekit_node_ip="",
        caddy_data_dir="",
        provider="cloudflare_quick_tunnel",
        auto_install=False,
        timeout_seconds=5,
        command="start",
    )

    assert module.cmd_start(args) == 0

    assert saved["public_playground_url"] == "https://example.trycloudflare.com"
    assert saved["public_livekit_url"] == "wss://example.trycloudflare.com"


def test_cmd_refresh_mappings_renews_saved_public_edge_ports(monkeypatch, tmp_path: Path) -> None:
    module = load_module()
    captured: list[tuple[str, int, str, int, int]] = []
    saved: dict[str, object] = {}

    state = {
        "provider": "public_https_edge",
        "router": {
            "local_ip": "192.168.50.10",
            "mappings": [
                {
                    "protocol": "TCP",
                    "external_port": 80,
                    "internal_host": "192.168.50.10",
                    "internal_port": 64822,
                },
                {
                    "protocol": "TCP",
                    "external_port": 443,
                    "internal_host": "192.168.50.10",
                    "internal_port": 64823,
                },
            ],
        },
    }

    monkeypatch.setattr(module, "load_state", lambda _path: dict(state))
    monkeypatch.setattr(module, "resolve_binary", lambda _name: "/opt/homebrew/bin/upnpc")
    monkeypatch.setattr(module.time, "strftime", lambda *_args, **_kwargs: "2026-04-07T03:30:00Z")

    monkeypatch.setattr(
        module,
        "ensure_upnp_mapping",
        lambda _bin, *, protocol, external_port, internal_host, internal_port, description, lease_seconds=14400: captured.append(
            (protocol, external_port, internal_host, internal_port, lease_seconds)
        ),
    )
    monkeypatch.setattr(module, "save_state", lambda _path, data: saved.update(data))

    args = types.SimpleNamespace(
        state_file=str(tmp_path / "public-network.json"),
        upnp_lease_seconds=7200,
    )

    assert module.cmd_refresh_mappings(args) == 0
    assert captured == [
        ("TCP", 80, "192.168.50.10", 64822, 7200),
        ("TCP", 443, "192.168.50.10", 64823, 7200),
    ]
    assert saved["router"]["mapping_lease_seconds"] == 7200
    assert saved["router"]["last_refreshed_at"] == "2026-04-07T03:30:00Z"


def test_cmd_start_tailscale_derives_public_urls_and_node_ip(monkeypatch, tmp_path: Path) -> None:
    module = load_module()

    class DummyLock:
        def fileno(self):
            return 0

        def close(self):
            return None

    monkeypatch.setattr(module, "with_lock", lambda _path: DummyLock())
    monkeypatch.setattr(module.fcntl, "flock", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "load_state", lambda _path: {})
    monkeypatch.setattr(module, "ensure_tailscale", lambda _auto_install: "/opt/homebrew/bin/tailscale")
    monkeypatch.setattr(module, "tailscale_status_json", lambda _bin: {"Self": {"DNSName": "home-node.tail123.ts.net."}})
    monkeypatch.setattr(module, "tailscale_dns_name", lambda _status: "home-node.tail123.ts.net")
    monkeypatch.setattr(module, "tailscale_ipv4", lambda _bin, _status: "100.101.102.103")
    configured: list[tuple[int, str]] = []
    monkeypatch.setattr(
        module,
        "configure_tailscale_https_proxy",
        lambda _bin, *, public_port, target_url: configured.append((public_port, target_url)),
    )
    saved: dict[str, object] = {}
    monkeypatch.setattr(module, "save_state", lambda _path, state: saved.update(state))

    args = types.SimpleNamespace(
        state_file=str(tmp_path / "public-network.json"),
        log_dir=str(tmp_path / "logs"),
        client_port=3190,
        api_port=3180,
        playground_port=3300,
        livekit_port=7888,
        public_client_origin="",
        public_api_origin="",
        public_playground_origin="",
        public_livekit_url="",
        livekit_turn_tls_port=5349,
        livekit_node_ip="",
        caddy_data_dir="",
        provider="tailscale_tailnet_https",
        auto_install=False,
        timeout_seconds=5,
        command="start",
    )

    assert module.cmd_start(args) == 0

    assert configured == [
        (443, "http://localhost:3190"),
        (8443, "http://localhost:3180"),
        (3443, "http://localhost:3300"),
        (7443, "http://localhost:7888"),
    ]
    assert saved["public_client_url"] == "https://home-node.tail123.ts.net"
    assert saved["public_api_url"] == "https://home-node.tail123.ts.net:8443"
    assert saved["public_playground_url"] == "https://home-node.tail123.ts.net:3443"
    assert saved["public_livekit_url"] == "wss://home-node.tail123.ts.net:7443"
    assert saved["livekit_node_ip"] == "100.101.102.103"


def test_cmd_start_netbird_preserves_explicit_livekit_node_ip(monkeypatch, tmp_path: Path) -> None:
    module = load_module()

    class DummyLock:
        def fileno(self):
            return 0

        def close(self):
            return None

    monkeypatch.setattr(module, "with_lock", lambda _path: DummyLock())
    monkeypatch.setattr(module.fcntl, "flock", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "load_state", lambda _path: {})
    monkeypatch.setattr(module, "ensure_caddy", lambda _auto_install: "/opt/homebrew/bin/caddy")
    monkeypatch.setattr(module, "pick_caddy_admin_port", lambda: 2019)
    monkeypatch.setattr(module, "start_caddy_process", lambda *_args, **_kwargs: 999)
    monkeypatch.setattr(module, "trust_caddy_root", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(module, "derive_local_ip_from_hostname", lambda _hostname: "10.0.0.99")
    saved: dict[str, object] = {}
    monkeypatch.setattr(module, "save_state", lambda _path, state: saved.update(state))

    args = types.SimpleNamespace(
        state_file=str(tmp_path / "public-network.json"),
        log_dir=str(tmp_path / "logs"),
        client_port=3190,
        api_port=3180,
        playground_port=3300,
        livekit_port=7888,
        public_client_origin="https://app.mesh.example",
        public_api_origin="https://app.mesh.example:8443",
        public_playground_origin="https://app.mesh.example:3443",
        public_livekit_url="wss://app.mesh.example:7443",
        livekit_turn_tls_port=5349,
        livekit_node_ip="100.64.0.12",
        caddy_data_dir="",
        provider="netbird_selfhosted_mesh",
        auto_install=False,
        timeout_seconds=5,
        command="start",
    )

    assert module.cmd_start(args) == 0

    assert saved["public_client_url"] == "https://app.mesh.example"
    assert saved["public_api_url"] == "https://app.mesh.example:8443"
    assert saved["public_playground_url"] == "https://app.mesh.example:3443"
    assert saved["public_livekit_url"] == "wss://app.mesh.example:7443"
    assert saved["livekit_node_ip"] == "100.64.0.12"


def test_cmd_start_public_https_edge_autogenerates_sslip_origins_and_media_mappings(
    monkeypatch, tmp_path: Path
) -> None:
    module = load_module()

    class DummyLock:
        def fileno(self):
            return 0

        def close(self):
            return None

    monkeypatch.setattr(module, "with_lock", lambda _path: DummyLock())
    monkeypatch.setattr(module.fcntl, "flock", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "load_state", lambda _path: {})
    monkeypatch.setattr(module, "ensure_caddy", lambda _auto_install: "/opt/homebrew/bin/caddy")
    monkeypatch.setattr(module, "ensure_upnpc", lambda _auto_install: "/opt/homebrew/bin/upnpc")
    monkeypatch.setattr(
        module,
        "resolve_binary",
        lambda name: "/opt/homebrew/bin/upnpc" if name == "upnpc" else None,
    )
    monkeypatch.setattr(
        module,
        "list_upnpc_state",
        lambda _bin: {"external_ip": "203.0.113.42", "local_ip": "192.168.50.10", "mappings": {}},
    )
    monkeypatch.setattr(module, "discover_public_ipv4", lambda _bin=None: "203.0.113.42")
    monkeypatch.setattr(module, "pick_caddy_admin_port", lambda: 2019)
    ports = iter([4080, 4443])
    monkeypatch.setattr(module, "pick_free_port", lambda: next(ports))
    created_mappings: list[tuple[str, int, int]] = []
    monkeypatch.setattr(
        module,
        "ensure_upnp_mapping",
        lambda _bin, *, protocol, external_port, internal_host, internal_port, description, lease_seconds=14400: created_mappings.append(
            (protocol, external_port, internal_port)
        ),
    )
    monkeypatch.setattr(module, "start_caddy_process", lambda *_args, **_kwargs: 777)
    written_configs: dict[str, str] = {}

    original_write_text = Path.write_text

    def capture_write_text(self: Path, text: str, encoding: str | None = None):
        written_configs[str(self)] = text
        return original_write_text(self, text, encoding=encoding)

    monkeypatch.setattr(Path, "write_text", capture_write_text)
    waited: list[tuple[list[str], int, int]] = []
    monkeypatch.setattr(
        module,
        "wait_for_public_caddy_hosts",
        lambda hostnames, *, https_port, timeout_seconds: waited.append((hostnames, https_port, timeout_seconds)),
    )
    monkeypatch.setattr(
        module,
        "resolve_public_edge_livekit_cert_pair",
        lambda _data_dir, _hostname: ("/tmp/livekit-turn.crt", "/tmp/livekit-turn.key"),
    )
    monkeypatch.setattr(
        module,
        "ensure_directory_identity",
        lambda _state_path: {
            "instance_id": "instance-123",
            "public_key_fingerprint": "sha256:test-fingerprint",
            "public_key_pem": "PUBLIC-KEY",
            "registration_algorithm": "rsa-sha256",
        },
    )
    saved: dict[str, object] = {}
    monkeypatch.setattr(module, "save_state", lambda _path, state: saved.update(state))

    args = types.SimpleNamespace(
        state_file=str(tmp_path / "public-network.json"),
        log_dir=str(tmp_path / "logs"),
        client_port=3190,
        api_port=3180,
        playground_port=3300,
        livekit_port=7888,
        livekit_tcp_port=7889,
        livekit_udp_port=7890,
        livekit_turn_tls_port=5349,
        public_client_origin="",
        public_api_origin="",
        public_playground_origin="",
        public_livekit_url="",
        livekit_node_ip="",
        caddy_data_dir="",
        provider="public_https_edge",
        auto_install=False,
        timeout_seconds=5,
        command="start",
    )

    assert module.cmd_start(args) == 0

    assert created_mappings == [
        ("TCP", 80, 4080),
        ("TCP", 443, 4443),
        ("TCP", 7889, 7889),
        ("UDP", 7890, 7890),
        ("TCP", 5349, 5349),
    ]
    assert waited == [
        (
            [
                "app.203.0.113.42.sslip.io",
                "api.203.0.113.42.sslip.io",
                "playground.203.0.113.42.sslip.io",
                "livekit.203.0.113.42.sslip.io",
            ],
            4443,
            5,
        )
    ]
    assert saved["public_client_url"] == "https://app.203.0.113.42.sslip.io"
    assert saved["public_api_url"] == "https://api.203.0.113.42.sslip.io"
    assert saved["public_playground_url"] == "https://playground.203.0.113.42.sslip.io"
    assert saved["public_livekit_url"] == "wss://livekit.203.0.113.42.sslip.io"
    assert saved["livekit_node_ip"] == "203.0.113.42"
    assert saved["directory_instance_id"] == "instance-123"
    assert saved["directory_public_key_fingerprint"] == "sha256:test-fingerprint"
    assert (
        saved["directory_well_known_url"]
        == "https://app.203.0.113.42.sslip.io/.well-known/viventium-instance.json"
    )
    config_path = str((tmp_path / "public-network.Caddyfile"))
    assert "handle /.well-known/viventium-instance.json" in written_configs[config_path]
    assert "instance-123" in written_configs[config_path]
    assert "PUBLIC-KEY" in written_configs[config_path]
    assert saved["livekit_turn_domain"] == "livekit.203.0.113.42.sslip.io"
    assert saved["livekit_turn_tls_port"] == 5349
    assert saved["livekit_turn_cert_file"] == "/tmp/livekit-turn.crt"
    assert saved["livekit_turn_key_file"] == "/tmp/livekit-turn.key"


def test_cmd_start_persists_error_state_when_remote_access_bootstrap_fails(monkeypatch, tmp_path: Path) -> None:
    module = load_module()

    class DummyLock:
        def fileno(self):
            return 0

        def close(self):
            return None

    monkeypatch.setattr(module, "with_lock", lambda _path: DummyLock())
    monkeypatch.setattr(module.fcntl, "flock", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "load_state", lambda _path: {})

    def fail_public_edge(*_args, **_kwargs):
        raise RuntimeError("Router already forwards TCP 80 to 10.88.111.46:50779")

    monkeypatch.setattr(module, "start_public_https_edge", fail_public_edge)

    args = types.SimpleNamespace(
        state_file=str(tmp_path / "public-network.json"),
        log_dir=str(tmp_path / "logs"),
        client_port=3190,
        api_port=3180,
        playground_port=3300,
        livekit_port=7888,
        livekit_tcp_port=7889,
        livekit_udp_port=7890,
        livekit_turn_tls_port=5349,
        public_client_origin="",
        public_api_origin="",
        public_playground_origin="",
        public_livekit_url="",
        livekit_node_ip="",
        caddy_data_dir="",
        provider="public_https_edge",
        auto_install=False,
        timeout_seconds=5,
        command="start",
    )

    with pytest.raises(RuntimeError, match="Router already forwards TCP 80"):
        module.cmd_start(args)

    saved = json.loads((tmp_path / "public-network.json").read_text(encoding="utf-8"))
    assert saved["provider"] == "public_https_edge"
    assert saved["last_error"].startswith("Router already forwards TCP 80")


def test_render_caddyfile_can_serve_directory_instance_document() -> None:
    module = load_module()

    caddyfile = module.render_caddyfile(
        admin_port=2019,
        surfaces=[("app.example.com", 3190)],
        tls_internal=False,
        http_port=4080,
        https_port=4443,
        well_known_bodies={"app.example.com": '{"app":"Viventium"}'},
    )

    assert "handle /.well-known/viventium-instance.json" in caddyfile
    assert 'header Content-Type application/json' in caddyfile
    assert 'respond "{\\"app\\":\\"Viventium\\"}" 200' in caddyfile


def test_parse_args_uses_remote_tunnel_timeout_env(monkeypatch) -> None:
    module = load_module()
    monkeypatch.setenv("VIVENTIUM_REMOTE_CALL_TUNNEL_TIMEOUT_SECONDS", "165")
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "remote_call_tunnel.py",
            "start",
            "--state-file",
            "/tmp/public-network.json",
            "--log-dir",
            "/tmp/logs",
            "--client-port",
            "3190",
            "--api-port",
            "3180",
            "--playground-port",
            "3300",
            "--livekit-port",
            "7888",
        ],
    )

    args = module.parse_args()

    assert args.timeout_seconds == 165
