from __future__ import annotations

import importlib.util
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
        lambda _bin: {"external_ip": "199.7.147.132", "local_ip": "10.88.111.46", "mappings": {}},
    )
    monkeypatch.setattr(module, "discover_public_ipv4", lambda _bin=None: "199.7.147.132")
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
                "app.199.7.147.132.sslip.io",
                "api.199.7.147.132.sslip.io",
                "playground.199.7.147.132.sslip.io",
                "livekit.199.7.147.132.sslip.io",
            ],
            4443,
            5,
        )
    ]
    assert saved["public_client_url"] == "https://app.199.7.147.132.sslip.io"
    assert saved["public_api_url"] == "https://api.199.7.147.132.sslip.io"
    assert saved["public_playground_url"] == "https://playground.199.7.147.132.sslip.io"
    assert saved["public_livekit_url"] == "wss://livekit.199.7.147.132.sslip.io"
    assert saved["livekit_node_ip"] == "199.7.147.132"
    assert saved["livekit_turn_domain"] == "livekit.199.7.147.132.sslip.io"
    assert saved["livekit_turn_tls_port"] == 5349
    assert saved["livekit_turn_cert_file"] == "/tmp/livekit-turn.crt"
    assert saved["livekit_turn_key_file"] == "/tmp/livekit-turn.key"


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
